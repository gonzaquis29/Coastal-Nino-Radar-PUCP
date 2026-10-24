"""Recolector diario: prioridad de fechas, descarte previo al período y alertas (sin red)."""

import datetime as dt

from radar import config
from radar.recoleccion import diario

MOMENTO = dt.datetime(2026, 10, 24, 12, 0, tzinfo=config.LIMA)


def fuente(medio="rpp"):
    return diario.Fuente(medio, cliente=None, momento=MOMENTO)


def test_fecha_de_publicacion_gana_a_la_de_modificacion():
    f = fuente()
    f.agregar("u", "noticia-1", "2026-10-23T10:00:00-05:00", "modificacion", "peru", "rpp:web/peru")
    f.agregar("u", "noticia-1", "2026-10-22T09:00:00-05:00", "publicacion", "actualidad", "rpp:news")
    fila = f.filas["noticia-1"]
    assert (fila["fecha"], fila["tipo_fecha"], fila["seccion"]) == (
        "2026-10-22T09:00:00-05:00",
        "publicacion",
        {"peru", "actualidad"},
    )


def test_descarta_lo_anterior_al_periodo():
    f = fuente()
    f.agregar("u", "1", "2025-12-31T23:00:00-05:00", "publicacion", "", "x")
    assert f.filas == {}


def test_alerta_de_hueco_y_nuevo_documento_del_enfen():
    rpp, enfen_ = fuente("rpp"), fuente("enfen")
    rpp.cobertura.append(("web/peru", MOMENTO - dt.timedelta(hours=10)))
    ultima = MOMENTO - dt.timedelta(hours=40)
    resumen = [(rpp, 10, [{"id": "n"}], "2026-10-20"), (enfen_, 1, [{"id": "comunicado-oficial-enfen-n-19-2026"}], "-")]
    alertas = diario.alertas_de(resumen, MOMENTO, ultima)
    assert any(a.startswith("HUECO rpp:web/peru") for a in alertas)
    assert "Nuevo documento del ENFEN: comunicado-oficial-enfen-n-19-2026" in alertas
    assert any("40 h" in a for a in alertas)
