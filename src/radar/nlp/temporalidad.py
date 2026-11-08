"""Temporalidad (plazo v2) de la capa 3: qué dura el evento y en qué periodo tiene cada magnitud
(docs/nlp/discrepancia.md, definición del 7-nov). Cada fecha es un intervalo de meses, para no inventar precisión
("verano 2027" → dic-2026 a mar-2027).

Uso: python -m radar.nlp.temporalidad validar   # sin red: T1 a T4 con los textos oficiales y temporalidad-oficial.csv
"""

import argparse
import collections
import datetime as dt
import logging
import re
import sys

from radar import config
from radar.comun.archivos import escribir_csv
from radar.comun.registro import configurar
from radar.comun.texto import MESES, ahora
from radar.nlp import esquemas
from radar.noticias.viabilidad import criterio, guardar, reporte
from radar.oficial import enfen
from radar.oficial.vigencia import Corpus

log = logging.getLogger(__name__)

PRUEBA = "Capa 3: temporalidad"
TOLERANCIA_MESES = 1
COMPLETITUD_MINIMA = 0.95  # T2
PARAFRASIS_MINIMA = 0.90  # T3
EVENTO = "evento"

# ---------------------------------------------------------------- fechas como intervalos de meses
# Estaciones del hemisferio sur, como las usa el ENFEN ("verano (diciembre 2025 - marzo 2026)"); el verano de un año
# empieza en diciembre del anterior (mes 0). (inicio, fin) por modificador: sin modificador, toda la estación.
ESTACIONES = {
    "verano": {None: (0, 3), "inicio": (0, 1), "mediado": (1, 2), "fin": (2, 3)},  # 0 = diciembre del año anterior
    "otoño": {None: (4, 6), "inicio": (4, 4), "mediado": (5, 5), "fin": (6, 6)},
    "invierno": {None: (7, 9), "inicio": (7, 7), "mediado": (8, 8), "fin": (9, 9)},
    "primavera": {None: (10, 12), "inicio": (10, 10), "mediado": (11, 11), "fin": (12, 12)},
}
ANIO_POR_MODIFICADOR = {None: (1, 12), "inicio": (1, 3), "mediado": (5, 8), "fin": (10, 12)}
TRIMESTRES = {"primer": (1, 3), "segundo": (4, 6), "tercer": (7, 9), "cuarto": (10, 12)}
_MES = "|".join(MESES)
_EST = "|".join(ESTACIONES)
_MOD = r"inicios?|comienzos?|principios?|mediados|fin(?:es|ales?)?|finales"
FECHA = (
    rf"(?:(?P<mod{{n}}>{_MOD})\s+(?:de(?:l)?\s+)?)?(?:(?:el|la|los|las)\s+)?"
    r"(?:(?P<rel{n}>pr[óo]ximo|presente|este|siguiente|ese|dicho)\s+)?(?:mes\s+de\s+)?"
    rf"(?:(?P<mes{{n}}>{_MES})|(?P<est{{n}}>{_EST})|(?P<trim{{n}}>primer|segundo|tercer|cuarto)\s+trimestre"
    r"|(?P<primeros{n}>primeros\s+meses)|(?P<solo{n}>año\b|20\d\d))"
    r"(?:\s*(?:de\s+|del\s+)?(?:(?:el|ese)\s+)?(?P<anio{n}>20\d\d(?:\s*[-–]\s*20\d\d)?|presente\s+año|este\s+año"
    r"|pr[óo]ximo\s+año|ese\s+año|dicho\s+año))?"
)


def _fecha(n):
    return FECHA.replace("{n}", str(n)).replace("{{", "{").replace("}}", "}")


F1, F2 = _fecha(1), _fecha(2)
# Relaciones, en orden: un rango se lee antes que su "hasta" o su "de"
RANGO = re.compile(
    rf"\b(?:de|desde|entre|en)\s+(?:el\s+|la\s+)?{F1}\s*(?:a|al|y|hasta|[-–])\s+(?:el\s+|la\s+)?{F2}", re.I
)
# "verano (diciembre 2025 - marzo 2026)": la estación y su rango son una sola fecha
RANGO_PARENTESIS = re.compile(rf"(?:(?:este|el|del|pr[óo]ximo|siguiente)\s+)?(?:{_EST})?\s*\(\s*{F1}\s*[-–]\s*"
                              rf"{F2}\s*\)", re.I)  # fmt: skip
RANGO_GUION = re.compile(rf"\b{F1}\s*[-–]\s*{F2}", re.I)  # "trimestre junio – agosto"
INICIO = re.compile(rf"\b(?:iniciad[oa]|inici[óo]|comenz[óo]|empez[óo])\s+(?:en|a\s+partir\s+de)\s+"
                    rf"(?:el\s+|la\s+)?{F1}", re.I)  # fmt: skip
HASTA = re.compile(rf"\b(?:hasta|hacia)\s+(?:el\s+|la\s+|en\s+)?{F1}", re.I)
DESDE = re.compile(rf"\b(?:a\s+partir\s+de|desde)\s+(?:el\s+|la\s+)?{F1}", re.I)
PUNTO = re.compile(rf"\b(?:en|durante|para|antes\s+de)\s+(?:el\s+|la\s+)?{F1}", re.I)


def _mod(texto):
    t = (texto or "").lower()
    if not t:
        return None
    if t.startswith(("inicio", "comienzo", "principio")):
        return "inicio"
    return "mediado" if t.startswith("mediado") else "fin"


def _anio_explicito(m, n, frase_antes, fecha):
    texto = (m.group(f"anio{n}") or "").lower()
    if re.fullmatch(r"20\d\d\s*[-–]\s*20\d\d", texto):  # "verano 2026 - 2027": el verano de 2027
        return int(texto[-4:])
    if texto.isdigit():
        return int(texto)
    if "presente" in texto or "este" in texto:
        return fecha.year
    if "próximo" in texto or "proximo" in texto:
        return fecha.year + 1
    if "ese" in texto or "dicho" in texto:
        anios = re.findall(r"\b20\d\d\b", frase_antes)
        return int(anios[-1]) if anios else fecha.year
    return None


def _meses(m, n):
    """(inicio, fin) en meses del año (el verano empieza en -1 = diciembre del año anterior), y si el año es fijo."""
    mod = _mod(m.group(f"mod{n}"))
    if m.group(f"mes{n}"):
        mes = MESES[m.group(f"mes{n}").lower()]
        return (mes, mes), None
    if m.group(f"est{n}"):
        return ESTACIONES[m.group(f"est{n}").lower()][mod], None
    if m.group(f"trim{n}"):
        return TRIMESTRES[m.group(f"trim{n}").lower()], None
    if m.group(f"primeros{n}"):
        return (1, 3), None
    solo = m.group(f"solo{n}").lower()
    return ANIO_POR_MODIFICADOR[mod], (int(solo) if solo.isdigit() else "año")


def _indice(anio, mes):
    return anio * 12 + (mes - 1)  # mes -1 (diciembre anterior) también vale


def intervalo(m, n, fecha, frase_antes=""):
    """(desde, hasta) en meses absolutos de la fecha n de la coincidencia; sin año, la próxima vez desde la fecha."""
    fecha = dt.date.fromisoformat(fecha[:10]) if isinstance(fecha, str) else fecha
    (ini, fin), anio_fijo = _meses(m, n)
    anio = _anio_explicito(m, n, frase_antes, fecha)
    if isinstance(anio_fijo, int):
        anio = anio_fijo
    elif anio_fijo == "año":
        rel = (m.group(f"rel{n}") or "").lower()
        anios_antes = re.findall(r"\b20\d\d\b", frase_antes)
        if rel in ("ese", "dicho") and anios_antes:
            anio = anio or int(anios_antes[-1])
        anio = anio or (fecha.year + (1 if rel.startswith(("pr", "sig")) else 0))
    elif anio is None:
        anio = fecha.year if _indice(fecha.year, fin) >= _indice(fecha.year, fecha.month) else fecha.year + 1
    return _indice(anio, ini), _indice(anio, fin)


def a_texto(i):
    return f"{i // 12:04d}-{i % 12 + 1:02d}"


def intervalo_texto(par):
    return a_texto(par[0]) if par[0] == par[1] else f"{a_texto(par[0])}..{a_texto(par[1])}"


# ---------------------------------------------------------------- sujeto de cada fecha

ANCLA = re.compile(r"Niño|evento|fen[óo]meno|calentamiento\s+del\s+mar|condiciones\s+c[áa]lidas|magnitud|intensidad"
                   r"|alerta", re.I)  # fmt: skip
CLIMA = re.compile(r"lluvi|precipitaci|caudal|r[íi]os?\b|crecid|viento|olea|temperatura|calor|fr[íi]o|sequ[íi]a"
                   r"|huaico|emergencia|declaratoria|bono|vigencia|medida|pesca|r[ée]cord|aire", re.I)  # fmt: skip
ECONOMIA = re.compile(r"\bPBI\b|\becon[óo]m|\binflaci|\bexportaci|\bcrecimiento\s+econ|\btrimestres\b", re.I)
OTRA_CONDICION = re.compile(r"condici[óo]n(?:es)?\s+neutra|Niña|condiciones\s+fr[íi]as|transici[óo]n", re.I)
# Desde aquí empieza otra fase del pronóstico: lo de antes no le da su magnitud
CORTE = re.compile(r";|\.\s|\bluego\b|\bposteriormente\b|\breduci\w*|\bdisminu\w*|\bdeclive\b|\btender[íi]a\b",
                   re.I)  # fmt: skip
DECLIVE = re.compile(r"reduci|disminu|declive|tender", re.I)
PALABRAS_VENTANA = 10


def _clausula(frase, inicio, fin):
    """(antes, después, corte) de la cláusula alrededor de [inicio, fin): desde el último corte antes hasta el primero
    después; corte es el texto del corte que la abre ('' si empieza la frase)."""
    cortes_antes = list(CORTE.finditer(frase, 0, inicio))
    despues = CORTE.search(frase, fin)
    desde = cortes_antes[-1].end() if cortes_antes else 0
    corte = cortes_antes[-1].group(0) if cortes_antes else ""
    return frase[desde:inicio], frase[fin : despues.start() if despues else None], corte


VERBO_DE_DURACION = re.compile(r"\b(?:prolong|extend|extiend|continu|persist|expand|perdur|dur[ae]r?\b|dure\b)\w*",
                               re.I)  # fmt: skip
# "el comunicado publicado en julio": es cuándo se publicó, no un periodo del evento
PUBLICACION = re.compile(r"(?:publicad|emitid|difundid|presentad|comunicado|informe|bolet[íi]n|reporte)\w*\s+"
                         r"(?:\S+\s+){0,2}$", re.I)  # fmt: skip


def sujetos(frase, inicio, fin):
    """Magnitudes a las que se refiere la fecha, [EVENTO], o [] si no es de El Niño (clima, condición neutra)."""
    antes, despues, corte = _clausula(frase, inicio, fin)
    if DECLIVE.search(corte):  # "para luego disminuir a fuerte hasta…"; sin magnitud, el evento decae hasta esa fecha
        terminos = [enfen.magnitud_canonica(t.group(1)) for t in enfen.TERMINO.finditer(antes)]
        return list(dict.fromkeys(terminos)) or [EVENTO]
    mags = [v for v, _ in enfen.magnitudes_de_frase(antes)]
    ventana = " ".join(antes.split()[-PALABRAS_VENTANA:])
    clima = [m.end() for m in CLIMA.finditer(ventana)]
    ancla = [m.end() for m in ANCLA.finditer(ventana)]
    del_clima = bool(clima) and (not ancla or clima[-1] > ancla[-1])
    if not ancla and ECONOMIA.search(f"{ventana} {' '.join(despues.split()[:PALABRAS_VENTANA])}"):
        return []  # "los próximos dos trimestres… el PBI podría caer": plazo de la economía (arreglo del 7-nov)
    if not mags and not del_clima and VERBO_DE_DURACION.search(antes) and ancla:
        return [EVENTO]  # "se extendería hasta diciembre, con probabilidad de moderada…": es la duración del evento
    if not mags:
        mags = [v for v, _ in enfen.magnitudes_de_frase(despues)]
    if not mags and CLIMA.search(" ".join(despues.split()[:PALABRAS_VENTANA])) and not ANCLA.search(despues):
        return []  # "para el trimestre julio–setiembre se prevé que las temperaturas del aire…"
    if del_clima and not mags:
        return []
    otra = OTRA_CONDICION.search(ventana) or OTRA_CONDICION.search(" ".join(despues.split()[:PALABRAS_VENTANA]))
    if otra and not mags:
        return []  # "Para este verano (…), es más probable la condición neutra"
    if mags:
        return list(dict.fromkeys(mags))
    if ancla or re.search(r"Niño|evento|fen[óo]meno", antes, re.I):
        return [EVENTO]
    return []


# ---------------------------------------------------------------- segmentos


def segmentos(frase, fecha):
    """[{sujeto, inicio, fin, relacion, span}] de una frase; inicio o fin pueden ser None (solo "hasta" o "desde")."""
    salida, ocupado = [], []

    def libre(m):
        return all(m.end() <= a or m.start() >= b for a, b in ocupado)

    def agregar(m, relacion, ini, fin):
        ocupado.append((m.start(), m.end()))
        for s in sujetos(frase, m.start(), m.end()):
            salida.append({"sujeto": s, "inicio": ini, "fin": fin, "relacion": relacion, "span": (m.start(), m.end())})

    for regex in (RANGO_PARENTESIS, RANGO, RANGO_GUION):
        for m in regex.finditer(frase):
            if regex is RANGO_GUION and m.group("solo2") and not m.group("solo1"):
                continue  # "verano 2026 - 2027" es una sola fecha
            if libre(m):
                f2 = intervalo(m, 2, fecha, frase[: m.start()])
                f1 = intervalo(m, 1, fecha, frase[: m.start()])
                if _anio_explicito(m, 1, frase[: m.start()], dt.date.fromisoformat(fecha[:10])) is None and \
                        _meses(m, 1)[1] is None and _anio_explicito(m, 2, frase[: m.start()],
                                                                   dt.date.fromisoformat(fecha[:10])):  # fmt: skip
                    (ini, fin), _ = _meses(m, 1)  # "entre enero y marzo del 2030": enero de 2030
                    anio = f2[1] // 12
                    f1 = (_indice(anio, ini), _indice(anio, fin))
                if f1[0] > f2[1]:  # "de setiembre a enero" sin años: el inicio es del año anterior
                    f1 = (f1[0] - 12, f1[1] - 12)
                agregar(m, "rango", f1, f2)
    for regex, relacion in ((INICIO, "inicio"), (HASTA, "hasta"), (DESDE, "desde"), (PUNTO, "punto")):
        for m in regex.finditer(frase):
            if not libre(m):
                continue
            f = intervalo(m, 1, fecha, frase[: m.start()])
            if relacion in ("punto", "desde") and PUBLICACION.search(frase[max(0, m.start() - 60) : m.start()]):
                continue
            if relacion == "punto":
                antes, despues, corte = _clausula(frase, m.start(), m.end())
                tras_declive = DECLIVE.search(corte) and enfen.TERMINO.search(antes)  # "disminuiría a moderada en…"
                if not (tras_declive or enfen.magnitudes_de_frase(antes) or enfen.magnitudes_de_frase(despues)):
                    continue  # un punto solo cuenta junto a una magnitud ("moderada en julio")
            if relacion == "inicio":  # "el Niño Costero, iniciado en marzo de 2026": inicio del evento
                ocupado.append((m.start(), m.end()))
                salida.append({"sujeto": EVENTO, "inicio": f, "fin": None, "relacion": relacion,
                               "span": (m.start(), m.end())})  # fmt: skip
                continue
            agregar(m, relacion, f if relacion != "hasta" else None, f if relacion not in ("desde",) else None)
    return sorted(salida, key=lambda s: s["span"])


def a_celda(segs):
    """'sujeto:inicio..fin|…' con '?' donde no hay extremo."""

    def extremo(x):
        return intervalo_texto(x) if x else "?"

    return "|".join(f"{s['sujeto']}:{extremo(s['inicio'])}>{extremo(s['fin'])}" for s in segs)


# ---------------------------------------------------------------- comparación


def se_cruzan(a, b, tolerancia=TOLERANCIA_MESES):
    return a is not None and b is not None and a[0] - tolerancia <= b[1] and b[0] - tolerancia <= a[1]


def fin_del_evento(segs):
    """Fin del evento: el más tardío de los segmentos (el evento dura al menos lo que dura cada magnitud)."""
    fines = [s["fin"] for s in segs if s["fin"]]
    return [max(fines, key=lambda x: x[1])] if fines else []


def respaldado(seg, oficiales):
    """El segmento de una nota coincide con alguno del mismo sujeto en los oficiales. Un "hasta" se compara con el fin;
    un punto, un rango o un "desde", con el periodo oficial entero ("débil en marzo" cae en "débil de marzo a
    octubre")."""
    if seg["sujeto"] == EVENTO:
        candidatos = [{"inicio": None, "fin": f} for f in fin_del_evento(oficiales)]
        candidatos += [o for o in oficiales if o["sujeto"] == EVENTO]
    else:
        candidatos = [o for o in oficiales if o["sujeto"] == seg["sujeto"]]
    for o in candidatos:
        if seg["inicio"] is None:
            if seg["fin"] is None or se_cruzan(seg["fin"], o["fin"]):
                return True
        elif se_cruzan(_periodo(seg), _periodo(o)):
            return True
    return False


def _periodo(s):
    """(desde, hasta) de todo el segmento; sin un extremo, el otro hace de ambos."""
    ini, fin = s["inicio"] or s["fin"], s["fin"] or s["inicio"]
    return (ini[0], fin[1]) if ini and fin else None


# ---------------------------------------------------------------- referencia oficial


def frases_oficiales(corpus):
    """{id: [(seccion, frase)]} de las frases de la costa de cada comunicado, sin párrafos duplicados."""
    salida = collections.defaultdict(list)
    for p in corpus.parrafos:
        if p["fuente"] == "enfen" and p["seccion"] in ("titular", "resumen", "cuerpo") and not p["duplicado_de"]:
            for f in enfen._frases_costeras([p["texto"]]):
                salida[p["doc_id"]].append((p["seccion"], f))
    return salida


def oficial(corpus):
    """{id: [segmento con 'seccion' y 'frase_n']} de cada comunicado."""
    por_doc = frases_oficiales(corpus)
    salida = {}
    for c in corpus.comunicados:
        fecha = c["vigente_desde"] or c["fecha_emision"]
        segs = []
        for n, (seccion, f) in enumerate(por_doc[c["id"]]):
            segs += [{**s, "seccion": seccion, "frase_n": n} for s in segmentos(f, fecha)]
        salida[c["id"]] = segs
    return salida


# ---------------------------------------------------------------- criterios

# (texto, fecha del texto, inicio esperado, fin esperado) de la fecha, con la forma "AAAA-MM" o "AAAA-MM..AAAA-MM"
CASOS = (
    ("hasta octubre de 2026", "2026-01-15", None, "2026-10"),
    ("hasta noviembre del presente año", "2026-02-13", None, "2026-11"),
    ("hasta enero de 2027", "2026-04-16", None, "2027-01"),
    ("hasta el próximo verano de 2027", "2026-06-15", None, "2026-12..2027-03"),
    ("hasta el verano", "2026-08-14", None, "2026-12..2027-03"),
    ("hasta abril de 2027", "2026-07-17", None, "2027-04"),
    ("hasta mediados de otoño de 2027", "2026-09-14", None, "2027-05"),
    ("hasta enero 2027", "2026-09-28", None, "2027-01"),
    ("hasta el otoño de 2027", "2026-09-28", None, "2027-04..2027-06"),
    ("hasta fines de otoño de 2027", "2026-10-30", None, "2027-06"),
    ("hasta inicios del otoño de 2027", "2026-10-16", None, "2027-04"),
    ("hasta diciembre", "2026-06-15", None, "2026-12"),
    ("hasta 2027", "2026-06-01", None, "2027-01..2027-12"),
    ("hasta el primer trimestre del 2027", "2026-08-01", None, "2027-01..2027-03"),
    ("hasta los primeros meses del 2027", "2026-08-01", None, "2027-01..2027-03"),
    ("hasta el mes de octubre", "2026-03-01", None, "2026-10"),
    ("hasta finales de año", "2026-05-01", None, "2026-10..2026-12"),
    ("hasta el próximo año", "2026-10-01", None, "2027-01..2027-12"),
    ("hasta mediados de ese año", "2026-10-01", None, "2026-05..2026-08"),
    ("hacia el otoño de 2027", "2026-09-28", None, "2027-04..2027-06"),
    ("entre junio y septiembre", "2026-06-15", "2026-06", "2026-09"),
    ("entre junio y julio del presente año", "2026-04-16", "2026-06", "2026-07"),
    ("entre mayo y agosto de 2026", "2026-05-15", "2026-05", "2026-08"),
    ("de setiembre 2026 a enero de 2027", "2026-08-28", "2026-09", "2027-01"),
    ("de mayo a julio", "2026-03-27", "2026-05", "2026-07"),
    ("entre febrero y marzo de 2027", "2026-08-28", "2027-02", "2027-03"),
    ("verano (diciembre 2025 - marzo 2026)", "2025-12-18", "2025-12", "2026-03"),
    ("a partir de abril de 2026", "2025-12-18", "2026-04", None),
    ("a partir de marzo", "2026-02-13", "2026-03", None),
    ("en julio", "2026-02-13", "2026-07", "2026-07"),
    ("en otoño", "2026-03-13", "2026-04..2026-06", "2026-04..2026-06"),
    ("para el verano 2026 - 2027", "2026-06-15", "2026-12..2027-03", "2026-12..2027-03"),
)


def _caso(texto, fecha):
    """El primer segmento de una frase con El Niño y una magnitud, para que todas las relaciones cuenten."""
    segs = segmentos(f"El Niño costero de magnitud fuerte {texto}", fecha)
    if not segs:
        return None, None
    s = segs[0]
    return (intervalo_texto(s["inicio"]) if s["inicio"] else None, intervalo_texto(s["fin"]) if s["fin"] else None)


def criterio_normalizacion():
    malos = [f"{t} ({f}): {_caso(t, f)} en vez de {(i, e)}" for t, f, i, e in CASOS if _caso(t, f) != (i, e)]
    for m in malos:
        print("  [T1]", m)
    return criterio(PRUEBA, "T1: normalización (casos conocidos)", len(CASOS) - len(malos), len(CASOS), not malos,
                    "; ".join(malos)[:500])  # fmt: skip


FECHA_SUELTA = re.compile(rf"\b(?:{_MES}|{_EST}|trimestre|primeros\s+meses)\b", re.I)


def criterio_completitud(corpus, refs):
    """T2: cada mes o estación de una frase costera que va pegada a El Niño queda dentro de algún segmento."""
    por_doc = frases_oficiales(corpus)
    total, cubiertas, fuera = 0, 0, []
    for c in corpus.comunicados:
        fecha = c["vigente_desde"] or c["fecha_emision"]
        for _, f in por_doc[c["id"]]:
            segs = segmentos(f, fecha)
            for m in FECHA_SUELTA.finditer(f):
                dentro = any(a <= m.start() < b for a, b in (s["span"] for s in segs))
                if not dentro and not sujetos(f, m.start(), m.end()):
                    continue  # no es de El Niño (lluvias, temperatura del aire, condición neutra): se lista abajo
                total += 1
                cubiertas += dentro
                if not dentro:
                    fuera.append(f"{c['id']}: «{f[max(0, m.start() - 50) : m.end() + 15]}»")
    for x in fuera:
        print("  [T2 sin segmento]", x)
    pasa = total > 0 and cubiertas / total >= COMPLETITUD_MINIMA
    return criterio(PRUEBA, "T2: completitud en los comunicados", f"{cubiertas}/{total}",
                    f">= {COMPLETITUD_MINIMA:.0%}", pasa, f"{cubiertas / total:.3f}" if total else "")  # fmt: skip


def criterio_parafrasis(corpus, refs):
    """T3: lo que dicen el titular o el resumen se cruza con lo que dice el cuerpo, en frases distintas."""
    por_doc = frases_oficiales(corpus)
    ok, n, malos = 0, 0, []
    for c in corpus.comunicados:
        segs = refs[c["id"]]
        textos = por_doc[c["id"]]
        arriba = [s for s in segs if s["seccion"] in ("titular", "resumen")]
        cuerpo = [s for s in segs if s["seccion"] == "cuerpo"]
        for s in arriba:
            pares = [
                o for o in cuerpo if textos[o["frase_n"]][1] != textos[s["frase_n"]][1] and o["sujeto"] == s["sujeto"]
            ]
            if not pares:
                continue
            n += 1
            bien = respaldado(s, pares)
            ok += bien
            if not bien:
                malos.append(f"{c['id']} {s['sujeto']} {a_celda([s])} frente a {a_celda(pares)}")
    for x in malos:
        print("  [T3]", x)
    pasa = n > 0 and ok / n >= PARAFRASIS_MINIMA
    return criterio(PRUEBA, "T3: paráfrasis oficiales", f"{ok}/{n}", f">= {PARAFRASIS_MINIMA:.0%}", pasa,
                    f"{ok / n:.3f}" if n else "sin pares")  # fmt: skip


def referencia_del_evento(c, corpus):
    """El texto del fin del evento: el titular si lo tiene (N.° 17 a 19) o, si no, el plazo de comunicados.csv."""
    titular = [p["texto"] for p in corpus.parrafos if p["doc_id"] == c["id"] and p["seccion"] == "titular"]
    return titular[0] if titular else c["plazo"]


def criterio_historia(corpus, refs):
    """T4: el fin del evento extraído de cada comunicado es el de su referencia (titular o plazo)."""
    ok, n, malos = 0, 0, []
    for c in corpus.comunicados:
        texto = referencia_del_evento(c, corpus)
        fecha = c["vigente_desde"] or c["fecha_emision"]
        esperado = [s["fin"] for s in segmentos(f"El Niño costero {texto}", fecha) if s["fin"]]
        if not texto or not esperado:
            continue
        n += 1
        cuerpo = [s for s in refs[c["id"]] if s["seccion"] != "titular"]
        obtenido = fin_del_evento(cuerpo) if c["id"] not in TITULAR_ES_EVENTO else fin_del_evento(refs[c["id"]])
        bien = any(se_cruzan(e, o, 0) for e in esperado for o in obtenido)
        ok += bien
        if not bien:
            malos.append(f"{c['id']}: «{texto}» → {[intervalo_texto(e) for e in esperado]}; "
                         f"extraído {[intervalo_texto(o) for o in obtenido]}")  # fmt: skip
    for x in malos:
        print("  [T4]", x)
    return criterio(PRUEBA, "T4: fin del evento en cada comunicado", f"{ok}/{n}", "100 %", n > 0 and ok == n,
                    "; ".join(malos)[:500])  # fmt: skip


TITULAR_ES_EVENTO = set()  # el cuerpo debe dar el fin por sí solo: el titular no entra en lo extraído


def validar():
    corpus = Corpus()
    refs = oficial(corpus)
    filas_csv = [
        {"comunicado": cid, "seccion": s["seccion"], "frase_n": s["frase_n"], "sujeto": s["sujeto"],
         "relacion": s["relacion"], "inicio": intervalo_texto(s["inicio"]) if s["inicio"] else "",
         "fin": intervalo_texto(s["fin"]) if s["fin"] else ""}
        for cid, segs in refs.items() for s in segs
    ]  # fmt: skip
    escribir_csv(config.DIR_NLP / "temporalidad-oficial.csv", esquemas.TEMPORALIDAD_OFICIAL, filas_csv)
    return [
        criterio_normalizacion(),
        criterio_completitud(corpus, refs),
        criterio_parafrasis(corpus, refs),
        criterio_historia(corpus, refs),
        criterio(PRUEBA, "segmentos oficiales (informativo)", len(filas_csv), "", True,
                 str(collections.Counter(f["sujeto"] for f in filas_csv))),
    ]  # fmt: skip


def main(argv=None):
    ap = argparse.ArgumentParser(description="Temporalidad (plazo v2) de la capa 3.")
    ap.add_argument("paso", choices=("validar",))
    ap.parse_args(argv)
    registro = configurar("nlp-temporalidad")
    inicio = ahora()
    config.DIR_NLP.mkdir(parents=True, exist_ok=True)
    filas = validar()
    guardar(filas, config.DIR_NLP / "validacion.csv")
    reporte(filas, [], inicio)
    log.info(
        f"Duración: {(ahora() - inicio).total_seconds() / 60:.1f} min · registro: {registro.relative_to(config.RAIZ)}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
