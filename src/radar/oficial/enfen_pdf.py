"""Lectura de los PDF de comunicados del ENFEN: líneas → párrafos, tablas y nota que define el estado."""

import difflib
import re

import pymupdf

from radar.comun.texto import clave, norm
from radar.oficial.vocabulario import ESTADOS_ENFEN

if hasattr(pymupdf, "no_recommend_layout"):
    pymupdf.no_recommend_layout()  # evita el aviso impreso en cada find_tables()

# Umbrales medidos en los 19 comunicados (docs/oficial/validacion-2026-10-24.md)
MARCA_NOTA_RELATIVA = 0.8  # un número con letra < 80 % de la línea es marca de nota al pie
HUECO_ENTRE_FRAGMENTOS = 0.15  # separación (en tamaños de letra) que obliga a poner un espacio
LETRA_MAXIMA_NOTA = 9.5  # las notas al pie y fuentes usan letra ≤ 9,5
ALTURA_MINIMA_NOTA = 0.35  # las notas empiezan por debajo de este tercio de la página
CUBRE_TABLA = 0.5  # fracción del bloque dentro de una tabla detectada
HUECO_LEYENDA = 1.5  # un bloque a menos de 1,5 letras de una leyenda la continúa
HUECO_PARRAFO = 0.45  # espacio vertical (en tamaños de letra) que separa párrafos
MARGEN_LINEA_CORTA = 480  # x final (pt) bajo el cual una línea que termina en punto cierra párrafo
LARGO_MINIMO = 25  # caracteres de un párrafo o titular
SIMILITUD_DUPLICADO = 0.9

CABECERA = re.compile(
    r"^(COMISIÓN MULTISECTORIAL ENCARGADA|DEL ESTUDIO NACIONAL DEL FENÓMENO|ENFEN$|Decreto Supremo N|"
    r"[“\"]Año de|https?://enfen\.imarpe\.gob\.pe/?$)",
    re.I,
)
FIRMA = re.compile(
    r"^Comisión Multisectorial( encargada)?( del Estudio Nacional del Fenómeno.*)?$"
    r"|^del Estudio Nacional del Fenómeno",
    re.I,
)
DESCARTE = re.compile(r"^(Figura|Tabla|Fuente)\s*\d*[.:)]|^Para más información|^https?://", re.I)
ENCABEZADO = re.compile(
    r"^(COMUNICADO (OFICIAL|EXTRAORDINARIO) ENFEN|Estado del? sistema de alerta|RESUMEN EJECUTIVO$|"
    r"\d{1,2} (de )?\w+ (de )?\d{4}$|(" + "|".join(ESTADOS_ENFEN) + r")$)",
    re.I,
)
ROTULO = re.compile(r"^(Lluvias|Caudales|Temperatura del [Aa]ire|Pesquero|Embalses)\s*:")
LEYENDA = re.compile(r"^(Figura|Tabla|Fuente)(\s*\d+\s*[.:)]|\s*:|$)", re.I)
INICIO_NOTA = re.compile(r"^\d{1,2}(\s|$|https?:)")
LINEA_ENLACE = re.compile(r"^(\d{1,2}\.?\s*)?https?://\S+$")
ENCABEZADO_TABLA = re.compile(r"^(Magnitud del evento|Probabilidad de Ocurrencia|El Niño( Costero)?\s*\(\w+ \d{4} -)")
ROTULO_PANEL = re.compile(r"^([a-d]\)?\s+)+")
VINETAS = "•−–"


def _texto_linea(linea):
    """Texto de una línea sin marcas de nota pegadas ("Costero1") y con los espacios que faltan entre fragmentos."""
    spans = [s for s in linea["spans"] if s["text"].strip()]
    base = max(s["size"] for s in spans)
    texto, x_fin = "", None
    for s in spans:
        es_marca = re.fullmatch(r"\s*\d{1,2}\s*", s["text"]) and (
            (s["flags"] & 1) or s["size"] < MARCA_NOTA_RELATIVA * base
        )
        if es_marca:
            x_fin = s["bbox"][2]
            continue
        separado = x_fin is not None and s["bbox"][0] - x_fin > HUECO_ENTRE_FRAGMENTOS * s["size"]
        if texto and separado and not texto.endswith(" ") and not s["text"].startswith(" "):
            texto += " "
        texto += s["text"]
        x_fin = s["bbox"][2]
    return norm(texto), base


def _tipo_bloque(bloque, lineas, alto, cajas_tabla, bajo_nota, fin_leyenda):
    """Tipo de un bloque: nota, tabla, leyenda o texto. Devuelve también si ya se está bajo las notas al pie."""
    primera = "".join(s["text"] for s in lineas[0]["spans"]).strip()
    inicio = ROTULO_PANEL.sub("", norm(" ".join("".join(s["text"] for s in ln["spans"]) for ln in lineas)))
    letra = max(s["size"] for ln in lineas for s in ln["spans"] if s["text"].strip())
    if letra <= LETRA_MAXIMA_NOTA and INICIO_NOTA.match(primera) and bloque["bbox"][1] > ALTURA_MINIMA_NOTA * alto:
        bajo_nota = True
    caja = pymupdf.Rect(bloque["bbox"])
    if bajo_nota and letra <= LETRA_MAXIMA_NOTA:
        return "nota", bajo_nota
    if any(caja.intersect(c).get_area() > CUBRE_TABLA * caja.get_area() for c in cajas_tabla):
        return "tabla", bajo_nota
    continua = fin_leyenda is not None and 0 <= bloque["bbox"][1] - fin_leyenda < HUECO_LEYENDA * letra
    if LEYENDA.match(inicio) or continua:
        return "leyenda", bajo_nota
    return "texto", bajo_nota


def lineas_y_tablas(doc):
    """Líneas de todo el documento con su tipo, y las tablas detectadas."""
    lineas, tablas = [], []
    for pagina in doc:
        encontradas = pagina.find_tables().tables
        cajas = [pymupdf.Rect(t.bbox) for t in encontradas]
        for t in encontradas:
            tablas.append(
                {"pag": pagina.number + 1, "filas": [f for f in t.extract() if any((c or "").strip() for c in f)]}
            )
        bajo_nota, fin_leyenda = False, None
        for bloque in pagina.get_text("dict", sort=True)["blocks"]:
            if bloque["type"] != 0:
                continue
            ls = [ln for ln in bloque["lines"] if any(s["text"].strip() for s in ln["spans"])]
            if not ls:
                continue
            tipo, bajo_nota = _tipo_bloque(bloque, ls, pagina.rect.height, cajas, bajo_nota, fin_leyenda)
            fin_leyenda = bloque["bbox"][3] if tipo == "leyenda" else None
            for ln in ls:
                texto, base = _texto_linea(ln)
                if not texto:
                    continue
                if LINEA_ENLACE.match(texto) or "wpdmdl=" in texto:
                    tipo_linea = "nota"  # notas "1. https://…" (N.° 14-15) y enlaces partidos en dos líneas
                elif ENCABEZADO_TABLA.match(texto):
                    tipo_linea = "tabla"
                else:
                    tipo_linea = tipo
                lineas.append(
                    {
                        "pag": pagina.number + 1,
                        "x1": ln["bbox"][2],
                        "y0": ln["bbox"][1],
                        "y1": ln["bbox"][3],
                        "tam": round(base),
                        "texto": texto,
                        "tipo": tipo_linea,
                    }
                )
    return lineas, tablas


def _empieza_parrafo(linea, previa):
    if previa is None:
        return True
    misma_pagina = linea["pag"] == previa["pag"]
    hueco = linea["y0"] - previa["y1"] > HUECO_PARRAFO * linea["tam"] or linea["y0"] < previa["y0"] - 1
    return bool(
        (not misma_pagina and re.search(r"[.:;”\"]$", previa["texto"]))
        or (misma_pagina and (hueco or linea["tam"] != previa["tam"]))
        or (re.search(r"[.:]$", previa["texto"]) and previa["x1"] < MARGEN_LINEA_CORTA)
        or ROTULO.match(linea["texto"])
        or linea["texto"][:1] in VINETAS
        or ENCABEZADO.match(linea["texto"])
        or ENCABEZADO.match(previa["texto"])
    )


def agrupar(lineas):
    """Une líneas en párrafos."""
    parrafos, previa = [], None
    for linea in lineas:
        if _empieza_parrafo(linea, previa):
            parrafos.append({"tam": linea["tam"], "texto": linea["texto"]})
        else:
            actual = parrafos[-1]["texto"]
            pegar = re.search(r"[a-záéíóúñ]-$", actual) and linea["texto"][:1].islower()
            parrafos[-1]["texto"] = actual + linea["texto"] if pegar else actual + " " + linea["texto"]
        previa = linea
    return parrafos


def _seccionar(parrafos_brutos, tam_resumen):
    """Asigna sección (titular, resumen, cuerpo) y descarta encabezados, leyendas y restos."""
    parrafos, seccion = [], "cuerpo"
    for p in parrafos_brutos:
        texto = re.sub(r"^[ab]\)\s+(?=[A-ZÁÉÍÓÚ])", "", p["texto"].lstrip(VINETAS + " ").strip())
        if texto.upper() == "RESUMEN EJECUTIVO":
            seccion = "resumen"
            continue
        if (
            ENCABEZADO.match(texto)
            or DESCARTE.match(texto)
            or FIRMA.match(texto)
            or re.fullmatch(r"[\d\s.,%°|()ab-]*", texto)
        ):
            continue
        if re.fullmatch(r"[A-ZÁÉÍÓÚÑ0-9 ,.]+", texto):
            if len(texto) > LARGO_MINIMO:
                parrafos.append({"seccion": "titular", "texto": texto})
            continue
        if len(texto) < LARGO_MINIMO:
            continue
        if seccion == "resumen" and p["tam"] > tam_resumen:
            seccion = "cuerpo"
        parrafos.append({"seccion": seccion, "texto": texto})
    return parrafos


def _definicion_estado(notas):
    """La nota al pie que define el estado del sistema de alerta ('Alerta de El Niño Costero: …')."""
    for estado in ESTADOS_ENFEN:
        patron = r"\b" + re.escape(estado) + r"\s*[:,]\s*(.+?)(?=\s\d{1,2}\s[A-ZÁÉÍÓÚ]|\s\d{1,2}\s?https?://|$)"
        m = re.search(patron, notas, re.I)
        if m:
            return norm(estado + ": " + re.sub(r"\(Nota Técnica.*", "", m.group(1)))
    return None


def _marcar_duplicados(parrafos):
    for i, p in enumerate(parrafos):
        for j in range(i):
            previo = parrafos[j]
            if "duplicado_de" in previo:
                continue
            if difflib.SequenceMatcher(None, clave(p["texto"]), clave(previo["texto"])).ratio() >= SIMILITUD_DUPLICADO:
                p["duplicado_de"] = j
                break


def extraer(ruta_pdf):
    """Párrafos [{seccion, texto, duplicado_de?}], tablas y texto completo de un comunicado."""
    with pymupdf.open(ruta_pdf) as doc:
        lineas, tablas = lineas_y_tablas(doc)
        texto = norm(" ".join(pagina.get_text() for pagina in doc))
    cuerpo = [
        ln
        for ln in lineas
        if ln["tipo"] == "texto" and not CABECERA.match(ln["texto"]) and not FIRMA.match(ln["texto"])
    ]
    tam_resumen = next(
        (cuerpo[i + 1]["tam"] for i, ln in enumerate(cuerpo[:-1]) if ln["texto"].upper() == "RESUMEN EJECUTIVO"), 0
    )
    parrafos = _seccionar(agrupar(cuerpo), tam_resumen)
    definicion = _definicion_estado(norm(" ".join(ln["texto"] for ln in lineas if ln["tipo"] == "nota")))
    if definicion:
        parrafos.append({"seccion": "definicion", "texto": definicion})
    _marcar_duplicados(parrafos)
    return parrafos, tablas, texto
