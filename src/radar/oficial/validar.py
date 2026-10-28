"""Pruebas de viabilidad del corpus oficial con referencias externas (criterios en docs/oficial/definicion.md).

Cada criterio se calcula aislado: si falla por un dato inesperado, se reporta como "no pasa" con el error,
sin detener el resto.
"""

import collections
import datetime as dt
import difflib
import logging
import re

import pymupdf
from pypdf import PdfReader

from radar.comun.regiones import MACROREGIONES_COSTA
from radar.comun.texto import clave
from radar.oficial import enfen, enfen_pdf
from radar.oficial.vocabulario import (
    CANCELADO,
    IMPACTOS,
    NIVELES_AVISO,
    NO_ACTIVO,
    PESCA,
    PRONOSTICO,
    RECOMENDACION,
    REGION_CENTRAL,
    REGION_COSTERA,
)

log = logging.getLogger(__name__)

TOLERANCIA_DIAS = 1
MINIMO_CADENA = 0.9  # emisión real frente a la anunciada
MINIMO_ACUERDO_EXTRACTORES = 0.98
SIMILITUD_FRASE = 0.9
MINIMO_FRASES = 0.95
MINIMO_ACUERDO_MACROREGION = 0.95
MINIMO_TIPO = 0.95  # tipo y región del párrafo frente a la estructura fija del resumen
# Estructura fija del resumen ejecutivo (N.° 13-2025 a 16-2026, 6 párrafos): referencia externa para el tipo y la
# región del océano, que se calculan con reglas sobre el texto, nunca con la posición
TIPO_POR_POSICION = (PRONOSTICO, PRONOSTICO, IMPACTOS, IMPACTOS, PESCA, RECOMENDACION)
REGION_POR_POSICION = (REGION_COSTERA, REGION_CENTRAL)
PARRAFOS_RESUMEN = len(TIPO_POR_POSICION)
LARGO_MINIMO_FRASE = 25
LARGO_DETALLE = 300

RESTOS = (
    ("url", r"https?://|www\."),
    ("cabecera", r"Decreto Supremo|COMISIÓN MULTISECTORIAL|Año de la"),
    ("leyenda", r"\bFigura \d+\.|\bFuente:"),
    ("marca_pegada", r"[a-záéíóú]\d{1,2}\b(?![.,]\d)"),
    ("caracter_invalido", "\ufffd"),
)
APERTURAS = (
    ("pesca", r"^En (relación|cuanto) (con |a )?(los |a los )?recursos pesqueros,?|^Pesquero:"),
    ("lluvias", r"^En cuanto al pronóstico hidrológico,?|^Caudales:|^Lluvias:"),
    ("prevencion", r"^Se recomienda a los tomadores de decisiones|^Se exhorta|^Se insta"),
    ("calor", r"^Temperatura del [Aa]ire:"),
)


class Reporte:
    """Junta las filas del reporte; cada criterio corre aislado."""

    def __init__(self):
        self.filas = []

    def criterio(self, prueba, nombre, umbral, calculo, minimo=None):
        """calculo() → (ok, total, detalle). minimo: proporción exigida; None exige ok == total."""
        try:
            ok, total, detalle = calculo()
        except Exception as e:
            log.debug("criterio %s", nombre, exc_info=True)
            ok, total, detalle, minimo = 0, 0, f"error al calcular: {type(e).__name__} {e}", 1.1
        valor = ok / total if total else 1.0
        pasa = valor >= minimo if minimo is not None else ok == total
        self.filas.append(
            {
                "prueba": prueba,
                "criterio": nombre,
                "valor": f"{ok}/{total}",
                "umbral": umbral,
                "pasa": pasa,
                "detalle": detalle[:LARGO_DETALLE],
            }
        )


def _dias_entre(a, b):
    return abs((dt.date.fromisoformat(a) - dt.date.fromisoformat(b)).days)


# ---------------------------------------------------------------- ENFEN


def _acuerdo_extractores(ruta_pdf):
    """Similitud de las bolsas de palabras de PyMuPDF y pypdf (coeficiente de Dice)."""
    a = collections.Counter(clave(" ".join(p.extract_text() or "" for p in PdfReader(ruta_pdf).pages)).split())
    with pymupdf.open(ruta_pdf) as doc:
        b = collections.Counter(clave(" ".join(p.get_text() for p in doc)).split())
    return 2 * sum((a & b).values()) / max(1, sum(a.values()) + sum(b.values()))


def _sin_numeros(texto):
    return re.sub(r"\s+", " ", re.sub(r"\d+", " ", texto)).strip()


def _frases_html(parrafos_web, parrafos_pdf):
    """(encontradas, total, faltantes) de las frases del resumen HTML en los párrafos del PDF."""
    texto_pdf = _sin_numeros(" ".join(clave(p) for p in parrafos_pdf))
    ok, total, faltan = 0, 0, []
    for p in parrafos_web:
        for frase in re.split(r"(?<=[.;])\s+", p):
            k = _sin_numeros(clave(frase))
            if len(k) < LARGO_MINIMO_FRASE or "comunicado oficial enfen" in k or "estado de sistema" in k:
                continue
            total += 1
            if k in texto_pdf:
                ok += 1
                continue
            m = difflib.SequenceMatcher(None, texto_pdf, k, autojunk=False).find_longest_match(
                0, len(texto_pdf), 0, len(k)
            )
            inicio = max(0, m.a - m.b)
            if difflib.SequenceMatcher(None, texto_pdf[inicio : inicio + len(k) + 10], k).ratio() >= SIMILITUD_FRASE:
                ok += 1
            else:
                faltan.append(frase[:80])
    return ok, total, faltan


def validar_enfen(comunicados, parrafos, control, errores):
    r = Reporte()
    prueba = "enfen"
    del_pdf = [c for c in comunicados if c["fuente_texto"] == "pdf"]

    r.criterio(
        prueba,
        "comunicados descargados y extraídos del PDF",
        "100 %",
        lambda: (len(del_pdf), len(comunicados) + len(errores), "; ".join(f"{k}: {v}" for k, v in errores.items())),
    )

    def numero_slug():
        mal = [
            f"{c['slug']}→{c['id']}"
            for c in comunicados
            if (m := enfen.SLUG_NUMERO.search(c["slug"])) is None
            or (int(m.group(1)), int(m.group(2))) != (int(c["numero"]), int(c["anio"]))
        ]
        return len(comunicados) - len(mal), len(comunicados), ", ".join(mal)

    r.criterio(prueba, "número y año del PDF = slug", "100 %", numero_slug)

    def fecha_pagina():
        mal = [
            f"{c['id']}: {c['fecha_emision']} / {c['fecha_web']}"
            for c in comunicados
            if not c["fecha_web"] or _dias_entre(c["fecha_emision"], c["fecha_web"]) > TOLERANCIA_DIAS
        ]
        return len(comunicados) - len(mal), len(comunicados), ", ".join(mal)

    r.criterio(prueba, "fecha de emisión a ±1 día de la fecha de la página", "100 %", fecha_pagina)

    def cadena():
        oficiales = [c for c in comunicados if c["tipo"] == "oficial"]
        pares = [(a, b) for a, b in zip(oficiales, oficiales[1:], strict=False) if a["proximo_anunciado"]]
        mal = [
            f"{a['id']}→{b['id']}"
            for a, b in pares
            if _dias_entre(b["fecha_emision"], a["proximo_anunciado"]) > TOLERANCIA_DIAS
        ]
        return len(pares) - len(mal), len(pares), ", ".join(mal)

    r.criterio(
        prueba, "emisión real a ±1 día de la anunciada en el comunicado anterior", "≥ 90 %", cadena, MINIMO_CADENA
    )

    def estado_web():
        mal = [
            f"{c['id']}: {c['estado']} / {control[c['id']]['web']['estado_web']}"
            for c in comunicados
            if (control[c["id"]]["web"]["estado_web"] or "").lower() != (c["estado"] or "").lower()
        ]
        return len(comunicados) - len(mal), len(comunicados), ", ".join(mal)

    r.criterio(prueba, "estado = estado de la página de descarga", "100 %", estado_web)

    def magnitud_extraida():
        activos = [c for c in comunicados if c["estado"] and c["estado"] != NO_ACTIVO]
        sin = [c["id"] for c in activos if not c["magnitud_max_prevista"]]
        return len(activos) - len(sin), len(activos), ", ".join(sin)

    r.criterio(prueba, "magnitud extraída (vigilancia o alerta)", "100 %", magnitud_extraida)

    def magnitud_html():
        ok = total = 0
        mal = []
        for c in comunicados:
            _, en_html = enfen.magnitud(control[c["id"]]["web"]["parrafos_web"])
            if not en_html:
                continue
            total += 1
            sobran = set(en_html) - set(c["magnitudes_mencionadas"])
            ok += not sobran
            if sobran:
                mal.append(f"{c['id']}: {sorted(sobran)}")
        return ok, total, "; ".join(mal)

    r.criterio(prueba, "magnitudes del resumen HTML ⊆ magnitudes del PDF", "100 %", magnitud_html)

    def magnitud_tabla():
        ok = total = 0
        mal = []
        for c in comunicados:
            filas = [p for p in enfen.probabilidades(control[c["id"]]["tablas"]) if p["region"] == REGION_COSTERA]
            if not filas:
                continue
            total += 1
            mas_probable = max(filas, key=lambda p: p["probabilidad"])["categoria"]
            categoria = enfen.magnitud_canonica(re.sub(r"(?i)el niño\s*", "", mas_probable))
            ok += categoria in c["magnitudes_mencionadas"]
            if categoria not in c["magnitudes_mencionadas"]:
                mal.append(f"{c['id']}: {categoria}")
        return ok, total, "; ".join(mal)

    r.criterio(prueba, "categoría más probable de la tabla ∈ magnitudes mencionadas", "100 %", magnitud_tabla)

    def extractores():
        bajos = []
        for c in del_pdf:
            acuerdo = _acuerdo_extractores(enfen.DIR / f"{c['slug']}.pdf")
            if acuerdo < MINIMO_ACUERDO_EXTRACTORES:
                bajos.append(f"{c['id']}={acuerdo:.3f}")
        return len(del_pdf) - len(bajos), len(del_pdf), ", ".join(bajos)

    r.criterio(prueba, "acuerdo PyMuPDF / pypdf ≥ 0,98 por documento", "100 %", extractores)

    def frases():
        ok = total = 0
        faltan = []
        for c in del_pdf:
            o, t, f = _frases_html(control[c["id"]]["web"]["parrafos_web"], control[c["id"]]["parrafos"])
            ok, total, faltan = ok + o, total + t, faltan + f
        return ok, total, "; ".join(faltan)

    r.criterio(
        prueba, "frases del resumen HTML presentes en los párrafos (similitud ≥ 0,9)", "≥ 95 %", frases, MINIMO_FRASES
    )

    def restos():
        de_texto = [p for p in parrafos if p["fuente"] == "enfen" and p["seccion"] != "definicion"]
        mal = [f"{p['id']}:{nombre}" for p in de_texto for nombre, patron in RESTOS if re.search(patron, p["texto"])]
        return len(de_texto) - len(mal), len(de_texto), ", ".join(mal)

    r.criterio(prueba, "párrafos sin URL, encabezado, leyenda ni marca de nota", "100 %", restos)

    def temas():
        ok = total = 0
        for p in parrafos:
            if p["fuente"] != "enfen" or p["seccion"] not in ("resumen", "cuerpo"):
                continue
            for tema, patron in APERTURAS:
                m = re.match(patron, p["texto"])
                if m:
                    total += 1
                    ok += tema in enfen.temas_por_palabras(p["texto"][m.end() :])
                    break
        return ok, total, ""

    r.criterio(
        "enfen (informativo)", "temas por palabras clave = tema de la frase de apertura", "referencia", temas, 0.0
    )
    _validar_tipo_y_region(r, prueba, [p for p in parrafos if p["fuente"] == "enfen"])
    return r.filas


def _resumenes(parrafos):
    por_doc = collections.defaultdict(list)
    for p in parrafos:
        if p["seccion"] == "resumen":
            por_doc[p["doc_id"]].append(p)
    return {d: sorted(ps, key=lambda p: int(p["orden"])) for d, ps in por_doc.items() if len(ps) == PARRAFOS_RESUMEN}


def _validar_tipo_y_region(r, prueba, parrafos):
    resumenes = _resumenes(parrafos)

    def tipo_por_posicion():
        mal = [
            f"{p['id']}:{p['tipo']}≠{esperado}"
            for ps in resumenes.values()
            for p, esperado in zip(ps, TIPO_POR_POSICION, strict=True)
            if p["tipo"] != esperado
        ]
        return len(resumenes) * PARRAFOS_RESUMEN - len(mal), len(resumenes) * PARRAFOS_RESUMEN, ", ".join(mal)

    r.criterio(
        prueba, "tipo de párrafo = posición en el resumen", f"≥ {MINIMO_TIPO:.0%}", tipo_por_posicion, MINIMO_TIPO
    )

    def region_por_posicion():
        mal = [
            f"{p['id']}:{p['region_enso'] or '-'}≠{esperada}"
            for ps in resumenes.values()
            for p, esperada in zip(ps, REGION_POR_POSICION, strict=False)
            if p["region_enso"] != esperada
        ]
        total = len(resumenes) * len(REGION_POR_POSICION)
        return total - len(mal), total, ", ".join(mal)

    r.criterio(
        prueba,
        "región del océano = posición en el resumen (1.ª costa, 2.ª Pacífico central)",
        f"≥ {MINIMO_TIPO:.0%}",
        region_por_posicion,
        MINIMO_TIPO,
    )

    def igual_que_su_duplicado():
        por_id = {p["id"]: p for p in parrafos}
        pares = [(p, por_id[p["duplicado_de"]]) for p in parrafos if p["duplicado_de"] in por_id]
        mal = [
            f"{a['id']}≠{b['id']}" for a, b in pares if (a["tipo"], a["region_enso"]) != (b["tipo"], b["region_enso"])
        ]
        return len(pares) - len(mal), len(pares), ", ".join(mal)

    r.criterio(
        prueba,
        "el cuerpo que repite al resumen tiene el mismo tipo y región",
        f"≥ {MINIMO_TIPO:.0%}",
        igual_que_su_duplicado,
        MINIMO_TIPO,
    )

    def sin_encabezados_de_tabla():
        mal = [p["id"] for p in parrafos if enfen_pdf.TABLA_EN_PARRAFO.match(p["texto"])]
        return len(parrafos) - len(mal), len(parrafos), ", ".join(mal)

    r.criterio(prueba, "párrafos que no son encabezado de tabla", "100 %", sin_encabezados_de_tabla)

    def sin_referencia():
        sin = [p for p in parrafos if p["doc_id"] not in resumenes and p["seccion"] != "definicion"]
        reparto = collections.Counter(p["tipo"] for p in sin)
        return len(sin), len(sin), "; ".join(f"{t} {n}" for t, n in reparto.most_common())

    r.criterio(
        "enfen (informativo)", "tipos en comunicados sin resumen (N.° 17 y 18)", "referencia", sin_referencia, 0.0
    )


# ---------------------------------------------------------------- Senamhi


def validar_senamhi(avisos, dias, control, errores):
    r = Reporte()
    prueba = "senamhi"
    detalles = [v for v in control if v["clase"] == "detalle"]
    cancelados = {a["id"] for a in avisos if a["estado"] == CANCELADO}

    r.criterio(
        prueba,
        "avisos candidatos con panel de detalle",
        "100 %",
        lambda: (len(detalles), len(detalles) + len(errores), ", ".join(errores)),
    )

    def campos_tabla():
        mal = []
        for v in detalles:
            t, d = v["tabla"], v["detalle"]
            iguales = {
                "numero": d["numero"] == t["numero"],
                "nivel": d["nivel"] == t["nivel"],
                "titulo": d["titulo"] == t["titulo"],
                "emision": d["emision"] == t["emision"],
                "inicio": (d["inicio"] or "")[:10] == t["inicio"],
                "fin": (d["fin"] or "")[:10] == t["fin"],
                "dias": all(t["inicio"] <= f <= t["fin"] for f in v["fechas_mapas"] if f),
            }
            if not all(iguales.values()):
                mal.append(f"{v['aviso_id']}:{[k for k, ok in iguales.items() if not ok]}")
        return len(detalles) - len(mal), len(detalles), ", ".join(mal)

    r.criterio(prueba, "número, nivel, título, emisión, inicio y fin del detalle = tabla", "100 %", campos_tabla)

    def nivel_mapas():
        mal = [
            v["aviso_id"]
            for v in detalles
            if v["niveles_mapas"]
            and max((int(n) for n in v["niveles_mapas"] if n.isdigit()), default=0)
            != NIVELES_AVISO.index(v["tabla"]["nivel"])
        ]
        return len(detalles) - len(mal), len(detalles), ", ".join(mal)

    r.criterio(prueba, "nivel máximo de los mapas diarios = nivel de la tabla", "100 %", nivel_mapas)

    for macro in MACROREGIONES_COSTA:

        def acuerdo(macro=macro):
            comparables = [
                v
                for v in control
                if v["clase"] == "alcance" and v["poligono"] is not None and v["aviso_id"] not in cancelados
            ]
            mal = [
                f"{v['aviso_id']}/{v['mapa']}:{'regla' if macro in v['regla'] else 'polígono'}"
                for v in comparables
                if (macro in v["regla"]) != (macro in v["poligono"])
            ]
            return len(comparables) - len(mal), len(comparables), ", ".join(mal)

        r.criterio(
            prueba,
            f"{macro}: polígono oficial y regla de título/departamentos coinciden",
            "≥ 95 %",
            acuerdo,
            MINIMO_ACUERDO_MACROREGION,
        )

    def sierra():
        sin_costa = [v for v in control if v["clase"] == "control"]
        tocan = [f"{v['aviso_id']}/{v['mapa']}" for v in sin_costa if set(v["cubre"]) & set(MACROREGIONES_COSTA)]
        return len(sin_costa) - len(tocan), len(sin_costa), ", ".join(tocan)

    r.criterio(
        prueba,
        "avisos sin costa en el título cuyo polígono no toca estaciones de costa norte o centro",
        "100 %",
        sierra,
    )

    def reemplazos():
        tipo = {a["id"]: a["tipo"] for a in avisos}
        cubiertos = {
            (d["fecha"], d["macroregion"], tipo[d["aviso_id"]]) for d in dias if d["aviso_id"] not in cancelados
        }
        sin = sorted(
            {
                d["aviso_id"]
                for d in dias
                if d["aviso_id"] in cancelados and (d["fecha"], d["macroregion"], tipo[d["aviso_id"]]) not in cubiertos
            }
        )
        return len(cancelados) - len(sin), len(cancelados), ", ".join(sin)

    r.criterio(prueba, "días de avisos cancelados cubiertos por otro aviso del mismo tipo", "100 %", reemplazos)

    def por_poligono():
        regla = [a["id"] for a in avisos if a["metodo_macroregion"] != "poligono"]
        return len(avisos) - len(regla), len(avisos), ", ".join(regla)

    r.criterio(
        "senamhi (informativo)",
        "avisos con macro-región por polígono (el resto usa la regla de respaldo)",
        "referencia",
        por_poligono,
        0.0,
    )
    return r.filas
