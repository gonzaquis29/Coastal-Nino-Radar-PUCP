"""Pruebas sintéticas de la capa 5 (comparación con lo oficial): frases e historia inventadas."""

import pytest

from radar.nlp import discrepancia as d


@pytest.mark.parametrize(("nombre", "afirmacion", "fecha", "esperado"), d.CASOS, ids=[c[0] for c in d.CASOS])
def test_categorias_de_casos_conocidos(nombre, afirmacion, fecha, esperado):
    assert d._obtenido(afirmacion, fecha) == esperado


@pytest.mark.parametrize(("categorias", "esperado"), d.COLORES)
def test_color_de_la_nota(categorias, esperado):
    assert d.color([{"categoria": c} for c in categorias]) == esperado


def test_desactualizada_va_antes_que_otra_escala():
    historia = [
        d._ref(0, "2026-01-01", "alerta", ["débil"]),
        d._ref(1, "2026-02-01", "alerta", ["moderada"], ["débil"]),
    ]
    a = d._afirmacion(region="costa", magnitudes=["débil"])
    assert d._obtenido(a, "2026-02-10", historia) == [("magnitud", "desactualizada", False)]


def test_desactualizada_guarda_cuantos_comunicados_atras():
    filas = d.clasificar(d._afirmacion(estado="vigilancia"), "2026-03-25", d.HISTORIA_SINTETICA)
    assert [(f["categoria"], f["atras"]) for f in filas] == [("desactualizada", 3)]


def test_direccion_frente_a_la_maxima():
    filas = d.clasificar(d._afirmacion(magnitudes=["moderada", "extraordinaria"]), "2026-03-10", d.HISTORIA_SINTETICA)
    assert [f["sentido"] for f in filas] == ["menor", "mayor"]


def test_mas_certeza_solo_sin_cautela():
    def a(texto, modalidad):
        return d._afirmacion(texto, magnitudes=["fuerte"], modalidad=modalidad)

    assert d.mas_certeza(a("El Niño costero alcanzará magnitud fuerte.", "afirma"))
    assert not d.mas_certeza(a("El Niño costero alcanzaría magnitud fuerte.", "condicional"))
    assert not d.mas_certeza(a("El Niño costero se mantiene fuerte.", "afirma"))
    assert not d.mas_certeza(d._afirmacion("La economía crecerá.", modalidad="afirma"))


def test_central_de_frase_separa_las_dos_regiones():
    frase = "El Niño Costero sería extraordinario y en el Pacífico central sería de magnitud muy fuerte."
    assert d._central_de_frase(frase, "") == {"muy fuerte"}
    assert d._central_de_frase("El Niño en esta región tendría magnitud débil.", "nino_3.4") == {"débil"}
    assert d._central_de_frase("El Niño en esta región tendría magnitud débil.", "nino_1+2") == set()


def test_region_heredada_del_parrafo():
    texto = "En el Pacífico central se espera El Niño. En esta región sería débil. El Niño Costero sería moderado."
    assert [r for _, r in d._region_heredada(texto)] == ["central", "central", "costa"]


def test_reemplazar_magnitud_respeta_muy_fuerte():
    texto = "El Niño sería fuerte en la costa y muy fuerte en el Pacífico central."
    assert d._reemplazar_magnitud(texto, "fuerte", "débil") == (
        "El Niño sería débil en la costa y muy fuerte en el Pacífico central."
    )
