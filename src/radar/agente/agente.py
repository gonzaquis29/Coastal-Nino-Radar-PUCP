"""Agente con herramientas sin LLM: reglas para lo genérico y embeddings para elegir la herramienta (definición
aprobada el 9-nov, docs/agente/definicion.md).

Las reglas solo cubren lo que no depende de la redacción: si la consulta no trata del dominio (fuera de alcance) y si
trae un texto para contrastar (comillas, "¿es cierto…?", una afirmación larga sin pregunta). El resto lo decide la
similitud minilm entre la consulta y las descripciones de cada herramienta, escritas sin mirar las preguntas de
evaluación como ejemplos. La fecha, la macro-región y el interés se extraen con reglas.

Uso: python -m radar.agente.agente validar
     python -m radar.agente.agente preguntar "¿Seguimos en alerta por El Niño?"
"""

import argparse
import collections
import datetime as dt
import functools
import logging
import random
import re
import statistics
import sys
import time

import numpy as np

from radar import config
from radar.agente import herramientas as h
from radar.comun.archivos import escribir_csv, leer_csv
from radar.comun.regiones import COSTA_CENTRO, COSTA_NORTE, LIMA_Y_CALLAO, regiones_mencionadas
from radar.comun.registro import configurar
from radar.comun.texto import ahora, sin_tildes
from radar.nlp import recuperador, semaforo
from radar.noticias.validar_texto import marcar_vistas, notas_vistas
from radar.noticias.viabilidad import _muestra, criterio, guardar, reporte

log = logging.getLogger(__name__)

PRUEBA = "Agente: validación"
INFO = "Agente (informativo)"
HERRAMIENTAS = ("estado_vigente", "buscar_oficial", "recomendar", "medir_discrepancia")
FUERA = "fuera_de_alcance"
ACIERTO_MINIMO = 0.90  # A1
PARAMETROS_MINIMO = 0.95  # A2
FUERA_MINIMO, ABSTENCION_MAXIMA = 0.90, 0.05  # A4
CONSULTA_MAXIMA_S = 2.0  # A5
PALABRAS_AFIRMACION = 8  # una afirmación sin "?" con al menos estas palabras es un texto para contrastar
DIAS_ATRAS, DIAS_ADELANTE = 300, 60  # año de una fecha sin año
HOY_EVALUACION = "2026-11-09"
MUESTRA = "agente-9nov"
TITULARES_POR_GRUPO = 100
PERFIL = {"macroregion": COSTA_NORTE, "interes": "prevencion"}

# El dominio: si no aparece nada de esto, no hay herramienta que responda
DOMINIO = re.compile(
    r"\bni[nñ][oa]\b|enfen|senamhi|clima|lluvi|precipitac|calor|temperatura|\bmar\b|pesca|pescador|anchoveta|aviso|"
    r"alerta|huaico|inundac|oleaje|friaje|sequ[ií]a|caudal|\brios?\b|desborde|verano|meteorol|comunicado|emergencia|"
    r"prevenci|tsm|fenomeno|costa",
    re.I,
)
CONTRASTE = re.compile(r"es cierto|es verdad|es correcto|verific|le[ií] que|dicen que|coincide con lo oficial|"
                       r"confiable es esto|[\"“”«»]", re.I)  # fmt: skip
CITA_ENTRE_COMILLAS = re.compile(r"[\"“«]([^\"”»]{8,})[\"”»]")
PREFIJO_CONTRASTE = re.compile(
    r"^\s*(?:¿\s*)?(?:es cierto que|es verdad que|le[ií] que|dicen que|un video dice que)\s*", re.I
)

# Descripciones de cada herramienta (no son preguntas de la evaluación)
DESCRIPCIONES = {
    "estado_vigente": (
        "estado vigente del sistema de alerta ante El Niño costero",
        "nivel de alerta y magnitud prevista en el último comunicado del ENFEN",
        "avisos meteorológicos del Senamhi que rigen en una región en una fecha",
    ),
    "buscar_oficial": (
        "qué dicen los comunicados del ENFEN sobre el pronóstico y la evolución de las condiciones",
        "impactos esperados en lluvias, caudales de ríos y temperatura del aire y del mar",
        "efectos en la pesca y la anchoveta según el ENFEN",
        "recomendaciones del ENFEN a las autoridades",
        "qué prevé el Senamhi para un día por lluvias o temperatura",
    ),
    "recomendar": (
        "recomendar qué información oficial y qué notas leer según la región y el interés de la persona",
        "sugerir fuentes confiables para un perfil como pescador o vecino de una región",
    ),
}
INTERESES = (
    ("pesca", re.compile(r"pesca|pescador|anchoveta|\bmar\b", re.I)),
    ("lluvias", re.compile(r"lluvi|inundac|huaico|\brios?\b|caudal|precipitac", re.I)),
    ("calor", re.compile(r"calor|temperatura", re.I)),
    ("prevencion", re.compile(r"prevenci|prepar|emergencia", re.I)),
)
MESES = recuperador.MESES
FECHA = re.compile(r"(\d{1,2}) de (" + "|".join(MESES) + r")(?: de (20\d\d))?", re.I)


# ---------------------------------------------------------------- parámetros


def fecha_de(texto, hoy):
    """La fecha que nombra el texto ("15 de marzo", "hoy", "mañana", "ayer"); si no nombra ninguna, None."""
    t = sin_tildes(texto).lower()
    base = dt.date.fromisoformat(hoy)
    for palabra, dias in (("pasado manana", 2), ("manana", 1), ("ayer", -1), ("hoy", 0)):
        if re.search(rf"\b{palabra}\b", t):
            return (base + dt.timedelta(dias)).isoformat()
    m = FECHA.search(t)
    if not m:
        return None
    dia, mes = int(m.group(1)), MESES.index(m.group(2).lower()) + 1
    if m.group(3):
        return dt.date(int(m.group(3)), mes, dia).isoformat()
    for anio in (base.year, base.year - 1, base.year + 1):
        try:
            f = dt.date(anio, mes, dia)
        except ValueError:
            continue
        if -DIAS_ATRAS <= (f - base).days <= DIAS_ADELANTE:
            return f.isoformat()
    return None


def macroregion_de(texto):
    """La macro-región del texto si nombra una sola (costa norte, costa centro o Lima); si no, None."""
    regiones = regiones_mencionadas(texto) & {COSTA_NORTE, COSTA_CENTRO, LIMA_Y_CALLAO}
    return next(iter(regiones)) if len(regiones) == 1 else None


def interes_de(texto):
    for nombre, regex in INTERESES:
        if regex.search(texto):
            return nombre
    return None


def texto_a_contrastar(consulta):
    m = CITA_ENTRE_COMILLAS.search(consulta)
    if m:
        return m.group(1).strip()
    return PREFIJO_CONTRASTE.sub("", consulta).rstrip("?¿ ").strip()


# ---------------------------------------------------------------- enrutador


class Enrutador:
    def __init__(self):
        self.oficial = h.oficial()
        self.etiquetas, frases = [], []
        for herramienta, descripciones in DESCRIPCIONES.items():
            self.etiquetas += [herramienta] * len(descripciones)
            frases += descripciones
        self.vectores = self.oficial.embeber(frases)

    def elegir(self, consulta):
        """(herramienta, origen de la decisión)."""
        if not DOMINIO.search(sin_tildes(consulta)):
            return FUERA, "regla: fuera del dominio"
        if CONTRASTE.search(consulta):
            return "medir_discrepancia", "regla: texto para contrastar"
        if "?" not in consulta and len(consulta.split()) >= PALABRAS_AFIRMACION:
            return "medir_discrepancia", "regla: afirmación sin pregunta"
        sim = self.vectores @ self.oficial.embeber([consulta])[0]
        return self.etiquetas[int(np.argmax(sim))], "embeddings"


@functools.cache
def enrutador():
    return Enrutador()


def responder(consulta, hoy=None, perfil=None):
    """La respuesta completa: herramienta, parámetros, texto con plantilla y citas literales."""
    hoy = hoy or dt.date.today().isoformat()
    perfil = perfil or PERFIL
    herramienta, origen = enrutador().elegir(consulta)
    parametros = {
        "fecha": fecha_de(consulta, hoy) or hoy,
        "macroregion": macroregion_de(consulta) or perfil["macroregion"],
        "interes": interes_de(consulta) or perfil["interes"],
    }
    if herramienta == FUERA:
        r = {"herramienta": FUERA, "texto": h.FUERA_DE_ALCANCE, "citas": []}
    elif herramienta == "estado_vigente":
        r = h.estado_vigente(parametros["fecha"], parametros["macroregion"])
    elif herramienta == "buscar_oficial":
        r = h.buscar_oficial(consulta, parametros["fecha"], macroregion_de(consulta))
    elif herramienta == "recomendar":
        r = h.recomendar(parametros["fecha"], parametros["macroregion"], parametros["interes"], consulta)
    else:
        r = h.medir_discrepancia(texto_a_contrastar(consulta), parametros["fecha"])
    return {**r, "origen": origen, "parametros": parametros}


# ---------------------------------------------------------------- evaluación


VALORES_REGION = {"la costa norte": COSTA_NORTE, "la costa centro": COSTA_CENTRO, "Lima": LIMA_Y_CALLAO,
                  "Piura": COSTA_NORTE}  # fmt: skip
VALORES_DIA = {"15 de marzo": "2026-03-15", "2 de octubre": "2026-10-02"}


def casos_congelados(filas):
    """Las redacciones de config/agente_preguntas.csv con sus valores: [{redaccion, pregunta, aceptables, esperado}]."""
    salida = []
    for f in filas:
        regiones = VALORES_REGION.items() if "{region}" in f["texto"] else [(None, None)]
        dias = VALORES_DIA.items() if "{dia}" in f["texto"] else [(None, None)]
        for texto_region, macro in regiones:
            for texto_dia, fecha in dias:
                pregunta = f["texto"].replace("{region}", texto_region or "").replace("{dia}", texto_dia or "")
                hoy = "hoy" if re.search(r"\bhoy\b", pregunta) else None
                esperado = {"macroregion": macro, "fecha": fecha or hoy, "interes": f["interes"] or None}
                salida.append({"redaccion": f["id"], "pregunta": pregunta, "hoy": HOY_EVALUACION,
                               "aceptables": {f["herramienta"], *filter(None, f["aceptables"].split("|"))},
                               "esperado": esperado})  # fmt: skip
    return salida


def casos_recuperador(preguntas):
    """Las preguntas del recuperador (6-nov): A y C buscan; B se reparte por redacción. La consulta se hace en la fecha
    de la pregunta (en el uso real se pregunta por días cercanos), así que el año de "1 de enero" no es ambiguo."""
    salida = []
    for p in preguntas:
        redaccion = int(p["id"].rsplit("-", 1)[1])
        if p["grupo"] == "B":
            aceptables = {"estado_vigente", "buscar_oficial"}
            macro = next((m for m in (COSTA_NORTE, COSTA_CENTRO) if m in p["id"]), None)
            esperado = {"fecha": p["fecha"], "macroregion": macro, "interes": None}
        else:
            aceptables = {"buscar_oficial"}
            esperado = {"fecha": p["fecha"] if p["grupo"] == "C" else None, "macroregion": None, "interes": None}
        salida.append({"redaccion": f"recuperador-{p['grupo']}{redaccion}", "pregunta": p["pregunta"],
                       "hoy": p["fecha"], "aceptables": aceptables,
                       "esperado": esperado})  # fmt: skip
    return salida


def parametros_bien(caso, parametros):
    """[(nombre, acertó)] de los parámetros que la pregunta da."""
    salida = []
    for nombre, valor in caso["esperado"].items():
        if valor is None:
            continue
        valor = caso["hoy"] if valor == "hoy" else valor
        salida.append((nombre, parametros[nombre] == valor))
    return salida


def titulares(notas, vistas):
    """Informativo: titulares sin ver que mencionan El Niño (contrastar) y de otros temas (fuera de alcance)."""
    control = leer_csv(config.DIR_NOTICIAS / "control_negativo.csv")
    menciona = [n for n in notas if n["menciona_nino"] == "1" and n["sobre_nino"] != "1"
                and (n["medio"], n["id"]) not in vistas and n["titular"].strip()]  # fmt: skip
    otros = [n for n in semaforo.negativos_elegibles(notas, vistas, control) if n["titular"].strip()]
    return (_muestra(menciona, TITULARES_POR_GRUPO, MUESTRA, "menciona"),
            _muestra(otros, TITULARES_POR_GRUPO, MUESTRA, "otros"))  # fmt: skip


def evaluar(casos):
    filas = []
    for caso in casos:
        inicio = time.perf_counter()
        r = responder(caso["pregunta"], caso["hoy"])
        segundos = time.perf_counter() - inicio
        literales, citas = h.citas_literales(r, h.corpus().parrafos)
        bien = parametros_bien(caso, r["parametros"])
        filas.append({"redaccion": caso["redaccion"], "herramienta": r["herramienta"], "origen": r["origen"],
                      "acierto": int(r["herramienta"] in caso["aceptables"]),
                      "esperada": "|".join(sorted(caso["aceptables"])),
                      "parametros_bien": sum(b for _, b in bien), "parametros": len(bien),
                      "citas_literales": literales, "citas": citas, "segundos": round(segundos, 4)})  # fmt: skip
    return filas


def por_redaccion(filas):
    grupos = collections.defaultdict(list)
    for f in filas:
        grupos[f["redaccion"]].append(f["acierto"])
    return {r: statistics.mean(v) for r, v in grupos.items()}


def criterios(filas, informativas):
    validas = [f for f in filas if FUERA not in f["esperada"]]
    fuera = [f for f in filas if f["esperada"] == FUERA]
    acierto = por_redaccion(validas)
    a1 = statistics.mean(acierto.values())
    malas = sorted(((v, r) for r, v in acierto.items() if v < 1))[:8]
    p_bien, p_total = sum(f["parametros_bien"] for f in filas), sum(f["parametros"] for f in filas)
    c_bien, c_total = sum(f["citas_literales"] for f in filas), sum(f["citas"] for f in filas)
    a4 = statistics.mean(f["herramienta"] == FUERA for f in fuera)
    abst = statistics.mean(f["herramienta"] == FUERA for f in validas)
    mediana = statistics.median(f["segundos"] for f in filas)
    salida = [
        criterio(PRUEBA, "A1. Herramienta correcta, promedio por redacción", round(a1, 3), f"≥ {ACIERTO_MINIMO}",
                 a1 >= ACIERTO_MINIMO, f"{len(acierto)} redacciones; peores: "
                 + ", ".join(f"{r} {v:.2f}" for v, r in malas)),
        criterio(PRUEBA, "A2. Parámetros extraídos bien", f"{p_bien}/{p_total}", f"≥ {PARAMETROS_MINIMO}",
                 p_total and p_bien / p_total >= PARAMETROS_MINIMO),
        criterio(PRUEBA, "A3. Citas literales", f"{c_bien}/{c_total}", "100 %", c_bien == c_total),
        criterio(PRUEBA, "A4. Fuera de alcance sin herramienta", round(a4, 3), f"≥ {FUERA_MINIMO}", a4 >= FUERA_MINIMO,
                 f"{len(fuera)} casos"),
        criterio(PRUEBA, "A4. Abstenciones en preguntas válidas", round(abst, 3), f"≤ {ABSTENCION_MAXIMA}",
                 abst <= ABSTENCION_MAXIMA, f"{len(validas)} casos"),
        criterio(PRUEBA, "A5. Tiempo por consulta (mediana)", round(mediana, 3), f"≤ {CONSULTA_MAXIMA_S} s",
                 mediana <= CONSULTA_MAXIMA_S, f"máximo {max(f['segundos'] for f in filas):.2f} s"),
    ]  # fmt: skip
    origenes = collections.Counter(f["origen"] for f in filas)
    salida.append(criterio(INFO, "Origen de las decisiones", "", "", True, str(dict(origenes))))
    for nombre, g in informativas.items():
        aciertos = statistics.mean(f["acierto"] for f in g) if g else 0
        salida.append(criterio(INFO, f"Titulares sin ver: {nombre}", f"{aciertos:.3f}", "", True,
                               str(dict(collections.Counter(f["herramienta"] for f in g)))))  # fmt: skip
    return salida


def validar():
    congelados = casos_congelados(leer_csv(config.DIR_CONFIG / "agente_preguntas.csv"))
    del_recuperador = casos_recuperador(leer_csv(config.DIR_NLP / "recuperador-preguntas.csv"))
    filas = evaluar(congelados + del_recuperador)
    notas = leer_csv(config.DIR_NOTICIAS / "notas.csv")
    vistas = notas_vistas()
    menciona, otros = titulares(notas, vistas)
    if not any(f["muestra"] == MUESTRA for f in leer_csv(config.ARCHIVO_NOTAS_VISTAS)):
        marcar_vistas(menciona + otros, MUESTRA)
    informativas = {
        "mencionan El Niño → contrastar": evaluar([{"redaccion": "titular", "pregunta": n["titular"],
                                                     "hoy": n["fecha_publicacion"][:10],
                                                     "aceptables": {"medir_discrepancia"}, "esperado": {}}
                                                    for n in menciona]),
        "otros temas → fuera de alcance": evaluar([{"redaccion": "titular", "pregunta": n["titular"],
                                                     "hoy": n["fecha_publicacion"][:10], "aceptables": {FUERA},
                                                     "esperado": {}} for n in otros]),
    }  # fmt: skip
    escribir_csv(config.DIR_AGENTE / "agente.csv", tuple(filas[0]), filas)
    return criterios(filas, informativas)


def main(argv=None):
    ap = argparse.ArgumentParser(description="Agente con herramientas (reglas y embeddings, sin LLM).")
    ap.add_argument("paso", choices=("validar", "preguntar"))
    ap.add_argument("consulta", nargs="?")
    ap.add_argument("--hoy", default=None)
    args = ap.parse_args(argv)
    if args.paso == "preguntar":
        r = responder(args.consulta or "", args.hoy)
        print(f"[{r['herramienta']} · {r['origen']} · {r['parametros']}]\n{r['texto']}")
        for c in r["citas"]:
            print(f"  «{c['cita']}» ({c['documento']}, {c['parrafo']})")
        return 0
    registro = configurar("agente-validar")
    inicio = ahora()
    config.DIR_AGENTE.mkdir(parents=True, exist_ok=True)
    random.seed(0)
    filas = validar()
    guardar(filas, config.DIR_AGENTE / "validacion.csv")
    reporte(filas, [], inicio)
    log.info(f"Registro: {registro.relative_to(config.RAIZ)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
