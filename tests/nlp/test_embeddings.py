"""Pruebas sintéticas de los embeddings: textos inventados y un modelo de juguete (sin descargar modelos)."""

import numpy as np
import pytest

from radar.nlp import embeddings, esquemas

pytest.importorskip("sklearn")


class Tok:
    """Un token por palabra; con especiales, dos más."""

    def __call__(self, textos, add_special_tokens=True):
        extra = [0, 0] if add_special_tokens else []
        return {"input_ids": [[*extra, *range(len(t.split()))] for t in textos]}


class Motor:
    """Bolsa de palabras con hash: textos con las mismas palabras dan el mismo vector."""

    tok = Tok()

    def embeber(self, textos):
        salida = np.zeros((len(textos), 64), dtype=np.float32)
        for i, t in enumerate(textos):
            for palabra in t.lower().split():
                salida[i, sum(map(ord, palabra.strip(".,:;"))) % 64] += 1
        return salida / np.maximum(np.linalg.norm(salida, axis=1, keepdims=True), 1e-9)


def _modelo(largo=14):
    m = embeddings.Modelo("minilm", motor=Motor())
    m.largo, m.maximo = largo, largo - 2 - embeddings.MARGEN_TOKENS
    return m


def contar(textos):
    return [len(t.split()) for t in textos]


def test_tramos_juntan_lineas_sin_pasarse():
    texto = "uno dos tres\ncuatro cinco\nseis siete ocho nueve\ndiez"
    salida = embeddings.tramos(texto, contar, 6)
    assert salida == ["uno dos tres\ncuatro cinco", "seis siete ocho nueve\ndiez"]
    assert all(len(t.split()) + t.count("\n") <= 6 for t in salida)


def test_linea_larga_se_parte_por_oraciones_y_palabras():
    linea = "Primera oración corta. " + " ".join(f"p{i}" for i in range(15)) + "."
    salida = embeddings.tramos(linea, contar, 6)
    assert salida[0] == "Primera oración corta."
    assert all(len(t.split()) <= 6 for t in salida)
    assert " ".join(salida).split() == linea.split()  # no se pierde ni se repite nada


def test_sin_fenomeno_quita_los_terminos_de_t4():
    texto = "El Niño Costero sigue, según el ENFEN.\nLos niños del FEN y la costera; La Niña también."
    salida = embeddings.sin_fenomeno(texto)
    assert not embeddings.TERMINOS.search(salida) and "Niño" not in salida and "Niña" not in salida
    assert salida.count("\n") == 1 and "sigue" in salida  # se conservan las líneas y el resto


def test_corpus_suma_los_positivos_que_no_son_sobre_el_nino():
    notas = [
        {"medio": "andina", "id": "1", "sobre_nino": "1", "comunicados": "enfen-2026-01:numero"},
        {"medio": "andina", "id": "2", "sobre_nino": "0", "comunicados": "enfen-2026-02:enlace|enfen-2026-02:numero"},
        {"medio": "rpp", "id": "3", "sobre_nino": "0", "comunicados": "enfen-2026-03:numero"},  # no es de Andina
        {"medio": "andina", "id": "4", "sobre_nino": "0", "comunicados": ""},
    ]
    assert embeddings.positivas(notas) == {("andina", "1"): {"enfen-2026-01"}, ("andina", "2"): {"enfen-2026-02"}}
    assert [(n["id"], e) for n, e in embeddings.corpus(notas, [])] == [("1", "sobre_nino"), ("2", "positivo")]


def test_puntajes_eligen_el_parrafo_mas_parecido():
    m = _modelo()
    parrafos = [
        {"id": "p1", "doc_id": "enfen-2026-01", "texto": "lluvias intensas en la costa norte"},
        {"id": "p2", "doc_id": "enfen-2026-02", "texto": "pesca de anchoveta y temperatura del mar"},
    ]
    oficial = embeddings.Oficial(m, parrafos)
    fila, n, truncados, promedio = embeddings.puntajes(m, oficial, "pesca de anchoveta y temperatura del mar")
    assert fila["con_parrafo"] == "p2" and fila["con_max"] == pytest.approx(1.0) and truncados == 0
    assert n == 1 and promedio.shape == (64,) and set(fila) == set(esquemas.PUNTAJES)


def test_fila_guarda_puntajes_y_vector_pero_no_el_texto(tmp_path):
    m = _modelo()
    oficial = embeddings.Oficial(m, [{"id": "p1", "doc_id": "d1", "texto": "lluvias en la costa"}])
    cuerpo = "Las lluvias llegan a la costa de Piura."
    campos = {"titular": "Lluvias", "resumen": "", "cuerpo": cuerpo, "n_palabras": 8, "sin_texto": False}
    nota = {"medio": "rpp", "id": "1", "sha1_cuerpo": ""}
    ruta = tmp_path / "vectores.csv"
    fila = embeddings.fila_embeddings(nota, "sobre_nino", campos, {"minilm": m}, {"minilm": oficial}, set(), ruta)
    assert set(fila) <= set(esquemas.EMBEDDINGS) and not fila["error"]
    assert not any(isinstance(v, str) and "Piura" in v for v in fila.values())
    contenido = ruta.read_text(encoding="utf-8")
    assert "Piura" not in contenido and contenido.count("\n") == 2  # encabezado y un vector por modelo
    error = embeddings.fila_embeddings(nota, "sobre_nino", ValueError("sin JSON-LD"), {}, {}, set(), ruta)
    assert error["error"] and "minilm_con_max" not in error


def test_base64_ida_y_vuelta():
    v = np.linspace(-1, 1, 384).astype(np.float32)
    assert np.array_equal(embeddings.de_base64(embeddings.a_base64(v)), v)


def test_auc_con_intervalo():
    valor, (bajo, alto) = embeddings.auc(np.array([0.9, 0.8, 0.85, 0.7]), np.array([0.1, 0.2, 0.75, 0.3]))
    assert valor == pytest.approx(15 / 16) and bajo <= valor <= alto <= 1
    assert embeddings.auc(np.array([]), np.array([0.1])) == (None, (None, None))


def test_semaforo_detecta_el_cruce():
    def fila(estrato, positivo, v):
        return {"estrato": estrato, "positivo": positivo, "e5_con_max": str(v)}

    separadas = [fila("positivo", "1", v) for v in (0.9, 0.92, 0.95, 0.97)]
    separadas += [fila("otros_temas", "0", v) for v in (0.5, 0.6, 0.7, 0.8)]
    assert embeddings.semaforo(separadas, "e5", "cuerpos", embeddings.PRUEBA)["pasa"]
    cruzadas = [fila("positivo", "1", v) for v in (0.6, 0.61, 0.9, 0.95, 0.97, 0.98, 0.99, 0.99)]
    cruzadas += [fila("otros_temas", "0", v) for v in (0.1, 0.2, 0.3, 0.4, 0.5, 0.85, 0.86, 0.87)]
    resultado = embeddings.semaforo(cruzadas, "e5", "cuerpos", embeddings.PRUEBA)
    assert resultado["valor"] >= embeddings.AUC_SEMAFORO and not resultado["pasa"]  # p25 positivo ≤ p75 negativo


def test_elegir_prefiere_e5_en_empate():
    assert embeddings.elegir({"minilm": 0.85, "e5": 0.84}) == "e5"
    assert embeddings.elegir({"minilm": 0.88, "e5": 0.84}) == "minilm"
    assert embeddings.elegir({"minilm": 0.80, "e5": 0.91}) == "e5"
