"""Capa 5 del índice: comparación con lo oficial (docs/nlp/discrepancia.md, definición aprobada el 7-nov).

Cada dato de cada afirmación de la capa 3 (magnitud, estado, segmentos de fechas) queda en una categoría frente a la
historia de comunicados del ENFEN: respaldada, desactualizada, sin respaldo, contradice, de otra escala o de otra
fuente; además, si se adelantó a un comunicado siguiente, si afirma con más certeza que lo oficial y si va por encima
o por debajo de la magnitud máxima. No dice si una nota es verdadera o falsa: mide cuánto se aleja de lo oficial.

Uso: python -m radar.nlp.discrepancia muestra   # elige las notas nuevas de la validación y las agrega a notas_vistas
     python -m radar.nlp.discrepancia validar   # C1, C2 y C5 sobre lo oficial; con la muestra, pide páginas: C3, C4, C6
     python -m radar.nlp.discrepancia calcular  # todas las notas sobre El Niño (después de T5 y del recálculo final)
"""

import argparse
import collections
import datetime as dt
import logging
import re
import sys
import threading

from radar import config
from radar.comun.archivos import anexar_csv, escribir_csv, leer_csv
from radar.comun.candado import exclusivo
from radar.comun.energia import sin_suspension
from radar.comun.registro import configurar, describir
from radar.comun.texto import ahora
from radar.nlp import afirmaciones as af
from radar.nlp import esquemas, temporalidad, tfidf, viabilidad
from radar.noticias.medios import MEDIOS
from radar.noticias.validar_texto import marcar_vistas, notas_vistas
from radar.noticias.viabilidad import _muestra, criterio, guardar, reporte
from radar.oficial import enfen
from radar.oficial.vigencia import Corpus

log = logging.getLogger(__name__)

PRUEBA = "Capa 5: comparación"
SEMILLA = "capa5-validacion-7nov"
RONDAS = {"a": SEMILLA, "b": "capa5-validacion-7nov-b", "c": "capa5-validacion-7nov-c"}  # b: arreglos A-D; c: 4 más
TAMANO_MUESTRA = 200
RESPALDO_PROPIO_MINIMO = 0.98  # C2
ESPERADA_MINIMA = 0.95  # C2
DESPLAZAMIENTO_MINIMO = 0.80  # C3
CERTEZA_OFICIAL_MAXIMA = 0.02  # C5
DIAS_DESACTUALIZADA = 7  # C6
DIAS_ADELANTADA = 14  # C6
CASOS_DINAMICA_MINIMOS = 20  # C6: con menos es informativo
DIAS_ADELANTO = 30
COMUNICADOS_ADELANTO = 2
AÑO_PERTURBADO = "2030"

ORDEN = {"débil": 1, "moderada": 2, "fuerte": 3, "muy fuerte": 3.5, "extraordinaria": 4}
MAGNITUDES_COSTA = ("débil", "moderada", "fuerte", "extraordinaria")
COSTA, CENTRAL = "costa", "central"
CATEGORIAS = ("respaldada", "desactualizada", "sin_respaldo", "contradice", "otra_escala", "otra_fuente")
AMARILLAS = {"desactualizada", "sin_respaldo", "otra_escala", "mas_certeza"}

# Pronóstico en futuro simple ("será", "provocará"): sin cautela es más certeza que lo oficial
FUTURO = re.compile(r"\b\w{2,}(?:rá|rán)\b", re.I)


# ---------------------------------------------------------------- referencia


def _central_de_frase(frase, region_parrafo):
    """Magnitudes del Pacífico central de una frase oficial; en las que nombran las dos regiones, cada magnitud va
    con la región nombrada antes de ella."""
    region = af.region(frase)
    if region == CENTRAL or (region == "ambigua" and region_parrafo == "nino_3.4"):
        return {m for m, _ in enfen.magnitudes_de_frase(frase)}
    if region != "ambas":
        return set()
    cortes = sorted([(m.start(), CENTRAL) for m in enfen.MENCIONA_CENTRAL.finditer(frase)]
                    + [(m.start(), COSTA) for m in enfen.MENCIONA_COSTERA.finditer(frase)])  # fmt: skip
    salida = set()
    for (inicio, cual), siguiente in zip(cortes, [*cortes[1:], (len(frase), None)], strict=True):
        if cual == CENTRAL:
            salida |= {m for m, _ in enfen.magnitudes_de_frase(frase[inicio : siguiente[0]])}
    return salida


def referencia(corpus):
    """Historia de comunicados en orden: [{id, desde, estado, costa, central, segmentos}]."""
    central = collections.defaultdict(set)
    for p in corpus.parrafos:
        if p["fuente"] == "enfen" and p["seccion"] in ("titular", "resumen", "cuerpo") and not p["duplicado_de"]:
            for frase in enfen.FRASE.split(p["texto"]):
                central[p["doc_id"]] |= _central_de_frase(frase, p["region_enso"])
    segmentos = temporalidad.oficial(corpus)
    return heredar(
        [
            {
                "id": c["id"],
                "desde": c["fecha_emision"],
                "estado": af.ESTADO_DE_ENCABEZADO.get(c["estado"], ""),
                COSTA: set(filter(None, c["magnitudes_mencionadas"].split("|"))),
                "maxima": c["magnitud_max_prevista"],
                CENTRAL: central[c["id"]],
                "segmentos": segmentos[c["id"]],
            }
            for c in corpus.comunicados
        ]
    )


def heredar(historia):
    """Lo último dicho de cada escala sigue vigente mientras otro comunicado no lo cambie (ajuste del 7-nov): si un
    comunicado no da magnitud del Pacífico central, vale la del último que la dio; si no repite el plazo de una
    magnitud costera que sigue mencionando, vale el último plazo dado para ella. El evento no se hereda: su fin viene
    en cada comunicado y su inicio ya pasado lo cubre la regla de los hechos pasados."""
    salida, central, plazos = [], set(), {}
    for r in historia:
        r = {**r, "segmentos": list(r["segmentos"])}
        if r[CENTRAL]:
            central = set(r[CENTRAL])
        else:
            r[CENTRAL] = set(central)
        presentes = {s["sujeto"] for s in r["segmentos"]}
        for sujeto, segs in plazos.items():
            if sujeto not in presentes and sujeto in r[COSTA]:
                r["segmentos"] += segs
        for sujeto in presentes - {temporalidad.EVENTO}:
            plazos[sujeto] = [s for s in r["segmentos"] if s["sujeto"] == sujeto]
        plazos = {k: v for k, v in plazos.items() if k in r[COSTA]}  # una magnitud que se deja de mencionar se va
        salida.append(r)
    return salida


def indice_vigente(historia, fecha):
    """Índice del comunicado vigente en la fecha (el último emitido hasta ese día); None antes del primero."""
    previos = [i for i, r in enumerate(historia) if r["desde"] <= fecha[:10]]
    return previos[-1] if previos else None


def _dias(desde, hasta):
    return (dt.date.fromisoformat(hasta[:10]) - dt.date.fromisoformat(desde[:10])).days


# ---------------------------------------------------------------- categorías


def _categoria(en, historia, i, mismo_dia, sin_referencia=False, en_otra=None):
    """(categoría, comunicados atrás) de un dato con en(ref) -> lo respalda. El día de emisión vale también el anterior
    (no se sabe la hora de la nota; regla de radar.oficial.vigencia)."""
    if en(historia[i]) or (mismo_dia and i > 0 and en(historia[i - 1])):
        return "respaldada", 0
    atras = next((i - j for j in range(i - 1, -1, -1) if en(historia[j])), 0)
    if atras:  # antes que la otra escala: "costero débil" cuando ya es moderado está desactualizado (C2, 7-nov)
        return "desactualizada", atras
    if en_otra and en_otra(historia[i]):
        return "otra_escala", 0
    return ("sin_respaldo" if sin_referencia else "contradice"), 0


def _adelantada(en, historia, i, fecha):
    siguientes = historia[i + 1 : i + 1 + COMUNICADOS_ADELANTO]
    return any(en(r) and _dias(fecha, r["desde"]) <= DIAS_ADELANTO for r in siguientes)


def _maxima(ref, escala):
    if escala == COSTA:
        return ref["maxima"]
    return max(ref[CENTRAL], key=ORDEN.get) if ref[CENTRAL] else ""


def _sentido(m, ref, escala):
    maxima = _maxima(ref, escala)
    if not maxima:
        return ""
    return "mayor" if ORDEN[m] > ORDEN[maxima] else "menor" if ORDEN[m] < ORDEN[maxima] else "igual"


def _escalas(region):
    return (COSTA,) if region == COSTA else (CENTRAL,) if region == CENTRAL else (COSTA, CENTRAL)


def _tiene_sujeto(seg, oficiales):
    if seg["sujeto"] == temporalidad.EVENTO:
        return bool(temporalidad.fin_del_evento(oficiales)) or any(
            o["sujeto"] == temporalidad.EVENTO for o in oficiales
        )
    return any(o["sujeto"] == seg["sujeto"] for o in oficiales)


def _pasado(seg, mes):
    """El segmento ya ocurrió en el mes de la nota: terminó antes, o solo tiene inicio y ya empezó."""
    if seg["fin"] is not None:
        return seg["fin"][1] < mes
    return seg["inicio"] is not None and seg["inicio"][1] <= mes


def _acumulados(historia, ref):
    """Segmentos de todos los comunicados hasta ref (incluido): lo que el ENFEN dijo de lo ya ocurrido."""
    return [s for r in historia if r["desde"] <= ref["desde"] for s in r["segmentos"]]


def evaluable(a):
    """Habla del Niño actual, no niega el dato y no es explicativa ni pregunta (la atribución se ve aparte)."""
    return (a["momento"] == "actual" and not a["negada"] and not a["explicativa"]
            and a["modalidad"] != "pregunta")  # fmt: skip


def mas_certeza(a):
    """Pronóstico con magnitud en futuro simple y sin cautela: el ENFEN siempre lo da con condicional."""
    verbos = [v for v in FUTURO.findall(a["_texto"]) if v.lower() not in af.NO_SON_VERBOS]
    return bool(a["magnitudes"]) and a["modalidad"] == "afirma" and bool(verbos)


def clasificar(a, fecha, historia, mismo_dia=None):
    """Filas [{dato, valor, categoria, escala, atras, adelantada, sentido, _en}] de una afirmación evaluable."""
    i = indice_vigente(historia, fecha)
    if i is None or not evaluable(a):
        return []
    if mismo_dia is None:
        mismo_dia = historia[i]["desde"] == fecha[:10]
    otra_fuente = a["atribucion"] == "agencia" or a["otro_pais"]
    escalas = _escalas(a["region"])
    ref = historia[i]
    filas = []

    def fila(dato, valor, en, sin_referencia=False, en_otra=None, escala="", sentido=""):
        if otra_fuente:
            categoria, atras, adelantada = "otra_fuente", 0, False
        else:
            categoria, atras = _categoria(en, historia, i, mismo_dia, sin_referencia, en_otra)
            adelantada = categoria in ("contradice", "sin_respaldo", "otra_escala") and _adelantada(
                en, historia, i, fecha
            )
        filas.append({"dato": dato, "valor": valor, "categoria": categoria, "escala": escala, "atras": atras,
                      "adelantada": adelantada, "sentido": sentido, "_en": en})  # fmt: skip

    posibles = set(a["magnitudes_posibles"])
    for m in dict.fromkeys(a["magnitudes"]):
        en = lambda r, m=m: any(m in r[e] for e in escalas)  # noqa: E731
        otra = {COSTA: CENTRAL, CENTRAL: COSTA}[escalas[0]]
        en_otra = (lambda r, m=m, e=otra: m in r[e]) if len(escalas) == 1 else None  # noqa: E731
        escala = next((e for e in escalas if m in ref[e]), COSTA if m in MAGNITUDES_COSTA else CENTRAL)
        fila("magnitud", m, en, m in posibles, en_otra, escala, _sentido(m, ref, escala))
    if a["estado"] and a["region"] != CENTRAL:
        fila("estado", a["estado"], lambda r: r["estado"] == a["estado"], escala=COSTA)
    if a["region"] != CENTRAL:
        mes = temporalidad._indice(int(fecha[:4]), int(fecha[5:7]))
        for seg in a["segmentos"]:
            if _pasado(seg, mes):  # "inició en marzo": un hecho pasado no caduca (arreglo A del 7-nov)
                en = lambda r, s=seg: temporalidad.respaldado(s, _acumulados(historia, r))  # noqa: E731
                referencia_ = _acumulados(historia, ref)
            else:
                en = lambda r, s=seg: temporalidad.respaldado(s, r["segmentos"])  # noqa: E731
                referencia_ = ref["segmentos"]
            fila("fecha", temporalidad.a_celda([seg]), en, not _tiene_sujeto(seg, referencia_), escala=COSTA)
    if not otra_fuente and mas_certeza(a):
        filas.append({"dato": "certeza", "valor": "futuro", "categoria": "mas_certeza", "escala": "", "atras": 0,
                      "adelantada": False, "sentido": "", "_en": None})  # fmt: skip
    return filas


def color(filas):
    """Semáforo de una nota: rojo si algo contradice; amarillo si algo se aleja; verde si todo respalda."""
    cats = {f["categoria"] for f in filas if f["categoria"] != "otra_fuente"}
    if not cats:
        return "sin_afirmaciones"  # el color lo da la distancia (umbrales del README)
    if "contradice" in cats:
        return "rojo"
    return "amarillo" if cats & AMARILLAS else "verde"


# ---------------------------------------------------------------- C1: lógica


def _ref(n, desde, estado, costa, central=(), maxima="", segmentos=()):
    return {"id": f"c{n}", "desde": desde, "estado": estado, COSTA: set(costa), CENTRAL: set(central),
            "maxima": maxima or max(costa, key=ORDEN.get), "segmentos": list(segmentos)}  # fmt: skip


def _seg(sujeto, inicio=None, fin=None):
    return {"sujeto": sujeto, "inicio": inicio, "fin": fin}


# Historia sintética: el estado pasa a alerta en c1; la magnitud sube de débil a fuerte; c2 da Pacífico central
def _mes(texto):
    return temporalidad._indice(int(texto[:4]), int(texto[5:7]))


def _par(texto):
    return (_mes(texto), _mes(texto))


# Historia sintética: el estado pasa a alerta en c1; la magnitud sube de débil a fuerte; c2 da Pacífico central; el
# inicio del evento (enero) solo lo dice c0
HISTORIA_SINTETICA = heredar([
    _ref(0, "2026-01-01", "vigilancia", ["débil"],
         segmentos=[_seg("evento", fin=_par("2026-10")), _seg("evento", inicio=_par("2026-01"))]),
    _ref(1, "2026-02-01", "alerta", ["débil", "moderada"], segmentos=[_seg("evento", fin=_par("2026-11"))]),
    _ref(2, "2026-03-01", "alerta", ["moderada", "fuerte"], ["muy fuerte"],
         segmentos=[_seg("evento", fin=_par("2027-01"))]),
    _ref(3, "2026-03-20", "alerta", ["fuerte", "extraordinaria"], ["muy fuerte"],
         segmentos=[_seg("evento", fin=_par("2027-01")), _seg("fuerte", fin=_par("2026-12"))]),
    # c4 no habla del Pacífico central ni del plazo de "fuerte"; c5 ya no menciona "fuerte"
    _ref(4, "2026-04-25", "alerta", ["fuerte", "extraordinaria"], segmentos=[_seg("evento", fin=_par("2027-01"))]),
    _ref(5, "2026-05-30", "alerta", ["extraordinaria"], ["muy fuerte"],
         segmentos=[_seg("evento", fin=_par("2027-01"))]),
])  # fmt: skip


def _afirmacion(texto="", region="ambigua", magnitudes=(), posibles=(), estado="", segmentos=(), atribucion="sin",
                modalidad="condicional", otro_pais=False):  # fmt: skip
    return {"_texto": texto, "region": region, "magnitudes": list(magnitudes), "magnitudes_posibles": list(posibles),
            "estado": estado, "segmentos": list(segmentos), "atribucion": atribucion, "otro_pais": otro_pais,
            "momento": "actual", "negada": False, "explicativa": False, "modalidad": modalidad}  # fmt: skip


# (nombre, afirmación, fecha, [(dato, categoría, adelantada)] esperadas): fijados el 7-nov
CASOS = (
    ("magnitud respaldada", _afirmacion(magnitudes=["fuerte"]), "2026-03-10", [("magnitud", "respaldada", False)]),
    ("magnitud de un comunicado anterior", _afirmacion(magnitudes=["débil"]), "2026-03-10",
     [("magnitud", "desactualizada", False)]),
    ("magnitud nunca dicha", _afirmacion(magnitudes=["extraordinaria"]), "2026-02-10",
     [("magnitud", "contradice", False)]),
    ("magnitud que llega después: adelantada", _afirmacion(magnitudes=["fuerte"]), "2026-02-20",
     [("magnitud", "contradice", True)]),
    ("posible sin respaldo", _afirmacion(magnitudes=["extraordinaria"], posibles=["extraordinaria"]), "2026-02-10",
     [("magnitud", "sin_respaldo", False)]),
    ("ambigua respaldada en el Pacífico central", _afirmacion(magnitudes=["muy fuerte"]), "2026-03-10",
     [("magnitud", "respaldada", False)]),
    ("costero con la escala del Pacífico central", _afirmacion(region="costa", magnitudes=["muy fuerte"]),
     "2026-03-10", [("magnitud", "otra_escala", False)]),
    ("Pacífico central con la escala costera", _afirmacion(region="central", magnitudes=["moderada"]), "2026-03-10",
     [("magnitud", "otra_escala", False)]),
    ("estado respaldado", _afirmacion(estado="alerta"), "2026-02-10", [("estado", "respaldada", False)]),
    ("estado de antes", _afirmacion(estado="vigilancia"), "2026-03-10", [("estado", "desactualizada", False)]),
    ("estado nunca dicho", _afirmacion(estado="no_activo"), "2026-03-10", [("estado", "contradice", False)]),
    ("el día de emisión vale el anterior", _afirmacion(magnitudes=["débil"]), "2026-03-01",
     [("magnitud", "respaldada", False)]),
    ("fecha respaldada", _afirmacion(segmentos=[_seg("evento", fin=_par("2027-01"))]), "2026-03-10",
     [("fecha", "respaldada", False)]),
    ("fecha de antes", _afirmacion(segmentos=[_seg("evento", fin=_par("2026-10"))]), "2026-03-10",
     [("fecha", "desactualizada", False)]),
    ("fecha que contradice", _afirmacion(segmentos=[_seg("evento", fin=_par("2028-06"))]), "2026-03-10",
     [("fecha", "contradice", False)]),
    ("fecha de algo sin plazo oficial", _afirmacion(segmentos=[_seg("fuerte", fin=_par("2028-06"))]), "2026-03-10",
     [("fecha", "sin_respaldo", False)]),
    ("inicio pasado dicho por un comunicado anterior", _afirmacion(segmentos=[_seg("evento", inicio=_par("2026-01"))]),
     "2026-03-10", [("fecha", "respaldada", False)]),
    ("inicio pasado que el ENFEN nunca dijo", _afirmacion(segmentos=[_seg("evento", inicio=_par("2025-06"))]),
     "2026-03-10", [("fecha", "contradice", False)]),
    ("de otra agencia", _afirmacion(magnitudes=["extraordinaria"], atribucion="agencia"), "2026-02-10",
     [("magnitud", "otra_fuente", False)]),
    ("de otro país", _afirmacion(magnitudes=["extraordinaria"], otro_pais=True), "2026-02-10",
     [("magnitud", "otra_fuente", False)]),
    ("futuro sin cautela", _afirmacion("El Niño será fuerte.", magnitudes=["fuerte"], modalidad="afirma"),
     "2026-03-10", [("magnitud", "respaldada", False), ("certeza", "mas_certeza", False)]),
    ("presente sin cautela no es pronóstico", _afirmacion("El Niño es fuerte.", magnitudes=["fuerte"],
                                                         modalidad="afirma"), "2026-03-10",
     [("magnitud", "respaldada", False)]),
    ("antes del primer comunicado no se compara", _afirmacion(magnitudes=["fuerte"]), "2025-12-01", []),
    ("silencio del vigente en el Pacífico central", _afirmacion(region="central", magnitudes=["muy fuerte"]),
     "2026-04-28", [("magnitud", "respaldada", False)]),
    ("silencio del vigente sobre el plazo de una magnitud",
     _afirmacion(segmentos=[_seg("fuerte", fin=_par("2026-12"))]),
     "2026-04-28", [("fecha", "respaldada", False)]),
    ("plazo de una magnitud que ya no se menciona", _afirmacion(segmentos=[_seg("fuerte", fin=_par("2026-12"))]),
     "2026-06-02", [("fecha", "desactualizada", False)]),
)  # fmt: skip

COLORES = (  # (categorías, color esperado)
    (["respaldada"], "verde"),
    (["respaldada", "desactualizada"], "amarillo"),
    (["respaldada", "mas_certeza"], "amarillo"),
    (["otra_escala"], "amarillo"),
    (["respaldada", "contradice", "sin_respaldo"], "rojo"),
    (["otra_fuente"], "sin_afirmaciones"),
    ([], "sin_afirmaciones"),
)


def _obtenido(a, fecha, historia=HISTORIA_SINTETICA):
    return [(f["dato"], f["categoria"], f["adelantada"]) for f in clasificar(a, fecha, historia)]


def criterio_logica():
    malos = [f"{n}: {_obtenido(a, fecha)} en vez de {esp}" for n, a, fecha, esp in CASOS if _obtenido(a, fecha) != esp]
    malos += [f"color {c}: {color([{'categoria': x} for x in c])} en vez de {esp}" for c, esp in COLORES
              if color([{"categoria": x} for x in c]) != esp]  # fmt: skip
    n = len(CASOS) + len(COLORES)
    return criterio(PRUEBA, "C1: lógica (casos sintéticos)", n - len(malos), n, not malos, "; ".join(malos))


# ---------------------------------------------------------------- C2 y C5: lo oficial


def afirmaciones_oficiales(corpus):
    """[(índice del comunicado, fecha, afirmación)] de los párrafos del ENFEN (titular, resumen, cuerpo)."""
    indice = {c["id"]: i for i, c in enumerate(corpus.comunicados)}
    salida = []
    for p in corpus.parrafos:
        if p["fuente"] != "enfen" or p["seccion"] not in ("titular", "resumen", "cuerpo") or p["duplicado_de"]:
            continue
        if p["doc_id"] not in indice:
            continue
        i = indice[p["doc_id"]]
        fecha = corpus.comunicados[i]["fecha_emision"]
        heredada = _region_heredada(p["texto"])
        for a in af.afirmaciones("", "", p["texto"], fecha):
            if a["region"] == "ambigua":  # "en esta región…": la de la frase anterior, como en la referencia
                a["region"] = next((r for f, r in heredada if a["_texto"] in f or f in a["_texto"]), "ambigua")
            salida.append((i, fecha, a))
    return salida


def _region_heredada(texto):
    """[(frase, región)] de un párrafo oficial: la frase que no nombra región hereda la de la anterior (la misma regla
    de enfen._frases_costeras)."""
    salida, region = [], "ambigua"
    for frase in enfen.FRASE.split(texto):
        if enfen.MENCIONA_CENTRAL.search(frase) and enfen.MENCIONA_COSTERA.search(frase):
            region = "ambas"
        elif enfen.MENCIONA_CENTRAL.search(frase):
            region = CENTRAL
        elif enfen.MENCIONA_COSTERA.search(frase):
            region = COSTA
        salida.append((frase, region))
    return salida


def _esperada_tabla(dato, valor, j, comunicados):
    """Categoría de un dato costero frente al comunicado j, solo con los campos de comunicados.csv."""

    def tiene(c):
        if dato == "estado":
            return af.ESTADO_DE_ENCABEZADO.get(c["estado"], "") == valor
        return valor in c["magnitudes_mencionadas"].split("|")

    if tiene(comunicados[j]):
        return "respaldada"
    return "desactualizada" if any(tiene(c) for c in comunicados[:j]) else "contradice"


def criterio_pares(corpus, historia, oficiales):
    propias, propias_ok, malos = 0, 0, []
    otras, otras_ok, malos_otras = 0, 0, collections.Counter()
    for i, fecha, a in oficiales:
        for f in clasificar(a, fecha, historia, mismo_dia=False):
            if f["dato"] == "certeza" or f["categoria"] == "otra_fuente":
                continue
            propias += 1
            propias_ok += f["categoria"] == "respaldada"
            if f["categoria"] != "respaldada":
                malos.append(f"{historia[i]['id']} {f['dato']}={f['valor']} {f['categoria']} | {a['_texto'][:160]}")
        if a["region"] != COSTA or not evaluable(a):
            continue
        datos = [("magnitud", m) for m in a["magnitudes"] if m not in a["magnitudes_posibles"]]
        datos += [("estado", a["estado"])] if a["estado"] else []
        for j, otro in enumerate(corpus.comunicados):
            if j == i:
                continue
            obtenidas = {(f["dato"], f["valor"]): f["categoria"]
                         for f in clasificar(a, otro["fecha_emision"], historia, mismo_dia=False)}  # fmt: skip
            for dato, valor in datos:
                esperada = _esperada_tabla(dato, valor, j, corpus.comunicados)
                otras += 1
                otras_ok += obtenidas.get((dato, valor)) == esperada
                if obtenidas.get((dato, valor)) != esperada:
                    malos_otras[f"{dato}={valor} frente a {otro['id']}: {obtenidas.get((dato, valor))} "
                                f"(esperada {esperada})"] += 1  # fmt: skip
    for m in malos:
        print("  [C2 propia]", m)
    for m, n in malos_otras.most_common(10):
        print(f"  [C2 otras] {m} ×{n}")
    return [
        criterio(PRUEBA, "C2: frases oficiales frente a su comunicado", f"{propias_ok}/{propias}",
                 f">= {RESPALDO_PROPIO_MINIMO:.0%}", propias > 0 and propias_ok / propias >= RESPALDO_PROPIO_MINIMO,
                 f"{propias_ok / propias:.3f} IC {af.wilson(propias_ok, propias)}" if propias else "sin frases"),
        criterio(PRUEBA, "C2: magnitud costera y estado frente a los demás", f"{otras_ok}/{otras}",
                 f">= {ESPERADA_MINIMA:.0%}", otras > 0 and otras_ok / otras >= ESPERADA_MINIMA,
                 f"{otras_ok / otras:.3f}" if otras else "sin pares"),
    ]  # fmt: skip


def criterio_certeza_oficial(oficiales):
    con = [a for _, _, a in oficiales if a["magnitudes"] and evaluable(a)]
    marcadas = [a for a in con if mas_certeza(a)]
    for a in marcadas:
        print("  [C5]", a["_texto"][:200])
    n = len(con)
    return criterio(PRUEBA, "C5: frases oficiales con más certeza", f"{len(marcadas)}/{n}",
                    f"<= {CERTEZA_OFICIAL_MAXIMA:.0%}", n > 0 and len(marcadas) / n <= CERTEZA_OFICIAL_MAXIMA,
                    )  # fmt: skip


# ---------------------------------------------------------------- C3, C4 y C6: la muestra


ATRIBUCION_C3 = ("enfen", "sin")  # las que deberían seguir al vigente; terceros aparte (cambio aprobado el 7-nov)


def criterio_desplazamiento(filas_notas, historia, atribuciones=ATRIBUCION_C3, nombre="C3: desplazamiento"):
    """En cada dato, el comunicado más cercano al vigente cuyo respaldo es distinto: ¿respalda el vigente?"""
    distintos, vigente_gana = 0, 0
    for nota in filas_notas:
        i = indice_vigente(historia, nota["fecha"])
        for f in nota["filas"]:
            if f["_en"] is None or f["categoria"] == "otra_fuente" or f["_atribucion"] not in atribuciones:
                continue
            propio = f["_en"](historia[i])
            otros = sorted((j for j in range(len(historia)) if j != i), key=lambda j: (abs(j - i), j))
            k = next((j for j in otros if f["_en"](historia[j]) != propio), None)
            if k is not None:
                distintos += 1
                vigente_gana += propio
                if not propio:  # solo a pantalla, para el diagnóstico
                    print(f"  [C3] {nota['medio']} {nota['id']} {nota['fecha']} {f['dato']}={f['valor']} "
                          f"{f['categoria']}; respalda {historia[k]['id']} | {f.get('_texto', '')[:200]}")  # fmt: skip
    informativo = atribuciones != ATRIBUCION_C3
    return criterio(PRUEBA, f"{nombre} (el vigente es el que respalda)", f"{vigente_gana}/{distintos}",
                    "" if informativo else f">= {DESPLAZAMIENTO_MINIMO:.0%}",
                    informativo or (distintos > 0 and vigente_gana / distintos >= DESPLAZAMIENTO_MINIMO),
                    f"{vigente_gana / distintos:.3f} IC {af.wilson(vigente_gana, distintos)}" if distintos else "",
                    )  # fmt: skip


ESTADO_PALABRA = {"alerta": "vigilancia", "vigilancia": "alerta", "no_activo": "alerta"}


def _reemplazar_magnitud(texto, m, nueva):
    return enfen.TERMINO.sub(lambda t: nueva if enfen.magnitud_canonica(t.group(1)) == m else t.group(0), texto)


def _historia_tiene(valor, dato, historia, i, escalas):
    if dato == "estado":
        return any(r["estado"] == valor for r in historia[:i])
    return any(valor in r[e] for r in historia[:i] for e in escalas)


def perturbaciones(nota, historia):
    """[(tipo, esperado, obtenido, texto)] de las frases respaldadas de una nota, perturbadas en memoria."""
    salida = []
    fecha = nota["fecha"]
    i = indice_vigente(historia, fecha)
    for a, filas in nota["afirmaciones"]:
        if any(f["categoria"] == "otra_fuente" for f in filas):
            continue
        texto = a["_texto"]
        escalas = _escalas(a["region"])
        excluir = {m for r in historia[max(0, i - 1) : i + 1] for e in (COSTA, CENTRAL) for m in r[e]}
        for f in filas:
            if f["categoria"] != "respaldada":
                continue
            if f["dato"] == "magnitud" and f["valor"] not in a["magnitudes_posibles"]:
                candidatas = [x for x in MAGNITUDES_COSTA if x not in excluir and x not in a["magnitudes"]]
                if not candidatas:
                    continue
                nueva = next((x for x in candidatas if not _historia_tiene(x, "magnitud", historia, i, escalas)),
                             candidatas[0])  # fmt: skip
                esperada = (
                    "desactualizada" if _historia_tiene(nueva, "magnitud", historia, i, escalas) else "contradice"
                )
                salida.append(_perturbada("magnitud", _reemplazar_magnitud(texto, f["valor"], nueva), fecha,
                                          historia, ("magnitud", nueva), esperada))  # fmt: skip
            elif f["dato"] == "estado":
                nuevo = ESTADO_PALABRA[f["valor"]]
                palabra = {"no_activo": "no activo"}.get(f["valor"], f["valor"])
                cambiado = re.sub(rf"\b{palabra}\b", nuevo, texto, flags=re.I)
                esperada = "desactualizada" if _historia_tiene(nuevo, "estado", historia, i, escalas) else "contradice"
                salida.append(_perturbada("estado", cambiado, fecha, historia, ("estado", nuevo), esperada))
        respaldadas = {f["valor"] for f in filas if f["dato"] == "fecha" and f["categoria"] == "respaldada"}
        for inicio, fin in sorted({s["span"] for s in a["segmentos"] if temporalidad.a_celda([s]) in respaldadas}):
            seg = next(s for s in a["segmentos"] if s["span"] == (inicio, fin))
            fechas_del_segmento = 2 if seg["relacion"] == "rango" else 1
            if len(re.findall(r"\b202[67]\b", texto[inicio:fin])) >= fechas_del_segmento:  # todos sus años explícitos
                cambiado = texto[:inicio] + re.sub(r"\b202[67]\b", AÑO_PERTURBADO, texto[inicio:fin]) + texto[fin:]
                salida.append(_perturbada("fecha", cambiado, fecha, historia, ("fecha", None), "sin respaldo actual"))
        verbos = [v for v in af.CONDICIONAL_VERBO.findall(texto) if v.lower() not in af.NO_SON_VERBOS]
        if a["magnitudes"] and len(verbos) == 1 and not af.CONDICIONAL.search(texto) and "?" not in texto:
            cambiado = re.sub(rf"\b{verbos[0]}\b", re.sub(r"ría(n?)$", r"rá\1", verbos[0]), texto, count=1)
            salida.append(_perturbada("certeza", cambiado, fecha, historia, ("certeza", "futuro"), "mas_certeza"))
    return salida


def _perturbada(tipo, texto, fecha, historia, clave, esperada):
    filas = [f for a in af.afirmaciones("", "", texto, fecha) for f in clasificar(a, fecha, historia)]
    if tipo == "fecha":
        fechas = [f["categoria"] for f in filas if f["dato"] == "fecha" and AÑO_PERTURBADO in f["valor"]]
        ok = bool(fechas) and not {"respaldada", "desactualizada"} & set(fechas)
        return tipo, esperada, "|".join(fechas), ok, texto
    obtenida = next((f["categoria"] for f in filas if (f["dato"], f["valor"]) == clave), "")
    return tipo, esperada, obtenida, obtenida == esperada, texto


def criterio_perturbaciones(filas_notas, historia):
    resultados = [p for nota in filas_notas for p in perturbaciones(nota, historia)]
    por_tipo = collections.Counter(t for t, *_ in resultados)
    malos = [(t, e, o, x) for t, e, o, ok, x in resultados if not ok]
    for t, e, o, x in malos:
        print(f"  [C4 {t}] esperada {e}, obtenida {o or '(nada)'} | {x[:200]}")
    n = len(resultados)
    return criterio(PRUEBA, "C4: perturbaciones", f"{n - len(malos)}/{n}", "100 %", n > 0 and not malos,
                    str(dict(por_tipo)))  # fmt: skip


def _proporcion(casos, total):
    return casos / total if total else 0.0


def criterio_dinamica(filas_notas, historia):
    """Desactualizadas: ¿más en los primeros días tras un comunicado? Adelantadas: ¿más en los días antes del
    siguiente?"""
    cuenta = collections.Counter()
    for nota in filas_notas:
        i = indice_vigente(historia, nota["fecha"])
        dias_desde = _dias(historia[i]["desde"], nota["fecha"])
        dias_hasta = _dias(nota["fecha"], historia[i + 1]["desde"]) if i + 1 < len(historia) else None
        cerca_inicio = dias_desde <= DIAS_DESACTUALIZADA
        cerca_fin = dias_hasta is not None and dias_hasta <= DIAS_ADELANTADA
        for f in nota["filas"]:
            if f["dato"] == "certeza" or f["categoria"] == "otra_fuente":
                continue
            cuenta[("inicio", cerca_inicio, "total")] += 1
            cuenta[("inicio", cerca_inicio, "casos")] += f["categoria"] == "desactualizada"
            if dias_hasta is not None:
                cuenta[("fin", cerca_fin, "total")] += 1
                cuenta[("fin", cerca_fin, "casos")] += f["adelantada"]
    salida = []
    for lado, nombre, dias in (("inicio", "desactualizadas tras cada comunicado", DIAS_DESACTUALIZADA),
                               ("fin", "adelantadas antes del siguiente", DIAS_ADELANTADA)):  # fmt: skip
        dentro = _proporcion(cuenta[(lado, True, "casos")], cuenta[(lado, True, "total")])
        fuera = _proporcion(cuenta[(lado, False, "casos")], cuenta[(lado, False, "total")])
        casos = cuenta[(lado, True, "casos")] + cuenta[(lado, False, "casos")]
        informativo = casos < CASOS_DINAMICA_MINIMOS
        detalle = (f"{dias} días: {cuenta[(lado, True, 'casos')]}/{cuenta[(lado, True, 'total')]} ({dentro:.3f}); "
                   f"resto: {cuenta[(lado, False, 'casos')]}/{cuenta[(lado, False, 'total')]} ({fuera:.3f})"
                   + ("; informativo: menos de 20 casos" if informativo else ""))  # fmt: skip
        salida.append(criterio(PRUEBA, f"C6: {nombre}", casos, "dirección esperada",
                               informativo or dentro > fuera, detalle))  # fmt: skip
    return salida


def descriptivos(filas_notas):
    validas = [n for n in filas_notas if not n["error"]]
    filas = [f for n in validas for f in n["filas"]]
    por_atribucion = collections.Counter((f["_atribucion"], f["categoria"]) for f in filas)
    por_origen = collections.Counter((f["_origen"], f["categoria"]) for f in filas)
    colores = collections.Counter(n["color"] for n in validas)
    return [
        criterio(PRUEBA, "notas leídas", len(validas), len(filas_notas), True,
                 str(collections.Counter(n["medio"] for n in validas))),
        criterio(PRUEBA, "semáforo (informativo)", len(validas), "", True, str(dict(colores))),
        criterio(PRUEBA, "categorías por atribución (informativo)", len(filas), "", True, str(dict(por_atribucion))),
        criterio(PRUEBA, "categorías por origen (informativo)", len(filas), "", True, str(dict(por_origen))),
        criterio(PRUEBA, "adelantadas (informativo)", sum(f["adelantada"] for f in filas), "", True,
                 str(collections.Counter(f["categoria"] for f in filas if f["adelantada"]))),
        criterio(PRUEBA, "dirección de la magnitud (informativo)", len(filas), "", True,
                 str(collections.Counter(f["sentido"] for f in filas if f["dato"] == "magnitud"))),
    ]  # fmt: skip


# ---------------------------------------------------------------- muestra y lectura


def muestra(notas, vistas, semilla=SEMILLA):
    """TAMANO_MUESTRA notas sobre El Niño sin ver, en proporción por medio."""
    pool = [n for n in notas if n["sobre_nino"] == "1" and (n["medio"], n["id"]) not in vistas]
    por_medio = {m: [n for n in pool if n["medio"] == m] for m in MEDIOS}
    return [x for m, lista in por_medio.items()
            for x in _muestra(lista, round(TAMANO_MUESTRA * len(lista) / max(1, len(pool))), semilla, m)]  # fmt: skip


def elegir_muestra(ronda):
    semilla = RONDAS[ronda]
    if viabilidad.registrada(semilla):
        log.info(f"La muestra {semilla} ya está en notas_vistas.csv; no se elige otra.")
        return []
    elegidas = muestra(leer_csv(config.DIR_NOTICIAS / "notas.csv"), notas_vistas(), semilla)
    marcar_vistas(elegidas, semilla)
    log.info(f"Muestra: {len(elegidas)} · {collections.Counter(n['medio'] for n in elegidas)}")
    return []


def fila_de_nota(nota, campos, historia, mostrar=True):
    salida = {"medio": nota["medio"], "id": nota["id"], "fecha": nota["fecha_publicacion"][:10], "error": "",
              "afirmaciones": [], "filas": [], "color": ""}  # fmt: skip
    if not isinstance(campos, dict):
        return {**salida, "error": describir(campos)[:200]}
    if campos["sin_texto"]:
        return {**salida, "error": "sin texto"}
    for a in af.afirmaciones(campos["titular"], campos["resumen"], campos["cuerpo"], salida["fecha"]):
        filas = clasificar(a, salida["fecha"], historia)
        for f in filas:
            f["_atribucion"], f["_origen"], f["frase"], f["_texto"] = (
                a["atribucion"],
                a["origen"],
                a["frase"],
                a["_texto"],
            )
            if mostrar and f["categoria"] not in (
                "respaldada",
                "otra_fuente",
            ):  # solo a pantalla: el texto no se guarda
                print(f"  [{f['categoria']}{' adelantada' if f['adelantada'] else ''}] {nota['medio']} {nota['id']} "
                      f"{salida['fecha']} {f['dato']}={f['valor']} ({a['atribucion']}) | {a['_texto'][:200]}",
                      )  # fmt: skip
        salida["afirmaciones"].append((a, filas))
        salida["filas"] += filas
    salida["color"] = color(salida["filas"])
    return salida


def a_filas_csv(nota):
    return [{"medio": nota["medio"], "id": nota["id"], "fecha": nota["fecha"],
             **{k: v for k, v in f.items() if not k.startswith("_")}, "adelantada": int(f["adelantada"])}
            for f in nota["filas"]]  # fmt: skip


@exclusivo("radar.nlp.discrepancia")
def _leer_muestra(parar, historia, ronda):
    elegidas = set(viabilidad.registrada(RONDAS[ronda]))
    if not elegidas:
        raise SystemExit(f"Falta la muestra: python -m radar.nlp.discrepancia muestra --ronda {ronda}")
    notas = [n for n in leer_csv(config.DIR_NOTICIAS / "notas.csv") if (n["medio"], n["id"]) in elegidas]
    filas_notas = []
    lectura = config.DIR_NLP / "discrepancia-notas.csv"
    lectura.unlink(missing_ok=True)  # una sola pasada: las filas se juntan en memoria

    def fila_de(nota, _estrato, campos):
        fila = fila_de_nota(nota, campos, historia)
        filas_notas.append(fila)
        return {k: fila[k] for k in ("medio", "id", "fecha", "error", "color")} | {
            "afirmaciones": len(fila["afirmaciones"]),
            "filas": len(fila["filas"]),
        }

    with sin_suspension():
        tfidf.leer_cuerpos([(n, "") for n in notas], lectura, esquemas.DISCREPANCIA_NOTAS, fila_de, parar)
    escribir_csv(config.DIR_NLP / "discrepancia.csv", esquemas.DISCREPANCIA,
                 [f for n in filas_notas for f in a_filas_csv(n)])  # fmt: skip
    return filas_notas


# ---------------------------------------------------------------- todas las notas (punto 5.4 de los pendientes)


def notas_a_calcular(notas):
    return [n for n in notas if n["sobre_nino"] == "1"]


def sin_huerfanas(filas_dato, notas_hechas):
    """Las filas por dato de las notas que terminaron: un corte entre las dos escrituras deja datos sin su nota, que
    se vuelven a calcular al relanzar."""
    return [f for f in filas_dato if (f["medio"], f["id"]) in notas_hechas]


@exclusivo("radar.nlp.discrepancia")
def calcular(parar):
    """Capa 5 de todas las notas sobre El Niño, sin mostrar frases. Se puede cortar y relanzar: salta las notas ya
    calculadas en discrepancia-todas-notas.csv."""
    historia = referencia(Corpus())
    notas = notas_a_calcular(leer_csv(config.DIR_NOTICIAS / "notas.csv"))
    ruta_notas, ruta_datos = config.DIR_NLP / "discrepancia-todas-notas.csv", config.DIR_NLP / "discrepancia-todas.csv"
    hechas = {k for k, f in tfidf.leidos(ruta_notas).items() if not f["error"] or f["error"] == "sin texto"}
    if ruta_datos.exists():
        escribir_csv(ruta_datos, esquemas.DISCREPANCIA, sin_huerfanas(leer_csv(ruta_datos), hechas))

    def fila_de(nota, _estrato, campos):
        fila = fila_de_nota(nota, campos, historia, mostrar=False)
        anexar_csv(ruta_datos, esquemas.DISCREPANCIA, a_filas_csv(fila))
        return {k: fila[k] for k in ("medio", "id", "fecha", "error", "color")} | {
            "afirmaciones": len(fila["afirmaciones"]),
            "filas": len(fila["filas"]),
        }

    with sin_suspension():
        tfidf.leer_cuerpos([(n, "") for n in notas], ruta_notas, esquemas.DISCREPANCIA_NOTAS, fila_de, parar)
    calculadas = leer_csv(ruta_notas)
    colores = collections.Counter(f["color"] or f["error"] for f in calculadas)
    return [criterio("Capa 5: todas las notas", "notas calculadas", f"{len(calculadas)}/{len(notas)}", "", True,
                     str(dict(colores)))]  # fmt: skip


def validar(parar, solo_oficial=False, ronda="b"):
    corpus = Corpus()
    historia = referencia(corpus)
    oficiales = afirmaciones_oficiales(corpus)
    filas = [criterio_logica(), *criterio_pares(corpus, historia, oficiales), criterio_certeza_oficial(oficiales)]
    if solo_oficial:
        return filas
    filas_notas = _leer_muestra(parar, historia, ronda)
    validas = [n for n in filas_notas if not n["error"] and indice_vigente(historia, n["fecha"]) is not None]
    terceros = ("oficial", "tercero")
    return filas + [criterio_desplazamiento(validas, historia),
                    criterio_desplazamiento(validas, historia, terceros, "C3 de otras entidades y terceros"),
                    criterio_perturbaciones(validas, historia),
                    *criterio_dinamica(validas, historia), *descriptivos(filas_notas)]  # fmt: skip


def main(argv=None):
    ap = argparse.ArgumentParser(description="Capa 5: comparación con lo oficial.")
    ap.add_argument("paso", choices=("muestra", "validar", "calcular"))
    ap.add_argument("--solo-oficial", action="store_true", help="solo C1, C2 y C5: no pide páginas")
    ap.add_argument("--ronda", choices=tuple(RONDAS), default="b", help="a: primera validación; b: tras los arreglos")
    args = ap.parse_args(argv)
    registro = configurar(f"nlp-discrepancia-{args.paso}-{args.ronda}")
    inicio, parar = ahora(), threading.Event()
    config.DIR_NLP.mkdir(parents=True, exist_ok=True)
    try:
        if args.paso == "calcular":
            filas = calcular(parar)
        elif args.paso == "muestra":
            filas = elegir_muestra(args.ronda)
        else:
            filas = validar(parar, args.solo_oficial, args.ronda)
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
