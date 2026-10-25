"""Descubrimiento, reanudación, fechas dudosas y estimación de pérdida (sin red)."""

import datetime as dt
import json

import pytest
import requests

from radar import config
from radar.comun.archivos import EstadoDescargas, leer_csv
from radar.noticias import historico, medios, viabilidad


class Respuesta:
    def __init__(self, estado=200, contenido=b"", cabeceras=None, url=""):
        self.status_code, self.content, self.headers, self.url = estado, contenido, cabeceras or {}, url

    def json(self):
        return json.loads(self.content)


class ClienteFalso:
    def __init__(self, respuestas):
        self.respuestas, self.pedidas = respuestas, []

    def get(self, url, **_):
        self.pedidas.append(url)
        r = self.respuestas(url)
        if r.status_code == 404:
            raise requests.HTTPError("404", response=r)
        return r


@pytest.fixture
def datos(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DIR_RAW_NOTICIAS", tmp_path)
    monkeypatch.setattr(medios, "filas_de_notas", lambda medio: [])
    return tmp_path


def test_andina_por_numero_se_reanuda_sin_repetir(datos, monkeypatch):
    monkeypatch.setattr(config, "ANDINA_PRIMER_ID", 10)

    def responder(url):
        n = int(url.rsplit("=", 1)[1])
        if n == 11:
            return Respuesta(302, cabeceras={"Location": "/agencia/inicio"})
        return Respuesta(301, cabeceras={"Location": f"https://andina.pe/agencia/noticia-lluvias-en-piura-{n}.aspx"})

    cliente = ClienteFalso(responder)
    andina = medios.Andina(cliente)
    andina.agregar([andina.fila("12", "https://andina.pe/agencia/noticia-x-12.aspx", "diaria")])
    with EstadoDescargas(datos / "estado.json") as estado:
        andina.descubrir(estado)
    assert len(cliente.pedidas) == 2  # el 12 ya estaba (recolección diaria)
    assert [f["url"] != "" for f in leer_csv(datos / "andina" / "lista.csv")] == [True, True, False]
    otra = medios.Andina(ClienteFalso(responder))
    with EstadoDescargas(datos / "estado.json") as estado:
        otra.descubrir(estado)
    assert otra.cliente.pedidas == []


def test_procesar_escribe_una_vez_y_recuerda_lo_que_no_existe(datos, monkeypatch):
    campos = {
        "titular": "Lluvias", "resumen": "Ante El Niño", "cuerpo": "El Niño " * 30, "enlaces": ["https://www.gob.pe/a"],
        "n_palabras": 60, "sin_texto": False, "resumen_en_cuerpo": 0.5, "cuerpo_vs_ld": None,
        "fecha_publicacion": "2026-02-01T10:00:00-05:00", "fecha_modificacion": "", "fecha_creacion": "",
        "fuente_fecha": "json-ld", "seccion": "peru", "etiquetas": [],
    }  # fmt: skip
    rpp = medios.Rpp(cliente=None)
    rpp.leer = lambda fila: campos if fila["id"] == "noticia-1" else (_ for _ in ()).throw(medios.NoExiste("404"))
    filas = [rpp.fila("noticia-1", "https://rpp.pe/peru/lluvias-noticia-1", "archivo:2026-02-01"),
             rpp.fila("noticia-2", "https://rpp.pe/peru/x-noticia-2", "archivo:2026-02-01")]  # fmt: skip
    with EstadoDescargas(datos / "estado.json") as estado:
        assert rpp.procesar(filas, "candidata", estado) == (1, 1, 0)
        assert rpp.procesar(filas, "candidata", estado) == (0, 0, 0)
    nota = leer_csv(datos / "rpp" / "notas.csv")[0]
    assert (nota["sobre_nino"], nota["n_enlaces_oficiales"], nota["terminos_titulo"]) == ("1", "1", "lluvias")
    assert "cuerpo" not in nota


def test_archivo_de_rpp_lee_todas_las_paginas(datos):
    item = '<h2 class="news__title"><a href="https://rpp.pe/peru/actualidad/{0}-noticia-{1}">T&iacute;tulo {1}</a>'
    item += '</h2><time data-x="2026-02-01T10:0{1}:00-05:00">'
    portada = f'<div id="container-news">{item.format("a", 1)}</div><div class="column-fixed">'
    paginas = {
        "https://rpp.pe/archivo/2026-02-01": portada,
        "https://rpp.pe/archivo/2026-02-01/page-1": json.dumps({"html": item.format("b", 2), "nextPage": 2}),
        "https://rpp.pe/archivo/2026-02-01/page-2": json.dumps({"html": item.format("c", 3), "nextPage": False}),
    }
    rpp = medios.Rpp(ClienteFalso(lambda url: Respuesta(contenido=paginas[url].encode())))
    filas = rpp.archivo(dt.date(2026, 2, 1))
    assert [f["id"] for f in filas] == ["noticia-1", "noticia-2", "noticia-3"]
    assert filas[0]["titulo"] == "Título 1" and filas[0]["seccion"] == "peru/actualidad"


def test_fechas_dudosas():
    def nota(medio, ident, fecha, creacion=""):
        return {"medio": medio, "id": ident, "fecha_publicacion": fecha, "fecha_creacion": creacion}

    andina = [nota("andina", str(100 + i), f"2026-03-{1 + i // 5:02d}T10:00:00-05:00") for i in range(30)]
    andina[15]["fecha_publicacion"] = "2026-10-23T08:00:00-05:00"
    rpp = [nota("rpp", "n1", "2026-03-20T10:00:00-05:00", "2026-03-01T10:00:00-05:00")]
    marcadas = historico.marcar_fechas_dudosas(andina + rpp)
    assert [n["id"] for n in marcadas if n["fecha_dudosa"]] == ["115", "n1"]


def test_perdida_por_estratos():
    estratos = [
        viabilidad.Estrato("rpp", "titulo", 10, [True] * 8 + [False] * 2, True),
        viabilidad.Estrato("rpp", "seccion", 100, [True] + [False] * 9, False),
    ]
    assert viabilidad.perdida(estratos, {"rpp": {"seccion"}}) == pytest.approx(10 / 18)
    bajo, alto = viabilidad.intervalo(estratos, {"rpp": {"seccion"}})
    assert 0 <= bajo <= 10 / 18 <= alto <= 1
