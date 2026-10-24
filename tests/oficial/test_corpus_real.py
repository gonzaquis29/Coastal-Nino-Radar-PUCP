"""Pruebas sobre el corpus versionado (data/oficial/) y, si existe, sobre lo descargado (data/raw/oficial/)."""

import pytest

from radar import config
from radar.comun.archivos import EstadoDescargas, leer_csv
from radar.oficial import enfen, esquemas
from radar.oficial.vigencia import Corpus

HAY_CORPUS = (config.DIR_OFICIAL / "comunicados.csv").exists()
UN_PDF = enfen.DIR / "comunicado-oficial-enfen-n-18-2026.pdf"


@pytest.mark.skipif(not HAY_CORPUS, reason="corpus no construido")
@pytest.mark.parametrize("nombre", sorted(esquemas.ARCHIVOS))
def test_columnas_segun_esquema(nombre):
    ruta = config.DIR_OFICIAL / nombre
    encabezado = ruta.read_text(encoding="utf-8").split("\n", 1)[0].split(",")
    assert tuple(encabezado) == esquemas.ARCHIVOS[nombre]


@pytest.mark.skipif(not HAY_CORPUS, reason="corpus no construido")
def test_ids_unicos_y_parrafos_con_documento():
    parrafos = leer_csv(config.DIR_OFICIAL / "parrafos.csv")
    documentos = {c["id"] for c in leer_csv(config.DIR_OFICIAL / "comunicados.csv")}
    documentos |= {a["id"] for a in leer_csv(config.DIR_OFICIAL / "avisos.csv")}
    assert len({p["id"] for p in parrafos}) == len(parrafos)
    assert {p["doc_id"] for p in parrafos} <= documentos


@pytest.mark.skipif(not HAY_CORPUS, reason="corpus no construido")
@pytest.mark.parametrize(
    "fecha,estado",
    [
        ("2026-01-01", "No Activo"),
        ("2026-01-14", "No Activo"),
        ("2026-01-15", "Vigilancia de El Niño Costero"),
        ("2026-02-12", "Vigilancia de El Niño Costero"),
        ("2026-02-13", "Alerta de El Niño Costero"),
        ("2026-10-24", "Alerta de El Niño Costero"),
    ],
)
def test_estado_en_fechas_conocidas(fecha, estado):
    assert Corpus().comunicado_vigente(fecha)["estado"] == estado


@pytest.mark.skipif(not (HAY_CORPUS and UN_PDF.exists()), reason="sin descargas en data/raw/oficial")
def test_extraccion_reproduce_el_corpus(tmp_path):
    estado = EstadoDescargas(tmp_path / "estado.json")
    comunicados, _, parrafos, _, errores = enfen.construir([UN_PDF.stem], estado)
    assert not errores
    guardados = [p for p in leer_csv(config.DIR_OFICIAL / "parrafos.csv") if p["doc_id"] == comunicados[0]["id"]]
    assert [p["texto"] for p in parrafos] == [p["texto"] for p in guardados]
