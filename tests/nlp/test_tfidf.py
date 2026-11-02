"""Pruebas sintéticas del preprocesamiento y del TF-IDF (textos inventados, sin notas reales)."""

import collections

import pytest

from radar.nlp import esquemas, preproceso, tfidf

spacy = pytest.importorskip("spacy")
try:
    preproceso.modelo()
except OSError:
    pytest.skip("falta es_core_news_sm", allow_module_level=True)


def test_marcar_fenomeno_usa_la_regla_de_rasgos():
    texto, n = preproceso.marcar_fenomeno(
        "El Niño Costero y La Niña. El ENFEN habló. Hospital del Niño. laguna La Niña"
    )
    assert n == 2  # ni ENFEN (sigue como lema), ni el hospital, ni la laguna
    assert texto.count("xfenninox") == 1 and texto.count("xfenninax") == 1


def test_bolsa_separa_el_fenomeno_de_los_ninos():
    b = preproceso.bolsa(
        "Fenómeno El Niño: el ENFEN prevé lluvias. Los niños del Hospital del Niño. RPP informó 3 veces."
    )
    assert b[preproceso.EL_NINO] == 1 and b["niño"] == 2 and b["enfen"] == 1 and b["lluvia"] == 1
    assert not {"rpp", "3", "el", "los", "del"} & set(b)  # medios, números y stopwords fuera


def test_lema_sin_cliticos():
    assert "adelantar" in preproceso.bolsa("Las lluvias se adelantaron; adelantarse fue un error.")
    assert not any(" " in t for t in preproceso.bolsa("Hay que prepararse y protegerse."))


def test_celda_no_guarda_el_orden():
    # T3: dos textos con las mismas palabras en otro orden dejan la misma celda; no se puede reconstruir el texto
    a = preproceso.bolsa("Las lluvias intensas afectan Piura y Tumbes.")
    b = preproceso.bolsa("Tumbes y Piura: afectan las intensas lluvias.")
    assert preproceso.a_celda(a) == preproceso.a_celda(b)
    assert preproceso.de_celda(preproceso.a_celda(a)) == a
    assert not {"texto", "cuerpo", "titular", "resumen"} & set(esquemas.CONTEOS + esquemas.DOCUMENTOS)


def _nota(medio, ident, sobre="1", sha1=""):
    return {"medio": medio, "id": ident, "sobre_nino": sobre, "sha1_cuerpo": sha1}


def test_corpus_une_notas_y_control():
    notas = [_nota("rpp", "1"), _nota("rpp", "2", sobre="0"), _nota("rpp", "3", sobre="0")]
    control = [{"medio": "rpp", "id": "2", "estrato": "otros_temas"}, {"medio": "rpp", "id": "9", "estrato": "cercano"}]
    assert [(n["id"], e) for n, e in tfidf.corpus(notas, control)] == [("1", "sobre_nino"), ("2", "otros_temas")]


def test_texto_de_agrega_el_resumen_solo_si_no_esta_en_el_cuerpo():
    cuerpo = "Las lluvias intensas afectaron Piura durante toda la semana pasada."
    repetido = {"titular": "T", "resumen": "Lluvias intensas afectaron Piura", "cuerpo": cuerpo}
    nuevo = {"titular": "T", "resumen": "Gobierno declara emergencia regional", "cuerpo": cuerpo}
    assert tfidf.texto_de(repetido) == (f"T\n{cuerpo}", False)
    assert tfidf.texto_de(nuevo)[1]


def test_fila_conteo():
    from radar.comun.texto import sha1_corto

    cuerpo = "El Niño Costero traerá lluvias a Tumbes, según el ENFEN."
    campos = {"titular": "Alerta por El Niño", "resumen": "", "cuerpo": cuerpo, "n_palabras": 9, "sin_texto": False}
    fila = tfidf.fila_conteo(_nota("rpp", "1", sha1=sha1_corto(cuerpo)), "sobre_nino", campos)
    assert fila["sha1_igual"] and fila["menciones"] == fila["terminos_fenomeno"] == 2 and not fila["error"]
    assert "el_niño 2" in fila["lemas"] and "lluvia 1" in fila["lemas"]
    error = tfidf.fila_conteo(_nota("rpp", "2"), "sobre_nino", ValueError("sin JSON-LD"))
    assert error["error"] and "lemas" not in error


def _docs():
    """Notas sobre El Niño parecidas a los párrafos del ENFEN y negativas de otros temas."""
    tema = collections.Counter({"lluvia": 2, "anomalía": 1, "costa": 1, "mar": 1, preproceso.EL_NINO: 1})
    otros = collections.Counter({"fútbol": 2, "partido": 1, "gol": 1})
    docs = [
        (
            {"tipo": "oficial", "medio": "enfen", "id": f"p{i}", "estrato": ""},
            tema + collections.Counter({"pronóstico": i}),
        )
        for i in (1, 2, 3)
    ]
    docs += [
        (
            {"tipo": "nota", "medio": "rpp", "id": f"n{i}", "estrato": "sobre_nino"},
            tema + collections.Counter({"alerta": 1}),
        )
        for i in range(4)
    ]
    docs += [({"tipo": "nota", "medio": "rpp", "id": f"o{i}", "estrato": "otros_temas"}, otros) for i in range(4)]
    docs += [
        (
            {"tipo": "nota", "medio": "rpp", "id": "c", "estrato": "cercano"},
            collections.Counter({"lluvia": 1, "gol": 1}),
        )
    ]
    return docs


def test_matrices_y_auc(monkeypatch):
    monkeypatch.setattr(tfidf, "MAX_DF", 1.0)  # en 7 documentos de ajuste, "lluvia" está en todos
    docs = _docs()
    conteos, x, vocabulario, df = tfidf.matrices(docs)
    assert conteos.shape == x.shape == (len(docs), len(vocabulario))
    assert "lluvia" in vocabulario and "gol" not in vocabulario  # solo en negativas: fuera del ajuste
    assert tfidf.auc(x, docs, "otros_temas") == 1.0
    sin = tfidf._sin_terminos(x, vocabulario, {preproceso.EL_NINO})
    assert sin[:, vocabulario.index(preproceso.EL_NINO)].nnz == 0


def test_criterios_lectura():
    todo = [(_nota("rpp", str(i)), "sobre_nino") for i in range(4)]
    filas = [
        {"error": "", "sha1_igual": "1", "menciones": "2", "terminos_fenomeno": "2", "medio": "rpp"},
        {"error": "", "sha1_igual": "0", "menciones": "1", "terminos_fenomeno": "0", "medio": "rpp"},
        {"error": "HTTP 404", "sha1_igual": "", "menciones": "", "terminos_fenomeno": "", "medio": "rpp"},
    ]
    t1, sha1, t2 = tfidf.criterios_lectura(todo, filas)
    assert t1["valor"] == 0.5 and not t1["pasa"] and "sin leer 1" in t1["detalle"]
    assert sha1["valor"] == 0.5 and t2["valor"] == 0.5
