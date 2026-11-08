"""Único intento con NLI, solo para los pronósticos de impacto sin datos (docs/nlp/discrepancia.md, punto 5.2).

Una frase que nombra El Niño, no trae datos (magnitud, estado, fechas) y pronostica un impacto ("traerá lluvias por
encima de lo normal") se compara con las 3 frases más parecidas (minilm) de los párrafos de impactos y pronóstico del
comunicado vigente. Marca "posible diferencia (NLI)" si alguna la contradice por encima de τ y ninguna la implica por
encima de τ. τ se calibra con enero a junio y se evalúa con julio a octubre; si no pasa, el NLI se cierra.

Uso: python -m radar.nlp.nli validar   # N1 a N3 y N5 sin red; N4 pide páginas (30 notas)
"""

import argparse
import collections
import datetime as dt
import logging
import re
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
from radar.comun.texto import ahora, sha1_corto
from radar.nlp import afirmaciones as af
from radar.nlp import candidatos, discrepancia, esquemas, semaforo, tfidf, viabilidad
from radar.noticias.viabilidad import criterio, guardar, reporte
from radar.oficial.vigencia import Corpus

log = logging.getLogger(__name__)

PRUEBA = "NLI: pronósticos de impacto sin datos"
INFO = "NLI (informativo)"
HILOS = 12
PREMISAS = 3
TIPOS_PREMISA = ("impactos", "pronostico")
REGION_FUERA = "nino_3.4"
GRILLA = tuple(round(0.50 + 0.05 * i, 2) for i in range(10))  # 0,50 … 0,95
CORTE_CALIBRACION = "2026-07-01"  # antes: calibra τ; desde: decide
DIAS_PAR = 31  # N2: comunicados a un mes o menos
PROPIA_MAXIMA = 0.05  # N1
IGUAL_MAXIMA = 0.10  # N2, lado "no cambia"
DETECCION_MINIMA = 0.60  # N2, lado "cambia"
CASOS_MINIMOS = 20  # N2: con menos casos que cambian en julio-octubre, el NLI se cierra
PERTURBACION_MINIMA = 0.80  # N3
NOTAS_MAXIMA = 0.10  # N4
CONSULTA_MAXIMA_S = 2.0  # N5
CONSULTAS = 20

# Población (medida el 8-nov antes de definir): impacto pronosticado, sin hablar de medidas
VARIABLE = re.compile(r"lluvi|precipitaci|caudal|temperatura|calor|anchoveta|huaico|desborde|inundaci|sequ[íi]a|oleaje"
                      r"|\bmar\b", re.I)  # fmt: skip
PRONOSTICO = re.compile(r"\b\w{3,}(?:rá|rán|ría|rían)\b|pronostic|se espera|prev[ée]|proyect|probab|tendenc|advierte",
                        re.I)  # fmt: skip
MEDIDA = re.compile(r"plan|prevenci|prepar|declar|emergencia|ministr|gobierno|alcald|municip|presupuest|obras"
                    r"|limpieza|descolmat|simulacro|precio|cómo|recomend", re.I)  # fmt: skip

# Pares naturales (N2) y perturbaciones (N3): variable, región explícita y categoría frente a lo normal
VARIABLES = {
    "lluvia": re.compile(r"lluvi|precipitaci", re.I),
    "caudal": re.compile(r"caudal", re.I),
    "t_aire": re.compile(r"temperatura\w*\s+(?:del\s+aire|m[áa]xima|m[íi]nima|diurna|nocturna)", re.I),
    "tsm": re.compile(r"temperatura\s+superficial\s+del\s+mar|\bTSM\b|temperatura\s+del\s+mar", re.I),
    "anchoveta": re.compile(r"anchoveta", re.I),
}
REGIONES = {"norte": re.compile(r"costa\s+norte", re.I), "centro": re.compile(r"costa\s+centr", re.I),
            "sur": re.compile(r"costa\s+sur", re.I)}  # fmt: skip
ENCIMA = re.compile(r"por\s+encima(?:\s+de\s+(?:lo|sus\s+valores)\s+normal\w*)?|superior\w*(?:\s+a\s+(?:lo|sus\s+"
                    r"valores)\s+normal\w*)?", re.I)  # fmt: skip
DEBAJO = re.compile(r"por\s+debajo(?:\s+de\s+(?:lo|sus\s+valores)\s+normal\w*)?|inferior\w*(?:\s+a\s+(?:lo|sus\s+"
                    r"valores)\s+normal\w*)?|d[ée]ficit\w*", re.I)  # fmt: skip
NORMAL = re.compile(r"\bnormal(?:es)?\b", re.I)
CAMBIO = (("por encima", "por debajo"), ("superior", "inferior"))


def de_impacto(frase):
    return bool(VARIABLE.search(frase) and PRONOSTICO.search(frase) and not MEDIDA.search(frase))


def poblacion(titular, resumen, cuerpo, fecha):
    """Afirmaciones de la capa 3 sin datos, evaluables, no de otra fuente, que pronostican un impacto."""
    return [a for a in af.afirmaciones(titular, resumen, cuerpo, fecha, sin_datos=True)
            if discrepancia.evaluable(a) and a["atribucion"] != "agencia" and not a["otro_pais"]
            and de_impacto(a["_texto"])]  # fmt: skip


def categorias(frase):
    """{encima, debajo, normal} frente a lo normal; "de normales a superiores" da las dos."""
    salida, resto = set(), frase
    for nombre, regex in (("encima", ENCIMA), ("debajo", DEBAJO)):
        if regex.search(resto):
            salida.add(nombre)
            resto = regex.sub(" ", resto)
    if NORMAL.search(resto):
        salida.add("normal")
    return salida


def simple(frase):
    """(variable, región, categoría) si la frase tiene una sola de cada una; si no, None."""
    variables = [v for v, r in VARIABLES.items() if r.search(frase)]
    regiones = [g for g, r in REGIONES.items() if r.search(frase)]
    cats = categorias(frase)
    if len(variables) == 1 and len(regiones) == 1 and len(cats) == 1:
        return variables[0], regiones[0], next(iter(cats))
    return None


def perturbar(frase):
    """La frase con "por encima" ↔ "por debajo" (y superior ↔ inferior); None si no es de una sola de esas dos."""
    cats = categorias(frase)
    if cats not in ({"encima"}, {"debajo"}):
        return None
    pares = CAMBIO if cats == {"encima"} else tuple((b, a) for a, b in CAMBIO)
    nueva = frase
    for de, a in pares:
        nueva = re.sub(de, a, nueva, flags=re.I)
    return nueva if nueva != frase else None


def marca(contra, implica, tau):
    """La regla: alguna premisa contradice por encima de τ y ninguna implica por encima de τ."""
    return contra > tau and implica <= tau


def elegir_tau(calibracion):
    """El menor τ de la grilla que en enero-junio cumple N1 ≤ 5 % y el lado "no cambia" de N2 ≤ 10 %; None si ninguno.
    calibracion: {"propia": [(contra, implica)], "igual": [...]}."""
    for tau in GRILLA:
        propia = _tasa(calibracion["propia"], tau)
        igual = _tasa(calibracion["igual"], tau)
        if propia is not None and propia <= PROPIA_MAXIMA and (igual is None or igual <= IGUAL_MAXIMA):
            return tau
    return None


def _tasa(pares, tau):
    return sum(marca(c, i, tau) for c, i in pares) / len(pares) if pares else None


# ---------------------------------------------------------------- frases oficiales y premisas


def _normal(texto):
    return " ".join(texto.split()).lower()


def frases_oficiales(corpus):
    """{comunicado: [frase]} de los párrafos de impactos y pronóstico, sin el Pacífico central ni duplicados."""
    salida = collections.defaultdict(list)
    ids = {c["id"] for c in corpus.comunicados}
    for p in corpus.parrafos:
        if (p["fuente"] != "enfen" or p["doc_id"] not in ids or p["tipo"] not in TIPOS_PREMISA
                or p["region_enso"] == REGION_FUERA or p["duplicado_de"]
                or p["seccion"] not in ("titular", "resumen", "cuerpo")):  # fmt: skip
            continue
        for _, _, frase, corta in af.frases("", "", p["texto"]):
            if not corta and _normal(frase) not in {_normal(f) for f in salida[p["doc_id"]]}:
                salida[p["doc_id"]].append(frase)
    return salida


class Nli:
    """mDeBERTa en float32 con 12 hilos y minilm para elegir las premisas del comunicado."""

    def __init__(self, corpus=None):
        import torch

        torch.set_num_threads(HILOS)
        self.corpus = corpus or Corpus()
        self.modelo = viabilidad.Torch(config.MODELO_NLI)
        etiquetas = {v.lower(): k for k, v in self.modelo.modelo.config.id2label.items()}
        self.i_implica, self.i_contra = etiquetas["entailment"], etiquetas["contradiction"]
        st = candidatos.cargar(semaforo.MODELO)
        self.embebedor = candidatos.Candidato(semaforo.MODELO, st, candidatos.prefijos(semaforo.MODELO)[0])
        self.oficiales = frases_oficiales(self.corpus)
        self._vectores = {}

    def _vectores_de(self, comunicado):
        if comunicado not in self._vectores:
            self._vectores[comunicado] = self.embebedor.embeber(self.oficiales[comunicado])
        return self._vectores[comunicado]

    def premisas(self, hipotesis, comunicados, excluir=None):
        """Las PREMISAS frases más parecidas de los comunicados, sin la frase `excluir`."""
        candidatas, vectores = [], []
        for c in comunicados:
            for frase, v in zip(self.oficiales.get(c, []), self._vectores_de(c), strict=False):
                if excluir is None or _normal(frase) != _normal(excluir):
                    candidatas.append(frase)
                    vectores.append(v)
        if not candidatas:
            return []
        h = self.embebedor.embeber([hipotesis])[0]
        orden = np.argsort(-(np.vstack(vectores) @ h))[:PREMISAS]
        return [candidatas[i] for i in orden]

    def medir(self, hipotesis, comunicados, excluir=None):
        """(contradicción máxima, implicación máxima) frente a las premisas; None si no hay premisas."""
        premisas = self.premisas(hipotesis, comunicados, excluir)
        if not premisas:
            return None
        p = self.modelo.nli(premisas, [hipotesis] * len(premisas))
        return round(float(p[:, self.i_contra].max()), 4), round(float(p[:, self.i_implica].max()), 4)

    def vigentes(self, fecha):
        c = self.corpus.comunicado_vigente(fecha)
        return [c["id"]] if c else []


# ---------------------------------------------------------------- casos de N1 a N3 (texto oficial)


def _mitad(fecha):
    return "calibracion" if fecha < CORTE_CALIBRACION else "decide"


def casos_oficiales(corpus, oficiales):
    """[{prueba, mitad, hipotesis, comunicados, excluir, etiqueta}] de N1, N2 y N3."""
    emision = {c["id"]: c["fecha_emision"] for c in corpus.comunicados}
    sin_datos = {c: [f for f in fs if de_impacto(f) and not af.tiene_dato(af.datos(f, emision[c]))]
                 for c, fs in oficiales.items()}  # fmt: skip
    simples = {c: [(f, s) for f in fs if (s := simple(f))] for c, fs in oficiales.items()}
    salida = []
    for c, frases in sin_datos.items():
        for f in frases:
            salida.append({"prueba": "N1", "mitad": _mitad(emision[c]), "hipotesis": f, "comunicados": [c],
                           "excluir": f, "etiqueta": "", "comunicado": c, "referencia": c})  # fmt: skip
    for j, frases in simples.items():
        fj = dt.date.fromisoformat(emision[j])
        for f, (var, reg, cat) in frases:
            for i in simples:
                if i == j or abs((dt.date.fromisoformat(emision[i]) - fj).days) > DIAS_PAR:
                    continue
                cats = {s[2] for _, s in simples[i] if s[:2] == (var, reg)}
                if not cats:
                    continue
                etiqueta = "cambia" if cat not in cats else ("igual" if cats == {cat} else "")
                if etiqueta:
                    salida.append({"prueba": "N2", "mitad": _mitad(emision[j]), "hipotesis": f, "comunicados": [i],
                                   "excluir": None, "etiqueta": etiqueta, "comunicado": j,
                                   "referencia": i})  # fmt: skip
            if (nueva := perturbar(f)) is not None:
                salida.append({"prueba": "N3", "mitad": _mitad(emision[j]), "hipotesis": nueva, "comunicados": [j],
                               "excluir": None, "etiqueta": "cambia", "comunicado": j, "referencia": j})  # fmt: skip
    return salida


def medir_casos(nli, casos):
    filas = []
    for k, caso in enumerate(casos, 1):
        medida = nli.medir(caso["hipotesis"], caso["comunicados"], caso["excluir"])
        if medida:
            filas.append({"prueba": caso["prueba"], "mitad": caso["mitad"], "comunicado": caso["comunicado"],
                          "referencia": caso["referencia"], "etiqueta": caso["etiqueta"],
                          "sha1": sha1_corto(caso["hipotesis"]),
                          "contra": medida[0], "implica": medida[1]})  # fmt: skip
        if k % 50 == 0:
            log.info(f"  {k}/{len(casos)}")
    return filas


def _pares(filas, prueba, mitad, etiqueta=None):
    return [
        (f["contra"], f["implica"])
        for f in filas
        if f["prueba"] == prueba and f["mitad"] == mitad and (etiqueta is None or f["etiqueta"] == etiqueta)
    ]


# ---------------------------------------------------------------- N4 y N5: notas


@exclusivo("radar.nlp.nli")
def _leer_positivos(nli, parar):
    notas = leer_csv(config.DIR_NOTICIAS / "notas.csv")
    claves = semaforo.positivo_limpio(notas)
    elegidas = [(n, "positivo") for n in notas if (n["medio"], n["id"]) in claves]
    ruta = config.DIR_NLP / "nli-notas.csv"
    ruta.unlink(missing_ok=True)
    filas = []

    def fila_de(nota, _grupo, campos):
        salida = {"medio": nota["medio"], "id": nota["id"], "error": "", "frases": 0}
        if not isinstance(campos, dict) or campos["sin_texto"]:
            return {**salida, "error": "sin texto o error"}
        fecha = nota["fecha_publicacion"][:10]
        medidas = [m for a in poblacion(campos["titular"], campos["resumen"], campos["cuerpo"], fecha)
                   if (m := nli.medir(a["_texto"], nli.vigentes(fecha)))]  # fmt: skip
        filas.extend(medidas)
        return {**salida, "frases": len(medidas)}

    with sin_suspension():
        tfidf.leer_cuerpos(elegidas, ruta, esquemas.NLI_NOTAS, fila_de, parar)
    return filas


def tiempo(nli, notas):
    tiempos = []
    for nota in notas[:CONSULTAS]:
        fecha = nota["fecha_publicacion"][:10]
        inicio = time.perf_counter()
        for a in poblacion(nota["titular"], nota["resumen"], "", fecha):
            nli.medir(a["_texto"], nli.vigentes(fecha))
        tiempos.append(time.perf_counter() - inicio)
    return round(statistics.median(tiempos), 3), round(max(tiempos), 3)


# ---------------------------------------------------------------- criterios


def _texto_tasa(pares, tau):
    t = _tasa(pares, tau)
    return (f"{sum(marca(c, i, tau) for c, i in pares)}/{len(pares)}", t)


def criterios(filas, tau, notas_medidas, consulta):
    if tau is None:
        return [criterio(PRUEBA, "τ calibrado en enero-junio", "ninguno", f"N1 ≤ {PROPIA_MAXIMA}, N2 igual ≤ "
                         f"{IGUAL_MAXIMA}", False, "ningún valor de la grilla cumple: el NLI se cierra")]  # fmt: skip
    n1, t1 = _texto_tasa(_pares(filas, "N1", "decide"), tau)
    cambia, igual = _pares(filas, "N2", "decide", "cambia"), _pares(filas, "N2", "decide", "igual")
    n2c, t2c = _texto_tasa(cambia, tau)
    n2i, t2i = _texto_tasa(igual, tau)
    n3, t3 = _texto_tasa(_pares(filas, "N3", "decide"), tau)
    n4, t4 = _texto_tasa(notas_medidas, tau)
    suficientes = len(cambia) >= CASOS_MINIMOS
    return [
        criterio(PRUEBA, "τ calibrado en enero-junio", tau, "menor de la grilla que cumple", True,
                 f"calibración: N1 {_texto_tasa(_pares(filas, 'N1', 'calibracion'), tau)[0]}, N2 igual "
                 f"{_texto_tasa(_pares(filas, 'N2', 'calibracion', 'igual'), tau)[0]}, N2 cambia "
                 f"{_texto_tasa(_pares(filas, 'N2', 'calibracion', 'cambia'), tau)[0]}"),
        criterio(PRUEBA, "N1. Frases propias marcadas (julio-octubre)", n1, f"≤ {PROPIA_MAXIMA}",
                 t1 is not None and t1 <= PROPIA_MAXIMA),
        criterio(PRUEBA, "N2. Casos que cambian (julio-octubre)", len(cambia), f"≥ {CASOS_MINIMOS}", suficientes,
                 "" if suficientes else "pocos casos: el NLI se cierra"),
        criterio(PRUEBA, "N2. Detecta si la categoría cambia", n2c, f"≥ {DETECCION_MINIMA}",
                 suficientes and t2c is not None and t2c >= DETECCION_MINIMA),
        criterio(PRUEBA, "N2. Marca si no cambia", n2i, f"≤ {IGUAL_MAXIMA}", t2i is None or t2i <= IGUAL_MAXIMA),
        criterio(PRUEBA, "N3. Perturbaciones detectadas", n3, f"≥ {PERTURBACION_MINIMA}",
                 t3 is not None and t3 >= PERTURBACION_MINIMA),
        criterio(PRUEBA, "N4. Frases de los positivos marcadas", n4, f"≤ {NOTAS_MAXIMA}",
                 t4 is not None and t4 <= NOTAS_MAXIMA),
        criterio(PRUEBA, "N5. Tiempo por consulta corta (mediana)", consulta[0], f"≤ {CONSULTA_MAXIMA_S} s",
                 consulta[0] <= CONSULTA_MAXIMA_S, f"máximo {consulta[1]} s"),
    ]  # fmt: skip


def informativos(filas):
    salida = []
    for prueba in ("N1", "N2", "N3"):
        for mitad in ("calibracion", "decide"):
            g = [f for f in filas if f["prueba"] == prueba and f["mitad"] == mitad]
            if g:
                etiquetas = collections.Counter(f["etiqueta"] or "-" for f in g)
                salida.append(criterio(INFO, f"{prueba} {mitad}: casos", len(g), "", True,
                                       f"{dict(etiquetas)}; contradicción mediana "
                                       f"{statistics.median(f['contra'] for f in g):.3f}"))  # fmt: skip
    return salida


def suficientes(casos):
    """Criterio previo de N2: sin al menos CASOS_MINIMOS pares que cambian en julio-octubre, el NLI se cierra sin
    cargar el modelo (8-nov: 0 con la regla aprobada y 6 aun con la región opcional)."""
    n = sum(c["prueba"] == "N2" and c["mitad"] == "decide" and c["etiqueta"] == "cambia" for c in casos)
    return criterio(PRUEBA, "N2. Casos que cambian (julio-octubre)", n, f"≥ {CASOS_MINIMOS}", n >= CASOS_MINIMOS,
                    "" if n >= CASOS_MINIMOS else "pocos casos: el NLI se cierra sin medir")  # fmt: skip


def validar(parar):
    corpus = Corpus()
    casos = casos_oficiales(corpus, frases_oficiales(corpus))
    conteo = collections.Counter((c["prueba"], c["mitad"], c["etiqueta"] or "-") for c in casos)
    previo = suficientes(casos)
    informe = [criterio(INFO, f"{p} {m}: casos {e}", n, "", True) for (p, m, e), n in sorted(conteo.items())]
    if not previo["pasa"]:
        return [previo] + informe
    nli = Nli(corpus)
    filas = medir_casos(nli, casos)
    escribir_csv(config.DIR_NLP / "nli.csv", esquemas.NLI, filas)
    tau = elegir_tau({"propia": _pares(filas, "N1", "calibracion"), "igual": _pares(filas, "N2", "calibracion",
                                                                                     "igual")})  # fmt: skip
    log.info(f"τ elegido: {tau}")
    notas_medidas = _leer_positivos(nli, parar)
    if not isinstance(notas_medidas, list):
        raise SystemExit(notas_medidas)
    notas = leer_csv(config.DIR_NOTICIAS / "notas.csv")
    positivos = semaforo.positivo_limpio(notas)
    consulta = tiempo(nli, [n for n in notas if (n["medio"], n["id"]) in positivos])
    return criterios(filas, tau, notas_medidas, consulta) + informativos(filas)


def main(argv=None):
    ap = argparse.ArgumentParser(description="Único intento con NLI: pronósticos de impacto sin datos.")
    ap.add_argument("paso", choices=("validar",))
    ap.parse_args(argv)
    registro = configurar("nlp-nli-validar")
    inicio, parar = ahora(), threading.Event()
    config.DIR_NLP.mkdir(parents=True, exist_ok=True)
    try:
        filas = validar(parar)
    except KeyboardInterrupt:
        parar.set()
        return 1
    guardar(filas, config.DIR_NLP / "validacion.csv")
    reporte(filas, [], inicio)
    log.info(
        f"Duración: {(ahora() - inicio).total_seconds() / 60:.1f} min · registro: {registro.relative_to(config.RAIZ)}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
