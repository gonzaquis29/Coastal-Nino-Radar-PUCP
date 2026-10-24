"""Registro de ejecución: resumen en pantalla y detalle técnico (con trazas) en data/registros/."""

import contextlib
import logging
import sys

from radar import config
from radar.comun.texto import ahora


def configurar(nombre):
    """Pantalla: INFO sin trazas. Archivo data/registros/<nombre>-AAAAMMDD-HHMMSS.log: DEBUG con trazas."""
    with contextlib.suppress(AttributeError, ValueError):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    raiz = logging.getLogger()
    raiz.setLevel(logging.DEBUG)
    for h in list(raiz.handlers):
        raiz.removeHandler(h)
    pantalla = logging.StreamHandler(sys.stdout)
    pantalla.setLevel(logging.INFO)
    pantalla.setFormatter(logging.Formatter("%(message)s"))
    raiz.addHandler(pantalla)
    config.DIR_REGISTROS.mkdir(parents=True, exist_ok=True)
    ruta = config.DIR_REGISTROS / f"{nombre}-{ahora():%Y%m%d-%H%M%S}.log"
    archivo = logging.FileHandler(ruta, encoding="utf-8")
    archivo.setLevel(logging.DEBUG)
    archivo.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    raiz.addHandler(archivo)
    for ruidoso in ("urllib3", "requests"):
        logging.getLogger(ruidoso).setLevel(logging.WARNING)
    return ruta
