"""Pruebas sintéticas de la comparación de candidatos (sin cargar modelos)."""

from types import SimpleNamespace

import numpy as np

from radar import config
from radar.nlp import candidatos, embeddings


def test_prefijos_fijados_antes_de_correr():
    assert candidatos.prefijos("e5-base") == ("query: ", "query: ")
    assert candidatos.prefijos("qwen3")[1] == "" and candidatos.prefijos("qwen3")[0].startswith("Instruct:")
    assert candidatos.prefijos("bge-m3") == ("", "")
    assert set(candidatos.PREFIJOS) <= set(config.CANDIDATOS_EMBEDDING)


class Tok:
    def __call__(self, texto, add_special_tokens=True):
        return {"input_ids": list(range(len(texto.split())))}

    def decode(self, ids):
        return " ".join(f"t{i}" for i in ids)


class Modelo:
    tokenizer = Tok()


def test_tramos_largos_tienen_el_largo_pedido():
    salida = candidatos.tramos_largos(Modelo(), ["uno dos tres"] * 20, n=3, tokens=10)
    assert len(salida) == 3 and all(len(t.split()) == 10 for t in salida)


def _medida(consulta=0.05, pico=2.0, tramos=4.0):
    return {"consulta_s": consulta, "primera_s": consulta, "pico_gb": pico, "tramos_por_s": tramos, "carga_s": 1,
            "parrafos_s": 1, "tokens_maximos": 512}  # fmt: skip


def test_criterio_a():
    assert candidatos.criterio_a("x", _medida())["pasa"]
    assert not candidatos.criterio_a("x", _medida(consulta=2.5))["pasa"]
    assert not candidatos.criterio_a("x", _medida(pico=7.0))["pasa"]
    horas = candidatos.TRAMOS_B / 4.0 / 3600
    assert f"~{horas:.1f} h" in candidatos.criterio_a("x", _medida())["detalle"]


# ---------------------------------------------------------------- B (un modelo falso de bolsa de palabras)
VOCABULARIO = ("lluvia", "pesca", "mar", "calor")


class TokPalabras:
    def __call__(self, textos, add_special_tokens=True):
        uno = isinstance(textos, str)
        ids = [[0] * (len(t.split()) + 2 * add_special_tokens) for t in ([textos] if uno else textos)]
        return {"input_ids": ids[0] if uno else ids}


class Bolsa:
    tokenizer, max_seq_length = TokPalabras(), 12

    def encode(self, textos, normalize_embeddings=True, batch_size=16):
        v = np.array([[t.split().count(p) for p in VOCABULARIO] for t in textos], dtype=float) + 1e-3
        return v / np.linalg.norm(v, axis=1, keepdims=True)


def _parrafo(i, doc, texto, desde, hasta="", tipo="pronostico"):
    return {"id": i, "doc_id": doc, "texto": texto, "vigente_desde": desde, "vigente_hasta": hasta, "tipo": tipo}


PARRAFOS = [
    _parrafo("p1", "enfen-2026-01", "lluvia lluvia mar", "2026-01-01", "2026-01-31"),
    _parrafo("p2", "enfen-2026-02", "pesca pesca mar", "2026-02-01", "2026-02-28"),
    _parrafo("p3", "enfen-2026-03", "calor", "2026-03-01", "", tipo="definicion"),
]


def test_candidato_descuenta_especiales_y_prefijo():
    c = candidatos.Candidato("minilm", Bolsa(), "query: ")
    assert c.maximo == 12 - 2 - 1 - embeddings.MARGEN_TOKENS


def test_vigentes():
    assert candidatos.vigentes(PARRAFOS, "2026-02-10").tolist() == [False, True, False]
    assert candidatos.vigentes(PARRAFOS, "2026-07-01").tolist() == [False, False, True]


def test_maximos_por_parrafo_sin_tramos_queda_en_menos_uno():
    oficial = SimpleNamespace(ids=["a", "b", "c"], por={"con": (np.eye(2), np.array([0, 1]), None, None)})
    salida = candidatos.maximos_por_parrafo(np.array([[0.6, 0.8]]), oficial, "con")
    assert np.allclose(salida, [0.6, 0.8, -1.0])


def test_puntajes_candidato_separa_todo_el_enfen_de_lo_vigente():
    modelo = candidatos.Candidato("minilm", Bolsa(), "")
    enfen = embeddings.Oficial(modelo, PARRAFOS)
    todo = embeddings.Oficial(modelo, [*PARRAFOS, _parrafo("x", "otro", "lluvia lluvia", "2026-01-01")])
    fila, tramos, truncados = candidatos.puntajes_candidato(
        modelo, enfen, todo, PARRAFOS, "lluvia lluvia", "2026-02-10"
    )
    assert fila["con_parrafo"] == "p1" and fila["vig_con_parrafo"] == "p2"
    assert fila["vig_con_max"] < fila["con_max"] <= fila["todo_con_max"]
    assert (tramos, truncados) == (1, 0)


def _fila(i, parrafo, estrato=candidatos.ESTRATO_NINO):
    return {"medio": "m", "id": str(i), "estrato": estrato, "x_con_parrafo": parrafo}


def test_vigencia_exacta_y_a_un_comunicado():
    filas = [_fila(1, "p1"), _fila(2, "p2"), _fila(3, "p3"), _fila(4, "p1", "otros")]
    notas = {("m", str(i)): {"fecha_publicacion": "2026-02-10T08:00"} for i in range(1, 5)}
    assert candidatos.vigencia(filas, "x", notas, PARRAFOS) == (round(1 / 3, 4), 1.0)


def test_concentracion():
    filas = [_fila(1, "p3"), _fila(2, "p3"), _fila(3, "p1"), _fila(4, "")]
    assert candidatos.concentracion(filas, "x", PARRAFOS) == (round(2 / 3, 4), round(2 / 3, 4))
    assert candidatos.concentracion([], "x", PARRAFOS) == (None, None)


def test_mcnemar():
    a = {i: True for i in range(10)}
    assert candidatos.mcnemar(a, {i: False for i in range(10)}) < 0.01
    assert candidatos.mcnemar(a, a) == 1.0


def _m(b1, b2, b3=True, ancho=0.01):
    return {"b1": (b1, (b1 - ancho, b1 + ancho)), "b2": (b2, (b2 - ancho, b2 + ancho)), "b3": b3}


def test_elegir_empate_lo_decide_la_rapidez():
    medidas = {
        "lento": _m(0.93, 0.90),
        "rapido": _m(0.92, 0.89),
        "malo": _m(0.85, 0.80),
        "falla": _m(0.99, 0.99, False),
    }
    elegido, empatados = candidatos.elegir(medidas, {"lento": 0.3, "rapido": 0.02, "malo": 0.01})
    assert elegido == "rapido" and set(empatados) == {"lento", "rapido"}


def test_elegir_reemplaza_solo_si_supera_en_b1_y_b2():
    medidas = {"lider": _m(0.95, 0.90), "otro": _m(0.90, 0.90)}  # supera en B1 pero no en B2: empatan
    assert candidatos.elegir(medidas, {"otro": 0.01, "lider": 0.1})[0] == "otro"
    assert candidatos.elegir({"a": _m(0.9, 0.9, False)}, {}) == (None, [])


def _todo():
    notas = [({"medio": "m", "id": str(i)}, "sobre_nino") for i in range(500)]
    notas += [({"medio": "m", "id": f"o{i}"}, "otros_temas") for i in range(400)]
    return notas + [({"medio": "m", "id": "c"}, "cercano")]


def test_muestra_por_estrato_y_repetible():
    claves = candidatos.clave_muestra(_todo(), n=50)
    assert claves == candidatos.clave_muestra(list(reversed(_todo())), n=50)
    assert sum(i.startswith("o") for _, i in claves) == 50 and len(claves) == 100
    assert ("m", "c") not in claves


def test_la_lectura_de_la_muestra_agrega_el_control_positivo():
    todo = _todo()
    fuera = next(k for k in (("m", str(i)) for i in range(500)) if k not in candidatos.clave_muestra(todo))
    claves = {(n["medio"], n["id"]) for n, _ in candidatos.de_la_muestra(todo, {fuera: {"x"}})}
    assert fuera in claves and len(claves) == len(candidatos.clave_muestra(todo)) + 1


def test_descartable_si_el_limite_no_llega_en_b1_o_en_b2():
    referencia = _m(0.91, 0.91)
    assert not candidatos.descartable(_m(0.93, 0.93), referencia)  # llega en las dos: hay que terminar la pasada
    assert candidatos.descartable(_m(0.89, 0.93), referencia)
    assert candidatos.descartable(_m(0.93, 0.89), referencia)
