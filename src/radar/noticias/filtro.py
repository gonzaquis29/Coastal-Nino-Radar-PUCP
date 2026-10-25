"""Filtro por título y elección de candidatas (términos en config/terminos_titulo.csv, secciones excluidas en
config/secciones_excluidas.csv)."""

import functools
import re
from urllib.parse import urlsplit

from radar import config
from radar.comun.archivos import leer_csv
from radar.comun.texto import sin_tildes

# Palabras funcionales para reconocer las notas en inglés de Andina, que comparten numeración y no se marcan
# en la página (25 de 25 notas del sitemap en inglés y 2 falsos positivos en 759, el 24-oct-2026)
FUNCIONALES_INGLES = {"the", "of", "to", "in", "and", "for", "on", "with", "is", "are", "its", "from", "at", "by"}
FUNCIONALES_ESPANOL = {"de", "la", "el", "en", "y", "a", "para", "por", "los", "las", "del", "con", "se", "al", "que"}


def palabras(texto):
    """Minúsculas, sin tildes, partido en letras y números: 'Fenómeno El Niño' → {'fenomeno', 'el', 'nino'}."""
    return {p for p in re.split(r"[^a-z0-9]+", sin_tildes((texto or "").lower())) if p}


@functools.cache
def terminos():
    """Formas exactas de los términos (sin quitar plurales: 'niños' no debe contar como 'niño')."""
    return frozenset(f["termino"] for f in leer_csv(config.ARCHIVO_TERMINOS))


@functools.cache
def secciones_excluidas():
    return frozenset((f["medio"], f["seccion"]) for f in leer_csv(config.ARCHIVO_SECCIONES_EXCLUIDAS))


def slug(url):
    """Último tramo de la dirección, sin la extensión de Andina."""
    return urlsplit(url).path.rstrip("/").rsplit("/", 1)[-1].removesuffix(".aspx")


def seccion_principal(url):
    return urlsplit(url).path.strip("/").split("/")[0]


def terminos_en(url, titulo=""):
    """Términos del filtro presentes en el slug y en el título disponible en la vía (ordenados)."""
    return sorted((palabras(slug(url).replace("-", " ")) | palabras(titulo)) & terminos())


def es_ingles(url):
    partes = slug(url).split("-")
    return sum(p in FUNCIONALES_INGLES for p in partes) > sum(p in FUNCIONALES_ESPANOL for p in partes)


def candidata_por(medio, url, titulo=""):
    """Por qué se descarga una nota: 'titulo', 'seccion', 'todo' o '' (no se descarga)."""
    if medio == "andina" and es_ingles(url):
        return ""
    if terminos_en(url, titulo):
        return "titulo"
    modo = config.CANDIDATAS[medio]
    if modo == "todo":
        return "todo"
    if modo == "secciones" and (medio, seccion_principal(url)) not in secciones_excluidas():
        return "seccion"
    return ""
