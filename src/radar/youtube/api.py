"""YouTube Data API v3 con google-api-python-client: cupo, reintentos y la clave fuera de todo mensaje.

Excepción declarada a `radar.comun.http.Cliente` (CLAUDE.md): la API no es una página web, no tiene robots.txt que
aplique y manda su propio cupo. Aquí se aplican el ritmo, los reintentos y el registro, y se lleva la cuenta del cupo
por día de cupo (se reinicia a medianoche del Pacífico). La clave solo se lee de la variable de entorno y se borra de
todo error y registro, porque los errores de la biblioteca traen la dirección completa con `key=`.
"""

import datetime as dt
import json
import logging
import re
import time

from radar import config
from radar.comun import entorno
from radar.comun.archivos import guardar_json, leer_json
from radar.comun.texto import ahora

log = logging.getLogger(__name__)

POR_PAGINA = 50  # search.list, videos.list y channels.list
COMENTARIOS_POR_PAGINA = 100
ESTADOS_TRANSITORIOS = {429, 500, 502, 503, 504}
MOTIVOS_CUPO = {"quotaExceeded", "dailyLimitExceeded", "rateLimitExceeded"}
MOTIVOS_SIN_COMENTARIOS = {"commentsDisabled", "videoNotFound", "forbidden"}
CLAVE_EN_URL = re.compile(r"(key=)[^&\s\"']+")


class SinClave(RuntimeError):
    pass


class CupoAgotado(RuntimeError):
    pass


class SinComentarios(RuntimeError):
    """Comentarios desactivados, o video borrado o privado."""


class ErrorApi(RuntimeError):
    pass


def clave():
    valor = entorno.valor(config.VARIABLE_CLAVE_YOUTUBE)
    if not valor:
        raise SinClave(f"Falta {config.VARIABLE_CLAVE_YOUTUBE} (variable de entorno o .env) con la clave de la API.")
    return valor


def ocultar(texto, valor=None):
    texto = CLAVE_EN_URL.sub(r"\1***", str(texto))
    return texto.replace(valor, "***") if valor else texto


class _Ocultador(logging.Filter):
    """Por si algún mensaje de la biblioteca llega al registro: le quita la clave."""

    def filter(self, registro):
        registro.msg = ocultar(registro.getMessage())
        registro.args = ()
        return True


def silenciar_biblioteca():
    for nombre in ("googleapiclient", "googleapiclient.discovery", "googleapiclient.http"):
        lg = logging.getLogger(nombre)
        lg.setLevel(logging.WARNING)
        if not any(isinstance(f, _Ocultador) for f in lg.filters):
            lg.addFilter(_Ocultador())


def dia_de_cupo(momento=None):
    """Día de cupo: de las 03:00 de Lima a las 03:00 del día siguiente (medianoche del Pacífico)."""
    return ((momento or ahora()) - dt.timedelta(hours=config.HORAS_LIMA_A_PACIFICO)).date()


def rfc3339(fecha):
    """Medianoche de Lima de esa fecha, en el formato de publishedAfter y publishedBefore."""
    return f"{fecha:%Y-%m-%d}T00:00:00-05:00"


class Cupo:
    """Cuenta de búsquedas y unidades gastadas en cada día de cupo, guardada en data/raw/youtube/cupo.json."""

    def __init__(self, ruta=None, reloj=None):
        self.ruta = ruta or config.DIR_RAW_YOUTUBE / "cupo.json"
        self.reloj = reloj or ahora
        self.datos = leer_json(self.ruta, {}) or {}

    def _hoy(self):
        return self.datos.setdefault(dia_de_cupo(self.reloj()).isoformat(), {"busquedas": 0, "unidades": 0})

    def busquedas_libres(self):
        return config.BUSQUEDAS_POR_DIA - self._hoy()["busquedas"]

    def unidades_libres(self):
        return config.CUPO_POR_DIA - config.MARGEN_CUPO - self._hoy()["unidades"]

    def gastar(self, metodo):
        hoy = self._hoy()
        hoy["busquedas" if metodo == "search" else "unidades"] += 1
        guardar_json(self.ruta, self.datos)

    def agotar(self, metodo):
        """La API dijo que no queda cupo: se anota para no insistir hasta el día siguiente."""
        hoy = self._hoy()
        if metodo == "search":
            hoy["busquedas"] = config.BUSQUEDAS_POR_DIA
        else:
            hoy["unidades"] = config.CUPO_POR_DIA
        guardar_json(self.ruta, self.datos)


def _motivo(error):
    try:
        detalle = json.loads(error.content.decode("utf-8"))["error"]
        return {e.get("reason", "") for e in detalle.get("errors", [])} | {detalle.get("status", "")}
    except (AttributeError, KeyError, TypeError, ValueError):
        return set()


def _estado(error):
    try:
        return int(error.resp.status)
    except (AttributeError, TypeError, ValueError):
        return None


class Api:
    """Las cuatro llamadas que usa el proyecto. `servicio` se inyecta en las pruebas."""

    def __init__(self, servicio=None, cupo=None, dormir=time.sleep):
        self._clave = None
        if servicio is None:
            from googleapiclient.discovery import build

            silenciar_biblioteca()
            self._clave = clave()
            servicio = build("youtube", "v3", developerKey=self._clave, cache_discovery=False)
        self.servicio = servicio
        self.cupo = cupo or Cupo()
        self.dormir = dormir

    def _ejecutar(self, metodo, peticion):
        if (self.cupo.busquedas_libres() if metodo == "search" else self.cupo.unidades_libres()) <= 0:
            raise CupoAgotado(f"sin cupo de {metodo} en el día de cupo {dia_de_cupo()}")
        from googleapiclient.errors import HttpError

        for intento in range(config.REINTENTOS + 1):
            self.dormir(config.PAUSA_API)
            self.cupo.gastar(metodo)
            try:
                return peticion.execute(num_retries=0)
            except HttpError as e:
                estado, motivos = _estado(e), _motivo(e)
                mensaje = ocultar(e, self._clave)
                if motivos & MOTIVOS_CUPO and estado == 403:
                    self.cupo.agotar(metodo)
                    raise CupoAgotado(mensaje) from None
                if motivos & MOTIVOS_SIN_COMENTARIOS or estado == 404:
                    raise SinComentarios(mensaje) from None
                if estado not in ESTADOS_TRANSITORIOS or intento == config.REINTENTOS:
                    raise ErrorApi(mensaje) from None
                log.debug("intento %d de %s: %s", intento + 1, metodo, mensaje)
            except OSError as e:  # red
                if intento == config.REINTENTOS:
                    raise ErrorApi(ocultar(e, self._clave)) from None
            self.dormir(min(config.ESPERA_BASE * 2**intento, config.ESPERA_MAXIMA))
        raise ErrorApi("reintentos agotados")

    def buscar(self, termino, desde, hasta, orden):
        """Ids de la primera página (hasta 50) de videos publicados de `desde` a `hasta`, ambos incluidos."""
        peticion = self.servicio.search().list(
            part="id", q=termino, type="video", regionCode="PE", relevanceLanguage="es", order=orden,
            maxResults=POR_PAGINA, publishedAfter=rfc3339(desde),
            publishedBefore=rfc3339(hasta + dt.timedelta(days=1)),
        )  # fmt: skip
        respuesta = self._ejecutar("search", peticion)
        return [i["id"]["videoId"] for i in respuesta.get("items", []) if i.get("id", {}).get("videoId")]

    def _por_lotes(self, metodo, ids, partes):
        salida = []
        ids = list(dict.fromkeys(ids))
        for i in range(0, len(ids), POR_PAGINA):
            lote = ids[i : i + POR_PAGINA]
            peticion = getattr(self.servicio, metodo)().list(part=partes, id=",".join(lote), maxResults=POR_PAGINA)
            salida += self._ejecutar(metodo, peticion).get("items", [])
        return salida

    def videos(self, ids):
        return self._por_lotes("videos", ids, "snippet,contentDetails,statistics")

    def canales(self, ids):
        return self._por_lotes("channels", ids, "snippet,statistics")

    def comentarios(self, video, pagina=None):
        """(hilos, token de la siguiente página o None). Cada hilo trae algunas de sus respuestas (`replies`); las
        demás se piden con `respuestas`. Lanza SinComentarios si están desactivados."""
        opciones = {"pageToken": pagina} if pagina else {}
        peticion = self.servicio.commentThreads().list(
            part="snippet,replies", videoId=video, maxResults=COMENTARIOS_POR_PAGINA, order="time",
            textFormat="plainText", **opciones,
        )  # fmt: skip
        respuesta = self._ejecutar("commentThreads", peticion)
        return respuesta.get("items", []), respuesta.get("nextPageToken")

    def respuestas(self, hilo, pagina=None):
        """(respuestas de un hilo, token de la siguiente página o None)."""
        opciones = {"pageToken": pagina} if pagina else {}
        peticion = self.servicio.comments().list(
            part="snippet", parentId=hilo, maxResults=COMENTARIOS_POR_PAGINA, textFormat="plainText", **opciones
        )
        respuesta = self._ejecutar("comments", peticion)
        return respuesta.get("items", []), respuesta.get("nextPageToken")
