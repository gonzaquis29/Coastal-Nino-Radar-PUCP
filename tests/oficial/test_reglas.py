"""Reglas de extracción del corpus oficial: campos y magnitud del ENFEN, alcance y polígonos del Senamhi."""

from radar.oficial import enfen, senamhi
from radar.oficial.corpus import conservar


def test_campos_formato_antiguo_nuevo_y_extraordinario():
    viejo = enfen.campos(
        "COMUNICADO OFICIAL ENFEN N° 01-2026 15 de enero 2026 Estado del sistema de alerta: Vigilancia de El Niño "
        "Costero RESUMEN … La emisión del próximo Comunicado Oficial ordinario será el viernes 30 de enero de 2026."
    )
    assert (viejo["numero"], viejo["anio"], viejo["fecha_emision"], viejo["estado"], viejo["proximo_anunciado"]) == (
        1,
        2026,
        "2026-01-15",
        "Vigilancia de El Niño Costero",
        "2026-01-30",
    )
    nuevo = enfen.campos(
        "COMUNICADO OFICIAL ENFEN N°18- 2026 16 octubre 2026 Alerta de El Niño Costero EL NIÑO COSTERO"
    )
    assert (nuevo["numero"], nuevo["fecha_emision"], nuevo["estado"]) == (18, "2026-10-16", "Alerta de El Niño Costero")
    extra = enfen.campos(
        "COMUNICADO EXTRAORDINARIO ENFEN N° 01-2025 27 de febrero de 2025 Estado del sistema de alerta: "
        "Vigilancia de El Niño Costero"
    )
    assert extra["tipo"] == "extraordinario"
    assert enfen.identificador(extra) == "enfen-ext-2025-01"


def test_magnitud_separa_regiones_y_lo_que_no_se_descarta():
    parrafos = [
        "En la región Niño 1+2, es más probable que el evento continúe de magnitud fuerte; sin embargo, no se descarta "
        "la magnitud extraordinaria, hacia finales de 2026. Para la región Niño 3.4 (Pacífico ecuatorial central), "
        "El Niño alcanzaría la magnitud muy fuerte.",
        "Se esperan lluvias de moderada a fuerte intensidad en la costa norte.",
    ]
    assert enfen.magnitud(parrafos) == ("fuerte", ["fuerte", "extraordinaria"])
    assert enfen.magnitud_canonica("El Niño Moderado".split()[-1]) == "moderada"


def test_temas_por_rotulo_y_palabras():
    assert enfen.temas("Pesquero: La anchoveta se observa…") == {"pesca"}
    assert enfen.temas("Se recomienda a los tomadores de decisiones considerar los avisos.") == {"prevencion"}


def test_tipo_y_segmentos_de_avisos():
    assert senamhi.tipo("LLOVIZNA EN LA COSTA CENTRO Y SUR") is None
    assert senamhi.tipo("PRECIPITACIONES EN LA COSTA NORTE Y SIERRA (AVISO CANCELADO)") == "precipitaciones"
    casos = {
        "INCREMENTO DE TEMPERATURA DIURNA EN LA COSTA NORTE Y CENTRO": {"norte", "centro"},
        "INCREMENTO DE TEMPERATURA DIURNA EN LA COSTA Y SIERRA": {"norte", "centro", "sur"},
        "COSTA NORTE, CENTRO Y SUR": {"norte", "centro", "sur"},
        "PRECIPITACIONES EN LA SIERRA Y COSTA NORTE": {"norte"},
        "LLUVIA EN TUMBES Y PIURA": {"norte"},
        "PRECIPITACIONES EN LA SIERRA": set(),
    }
    for titulo, esperado in casos.items():
        assert senamhi.segmentos(titulo) == esperado, titulo


def test_candidato_y_relacion():
    base = {"emision": "2026-10-20", "fin": "2026-10-22"}
    assert senamhi.candidato({**base, "titulo": "PRECIPITACIONES EN LA COSTA NORTE Y SIERRA"}) == senamhi.ALCANCE
    assert senamhi.candidato({**base, "titulo": "PRECIPITACIONES EN LA SIERRA CENTRO Y SUR"}) == senamhi.CONTROL
    assert senamhi.candidato({**base, "titulo": "LLUVIA EN LA SELVA"}) is None
    assert senamhi.candidato({"emision": "2025-12-01", "fin": "2025-12-03", "titulo": "LLUVIA EN LA COSTA"}) is None
    assert senamhi.relacion("X (ACTUALIZACIÓN DEL AVISO 425)") == ("actualizacion", 425)


def test_firma_ignora_el_sufijo_de_estado():
    fila = {
        "titulo": "A",
        "emision": "2026-10-22",
        "inicio": "2026-10-23",
        "fin": "2026-10-25",
        "duracion": "71 Hrs.",
        "nivel": "ROJO",
    }
    assert senamhi.firma({**fila, "estado_tabla": "vigente"}) == senamhi.firma({**fila, "estado_tabla": ""})


def test_cobertura_punto_en_poligono():
    cuadro = [[[-81.5, -4.5], [-80.0, -4.5], [-80.0, -3.0], [-81.5, -3.0], [-81.5, -4.5]]]
    geojson = {
        "features": [
            {"properties": {"nivel": "Nivel 3"}, "geometry": {"type": "MultiPolygon", "coordinates": [cuadro]}}
        ]
    }
    cubiertas = senamhi.cobertura(geojson)
    assert cubiertas["PUENTE TUMBES"] == ("costa_norte", 3)
    assert "TRUJILLO" not in cubiertas


def test_conservar_no_empeora_el_corpus():
    anteriores = [{"id": "a", "v": 1}, {"id": "b", "v": 1}]
    assert conservar([{"id": "a", "v": 2}], anteriores, {"b"}) == [{"id": "a", "v": 2}, {"id": "b", "v": 1}]
