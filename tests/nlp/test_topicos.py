"""Pruebas sintéticas del punto 4 (sin cargar modelos de transformers)."""

import collections

import numpy as np
import pytest

from radar.nlp import topicos as t


def bolsas_de_dos_temas(n=30):
    pesca = collections.Counter({"pesca": 3, "anchoveta": 2, "mar": 2, "comun": 1})
    lluvia = collections.Counter({"lluvia": 3, "huaico": 2, "río": 2, "comun": 1})
    return [pesca if i % 2 == 0 else lluvia for i in range(n)]


def test_vocabulario_usa_el_corte_de_tfidf():
    bolsas = [{"a": 1, "b": 1}, {"a": 1, "b": 1}, {"a": 1, "c": 1}, {"a": 1, "b": 1}]
    assert t.vocabulario_de(bolsas) == ["b"]  # "a" está en todas (> 0,9) y "c" en una (< 3)


def test_ctfidf_separa_los_temas():
    bolsas = bolsas_de_dos_temas()
    vocab = t.vocabulario_de(bolsas + [{"x": 1}] * 10)
    x = t.matriz(bolsas, vocab)
    tops = t.palabras(x, [i % 2 for i in range(len(bolsas))], 2, vocab, top=3)
    assert set(tops[0]) == {"pesca", "anchoveta", "mar"} and set(tops[1]) == {"lluvia", "huaico", "río"}


def test_palabras_deja_vacio_el_topico_sin_notas():
    bolsas = bolsas_de_dos_temas(10)
    vocab = sorted({p for b in bolsas for p in b})
    assert t.palabras(t.matriz(bolsas, vocab), [0] * 10, 3, vocab)[1:] == [[], []]


def test_emparejado_ignora_el_orden_de_los_topicos():
    a = [["a", "b"], ["c", "d"]]
    assert t.emparejado(a, list(reversed(a))) == 1.0
    assert t.emparejado(a, [["a", "x"], ["y", "z"]]) == pytest.approx((1 / 3 + 0) / 2)


def test_estabilidad_promedia_los_pares_de_semillas():
    a, b = [["a", "b"]], [["a", "c"]]
    assert t.estabilidad([a, a, b]) == pytest.approx((1 + 1 / 3 + 1 / 3) / 3)


def test_elegir_por_cv_y_empate_a_menos_topicos():
    r = {("lda", 6): {"estable": 0.6, "cv": 0.500}, ("lda", 8): {"estable": 0.7, "cv": 0.505},
         ("bertopic", 10): {"estable": 0.4, "cv": 0.900}}  # fmt: skip
    assert t.elegir(r) == (("lda", 6), True)
    r[("lda", 8)]["cv"] = 0.52
    assert t.elegir(r) == (("lda", 8), True)


def test_elegir_sin_estables_toma_el_mas_estable_y_lo_declara():
    r = {("lda", 6): {"estable": 0.3, "cv": 0.6}, ("bertopic", 8): {"estable": 0.45, "cv": 0.4}}
    assert t.elegir(r) == (("bertopic", 8), False)


def test_coherencia_mayor_para_temas_coherentes():
    bolsas = bolsas_de_dos_temas()
    buena = t.coherencia([["pesca", "anchoveta", "mar"], ["lluvia", "huaico", "río"]], bolsas)
    mala = t.coherencia([["pesca", "huaico", "mar"], ["lluvia", "anchoveta", "río"]], bolsas)
    assert buena > mala


def test_categoria_pide_dos_palabras():
    assert t.categoria(["pesca", "anchoveta", "lima"]) == "Pesca y mar"
    assert t.categoria(["pesca", "lima", "gobierno"]) == ""


def test_diversidad():
    assert t.diversidad([["a", "b"], ["a", "c"]]) == 0.75


def test_promedio_y_etiqueta():
    p = t.promedio(
        [{"negativo": 0.6, "neutral": 0.3, "positivo": 0.1}, {"negativo": 0.2, "neutral": 0.7, "positivo": 0.1}]
    )
    assert p["neutral"] == pytest.approx(0.5) and t.etiqueta(p) == "neutral"
    assert t.promedio([]) == {} and t.etiqueta({}) == ""


def test_kappa_perfecto_y_al_azar():
    a = ["negativo", "neutral", "positivo"] * 4
    assert t.kappa(a, a) == 1.0
    assert t.kappa(a, ["neutral"] * 12) == 0.0


def nota(medio, id_, fecha):
    return {"medio": medio, "id": id_, "fecha_publicacion": fecha}


def test_agregados_corta_celdas_cruzadas_pequenas():
    notas = [nota("rpp", str(i), "2026-05-03" if i < 25 else "2026-06-01") for i in range(30)]
    regiones = [{"medio": "rpp", "id": str(i), "macroregion_principal": "costa_norte"} for i in range(30)]
    claves = [(n["medio"], n["id"]) for n in notas]
    filas = t.agregados(claves, [0] * 20 + [1] * 10, ["neutral"] * 30, notas, regiones, 2)
    celdas = {(f["dimension"], f["valor"]): f for f in filas}
    assert celdas[("mes", "2026-05")]["n"] == 25 and celdas[("mes", "2026-06")]["topico_1"] == 1.0
    assert ("mes_region", "2026-05|costa_norte") in celdas and ("mes_region", "2026-06|costa_norte") not in celdas
    assert celdas[("region", "costa_norte")]["pol_neutral"] == 1.0


def test_muestra_cien_por_medio_sin_vistas(monkeypatch):
    monkeypatch.setattr(t, "POR_MEDIO_P2", 2)
    notas = [{"medio": m, "id": str(i), "sobre_nino": "1", "comunicados": "", "actores": ""}
             for m in ("andina", "rpp") for i in range(5)]  # fmt: skip
    elegidas = t.muestra(notas, {("andina", "0")})
    assert collections.Counter(n["medio"] for n in elegidas) == {"andina": 2, "rpp": 2}
    assert ("andina", "0") not in {(n["medio"], n["id"]) for n in elegidas}
    assert elegidas == t.muestra(notas, {("andina", "0")})


def test_lda_y_bertopic_corren_en_datos_sinteticos():
    bolsas = bolsas_de_dos_temas(40)
    vocab = ["anchoveta", "huaico", "lluvia", "mar", "pesca", "río"]
    x = t.matriz(bolsas, vocab)
    asignacion = t.lda(x, 2, 0)
    assert len(set(asignacion[::2])) == 1 and len(set(asignacion[1::2])) == 1 and asignacion[0] != asignacion[1]
    rng = np.random.default_rng(0)
    vectores = np.vstack([np.eye(8)[i % 2] + rng.normal(0, 0.01, 8) for i in range(40)]).astype(np.float32)
    temas = t.bertopic(x, vectores, vocab, 2, 0)
    assert len(set(temas[::2])) == 1 and temas[0] != temas[1]
