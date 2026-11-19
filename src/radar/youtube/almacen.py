"""Archivos de YouTube con fecha de descarga en el nombre (AAAA-MM-DD_<tipo>.jsonl o .csv).

Todo dato que viene de la API vence a los config.DIAS_VIDA_YOUTUBE días: `leer` se niega a usar un archivo vencido y
`radar.youtube.borrar` lo elimina. Solo la validación (agregados sin ids) queda sin fecha.
"""

import datetime as dt
import json
import os
import re

from radar import config
from radar.comun.archivos import ruta_segura
from radar.comun.texto import ahora

NOMBRE = re.compile(r"^(\d{4}-\d{2}-\d{2})_([a-z0-9-]+)\.(jsonl|csv|json)$")


class Vencido(RuntimeError):
    """Hay datos de YouTube con más de 30 días: hay que borrarlos o refrescarlos antes de seguir."""


def hoy():
    return ahora().date()


def ruta(tipo, fecha=None, extension="jsonl", base=None):
    fecha = fecha or hoy()
    return ruta_segura(base or config.DIR_RAW_YOUTUBE, f"{fecha:%Y-%m-%d}_{tipo}.{extension}")


def fecha_de(ruta_archivo):
    m = NOMBRE.match(ruta_archivo.name)
    return dt.date.fromisoformat(m.group(1)) if m else None


def vence(fecha):
    return fecha + dt.timedelta(days=config.DIAS_VIDA_YOUTUBE)


def archivos(tipo=None, bases=None):
    """Archivos con fecha de las carpetas de YouTube, del más antiguo al más nuevo."""
    salida = []
    for base in bases or (config.DIR_RAW_YOUTUBE, config.DIR_YOUTUBE):
        if not base.exists():
            continue
        for r in base.iterdir():
            m = NOMBRE.match(r.name)
            if m and (tipo is None or m.group(2) == tipo):
                salida.append(r)
    return sorted(salida, key=lambda r: (fecha_de(r), r.name))


def vencidos(en=None, bases=None):
    en = en or hoy()
    return [r for r in archivos(bases=bases) if vence(fecha_de(r)) <= en]


def comprobar_vigencia(en=None, bases=None):
    viejos = vencidos(en, bases)
    if viejos:
        raise Vencido(
            f"{len(viejos)} archivo(s) de YouTube con más de {config.DIAS_VIDA_YOUTUBE} días (el más antiguo, "
            f"{viejos[0].name}). Córrelo antes: python -m radar.youtube.borrar"
        )


def anexar(tipo, registros, fecha=None):
    """Agrega registros JSON (uno por línea) y los fuerza al disco."""
    destino = ruta(tipo, fecha)
    destino.parent.mkdir(parents=True, exist_ok=True)
    with open(destino, "a", encoding="utf-8", newline="\n") as archivo:
        for r in registros:
            archivo.write(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n")
        archivo.flush()
        os.fsync(archivo.fileno())
    return destino


def leer(tipo, en=None):
    """Registros de todos los archivos vigentes de ese tipo, del más antiguo al más nuevo (cada uno con su fecha)."""
    comprobar_vigencia(en)
    for r in archivos(tipo, bases=(config.DIR_RAW_YOUTUBE,)):
        fecha = fecha_de(r).isoformat()
        with open(r, encoding="utf-8") as archivo:
            for linea in archivo:
                if linea.strip():
                    try:
                        registro = json.loads(linea)
                    except ValueError:
                        continue  # última línea a medias por un corte
                    registro.setdefault("descargado", fecha)
                    yield registro


def ultimos(tipo, clave="id", en=None):
    """El registro más reciente de cada id."""
    return {r[clave]: r for r in leer(tipo, en)}
