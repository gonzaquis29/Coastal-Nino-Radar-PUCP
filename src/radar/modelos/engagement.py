"""Modelo de engagement de los videos de YouTube (docs/modelos/engagement.md, definición aprobada el 22-nov).

Uso: python -m radar.modelos.engagement variables   # sin red; minilm y el semáforo una vez; reanudable
     python -m radar.modelos.engagement entrenar    # solo el entrenamiento: M0, validación cruzada por canal, elección
     python -m radar.modelos.engagement evaluar     # la prueba, UNA vez: M1 a M6 (--repetir para volver a escribirla)
     python -m radar.modelos.engagement cercania    # V1 a V5: la cercanía en videos frente a controles (sección 8)
Requiere pip install -e ".[nlp]".

Las variables por video (con ids) van a data/processed/youtube/ con la fecha del corte, así que vencen con los datos
de YouTube (`radar.youtube.borrar`). Los resultados (solo agregados, sin ids ni textos) van a data/processed/modelos/.
"""

import argparse
import collections
import csv
import datetime as dt
import json
import logging
import math
import os
import sys
import time

import numpy as np

from radar import config
from radar.comun.archivos import anexar_csv, escribir_csv, guardar_json, leer_csv, leer_json, reparar_csv
from radar.comun.registro import configurar
from radar.comun.texto import ahora
from radar.modelos import cercania
from radar.modelos import rasgos as rg
from radar.noticias.viabilidad import criterio, reporte
from radar.youtube import almacen, canales, filtro

log = logging.getLogger(__name__)

PRUEBA = "Modelo de engagement"
INFO = "Modelo de engagement (informativo)"
SEMILLA = config.SEMILLA_MUESTRAS
GRUPOS_CV = 5
REPLICAS = 1000  # bootstrap por canal
PERMUTACIONES = 30  # importancia en la prueba
PERMUTACIONES_CV = 10  # M5
LOTE = 20  # videos por escritura en `variables`
ALFAS_RIDGE = (0.1, 1, 10, 100)
PROFUNDIDADES = (2, 3)
ARBOLES = (100, 200, 300)
TASA_APRENDIZAJE = 0.05
HOJA_MINIMA = 20
ALFA_POISSON_LINEAL = 1e-3  # M4 con la familia lineal (informativo)
TOPICO_MAXIMO = 0.50  # M0
MINIMO_CON_DATOS = 30  # "alguna no coincide" entra solo con ≥ 30 videos del entrenamiento con afirmaciones
SPEARMAN_MINIMO = 0.20  # M1
MES_PERSISTENCIA = 8  # B0: la mediana del último mes del entrenamiento
MESES_MOVILES = (9, 10, 11)  # M6
NO_COINCIDE = frozenset({"rojo", "amarillo"})
SIN_AFIRMACIONES = "sin_afirmaciones"

TIPO_VARIABLES = "engagement-variables"
COLUMNAS_VARIABLES = (
    "id", "canal", "fecha", "particion", "tipo", "categoria", "vistas", "likes", "comentarios", "suscriptores",
    "videos_canal", "canal_peru", "duracion", "fin_semana", "diurno", "enlaza_gob", "mayusculas", "exclamaciones",
    "emojis", "pregunta", "palabras_titulo", "magnitud", "palabras_texto", "tipo_texto", "coseno", "color_reglas",
    "topico", "coseno_topico",
)  # fmt: skip
COLUMNAS_DETALLE = ("modelo", "grupo", "n", "mae", "mae_por_mil", "r2", "sesgo", "spearman", "spearman_por_tipo")
COLUMNAS_IMPORTANCIA = ("grupo", "variables", "aumento_mae", "ic_inf", "ic_sup", "signo_cv", "estable")
COLUMNAS_MESES = ("mes", "n", "entrenamiento", "mae", "sesgo", "spearman_por_tipo", "mae_b0")
COLUMNAS_VALIDACION = ("prueba", "criterio", "valor", "umbral", "pasa", "detalle")

CONTROLES = (
    "log_suscriptores", "log_videos_canal", "canal_peru", "log_duracion",
    *(f"tipo_{t}" for t in rg.TIPOS_CANAL), *(f"cat_{c}" for c in (*rg.CATEGORIAS, "otra")), "fin_semana", "diurno",
)  # fmt: skip
RASGOS = ("mayusculas", "exclamaciones", "emojis", "pregunta", "palabras_titulo", "magnitud")


def ruta_variables(corte):
    fecha = dt.date.fromisoformat(corte) if isinstance(corte, str) else corte
    return almacen.ruta(TIPO_VARIABLES, fecha=fecha, extension="csv", base=config.DIR_YOUTUBE)


def ruta_resultado(nombre):
    return config.DIR_MODELOS / nombre


# ---------------------------------------------------------------- muestra y variables sin modelo


def muestra():
    """(videos que entran con su canal y tipo, fecha del corte, descartes por motivo)."""
    videos, canales_por_id, tipos = almacen.ultimos("videos"), almacen.ultimos("canales"), canales.tipos()
    corte = max(v["descargado"] for v in videos.values())
    entran, descartes = [], collections.Counter()
    for v in sorted(videos.values(), key=lambda x: x["id"]):
        canal = canales_por_id.get(v["canal"])
        if not filtro.pasa(v, canal):
            continue
        motivo = rg.motivo_fuera(v, canal, corte)
        if motivo:
            descartes[motivo] += 1
            continue
        entran.append((v, canal or {}, (tipos.get(v["canal"]) or {}).get("tipo", "otros")))
    return entran, corte, descartes


def fila_base(video, canal, tipo):
    fecha = filtro.fecha_lima(video["publicado"])
    fin_semana, diurno = rg.momento(video["publicado"])
    return {
        "id": video["id"],
        "canal": video["canal"],
        "fecha": fecha.isoformat(),
        "particion": rg.particion(fecha),
        "tipo": tipo,
        "categoria": rg.categoria(video.get("categoria")),
        "vistas": video["vistas"],
        "likes": video["likes"],
        "comentarios": video["comentarios"],
        "suscriptores": canal.get("suscriptores") or 0,
        "videos_canal": canal.get("videos") or 0,
        "canal_peru": canal.get("pais") == filtro.PAIS_PERU,
        "duracion": rg.segundos(video.get("duracion")) or 0,
        "fin_semana": fin_semana,
        "diurno": diurno,
        "enlaza_gob": rg.enlaza_gob(video.get("enlaces")),
        **rg.rasgos_titulo(video.get("titulo")),
    }


# ---------------------------------------------------------------- variables con minilm


def centroides_topicos():
    """(ids de tópico, matriz normalizada) con el centroide minilm de las notas de cada tópico."""
    from radar.nlp import embeddings

    csv.field_size_limit(2**31 - 1)  # la bolsa de lemas de una nota larga pasa del límite por defecto
    topico = {(f["medio"], f["id"]): int(f["topico"]) for f in leer_csv(config.DIR_NLP / "topicos-notas.csv")}
    sumas, cuentas = {}, collections.Counter()
    with open(config.DIR_NLP / "topicos-lectura.csv", encoding="utf-8", newline="") as archivo:
        for f in csv.DictReader(archivo):
            t = topico.get((f["medio"], f["id"]))
            if t is None or not f["vector"]:
                continue
            v = embeddings.de_base64(f["vector"])
            sumas[t] = sumas.get(t, 0) + v
            cuentas[t] += 1
    if not sumas:
        raise SystemExit("Faltan los tópicos de las notas: python -m radar.nlp.topicos ajustar")
    ids = sorted(sumas)
    matriz = np.stack([sumas[t] / cuentas[t] for t in ids])
    return ids, embeddings._normalizar(matriz)


class Medidor:
    """El semáforo (cercanía y capa 5) y el tópico más cercano, con minilm cargado una sola vez."""

    def __init__(self):
        os.environ.setdefault("HF_HUB_OFFLINE", "1")
        from radar.nlp import embeddings, semaforo

        self.semaforo = semaforo.Semaforo()
        self.minilm = embeddings.Modelo("minilm")
        self.normalizar = embeddings._normalizar
        self.ids_topicos, self.centroides = centroides_topicos()

    def medir(self, texto, fecha):
        m = self.semaforo.medir(texto, fecha)
        fila = {"tipo_texto": m["tipo_texto"], "palabras_texto": m["palabras"], "coseno": m["coseno"],
                "color_reglas": m["color_reglas"], "topico": None, "coseno_topico": None}  # fmt: skip
        tramos = self.minilm.tramos(texto) if m["tipo_texto"] != "insuficiente" else []
        if tramos:
            vector = self.normalizar(self.minilm.embeber(tramos).mean(axis=0))
            cosenos = self.centroides @ vector
            i = int(cosenos.argmax())
            fila |= {"topico": self.ids_topicos[i], "coseno_topico": round(float(cosenos[i]), 4)}
        return fila


def variables(limite=None):
    entran, corte, descartes = muestra()
    destino = ruta_variables(corte)
    if reparar_csv(destino, COLUMNAS_VARIABLES):
        log.info("Se quitó una línea a medias del corte anterior.")
    hechos = {f["id"] for f in leer_csv(destino)}
    pendientes = [x for x in entran if x[0]["id"] not in hechos][:limite]
    log.info(f"{len(entran)} videos entran (corte {corte}); descartes: {dict(descartes)}. "
             f"Hechos {len(hechos)}, faltan {len(pendientes)}.")  # fmt: skip
    if not pendientes:
        return destino
    medidor = Medidor()
    inicio, lote = time.monotonic(), []
    try:
        for i, (video, canal, tipo) in enumerate(pendientes, 1):
            fila = fila_base(video, canal, tipo)
            texto = rg.texto_para_distancia(video.get("titulo"), video.get("descripcion"))
            lote.append(fila | medidor.medir(texto, fila["fecha"]))
            if len(lote) >= LOTE or i == len(pendientes):
                anexar_csv(destino, COLUMNAS_VARIABLES, lote)
                lote = []
                ritmo = (time.monotonic() - inicio) / i
                log.info(f"  {i}/{len(pendientes)} videos; faltan ~{ritmo * (len(pendientes) - i) / 60:.1f} min")
    except KeyboardInterrupt:
        if lote:
            anexar_csv(destino, COLUMNAS_VARIABLES, lote)
        log.info("Cortado: lo medido quedó guardado; vuelve a correrlo para seguir.")
        raise
    return destino


# ---------------------------------------------------------------- matrices


def _num(valor):
    return float("nan") if valor in ("", None) else float(valor)


def _si(valor):
    return valor in ("1", 1, True, "True")


def cargar_variables():
    previos = almacen.archivos(TIPO_VARIABLES, bases=(config.DIR_YOUTUBE,))
    if not previos:
        raise SystemExit("Faltan las variables: python -m radar.modelos.engagement variables")
    almacen.comprobar_vigencia()
    return leer_csv(previos[-1])


def columnas_de(eleccion):
    contenido = {"cercania": ["coseno"] + (["no_coincide"] if eleccion["con_no_coincide"] else []),
                 "rasgos": list(RASGOS), "enlaces": ["enlaza_gob"]}  # fmt: skip
    if eleccion["con_topicos"]:
        contenido["topicos"] = [f"topico_{t}" for t in eleccion["topicos"]]
    return contenido


def valores(fila, topicos):
    v = {
        "log_suscriptores": math.log1p(_num(fila["suscriptores"])),
        "log_videos_canal": math.log1p(_num(fila["videos_canal"])),
        "canal_peru": _si(fila["canal_peru"]),
        "log_duracion": math.log(max(_num(fila["duracion"]), 1)),
        **{f"tipo_{t}": fila["tipo"] == t for t in rg.TIPOS_CANAL},
        **{f"cat_{c}": fila["categoria"] == c for c in (*rg.CATEGORIAS, "otra")},
        "fin_semana": _si(fila["fin_semana"]),
        "diurno": _si(fila["diurno"]),
        "coseno": _num(fila["coseno"]),
        "no_coincide": fila["color_reglas"] in NO_COINCIDE,
        "enlaza_gob": _si(fila["enlaza_gob"]),
        **{k: _num(fila[k]) if k in ("mayusculas", "exclamaciones", "emojis", "palabras_titulo") else _si(fila[k])
           for k in RASGOS},
    }  # fmt: skip
    topico = fila["topico"]
    for t in topicos:
        v[f"topico_{t}"] = topico != "" and int(topico) == t
    return v


class Datos:
    """Las filas de una partición con su matriz completa, el objetivo y los grupos."""

    def __init__(self, filas, eleccion):
        self.filas = filas
        self.grupos_contenido = columnas_de(eleccion)
        self.columnas = list(CONTROLES) + [c for g in self.grupos_contenido.values() for c in g]
        vals = [valores(f, eleccion["topicos"]) for f in filas]
        self.X = np.array([[float(v[c]) for c in self.columnas] for v in vals], float)
        self.exitos = np.array([_num(f["likes"]) + _num(f["comentarios"]) for f in filas])
        self.vistas = np.array([_num(f["vistas"]) for f in filas])
        self.y = rg.objetivo(self.exitos, self.vistas, eleccion["alfa"], eleccion["beta"])
        self.canal = np.array([f["canal"] for f in filas])
        self.tipo = np.array([f["tipo"] for f in filas])
        self.mes = np.array([int(f["fecha"][5:7]) for f in filas])
        self.n_controles = len(CONTROLES)

    def controles(self):
        return self.X[:, : self.n_controles]

    def indices(self, grupo):
        return [self.columnas.index(c) for c in self.grupos_contenido[grupo]]

    def sub(self, mascara):
        nuevo = object.__new__(Datos)
        nuevo.__dict__ = self.__dict__.copy()
        for k in ("X", "exitos", "vistas", "y", "canal", "tipo", "mes"):
            setattr(nuevo, k, getattr(self, k)[mascara])
        nuevo.filas = [f for f, m in zip(self.filas, mascara, strict=True) if m]
        return nuevo


# ---------------------------------------------------------------- modelos


def grilla(familia):
    if familia == "L":
        return [{"alfa": a} for a in ALFAS_RIDGE]
    return [{"profundidad": p, "arboles": n} for p in PROFUNDIDADES for n in ARBOLES]


def hacer(familia, h, poisson=False):
    from sklearn.ensemble import HistGradientBoostingRegressor
    from sklearn.impute import SimpleImputer
    from sklearn.linear_model import PoissonRegressor, Ridge
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler

    if familia == "L":
        final = PoissonRegressor(alpha=ALFA_POISSON_LINEAL, max_iter=1000) if poisson else Ridge(alpha=h["alfa"])
        return make_pipeline(SimpleImputer(strategy="median"), StandardScaler(), final)
    return HistGradientBoostingRegressor(
        loss="poisson" if poisson else "squared_error", max_depth=h["profundidad"], max_iter=h["arboles"],
        learning_rate=TASA_APRENDIZAJE, min_samples_leaf=HOJA_MINIMA, early_stopping=False, random_state=SEMILLA,
    )  # fmt: skip


def ajustar(familia, h, X, y):
    modelo = hacer(familia, h)
    modelo.fit(X, y)
    return modelo


def ajustar_poisson(familia, h, X, exitos, vistas):
    """M4: el conteo con las vistas como exposición (tasa con peso = vistas, equivalente a Poisson con offset)."""
    modelo = hacer(familia, h, poisson=True)
    tasa_ = exitos / vistas
    if familia == "L":
        modelo.fit(X, tasa_, poissonregressor__sample_weight=vistas)
    else:
        modelo.fit(X, tasa_, sample_weight=vistas)
    return modelo


def pliegues(grupos):
    from sklearn.model_selection import GroupKFold

    return list(GroupKFold(n_splits=GRUPOS_CV).split(np.zeros(len(grupos)), groups=grupos))


def fuera_de_pliegue(familia, h, X, y, divisiones):
    prediccion = np.zeros(len(y))
    for tr, va in divisiones:
        prediccion[va] = ajustar(familia, h, X[tr], y[tr]).predict(X[va])
    return prediccion


def buscar(familia, X, y, divisiones, tipos):
    """El mejor hiperparámetro de una familia por el MAE fuera de pliegue."""
    resultados = []
    for h in grilla(familia):
        p = fuera_de_pliegue(familia, h, X, y, divisiones)
        resultados.append({"h": h, "mae": rg.mae(p, y), "spearman_por_tipo": rg.spearman_por_tipo(p, y, tipos)})
    return min(resultados, key=lambda r: r["mae"]), resultados


# ---------------------------------------------------------------- entrenar (solo el entrenamiento)


def entrenar():
    filas = cargar_variables()
    ent = [f for f in filas if f["particion"] == "entrenamiento"]
    alfa, beta = rg.beta_binomial(
        [_num(f["likes"]) + _num(f["comentarios"]) for f in ent], [_num(f["vistas"]) for f in ent]
    )
    topicos = sorted({int(f["topico"]) for f in filas if f["topico"] != ""})
    cuenta_topicos = collections.Counter(f["topico"] for f in ent if f["topico"] != "")
    mayor = max(cuenta_topicos.values()) / sum(cuenta_topicos.values())
    con_datos = sum(f["color_reglas"] not in ("", SIN_AFIRMACIONES) for f in ent)
    eleccion = {"alfa": alfa, "beta": beta, "topicos": topicos, "con_topicos": mayor <= TOPICO_MAXIMO,
                "con_no_coincide": con_datos >= MINIMO_CON_DATOS}  # fmt: skip
    d = Datos(ent, eleccion)
    divisiones = pliegues(d.canal)
    familias = {}
    for familia in ("L", "G"):
        mejor, todos = buscar(familia, d.X, d.y, divisiones, d.tipo)
        familias[familia] = {"mejor": mejor, "grilla": todos}
        log.info(
            f"  {familia}: {mejor['h']} MAE de validación {mejor['mae']:.4f}, Spearman {mejor['spearman_por_tipo']:.3f}"
        )
    elegida = min(familias, key=lambda f: familias[f]["mejor"]["mae"])
    b1, _ = buscar(elegida, d.controles(), d.y, divisiones, d.tipo)
    log.info(f"  B1 ({elegida}, solo controles): {b1['h']} MAE {b1['mae']:.4f}, Spearman {b1['spearman_por_tipo']:.3f}")
    eleccion |= {
        "familia": elegida, "h": familias[elegida]["mejor"]["h"], "h_b1": b1["h"],
        "cv": {f: {"mae": v["mejor"]["mae"], "spearman_por_tipo": v["mejor"]["spearman_por_tipo"], "h": v["mejor"]["h"]}
               for f, v in familias.items()},
        "cv_b1": {"mae": b1["mae"], "spearman_por_tipo": b1["spearman_por_tipo"]},
        "cv_b0": rg.mae(np.full(len(d.y), np.median(d.y)), d.y),
        "m0": {"mayor_topico": mayor, "con_afirmaciones": con_datos}, "n_entrenamiento": len(ent),
        "fecha": ahora().isoformat(timespec="seconds"),
    }  # fmt: skip
    guardar_json(ruta_resultado("engagement-eleccion.json"), eleccion)
    filas_v = [
        criterio(PRUEBA, "M0 tópicos útiles en videos (mayor tópico del entrenamiento)", round(mayor, 3),
                 f"<= {TOPICO_MAXIMO}", mayor <= TOPICO_MAXIMO,
                 f"{len(topicos)} tópicos; {'entran' if mayor <= TOPICO_MAXIMO else 'salen del modelo'}"),
        criterio(INFO, "Videos del entrenamiento con afirmaciones con datos", con_datos, f">= {MINIMO_CON_DATOS}",
                 con_datos >= MINIMO_CON_DATOS,
                 "entra 'alguna no coincide'" if con_datos >= MINIMO_CON_DATOS else "'alguna no coincide' se omite"),
        criterio(INFO, "Elección por validación cruzada (MAE)", elegida, "menor MAE", True,
                 "; ".join(f"{f}: {v['mejor']['mae']:.4f}" for f, v in familias.items())
                 + f"; B1: {b1['mae']:.4f}; B0: {eleccion['cv_b0']:.4f}"),
    ]  # fmt: skip
    return eleccion, filas_v


# ---------------------------------------------------------------- evaluar (la prueba, una vez)


def metricas(nombre, grupo, prediccion, d):
    if not len(d.y):
        return None
    return {
        "modelo": nombre, "grupo": grupo, "n": len(d.y), "mae": round(rg.mae(prediccion, d.y), 4),
        "mae_por_mil": round(float(np.mean(np.abs(rg.tasa(prediccion) - d.exitos / d.vistas))) * 1000, 3),
        "r2": round(rg.r2(prediccion, d.y), 4), "sesgo": round(float(np.mean(prediccion - d.y)), 4),
        "spearman": round(rg.spearman(prediccion, d.y), 4),
        "spearman_por_tipo": round(rg.spearman_por_tipo(prediccion, d.y, d.tipo), 4),
    }  # fmt: skip


def importancia(modelo, X, y, indices, veces, semilla):
    """Aumento del MAE al permutar juntas las columnas de un grupo (media y percentiles 2,5 y 97,5)."""
    base = rg.mae(modelo.predict(X), y)
    azar = np.random.default_rng(semilla)
    aumentos = []
    for _ in range(veces):
        Xp = X.copy()
        orden = azar.permutation(len(y))
        Xp[:, indices] = X[orden][:, indices]
        aumentos.append(rg.mae(modelo.predict(Xp), y) - base)
    return float(np.mean(aumentos)), *(float(np.percentile(aumentos, q)) for q in (2.5, 97.5))


def evaluar(eleccion):
    filas = cargar_variables()
    ent = Datos([f for f in filas if f["particion"] == "entrenamiento"], eleccion)
    pru = Datos([f for f in filas if f["particion"] == "prueba"], eleccion)
    fam, h, h_b1 = eleccion["familia"], eleccion["h"], eleccion["h_b1"]
    modelo = ajustar(fam, h, ent.X, ent.y)
    pred = modelo.predict(pru.X)
    b1 = ajustar(fam, h_b1, ent.controles(), ent.y).predict(pru.controles())
    b0s = {"B0 mediana": np.full(len(pru.y), np.median(ent.y)),
           "B0 agosto": np.full(len(pru.y), np.median(ent.y[ent.mes == MES_PERSISTENCIA]))}  # fmt: skip
    nombre_b0 = min(b0s, key=lambda k: rg.mae(b0s[k], pru.y))  # la más exigente
    b0 = b0s[nombre_b0]
    # el rival predice la tasa: se pasa a logit para que su MAE, R² y sesgo estén en la escala del objetivo
    tasa_rival = np.clip(ajustar_poisson(fam, h, ent.X, ent.exitos, ent.vistas).predict(pru.X), 1e-6, 1 - 1e-6)
    rival = np.log(tasa_rival / (1 - tasa_rival))

    # bootstrap por canal
    m1, m2, m3, m4 = [], [], [], []
    for idx in rg.remuestras_por_grupo(pru.canal, REPLICAS, SEMILLA):
        y, t = pru.y[idx], pru.tipo[idx]
        sp = rg.spearman_por_tipo(pred[idx], y, t)
        m1.append(sp)
        m2.append(rg.mae(b0[idx], y) - rg.mae(pred[idx], y))
        m3.append(sp - rg.spearman_por_tipo(b1[idx], y, t))
        m4.append(sp - rg.spearman_por_tipo(rival[idx], y, t))
    v1 = rg.spearman_por_tipo(pred, pru.y, pru.tipo)
    v2 = rg.mae(b0, pru.y) - rg.mae(pred, pru.y)
    v3 = v1 - rg.spearman_por_tipo(b1, pru.y, pru.tipo)
    v4 = v1 - rg.spearman_por_tipo(rival, pru.y, pru.tipo)
    (i1, s1), (i2, s2), (i3, s3), (i4, s4) = (rg.intervalo(m) for m in (m1, m2, m3, m4))
    mejora = v2 / rg.mae(b0, pru.y) * 100
    nombre = {"L": "Ridge", "G": "Gradient boosting"}[fam]
    validacion = [
        criterio(PRUEBA, f"M1 orden: Spearman por tipo ({nombre})", round(v1, 3), f">= {SPEARMAN_MINIMO} e IC sin 0",
                 v1 >= SPEARMAN_MINIMO and i1 > 0, f"IC 95 % {i1:.3f} a {s1:.3f}"),
        criterio(PRUEBA, f"M2 error: MAE frente a {nombre_b0}", round(v2, 4), "IC de la mejora sin 0", i2 > 0,
                 f"MAE {rg.mae(pred, pru.y):.4f} frente a {rg.mae(b0, pru.y):.4f} ({mejora:+.1f} %); "
                 f"IC 95 % {i2:.4f} a {s2:.4f}"),
        criterio(PRUEBA, "M3 el contenido agrega: Spearman por tipo menos el de B1", round(v3, 3), "IC sin 0", i3 > 0,
                 f"B1 {rg.spearman_por_tipo(b1, pru.y, pru.tipo):.3f}; IC 95 % {i3:.3f} a {s3:.3f}"),
        criterio(INFO, "M4 objetivo B menos el rival C (Poisson), Spearman por tipo", round(v4, 3), "informativo",
                 True, f"C {rg.spearman_por_tipo(rival, pru.y, pru.tipo):.3f}; IC 95 % {i4:.3f} a {s4:.3f}"),
    ]  # fmt: skip

    # detalle por modelo y grupo
    nuevos = ~np.isin(pru.canal, np.unique(ent.canal))
    grupos = {"todos": np.ones(len(pru.y), bool), "medio": pru.tipo == "medio", "otros": pru.tipo == "otros",
              "oficial": pru.tipo == "oficial", "canal nuevo": nuevos, "canal visto": ~nuevos}  # fmt: skip
    detalle = []
    for nom, p in {nombre: pred, "B1 solo controles": b1, **b0s, "C Poisson": rival}.items():
        for g, m in grupos.items():
            fila = metricas(nom, g, p[m], pru.sub(m))
            if fila:
                detalle.append(fila)

    # importancia (prueba) y estabilidad de signo (M5, validación cruzada)
    divisiones = pliegues(ent.canal)
    signos = collections.defaultdict(list)
    for k, (tr, va) in enumerate(divisiones):
        m = ajustar(fam, h, ent.X[tr], ent.y[tr])
        for g in ent.grupos_contenido:
            signos[g].append(
                np.sign(importancia(m, ent.X[va], ent.y[va], ent.indices(g), PERMUTACIONES_CV, SEMILLA + k)[0])
            )
    tabla_imp = []
    for g in ent.grupos_contenido:
        media, inf, sup = importancia(modelo, pru.X, pru.y, pru.indices(g), PERMUTACIONES, SEMILLA)
        estable = len(set(signos[g])) == 1
        tabla_imp.append({"grupo": g, "variables": "|".join(ent.grupos_contenido[g]), "aumento_mae": round(media, 5),
                          "ic_inf": round(inf, 5), "ic_sup": round(sup, 5),
                          "signo_cv": "|".join(str(int(s)) for s in signos[g]), "estable": estable})  # fmt: skip
    inestables = [f["grupo"] for f in tabla_imp if not f["estable"]]
    validacion.append(criterio(INFO, "M5 grupos con el mismo signo en los 5 pliegues",
                               f"{len(tabla_imp) - len(inestables)}/{len(tabla_imp)}", "informativo", True,
                               f"inestables (no se interpretan): {', '.join(inestables) or 'ninguno'}"))  # fmt: skip

    # M6: origen móvil
    todos = Datos(filas, eleccion)
    meses = []
    for mes in MESES_MOVILES:
        antes, ahora_ = todos.mes < mes, todos.mes == mes
        if not ahora_.any():
            continue
        p = ajustar(fam, h, todos.X[antes], todos.y[antes]).predict(todos.X[ahora_])
        y, t = todos.y[ahora_], todos.tipo[ahora_]
        b0_mes = rg.mae(np.full(len(y), np.median(todos.y[antes])), y)
        meses.append({"mes": mes, "n": int(ahora_.sum()), "entrenamiento": int(antes.sum()),
                      "mae": round(rg.mae(p, y), 4), "sesgo": round(float(np.mean(p - y)), 4),
                      "spearman_por_tipo": round(rg.spearman_por_tipo(p, y, t), 4),
                      "mae_b0": round(b0_mes, 4)})  # fmt: skip
    validacion.append(criterio(INFO, "M6 origen móvil (MAE, sesgo y Spearman por mes)", len(meses), "informativo", True,
                               "; ".join(f"mes {m['mes']}: MAE {m['mae']} (B0 {m['mae_b0']}), sesgo {m['sesgo']}, "
                                         f"Spearman {m['spearman_por_tipo']}" for m in meses)))  # fmt: skip
    return validacion, detalle, tabla_imp, meses


# ---------------------------------------------------------------- línea de comandos


def guardar_validacion(filas):
    ruta = ruta_resultado("engagement-validacion.csv")
    corridas = {(f["prueba"], f["criterio"][:2]) for f in filas}
    previas = [f for f in leer_csv(ruta) if (f["prueba"], f["criterio"][:2]) not in corridas]
    escribir_csv(ruta, COLUMNAS_VALIDACION, previas + filas)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("etapa", choices=("variables", "entrenar", "evaluar", "cercania"))
    ap.add_argument("--limite", type=int, help="variables: solo los N primeros pendientes (ensayo)")
    ap.add_argument("--repetir", action="store_true", help="evaluar: vuelve a escribir la prueba ya evaluada")
    args = ap.parse_args(argv)
    configurar(f"modelos-engagement-{args.etapa}")
    inicio = ahora()
    try:
        if args.etapa == "variables":
            destino = variables(args.limite)
            log.info(f"Variables en {destino.name}")
            return 0
        if args.etapa == "cercania":
            filas = cercania.validar()
            guardar_validacion(filas)
            reporte(filas, [], inicio)
            return 0
        if args.etapa == "entrenar":
            eleccion, filas = entrenar()
            guardar_validacion(filas)
            reporte(filas, [], inicio)
            return 0
        eleccion = leer_json(ruta_resultado("engagement-eleccion.json"))
        if not eleccion:
            log.error("Falta la elección: python -m radar.modelos.engagement entrenar")
            return 1
        detalle_ruta = ruta_resultado("engagement-detalle.csv")
        if detalle_ruta.exists() and not args.repetir:
            log.error(
                "La prueba ya se evaluó (se usa una sola vez). Para volver a escribirla: --repetir, y declararlo."
            )
            return 1
        validacion, detalle, imp, meses = evaluar(eleccion)
        escribir_csv(detalle_ruta, COLUMNAS_DETALLE, detalle)
        escribir_csv(ruta_resultado("engagement-importancia.csv"), COLUMNAS_IMPORTANCIA, imp)
        escribir_csv(ruta_resultado("engagement-meses.csv"), COLUMNAS_MESES, meses)
        guardar_validacion(validacion)
        reporte(validacion, [], inicio)
        log.info("\n" + "\n".join(json.dumps(f, ensure_ascii=False) for f in detalle if f["grupo"] == "todos"))
        return 0
    except almacen.Vencido as e:
        log.error(str(e))
        return 1
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    sys.exit(main())
