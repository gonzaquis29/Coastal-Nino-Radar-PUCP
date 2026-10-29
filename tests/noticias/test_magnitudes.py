"""Regla de magnitud por cercanía (oficial.enfen.magnitudes_de_frase y rasgos.magnitudes), con frases sintéticas
fijadas antes de validar (docs/nlp/magnitud.md). Son una prueba de regresión: salen de los patrones del diseño."""

import pytest

from radar.noticias import rasgos
from radar.oficial import enfen

POSITIVAS = [
    ("El Niño costero de intensidad fuerte a muy fuerte.", ["fuerte", "muy fuerte"]),
    ("Existe un 62 % de probabilidad de un Niño Costero de fuerte intensidad.", ["fuerte"]),
    ("El Niño Costero débil pasará a magnitud moderada en julio.", ["débil", "moderada"]),
    ("El Niño tendría una magnitud entre fuerte (48 %) y moderada (46 %).", ["moderada", "fuerte"]),
    (
        "El Niño Costero persistiría con una magnitud extraordinaria de setiembre a enero, y entre fuerte y "
        "extraordinaria en febrero.",
        ["fuerte", "extraordinaria"],
    ),
    ("El Niño sería fuerte o extraordinario.", ["fuerte", "extraordinaria"]),
    ("El Niño continuará y el evento será moderado en junio.", ["moderada"]),
    ("Lambayeque se prepara ante un posible El Niño fuerte.", ["fuerte"]),
    ("Un fuerte fenómeno El Niño agravará las lluvias.", ["fuerte"]),
    ("El Niño entra en fase extraordinaria.", ["extraordinaria"]),
    ("Un Niño Costero de nivel extraordinario.", ["extraordinaria"]),
    ("Ante un posible Fenómeno de El Niño (FEN) extraordinario, el ministerio actúa.", ["extraordinaria"]),
    (
        'El ENFEN eleva la probabilidad de que El Niño llegue a magnitud "entre fuerte y extraordinaria".',
        ["fuerte", "extraordinaria"],
    ),
    ("El Niño Costero: a partir de abril, las condiciones cálidas débiles son las más probables.", ["débil"]),
    ("Aumenta la probabilidad de un evento El Niño históricamente fuerte.", ["fuerte"]),
    (
        "¿En qué se diferencian los eventos moderado, fuerte y muy fuerte del Niño?",
        ["moderada", "fuerte", "muy fuerte"],
    ),
    ("El Niño: si el evento 2026 es muy fuerte, habrá sequía.", ["muy fuerte"]),
    ("El ENFEN prevé que El Niño continúe. Su magnitud sería fuerte.", ["fuerte"]),
    ("El Niño de magnitud fuerte traerá lluvias fuertes.", ["fuerte"]),
    ("El Niño Costero sería moderado. En el Pacífico central sería fuerte.", ["moderada"]),
    ("El calentamiento global y El Niño de magnitud moderada preocupan.", ["moderada"]),
    # omisiones halladas en la validación (28-oct-2026), en frases propias
    ("Los organismos agrupan los eventos ENOS como débiles o fuertes, también a El Niño.", ["débil", "fuerte"]),
    (
        "Las condiciones de El Niño Costero llegarían a niveles entre fuerte y extraordinario.",
        ["fuerte", "extraordinaria"],
    ),
    ("Hoy vemos un evento El Niño de modo primero débil, ahora moderado.", ["débil", "moderada"]),
]
NEGATIVAS = [
    "Lluvias de fuerte intensidad son un adelanto del Fenómeno El Niño.",
    "Por El Niño no se descartan lluvias de moderada a fuerte intensidad.",
    "El Niño traerá precipitaciones de débil a moderada intensidad.",
    "Por El Niño, alerta por temperaturas de moderada a extrema intensidad.",
    "El Niño traerá fuertes lluvias.",
    "El fenómeno El Niño podría ser el más fuerte en décadas.",
    "El PBI cae por la fuerte caída de la pesca por El Niño.",
    "Indeci realizó un simulacro extraordinario ante El Niño.",
    "La débil infraestructura del norte ante El Niño preocupa.",
    "En el Pacífico central, El Niño sería muy fuerte.",
    "El Niño continuará. La inversión será fuerte.",
    "El Niño global sería fuerte.",
    "Nunca llegó un fenómeno El Niño tan fuerte como este.",
]


@pytest.mark.parametrize(("frase", "esperado"), POSITIVAS)
def test_magnitud_pegada_a_el_nino_o_a_su_grado(frase, esperado):
    assert rasgos.magnitudes(frase) == esperado


@pytest.mark.parametrize("frase", NEGATIVAS)
def test_no_es_magnitud_de_el_nino(frase):
    assert rasgos.magnitudes(frase) == []


@pytest.mark.parametrize(
    ("frase", "esperado"),
    [
        (
            "El Niño sería un evento de magnitud moderada, pudiendo alcanzar la magnitud fuerte.",
            [("moderada", False), ("fuerte", True)],
        ),
        (
            "El Niño sería débil, aunque no se descarta que alcance una intensidad moderada.",
            [("débil", False), ("moderada", True)],
        ),
    ],
)
def test_separa_lo_principal_de_lo_posible(frase, esperado):
    assert enfen.magnitudes_de_frase(frase) == esperado


def test_lineas_no_heredan_el_nino_entre_si():
    assert rasgos.magnitudes("El Niño continuará. La magnitud del evento sería fuerte.") == ["fuerte"]
    assert rasgos.magnitudes("El Niño continuará.\nLa magnitud del evento sería fuerte.") == []


def test_instrumento_cuenta_cada_criterio_y_excluye_el_diseno():
    from radar.noticias.validar_magnitud import frases_evaluables, medir, regla_anterior, regla_nueva

    cuerpo = "El Niño traerá lluvias de fuerte intensidad. Sería un evento moderado.\nOtra línea fuerte."
    frases = list(frases_evaluables(cuerpo, vistas=set()))
    assert frases == ["El Niño traerá lluvias de fuerte intensidad.", "Sería un evento moderado."]
    assert list(frases_evaluables(cuerpo, vistas={"el nino traera lluvias de fuerte intensidad"})) == frases[1:]
    nota = {"medio": "rpp", "id": "1"}
    casos = [(nota, frases[0], [("fuerte", "clima", True)]), (nota, frases[1], [("moderada", "evento", True)])]
    nueva, _ = medir(casos, regla_nueva)
    anterior, _ = medir(casos, regla_anterior)
    assert (nueva["clima"], nueva["aceptados"], nueva["rechazados"], nueva["directos"]) == (0, 1, 0, 1)
    assert (anterior["clima"], anterior["rechazados"]) == (1, 1)
