"""Recomendador híbrido (definición aprobada el 8-nov, docs/analitica/recomendador.md).

Parte oficial por reglas (comunicado vigente, sus párrafos del interés del perfil y los avisos de la macro-región) y
notas relacionadas en cascada: filtro de fecha, similitud minilm del titular y el resumen, premio por macro-región y
diversidad con MMR. Ningún parámetro se ajusta con datos. Se evalúa con los enlaces que cada medio pone entre sus
notas, desde notas sin ver que mencionan El Niño (no toca la reserva de T5). Sin red: solo notas.csv y data/oficial.

Ronda b (aprobada el 8-nov): la ronda a mostró que los editores enlazan sobre todo lo último que publicaron, así que
la frescura entra como regla de la cascada: primero las notas de los últimos DIAS_FRESCOS días ordenadas por el
híbrido, después el resto por fecha. DIAS_FRESCOS se calibra con la muestra A (ya vista: solo desarrollo) y se decide
con la muestra B, notas nuevas desde el 9-nov, el 18-nov junto con T5.

Uso: python -m radar.analitica.recomendador validar             # ronda a (muestra A)
     python -m radar.analitica.recomendador calibrar            # ronda b: elige DIAS_FRESCOS con la muestra A
     python -m radar.analitica.recomendador validar --ronda b   # ronda b: decide con la muestra B (18-nov)
"""

import argparse
import collections
import datetime as dt
import logging
import random
import statistics
import sys
import time

import numpy as np

from radar import config
from radar.comun.archivos import escribir_csv, leer_csv
from radar.comun.regiones import COSTA_CENTRO, COSTA_NORTE, LIMA_Y_CALLAO
from radar.comun.registro import configurar
from radar.comun.texto import ahora
from radar.nlp import candidatos, reranker, semaforo
from radar.noticias.validar_texto import marcar_vistas, notas_vistas
from radar.noticias.viabilidad import criterio, guardar, reporte
from radar.oficial.vigencia import Corpus
from radar.oficial.vocabulario import orden_nivel

log = logging.getLogger(__name__)

PRUEBA = "Recomendador: validación"
INFO = "Recomendador (informativo)"
MUESTRA = "recomendador-a-8nov"
INICIO = "2026-01-01"
INTERESES = ("pesca", "lluvias", "calor", "prevencion")  # el campo temas de radar.oficial
MACROREGIONES = (COSTA_NORTE, COSTA_CENTRO, LIMA_Y_CALLAO)
DIAS_PREVIOS = 90
PREMIO_REGION = 0.05
LAMBDA_MMR = 0.7
PRIMEROS_MMR = 50
NOTAS = 5
AUC_MINIMA = 0.60  # P
MEJORA_MINIMA = 0.05  # R1
TOLERANCIA_CONTENIDO = 0.02  # R2
MEDIOS_MINIMOS = 2.0  # R3
CONSULTA_MAXIMA_S = 2.0  # R4
CONSULTAS = 20
REMUESTREOS = 2000
SEMILLA = "recomendador-8nov"
METODOS = ("azar", "recientes", "contenido", "region", "hibrido")
# Ronda b
GRILLA_FRESCURA = (3, 7, 14, 30)  # días; empate: el menor
DIAS_FRESCOS = 3  # fijado con `calibrar` el 8-nov (muestra A); no se vuelve a ajustar
MUESTRA_B = "recomendador-b-18nov"
INICIO_B = "2026-11-09"  # notas nuevas: después de la última recolección usada en la ronda a
ORIGENES_MINIMOS_B = 30  # con menos, la ronda b es informativa


# ---------------------------------------------------------------- reglas (parte oficial)


def parrafos_de_interes(parrafos, doc_id, interes):
    """Párrafos del comunicado con ese tema, sin definiciones, Pacífico central ni duplicados."""
    return [p for p in parrafos if p["doc_id"] == doc_id and interes in p["temas"].split("|")
            and p["tipo"] != "definicion" and p["region_enso"] != "nino_3.4" and not p["duplicado_de"]]  # fmt: skip


def oficial(corpus, fecha, macroregion, interes, puntaje=None):
    """{comunicado, parrafos, avisos} que rigen; puntaje(textos) ordena los párrafos si se da."""
    if interes not in INTERESES:
        raise ValueError(f"interés desconocido: {interes}")
    comunicado = corpus.comunicado_vigente(fecha)
    parrafos = parrafos_de_interes(corpus.parrafos, comunicado["id"], interes) if comunicado else []
    if puntaje and parrafos:
        orden = np.argsort(-puntaje([p["texto"] for p in parrafos]), kind="stable")
        parrafos = [parrafos[i] for i in orden]
    avisos = sorted(corpus.avisos_aplicables(fecha, macroregion), key=lambda a: (-orden_nivel(a["nivel"]), a["id"]))
    return {"comunicado": comunicado, "parrafos": parrafos, "avisos": avisos}


# ---------------------------------------------------------------- notas (cascada)


def momento(nota):
    return dt.datetime.fromisoformat(nota["fecha_publicacion"])


def candidatas(catalogo, cuando, medio=None):
    """Índices del catálogo publicados en los DIAS_PREVIOS antes de `cuando` (y del medio, si se da)."""
    desde = cuando - dt.timedelta(DIAS_PREVIOS)
    return [
        i for i, n in enumerate(catalogo) if desde <= momento(n) < cuando and (medio is None or n["medio"] == medio)
    ]


def puntajes_region(cosenos, regiones, region):
    premio = np.array([PREMIO_REGION if region in MACROREGIONES and r == region else 0.0 for r in regiones])
    return cosenos + premio


def mmr(puntajes, vectores, k=NOTAS, lam=LAMBDA_MMR, primeros=PRIMEROS_MMR):
    """Orden completo: los k primeros por MMR entre los `primeros` mejores; el resto por puntaje."""
    orden = list(np.argsort(-puntajes, kind="stable"))
    grupo, elegidos = orden[:primeros], []
    while grupo and len(elegidos) < k:
        if elegidos:
            parecido = np.max(vectores[grupo] @ vectores[elegidos].T, axis=1)
        else:
            parecido = np.zeros(len(grupo))
        valor = lam * puntajes[grupo] - (1 - lam) * parecido
        elegidos.append(grupo.pop(int(np.argmax(valor))))
    return elegidos + [i for i in orden if i not in set(elegidos)]


def ordenar(metodo, cosenos, vectores, fechas, regiones, region, azar):
    """Orden (índices locales) de cada método."""
    if metodo == "azar":
        orden = list(range(len(cosenos)))
        azar.shuffle(orden)
        return orden
    if metodo == "recientes":
        return sorted(range(len(fechas)), key=lambda i: fechas[i], reverse=True)
    if metodo == "contenido":
        return list(np.argsort(-cosenos, kind="stable"))
    puntajes = puntajes_region(cosenos, regiones, region)
    if metodo == "region":
        return list(np.argsort(-puntajes, kind="stable"))
    return mmr(puntajes, vectores)


def fresco(cosenos, vectores, fechas, regiones, region, cuando, dias):
    """Cascada de la ronda b: las notas de los últimos `dias` por el híbrido; después el resto, de la más reciente."""
    desde = cuando - dt.timedelta(dias)
    dentro = [i for i, f in enumerate(fechas) if f >= desde]
    resto = sorted((i for i, f in enumerate(fechas) if f < desde), key=lambda i: fechas[i], reverse=True)
    if not dentro:
        return resto
    sub = mmr(puntajes_region(cosenos[dentro], [regiones[i] for i in dentro], region), vectores[dentro])
    return [dentro[i] for i in sub] + resto


def rango_reciproco(orden, relevantes):
    for r, i in enumerate(orden, 1):
        if i in relevantes:
            return 1 / r
    return 0.0


def auc_mismo_dia(cosenos, dias, relevantes):
    """(pares a favor, pares) de la enlazada frente a las no enlazadas publicadas el mismo día."""
    favor = total = 0.0
    for i in relevantes:
        otros = [j for j in range(len(dias)) if dias[j] == dias[i] and j not in relevantes]
        for j in otros:
            favor += 1.0 if cosenos[i] > cosenos[j] else (0.5 if cosenos[i] == cosenos[j] else 0.0)
            total += 1
    return favor, total


def diferencia_bootstrap(a, b, azar, n=REMUESTREOS):
    """(media de a − b, percentil 2,5, percentil 97,5) remuestreando los orígenes."""
    a, b = np.asarray(a), np.asarray(b)
    rng = np.random.default_rng(azar.randrange(2**32))
    idx = rng.integers(0, len(a), size=(n, len(a)))
    d = (a[idx] - b[idx]).mean(axis=1)
    return float((a - b).mean()), float(np.percentile(d, 2.5)), float(np.percentile(d, 97.5))


# ---------------------------------------------------------------- muestra y catálogo


def reserva_t5(notas, vistas):
    return {(n["medio"], n["id"]) for n in notas if n["sobre_nino"] == "1" and (n["medio"], n["id"]) not in vistas}


def catalogo_de(notas, reserva):
    return [n for n in notas if n["sobre_nino"] == "1" and (n["medio"], n["id"]) not in reserva
            and n["fecha_publicacion"] >= INICIO]  # fmt: skip


def _clave_url(url):
    return url.split("?")[0].split("#")[0].rstrip("/")


def muestra_a(notas, enlaces, vistas, catalogo, desde=INICIO, con_sobre=False):
    """{origen: {claves enlazadas}}: notas sin ver que mencionan El Niño (sin ser sobre El Niño, salvo con_sobre),
    publicadas desde `desde`, que enlazan a una nota anterior del catálogo, del mismo medio y en los DIAS_PREVIOS."""
    por_clave = {(n["medio"], n["id"]): n for n in notas}
    en_catalogo = {(n["medio"], n["id"]) for n in catalogo}
    por_url = {_clave_url(n["url"]): (n["medio"], n["id"]) for n in catalogo}
    salida = collections.defaultdict(set)
    for e in enlaces:
        o = (e["medio"], e["id"])
        n = por_clave.get(o)
        d = por_url.get(_clave_url(e["url"]))
        if (not n or not d or d == o or o in vistas or (n["sobre_nino"] == "1" and not con_sobre)
                or n["menciona_nino"] != "1" or n["fecha_publicacion"] < desde or d not in en_catalogo
                or d[0] != o[0]):  # fmt: skip
            continue
        if 0 < (momento(n) - momento(por_clave[d])).total_seconds() <= DIAS_PREVIOS * 86400:
            salida[o].add(d)
    return dict(salida)


class Embebedor:
    def __init__(self):
        st = candidatos.cargar(semaforo.MODELO)
        self.modelo = candidatos.Candidato(semaforo.MODELO, st, candidatos.prefijos(semaforo.MODELO)[0])

    def __call__(self, textos):
        return np.asarray(self.modelo.embeber(list(textos)))


# ---------------------------------------------------------------- criterios


def evaluar(muestra, por_clave, catalogo, vectores, region_de, azar, frescuras=()):
    """Filas por origen con el rango recíproco de cada método y los pares de la puerta."""
    indice = {(n["medio"], n["id"]): i for i, n in enumerate(catalogo)}
    filas, favor, pares, fuera = [], 0.0, 0.0, 0
    for o, enlazadas in sorted(muestra.items()):
        nota = por_clave[o]
        cand = candidatas(catalogo, momento(nota), o[0])
        locales = {indice[d] for d in enlazadas} & set(cand)
        if not locales:
            fuera += 1
            continue
        relevantes = {cand.index(i) for i in locales}
        q = vectores["consulta"][o]
        v = vectores["catalogo"][cand]
        cos = v @ q
        fechas = [momento(catalogo[i]) for i in cand]
        regiones = [region_de.get((catalogo[i]["medio"], catalogo[i]["id"]), "") for i in cand]
        region = region_de.get(o, "")
        f, t = auc_mismo_dia(cos, [x.date() for x in fechas], relevantes)
        favor, pares = favor + f, pares + t
        fila = {"medio": o[0], "id": o[1], "fecha": nota["fecha_publicacion"][:10], "candidatas": len(cand),
                "enlazadas": len(relevantes)}  # fmt: skip
        ordenes = {m: ordenar(m, cos, v, fechas, regiones, region, azar) for m in METODOS}
        ordenes |= {f"fresco_{d}": fresco(cos, v, fechas, regiones, region, momento(nota), d) for d in frescuras}
        for m, orden in ordenes.items():
            fila[f"rr_{m}"] = round(rango_reciproco(orden, relevantes), 4)
            fila[f"r5_{m}"] = int(bool(set(orden[:NOTAS]) & relevantes))
        filas.append(fila)
    return filas, (favor / pares if pares else None, int(pares)), fuera


def diversidad(muestra, por_clave, catalogo, vectores, region_de, dias=None):
    """Medios distintos entre las 5 notas del híbrido (o de la cascada fresca) con candidatas de todos los medios, y
    cobertura."""
    medios, vistos = [], collections.Counter()
    for o in sorted(muestra):
        cand = candidatas(catalogo, momento(por_clave[o]))
        if not cand:
            continue
        v = vectores["catalogo"][cand]
        regiones = [region_de.get((catalogo[i]["medio"], catalogo[i]["id"]), "") for i in cand]
        cos = v @ vectores["consulta"][o]
        if dias:
            fechas = [momento(catalogo[i]) for i in cand]
            orden = fresco(cos, v, fechas, regiones, region_de.get(o, ""), momento(por_clave[o]), dias)[:NOTAS]
        else:
            orden = mmr(puntajes_region(cos, regiones, region_de.get(o, "")), v)[:NOTAS]
        medios.append(len({catalogo[cand[i]]["medio"] for i in orden}))
        vistos.update(cand[i] for i in orden)
    return statistics.mean(medios), len(vistos)


def tiempo(embebedor, corpus, consultas, catalogo, vectores_catalogo, region_de):
    tiempos = []
    for nota in consultas[:CONSULTAS]:
        inicio = time.perf_counter()
        q = embebedor([reranker.texto_corto(nota)])[0]
        fecha = nota["fecha_publicacion"][:10]
        region = region_de.get((nota["medio"], nota["id"]), COSTA_NORTE)
        oficial(corpus, fecha, region if region in MACROREGIONES else COSTA_NORTE, "lluvias",
                lambda textos, q=q: embebedor(textos) @ q)  # fmt: skip
        cand = candidatas(catalogo, momento(nota))
        if cand:
            v = vectores_catalogo[cand]
            regiones = [region_de.get((catalogo[i]["medio"], catalogo[i]["id"]), "") for i in cand]
            mmr(puntajes_region(v @ q, regiones, region), v)
        tiempos.append(time.perf_counter() - inicio)
    return round(statistics.median(tiempos), 3), round(max(tiempos), 3)


def criterio_k2(corpus, fin):
    dias = (dt.date.fromisoformat(fin) - dt.date.fromisoformat(INICIO)).days + 1
    fallan = [(d, m) for k in range(dias) for m in MACROREGIONES
              if oficial(corpus, (d := (dt.date.fromisoformat(INICIO) + dt.timedelta(k)).isoformat()), m,
                         "lluvias")["comunicado"] is None]  # fmt: skip
    total = dias * len(MACROREGIONES)
    return criterio(PRUEBA, "K2. Cada día × macro-región tiene comunicado vigente", f"{total - len(fallan)}/{total}",
                    "100 %", not fallan, ", ".join(f"{d} {m}" for d, m in fallan[:5]))  # fmt: skip


def _mrr(filas, m, mitad=None):
    g = [f[f"rr_{m}"] for f in filas if mitad is None or (f["fecha"] < "2026-07-01") == (mitad == "ene-jun")]
    return statistics.mean(g) if g else None


def criterios(filas, puerta, fuera, medios, cobertura, catalogo_n, consulta, k2, azar):
    auc, pares = puerta
    pasa_puerta = auc is not None and auc >= AUC_MINIMA
    salida = [criterio(PRUEBA, "P. Puerta: el enlace sigue al contenido (AUC del mismo día)",
                       None if auc is None else round(auc, 3), f"≥ {AUC_MINIMA}", pasa_puerta,
                       f"{pares} pares; {len(filas)} orígenes ({fuera} sin enlazada en la ventana)")]  # fmt: skip
    if pasa_puerta:
        d, bajo, alto = diferencia_bootstrap([f["rr_hibrido"] for f in filas], [f["rr_recientes"] for f in filas], azar)
        salida.append(criterio(PRUEBA, "R1. MRR del híbrido menos el de lo más reciente", round(d, 3),
                               f"≥ {MEJORA_MINIMA} e IC > 0", d >= MEJORA_MINIMA and bajo > 0,
                               f"IC 95 % {bajo:.3f} a {alto:.3f}"))  # fmt: skip
        h, c = _mrr(filas, "hibrido"), _mrr(filas, "contenido")
        salida.append(criterio(PRUEBA, "R2. MRR del híbrido frente al contenido solo", f"{h:.3f} frente a {c:.3f}",
                               f"≥ contenido − {TOLERANCIA_CONTENIDO}", h >= c - TOLERANCIA_CONTENIDO))  # fmt: skip
    salida += [
        criterio(PRUEBA, "R3. Medios distintos entre las 5 notas", round(medios, 2), f"≥ {MEDIOS_MINIMOS}",
                 medios >= MEDIOS_MINIMOS),
        criterio(PRUEBA, "R4. Tiempo por consulta (mediana)", consulta[0], f"≤ {CONSULTA_MAXIMA_S} s",
                 consulta[0] <= CONSULTA_MAXIMA_S, f"máximo {consulta[1]} s"),
        k2,
    ]  # fmt: skip
    for m in METODOS:
        r5 = statistics.mean(f[f"r5_{m}"] for f in filas)
        salida.append(criterio(INFO, f"MRR y recall@5: {m}", f"{_mrr(filas, m):.3f} · {r5:.3f}", "", True,
                               f"ene-jun {_mrr(filas, m, 'ene-jun') or 0:.3f} · jul-oct "
                               f"{_mrr(filas, m, 'jul-oct') or 0:.3f}"))  # fmt: skip
    mediana = statistics.median(f["candidatas"] for f in filas)
    salida.append(criterio(INFO, "Cobertura del catálogo entre las 5 notas", f"{cobertura}/{catalogo_n}", "", True,
                           f"candidatas por origen (mediana) {mediana}"))  # fmt: skip
    return salida


def validar():
    notas = leer_csv(config.DIR_NOTICIAS / "notas.csv")
    vistas = notas_vistas()
    reserva = reserva_t5(notas, vistas)
    catalogo = catalogo_de(notas, reserva)
    muestra = muestra_a(notas, leer_csv(config.DIR_NOTICIAS / "enlaces.csv"), vistas, catalogo)
    por_clave = {(n["medio"], n["id"]): n for n in notas}
    log.info(f"Catálogo {len(catalogo)} notas · muestra A {len(muestra)} orígenes · reserva T5 {len(reserva)}")
    if muestra and not any(f["muestra"] == MUESTRA for f in leer_csv(config.ARCHIVO_NOTAS_VISTAS)):
        marcar_vistas([por_clave[o] for o in sorted(muestra)], MUESTRA)
    region_de = {(f["medio"], f["id"]): f["macroregion_principal"]
                 for f in leer_csv(config.DIR_NOTICIAS / "regiones.csv")}  # fmt: skip
    embebedor = Embebedor()
    origenes = sorted(muestra)
    vectores = {"catalogo": embebedor(reranker.texto_corto(n) for n in catalogo)}
    vectores["consulta"] = dict(zip(origenes, embebedor(reranker.texto_corto(por_clave[o]) for o in origenes),
                                    strict=True))  # fmt: skip
    azar = random.Random(SEMILLA)
    filas, puerta, fuera = evaluar(muestra, por_clave, catalogo, vectores, region_de, azar)
    escribir_csv(config.DIR_ANALITICA / "recomendador.csv", tuple(filas[0]) if filas else ("medio",), filas)
    medios, cobertura = diversidad(muestra, por_clave, catalogo, vectores, region_de)
    corpus = Corpus()
    consulta = tiempo(embebedor, corpus, [por_clave[o] for o in origenes], catalogo, vectores["catalogo"], region_de)
    fin = max(n["fecha_publicacion"][:10] for n in notas)
    return criterios(filas, puerta, fuera, medios, cobertura, len(catalogo), consulta, criterio_k2(corpus, fin), azar)


# ---------------------------------------------------------------- ronda b


def elegir_dias(filas):
    """El N de la grilla con el mayor MRR de la cascada fresca; empate: el menor."""
    mrr = {d: statistics.mean(f[f"rr_fresco_{d}"] for f in filas) for d in GRILLA_FRESCURA}
    mejor = max(mrr.values())
    return min(d for d, v in mrr.items() if v == mejor), mrr


def muestra_b(notas, enlaces, vistas, catalogo):
    """Orígenes nuevos desde INICIO_B que mencionan El Niño (sobre El Niño o no) y enlazan una nota anterior."""
    return muestra_a(notas, enlaces, vistas, catalogo, desde=INICIO_B, con_sobre=True)


def _preparar(muestra, por_clave, catalogo):
    embebedor = Embebedor()
    origenes = sorted(muestra)
    vectores = {"catalogo": embebedor(reranker.texto_corto(n) for n in catalogo)}
    vectores["consulta"] = dict(zip(origenes, embebedor(reranker.texto_corto(por_clave[o]) for o in origenes),
                                    strict=True))  # fmt: skip
    return vectores


def calibrar():
    """Ronda b: DIAS_FRESCOS con la muestra A (ya vista)."""
    notas = leer_csv(config.DIR_NOTICIAS / "notas.csv")
    vistas_a = {(f["medio"], f["id"]) for f in leer_csv(config.ARCHIVO_NOTAS_VISTAS) if f["muestra"] == MUESTRA}
    vistas = notas_vistas() - vistas_a
    catalogo = catalogo_de(notas, reserva_t5(notas, notas_vistas()))
    muestra = {o: d for o, d in muestra_a(notas, leer_csv(config.DIR_NOTICIAS / "enlaces.csv"), vistas,
                                          catalogo).items() if o in vistas_a}  # fmt: skip
    por_clave = {(n["medio"], n["id"]): n for n in notas}
    region_de = _regiones()
    vectores = _preparar(muestra, por_clave, catalogo)
    filas, _, _ = evaluar(muestra, por_clave, catalogo, vectores, region_de, random.Random(SEMILLA), GRILLA_FRESCURA)
    dias, mrr = elegir_dias(filas)
    salida = [criterio(INFO, f"Calibración con A ({len(filas)} orígenes): MRR de la cascada fresca", dias, "", True,
                       " · ".join(f"{d} días {v:.3f}" for d, v in mrr.items())
                       + f" · lo más reciente {statistics.mean(f['rr_recientes'] for f in filas):.3f}")]  # fmt: skip
    for mitad in ("ene-jun", "jul-oct"):
        metodos = ("recientes", "contenido", f"fresco_{dias}")
        detalle = " · ".join(f"{m} {_mrr(filas, m, mitad) or 0:.3f}" for m in metodos)
        salida.append(criterio(INFO, f"Calibración con A, {mitad}", "", "", True, detalle))
    return salida


def validar_b():
    """Ronda b: decide con la muestra B (notas nuevas desde INICIO_B, primera vez que se usan)."""
    if DIAS_FRESCOS is None:
        raise SystemExit("Falta fijar DIAS_FRESCOS con `calibrar`.")
    notas = leer_csv(config.DIR_NOTICIAS / "notas.csv")
    vistas = notas_vistas()
    catalogo = [n for n in notas if n["sobre_nino"] == "1" and n["fecha_publicacion"] >= INICIO]  # B va con T5
    muestra = muestra_b(notas, leer_csv(config.DIR_NOTICIAS / "enlaces.csv"), vistas, catalogo)
    por_clave = {(n["medio"], n["id"]): n for n in notas}
    log.info(f"Muestra B: {len(muestra)} orígenes desde {INICIO_B}")
    if not muestra:
        raise SystemExit("La muestra B está vacía: falta la recolección desde el 9-nov.")
    if not any(f["muestra"] == MUESTRA_B for f in leer_csv(config.ARCHIVO_NOTAS_VISTAS)):
        marcar_vistas([por_clave[o] for o in sorted(muestra)], MUESTRA_B)
    region_de = _regiones()
    vectores = _preparar(muestra, por_clave, catalogo)
    azar = random.Random(SEMILLA + "-b")
    filas, puerta, fuera = evaluar(muestra, por_clave, catalogo, vectores, region_de, azar, (DIAS_FRESCOS,))
    m = f"fresco_{DIAS_FRESCOS}"
    suficientes = len(filas) >= ORIGENES_MINIMOS_B
    prueba = PRUEBA + " (ronda b)" if suficientes else INFO + " (ronda b, pocos orígenes)"
    d, bajo, alto = diferencia_bootstrap([f[f"rr_{m}"] for f in filas], [f["rr_recientes"] for f in filas], azar)
    h, c = _mrr(filas, m), _mrr(filas, "contenido")
    medios, _ = diversidad(muestra, por_clave, catalogo, vectores, region_de, DIAS_FRESCOS)
    auc, pares = puerta
    return [
        criterio(prueba, "Orígenes de la muestra B", len(filas), f"≥ {ORIGENES_MINIMOS_B}", suficientes,
                 f"{fuera} sin enlazada en la ventana; puerta AUC {auc if auc is None else round(auc, 3)} ({pares})"),
        criterio(prueba, f"R1. MRR de la cascada fresca ({DIAS_FRESCOS} días) menos el de lo más reciente", round(d, 3),
                 f"≥ {MEJORA_MINIMA} e IC > 0", d >= MEJORA_MINIMA and bajo > 0, f"IC 95 % {bajo:.3f} a {alto:.3f}"),
        criterio(prueba, "R2. MRR de la cascada fresca frente al contenido solo", f"{h:.3f} frente a {c:.3f}",
                 f"≥ contenido − {TOLERANCIA_CONTENIDO}", h >= c - TOLERANCIA_CONTENIDO),
        criterio(prueba, "R3. Medios distintos entre las 5 notas", round(medios, 2), f"≥ {MEDIOS_MINIMOS}",
                 medios >= MEDIOS_MINIMOS),
    ]  # fmt: skip


def _regiones():
    return {(f["medio"], f["id"]): f["macroregion_principal"] for f in leer_csv(config.DIR_NOTICIAS / "regiones.csv")}


def main(argv=None):
    ap = argparse.ArgumentParser(description="Recomendador híbrido: validación offline.")
    ap.add_argument("paso", choices=("validar", "calibrar"))
    ap.add_argument("--ronda", choices=("a", "b"), default="a")
    args = ap.parse_args(argv)
    registro = configurar(f"analitica-recomendador-{args.paso}-{args.ronda}")
    inicio = ahora()
    config.DIR_ANALITICA.mkdir(parents=True, exist_ok=True)
    if args.paso == "calibrar":
        filas = calibrar()
    else:
        filas = validar_b() if args.ronda == "b" else validar()
    guardar(filas, config.DIR_ANALITICA / "validacion.csv")
    reporte(filas, [], inicio)
    log.info(f"Registro: {registro.relative_to(config.RAIZ)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
