"""Peligros del mapa: se asignan por palabras clave, sin etiquetado manual. El primero que coincide manda."""

import re
import unicodedata

from radar import config
from radar.comun.archivos import leer_csv, leer_json

OTRO = "otro"
PELIGROS = (
    ("sismo", r"sismo|temblor|terremoto|tsunami"),
    ("lluvias", r"lluvia|precipitaci|llovizna|hua[iy]co|inundaci|deslizamiento|movimientos? en masa|desborde"),
    ("oleaje", r"oleaje|marejada"),
    ("calor", r"temperatura diurna|calor|radiaci[oó]n ultravioleta"),
    ("viento", r"viento"),
    ("frio", r"helada|friaje|descenso de (?:la )?temperatura|nevada|bajas temperaturas|temperatura nocturna"),
)
RECOMENDACION = re.compile(r"recomienda a la poblaci|se recomienda|se sugiere|exhorta|se insta", re.I)
INTRODUCCION = re.compile(r"recomienda adoptar medidas de preparaci", re.I)
FRASE = re.compile(r"(?<=[.;])\s+(?=[A-ZÁÉÍÓÚ])")
MAXIMO_RECOMENDACIONES = 6


def peligro(titulo):
    return next((nombre for nombre, patron in PELIGROS if re.search(patron, titulo, re.I)), OTRO)


def recomendaciones(texto):
    """Frases literales de la fuente que recomiendan algo a la población."""
    frases = (f.strip() for f in FRASE.split(texto))
    return [f for f in frases if RECOMENDACION.search(f) and not INTRODUCCION.search(f)][:MAXIMO_RECOMENDACIONES]


def normalizar(texto):
    sin_tildes = "".join(c for c in unicodedata.normalize("NFD", texto) if unicodedata.category(c) != "Mn")
    return re.sub(r"[^A-Z0-9]+", " ", sin_tildes.upper()).strip()


def departamentos_nombrados(texto):
    """Departamentos que el texto nombra. Solo se usa con las notas del INDECI: los avisos van por su polígono."""
    t = f" {normalizar(texto)} "
    return sorted(r["departamento"] for r in leer_csv(config.ARCHIVO_REGIONES) if f" {r['departamento']} " in t)


def macroregiones():
    return {r["departamento"]: r["macroregion"] for r in leer_csv(config.ARCHIVO_REGIONES)}


def distritos():
    """[[departamento, provincia, distrito, lat, lon]] en el mismo orden que usa la interfaz."""
    return leer_json(config.ARCHIVO_DISTRITOS, [])
