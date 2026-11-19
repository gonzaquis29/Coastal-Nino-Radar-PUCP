"""Seudónimos y limpieza del texto de los comentarios (docs/youtube/definicion.md, sección 4).

El seudónimo es HMAC-SHA256 con una sal secreta que solo está en una variable de entorno: sin la sal no se puede
revertir ni cruzar con otros datos, y al borrarla junto con los datos los seudónimos dejan de poder recalcularse.
"""

import functools
import hashlib
import hmac
import re

from radar import config
from radar.comun import entorno

LARGO_SEUDONIMO = 16
LARGO_MINIMO_SAL = 16

MENCION = re.compile(r"(?<![\w.])@[\w.\-]{2,}")
CORREO = re.compile(r"[\w.+\-]+@[\w\-]+\.[\w.\-]+")
URL = re.compile(r"https?://\S+|www\.\S+", re.I)
TELEFONO = re.compile(
    r"(?<!\d)(?:\+?51[\s\-]?)?9\d{2}[\s\-]?\d{3}[\s\-]?\d{3}(?!\d)|(?<!\d)\(?0?1\)?[\s\-]?\d{3}[\s\-]?\d{4}(?!\d)"
)


class SinSal(RuntimeError):
    pass


@functools.cache
def _sal():
    sal = entorno.valor(config.VARIABLE_SAL_YOUTUBE)
    if len(sal) < LARGO_MINIMO_SAL:
        raise SinSal(
            f"Falta la variable de entorno {config.VARIABLE_SAL_YOUTUBE} (al menos {LARGO_MINIMO_SAL} caracteres "
            "al azar). Créala tú; nunca va en el repo."
        )
    return sal.encode("utf-8")


def seudonimo(identificador, sal=None):
    if not identificador:
        return ""
    sal = sal if sal is not None else _sal()
    return hmac.new(sal, identificador.encode("utf-8"), hashlib.sha256).hexdigest()[:LARGO_SEUDONIMO]


def limpiar_texto(texto):
    """Quita correos, direcciones, @menciones y teléfonos (en ese orden: un correo contiene una @)."""
    texto = CORREO.sub("[correo]", texto or "")
    texto = URL.sub("[enlace]", texto)
    texto = MENCION.sub("[mencion]", texto)
    return TELEFONO.sub("[telefono]", texto)
