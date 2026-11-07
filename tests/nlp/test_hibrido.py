"""Pruebas sintéticas de la prueba D (sin cargar modelos)."""

import math

import numpy as np
import pytest

from radar.nlp import hibrido, reranker, tfidf

NINO, OTROS = tfidf.ESTRATO_NINO, tfidf.ESTRATO_NEGATIVO


def test_limpia_quita_terminos_solo_en_sin():
    bolsa = {"el_niño": 2, "lluvia": 1, "enfen": 1}
    assert hibrido.limpia(bolsa, "sin") == {"lluvia": 1}
    assert hibrido.limpia(bolsa, "con") == bolsa


def test_bm25_calcula_la_formula_y_divide_por_el_largo():
    modelo = hibrido.Bm25([{"lluvia": 1, "piura": 1}, {"pesca": 2}])
    idf = math.log(1 + 1.5 / 1.5)
    freno = 1.5 * (1 - 0.75 + 0.75 * 2 / 2)
    esperado = idf * 1 * 2.5 / (1 + freno)
    puntajes = modelo.puntajes({"lluvia": 1, "ausente": 1})
    assert puntajes[0] == pytest.approx(esperado / 2) and puntajes[1] == 0


def test_bm25_consulta_vacia_no_divide_por_cero():
    assert hibrido.Bm25([{"a": 1}]).puntajes({}).tolist() == [0.0]


def test_parametros_por_variante():
    filas = [{"cos_con": "1", "bm25_con": "2", "cos_sin": "3", "bm25_sin": ""},
             {"cos_con": "3", "bm25_con": "4", "cos_sin": "5", "bm25_sin": "1"},
             {"cos_con": "", "bm25_con": "", "cos_sin": "", "bm25_sin": "3"}]  # fmt: skip
    param = hibrido.parametros(filas)
    assert param["con"][0][0] == 2 and param["sin"][1][0] == 2


def test_fusion_da_el_mismo_peso_a_los_dos():
    param = ((1.0, 2.0), (10.0, 5.0))
    salida = hibrido.fusion(np.array([3.0, 1.0]), np.array([10.0, 15.0]), param)
    assert salida.tolist() == [1.0, 1.0]


class Falso:
    parrafos = [
        {"id": "viejo", "tipo": "pesca", "vigente_desde": "2026-01-01", "vigente_hasta": "2026-02-01"},
        {"id": "p1", "tipo": "pesca", "vigente_desde": "2026-05-01", "vigente_hasta": "2026-05-14"},
        {"id": "p2", "tipo": "impactos", "vigente_desde": "2026-05-01", "vigente_hasta": "2026-05-14"},
    ]

    def crudos(self, texto, mascara, variante):
        assert mascara.tolist() == [False, True, True]
        return np.array([0.4, 0.5]), np.array([3.0, 0.0])


NOTA = {"medio": "rpp", "id": "a", "titular": "T", "resumen": "R", "fecha_publicacion": "2026-05-02"}


def test_fila_elige_por_la_fusion_y_no_guarda_texto():
    param = {"sin": ((0.0, 1.0), (0.0, 1.0)), "con": ((0.0, 1.0), (0.0, 1.0))}
    fila = hibrido.fila_puntuada(NOTA, NINO, False, False, Falso(), param)
    assert fila["sin"] == 3.4 and fila["cos_sin"] == 0.5 and fila["parrafo"] == "p1" and "con" not in fila
    assert "T" not in fila.values() and "R" not in fila.values()


def test_fila_referencia_guarda_los_dos_maximos():
    fila = hibrido.fila_referencia(NOTA, Falso())
    assert fila["cos_con"] == 0.5 and fila["bm25_con"] == 3.0 and fila["cos_sin"] == 0.5 and fila["bm25_sin"] == 3.0


def test_referencia_solo_del_estrato_y_con_texto():
    notas = [{"medio": "rpp", "id": x} for x in "abcd"]
    control = [
        {"medio": "rpp", "id": "a", "estrato": "cercano"},
        {"medio": "rpp", "id": "b", "estrato": OTROS},
        {"medio": "rpp", "id": "c", "estrato": "cercano"},
        {"medio": "rpp", "id": "z", "estrato": "cercano"},
    ]
    lista = {("rpp", "a"): {"error": ""}, ("rpp", "b"): {"error": ""}, ("rpp", "c"): {"error": "sin texto"}}
    assert [n["id"] for n in hibrido.referencia_de_notas(notas, control, lista)] == ["a"]


BASE = {"e4": (0.86, (0.84, 0.878)), "e3": (0.86, (0.78, 0.94)), "nuevas": (0.90, (0.87, 0.93))}


def medida(e4=0.90, bajo=0.88, e3=0.85, nuevas=0.91):
    return {"e4": (e4, (bajo, 0.92)), "e3": (e3, (0.8, 0.9)), "nuevas": (nuevas, (0.8, 0.9))}


def test_resultado_exige_tiempo_ademas_de_la_regla():
    assert hibrido.resultado_de(medida(), BASE, True)[0]
    assert not hibrido.resultado_de(medida(), BASE, False)[0]
    assert not hibrido.resultado_de(medida(e4=0.87), BASE, True)[0]
    assert not hibrido.resultado_de(medida(nuevas=0.90), BASE, True)[0]


def test_control_compara_con_la_base_por_nota():
    filas = [{"medio": "m", "id": "1", "cos_sin": "0.5"}, {"medio": "m", "id": "2", "cos_sin": ""}]
    base = [{"medio": "m", "id": "1", "sin": "0.5002"}]
    assert hibrido.diferencia_de_control(filas, base) == pytest.approx(0.0002)
    assert hibrido.diferencia_de_control([], base) is None


def test_base_es_la_de_reranker():
    assert reranker.BASE == "minilm"
