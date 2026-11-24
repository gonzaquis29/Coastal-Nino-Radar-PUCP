"""Pruebas del mapa con datos sintéticos, sin red."""

import datetime as dt
import json

import pytest
from fastapi.testclient import TestClient

from radar import config
from radar.app import api
from radar.monitoreo import actualizar, fuentes, servicio, zonas
from radar.monitoreo import vocabulario as vo

CUADRO = [[[-81, -6], [-80, -6], [-80, -5], [-81, -5], [-81, -6]]]
MITAD = [[[-81, -6], [-80.5, -6], [-80.5, -5], [-81, -5], [-81, -6]]]


def rasgo(nivel, coordenadas):
    return {"type": "Feature", "geometry": {"type": "Polygon", "coordinates": coordenadas},
            "properties": {"nivel": f"Nivel {nivel}", "fech_ini": "2026-11-24T05:00:00Z", "respons": "PERSONA",
                           "fech_fin": "2026-11-25T04:59:59Z"}}  # fmt: skip


@pytest.mark.parametrize(
    ("titulo", "esperado"),
    [
        ("PRECIPITACIONES EN LA SIERRA", "lluvias"),
        ("INCREMENTO DE TEMPERATURA DIURNA EN LA COSTA", "calor"),
        ("DESCENSO DE TEMPERATURA NOCTURNA", "frio"),
        ("Simulacro de sismo y tsunami", "sismo"),
        ("Taller de coordinación", vo.OTRO),
    ],
)
def test_peligro(titulo, esperado):
    assert vo.peligro(titulo) == esperado


def test_departamentos_nombrados_con_tilde():
    assert vo.departamentos_nombrados("lluvias en Áncash y Huánuco") == ["ANCASH", "HUANUCO"]


def test_leer_avisos_y_enlace():
    texto = (
        "Aviso N°481 ROJO PRECIPITACIONES EN LA COSTA NORTE Fecha de emisión: 22 de Noviembre de 2026 "
        "Inicio del evento: 24 de Noviembre de 2026 a las 00:00 Fecha de emisión: x "
        "Fin del evento: 26 de Noviembre de 2026 a las 23:59 Periodo 71 El SENAMHI informa lluvias."
    )
    (a,) = fuentes.leer_avisos(texto, {481: "https://ejemplo/481"}, "https://otro")
    assert (a["numero"], a["nivel"], a["peligro"], a["url"]) == (481, "rojo", "lluvias", "https://ejemplo/481")
    assert (a["inicio"], a["fin"]) == ("2026-11-24T00:00:00", "2026-11-26T23:59:00")


def test_nota_indeci():
    pagina = (
        "<html><body><p>24 de noviembre de 2026</p><h1>INDECI recomienda medidas ante lluvias</h1>"
        "<p>Habrá lluvias en Piura. Se recomienda a la población reforzar los techos.</p></body></html>"
    )
    n = fuentes.leer_nota(pagina, "https://ejemplo")
    assert (n["fecha"], n["peligro"], n["departamentos"]) == ("2026-11-24", "lluvias", ["PIURA"])
    assert n["recomendaciones"] == ["Se recomienda a la población reforzar los techos."]


def test_sismos_en_hora_de_lima():
    f = {"id": "x", "properties": {"mag": 5.04, "time": 1795305600000, "place": "9 km W of Ica, Peru", "url": "u"},
         "geometry": {"coordinates": [-75.0, -14.0, 10.2]}}  # fmt: skip
    (s,) = fuentes.leer_sismos({"features": [f]})
    esperado = dt.datetime.fromtimestamp(1795305600, dt.UTC) - dt.timedelta(hours=5)
    assert s["momento"] == esperado.strftime("%Y-%m-%dT%H:%M:%S")
    assert (s["magnitud"], s["lugar"], s["profundidad"]) == (5.0, "9 km al O de Ica", 10)


def test_mapa_en_hora_de_lima_y_sin_datos_personales():
    z = zonas.leer_mapa({"features": [rasgo(1, CUADRO), rasgo(4, CUADRO)]})
    assert (z["dia"], z["inicio"], z["fin"]) == ("2026-11-24", "2026-11-24T00:00:00", "2026-11-24T23:59:59")
    assert list(z["niveles"]) == ["4"]  # el nivel 1 es «sin aviso»
    assert "PERSONA" not in json.dumps(z)
    assert zonas.leer_mapa({"features": []}) is None


def test_el_nivel_mas_alto_no_se_solapa():
    from shapely.geometry import shape

    por_nivel = {2: [shape({"type": "Polygon", "coordinates": CUADRO})],
                 4: [shape({"type": "Polygon", "coordinates": MITAD})]}  # fmt: skip
    e = zonas.excluyentes(por_nivel)
    assert e[4].area == pytest.approx(0.5)
    assert e[2].area == pytest.approx(0.5)
    assert e[2].intersection(e[4]).area == pytest.approx(0)


@pytest.fixture
def carpeta(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DIR_ZONAS", tmp_path / "zonas")
    monkeypatch.setattr(config, "DIR_RAW_ZONAS", tmp_path / "crudo")
    monkeypatch.setattr(config, "ARCHIVO_MONITOREO", tmp_path / "monitoreo.json")
    return tmp_path


class Caido:
    def get(self, *a, **k):
        raise OSError("sin red")


def test_una_fuente_caida_conserva_su_ultimo_dato(carpeta):
    (carpeta / "monitoreo.json").write_text(json.dumps({"sismos": [{"id": "viejo"}]}), encoding="utf-8")
    g = actualizar.actualizar(Caido(), dt.datetime(2026, 11, 24, 9, tzinfo=config.LIMA))
    assert g["sismos"] == [{"id": "viejo"}]
    assert g["fuentes"]["sismos"]["error"] and not g["fuentes"]["sismos"]["ok"]


def test_zonas_y_nivel_por_distrito(carpeta, monkeypatch):
    class Servidor:
        def get(self, *a, **k):
            return type("R", (), {"json": lambda _: {"features": [rasgo(2, CUADRO), rasgo(4, MITAD)]}})()

    lugares = [["PIURA", "P", "A", -5.5, -80.9], ["PIURA", "P", "B", -5.5, -80.2], ["LIMA", "L", "C", -12.0, -77.0]]
    monkeypatch.setattr(vo, "distritos", lambda: lugares)
    aviso = {"numero": 1, "peligro": "lluvias", "emision": "2026-11-22", "inicio": "2026-11-24T00:00:00",
             "fin": "2026-11-24T23:59:00"}  # fmt: skip
    indice, leidos, fallos = zonas.construir(Servidor(), [aviso], dt.date(2026, 11, 24))
    assert (leidos, fallos) == (1, [])
    assert indice["1"]["2026-11-24"]["distritos"] == "420"
    for clave in ("todo", "lluvias", "aviso-1"):
        assert servicio.ruta_zona(f"{clave}_2026-11-24")


def test_rutas_de_la_api(carpeta):
    cliente = TestClient(api.crear())  # sin el ciclo de arranque: no carga modelos
    assert cliente.get("/api/mapa").json() == {"disponible": False}
    assert cliente.get("/api/mapa/zonas/todo_2026-11-24").status_code == 404
    assert cliente.get("/api/mapa/zonas/..%2Fmonitoreo").status_code in (404, 422)


def test_distritos_de_la_interfaz():
    lugares = vo.distritos()
    assert len(lugares) > 1800
    assert {x[0] for x in lugares} == set(vo.macroregiones())
