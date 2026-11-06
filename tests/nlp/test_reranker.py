"""Pruebas sintéticas de la prueba C (sin cargar modelos)."""

import numpy as np

from radar import config
from radar.nlp import reranker, tfidf

NINO, OTROS = tfidf.ESTRATO_NINO, tfidf.ESTRATO_NEGATIVO


def nota(id_, sobre="1", medio="rpp", fecha="2026-05-02"):
    return {
        "medio": medio,
        "id": id_,
        "titular": f"T {id_}",
        "resumen": "R",
        "fecha_publicacion": fecha,
        "sobre_nino": sobre,
        "comunicados": "",
    }


def parrafo(id_, desde, hasta, tipo="pesca"):
    return {"id": id_, "texto": f"Texto {id_}", "vigente_desde": desde, "vigente_hasta": hasta, "tipo": tipo}


def test_candidatos_son_los_aprobados():
    assert set(config.CANDIDATOS_RERANKER) == {"mmarco", "bge", "mxbai", "qwen3"}


def test_texto_corto_omite_el_resumen_vacio():
    assert reranker.texto_corto({"titular": "T", "resumen": "R"}) == "T\nR"
    assert reranker.texto_corto({"titular": "T", "resumen": " "}) == "T"


def test_variantes_solo_las_que_usan_los_criterios():
    assert reranker.variantes_de(NINO, False) == ["sin"]
    assert reranker.variantes_de(NINO, True) == ["sin", "con"]
    assert reranker.variantes_de(OTROS, False) == ["sin", "con"]
    assert reranker.variantes_de("positivo", True) == ["con"]
    assert reranker.variantes_de("cercano", False) == []


def test_universo_marca_nuevas_y_excluye_errores_y_cercanas():
    notas = [nota("a"), nota("b"), nota("c"), nota("n"), nota("x", sobre="0"), nota("y", sobre="0")]
    control = [{"medio": "rpp", "id": "x", "estrato": OTROS}, {"medio": "rpp", "id": "y", "estrato": "cercano"}]
    bien = {"positivo": "0", "error": ""}
    lista_b = {
        ("rpp", "a"): {"positivo": "1", "error": ""},
        ("rpp", "b"): {"positivo": "0", "error": "sin texto"},
        ("rpp", "c"): bien,
        ("rpp", "x"): bien,
        ("rpp", "y"): bien,
    }
    salida = {n["id"]: (e, p, nueva) for n, e, p, nueva in reranker.universo(notas, control, lista_b)}
    assert salida == {
        "a": (NINO, True, False),
        "c": (NINO, False, False),
        "n": (NINO, False, True),
        "x": (OTROS, False, False),
    }


def test_pares_usan_la_misma_variante_en_los_dos_lados():
    pares = reranker.pares_de("El Niño costero sube", [{"texto": "El Niño costero baja"}], "sin")
    assert "Niño" not in pares[0][0] and "Niño" not in pares[0][1]
    assert reranker.pares_de("Hola", [{"texto": "Chau"}], "con") == [("Hola", "Chau")]


def test_fila_puntuada_no_guarda_texto_y_elige_el_mejor_vigente():
    parrafos = [
        parrafo("viejo", "2026-01-01", "2026-02-01"),
        parrafo("p1", "2026-05-01", "2026-05-14"),
        parrafo("p2", "2026-05-01", "2026-05-14"),
    ]

    def puntuar(texto, mascara, variante):
        assert list(mascara) == [False, True, True]
        return np.array([0.1, 0.9]), 0

    fila = reranker.fila_puntuada(nota("a"), NINO, False, False, puntuar, parrafos)
    assert fila["sin"] == 0.9 and fila["parrafo"] == "p2" and fila["pares"] == 2 and "con" not in fila
    assert not any("T a" in str(v) for v in fila.values())


def test_fila_sin_parrafos_vigentes_es_error():
    fila = reranker.fila_puntuada(nota("a"), NINO, False, False, None, [parrafo("v", "2020-01-01", "2020-02-01")])
    assert fila["error"] == "sin párrafos vigentes"


BASE = {"e4": (0.865, (0.845, 0.883)), "e3": (0.87, (0.78, 0.94)), "nuevas": (0.85, (0.8, 0.9))}


def medida(e4=0.90, bajo=0.885, e3=0.85, nuevas=0.86):
    return {"e4": (e4, (bajo, 0.92)), "e3": (e3, (0.8, 0.9)), "nuevas": (nuevas, (0.8, 0.9))}


def test_pasa_candidato_cada_regla():
    assert reranker.pasa_candidato(medida(), BASE)[0]
    assert not reranker.pasa_candidato(medida(e4=0.88), BASE)[0]  # menos de minilm + 0,02
    assert not reranker.pasa_candidato(medida(bajo=0.883), BASE)[0]  # IC solapado
    assert not reranker.pasa_candidato(medida(e3=0.79), BASE)[0]
    assert not reranker.pasa_candidato(medida(nuevas=0.85), BASE)[0]  # no supera en las nuevas


def test_elegir_el_mas_rapido_de_los_que_pasan():
    medidas = {"a": medida(), "b": medida(), "c": medida(e4=0.87)}
    assert reranker.elegir(medidas, BASE, {"a": 1.5, "b": 0.5, "c": 0.1}) == "b"
    assert reranker.elegir({"c": medida(e4=0.87)}, BASE, {"c": 0.1}) is None
    assert reranker.elegir({"a": medida()}, BASE, {}) is None  # no pasó el tiempo


def test_medidas_de_separa_nuevas_y_antiguas():
    casos = [
        (NINO, "False", 0.9),
        (NINO, "False", 0.8),
        (OTROS, "False", 0.1),
        (OTROS, "False", 0.2),
        (NINO, "True", 0.05),
    ]
    filas = [
        {"id": i, "estrato": e, "nueva": n, "positivo": "False", "sin": s, "con": "", "error": ""}
        for i, (e, n, s) in enumerate(casos)
    ]
    m = reranker.medidas_de(filas)
    assert m["e4"][0] == 1.0 and m["nuevas"][0] == 0.0
