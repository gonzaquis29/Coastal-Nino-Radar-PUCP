"""Archivos de data/urls/: uno por ejecución diaria (AAAA-MM-DD_persona.csv) más su registro de sitemaps."""

import re

from radar import config
from radar.comun.archivos import leer_csv

ARCHIVO_NOTAS = re.compile(r"^\d{4}-\d{2}-\d{2}_[a-z]+\.csv$")


def archivos_de_notas():
    """Rutas de los CSV de notas, en orden (sin los *_sitemaps.csv)."""
    return [ruta for ruta in sorted(config.DIR_URLS.glob("*.csv")) if ARCHIVO_NOTAS.match(ruta.name)]


def filas_de_notas(medio=None):
    """Todas las filas recolectadas, opcionalmente de un solo medio."""
    return [fila for ruta in archivos_de_notas() for fila in leer_csv(ruta) if medio in (None, fila["medio"])]
