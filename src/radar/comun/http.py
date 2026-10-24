"""Cliente HTTP del proyecto: robots.txt, ritmo por host, reintentos, hosts caídos y controles de respuesta."""

import email.utils
import logging
import random
import re
import time
from urllib.parse import urlsplit

import requests

from radar import config

log = logging.getLogger(__name__)

ESTADOS_TRANSITORIOS = {429, 500, 502, 503, 504}
ERRORES_TRANSITORIOS = (
    requests.ConnectionError,
    requests.Timeout,
    requests.exceptions.ChunkedEncodingError,
    requests.exceptions.ContentDecodingError,
)


class ErrorDescarga(Exception):
    """Base de los errores de descarga propios (además de los de requests)."""


class Bloqueado(ErrorDescarga):
    """robots.txt no lo permite, el sitio responde 403 o su robots.txt no se puede leer."""


class Rechazado(ErrorDescarga):
    """La respuesta no pasa los controles: host no permitido, tamaño, tipo o descarga incompleta."""


class HostSuspendido(ErrorDescarga):
    """El host falló varias veces seguidas en esta ejecución y ya no se le pide nada más."""


# ---------------------------------------------------------------- robots.txt


def parsear_robots(texto):
    """Grupos de robots.txt: [{"agentes": [...], "reglas": [(permite, patron)]}]."""
    grupos, actual, en_reglas = [], None, False
    for linea in texto.splitlines():
        linea = linea.split("#", 1)[0].strip()
        if ":" not in linea:
            continue
        clave, valor = (x.strip() for x in linea.split(":", 1))
        clave = clave.lower()
        if clave == "user-agent":
            if actual is None or en_reglas:
                actual = {"agentes": [], "reglas": []}
                grupos.append(actual)
                en_reglas = False
            actual["agentes"].append(valor.lower())
        elif clave in ("allow", "disallow") and actual is not None:
            en_reglas = True
            if valor:
                actual["reglas"].append((clave == "allow", valor))
    return grupos


def reglas_para(grupos, token=config.TOKEN_ROBOTS):
    """Reglas del grupo que nombra a nuestro user-agent; si no hay, las de '*'."""
    propias = [g for g in grupos if any(a != "*" and a in token for a in g["agentes"])]
    elegidos = propias or [g for g in grupos if "*" in g["agentes"]]
    return [r for g in elegidos for r in g["reglas"]]


def _patron_a_regex(patron):
    fin = patron.endswith("$")
    cuerpo = re.escape(patron[:-1] if fin else patron).replace(r"\*", ".*")
    return re.compile(cuerpo + ("$" if fin else ""))


def permitido(reglas, ruta):
    """Gana la regla más larga que coincide; en empate, Allow (como Google). Entiende '*' y '$'."""
    largo, permite = -1, True
    for es_allow, patron in reglas:
        if _patron_a_regex(patron).match(ruta) and (len(patron) > largo or (len(patron) == largo and es_allow)):
            largo, permite = len(patron), es_allow
    return permite


def segundos_retry_after(valor, ahora=None):
    """Retry-After en segundos o como fecha HTTP; None si no se entiende. Con tope de config.ESPERA_MAXIMA."""
    valor = (valor or "").strip()
    if valor.isdigit():
        return min(int(valor), config.ESPERA_MAXIMA)
    try:
        fecha = email.utils.parsedate_to_datetime(valor)
    except (TypeError, ValueError):
        return None
    ahora = ahora or time.time()
    return max(0, min(fecha.timestamp() - ahora, config.ESPERA_MAXIMA))


# ---------------------------------------------------------------- cliente


class Cliente:
    """Sesión con user-agent del proyecto. Opcionalmente restringida a hosts permitidos."""

    def __init__(self, hosts_permitidos=None, dormir=time.sleep, reloj=time.monotonic):
        self.sesion = requests.Session()
        self.sesion.headers["User-Agent"] = config.USER_AGENT
        self.hosts = set(hosts_permitidos) if hosts_permitidos else None
        self.dormir, self.reloj = dormir, reloj
        self.ultimo = {}  # host -> momento de la última petición
        self.fallos = {}  # host -> fallos seguidos
        self.robots = {}  # host -> (reglas, sitemaps declarados)

    def _esperar(self, host):
        falta = config.PAUSA_POR_HOST - (self.reloj() - self.ultimo.get(host, -1e9))
        if falta > 0:
            self.dormir(falta)
        self.ultimo[host] = self.reloj()

    def _espera(self, intento, respuesta=None):
        if respuesta is not None:
            s = segundos_retry_after(respuesta.headers.get("Retry-After"))
            if s is not None:
                return s
        return min(config.ESPERA_BASE * 2**intento + random.uniform(0, 1), config.ESPERA_MAXIMA)

    def _fallo(self, host):
        self.fallos[host] = self.fallos.get(host, 0) + 1
        if self.fallos[host] == config.FALLOS_SEGUIDOS_POR_HOST:
            log.warning("%s falló %d veces seguidas: se suspende en esta ejecución", host, self.fallos[host])

    def _pedir(self, url, **kw):
        """GET con reintentos ante errores de red y respuestas 429/5xx; devuelve la última respuesta."""
        host = urlsplit(url).netloc
        if self.fallos.get(host, 0) >= config.FALLOS_SEGUIDOS_POR_HOST:
            raise HostSuspendido(host)
        kw.setdefault("timeout", (config.TIEMPO_CONEXION, config.TIEMPO_LECTURA))
        for intento in range(config.REINTENTOS + 1):
            self._esperar(host)
            ultimo = intento == config.REINTENTOS
            try:
                r = self.sesion.get(url, **kw)
                largo = r.headers.get("Content-Length", "")
                if largo.isdigit() and "Content-Encoding" not in r.headers and int(largo) != len(r.content):
                    raise requests.exceptions.ChunkedEncodingError(f"{len(r.content)} de {largo} bytes")
            except ERRORES_TRANSITORIOS as e:
                log.debug("intento %d de %s: %s", intento + 1, url, e)
                if ultimo:
                    self._fallo(host)
                    raise
                self.dormir(self._espera(intento))
                continue
            if r.status_code in ESTADOS_TRANSITORIOS and not ultimo:
                log.debug("intento %d de %s: HTTP %d", intento + 1, url, r.status_code)
                self.dormir(self._espera(intento, r))
                continue
            if r.status_code in ESTADOS_TRANSITORIOS:
                self._fallo(host)
            else:
                self.fallos[host] = 0
            return r
        raise AssertionError("inalcanzable")

    def robots_de(self, host):
        if host not in self.robots:
            r = self._pedir(f"https://{host}/robots.txt")
            if r.status_code >= 500:
                raise Bloqueado(f"robots.txt de {host} respondió {r.status_code}")
            texto = r.text if r.status_code == 200 else ""
            sitemaps = re.findall(r"(?im)^\s*sitemap:\s*(\S+)", texto)
            self.robots[host] = (reglas_para(parsear_robots(texto)), sitemaps)
        return self.robots[host]

    def get(self, url, pdf=False, **kw):
        """GET respetando robots.txt; con hosts permitidos, controla redirecciones, tamaño y (si pdf) el tipo."""
        partes = urlsplit(url)
        if self.hosts is not None and partes.netloc not in self.hosts:
            raise Rechazado(f"host no permitido: {url}")
        ruta = partes.path + ("?" + partes.query if partes.query else "")
        if not permitido(self.robots_de(partes.netloc)[0], ruta):
            raise Bloqueado(f"robots.txt no permite {url}")
        r = self._pedir(url, **kw)
        if r.status_code == 403:
            raise Bloqueado(f"403 en {url} (no se eluden bloqueos)")
        r.raise_for_status()
        if self.hosts is not None:
            for paso in [*r.history, r]:
                if urlsplit(paso.url).netloc not in self.hosts:
                    raise Rechazado(f"redirección fuera de los hosts permitidos: {paso.url}")
        if len(r.content) > config.MAX_BYTES:
            raise Rechazado(f"{len(r.content)} bytes en {url}")
        if pdf and not (r.content[:5] == b"%PDF-" and "pdf" in r.headers.get("Content-Type", "")):
            raise Rechazado(f"no es un PDF: {url} ({r.headers.get('Content-Type')})")
        return r
