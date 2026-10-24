"""Pruebas de las reglas del corpus oficial. Uso: python -m pytest tests/"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from oficial import comun, enfen, senamhi  # noqa: E402
from oficial.corpus import COL_AVISOS, COL_COMUNICADOS, COL_DIAS, COL_PARRAFOS, conservar  # noqa: E402
from oficial.vigencia import Corpus  # noqa: E402


# ---------------------------------------------------------------- seguridad

def test_ruta_segura_rechaza_salir_de_la_carpeta(tmp_path):
    with pytest.raises(comun.Rechazado):
        comun.ruta_segura(tmp_path, "../fuera.pdf")
    with pytest.raises(comun.Rechazado):
        comun.ruta_segura(tmp_path, "a/b.pdf")
    assert comun.ruta_segura(tmp_path, "comunicado-oficial-enfen-n-18-2026.pdf").parent == tmp_path


def test_cliente_rechaza_hosts_no_oficiales():
    with pytest.raises(comun.Rechazado):
        comun.ClienteOficial().traer("https://example.com/x.pdf")


def test_escritura_atomica_no_deja_temporales(tmp_path):
    comun.escribir_csv(tmp_path / "a.csv", ["x", "y"], [{"x": 1, "y": {"b", "a"}}])
    assert (tmp_path / "a.csv").read_text(encoding="utf-8") == "x,y\n1,a|b\n"
    assert not list(tmp_path.glob(".tmp-*"))


# ---------------------------------------------------------------- ENFEN

def test_campos_formato_antiguo_y_nuevo():
    viejo = enfen.campos("COMUNICADO OFICIAL ENFEN N° 01-2026 15 de enero 2026 Estado del sistema de alerta: "
                         "Vigilancia de El Niño Costero RESUMEN … La emisión del próximo Comunicado Oficial ordinario será el viernes 30 de enero de 2026.")
    assert (viejo["numero"], viejo["anio"], viejo["fecha_emision"], viejo["estado"], viejo["proximo_anunciado"]) == \
        (1, 2026, "2026-01-15", "Vigilancia de El Niño Costero", "2026-01-30")
    nuevo = enfen.campos("COMUNICADO OFICIAL ENFEN N°18- 2026 16 octubre 2026 Alerta de El Niño Costero EL NIÑO COSTERO SE EXTENDERÍA")
    assert (nuevo["numero"], nuevo["fecha_emision"], nuevo["estado"]) == (18, "2026-10-16", "Alerta de El Niño Costero")
    ext = enfen.campos("COMUNICADO EXTRAORDINARIO ENFEN N° 01-2025 27 de febrero de 2025 Estado del sistema de alerta: Vigilancia de El Niño Costero")
    assert ext["tipo"] == "extraordinario"


def test_magnitud_separa_regiones_y_lo_que_no_se_descarta():
    p = ["En la región Niño 1+2, es más probable que el evento continúe de magnitud fuerte; sin embargo, no se descarta la magnitud "
         "extraordinaria, hacia finales de 2026. Para la región Niño 3.4 (Pacífico ecuatorial central), El Niño alcanzaría la magnitud muy fuerte.",
         "Se esperan lluvias de moderada a fuerte intensidad en la costa norte."]
    assert enfen.magnitud(p) == ("fuerte", ["fuerte", "extraordinaria"])


def test_temas_por_rotulo_y_palabras():
    assert enfen.temas("Pesquero: La anchoveta se observa…") == {"pesca"}
    assert enfen.temas("Se recomienda a los tomadores de decisiones considerar los avisos.") == {"prevencion"}


def test_regiones_mencionadas():
    assert comun.regiones_mencionadas("lluvias en la costa norte y en Áncash") == {"costa_norte", "costa_centro"}
    assert comun.regiones_mencionadas("anomalías en el Pacífico atmosférico") == set()


# ---------------------------------------------------------------- Senamhi

def test_tipo_y_segmentos_de_avisos():
    assert senamhi.tipo("LLOVIZNA EN LA COSTA CENTRO Y SUR") is None
    assert senamhi.tipo("PRECIPITACIONES EN LA COSTA NORTE Y SIERRA (AVISO CANCELADO)") == "precipitaciones"
    assert senamhi.segmentos("INCREMENTO DE TEMPERATURA DIURNA EN LA COSTA NORTE Y CENTRO") == {"norte", "centro"}
    assert senamhi.segmentos("INCREMENTO DE TEMPERATURA DIURNA EN LA COSTA Y SIERRA") == {"norte", "centro", "sur"}
    assert senamhi.segmentos("LLUVIA EN TUMBES Y PIURA") == {"norte"}


def test_firma_ignora_el_sufijo_de_estado():
    f = {"titulo": "A", "emision": "2026-10-22", "inicio": "2026-10-23", "fin": "2026-10-25", "duracion": "71 Hrs.", "nivel": "ROJO"}
    assert senamhi.firma({**f, "estado_tabla": "vigente"}) == senamhi.firma({**f, "estado_tabla": ""})


def test_cobertura_punto_en_poligono():
    cuadro = [[[-81.5, -4.5], [-80.0, -4.5], [-80.0, -3.0], [-81.5, -3.0], [-81.5, -4.5]]]
    g = {"features": [{"properties": {"nivel": "Nivel 3"}, "geometry": {"type": "MultiPolygon", "coordinates": [cuadro]}}]}
    cub = senamhi.cobertura(g)
    assert cub["PUENTE TUMBES"] == ("costa_norte", 3) and "TRUJILLO" not in cub


def test_conservar_no_empeora_el_corpus():
    viejas = [{"id": "a", "v": 1}, {"id": "b", "v": 1}]
    assert conservar([{"id": "a", "v": 2}], viejas, {"b"}) == [{"id": "a", "v": 2}, {"id": "b", "v": 1}]


# ---------------------------------------------------------------- vigencia (corpus mínimo)

@pytest.fixture
def corpus(tmp_path):
    coms = [{"id": "enfen-2025-13", "fecha_emision": "2025-12-18", "estado": "No Activo"},
            {"id": "enfen-2026-01", "fecha_emision": "2026-01-15", "estado": "Vigilancia de El Niño Costero"}]
    avisos = [{"id": "senamhi-2026-010", "numero": 10, "titulo": "LLUVIA EN LA COSTA NORTE", "tipo": "precipitaciones", "estado": "vencido",
               "emision": "2026-01-10", "inicio": "2026-01-12T00:00:00-05:00", "fin": "2026-01-13T23:59:00-05:00", "macroregiones": "costa_norte", "url": "u"},
              {"id": "senamhi-2026-011", "numero": 11, "titulo": "X (AVISO CANCELADO)", "tipo": "precipitaciones", "estado": "cancelado",
               "emision": "2026-01-10", "inicio": "2026-01-12T00:00:00-05:00", "fin": "2026-01-13T23:59:00-05:00", "macroregiones": "costa_norte", "url": "u"}]
    dias = [{"aviso_id": "senamhi-2026-010", "fecha": f, "macroregion": "costa_norte", "nivel_macroregion": n} for f, n in
            [("2026-01-12", "AMARILLO"), ("2026-01-13", "NARANJA")]]
    comun.escribir_csv(tmp_path / "comunicados.csv", COL_COMUNICADOS, coms)
    comun.escribir_csv(tmp_path / "avisos.csv", COL_AVISOS, avisos)
    comun.escribir_csv(tmp_path / "aviso_dias.csv", COL_DIAS, dias)
    comun.escribir_csv(tmp_path / "parrafos.csv", COL_PARRAFOS, [])
    return Corpus(tmp_path)


def test_comunicado_vigente_y_dia_de_cambio(corpus):
    assert corpus.comunicado_vigente("2026-01-10")["id"] == "enfen-2025-13"
    assert [c["id"] for c in corpus.comunicados_a_comparar("2026-01-15")] == ["enfen-2026-01", "enfen-2025-13"]
    assert [c["id"] for c in corpus.comunicados_a_comparar("2026-01-16")] == ["enfen-2026-01"]
    assert corpus.comunicado_vigente("2025-01-01") is None


def test_avisos_aplicables(corpus):
    assert corpus.avisos_aplicables("2026-01-09", "costa_norte") == []
    emitido = corpus.avisos_aplicables("2026-01-10", "costa_norte")
    assert [(a["id"], a["estado_en_fecha"]) for a in emitido] == [("senamhi-2026-010", "emitido")]  # el cancelado no aparece
    hoy = corpus.estado_vigente("2026-01-13", "costa_norte")
    assert hoy["nivel_maximo_por_tipo"] == {"precipitaciones": "NARANJA"}
    assert corpus.avisos_aplicables("2026-01-13", "costa_centro") == []
    assert corpus.avisos_aplicables("2026-01-13", "lima") == []  # Lima usa los de costa centro


# ---------------------------------------------------------------- corpus real (si está construido)

REAL = comun.DIR_OFICIAL / "comunicados.csv"


@pytest.mark.skipif(not REAL.exists(), reason="corpus no construido")
@pytest.mark.parametrize("fecha,estado", [("2026-01-01", "No Activo"), ("2026-01-14", "No Activo"),
                                          ("2026-01-15", "Vigilancia de El Niño Costero"), ("2026-02-12", "Vigilancia de El Niño Costero"),
                                          ("2026-02-13", "Alerta de El Niño Costero"), ("2026-10-24", "Alerta de El Niño Costero")])
def test_estado_en_fechas_conocidas(fecha, estado):
    assert Corpus().comunicado_vigente(fecha)["estado"] == estado
