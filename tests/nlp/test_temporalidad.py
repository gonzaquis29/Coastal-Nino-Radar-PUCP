"""Pruebas sintéticas de la temporalidad (plazo v2): frases inventadas."""

import pytest

from radar.nlp import temporalidad as t


@pytest.mark.parametrize(("texto", "fecha", "inicio", "fin"), t.CASOS)
def test_normalizacion_de_casos_conocidos(texto, fecha, inicio, fin):
    assert t._caso(texto, fecha) == (inicio, fin)


def celda(frase, fecha="2026-08-01"):
    return t.a_celda(t.segmentos(frase, fecha))


def test_sujeto_evento_o_magnitud():
    assert celda("El Niño costero se prolongaría hasta el primer trimestre del 2027.") == "evento:?>2027-01..2027-03"
    assert celda("Habría una magnitud fuerte entre junio y septiembre.", "2026-06-15") == "fuerte:2026-06>2026-09"


def test_declive_cambia_de_fase():
    frase = "El Niño tendría magnitud extraordinaria hasta febrero; luego disminuiría a fuerte hasta abril."
    assert celda(frase, "2026-10-01") == "extraordinaria:?>2027-02|fuerte:?>2027-04"
    assert celda("El Niño sería extraordinario hasta enero, para luego disminuir gradualmente hasta junio.",
                 "2026-10-01") == "extraordinaria:?>2027-01|evento:?>2027-06"  # fmt: skip


def test_fechas_que_no_son_de_el_nino():
    assert celda("El Niño traería lluvias intensas que podrían extenderse hasta febrero de 2027.") == ""
    assert celda("Por El Niño, para el trimestre julio–setiembre se prevé que las temperaturas del aire suban.") == ""
    assert celda("El Niño costero continuaría; la condición neutra llegaría a partir de mayo 2027.") == ""


def test_punto_solo_junto_a_una_magnitud():
    assert celda("El Niño se analizará en julio.", "2026-02-01") == ""
    assert celda("El Niño podría alcanzar una magnitud moderada en julio.", "2026-02-01") == "moderada:2026-07>2026-07"


def test_inicio_del_evento():
    assert celda("El Niño Costero, iniciado en marzo de 2026, se extendería hasta abril.") == (
        "evento:2026-03>?|evento:?>2027-04"
    )


def test_se_cruzan_con_tolerancia():
    assert t.se_cruzan((10, 10), (11, 12))
    assert not t.se_cruzan((10, 10), (12, 12))
    assert t.se_cruzan((10, 10), (12, 12), tolerancia=2)


def seg(sujeto, inicio=None, fin=None):
    return {"sujeto": sujeto, "inicio": inicio, "fin": fin}


def test_fin_del_evento_es_el_mas_tardio():
    assert t.fin_del_evento([seg("evento", fin=(5, 5)), seg("fuerte", fin=(8, 8))]) == [(8, 8)]
    assert t.fin_del_evento([seg("evento", inicio=(1, 1))]) == []


def test_respaldado():
    oficiales = [seg("extraordinaria", (100, 100), (104, 104)), seg("fuerte", None, (107, 108))]
    assert t.respaldado(seg("evento", fin=(108, 109)), oficiales)
    assert t.respaldado(seg("extraordinaria", (101, 101), (104, 104)), oficiales)
    assert not t.respaldado(seg("extraordinaria", None, (110, 110)), oficiales)
    assert not t.respaldado(seg("moderada", None, (104, 104)), oficiales)
