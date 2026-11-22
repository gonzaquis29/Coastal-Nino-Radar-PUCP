"""Lo que entra a la API: listas cerradas, fechas con formato y textos con tope de largo."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from radar.app import textos as tx

FECHA = r"^\d{4}-\d{2}-\d{2}$"
LARGO_MAXIMO = 20_000  # caracteres: una nota larga cabe de sobra
LARGO_PREGUNTA = 500

Macroregion = Literal[tuple(tx.MACROREGIONES)]
Interes = Literal[tuple(tx.INTERESES)]
Seccion = Literal["hallazgos", "linea", "magnitudes", "reaccion", "temas", "citas", "youtube"]
SECCIONES_CON_FILTRO = ("linea", "magnitudes", "temas", "youtube")


class PedidoVerificar(BaseModel):
    model_config = ConfigDict(extra="forbid")

    texto: str = Field(max_length=LARGO_MAXIMO)
    macroregion: Macroregion = "lima"
    interes: Interes | None = None
    fecha: str | None = Field(default=None, pattern=FECHA)


class PedidoPreguntar(BaseModel):
    model_config = ConfigDict(extra="forbid")

    consulta: str = Field(min_length=1, max_length=LARGO_PREGUNTA)
    macroregion: Macroregion = "lima"
    interes: Interes | None = None
    fecha: str | None = Field(default=None, pattern=FECHA)
