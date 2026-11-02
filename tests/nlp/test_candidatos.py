"""Pruebas sintéticas de la comparación de candidatos (sin cargar modelos)."""

from radar import config
from radar.nlp import candidatos


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
