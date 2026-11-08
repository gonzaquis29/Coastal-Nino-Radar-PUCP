import datetime as dt
import random

import numpy as np
import pytest

from radar.analitica import recomendador as rec


def _p(doc, temas, tipo="impactos", region="costa", dup="", texto="x"):
    return {"doc_id": doc, "temas": temas, "tipo": tipo, "region_enso": region, "duplicado_de": dup, "texto": texto}


class CorpusFalso:
    def __init__(self):
        self.parrafos = [
            _p("c1", "lluvias", texto="lluvias norte"),
            _p("c1", "pesca"),
            _p("c1", "lluvias|calor", texto="calor y lluvias"),
            _p("c1", "lluvias", tipo="definicion"),
            _p("c1", "lluvias", region="nino_3.4"),
            _p("c1", "lluvias", dup="x"),
            _p("c2", "lluvias"),
        ]

    def comunicado_vigente(self, fecha):
        return {"id": "c1"} if fecha >= "2026-01-01" else None

    def avisos_aplicables(self, fecha, macroregion):
        return (
            [{"id": "a1", "nivel": "AMARILLO"}, {"id": "a2", "nivel": "ROJO"}] if macroregion == "costa_norte" else []
        )


def test_oficial_filtra_por_interes_y_ordena():
    salida = rec.oficial(CorpusFalso(), "2026-03-01", "costa_norte", "lluvias")
    assert [p["texto"] for p in salida["parrafos"]] == ["lluvias norte", "calor y lluvias"]
    assert [a["id"] for a in salida["avisos"]] == ["a2", "a1"]  # el nivel más alto primero
    ordenado = rec.oficial(CorpusFalso(), "2026-03-01", "costa_norte", "lluvias",
                           lambda textos: np.array([t.startswith("calor") for t in textos], float))  # fmt: skip
    assert ordenado["parrafos"][0]["texto"] == "calor y lluvias"
    assert rec.oficial(CorpusFalso(), "2026-03-01", "lima", "pesca")["avisos"] == []
    assert rec.oficial(CorpusFalso(), "2025-12-01", "lima", "pesca")["parrafos"] == []
    with pytest.raises(ValueError):
        rec.oficial(CorpusFalso(), "2026-03-01", "lima", "salud")


def _nota(medio, id_, fecha, sobre="1", menciona="1", url=None):
    return {"medio": medio, "id": id_, "fecha_publicacion": f"{fecha}T10:00:00-05:00", "sobre_nino": sobre,
            "menciona_nino": menciona, "url": url or f"https://{medio}.pe/{id_}"}  # fmt: skip


def test_candidatas_ventana_y_medio():
    cat = [_nota("a", "1", "2026-01-01"), _nota("a", "2", "2026-04-01"), _nota("b", "3", "2026-04-02"),
           _nota("a", "4", "2026-05-01")]  # fmt: skip
    cuando = dt.datetime.fromisoformat("2026-04-10T00:00:00-05:00")
    assert rec.candidatas(cat, cuando) == [1, 2]
    assert rec.candidatas(cat, cuando, "a") == [1]


def test_muestra_a_reglas():
    notas = [_nota("a", "1", "2026-03-01"), _nota("a", "2", "2026-03-05", sobre="0"),
             _nota("a", "3", "2026-03-06", sobre="0", menciona="0"), _nota("b", "4", "2026-03-07", sobre="0"),
             _nota("a", "5", "2026-03-08", sobre="0")]  # fmt: skip
    enlaces = [
        {"medio": "a", "id": "2", "url": "https://a.pe/1?x=1"},  # entra
        {"medio": "a", "id": "3", "url": "https://a.pe/1"},  # no menciona El Niño
        {"medio": "b", "id": "4", "url": "https://a.pe/1"},  # otro medio
        {"medio": "a", "id": "5", "url": "https://a.pe/1"},
    ]  # ya vista
    catalogo = [notas[0]]
    assert rec.muestra_a(notas, enlaces, {("a", "5")}, catalogo) == {("a", "2"): {("a", "1")}}


def test_reserva_y_catalogo():
    notas = [_nota("a", "1", "2026-03-01"), _nota("a", "2", "2026-03-02"), _nota("a", "3", "2026-03-03", sobre="0"),
             _nota("a", "4", "2025-12-30")]  # fmt: skip
    reserva = rec.reserva_t5(notas, {("a", "1"), ("a", "4")})
    assert reserva == {("a", "2")}
    assert [n["id"] for n in rec.catalogo_de(notas, reserva)] == ["1"]


def test_mmr_diversifica():
    vectores = np.array([[1, 0], [1, 0], [0, 1.0]])
    puntajes = np.array([0.9, 0.89, 0.8])
    assert rec.mmr(puntajes, vectores, k=2, lam=0.5)[:2] == [0, 2]
    assert rec.mmr(puntajes, vectores, k=2, lam=1.0) == [0, 1, 2]


def test_premio_region_solo_costa_y_lima():
    cos = np.zeros(3)
    salida = rec.puntajes_region(cos, ["costa_norte", "nacional", "costa_norte"], "costa_norte")
    assert list(salida) == [rec.PREMIO_REGION, 0, rec.PREMIO_REGION]
    assert list(rec.puntajes_region(cos, ["nacional"] * 3, "nacional")) == [0, 0, 0]


def test_metricas():
    assert rec.rango_reciproco([3, 1, 2], {1}) == 0.5
    assert rec.rango_reciproco([3, 2], {1}) == 0.0
    dias = ["d1", "d1", "d1", "d2"]
    assert rec.auc_mismo_dia(np.array([0.9, 0.5, 0.95, 0.1]), dias, {0}) == (1.0, 2)
    d, bajo, alto = rec.diferencia_bootstrap([1.0, 1.0, 1.0], [0.0, 0.0, 0.0], random.Random(0))
    assert d == 1.0 and bajo == 1.0 and alto == 1.0


def test_ordenar_recientes_y_contenido():
    fechas = [dt.datetime(2026, 1, d) for d in (1, 3, 2)]
    cos = np.array([0.1, 0.2, 0.9])
    v = np.eye(3)
    azar = random.Random(0)
    assert rec.ordenar("recientes", cos, v, fechas, [""] * 3, "", azar) == [1, 2, 0]
    assert rec.ordenar("contenido", cos, v, fechas, [""] * 3, "", azar) == [2, 1, 0]


def test_fresco_primero_la_ventana_y_luego_por_fecha():
    cuando = dt.datetime(2026, 3, 10)
    fechas = [dt.datetime(2026, 3, 9), dt.datetime(2026, 3, 1), dt.datetime(2026, 3, 8), dt.datetime(2026, 2, 1)]
    cos = np.array([0.1, 0.99, 0.5, 0.98])
    v = np.eye(4)
    orden = rec.fresco(cos, v, fechas, [""] * 4, "", cuando, 3)
    assert orden[:2] == [2, 0] and orden[2:] == [1, 3]  # dentro por contenido; fuera de la más reciente
    assert rec.fresco(cos, v, fechas, [""] * 4, "", dt.datetime(2026, 5, 1), 3) == [0, 2, 1, 3]


def test_elegir_dias_empate_al_menor():
    filas = [{f"rr_fresco_{d}": (0.5 if d in (7, 14) else 0.1) for d in rec.GRILLA_FRESCURA}]
    assert rec.elegir_dias(filas)[0] == 7


def test_muestra_b_incluye_notas_sobre_el_nino_nuevas():
    notas = [_nota("a", "1", "2026-11-01"), _nota("a", "2", "2026-11-10"), _nota("a", "3", "2026-11-05", sobre="0")]
    enlaces = [{"medio": "a", "id": "2", "url": "https://a.pe/1"}, {"medio": "a", "id": "3", "url": "https://a.pe/1"}]
    assert rec.muestra_b(notas, enlaces, set(), [notas[0]]) == {("a", "2"): {("a", "1")}}
