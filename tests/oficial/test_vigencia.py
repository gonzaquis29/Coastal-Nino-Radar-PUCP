"""Vigencia del ENFEN y avisos aplicables del Senamhi, con un corpus mínimo armado en la prueba."""

import pytest

from radar.comun.archivos import escribir_csv
from radar.oficial import esquemas
from radar.oficial.vigencia import Corpus

COMUNICADOS = [
    {"id": "enfen-2025-13", "fecha_emision": "2025-12-18", "estado": "No Activo"},
    {"id": "enfen-2026-01", "fecha_emision": "2026-01-15", "estado": "Vigilancia de El Niño Costero"},
]
AVISO = {
    "tipo": "precipitaciones",
    "emision": "2026-01-10",
    "inicio": "2026-01-12T00:00:00-05:00",
    "fin": "2026-01-13T23:59:00-05:00",
    "macroregiones": "costa_norte",
    "url": "u",
}
AVISOS = [
    {**AVISO, "id": "senamhi-2026-010", "numero": 10, "titulo": "LLUVIA EN LA COSTA NORTE", "estado": "vencido"},
    {**AVISO, "id": "senamhi-2026-011", "numero": 11, "titulo": "X (AVISO CANCELADO)", "estado": "cancelado"},
]
DIAS = [
    {"aviso_id": "senamhi-2026-010", "fecha": f, "macroregion": "costa_norte", "nivel_macroregion": n}
    for f, n in [("2026-01-12", "AMARILLO"), ("2026-01-13", "NARANJA")]
]


@pytest.fixture
def corpus(tmp_path):
    for nombre, filas in (
        ("comunicados.csv", COMUNICADOS),
        ("avisos.csv", AVISOS),
        ("aviso_dias.csv", DIAS),
        ("parrafos.csv", []),
    ):
        escribir_csv(tmp_path / nombre, esquemas.ARCHIVOS[nombre], filas)
    return Corpus(tmp_path)


def test_comunicado_vigente_y_dia_de_cambio(corpus):
    assert corpus.comunicado_vigente("2026-01-10")["id"] == "enfen-2025-13"
    assert [c["id"] for c in corpus.comunicados_a_comparar("2026-01-15")] == ["enfen-2026-01", "enfen-2025-13"]
    assert [c["id"] for c in corpus.comunicados_a_comparar("2026-01-16")] == ["enfen-2026-01"]
    assert corpus.comunicado_vigente("2025-01-01") is None


def test_avisos_aplicables(corpus):
    assert corpus.avisos_aplicables("2026-01-09", "costa_norte") == []
    emitidos = corpus.avisos_aplicables("2026-01-10", "costa_norte")
    assert [(a["id"], a["estado_en_fecha"]) for a in emitidos] == [("senamhi-2026-010", "emitido")]  # sin el cancelado
    assert corpus.estado_vigente("2026-01-13", "costa_norte")["nivel_maximo_por_tipo"] == {"precipitaciones": "NARANJA"}
    assert corpus.avisos_aplicables("2026-01-13", "costa_centro") == []
    assert corpus.avisos_aplicables("2026-01-13", "lima") == []  # Lima usa los de costa centro
    assert corpus.avisos_aplicables("2026-01-13", "nacional") == []


def test_parrafos_vigentes(tmp_path):
    parrafos = [
        {"id": "enfen-2026-01-p01", "doc_id": "enfen-2026-01", "fuente": "enfen", "orden": 1, "duplicado_de": ""},
        {"id": "enfen-2026-01-p02", "doc_id": "enfen-2026-01", "fuente": "enfen", "orden": 2, "duplicado_de": "x"},
        {"id": "enfen-2025-13-p01", "doc_id": "enfen-2025-13", "fuente": "enfen", "orden": 1, "duplicado_de": ""},
        {
            "id": "senamhi-2026-010-p01",
            "doc_id": "senamhi-2026-010",
            "fuente": "senamhi",
            "orden": 1,
            "duplicado_de": "",
        },
    ]
    for nombre, filas in (
        ("comunicados.csv", COMUNICADOS),
        ("avisos.csv", AVISOS),
        ("aviso_dias.csv", DIAS),
        ("parrafos.csv", parrafos),
    ):
        escribir_csv(tmp_path / nombre, esquemas.ARCHIVOS[nombre], filas)
    corpus = Corpus(tmp_path)
    assert [p["id"] for p in corpus.parrafos_vigentes("2026-01-16")] == ["enfen-2026-01-p01"]
    dia_de_cambio = {p["id"] for p in corpus.parrafos_vigentes("2026-01-15")}
    assert dia_de_cambio == {"enfen-2026-01-p01", "enfen-2025-13-p01"}
    con_aviso = {p["id"] for p in corpus.parrafos_vigentes("2026-01-12", "costa_norte")}
    assert "senamhi-2026-010-p01" in con_aviso
