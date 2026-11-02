"""Pruebas sintéticas de las pruebas de viabilidad de los modelos (sin modelos ni notas reales)."""

import numpy as np
import pytest

from radar import config
from radar.comun.archivos import escribir_csv
from radar.nlp import viabilidad as v


def _nota(medio, ident, sobre="1", comunicados="", actores=""):
    return {
        "medio": medio, "id": str(ident), "sobre_nino": sobre, "comunicados": comunicados, "actores": actores,
        "titular": f"Titular {medio} {ident}",
    }  # fmt: skip


@pytest.fixture
def notas():
    filas = [_nota(m, i) for m in ("andina", "rpp", "exitosa", "eltiempo") for i in range(40)]
    filas += [_nota("andina", 100, sobre="0"), _nota("rpp", 101, comunicados="enfen-2026-01:numero")]
    filas += [_nota("exitosa", 102, actores="ENFEN:1")]
    return filas


def test_disponibles_excluye_vistas_capa3_y_otros_temas(notas):
    libres = {(n["medio"], n["id"]) for n in v.disponibles(notas, {("andina", "0")})}
    assert ("andina", "0") not in libres
    assert ("andina", "100") not in libres  # no es sobre El Niño
    assert ("rpp", "101") not in libres and ("exitosa", "102") not in libres  # reservadas para la capa 3
    assert len(libres) == 159


def test_muestra_e2_nueva_reparte_por_medio_y_es_estable(notas):
    elegidas, nueva = v.muestra_e2(notas, set(), [])
    assert nueva and len(elegidas) == 4 * v.POR_MEDIO_E2
    assert {n["medio"] for n in elegidas} == {"andina", "rpp", "exitosa", "eltiempo"}
    assert elegidas == v.muestra_e2(notas, set(), [])[0]


def test_muestra_e2_registrada_reusa_las_mismas_notas(notas):
    anterior = [("rpp", "3"), ("andina", "7"), ("andina", "100")]
    elegidas, nueva = v.muestra_e2(notas, {("rpp", "3"), ("andina", "7")}, anterior)
    assert not nueva
    assert [(n["medio"], n["id"]) for n in elegidas] == anterior  # aunque ya estén vistas o hayan cambiado


def test_registrada_lee_solo_esa_muestra(tmp_path, monkeypatch):
    ruta = tmp_path / "vistas.csv"
    escribir_csv(
        ruta,
        ("medio", "id", "muestra"),
        [{"medio": "rpp", "id": "1", "muestra": "x"}, {"medio": "rpp", "id": "2", "muestra": "y"}],
    )
    monkeypatch.setattr(config, "ARCHIVO_NOTAS_VISTAS", ruta)
    assert v.registrada("x") == [("rpp", "1")]
    assert v.registrada("z") == []


def test_muestra_revision_toma_ambos_grupos(notas):
    salidas = [(n, "fear" if i % 7 == 0 else "others") for i, n in enumerate(notas)]
    elegidas, nueva = v.muestra_revision(salidas, [])
    assert nueva and len(elegidas) == 2 * v.POR_GRUPO_REVISION
    assert sum(e != "others" for _, e in elegidas) == v.POR_GRUPO_REVISION


def test_resumen_e2_cuenta_others_por_medio(notas):
    salidas = [(notas[0], "others", "NEU"), (notas[1], "joy", "POS"), (notas[40], "others", "NEG")]
    others, polaridad = v.resumen_e2(salidas)
    assert others["valor"] == 2 and others["umbral"] == 3
    assert "andina 1/2" in others["detalle"] and "rpp 1/1" in others["detalle"]
    assert polaridad["valor"] == {"NEU": 1, "POS": 1, "NEG": 1}


def test_criterio_d1():
    assert v.criterio_d1("x", {"pico_gb": 1.9, "estable_gb": 1.5, "parrafos": 865})["pasa"]
    assert not v.criterio_d1("x", {"pico_gb": 2.01, "estable_gb": 1.5, "parrafos": 865})["pasa"]


def test_pares_de_comunicados_distintos_y_frases_largas():
    parrafos = [
        {"doc_id": f"d{i % 3}", "texto": f"Frase corta {i}. Esta es una frase con bastantes palabras para servir {i}."}
        for i in range(12)
    ]
    lista = v.pares(parrafos, n=20, semilla="prueba")
    por_texto = {p["texto"]: p["doc_id"] for p in parrafos}
    assert len(lista) == 20
    for premisa, hipotesis in lista:
        assert len(hipotesis.split()) >= v.PALABRAS_MINIMAS_HIPOTESIS
        origen = next(p["doc_id"] for p in parrafos if hipotesis in p["texto"])
        assert origen != por_texto[premisa]
    assert lista == v.pares(parrafos, n=20, semilla="prueba")


def test_criterios_nli():
    a = np.array([[0.8, 0.1, 0.1], [0.2, 0.7, 0.1], [0.1, 0.2, 0.7], [0.5, 0.4, 0.1]])
    b = a.copy()
    b[3] = [0.4, 0.5, 0.1]  # cambia la etiqueta y |Δp| = 0,1
    iguales, rango = v.criterios_nli("p", a, b, 0.99, 0.05, 0.99)
    assert iguales["valor"] == 0.75 and not iguales["pasa"]
    assert rango["valor"] == 0.75 and not rango["pasa"]
    assert all(f["pasa"] for f in v.criterios_nli("p", a, a, 1.0, 0.001, 1.0))


def test_criterio_coseno():
    u = v._normalizar(np.array([[1.0, 0.0], [1.0, 1.0]]))
    w = v._normalizar(np.array([[1.0, 0.2], [1.0, 1.0]]))
    fila = v.criterio_coseno("p", "e5", u, w)
    assert fila["valor"] == pytest.approx(0.9806, abs=1e-4) and not fila["pasa"]
    assert v.criterio_coseno("p", "e5", u, u)["pasa"]


class _Entrada:
    def __init__(self, nombre):
        self.name = nombre


class _Sesion:
    """Sesión ONNX de mentira que exige token_type_ids y devuelve lo que recibió."""

    def __init__(self):
        self.feed = None

    def get_inputs(self):
        return [_Entrada("input_ids"), _Entrada("attention_mask"), _Entrada("token_type_ids")]

    def run(self, _, feed):
        self.feed = feed
        ids = feed["input_ids"]
        return [np.ones((*ids.shape, 4), dtype=np.float32) * ids[..., None]]


def _tok(textos, *_, **__):
    largo = max(len(t.split()) for t in textos)
    ids = np.array([[i + 1] * len(t.split()) + [0] * (largo - len(t.split())) for i, t in enumerate(textos)])
    return {"input_ids": ids, "attention_mask": (ids > 0).astype(np.int64)}


def test_onnx_agrega_token_type_ids_y_promedia_sin_relleno():
    sesion = _Sesion()
    modelo = v.Onnx("repo", "archivo", prefijo="query: ", sesion=sesion, tok=_tok)
    vectores = modelo.embeber(["a b", "c"])
    assert "token_type_ids" in sesion.feed and not sesion.feed["token_type_ids"].any()
    assert sesion.feed["input_ids"].dtype == np.int64
    assert np.allclose(np.linalg.norm(vectores, axis=1), 1.0)


def test_softmax_y_nombre_de_configuracion():
    p = v._softmax(np.array([[1.0, 2.0, 3.0]]))
    assert p.sum() == pytest.approx(1.0) and p.argmax() == 2
    assert v.nombre_configuracion("e5", "onnxq", None) == "e5 onnxq (solo embedding)"
    assert v.nombre_configuracion("minilm", "torch", "torch") == "minilm torch + NLI torch"
