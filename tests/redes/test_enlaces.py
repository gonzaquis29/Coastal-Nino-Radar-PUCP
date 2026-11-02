"""Pruebas sintéticas de la red de enlaces y citas (sin notas reales)."""

import pytest

from radar.redes import enlaces as red


def _nota(medio, ident, url, sobre="1", actores="", fecha="2026-03-10T10:00:00-05:00"):
    return {
        "medio": medio, "id": ident, "url": url, "sobre_nino": sobre, "actores": actores, "fecha_publicacion": fecha,
    }  # fmt: skip


def _enlace(medio, ident, url):
    return {"medio": medio, "id": ident, "url": url}


@pytest.mark.parametrize(
    ("url", "esperado"),
    [
        ("https://enfen.imarpe.gob.pe/comunicados/", "ENFEN"),
        ("https://cdn.www.gob.pe/uploads/document/file/1/2-comunicado_of_enfen-n-01-2026.pdf?v=1", "ENFEN"),
        ("https://www.imarpe.gob.pe/", "IMARPE"),
        ("https://www.gob.pe/institucion/senamhi/noticias/1-aviso", "SENAMHI"),
        ("https://www.gob.pe/indeci", "INDECI"),
        ("https://portal.indeci.gob.pe/coen/", "INDECI"),
        ("https://www.gob.pe/institucion/pcm/normas-legales/1-115-2026-pcm", "PCM"),
        ("https://www.ana.gob.pe/", "ANA"),
        ("https://www.gob.pe/anin", "gob.pe:anin"),  # 'ana' no es prefijo de 'anin'
        ("https://www.gob.pe/mef", "gob.pe:mef"),
        (
            "https://cdn.www.gob.pe/uploads/document/file/9/7-resolucion-ministerial-n-053-2026-minsa.pdf",
            "gob.pe:minsa",
        ),
        ("https://www.bcrp.gob.pe/", "bcrp"),
        ("https://www.gob.pe/", ""),
        ("https://www.gob.pe/113355-que-es-la-leptospirosis", ""),
        ("https://www.noaa.gov/", None),
    ],
)
def test_entidad(url, esperado):
    assert red.entidad(url) == esperado


def test_medio_de_host():
    assert red.medio_de_host("podcast.andina.pe") == "andina"
    assert red.medio_de_host("www.exitosanoticias.pe") == "exitosa"
    assert red.medio_de_host("rotafono.pe") is None


@pytest.fixture
def datos():
    notas = [
        _nota("rpp", "noticia-1", "https://rpp.pe/peru/a-noticia-1", actores="ENFEN:2|INDECI:1"),
        _nota("rpp", "noticia-2", "https://rpp.pe/peru/b-noticia-2", sobre="0", actores="PCM:1"),
        _nota("andina", "5", "https://andina.pe/agencia/noticia-c-5.aspx", fecha="2026-04-01T09:00:00-05:00"),
    ]
    enlaces = [
        _enlace("rpp", "noticia-1", "https://enfen.imarpe.gob.pe/comunicados/"),
        _enlace("rpp", "noticia-1", "https://enfen.imarpe.gob.pe/otra/"),  # mismo actor: una sola arista
        _enlace("rpp", "noticia-1", "https://rpp.pe/peru/b-noticia-2/"),
        _enlace("rpp", "noticia-1", "https://rpp.pe/peru/a-noticia-1"),  # a sí misma: no cuenta
        _enlace("rpp", "noticia-1", "https://rpp.pe/noticias/enfen"),  # etiqueta
        _enlace("rpp", "noticia-1", "https://www.gob.pe/"),
        _enlace("andina", "5", "https://www.noaa.gov/x"),
        _enlace("andina", "5", "https://www.gob.pe/mef"),
        _enlace("rpp", "noticia-2", "https://www.gob.pe/pcm"),  # no es sobre El Niño: fuera de la red
    ]
    return notas, enlaces, {("rpp", "noticia-1"): "costa_norte"}


def test_aristas(datos):
    notas, enlaces, regiones = datos
    filas, fuera = red.aristas(notas, enlaces, regiones)
    pares = {(a["origen"], a["destino"], a["tipo"]) for a in filas}
    assert pares == {
        ("nota:rpp:noticia-1", "actor:ENFEN", red.ENLACE_ACTOR),
        ("nota:rpp:noticia-1", "actor:ENFEN", red.MENCION),
        ("nota:rpp:noticia-1", "actor:INDECI", red.MENCION),
        ("nota:rpp:noticia-1", "nota:rpp:noticia-2", red.ENLACE_NOTA),
        ("nota:andina:5", "dominio:noaa.gov", red.ENLACE_EXTERNO),
        ("nota:andina:5", "oficial:gob.pe:mef", red.ENLACE_OFICIAL),
    }
    assert len(filas) == len(pares)
    assert fuera["oficial sin entidad"] == 1 and sum(fuera.values()) == 2
    assert {a["macroregion"] for a in filas if a["medio"] == "rpp"} == {"costa_norte"}
    assert {a["mes"] for a in filas if a["medio"] == "andina"} == {"2026-04"}


def test_nodos_pagerank(datos):
    filas = red.nodos(red.aristas(*datos)[0])
    assert sum(f["pagerank"] for f in filas) == pytest.approx(1.0, abs=1e-4)
    enfen = next(f for f in filas if f["nodo"] == "actor:ENFEN")
    assert enfen["grado_entrada"] == 1 and enfen["clase"] == "actor"  # enlace y mención: una arista
    assert next(f for f in filas if f["nodo"] == "nota:rpp:noticia-2")["medio"] == "rpp"


def test_citas(datos):
    notas, _, regiones = datos
    filas = red.citas(notas, red.aristas(*datos)[0], regiones)
    todos = {f["actor"]: f for f in filas if f["grupo"] == "todos"}
    assert todos["ENFEN"]["notas"] == 2
    assert (todos["ENFEN"]["enlazan"], todos["ENFEN"]["mencionan"], todos["ENFEN"]["enlazan_o_mencionan"]) == (1, 1, 1)
    assert todos["ENFEN"]["proporcion"] == 0.5 and todos["PCM"]["enlazan_o_mencionan"] == 0
    assert {(f["grupo"], f["valor"]) for f in filas} >= {
        ("medio", "andina"),
        ("mes", "2026-03"),
        ("macroregion", "costa_norte"),
    }


def test_r1_y_r2(datos, monkeypatch):
    notas, enlaces, _ = datos
    fila = red.r1(notas, enlaces)[0]
    assert fila["valor"] == 0.75 and not fila["pasa"]  # dos al ENFEN y el MEF, de 4 enlaces oficiales
    monkeypatch.setattr(red, "MIN_NOTAS_R2", 1)
    r2 = {f["criterio"]: f for f in red.r2(notas, enlaces)}
    assert r2["R2: ENFEN enlazado y mencionado"]["pasa"]
    assert r2["R2: PCM enlazado y mencionado"]["valor"] == 1.0  # R2 usa notas de todos los temas
