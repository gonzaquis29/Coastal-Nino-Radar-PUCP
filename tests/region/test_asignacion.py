"""Asignación de macro-región con lugares y textos sintéticos (ninguna nota real)."""

import pytest

from radar.region.asignacion import Asignador, clave, es_nombre_propio, zonas_nota


def lugar(ubigeo, nivel, nombre, departamento, usar=True):
    return {
        "ubigeo": ubigeo,
        "nivel": nivel,
        "nombre": nombre,
        "clave": clave(nombre),
        "departamento": departamento,
        "usar": "1" if usar else "0",
    }


LUGARES = [
    lugar("200000", "departamento", "PIURA", "PIURA"),
    lugar("200600", "provincia", "SULLANA", "PIURA"),
    lugar("130000", "departamento", "LA LIBERTAD", "LA LIBERTAD"),
    lugar("020000", "departamento", "ANCASH", "ANCASH"),
    lugar("021800", "provincia", "SANTA", "ANCASH", usar=False),
    lugar("150000", "departamento", "LIMA", "LIMA"),
    lugar("150135", "distrito", "SAN MARTIN DE PORRES", "LIMA"),
    lugar("220000", "departamento", "SAN MARTIN", "SAN MARTIN"),
    lugar("150500", "provincia", "CAÑETE", "LIMA"),
    lugar("200104", "distrito", "CASTILLA", "PIURA", usar=False),
    lugar("040400", "provincia", "CASTILLA", "AREQUIPA", usar=False),
]


@pytest.fixture
def asignador():
    return Asignador(LUGARES)


def macros(asignador, titular, resumen="", cuerpo=None):
    return asignador.asignar(zonas_nota(titular, resumen, cuerpo))["macroregiones"]


def test_nombre_propio():
    assert es_nombre_propio("La Libertad")
    assert es_nombre_propio("Santiago de Chuco")
    assert not es_nombre_propio("la libertad")


def test_tildes_mayusculas_y_guiones(asignador):
    assert macros(asignador, "Lluvias en Áncash") == ["costa_centro"]
    assert macros(asignador, "LLUVIAS EN PIURA") == ["costa_norte"]
    assert macros(asignador, "Carretera Piura-Sullana bloqueada") == ["costa_norte"]
    assert macros(asignador, "Oleaje en Cañete") == ["lima"]


def test_palabra_comun_y_nombre_excluido(asignador):
    assert macros(asignador, "Defienden la libertad de prensa") == ["nacional"]
    assert macros(asignador, "Feriado de Semana Santa") == ["nacional"]


def test_nombre_mas_largo_gana(asignador):
    assert macros(asignador, "Huaico en San Martín de Porres") == ["lima"]
    assert macros(asignador, "Lluvias en San Martín") == ["otras"]


def test_contexto_administrativo_resuelve_excluidos(asignador):
    assert macros(asignador, "Emergencia en la provincia del Santa") == ["costa_centro"]
    assert macros(asignador, "Alcalde del distrito de Castilla") == ["costa_norte"]
    assert macros(asignador, "Calles de Castilla inundadas") == ["nacional"]


def test_expresiones_de_macroregion(asignador):
    assert macros(asignador, "Lluvias en el norte del país") == ["costa_norte"]
    assert macros(asignador, "Oleaje en toda la costa") == ["costa_centro", "costa_norte", "lima"]
    assert macros(asignador, "Calor en la costa sur") == ["otras"]


def test_pesos_y_umbral(asignador):
    cuerpo_sin_inicio = " ".join(["texto"] * 70)
    assert macros(asignador, "Gobierno anuncia plan", "Medidas", cuerpo_sin_inicio + " Piura") == ["nacional"]
    assert macros(asignador, "Gobierno anuncia plan", "", cuerpo_sin_inicio + " Piura y Sullana") == ["costa_norte"]
    assert macros(asignador, "Gobierno anuncia plan", "", "En Piura " + cuerpo_sin_inicio) == ["costa_norte"]


def test_varias_macroregiones_y_principal(asignador):
    r = asignador.asignar(zonas_nota("Lluvias en Áncash y Piura", "Piura declara emergencia"))
    assert r["macroregiones"] == ["costa_centro", "costa_norte"]
    assert r["macroregion_principal"] == "costa_norte"
    assert r["departamentos"] == ["ANCASH", "PIURA"]
    assert r["lugares"] == ["ANCASH", "PIURA"]
    empate = asignador.asignar(zonas_nota("Lluvias en Áncash y Piura", ""))
    assert empate["macroregion_principal"] == "costa_centro"  # en empate, la nombrada primero
