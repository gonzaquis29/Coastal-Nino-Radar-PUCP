"""Clasificador de tema con clima y mar (docs/app/definicion.md, sección 12): criterios K1 a K10.

python -m radar.app.tema_clima muestra    ->  las notas nuevas de la prueba (corto y cuerpo), fijadas antes de entrenar
python -m radar.app.tema_clima entrenar   ->  data/processed/app/tema-clima-modelo.joblib (solo enero a agosto)
python -m radar.app.tema_clima cuerpos    ->  lee en memoria los cuerpos nuevos (puede correr mientras se entrena)
python -m radar.app.tema_clima validar    ->  prueba "App: clasificador de tema con clima y mar" en validacion.csv

Etiquetas automáticas: positivos = sobre_nino más la zona gris sin ver con etiquetas editoriales de clima y mar;
negativos = otros_temas sin etiquetas de clima o mar más los negativos difíciles (zona gris sin ver con etiquetas solo
de otros temas). Las listas de etiquetas están en radar.comun.dominio. La prueba (septiembre al corte) se mira una vez.
"""

import argparse
import collections
import functools
import logging
import re
import threading

import joblib
import numpy as np

from radar import config
from radar.app import tema
from radar.app import validar_tema as vt
from radar.comun import dominio
from radar.comun.archivos import escribir_csv, leer_csv
from radar.comun.registro import configurar
from radar.comun.texto import sin_tildes
from radar.nlp import reranker
from radar.nlp.viabilidad import registrada
from radar.noticias.medios import MEDIOS
from radar.noticias.validar_texto import marcar_vistas, notas_vistas
from radar.noticias.viabilidad import _muestra, criterio, guardar

log = logging.getLogger(__name__)

PRUEBA = "App: clasificador de tema con clima y mar"
ARCHIVO_MODELO = config.DIR_APP / "tema-clima-modelo.joblib"
MUESTRA = "validacion-clima-mar"
SEMILLA_CUERPOS = "clima-mar-cuerpos-20261123"
CUERPOS_POR_MEDIO = 50
VALORES_C = (0.1, 1.0, 10.0, 100.0)  # en la sección 10, C quedó en el borde de la grilla (10)
MAX_OTROS_CV, MAX_DUROS_CV = 0.01, 0.05  # τ: el menor que deja pasar a lo sumo esto en la validación cruzada
ULTIMO_DIA_ENTRENA = "2026-08-31"
TIPOS_OFICIALES_ENFEN = ("impactos", "pesca")  # opción C, con los párrafos de los avisos del Senamhi

# Grupos
TEMA, CLIMA, OTRO, DURO = "tema", "clima", "otro", "duro"
COLUMNAS_MUESTRA = ("medio", "id", "grupo", "forma")
CORTO, CUERPO = "corto", "cuerpo"

# Umbrales fijados en la sección 12.5 antes de construir
MAX_ALTA_DUROS_CORTO, MAX_ALTA_DUROS_CUERPO = 0.02, 0.02
MAX_ALTA_OTROS_CORTO, MAX_ALTA_OTROS_CUERPO = 0.01, 0.02
MARGEN_CLIMA_CORTO = 0.02  # puntos que se aceptan perder en clima y mar frente a la sección 9 (K4)
MAX_FUERA_CLIMA_CUERPO = 0.05
MAX_SINTETICOS_DEL_TEMA_FUERA, MAX_SINTETICOS_OTRO_TEMA_PASAN = 2, 2

# Sintéticos nuevos, escritos el 23-nov antes de medir (distintos de los de las secciones 9.4 y 10.3). Inventados.
NINO_OTRO_SENTIDO = (
    "Niño de 7 años gana un torneo nacional de ajedrez",
    "Hospital del Niño amplía su servicio de emergencias",
    "La niña que vende flores en el mercado de Surquillo",
    "Campaña de juguetes para niños de albergues en Puno",
    "Un niño perdido fue hallado en una playa de Chorrillos",
    "Niños de Huancavelica reciben útiles escolares",
    "El niño prodigio del violín que toca en el Gran Teatro",
    "Niña de 12 años crea una aplicación para estudiar",
    "Fiesta del Niño Jesús de Praga reúne a cientos de fieles",
    "Padres denuncian maltrato a un niño en una guardería",
)
FENOMENO_BIEN_ESCRITO = (
    "El Niño costero eleva el precio del limón en los mercados",
    "Productores de mango temen al fenómeno El Niño",
    "Piura prepara albergues ante un posible Niño costero",
    "El ENFEN mantiene la alerta de El Niño costero",
    "¿Qué tan fuerte será El Niño este verano?",
    "Fenómeno del Niño: el MEF transfiere fondos a Tumbes",
    "La Niña podría llegar al Pacífico central en invierno",
    "El Niño global sigue débil, según la NOAA",
    "Escolares de Chiclayo hacen simulacro por El Niño",
    "Seguro agrario cubrirá pérdidas por El Niño costero",
)
DEL_TEMA_SIN_NINO = (
    # clima
    "Lluvias intensas aíslan a tres distritos de Cajamarca",
    "Senamhi prevé temperaturas de hasta 35 grados en Piura",
    "Huaico sepulta viviendas en Chosica tras la tormenta",
    "Río Tumbes se desborda y anega cultivos de arroz",
    "Heladas afectan a la ganadería de alpacas en Puno",
    "Ola de calor obliga a cambiar el horario escolar en Ica",
    "Declaran emergencia por déficit hídrico en Arequipa",
    "Granizada sorpresiva cubre las calles de Huancayo",
    "Radiación ultravioleta llega a niveles extremos en Lima",
    "Neblina y llovizna persistirán en la costa central",
    # mar y pesca
    "Capitanías cierran puertos por oleaje en el litoral sur",
    "Imarpe reporta agua más cálida frente a Paita",
    "Segunda temporada de anchoveta empieza con buena biomasa",
    "Pescadores artesanales de Sechura no salen a faenar por el mar agitado",
    "Varamiento de lobos marinos en playas de Lambayeque",
    "Desembarque de perico crece en el puerto de Paita",
    "Nivel del mar sube y afecta el malecón de Huanchaco",
    "Flota de pota vuelve a puerto por la escasez del recurso",
    "Marea roja obliga a cerrar la extracción de conchas",
    "Corriente de Humboldt se debilita, advierten oceanógrafos",
)
OTRO_TEMA_CON_PALABRAS_DE_CLIMA = (
    "Sismo de magnitud 5 se siente en Lima y declaran emergencia en Cañete",
    "Casos de dengue suben en Loreto y el Minsa refuerza la fumigación",
    "El clima político se tensa antes del debate presidencial",
    "Un mar de gente llenó la plaza para recibir a la selección",
    "Alerta en la Bolsa de Lima por la caída del precio del cobre",
    "Congreso aprueba la ley de la reforma de pensiones en medio de la emergencia fiscal",
    "Ola de robos en San Juan de Lurigancho preocupa a los vecinos",
    "Lluvia de goles: Alianza Lima golea a Cienciano",
    "Temperatura del mercado inmobiliario: suben los precios en Miraflores",
    "Evento de lanzamiento del nuevo celular reúne a influencers en Barranco",
)


def ruta(nombre):
    return config.DIR_APP / f"tema-clima-{nombre}.csv"


def en_entrenamiento(nota):
    return nota["fecha_publicacion"][:10] <= ULTIMO_DIA_ENTRENA


def grupos(notas, vistas):
    """{(medio, id): tema | clima | otro | duro}; las notas sin grupo quedan fuera."""
    base = tema.grupos(notas)
    salida = {}
    for n in notas:
        k = (n["medio"], n["id"])
        con_clima = dominio.etiquetada_clima_mar(n)
        con_otro_sentido = any(dominio.ETIQUETAS_CON_OTRO_SENTIDO.fullmatch(e) for e in dominio.etiquetas(n))
        if base[k] == tema.TEMA:
            salida[k] = TEMA
        elif base[k] == tema.OTRO:
            if not con_clima and not con_otro_sentido:
                salida[k] = OTRO
        elif k not in vistas:  # zona gris sin ver
            if con_clima:
                salida[k] = CLIMA
            elif dominio.etiquetada_otro_tema(n):
                salida[k] = DURO
    return salida


_SIN_FECHA = re.compile(
    r"\d+|lunes|martes|miercoles|jueves|viernes|sabado|domingo|enero|febrero|marzo|abril|mayo|junio|julio|agosto|"
    r"septiembre|setiembre|octubre|noviembre|diciembre"
)


def plantilla(titular):
    """El titular sin números, días ni meses: los pronósticos diarios cuentan una sola vez (K4)."""
    return " ".join(_SIN_FECHA.sub("#", sin_tildes(titular.lower())).split())


def una_por_plantilla(notas):
    vistas, salida = set(), []
    for n in sorted(notas, key=lambda n: (n["medio"], n["id"])):
        p = plantilla(n["titular"])
        if p not in vistas:
            vistas.add(p)
            salida.append(n)
    return salida


def muestra():
    """Fija las notas nuevas de la prueba antes de entrenar: corto (todas) y cuerpo (hasta 50 por medio)."""
    if ruta("muestra").exists():
        log.info(f"La muestra ya existe en {ruta('muestra')}; no se elige otra.")
        return
    if registrada(MUESTRA):
        raise SystemExit(f"La muestra {MUESTRA} ya está en notas_vistas.csv: no queda una prueba limpia.")
    notas = leer_csv(config.DIR_NOTICIAS / "notas.csv")
    g = grupos(notas, notas_vistas())
    prueba = [n for n in notas if not en_entrenamiento(n)]
    filas = []
    for grupo in (CLIMA, DURO):
        del_grupo = [n for n in prueba if g.get((n["medio"], n["id"])) == grupo]
        filas += [{"medio": n["medio"], "id": n["id"], "grupo": grupo, "forma": CORTO} for n in del_grupo]
        for m in MEDIOS:
            del_medio = [n for n in del_grupo if n["medio"] == m]
            filas += [{"medio": n["medio"], "id": n["id"], "grupo": grupo, "forma": CUERPO}
                      for n in _muestra(del_medio, CUERPOS_POR_MEDIO, SEMILLA_CUERPOS, grupo, m)]  # fmt: skip
    escribir_csv(ruta("muestra"), COLUMNAS_MUESTRA, filas)
    log.info(f"Muestra: {collections.Counter((f['grupo'], f['forma']) for f in filas)}")


def textos_oficiales():
    """Opción C: párrafos de los avisos del Senamhi y de impactos y pesca del ENFEN, [(texto, fecha)]."""
    return [(p["texto"], p["fecha_doc"][:10]) for p in leer_csv(config.DIR_OFICIAL / "parrafos.csv")
            if p["fuente"] == "senamhi" or p["tipo"] in TIPOS_OFICIALES_ENFEN]  # fmt: skip


def umbral_de(prob, y, duro):
    """El menor τ que deja pasar a lo sumo MAX_OTROS_CV de otros temas y MAX_DUROS_CV de los difíciles."""
    otros, duros = prob[(y == 0) & ~duro], prob[(y == 0) & duro]
    return max(float(np.quantile(otros, 1 - MAX_OTROS_CV, method="higher")),
               float(np.quantile(duros, 1 - MAX_DUROS_CV, method="higher")))  # fmt: skip


def elegir_modelo(x, y, duro, x_oficial):
    """(C, con_oficiales, τ, average precision) por validación cruzada solo sobre las notas del entrenamiento. Los
    textos oficiales, si entran, van a todos los grupos de entrenamiento y nunca se evalúan."""
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import average_precision_score
    from sklearn.model_selection import StratifiedKFold

    cv = StratifiedKFold(n_splits=tema.GRUPOS_CV, shuffle=True, random_state=tema.SEMILLA)
    estratos = y * 2 + duro  # que cada grupo tenga su parte de difíciles
    resultados = {}
    for con in (False, True):
        for c in VALORES_C:
            fuera = np.zeros(len(y))
            for a, b in cv.split(x, estratos):
                xa, ya = (np.vstack([x[a], x_oficial]), np.r_[y[a], np.ones(len(x_oficial))]) if con else (x[a], y[a])
                fuera[b] = LogisticRegression(C=c, class_weight="balanced", max_iter=5000).fit(xa, ya).predict_proba(
                    x[b])[:, 1]  # fmt: skip
            resultados[(c, con)] = (average_precision_score(y, fuera), fuera)
            log.info(f"CV: C {c}, oficiales {con}: AP {resultados[(c, con)][0]:.4f}")
    c, con = max(resultados, key=lambda k: resultados[k][0])
    tau = umbral_de(resultados[(c, con)][1], y, duro)
    return c, con, tau, {f"{k[0]}{'+oficiales' if k[1] else ''}": round(r[0], 4) for k, r in resultados.items()}


def entrenar():
    from sklearn.linear_model import LogisticRegression

    if not ruta("muestra").exists():
        raise SystemExit("Primero la muestra (se fija antes de entrenar): python -m radar.app.tema_clima muestra")
    notas = leer_csv(config.DIR_NOTICIAS / "notas.csv")
    g = grupos(notas, notas_vistas())
    entrena = [n for n in notas if en_entrenamiento(n) and (n["medio"], n["id"]) in g]
    grupo = [g[(n["medio"], n["id"])] for n in entrena]
    y = np.array([x in (TEMA, CLIMA) for x in grupo], dtype=int)
    duro = np.array([x == DURO for x in grupo])
    log.info(f"Entrenamiento: {collections.Counter(grupo)}")
    oficiales = [t for t, f in textos_oficiales() if f <= ULTIMO_DIA_ENTRENA]
    modelo = tema.modelo_de_texto()
    x = tema.vectores([reranker.texto_corto(n) for n in entrena], modelo)
    x_oficial = tema.vectores(oficiales, modelo)
    c, con, tau, ap = elegir_modelo(x, y, duro, x_oficial)
    xa, ya = (np.vstack([x, x_oficial]), np.r_[y, np.ones(len(x_oficial))]) if con else (x, y)
    m = LogisticRegression(C=c, class_weight="balanced", max_iter=5000).fit(xa, ya)
    joblib.dump({"coef": m.coef_[0], "intercepto": float(m.intercept_[0]), "C": c, "tau": tau, "ap_cv": ap,
                 "oficiales": con, "n_oficiales": len(oficiales) if con else 0,
                 "grupos": dict(collections.Counter(grupo)),
                 "hasta": ULTIMO_DIA_ENTRENA}, ARCHIVO_MODELO)  # fmt: skip
    log.info(f"Modelo: C {c}, oficiales {con}, τ {tau:.4f}, AP en CV {ap} -> {ARCHIVO_MODELO}")


@functools.cache
def clasificador():
    return tema.Clasificador(ARCHIVO_MODELO, modelo=tema.modelo_de_texto())


def lista_de_cuerpos(notas):
    por_clave = {(n["medio"], n["id"]): n for n in notas}
    return [(por_clave[(f["medio"], f["id"])], f["grupo"]) for f in leer_csv(ruta("muestra")) if f["forma"] == CUERPO]


def cuerpos():
    """Solo la lectura de los cuerpos nuevos (reanudable); se puede correr mientras se entrena."""
    import torch

    from radar.app import servicio

    torch.set_num_threads(tema.HILOS_LECTURA)
    if not ruta("muestra").exists():
        raise SystemExit("Falta la muestra: python -m radar.app.tema_clima muestra")
    r = tema.leer_cuerpos(servicio.servicio(), lista_de_cuerpos(leer_csv(config.DIR_NOTICIAS / "notas.csv")),
                          threading.Event(), ruta("cuerpos"))  # fmt: skip
    if not isinstance(r, list):
        raise SystemExit(r)


def tasa(k_, n, nombre, umbral, pasa, detalle=""):
    p, ic = vt.proporcion(k_, n)
    return criterio(PRUEBA, nombre, vt.texto(p, ic), umbral, pasa, f"{k_} de {n}{detalle}")


def leidos(filas, k):
    """Las filas leídas sin error, con lo que decide el clasificador y si la cercanía es «Alta»."""
    return [f | {"pasa_c": tema.pasa_c_de(f, k), "pasa_a_": f["pasa_a"] == "1",
                 "alta": f["origen"] == "distancia" and f["banda"] == "cercano"}
            for f in filas if not f["error"]]  # fmt: skip


def por_medio(filas, campo):
    c, n = collections.Counter(), collections.Counter()
    for f in filas:
        n[f["medio"]] += 1
        c[f["medio"]] += not f[campo]
    return ", ".join(f"{m} {c[m]}/{n[m]}" for m in sorted(n))


def validar(repetir=False):
    for falta, orden in ((ARCHIVO_MODELO, "entrenar"), (ruta("muestra"), "muestra")):
        if not falta.exists():
            raise SystemExit(f"Falta {falta.name}: python -m radar.app.tema_clima {orden}")
    if registrada(MUESTRA) and not repetir:
        raise SystemExit(f"La prueba ya se miró ({MUESTRA} en notas_vistas.csv). Usa --repetir y decláralo.")
    from radar.app import servicio

    s = servicio.servicio()
    k = clasificador()
    notas = leer_csv(config.DIR_NOTICIAS / "notas.csv")
    por_clave = {(n["medio"], n["id"]): n for n in notas}
    elegidas = leer_csv(ruta("muestra"))
    corto = {grupo: [por_clave[(f["medio"], f["id"])] for f in elegidas if f["grupo"] == grupo and f["forma"] == CORTO]
             for grupo in (CLIMA, DURO)}  # fmt: skip
    g_base = tema.grupos(notas)
    reutil = {grupo: [n for n in notas if not en_entrenamiento(n) and g_base[(n["medio"], n["id"])] == grupo]
              for grupo in (tema.TEMA, tema.OTRO)}  # fmt: skip
    # Los otros temas reutilizados, sin las etiquetas de clima o mar (12.3)
    reutil[tema.OTRO] = [n for n in reutil[tema.OTRO] if not dominio.etiquetada_clima_mar(n) and not any(
        dominio.ETIQUETAS_CON_OTRO_SENTIDO.fullmatch(e) for e in dominio.etiquetas(n))]  # fmt: skip
    clima_unicas = una_por_plantilla(corto[CLIMA])

    def medir(lista):
        return tema.medir_textos(s, k, [(reranker.texto_corto(n), n["fecha_publicacion"][:10]) for n in lista])

    filas = []
    m = medir(corto[DURO])
    alta_c, alta_a = sum(pc and al for pc, _, al in m), sum(pa and al for _, pa, al in m)
    filas.append(tasa(alta_c, len(m), "K1. Negativos difíciles con «Alta», corto (nuevas)",
                      "≤ 2 % y menos que la sección 9", alta_c / len(m) <= MAX_ALTA_DUROS_CORTO and alta_c < alta_a,
                      f"; sección 9 en las mismas notas: {alta_a}; pasan el filtro: clasificador "
                      f"{sum(pc for pc, _, _ in m)}, sección 9 {sum(pa for _, pa, _ in m)}"))  # fmt: skip

    leidas = tema.leer_cuerpos(s, lista_de_cuerpos(notas), threading.Event(), ruta("cuerpos"))
    if not isinstance(leidas, list):
        raise SystemExit(leidas)
    ok = leidos(leidas, k)
    duros = [f for f in ok if f["grupo"] == DURO]
    a_c, a_a = sum(f["pasa_c"] and f["alta"] for f in duros), sum(f["pasa_a_"] and f["alta"] for f in duros)
    pasa2 = a_c / max(1, len(duros)) <= MAX_ALTA_DUROS_CUERPO and a_c <= a_a
    filas.append(tasa(a_c, len(duros), "K2. Negativos difíciles con «Alta», cuerpo (nuevas)",
                      "≤ 2 % y no peor que la sección 9", pasa2,
                      f"; sección 9 en los mismos: {a_a}; sin leer: "
                      f"{sum(1 for f in leidas if f['grupo'] == DURO) - len(duros)}"))  # fmt: skip

    m = medir(reutil[tema.OTRO])
    alta_c, alta_a = sum(pc and al for pc, _, al in m), sum(pa and al for _, pa, al in m)
    previos = leidos(leer_csv(tema.ruta("cuerpos")), k)
    otros_cu = [f for f in previos if f["grupo"] == tema.OTRO]
    cu_c = sum(f["pasa_c"] and f["alta"] for f in otros_cu)
    cu_a = sum(f["pasa_a_"] and f["alta"] for f in otros_cu)
    p_corto, p_cuerpo = alta_c / len(m), cu_c / max(1, len(otros_cu))
    pasa3 = p_corto <= MAX_ALTA_OTROS_CORTO and p_cuerpo <= MAX_ALTA_OTROS_CUERPO and alta_c <= alta_a and cu_c <= cu_a
    filas.append(criterio(PRUEBA, "K3. otros_temas con «Alta», corto / cuerpo (reutilizadas, --repetir)",
                          f"{vt.texto(*vt.proporcion(alta_c, len(m)))} / "
                          f"{vt.texto(*vt.proporcion(cu_c, len(otros_cu)))}",
                          "≤ 1 % / ≤ 2 %, y no peor que la sección 9", pasa3,
                          f"corto {alta_c} de {len(m)} (sección 9: {alta_a}); cuerpo {cu_c} de {len(otros_cu)} "
                          f"(sección 9: {cu_a})"))  # fmt: skip

    m4 = medir(clima_unicas)
    fuera_c, fuera_a = sum(not pc for pc, _, _ in m4), sum(not pa for _, pa, _ in m4)
    m = m4
    pasa4 = fuera_c / len(m) <= fuera_a / len(m) + MARGEN_CLIMA_CORTO
    filas.append(tasa(fuera_c, len(m), "K4. Clima y mar que quedan fuera, corto (nuevas, una por plantilla)",
                      "no peor que la sección 9 más 2 puntos", pasa4,
                      f"; sección 9: {fuera_a}; de {len(corto[CLIMA])} notas"))  # fmt: skip
    clima_cu = [f for f in ok if f["grupo"] == CLIMA]
    fuera_cu = sum(not f["pasa_c"] for f in clima_cu)
    filas.append(tasa(fuera_cu, len(clima_cu), "K5. Clima y mar que quedan fuera, cuerpo (nuevas)", "≤ 5 %",
                      fuera_cu / max(1, len(clima_cu)) <= MAX_FUERA_CLIMA_CUERPO,
                      f"; sección 9: {sum(not f['pasa_a_'] for f in clima_cu)}; por medio: "
                      f"{por_medio(clima_cu, 'pasa_c')}"))  # fmt: skip

    m = medir(reutil[tema.TEMA])
    fuera_c, fuera_a = sum(not pc for pc, _, _ in m), sum(not pa for _, pa, _ in m)
    filas.append(tasa(fuera_c, len(m), "K6. Sobre El Niño que quedan fuera, corto (reutilizadas, --repetir)",
                      "no peor que la sección 9", fuera_c <= fuera_a, f"; sección 9: {fuera_a}"))  # fmt: skip

    otro = [t for t in NINO_OTRO_SENTIDO if k.en_tema(t)]
    perdidas = [t for t in FENOMENO_BIEN_ESCRITO if not k.en_tema(t)]
    sin_nino = [t for t in DEL_TEMA_SIN_NINO if not k.en_tema(t)]
    ajenos = [t for t in OTRO_TEMA_CON_PALABRAS_DE_CLIMA if k.en_tema(t)]
    pasa7 = (not otro and not perdidas and len(sin_nino) <= MAX_SINTETICOS_DEL_TEMA_FUERA
             and len(ajenos) <= MAX_SINTETICOS_OTRO_TEMA_PASAN)  # fmt: skip
    filas.append(criterio(PRUEBA, "K7. Sintéticos: «niño» con otro sentido que pasa / el fenómeno que no pasa / del "
                          "tema sin «El Niño» fuera / de otros temas con palabras de clima que pasan",
                          f"{len(otro)} / {len(perdidas)} / {len(sin_nino)} de 20 / {len(ajenos)} de 10",
                          "0 / 0 / ≤ 2 / ≤ 2", pasa7, "; ".join(otro + perdidas + sin_nino + ajenos)))  # fmt: skip

    avisos = [t for t, f in textos_oficiales() if f > ULTIMO_DIA_ENTRENA and t]
    fuera_av = sum(not k.en_tema(t) for t in avisos)
    pares = zip(clima_unicas, m4, strict=True)
    clima_por_medio = por_medio([{"medio": n["medio"], "pasa": pc} for n, (pc, _, _) in pares], "pasa")
    filas.append(criterio(f"{PRUEBA} (informativo)", "K8. Textos oficiales de septiembre al corte que quedan fuera; "
                          "K4 por medio", f"{fuera_av} de {len(avisos)}", "informativo", True,
                          f"clima y mar en corto, fuera por medio: {clima_por_medio}"))  # fmt: skip
    f10 = vt.f6()
    filas.append(criterio(PRUEBA, "K10. Preguntar sin cambios (no usa el clasificador)", f10["valor"], "0 cambios",
                          f10["valor"] == "0 cambios", f10["detalle"]))  # fmt: skip
    guardar(filas, config.DIR_APP / "validacion.csv")
    for f in filas:
        log.info(f"[{'ok' if f['pasa'] else 'NO'}] {f['criterio']}: {f['valor']} (umbral {f['umbral']}) {f['detalle']}")

    if not registrada(MUESTRA):
        vistas = notas_vistas()
        usadas = {(f["medio"], f["id"]): por_clave[(f["medio"], f["id"])] for f in elegidas}
        marcar_vistas([n for c, n in usadas.items() if c not in vistas], MUESTRA)
        log.info(f"{len(usadas)} notas nuevas pasan a notas_vistas.csv ({MUESTRA})")


def main(argv=None):
    ap = argparse.ArgumentParser(description="Clasificador de tema con clima y mar: K1 a K10 (sección 12).")
    ap.add_argument("accion", choices=("muestra", "entrenar", "cuerpos", "validar"))
    ap.add_argument("--repetir", action="store_true", help="volver a medir una prueba ya mirada (se declara)")
    a = ap.parse_args(argv)
    configurar("app-tema-clima")
    if a.accion == "validar":
        validar(a.repetir)
    else:
        {"muestra": muestra, "entrenar": entrenar, "cuerpos": cuerpos}[a.accion]()


if __name__ == "__main__":
    main()
