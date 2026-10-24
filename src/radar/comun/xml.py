"""XML de sitemaps: espacios de nombres y lectura segura (sin entidades externas ni red)."""

from lxml import etree

NS_SITEMAP = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9", "n": "http://www.google.com/schemas/sitemap-news/0.9"}
XMLMalFormado = etree.XMLSyntaxError
_PARSER = etree.XMLParser(resolve_entities=False, no_network=True)


def leer_xml(contenido):
    return etree.fromstring(contenido, _PARSER)
