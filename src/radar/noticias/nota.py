"""Lectura de una nota (HTML o API de WordPress) en campos. El cuerpo vive solo en memoria: nunca se guarda."""

import html as html_texto
import json
import re
from urllib.parse import urljoin, urlsplit

from lxml import html

from radar.comun.texto import a_lima, clave, norm

MIN_PALABRAS = 50  # menos que esto es una galería, un video o una página sin texto
TIPOS_NOTA = {"NewsArticle", "Article", "ReportageNewsArticle", "BlogPosting", "AnalysisNewsArticle"}


def _clase(nombre):
    return f"contains(concat(' ', normalize-space(@class), ' '), ' {nombre} ')"


# Contenedor del cuerpo por medio, en orden de preferencia (validado el 24 y el 28-oct-2026); si ninguno aparece, se
# usa el articleBody del JSON-LD. En Andina el cuerpo está en "linknotas", sin el titular ni el crédito de la foto.
CUERPO = {
    "andina": (f"//div[{_clase('paddingnota')}]//div[{_clase('linknotas')}]", f"//div[{_clase('paddingnota')}]"),
    "rpp": (f"//div[{_clase('body')}]",),
    "exitosa": (f"//article[{_clase('content')}]",),
    "eltiempo": ("//div[contains(@class, 'et_pb_post_content')]",),
}
# Dentro del cuerpo: código, leyendas e incrustados de redes no son texto de la nota (RPP pone el cuerpo en un <figure>)
FUERA_DEL_CUERPO = (
    "//script|//style|//noscript|//figcaption|//iframe|//svg"
    "|//blockquote[contains(@class, 'twitter') or contains(@class, 'instagram') or contains(@class, 'tiktok')]"
)
# Bloques que no son la nota: recomendados, promociones, reproductor y anuncios (revisados el 28-oct-2026)
FUERA_POR_MEDIO = {
    "andina": f".//div[{_clase('Top3')}]|.//div[@data-type='_mgwidget']",
    "rpp": (
        f".//div[{_clase('banner')}]|.//div[{_clase('gray-media')}]|.//div[{_clase('article__block')}]"
        f"|.//div[{_clase('player-audio')}]|.//figure[{_clase('media-video')}]"
    ),
    "exitosa": f".//div[{_clase('rela')}]|.//div[{_clase('module_mm')}]|.//div[{_clase('raw-html-embed')}]",
    "eltiempo": "",
}
# Bloques y líneas que enlazan a otras notas: se quitan como nodo (así sus enlaces tampoco cuentan) y como línea
ENLACE_A_OTRAS = re.compile(
    r"^[\s\[(«\"“]*(►|lea también|lee también|puede?s? leer|lee más|leer más|te recomendamos|más en andina|mira también"
    r"|video recomendado|¡mira rpp)",
    re.I,
)
MAX_PALABRAS_ENLACES = 80  # un bloque más largo que empieza así es cuerpo, no una lista de enlaces
# Andina abre el cuerpo con un bloque corto de hora y lugar ("14:11 | Loreto ene. 30.", "22:36 | Ciudad de México,
# ago. 17 (EFE).-"); se reconoce por cómo empieza, no por el formato del lugar o la fecha, que varía
HORA_Y_LUGAR = re.compile(r"^\s*\d{1,2}:\d{2}\s*\|")
MAX_PALABRAS_HORA_Y_LUGAR = 15
# Otras líneas que no son la nota: los créditos de agencia o de foto ("ANDINA/Difusión", "AFP")
LINEA_FUERA = re.compile(
    ENLACE_A_OTRAS.pattern + r"|^(andina|afp|ap|efe|reuters|europa press)(/[^/]{2,40})?$",
    re.I,
)
INICIALES = re.compile(r"^(\(FIN\)\s*)?[A-Z]{2,4}(/[A-Z]{2,4})*$")  # sin re.I: "Lima" o "Piura" no son iniciales
# El Tiempo pone sus enlaces a otras notas en un <blockquote> ("PUEDES LEER ►"); las citas textuales se conservan
CITA_QUE_ES_ENLACE = re.compile(r"^\s*(puede?s?|lee)\s*(leer|más)\b|►", re.I)
SALTO = {
    "p",
    "div",
    "li",
    "ul",
    "ol",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "blockquote",
    "figure",
    "table",
    "tr",
    "section",
}
ENLACES_DE_COMPARTIR = re.compile(r"^(mailto:|javascript:|whatsapp:|#)|sharer|/intent/|shareArticle|share\?", re.I)
CHARSET = re.compile(rb"charset=[\"']?([\w-]+)", re.I)


class NotaInvalida(ValueError):
    """La página no es una nota legible (sin JSON-LD de noticia ni fecha de publicación)."""


def decodificar(contenido, tipo=""):
    """Texto de la página con su charset declarado (Exitosa es ISO-8859-1); UTF-8 si no declara."""
    m = CHARSET.search((tipo or "").encode()) or CHARSET.search(contenido[:5000])
    codificacion = m.group(1).decode().lower() if m else "utf-8"
    try:
        return contenido.decode(codificacion, "replace")
    except LookupError:
        return contenido.decode("utf-8", "replace")


def _objetos_ld(doc):
    for bloque in doc.xpath('//script[@type="application/ld+json"]/text()'):
        try:
            datos = json.loads(bloque, strict=False)
        except ValueError:
            continue
        for objeto in datos if isinstance(datos, list) else datos.get("@graph", [datos]):
            if isinstance(objeto, dict):
                yield objeto


def _nota_ld(doc):
    for objeto in _objetos_ld(doc):
        tipos = objeto.get("@type")
        tipos = set(tipos) if isinstance(tipos, list) else {tipos}
        if tipos & TIPOS_NOTA:
            return objeto
    raise NotaInvalida("sin JSON-LD de noticia")


def _meta(doc, *nombres):
    for nombre in nombres:
        valores = doc.xpath(f'//meta[@name="{nombre}" or @property="{nombre}"]/@content')
        if valores:
            return [limpiar(v) for v in valores if limpiar(v)]
    return []


def limpiar(texto):
    """Entidades HTML (RPP las deja dentro del JSON-LD) y espacios."""
    return norm(html_texto.unescape(texto or ""))


def _sin_titular(cuerpo, titular):
    """Si la primera línea repite el titular, se quita para que no cuente como primer párrafo."""
    primera, _, resto = cuerpo.partition("\n")
    return resto if titular and primera == titular else cuerpo


def _sin_bloques_ajenos(nodo, medio):
    """Quita del cuerpo lo que no es la nota; los enlaces se toman después, sin los de recomendados."""
    for basura in nodo.xpath(FUERA_DEL_CUERPO.replace("//", ".//")):
        basura.drop_tree()
    if FUERA_POR_MEDIO[medio]:
        for basura in nodo.xpath(FUERA_POR_MEDIO[medio]):
            basura.drop_tree()
    for cita in nodo.xpath(".//blockquote"):
        if CITA_QUE_ES_ENLACE.search(cita.text_content()):
            cita.drop_tree()
    for bloque in nodo.xpath(".//p|.//div|.//li|.//ul"):
        texto = bloque.text_content()
        palabras = len(texto.split())
        if (ENLACE_A_OTRAS.match(texto) and palabras <= MAX_PALABRAS_ENLACES) or (
            HORA_Y_LUGAR.match(texto) and palabras <= MAX_PALABRAS_HORA_Y_LUGAR
        ):
            bloque.drop_tree()


def _lineas(nodo):
    """Texto del cuerpo con un salto en cada bloque y en cada <br>: ninguna frase queda pegada a la siguiente."""
    for el in nodo.iter():
        if not isinstance(el.tag, str):
            continue
        if el.tag == "br" or el.tag in SALTO:
            el.tail = "\n" + (el.tail or "")
        if el.tag in SALTO:
            el.text = "\n" + (el.text or "")
    lineas = (norm(linea) for linea in nodo.text_content().split("\n"))
    return "\n".join(
        linea for linea in lineas if linea and not LINEA_FUERA.search(linea) and not INICIALES.match(linea)
    )


def _enlaces(nodo, url_base):
    enlaces = []
    for a in nodo.iter("a"):
        href = (a.get("href") or "").strip()
        if href and not ENLACES_DE_COMPARTIR.search(href):
            enlaces.append(urljoin(url_base, html_texto.unescape(href)))
    return list(dict.fromkeys(enlaces))


def proporcion_en_cuerpo(texto, cuerpo):
    """Qué parte de las palabras (de más de 3 letras) de un texto aparece en el cuerpo."""
    palabras = [p for p in clave(texto).split() if len(p) > 3]
    presentes = set(clave(cuerpo).split())
    return round(sum(p in presentes for p in palabras) / len(palabras), 3) if palabras else None


def _campos(titular, resumen, cuerpo, enlaces, **otros):
    lineas = (norm(linea) for linea in (cuerpo or "").split("\n"))
    cuerpo = _sin_titular("\n".join(linea for linea in lineas if linea), titular)
    return {
        "titular": titular,
        "resumen": resumen,
        "cuerpo": cuerpo,
        "enlaces": enlaces,
        "n_palabras": len(cuerpo.split()),
        "sin_texto": len(cuerpo.split()) < MIN_PALABRAS,
        "resumen_en_cuerpo": proporcion_en_cuerpo(resumen, cuerpo),
        **otros,
    }


def leer_html(medio, contenido, url, tipo=""):
    """Campos de una nota a partir de su HTML (en memoria)."""
    doc = html.fromstring(decodificar(contenido, tipo))
    ld = _nota_ld(doc)
    publicada = a_lima(str(ld.get("datePublished") or ""))
    if not publicada:
        raise NotaInvalida("sin datePublished")
    titular = limpiar(ld.get("headline")) or next(iter(_meta(doc, "og:title")), "")
    resumen = next(iter(_meta(doc, "description", "og:description")), "") or limpiar(ld.get("description"))
    creacion = next((t.split(":", 1)[1] for t in _meta(doc, "mrf:tags") if t.startswith("dateCreated:")), "")
    seccion = limpiar(str(ld.get("articleSection") or "")) or next(iter(_meta(doc, "article:section")), "")
    etiquetas = _meta(doc, "article:tag") or _meta(doc, "news_keywords", "keywords")
    nodo = next((n[0] for xpath in CUERPO[medio] if (n := doc.xpath(xpath))), None)
    if nodo is not None:
        _sin_bloques_ajenos(nodo, medio)
    cuerpo = _lineas(nodo) if nodo is not None else ""
    cuerpo_ld = limpiar(ld.get("articleBody"))
    if len(cuerpo.split()) < MIN_PALABRAS and cuerpo_ld:
        cuerpo = cuerpo_ld
    return _campos(
        titular,
        resumen,
        cuerpo,
        _enlaces(nodo, url) if nodo is not None else [],
        fecha_publicacion=publicada,
        fecha_modificacion=a_lima(str(ld.get("dateModified") or "")),
        fecha_creacion=a_lima(creacion) if creacion else "",
        fuente_fecha="json-ld",
        seccion=seccion or urlsplit(url).path.strip("/").split("/")[0],
        etiquetas=etiquetas,
        cuerpo_vs_ld=proporcion_en_cuerpo(cuerpo_ld, cuerpo) if cuerpo_ld else None,
    )


def _texto_html(fragmento):
    return html.fromstring(f"<div>{fragmento}</div>") if fragmento else None


def leer_api(entrada):
    """Campos de una entrada de la API REST de WordPress (El Tiempo); date_gmt = datePublished (validado)."""
    contenido = _texto_html(entrada.get("content", {}).get("rendered", ""))
    resumen = _texto_html(entrada.get("excerpt", {}).get("rendered", ""))
    if not entrada.get("date_gmt"):
        raise NotaInvalida("sin date_gmt")
    if contenido is not None:
        _sin_bloques_ajenos(contenido, "eltiempo")
    return _campos(
        limpiar(entrada.get("title", {}).get("rendered", "")),
        limpiar(resumen.text_content()) if resumen is not None else "",
        _lineas(contenido) if contenido is not None else "",
        _enlaces(contenido, entrada["link"]) if contenido is not None else [],
        fecha_publicacion=a_lima(entrada["date_gmt"]),
        fecha_modificacion=a_lima(entrada.get("modified_gmt", "")),
        fecha_creacion="",
        fuente_fecha="api",
        seccion=urlsplit(entrada["link"]).path.strip("/").split("/")[0],
        etiquetas=[],
        cuerpo_vs_ld=None,
    )
