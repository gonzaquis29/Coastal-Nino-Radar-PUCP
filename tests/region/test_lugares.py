"""Lista de lugares: lectura del WFS del INEI, decisión medida por nombre y referencias (datos sintéticos)."""

import collections

import pytest

from radar.comun import regiones
from radar.region import lugares, referencias

CAPAS = {
    "ig_departamento": "FID,ccdd,nombdep\n"
    + "".join(f"d.{i},{i:02d},{d['departamento']}\n" for i, d in enumerate(regiones.departamentos(), 1)),
    "ig_provincia": "FID,ccdd,ccpp,nombprov\np.1,01,01,PRIMERA\n",
    "ig_distrito": "FID,ccdd,ccpp,ccdi,ubigeo,nombdist\nx.1,01,01,01,010101,PRIMERA\n",
}


def test_leer_inei():
    leidos = lugares.leer_inei(CAPAS)
    assert len(leidos) == 27
    provincia = next(x for x in leidos if x["nivel"] == "provincia")
    assert provincia["ubigeo"] == "010100" and provincia["departamento"] == "AMAZONAS"


def test_inei_con_departamentos_distintos_es_un_error():
    capas = dict(CAPAS, ig_departamento="FID,ccdd,nombdep\nd.1,01,AMAZONAS\n")
    with pytest.raises(lugares.DatosInvalidos):
        lugares.leer_inei(capas)
    with pytest.raises(lugares.DatosInvalidos):
        lugares.leer_inei(dict(CAPAS, ig_provincia="FID,ccdd,nombre\n"))


def lugar(ubigeo, nivel, nombre, departamento):
    return {"ubigeo": ubigeo, "nivel": nivel, "nombre": nombre, "clave": nombre, "departamento": departamento}


def conteos(rpp=None, eltiempo=None, mayusculas=None, minusculas=None):
    def contadores(d):
        return {k: collections.Counter(v) for k, v in (d or {}).items()}

    return {
        "rpp": contadores(rpp),
        "eltiempo": contadores(eltiempo),
        "mayusculas": collections.Counter(mayusculas or {}),
        "minusculas": collections.Counter(minusculas or {}),
    }


def decision(filas, ubigeo):
    fila = next(f for f in filas if f["ubigeo"] == ubigeo)
    return fila["usar"], fila["motivo"]


def test_decision_medida_y_homonimos():
    todos = [
        lugar("021800", "provincia", "SANTA", "ANCASH"),
        lugar("150110", "distrito", "COMAS", "LIMA"),
        lugar("120000", "distrito", "COMAS", "JUNIN"),
        lugar("040400", "provincia", "CASTILLA", "AREQUIPA"),
        lugar("200104", "distrito", "CASTILLA", "PIURA"),
        lugar("200500", "provincia", "PAITA", "PIURA"),
        lugar("150300", "provincia", "CANTA", "LIMA"),
        lugar("150101", "distrito", "BREÑA", "LIMA"),
    ]
    filas = lugares.decidir(
        todos,
        conteos(
            rpp={"SANTA": {"lima": 5, "costa_centro": 2}, "COMAS": {"lima": 9, "otras": 1}},
            eltiempo={"PAITA": {"local": 8, "nacional": 2}},
            mayusculas={"CANTA": 1},
            minusculas={"CANTA": 5},
        ),
    )
    assert decision(filas, "021800") == (False, "precision_baja")
    assert decision(filas, "150110") == (True, "medido_rpp")
    assert decision(filas, "120000") == (False, "homonimo")
    assert decision(filas, "040400") == (False, "homonimo_sin_medir")
    assert decision(filas, "200500") == (True, "medido_eltiempo")
    assert decision(filas, "150300") == (False, "palabra_comun")
    assert decision(filas, "150101") == (False, "distrito_sin_medir")


def test_referencias():
    assert referencias.macro_rpp("https://rpp.pe/peru/la-libertad/lluvias-noticia-1") == "costa_norte"
    assert referencias.macro_rpp("https://rpp.pe/lima/actualidad/huaico-noticia-2") == "lima"
    assert referencias.macro_rpp("https://rpp.pe/peru/actualidad/x-noticia-3") is None
    assert referencias.macro_rpp("https://rpp.pe/politica/congreso/x-noticia-4") is None
    assert referencias.mitad("noticia-1") == referencias.mitad("noticia-1") in (0, 1)
