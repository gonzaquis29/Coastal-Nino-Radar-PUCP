"""Cliente HTTP: robots.txt, reintentos, Retry-After, hosts caídos y controles de respuesta (sin red)."""

import email.utils

import pytest
import requests

from radar import config
from radar.comun import http


class Respuesta:
    def __init__(self, estado=200, contenido=b"ok", cabeceras=None, url="https://a.pe/x", historial=()):
        self.status_code, self.content, self.url, self.history = estado, contenido, url, list(historial)
        self.headers = {"Content-Type": "text/html", **(cabeceras or {})}
        self.text = contenido.decode("utf-8", "replace")

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(str(self.status_code), response=self)


def cliente_con(respuestas, hosts=None):
    """Cliente cuya sesión devuelve (o lanza) las respuestas en orden; robots.txt ya resuelto."""
    cola = list(respuestas)
    cliente = http.Cliente(hosts_permitidos=hosts, dormir=lambda _: None)
    cliente.pedidas = []

    def get(url, **_):
        cliente.pedidas.append(url)
        r = cola.pop(0)
        if isinstance(r, Exception):
            raise r
        return r

    cliente.sesion.get = get
    cliente.robots = {"a.pe": ([], []), "b.pe": ([], [])}
    return cliente


def test_robots_entiende_comodines():
    reglas = http.reglas_para(http.parsear_robots("User-agent: *\nDisallow: /tema*\nAllow: /tema-ok$\n"))
    assert not http.permitido(reglas, "/tema-el-nino")
    assert http.permitido(reglas, "/tema-ok")
    assert http.permitido(reglas, "/peru/actualidad")


def test_retry_after_en_segundos_y_como_fecha():
    assert http.segundos_retry_after("30") == 30
    assert http.segundos_retry_after("9999") == config.ESPERA_MAXIMA
    assert http.segundos_retry_after(email.utils.formatdate(1_000_060, usegmt=True), ahora=1_000_000) == 60
    assert http.segundos_retry_after("mañana") is None


def test_reintenta_errores_transitorios(sin_esperas):
    cliente = cliente_con(
        [requests.exceptions.ChunkedEncodingError("cortada"), Respuesta(503), Respuesta(200, b"listo")]
    )
    assert cliente.get("https://a.pe/x").content == b"listo"
    assert len(cliente.pedidas) == 3


def test_descarga_incompleta_se_reintenta(sin_esperas):
    incompleta = Respuesta(200, b"abc", {"Content-Length": "10"})
    completa = Respuesta(200, b"abcdefghij", {"Content-Length": "10"})
    assert cliente_con([incompleta, completa]).get("https://a.pe/x").content == b"abcdefghij"


def test_host_caido_se_suspende(sin_esperas, monkeypatch):
    monkeypatch.setattr(config, "FALLOS_SEGUIDOS_POR_HOST", 2)
    intentos = config.REINTENTOS + 1
    cliente = cliente_con([requests.ConnectionError("caído")] * (2 * intentos))
    for _ in range(2):
        with pytest.raises(requests.ConnectionError):
            cliente.get("https://a.pe/x")
    with pytest.raises(http.HostSuspendido):
        cliente.get("https://a.pe/y")
    assert len(cliente.pedidas) == 2 * intentos


def test_exito_reinicia_los_fallos(sin_esperas):
    cliente = cliente_con([Respuesta(503)] * (config.REINTENTOS + 1) + [Respuesta(200)])
    with pytest.raises(requests.HTTPError):
        cliente.get("https://a.pe/x")
    assert cliente.fallos["a.pe"] == 1
    cliente.get("https://a.pe/x")
    assert cliente.fallos["a.pe"] == 0


def test_403_no_se_elude():
    cliente = cliente_con([Respuesta(403)])
    with pytest.raises(http.Bloqueado):
        cliente.get("https://a.pe/x")
    assert len(cliente.pedidas) == 1


def test_robots_prohibe_sin_pedir():
    cliente = cliente_con([])
    cliente.robots["a.pe"] = (http.reglas_para(http.parsear_robots("User-agent: *\nDisallow: /privado")), [])
    with pytest.raises(http.Bloqueado):
        cliente.get("https://a.pe/privado/1")
    assert cliente.pedidas == []


def test_hosts_permitidos_y_redirecciones():
    redirigida = Respuesta(200, url="https://otro.pe/x", historial=[Respuesta(301, url="https://a.pe/x")])
    cliente = cliente_con([redirigida], hosts={"a.pe"})
    with pytest.raises(http.Rechazado):
        cliente.get("https://b.pe/x")
    with pytest.raises(http.Rechazado):
        cliente.get("https://a.pe/x")


def test_pdf_se_valida():
    html_falso = Respuesta(200, b"<html>", {"Content-Type": "text/html"})
    pdf = Respuesta(200, b"%PDF-1.5 ...", {"Content-Type": "application/pdf"})
    cliente = cliente_con([html_falso, pdf])
    with pytest.raises(http.Rechazado):
        cliente.get("https://a.pe/c.pdf", pdf=True)
    assert cliente.get("https://a.pe/c.pdf", pdf=True).content.startswith(b"%PDF-")
