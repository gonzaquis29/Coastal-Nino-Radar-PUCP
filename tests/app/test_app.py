"""Pruebas de la app sin modelos: textos (U2, U3, U6), registro de uso (P5), notas (P3) y rutas de la API."""

import re

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from radar import config
from radar.app import api, eventos, legibilidad, servicio, validar
from radar.app import textos as tx

SESION = "abc123def456gh78"


def palabras(texto):
    return set(re.findall(r"[a-záéíóúüñ]+", texto.lower()))


def test_u2_sin_jerga_en_los_textos_del_ciudadano():
    textos = tx.textos_del_ciudadano() + list(tx.CERCANIA.values()) + list(tx.INTERESES.values())
    assert not [t for t in textos if palabras(t) & set(tx.JERGA)]


def test_u3_textos_bastante_faciles():
    assert {t: round(legibilidad.inflesz(t)) for t in tx.textos_del_ciudadano() if legibilidad.inflesz(t) < 65} == {}


def test_u6_sin_promesas_en_resultados_sin_datos():
    sin_datos = [tx.SIN_DATOS, tx.INSUFICIENTE, *tx.CERCANIA_FRASE.values(), *tx.CERCANIA.values()]
    assert not [t for t in sin_datos if palabras(t) & set(tx.PROMESAS)]


SILABAS = [("comunicado", 5), ("ríos", 2), ("huaicos", 2), ("que", 1), ("país", 2), ("aéreo", 4)]


@pytest.mark.parametrize(("palabra", "esperadas"), SILABAS)
def test_silabas(palabra, esperadas):
    assert legibilidad.silabas(palabra) == esperadas


def test_p5_el_registro_no_acepta_texto_libre():
    assert validar.campos_libres(eventos.Evento) == []
    lote = {"sesion": SESION, "dispositivo": "celular", "eventos": [{"evento": "verificar", "texto": "hola"}]}
    with pytest.raises(ValidationError):
        eventos.Lote(**lote)
    with pytest.raises(ValidationError):
        eventos.Lote(sesion="Juan.Perez@correo", dispositivo="celular", eventos=[])
    with pytest.raises(ValidationError):
        eventos.Evento(evento="vista", pantalla="otra")


def test_p3_nota_reciente_solo_con_campos_permitidos(monkeypatch):
    nota = {"medio": "rpp", "id": "1", "titular": "T", "fecha": "2026-11-14", "url": "u", "macroregion": "lima",
            "macroregiones": {"lima"}, "sobre_nino": True, "color": "verde", "resumen": "no debe salir"}  # fmt: skip
    monkeypatch.setattr(servicio, "notas", lambda: {("rpp", "1"): nota})
    s = object.__new__(servicio.Servicio)
    salida = s.nota_reciente("2026-11-15", "lima")
    assert set(salida) <= validar.CAMPOS_PERMITIDOS


def test_notas_en_y_citas_en():
    r = {"que_hacer": {"oficiales": [{"texto": "Se recomienda X.", "parrafo": "p1"}], "nota": {"titular": "T"}},
         "oficial_cercano": None, "afirmaciones": []}  # fmt: skip
    assert list(validar.notas_en(r)) == [{"titular": "T"}]
    assert validar.citas_en(r, {"p1": "Texto. Se recomienda X."}) == (1, 1)
    assert validar.citas_en(r, {"p1": "Otra cosa."}) == (0, 1)


class Falso:
    def estado(self, fecha, macroregion):
        return {"fecha": fecha, "macroregion": macroregion}

    def verificar(self, texto, fecha, macroregion, interes=None):
        return {"tipo": "insuficiente", "fecha": fecha, "interes": interes}


@pytest.fixture
def cliente(monkeypatch, tmp_path):
    monkeypatch.setattr(servicio, "servicio", lambda: Falso())
    monkeypatch.setattr(config, "DIR_APP", tmp_path)
    monkeypatch.setattr(api, "DIST", tmp_path / "dist")
    return TestClient(api.crear(cargar=False))


def test_rutas_y_validacion_de_entrada(cliente):
    assert cliente.post("/api/verificar", json={"texto": "x", "fecha": "2026-11-15"}).json()["fecha"] == "2026-11-15"
    assert cliente.post("/api/verificar", json={"texto": "x", "macroregion": "marte"}).status_code == 422
    assert cliente.post("/api/verificar", json={"texto": "x", "otro": 1}).status_code == 422
    assert cliente.get("/api/estado", params={"fecha": "15/11/2026"}).status_code == 422
    assert cliente.get("/api/no-existe").status_code == 404
    assert cliente.get("/panorama").status_code == 503  # sin web/dist construido


def test_eventos_se_guardan_sin_texto(cliente):
    verificar = {"evento": "verificar", "tipo_resultado": "datos", "resultado": "coincide", "palabras": 12}
    lote = {"sesion": SESION, "dispositivo": "escritorio",
            "eventos": [{"evento": "vista", "pantalla": "verificar"}, verificar]}  # fmt: skip
    assert cliente.post("/api/eventos", json=lote).status_code == 204
    filas = eventos.leer()
    assert [f["evento"] for f in filas] == ["vista", "verificar"]
    assert set(filas[0]) == set(eventos.COLUMNAS)


def test_interfaz_sirve_index_y_no_sale_de_dist(cliente, tmp_path):
    (tmp_path / "dist").mkdir()
    (tmp_path / "dist" / "index.html").write_text("<html>app</html>", encoding="utf-8")
    (tmp_path / "secreto.txt").write_text("no", encoding="utf-8")
    assert "app" in cliente.get("/verificar").text
    assert cliente.get("/../secreto.txt").text != "no"
