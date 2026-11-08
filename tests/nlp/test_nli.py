import pytest

from radar.nlp import nli


@pytest.mark.parametrize(
    ("frase", "esperado"),
    [
        ("El Niño traerá lluvias intensas en Piura", True),
        ("Se espera que el caudal del río Tumbes aumente", True),
        ("El gobierno prepara un plan ante las lluvias que traerá El Niño", False),  # medida
        ("El Niño costero preocupa a los pescadores", False),  # sin pronóstico ni variable
    ],
)
def test_de_impacto(frase, esperado):
    assert nli.de_impacto(frase) is esperado


@pytest.mark.parametrize(
    ("frase", "esperado"),
    [
        ("Las lluvias estarían por encima de lo normal", {"encima"}),
        ("Las lluvias serían inferiores a lo normal", {"debajo"}),
        ("Se esperan lluvias normales", {"normal"}),
        ("Lluvias de normales a por encima de lo normal", {"encima", "normal"}),
        ("Habría déficit de lluvias", {"debajo"}),
        ("Lluvias intensas", set()),
    ],
)
def test_categorias(frase, esperado):
    assert nli.categorias(frase) == esperado


def test_simple():
    assert nli.simple("Lluvias por encima de lo normal en la costa norte") == ("lluvia", "norte", "encima")
    assert nli.simple("Lluvias por encima de lo normal en la costa norte y centro") == ("lluvia", "norte", "encima")
    assert nli.simple("Lluvias y caudales por encima de lo normal en la costa norte") is None
    assert nli.simple("Lluvias por encima de lo normal") is None  # sin región


def test_perturbar():
    assert nli.perturbar("Lluvias por encima de lo normal") == "Lluvias por debajo de lo normal"
    assert nli.perturbar("Caudales inferiores a lo normal") == "Caudales superiores a lo normal"
    assert nli.perturbar("Lluvias normales") is None
    assert nli.perturbar("Lluvias de normales a por encima de lo normal") is None


@pytest.mark.parametrize(
    ("contra", "implica", "tau", "esperado"),
    [(0.9, 0.1, 0.5, True), (0.9, 0.6, 0.5, False), (0.4, 0.1, 0.5, False), (0.5, 0.1, 0.5, False)],
)
def test_marca(contra, implica, tau, esperado):
    assert nli.marca(contra, implica, tau) is esperado


def test_elegir_tau():
    propia = [(0.7, 0.1)] * 2 + [(0.1, 0.9)] * 98  # con τ < 0,7 marca el 2 %
    igual = [(0.62, 0.1)] * 2 + [(0.1, 0.9)] * 8  # con τ < 0,62 marca el 20 %
    assert nli.elegir_tau({"propia": propia, "igual": igual}) == 0.65
    assert nli.elegir_tau({"propia": propia, "igual": []}) == 0.5
    assert nli.elegir_tau({"propia": [(0.99, 0.0)], "igual": []}) is None
    assert nli.elegir_tau({"propia": [], "igual": []}) is None


def _pares(prueba, mitad, etiqueta, n_marcadas, n):
    return [{"prueba": prueba, "mitad": mitad, "etiqueta": etiqueta, "contra": 0.9 if k < n_marcadas else 0.1,
             "implica": 0.1} for k in range(n)]  # fmt: skip


def test_criterios_cierra_con_pocos_casos():
    filas = (_pares("N1", "decide", "", 0, 50) + _pares("N2", "decide", "cambia", 5, 5)
             + _pares("N3", "decide", "cambia", 10, 10))  # fmt: skip
    salida = {c["criterio"]: c for c in nli.criterios(filas, 0.5, [(0.1, 0.9)] * 10, (0.1, 0.2))}
    assert salida["N2. Casos que cambian (julio-octubre)"]["pasa"] is False
    assert salida["N2. Detecta si la categoría cambia"]["pasa"] is False  # 5/5 no basta
    assert salida["N1. Frases propias marcadas (julio-octubre)"]["pasa"] is True


def test_criterios_sin_tau():
    salida = nli.criterios([], None, [], (0.1, 0.1))
    assert len(salida) == 1 and salida[0]["pasa"] is False


def test_suficientes():
    casos = [{"prueba": "N2", "mitad": "decide", "etiqueta": "cambia"}] * 19
    assert nli.suficientes(casos)["pasa"] is False
    assert nli.suficientes(casos + casos[:1])["pasa"] is True
