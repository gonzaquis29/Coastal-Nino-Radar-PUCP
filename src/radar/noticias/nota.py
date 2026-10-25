"""Lectura de una nota (HTML o API de WordPress) en campos. El cuerpo vive solo en memoria: nunca se guarda."""

import html as html_texto
import json
import re
from urllib.parse import urljoin, urlsplit

from lxml import html

from radar.comun.texto import a_lima, clave, norm

MIN_PALABRAS = 50  # menos que esto es una galería, un video o una página sin texto
TIPOS_NOTA = {"NewsArticle", "Article", "ReportageNewsArticle", "BlogPosting", "AnalysisNewsArticle"}
# Contenedor del cuerpo por medio (validado el 24-oct-2026); si no aparece, se usa el articleBody del JSON-LD
CUERPO = {
    "andina": "//div[contains(concat(' ', @class, ' '), ' paddingnota ')]",
    "rpp": "//div[contains(concat(' ', @class, ' '), ' body ')]",
    "exitosa": "//article[contains(concat(' ', @class, ' '), ' content ')]",
    "eltiempo": "//div[contains(@class, 'et_pb_post_content')]",
}
# Dentro del cuerpo: tuits incrustados, leyendas y código no son texto de la nota (RPP pone el cuerpo en un <figure>)
FUERA_DEL_CUERPO = "//script|//style|//noscript|//blockquote|//figcaption|//iframe"
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
    """Andina repite el titular al inicio del contenedor: se quita para que no cuente como primer párrafo."""
    return cuerpo[len(titular) :].strip() if titular and cuerpo.startswith(titular) else cuerpo


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
    cuerpo = _sin_titular(norm(cuerpo), titular)
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
    for basura in doc.xpath(FUERA_DEL_CUERPO):
        basura.drop_tree()
    nodos = doc.xpath(CUERPO[medio])
    cuerpo = nodos[0].text_content() if nodos else ""
    cuerpo_ld = limpiar(ld.get("articleBody"))
    if len(cuerpo.split()) < MIN_PALABRAS and cuerpo_ld:
        cuerpo = cuerpo_ld
    return _campos(
        titular,
        resumen,
        cuerpo,
        _enlaces(nodos[0], url) if nodos else [],
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
        for basura in contenido.xpath(FUERA_DEL_CUERPO.replace("//", ".//")):
            basura.drop_tree()
    return _campos(
        limpiar(entrada.get("title", {}).get("rendered", "")),
        limpiar(resumen.text_content()) if resumen is not None else "",
        contenido.text_content() if contenido is not None else "",
        _enlaces(contenido, entrada["link"]) if contenido is not None else [],
        fecha_publicacion=a_lima(entrada["date_gmt"]),
        fecha_modificacion=a_lima(entrada.get("modified_gmt", "")),
        fecha_creacion="",
        fuente_fecha="api",
        seccion=urlsplit(entrada["link"]).path.strip("/").split("/")[0],
        etiquetas=[],
        cuerpo_vs_ld=None,
    )
