"""Registro de uso de la app (minería de uso web; docs/app/definicion.md, sección 5).

Cada campo es una opción de una lista cerrada o un número: nunca texto libre, IP ni identificadores (P5). La sesión es
un id al azar que vive en la pestaña del navegador.
"""

import datetime as dt
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from radar import config
from radar.app import textos as tx
from radar.comun.archivos import anexar_csv, leer_csv

ARCHIVO = "eventos.csv"
EVENTOS_POR_LOTE = 50

Pantalla = Literal["verificar", "preguntar", "panorama", "metodologia"]
COLUMNAS = ("momento", "sesion", "dispositivo", "evento", "pantalla", "anterior", "segundos", "tipo_resultado",
            "resultado", "macroregion", "palabras", "interes", "tipo", "posicion", "herramienta", "fuera_alcance",
            "seccion", "filtro")  # fmt: skip


class Evento(BaseModel):
    model_config = ConfigDict(extra="forbid")  # un campo que no está en la lista se rechaza

    evento: Literal["vista", "verificar", "ver_por_que", "interes", "clic_que_hacer", "compartir", "preguntar",
                    "filtro_panorama", "tabla_descargada"]  # fmt: skip
    pantalla: Pantalla | None = None
    anterior: Pantalla | None = None
    segundos: int | None = Field(default=None, ge=0, le=86_400)
    tipo_resultado: Literal["datos", "cercania", "insuficiente"] | None = None
    resultado: Literal["coincide", "revisar", "no_coincide", "cercano", "intermedio", "lejano"] | None = None
    macroregion: Literal[tuple(tx.MACROREGIONES)] | None = None
    palabras: int | None = Field(default=None, ge=0, le=100_000)
    interes: Literal[tuple(tx.INTERESES)] | None = None
    tipo: Literal["oficial", "nota"] | None = None
    posicion: int | None = Field(default=None, ge=0, le=100)
    herramienta: Literal["estado_vigente", "buscar_oficial", "medir_discrepancia", "recomendar", "fuera"] | None = None
    fuera_alcance: bool | None = None
    seccion: Literal["hallazgos", "linea", "magnitudes", "reaccion", "temas", "citas"] | None = None
    filtro: Literal["fechas", "macroregion"] | None = None


class Lote(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sesion: str = Field(pattern=r"^[a-z0-9]{16}$")
    dispositivo: Literal["celular", "escritorio"]
    eventos: list[Evento] = Field(max_length=EVENTOS_POR_LOTE)


def ruta():
    return config.DIR_APP / ARCHIVO


def registrar(lote: Lote, momento=None):
    momento = momento or dt.datetime.now().astimezone().isoformat(timespec="seconds")
    filas = []
    for e in lote.eventos:
        fila = {k: ("" if v is None else int(v) if isinstance(v, bool) else v) for k, v in e.model_dump().items()}
        filas.append({"momento": momento, "sesion": lote.sesion, "dispositivo": lote.dispositivo, **fila})
    config.DIR_APP.mkdir(parents=True, exist_ok=True)
    anexar_csv(ruta(), COLUMNAS, filas)
    return len(filas)


def leer():
    return leer_csv(ruta()) if ruta().exists() else []
