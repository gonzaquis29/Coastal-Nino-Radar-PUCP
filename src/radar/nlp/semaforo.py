"""Semáforo de alineación: la capa 5 y la distancia de minilm en una sola función (docs/nlp/discrepancia.md, punto 5.1).

`medir_discrepancia(texto, fecha)` es la que usan la app, el agente y los videos. Si el texto tiene afirmaciones
evaluables, el color es el de la capa 5 (rojo, amarillo o verde). Si no, lo da la distancia a los párrafos del ENFEN
vigentes en la fecha, sin los de definiciones: verde si es cercano, amarillo si es intermedio y gris si es lejano.
Lejos no es contradecir: el rojo queda solo para lo que contradice. Mide cercanía a lo oficial, no verdad.

Uso: python -m radar.nlp.semaforo muestra    # negativos nuevos, que se agregan a notas_vistas
     python -m radar.nlp.semaforo calibrar   # umbrales de corto (sin red) y de cuerpo (pide páginas)
     python -m radar.nlp.semaforo validar    # S1 a S6 (pide páginas para los cuerpos nuevos)
"""

import argparse
import collections
import datetime as dt
import functools
import logging
import statistics
import sys
import threading
import time

import numpy as np

from radar import config
from radar.comun.archivos import escribir_csv, leer_csv
from radar.comun.candado import exclusivo
from radar.comun.energia import sin_suspension
from radar.comun.registro import configurar
from radar.comun.texto import ahora
from radar.nlp import afirmaciones as af
from radar.nlp import candidatos, discrepancia, embeddings, esquemas, reranker, tfidf, viabilidad
from radar.noticias.medios import MEDIOS
from radar.noticias.validar_texto import marcar_vistas, notas_vistas
from radar.noticias.viabilidad import _en_historico, _muestra, _si, criterio, guardar, reporte
from radar.oficial.vigencia import Corpus

log = logging.getLogger(__name__)

PRUEBA = "Semáforo: distancia y reglas"
INFO = "Semáforo (informativo)"
MODELO = "minilm"
TIPOS_FUERA = frozenset({"definicion"})  # hubness: no aportan tema y serían el "párrafo más cercano"
PALABRAS_CORTO = 100  # titular con resumen: p99 de 74 palabras; cuerpo: p1 de 117
PALABRAS_MINIMAS = 5
PERCENTIL_CERCANO = 95  # del control negativo: el p25 de un positivo chico es inestable
PERCENTIL_LEJANO = 75  # del control negativo (README)
PERCENTIL_POSITIVO = 25  # S2: sin cruce con el p75 del negativo (README)
AUC_MINIMO = embeddings.AUC_SEMAFORO  # S2
CERCANO_NEGATIVO_MAXIMO = 0.10  # S3
LEJANO_NEGATIVO_MINIMO = 0.60  # S3
LEJANO_POSITIVO_MAXIMO = 0.25  # S4
CONSULTA_MAXIMA_S = 2.0  # S6
CONSULTAS = 20
SEMILLA_NEGATIVOS = "semaforo-negativos-7nov"
NEGATIVOS_POR_MEDIO = 100
CUERPOS_POR_MEDIO = 25

CORTO, CUERPO, INSUFICIENTE = "corto", "cuerpo", "insuficiente"
TIPOS_TEXTO = (CORTO, CUERPO)
CERCANO, INTERMEDIO, LEJANO = "cercano", "intermedio", "lejano"
COLOR_DE_BANDA = {CERCANO: "verde", INTERMEDIO: "amarillo", LEJANO: "gris"}
SIN_AFIRMACIONES = "sin_afirmaciones"
POSITIVO, NEGATIVO, NEGATIVO_NUEVO = "positivo", "negativo", "negativo_nuevo"


# ---------------------------------------------------------------- reglas puras


def tipo_de_texto(texto):
    """corto (titular, título y descripción), cuerpo o insuficiente: cada tipo tiene sus umbrales."""
    palabras = len((texto or "").split())
    if palabras < PALABRAS_MINIMAS:
        return INSUFICIENTE
    return CORTO if palabras <= PALABRAS_CORTO else CUERPO


def banda(coseno, umbral):
    """cercano, intermedio o lejano frente a los umbrales del tipo de texto; None sin coseno o sin umbral."""
    if coseno is None or not umbral:
        return None
    if coseno >= umbral["cercano"]:
        return CERCANO
    return LEJANO if coseno <= umbral["lejano"] else INTERMEDIO


def combinar(color_reglas, banda_, con_color=True):
    """(color, origen): manda la capa 5 si hay afirmaciones evaluables; si no, la banda de la distancia."""
    if color_reglas != SIN_AFIRMACIONES:
        return color_reglas, "reglas"
    if banda_ is None:
        return "sin_color", "ninguno"
    return (COLOR_DE_BANDA[banda_] if con_color else "sin_color"), "distancia"


def umbrales_de(positivos, negativos):
    """Umbrales de un tipo de texto a partir de los controles, con su E3 (S2)."""
    if not len(positivos) or not len(negativos):
        raise ValueError("Sin controles para calibrar")
    valor, ic = embeddings.auc(positivos, negativos)
    p25, p75 = float(np.percentile(positivos, PERCENTIL_POSITIVO)), float(np.percentile(negativos, PERCENTIL_LEJANO))
    return {
        "cercano": round(float(np.percentile(negativos, PERCENTIL_CERCANO)), 4),
        "lejano": round(p75, 4),
        "auc": valor,
        "auc_ic": f"{ic[0]}-{ic[1]}",
        "p25_positivo": round(p25, 4),
        "p75_negativo": round(p75, 4),
        "positivos": len(positivos),
        "negativos": len(negativos),
        "con_color": valor is not None and valor >= AUC_MINIMO and p25 > p75,
    }


def es_si(valor):
    return valor in (True, 1, "1", "True", "true")


def leer_umbrales(ruta=None):
    """{tipo: umbral} de config/semaforo_umbrales.csv; vacío si aún no se calibró."""
    ruta = ruta or config.ARCHIVO_UMBRALES_SEMAFORO
    if not ruta.exists():
        return {}
    numeros = ("cercano", "lejano", "auc", "p25_positivo", "p75_negativo")
    return {
        f["tipo"]: {**f, **{k: float(f[k]) for k in numeros if f[k]}, "con_color": es_si(f["con_color"])}
        for f in leer_csv(ruta)
    }


# ---------------------------------------------------------------- C1 del semáforo: casos sintéticos

UMBRAL_SINTETICO = {"cercano": 0.5, "lejano": 0.3, "con_color": True}
CASOS_BANDA = (  # (coseno, banda esperada)
    (0.9, CERCANO), (0.5, CERCANO), (0.49, INTERMEDIO), (0.31, INTERMEDIO), (0.3, LEJANO), (0.0, LEJANO),
    (None, None),
)  # fmt: skip
CASOS_COMBINACION = (  # (color de la capa 5, banda, con_color, (color, origen))
    ("rojo", CERCANO, True, ("rojo", "reglas")),
    ("rojo", LEJANO, True, ("rojo", "reglas")),
    ("amarillo", CERCANO, True, ("amarillo", "reglas")),
    ("verde", LEJANO, True, ("verde", "reglas")),
    ("verde", None, True, ("verde", "reglas")),
    (SIN_AFIRMACIONES, CERCANO, True, ("verde", "distancia")),
    (SIN_AFIRMACIONES, INTERMEDIO, True, ("amarillo", "distancia")),
    (SIN_AFIRMACIONES, LEJANO, True, ("gris", "distancia")),
    (SIN_AFIRMACIONES, CERCANO, False, ("sin_color", "distancia")),
    (SIN_AFIRMACIONES, None, True, ("sin_color", "ninguno")),
)
CASOS_TIPO = (("El Niño", INSUFICIENTE), ("uno dos tres cuatro cinco", CORTO), (" ".join(["p"] * 100), CORTO),
              (" ".join(["p"] * 101), CUERPO))  # fmt: skip


def criterio_logica():
    """S1: bandas, combinación y tipo de texto."""
    total, malos = 0, []
    for coseno, esperado in CASOS_BANDA:
        total += 1
        if banda(coseno, UMBRAL_SINTETICO) != esperado:
            malos.append(f"banda {coseno}")
    for reglas, b, con_color, esperado in CASOS_COMBINACION:
        total += 1
        if combinar(reglas, b, con_color) != esperado:
            malos.append(f"{reglas}+{b}")
    for texto, esperado in CASOS_TIPO:
        total += 1
        if tipo_de_texto(texto) != esperado:
            malos.append(f"tipo {len(texto.split())} palabras")
    return criterio(PRUEBA, "S1. Lógica (casos sintéticos)", f"{total - len(malos)}/{total}", "100 %", not malos,
                    "; ".join(malos))  # fmt: skip


# ---------------------------------------------------------------- el semáforo


class Semaforo:
    """minilm con los párrafos del ENFEN embebidos una vez, la historia de comunicados y los umbrales."""

    def __init__(self, corpus=None, umbrales=None):
        self.corpus = corpus or Corpus()
        self.historia = discrepancia.referencia(self.corpus)
        self.parrafos = [p for p in self.corpus.parrafos if p["fuente"] == "enfen"]
        st = candidatos.cargar(MODELO)
        pre_nota, pre_oficial = candidatos.prefijos(MODELO)
        self.modelo = candidatos.Candidato(MODELO, st, pre_nota)
        self.oficial = embeddings.Oficial(candidatos.Candidato(MODELO, st, pre_oficial), self.parrafos)
        self.fuera = np.array([p["tipo"] in TIPOS_FUERA for p in self.parrafos])
        self.umbrales = leer_umbrales() if umbrales is None else umbrales

    def distancia(self, texto, fecha):
        """(coseno máximo, párrafo) frente a los párrafos vigentes sin definiciones; None si no hay con qué comparar."""
        mascara = candidatos.vigentes(self.parrafos, fecha) & ~self.fuera
        tramos = self.modelo.tramos(texto)
        if not tramos or not mascara.any():
            return None
        maximos = candidatos.maximos_por_parrafo(self.modelo.embeber(tramos), self.oficial, "con")
        i = int(np.where(mascara, maximos, -2).argmax())
        return round(float(maximos[i]), 4), self.parrafos[i]

    def reglas(self, fecha, titular, resumen, cuerpo):
        """(color de la capa 5, filas sin campos internos)."""
        filas = []
        for a in af.afirmaciones(titular, resumen, cuerpo, fecha):
            filas += discrepancia.clasificar(a, fecha, self.historia)
        return discrepancia.color(filas), [{k: v for k, v in f.items() if not k.startswith("_")} for f in filas]

    def _medir(self, texto_distancia, fecha, titular, resumen, cuerpo):
        fecha = fecha[:10]
        tipo = tipo_de_texto(texto_distancia)
        color_reglas, filas = self.reglas(fecha, titular, resumen, cuerpo)
        medida = self.distancia(texto_distancia, fecha) if tipo != INSUFICIENTE else None
        coseno, parrafo = medida if medida else (None, None)
        umbral = self.umbrales.get(tipo)
        banda_ = banda(coseno, umbral)
        color, origen = combinar(color_reglas, banda_, bool(umbral) and umbral["con_color"])
        return {
            "color": color,
            "origen": origen,
            "color_reglas": color_reglas,
            "tipo_texto": tipo,
            "palabras": len(texto_distancia.split()),
            "coseno": coseno,
            "banda": banda_,
            "parrafo": parrafo["id"] if parrafo else None,
            "tipo_parrafo": parrafo["tipo"] if parrafo else None,
            "comunicado": parrafo["doc_id"] if parrafo else None,
            "umbrales": {k: umbral[k] for k in ("cercano", "lejano", "con_color")} if umbral else None,
            "filas": filas,
        }

    def medir(self, texto, fecha, titular="", resumen=""):
        """Un texto libre (titular, título y descripción de un video, o una nota pegada) en una fecha aaaa-mm-dd."""
        completo = "\n".join(x for x in (titular, resumen, texto) if x and x.strip())
        return self._medir(completo, fecha, titular, resumen, texto)

    def medir_nota(self, campos, fecha):
        """Una nota leída: el texto de la distancia es el de E3 (titular, resumen si no está en el cuerpo, cuerpo)."""
        texto, _ = tfidf.texto_de(campos)
        return self._medir(texto, fecha, campos["titular"], campos["resumen"], campos["cuerpo"])


@functools.cache
def _semaforo():
    return Semaforo()


def medir_discrepancia(texto, fecha, titular="", resumen=""):
    """La función única del semáforo (app, agente, videos). Carga minilm la primera vez."""
    return _semaforo().medir(texto, fecha, titular, resumen)


# ---------------------------------------------------------------- muestras y controles


def positivo_limpio(notas):
    """Control positivo de E3 sin las citas falsas: Andina que cita un comunicado y menciona El Niño."""
    citan = embeddings.positivas(notas)
    return {(n["medio"], n["id"]) for n in notas if (n["medio"], n["id"]) in citan and _si(n["menciona_nino"])}


def negativos_elegibles(notas, vistas, control):
    """La definición de otros_temas del control negativo, sin las notas vistas ni las del control."""
    fuera = vistas | {(c["medio"], c["id"]) for c in control}
    return [n for n in notas if _en_historico(n) and not _si(n["sin_texto"]) and not _si(n["menciona_nino"])
            and not n["terminos_cuerpo"] and (n["medio"], n["id"]) not in fuera]  # fmt: skip


def muestra_negativos(notas, vistas, control):
    elegibles = negativos_elegibles(notas, vistas, control)
    return [x for m in MEDIOS for x in _muestra([n for n in elegibles if n["medio"] == m], NEGATIVOS_POR_MEDIO,
                                                 SEMILLA_NEGATIVOS, m)]  # fmt: skip


def cuerpos_de(negativos):
    """Las CUERPOS_POR_MEDIO de cada medio que se leen en cuerpo."""
    return [x for m in MEDIOS for x in _muestra([n for n in negativos if n["medio"] == m], CUERPOS_POR_MEDIO,
                                                 SEMILLA_NEGATIVOS, m, "cuerpo")]  # fmt: skip


def elegir_muestra():
    if viabilidad.registrada(SEMILLA_NEGATIVOS):
        log.info(f"La muestra {SEMILLA_NEGATIVOS} ya está en notas_vistas.csv; no se elige otra.")
        return []
    notas = leer_csv(config.DIR_NOTICIAS / "notas.csv")
    elegidas = muestra_negativos(notas, notas_vistas(), leer_csv(config.DIR_NOTICIAS / "control_negativo.csv"))
    marcar_vistas(elegidas, SEMILLA_NEGATIVOS)
    log.info(f"Muestra: {len(elegidas)} · {collections.Counter(n['medio'] for n in elegidas)}")
    return []


def negativos_registrados(notas):
    elegidas = set(viabilidad.registrada(SEMILLA_NEGATIVOS))
    if not elegidas:
        raise SystemExit("Falta la muestra: python -m radar.nlp.semaforo muestra")
    return [n for n in notas if (n["medio"], n["id"]) in elegidas]


def controles(notas):
    """[(nota, grupo)] del control positivo limpio y del negativo (otros_temas) de E3."""
    por_clave = {(n["medio"], n["id"]): n for n in notas}
    positivos = [(por_clave[k], POSITIVO) for k in sorted(positivo_limpio(notas))]
    control = leer_csv(config.DIR_NOTICIAS / "control_negativo.csv")
    negativos = [(por_clave[k], NEGATIVO) for c in control if c["estrato"] == tfidf.ESTRATO_NEGATIVO
                 and (k := (c["medio"], c["id"])) in por_clave]  # fmt: skip
    return positivos + negativos


# ---------------------------------------------------------------- lectura (sin guardar el texto)


def archivo(nombre):
    return config.DIR_NLP / f"semaforo-{nombre}.csv"


def fila_leida(semaforo, historia):
    def fila_de(nota, grupo, campos):
        fila = {"medio": nota["medio"], "id": nota["id"], "grupo": grupo, "error": ""}
        if not isinstance(campos, dict):
            return {**fila, "error": str(campos)[:200]}
        if campos["sin_texto"]:
            return {**fila, "error": "sin texto"}
        fecha = nota["fecha_publicacion"][:10]
        r = semaforo.medir_nota(campos, fecha)
        capa5 = discrepancia.fila_de_nota(nota, campos, historia)["color"]  # el camino validado de la capa 5
        return fila | {"palabras": r["palabras"], "coseno": r["coseno"], "parrafo": r["parrafo"],
                       "tipo_parrafo": r["tipo_parrafo"], "color_capa5": capa5, "color": r["color"],
                       "origen": r["origen"]}  # fmt: skip

    return fila_de


@exclusivo("radar.nlp.semaforo")
def _leer(lista, ruta, semaforo, parar):
    with sin_suspension():
        tfidf.leer_cuerpos(lista, ruta, esquemas.SEMAFORO_LECTURA, fila_leida(semaforo, semaforo.historia), parar)
    return leer_csv(ruta)


def cosenos_cortos(semaforo, lista):
    """{grupo: [coseno]} del titular con el resumen, sin red."""
    salida = collections.defaultdict(list)
    for nota, grupo in lista:
        medida = semaforo.distancia(reranker.texto_corto(nota), nota["fecha_publicacion"][:10])
        if medida:
            salida[grupo].append(medida[0])
    return salida


def _numeros(filas, grupo):
    return [float(f["coseno"]) for f in filas if f["grupo"] == grupo and not f["error"] and f["coseno"]]


def calibrar(parar):
    notas = leer_csv(config.DIR_NOTICIAS / "notas.csv")
    lista = controles(notas)
    semaforo = Semaforo(umbrales={})
    log.info(f"Controles: {collections.Counter(g for _, g in lista)}")
    cortos = cosenos_cortos(semaforo, lista)
    leidas = _leer(lista, archivo("calibracion"), semaforo, parar)
    if not isinstance(leidas, list):
        raise SystemExit(leidas)
    por_tipo = {CORTO: (cortos[POSITIVO], cortos[NEGATIVO]), CUERPO: (_numeros(leidas, POSITIVO),
                                                                       _numeros(leidas, NEGATIVO))}  # fmt: skip
    hoy = dt.date.today().isoformat()
    umbrales = [{"tipo": t, **umbrales_de(*por_tipo[t]), "fecha": hoy} for t in TIPOS_TEXTO]
    escribir_csv(config.ARCHIVO_UMBRALES_SEMAFORO, esquemas.SEMAFORO_UMBRALES, umbrales)
    return [criterio_e3(u) for u in umbrales]


def criterio_e3(u):
    """S2: E3 con la configuración final y el positivo limpio."""
    con_color = es_si(u["con_color"])
    return criterio(PRUEBA, f"S2. E3 en {u['tipo']} (positivo limpio, vigentes sin definiciones)", u["auc"],
                    f"≥ {AUC_MINIMO} y p25 positivo > p75 negativo", con_color,
                    f"IC95 {u['auc_ic']}; p25 positivo {u['p25_positivo']}, p75 negativo {u['p75_negativo']}; "
                    f"cercano ≥ {u['cercano']}, lejano ≤ {u['lejano']}; n {u['positivos']} frente a "
                    f"{u['negativos']}")  # fmt: skip


# ---------------------------------------------------------------- validación


def _proporciones(bandas):
    conteo, total = collections.Counter(bandas), max(1, len(bandas))
    return {b: round(conteo[b] / total, 3) for b in (CERCANO, INTERMEDIO, LEJANO)}, len(bandas)


def criterio_negativos(tipo, cosenos, umbral):
    """S3: los negativos nuevos casi nunca quedan cercanos y en su mayoría quedan lejanos."""
    p, n = _proporciones([banda(c, umbral) for c in cosenos])
    pasa = n > 0 and p[CERCANO] <= CERCANO_NEGATIVO_MAXIMO and p[LEJANO] >= LEJANO_NEGATIVO_MINIMO
    return criterio(PRUEBA, f"S3. Negativos nuevos en {tipo}: cercano / lejano", f"{p[CERCANO]} / {p[LEJANO]}",
                    f"≤ {CERCANO_NEGATIVO_MAXIMO} / ≥ {LEJANO_NEGATIVO_MINIMO}", pasa,
                    f"n {n}; intermedio {p[INTERMEDIO]}")  # fmt: skip


def resumenes_oficiales(corpus):
    """[(texto, fecha del día anterior a su emisión)] de los párrafos de resumen sin duplicados, en corto."""
    emision = {c["id"]: c["fecha_emision"] for c in corpus.comunicados}
    primero = min(emision.values())
    salida = []
    for p in corpus.parrafos:
        fecha = emision.get(p["doc_id"])
        if (p["fuente"] != "enfen" or p["seccion"] != "resumen" or p["duplicado_de"] or not fecha or fecha == primero
                or tipo_de_texto(p["texto"]) != CORTO):  # fmt: skip
            continue
        salida.append((p["texto"], (dt.date.fromisoformat(fecha) - dt.timedelta(days=1)).isoformat()))
    return salida


def criterio_oficial(semaforo, umbral):
    """S4: texto oficial frente al comunicado anterior; casi nunca lejano (prueba fácil: solo descarta lo grueso)."""
    cosenos = [m[0] for texto, fecha in resumenes_oficiales(semaforo.corpus) if (m := semaforo.distancia(texto, fecha))]
    p, n = _proporciones([banda(c, umbral) for c in cosenos])
    return criterio(PRUEBA, "S4. Resúmenes del ENFEN frente al comunicado anterior (corto): lejano", p[LEJANO],
                    f"≤ {LEJANO_POSITIVO_MAXIMO}", n > 0 and p[LEJANO] <= LEJANO_POSITIVO_MAXIMO,
                    f"n {n}; cercano {p[CERCANO]}, intermedio {p[INTERMEDIO]}")  # fmt: skip


def criterio_reglas_mandan(filas):
    """S5: con afirmaciones evaluables, el color es el de la capa 5."""
    con = [f for f in filas if not f["error"] and f["color_capa5"] and f["color_capa5"] != SIN_AFIRMACIONES]
    malas = [f"{f['medio']} {f['id']}" for f in con if f["color"] != f["color_capa5"] or f["origen"] != "reglas"]
    return criterio(PRUEBA, "S5. Con afirmaciones, manda la capa 5", f"{len(con) - len(malas)}/{len(con)}", "100 %",
                    bool(con) and not malas, "; ".join(malas[:10]))  # fmt: skip


def criterio_tiempo(semaforo, notas):
    textos = [reranker.texto_corto(n) for n in notas[:CONSULTAS]]
    tiempos = []
    for texto, nota in zip(textos, notas, strict=False):
        inicio = time.perf_counter()
        semaforo.medir(texto, nota["fecha_publicacion"][:10])
        tiempos.append(time.perf_counter() - inicio)
    mediana = round(statistics.median(tiempos), 3)
    return criterio(PRUEBA, "S6. Tiempo por consulta (mediana)", mediana, f"≤ {CONSULTA_MAXIMA_S} s",
                    mediana <= CONSULTA_MAXIMA_S, f"n {len(tiempos)}; máximo {max(tiempos):.3f} s")  # fmt: skip


def descriptivos(calibracion, leidas):
    """Solo descriptivo. En la calibración (leída sin umbrales) se cuenta el color de la capa 5; en los cuerpos nuevos,
    el color final, su origen y el tipo del párrafo más parecido."""
    salida = []
    for grupo in (POSITIVO, NEGATIVO):
        g = [f for f in calibracion if not f["error"] and f["grupo"] == grupo]
        if g:
            capa5 = collections.Counter(f["color_capa5"] for f in g)
            salida.append(criterio(INFO, f"capa 5 en los controles: {grupo}", len(g), "", True, str(dict(capa5))))
    g = [f for f in leidas if not f["error"]]
    if g:
        colores, origen = collections.Counter(f["color"] for f in g), collections.Counter(f["origen"] for f in g)
        tipos = collections.Counter(f["tipo_parrafo"] for f in g)
        salida.append(criterio(INFO, f"colores en cuerpo: {NEGATIVO_NUEVO}", len(g), "", True,
                               f"{dict(colores)}; origen {dict(origen)}; párrafo {dict(tipos)}"))  # fmt: skip
    return salida


def validar(parar):
    umbrales = leer_umbrales()
    if set(umbrales) != set(TIPOS_TEXTO):
        raise SystemExit("Faltan los umbrales: python -m radar.nlp.semaforo calibrar")
    notas = leer_csv(config.DIR_NOTICIAS / "notas.csv")
    negativos = negativos_registrados(notas)
    semaforo = Semaforo(umbrales=umbrales)
    filas = [criterio_logica(), *[criterio_e3(umbrales[t]) for t in TIPOS_TEXTO]]
    cortos = cosenos_cortos(semaforo, [(n, NEGATIVO_NUEVO) for n in negativos])[NEGATIVO_NUEVO]
    filas.append(criterio_negativos(CORTO, cortos, umbrales[CORTO]))
    leidas = _leer([(n, NEGATIVO_NUEVO) for n in cuerpos_de(negativos)], archivo("validacion"), semaforo, parar)
    if not isinstance(leidas, list):
        raise SystemExit(leidas)
    filas.append(criterio_negativos(CUERPO, _numeros(leidas, NEGATIVO_NUEVO), umbrales[CUERPO]))
    filas.append(criterio_oficial(semaforo, umbrales[CORTO]))
    calibracion = leer_csv(archivo("calibracion")) if archivo("calibracion").exists() else []
    filas.append(criterio_reglas_mandan(calibracion + leidas))
    filas.append(criterio_tiempo(semaforo, negativos))
    return filas + descriptivos(calibracion, leidas)


def main(argv=None):
    ap = argparse.ArgumentParser(description="Semáforo: la capa 5 y la distancia en una sola función.")
    ap.add_argument("paso", choices=("muestra", "calibrar", "validar"))
    args = ap.parse_args(argv)
    registro = configurar(f"nlp-semaforo-{args.paso}")
    inicio, parar = ahora(), threading.Event()
    config.DIR_NLP.mkdir(parents=True, exist_ok=True)
    pasos = {
        "muestra": lambda: elegir_muestra(),
        "calibrar": lambda: calibrar(parar),
        "validar": lambda: validar(parar),
    }
    try:
        filas = pasos[args.paso]()
    except KeyboardInterrupt:
        parar.set()
        return 1
    if filas:
        guardar(filas, config.DIR_NLP / "validacion.csv")
        reporte(filas, [], inicio)
    log.info(
        f"Duración: {(ahora() - inicio).total_seconds() / 60:.1f} min · registro: {registro.relative_to(config.RAIZ)}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
