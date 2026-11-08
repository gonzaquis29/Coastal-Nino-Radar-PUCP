"""Pruebas sintéticas del semáforo (S1): bandas, combinación, tipo de texto, umbrales y muestras, sin modelo."""

import types

import pytest

from radar.nlp import semaforo as s


@pytest.mark.parametrize(("coseno", "esperado"), s.CASOS_BANDA)
def test_banda(coseno, esperado):
    assert s.banda(coseno, s.UMBRAL_SINTETICO) == esperado


@pytest.mark.parametrize(("reglas", "banda", "con_color", "esperado"), s.CASOS_COMBINACION)
def test_combinacion(reglas, banda, con_color, esperado):
    assert s.combinar(reglas, banda, con_color) == esperado


@pytest.mark.parametrize(("texto", "esperado"), s.CASOS_TIPO)
def test_tipo_de_texto(texto, esperado):
    assert s.tipo_de_texto(texto) == esperado


def test_lejos_nunca_es_rojo():
    assert {s.combinar(s.SIN_AFIRMACIONES, b)[0] for b in (s.CERCANO, s.INTERMEDIO, s.LEJANO)} == {
        "verde",
        "amarillo",
        "gris",
    }


def test_banda_sin_umbral():
    assert s.banda(0.9, None) is None


def test_criterio_logica_pasa():
    assert s.criterio_logica()["pasa"]


def test_umbrales_de_controles_separados():
    u = s.umbrales_de([0.8, 0.85, 0.9, 0.95], [0.001 * i for i in range(100)])
    assert u["con_color"] and u["auc"] == 1.0
    assert u["lejano"] < u["cercano"] < u["p25_positivo"]


def test_umbrales_de_controles_cruzados():
    assert not s.umbrales_de([0.1, 0.2, 0.3], [0.2, 0.3, 0.4, 0.5])["con_color"]


def test_umbrales_sin_controles():
    with pytest.raises(ValueError):
        s.umbrales_de([], [0.1])


def test_leer_umbrales(tmp_path):
    ruta = tmp_path / "u.csv"
    ruta.write_text("tipo,cercano,lejano,auc,auc_ic,p25_positivo,p75_negativo,positivos,negativos,con_color,fecha\n"
                    "corto,0.41,0.3,0.99,0.98-1.0,0.55,0.3,30,400,True,2026-11-07\n", encoding="utf-8")  # fmt: skip
    u = s.leer_umbrales(ruta)["corto"]
    assert u["cercano"] == 0.41 and u["con_color"] is True
    assert s.leer_umbrales(tmp_path / "no.csv") == {}


def _nota(medio, id_, **campos):
    base = {"medio": medio, "id": id_, "comunicados": "", "menciona_nino": "0", "sin_texto": "0",
            "terminos_cuerpo": "", "fecha_publicacion": "2026-03-01T10:00:00"}  # fmt: skip
    return base | campos


def test_positivo_limpio_quita_citas_sin_el_nino():
    notas = [
        _nota("andina", "1", comunicados="enfen-2026-01:numero", menciona_nino="1"),
        _nota("andina", "2", comunicados="enfen-2026-01:numero"),  # "Comunicado N.° 1" de otra entidad
        _nota("rpp", "3", comunicados="enfen-2026-01:numero", menciona_nino="1"),  # E3 solo usa Andina
    ]
    assert s.positivo_limpio(notas) == {("andina", "1")}


def test_negativos_elegibles_con_la_definicion_de_otros_temas():
    notas = [
        _nota("andina", "1"),
        _nota("andina", "2", menciona_nino="1"),
        _nota("andina", "3", terminos_cuerpo="lluvias"),
        _nota("andina", "4", sin_texto="1"),
        _nota("andina", "5"),  # vista
        _nota("andina", "6"),  # en el control negativo
    ]
    elegibles = s.negativos_elegibles(notas, {("andina", "5")}, [{"medio": "andina", "id": "6"}])
    assert [n["id"] for n in elegibles] == ["1"]


def _p(doc, texto="uno dos tres cuatro cinco", seccion="resumen", duplicado=""):
    return {"fuente": "enfen", "seccion": seccion, "duplicado_de": duplicado, "doc_id": doc, "texto": texto}


def test_resumenes_oficiales_frente_al_dia_anterior():
    corpus = types.SimpleNamespace(
        comunicados=[{"id": "c1", "fecha_emision": "2026-01-15"}, {"id": "c2", "fecha_emision": "2026-02-01"}],
        parrafos=[_p("c1"), _p("c2"), _p("c2", duplicado="x"), _p("c2", seccion="cuerpo"), _p("c2", texto="corto")],
    )
    assert s.resumenes_oficiales(corpus) == [("uno dos tres cuatro cinco", "2026-01-31")]


def test_reglas_mandan_detecta_un_color_cambiado():
    filas = [
        {"medio": "a", "id": "1", "error": "", "color_capa5": "rojo", "color": "rojo", "origen": "reglas"},
        {"medio": "a", "id": "2", "error": "", "color_capa5": s.SIN_AFIRMACIONES, "color": "gris",
         "origen": "distancia"},
    ]  # fmt: skip
    assert s.criterio_reglas_mandan(filas)["pasa"]
    filas[0]["color"] = "gris"
    assert not s.criterio_reglas_mandan(filas)["pasa"]
