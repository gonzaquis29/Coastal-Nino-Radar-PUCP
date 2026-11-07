"""Pruebas sintéticas de la prueba E (sin cargar modelos)."""

import numpy as np
import pytest

from radar.nlp import candidatos
from radar.nlp import recuperador as r


def parrafo(id_, doc, tipo="pesca", seccion="cuerpo", texto="Texto", desde="2026-05-01", hasta="2026-05-14"):
    return {"id": id_, "doc_id": doc, "tipo": tipo, "seccion": seccion, "texto": texto,
            "vigente_desde": desde, "vigente_hasta": hasta}  # fmt: skip


def aviso(id_, tipo="precipitaciones", macro="costa_norte", inicio="2026-05-02", fin="2026-05-03", estado="vigente"):
    return {"id": id_, "tipo": tipo, "macroregiones": macro, "inicio": f"{inicio}T00:00", "fin": f"{fin}T23:59",
            "estado": estado}  # fmt: skip


def test_son_trece_comparaciones_y_tres_redacciones():
    assert r.COMPARACIONES == 13 and round(r.UMBRAL_P, 4) == 0.0038
    assert all(len(x) == 3 for x in r.PLANTILLAS_A.values()) and len(r.PLANTILLAS_B) == len(r.PLANTILLAS_C) == 3
    assert r.BASE in r.CANDIDATOS and r.CRUZADO in r.CANDIDATOS


def test_prefijos_no_incluyen_un_candidato_desconocido():
    assert set(r.PREFIJOS) <= set(r.CANDIDATOS)


def test_fecha_del_parrafo_con_cambio_de_anio():
    assert r.fecha_del_parrafo({"texto": "El lunes 2 de mayo llueve"}, "2026-05-01T00") == "2026-05-02"
    assert r.fecha_del_parrafo({"texto": "El lunes 2 de enero llueve"}, "2026-12-30T00") == "2027-01-02"
    assert r.fecha_del_parrafo({"texto": "Sin fecha"}, "2026-05-01T00") is None


def test_preguntas_grupo_a_usa_el_tipo_del_comunicado():
    parrafos = [parrafo("p0", "c1", "pesca"), parrafo("p1", "c1", "impactos"), parrafo("p2", "c2", "pesca")]
    lista = r.preguntas(parrafos, [], [{"id": "c1", "vigente_desde": "2026-05-01"}])
    pesca = [p for p in lista if p["id"].startswith("A-c1-pesca")]
    assert len(pesca) == 3 and all(p["oro"] == {0} and p["fecha"] == "2026-05-01" for p in pesca)
    assert not [p for p in lista if "seguimiento" in p["id"]]


def test_preguntas_grupo_b_incluye_avisos_simultaneos_y_excluye_cancelados():
    parrafos = [parrafo("a0", "av1", seccion="titulo"), parrafo("b0", "av2", seccion="titulo"),
                parrafo("x0", "av3", seccion="titulo"), parrafo("c0", "av4", seccion="titulo")]  # fmt: skip
    avisos = [aviso("av1"), aviso("av2", inicio="2026-05-01"), aviso("av3", tipo="temperatura"),
              aviso("av4", estado="cancelado")]  # fmt: skip
    lista = [p for p in r.preguntas(parrafos, avisos, []) if p["grupo"] == "B"]
    primera = next(p for p in lista if p["id"].startswith("B-precipitaciones-costa_norte-2026-05-02"))
    assert primera["oro"] == {0, 1}
    assert "2 de mayo" in primera["pregunta"] and "la costa norte" in primera["pregunta"]


def test_preguntas_grupo_c_junta_el_mismo_dia_y_tipo():
    parrafos = [parrafo("a", "av1", seccion="dia", texto="El lunes 2 de mayo"),
                parrafo("b", "av2", seccion="dia", texto="El lunes 2 de mayo"),
                parrafo("c", "av1", seccion="titulo", texto="3 de mayo")]  # fmt: skip
    lista = [p for p in r.preguntas(parrafos, [aviso("av1"), aviso("av2")], []) if p["grupo"] == "C"]
    assert len(lista) == 3 and lista[0]["oro"] == {0, 1} and lista[0]["fecha"] == "2026-05-02"


def test_orden_rompe_empates_al_azar_pero_de_forma_estable():
    idx = list(range(50))
    a = r.orden_de(np.zeros(50), idx, "s1")
    assert a == r.orden_de(np.zeros(50), idx, "s1") and a != idx
    assert r.orden_de(np.array([0.0, 2.0, 1.0]), [10, 20, 30], "s")[:2] == [20, 30]


def test_fusion_de_rangos():
    salida = r.fusion_rangos([0.9, 0.1], [0.2, 0.8], k=60)
    assert salida[0] == pytest.approx(1 / 61 + 1 / 62) and salida[0] == salida[1]


def test_azar_exacto():
    assert r.azar_en(3, 10, 1) == pytest.approx(0.3)
    assert r.azar_en(3, 4, 2) == 1.0


def test_fila_primer_acierto_y_en5():
    fila = r.fila_de({"id": "q", "grupo": "A", "oro": {5, 9}}, [1, 5, 2, 9, 3, 4], 0.1)
    assert fila["primero"] == 2 and fila["en5"] == 2 and fila["oro"] == 2 and fila["candidatos"] == 6
    assert r.fila_de({"id": "q", "grupo": "A", "oro": {7}}, [1, 2], 0.1)["primero"] == ""


def filas_de(grupo, primeros, oro="1", candidatos_n="10"):
    return [{"id": f"{grupo}{i}", "grupo": grupo, "primero": str(p) if p else "", "en5": "1" if p and p <= 5 else "0",
             "oro": oro, "candidatos": candidatos_n} for i, p in enumerate(primeros)]  # fmt: skip


def test_medidas_promedia_grupos_con_el_mismo_peso():
    filas = filas_de("A", [1, 4]) + filas_de("B", [1, 1, 1, 1]) + filas_de("C", [None, None])
    grupos, promedio = r.medidas_de(filas)
    assert grupos["A"]["hit3"] == 0.5 and grupos["B"]["hit3"] == 1 and grupos["C"]["hit3"] == 0
    assert promedio == pytest.approx(0.5)
    assert grupos["A"]["mrr"] == pytest.approx((1 + 0.25) / 2)
    assert grupos["A"]["azar"] == pytest.approx(0.3)


BASE = ({"A": {"hit3": 0.6}, "B": {"hit3": 0.9}}, 0.75)


def medida(a=0.7, b=0.9, promedio=0.80):
    return {"A": {"hit3": a}, "B": {"hit3": b}}, promedio


def test_pasa_candidato_cada_regla():
    assert r.pasa_candidato(medida(), BASE, 0.001, 1.0, 2.0)[0]
    assert not r.pasa_candidato(medida(promedio=0.79), BASE, 0.001, 1.0, 2.0)[0]
    assert not r.pasa_candidato(medida(), BASE, 0.004, 1.0, 2.0)[0]
    assert not r.pasa_candidato(medida(b=0.84), BASE, 0.001, 1.0, 2.0)[0]
    assert not r.pasa_candidato(medida(), BASE, 0.001, 2.5, 2.0)[0]
    assert not r.pasa_candidato(medida(), BASE, 0.001, 1.0, 6.5)[0]


def test_minimos_frente_al_azar():
    assert r.minimos({"A": {"hit3": 0.5, "azar": 0.3}, "B": {"hit3": 0.35, "azar": 0.3}}) == {"A": True, "B": False}


def test_mcnemar_recibe_aciertos_por_pregunta():
    a = {str(i): True for i in range(10)}
    b = {str(i): False for i in range(10)}
    assert candidatos.mcnemar(a, b) == pytest.approx(0.00195, abs=1e-4)
