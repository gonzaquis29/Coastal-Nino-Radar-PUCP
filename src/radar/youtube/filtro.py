"""Qué videos entran (README, "Videos de YouTube"): el título o la descripción mencionan El Niño, con la misma regla
de las notas (`radar.noticias.rasgos.menciones`), y además mencionan Perú o una región peruana, o el canal es de Perú.
Solo cuentan los publicados en el período (del 1-ene al corte, en hora de Lima)."""

import datetime as dt
import re

from radar import config
from radar.comun.texto import a_lima
from radar.noticias.rasgos import menciones
from radar.region.asignacion import NACIONAL, asignar_nota

PERU = re.compile(r"(?<!\w)(?:Per[úu]|peruan[oa]s?)(?!\w)", re.I)
PAIS_PERU = "PE"


def fecha_lima(publicado):
    return dt.date.fromisoformat(a_lima(publicado)[:10]) if publicado else None


def en_periodo(video, fin=None):
    fecha = fecha_lima(video.get("publicado"))
    return fecha is not None and config.INICIO <= fecha <= (fin or config.FIN_CORTE)


def sobre_el_nino(video):
    return bool(menciones(video.get("titulo")) or menciones(video.get("descripcion")))


def de_peru(video, canal=None):
    if canal and canal.get("pais") == PAIS_PERU:
        return True
    titulo, descripcion = video.get("titulo") or "", video.get("descripcion") or ""
    if PERU.search(titulo) or PERU.search(descripcion):
        return True
    return asignar_nota(titulo, descripcion)["macroregiones"] != [NACIONAL]


def pasa(video, canal=None, fin=None):
    return en_periodo(video, fin) and sobre_el_nino(video) and de_peru(video, canal)
