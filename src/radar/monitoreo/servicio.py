"""Lo que la API entrega al mapa. Lee archivos ya descargados: no pide nada a internet."""

import datetime as dt
import re

from radar import config
from radar.comun.archivos import leer_json
from radar.monitoreo import vocabulario as vo

CLAVE = re.compile(r"[a-z0-9-]+_\d{4}-\d{2}-\d{2}")


def datos():
    guardado = leer_json(config.ARCHIVO_MONITOREO)
    if not guardado:
        return {"disponible": False}
    ahora = dt.datetime.now(config.LIMA).strftime("%Y-%m-%dT%H:%M:%S")
    return {"disponible": True, "ahora": ahora, "macroregiones": vo.macroregiones(), **guardado}


def ruta_zona(clave):
    """Ruta del archivo de zona, o None si la clave no es válida o no existe."""
    if not CLAVE.fullmatch(clave):
        return None
    ruta = config.DIR_ZONAS / f"{clave}.json"
    return ruta if ruta.is_file() else None
