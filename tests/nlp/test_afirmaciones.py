"""Pruebas sintéticas de la capa 3: frases inventadas, sin notas reales."""

import pytest

from radar.nlp import afirmaciones as a


@pytest.mark.parametrize(("texto", "fecha", "esperado"), a.CASOS_PLAZO)
def test_conversion_de_plazos_conocidos(texto, fecha, esperado):
    assert a.plazos(texto, fecha) == [esperado]


def test_plazo_sin_anio_toma_la_proxima_vez():
    assert a.plazos("se extendería hasta marzo", "2026-10-01") == ["2027-03"]
    assert a.plazos("se extendería hasta diciembre", "2026-10-01") == ["2026-12"]
    assert a.plazos("hasta el próximo año", "2026-10-01") == ["2027"]


def test_plazo_de_solo_anio_y_su_comparacion():
    assert a.plazos("El ENFEN mantiene la alerta hasta 2027", "2026-06-01") == ["2027"]
    assert a.mismo_plazo("2027", "2027-02") and a.mismo_plazo("2027-02", "2027")
    assert not a.mismo_plazo("2027", "2026-12") and not a.mismo_plazo("2027-03", "2027-02")


def test_plazo_solo_si_va_pegado_a_el_nino():
    assert a.plazos("El Niño traería lluvias intensas que podrían extenderse hasta marzo", "2026-08-01") == []
    assert a.plazos("El calor en la costa alcanzará récords hasta el 2027", "2026-08-01") == []
    assert a.plazos("Las lluvias llegarán, pero El Niño seguiría hasta marzo", "2026-08-01") == ["2027-03"]


@pytest.mark.parametrize(
    ("frase", "esperado"),
    [
        ("El Enfen descarta por ahora un Niño de magnitud muy fuerte.", True),
        ("Es prematuro afirmar un Niño muy fuerte.", True),
        ("El Niño no evolucionará a magnitud extraordinaria.", True),
        ("No se descarta un Niño extraordinario.", False),
        ("El Niño sería fuerte, sin descartar que sea extraordinario.", False),
        ("El Niño sería fuerte.", False),
    ],
)
def test_negada(frase, esperado):
    assert a.negada(frase) is esperado


def test_comunicado_pasado_es_historico():
    assert (
        a.momento("En su comunicado oficial de julio, el ENFEN indicó que El Niño seguiría.", "2026-09-26")
        == "historico"
    )
    texto = "En su comunicado extraordinario de enero de 2026, el ENFEN cambió el estado."
    assert a.momento(texto, "2026-09-08") == "historico"
    assert a.momento("En su comunicado de agosto, el ENFEN prevé un Niño fuerte.", "2026-09-08") == "actual"


@pytest.mark.parametrize(
    ("frase", "esperado"),
    [
        (
            "El ENFEN cambió el estado del sistema de alerta de «No Activo» a «Vigilancia de El Niño Costero».",
            "vigilancia",
        ),
        ("El ENFEN mantiene el estado de Alerta de El Niño Costero.", "alerta"),
        ("El Niño costero en alerta: así lo anunció el ENFEN.", "alerta"),
        ("El sistema de alerta ante El Niño Costero sigue en No Activo.", "no_activo"),
        ("Se declaró alerta roja ante El Niño en la región.", ""),
        ("Indeci emitió una alerta amarilla por lluvias ante El Niño.", ""),
        ("El estado del sistema de alerta ante El Niño se revisará mañana.", ""),
    ],
)
def test_estado(frase, esperado):
    assert a.estado(frase) == esperado


def test_probabilidad_solo_junto_a_el_nino():
    assert a.probabilidades("La probabilidad de El Niño fuerte es de 48 %.") == [48]
    assert a.probabilidades("La inflación subió 3 % por El Niño, según el BCR; la pesca cayó.") == []


@pytest.mark.parametrize(
    ("frase", "fuente", "pais"),
    [
        ("El ENFEN prevé que El Niño continúe.", "enfen", False),
        ("Según el Senamhi, El Niño traerá lluvias.", "oficial", False),
        ("La NOAA confirmó El Niño en el Pacífico.", "agencia", False),
        ("Un experto dijo que El Niño será fuerte.", "tercero", False),
        ("En Ecuador se teme a El Niño.", "tercero", True),
        ("El Niño será fuerte.", "sin", False),
    ],
)
def test_atribucion(frase, fuente, pais):
    assert a.atribucion(frase) == (fuente, pais)


def test_atribucion_pasa_a_la_frase_siguiente_del_parrafo():
    cuerpo = ("Según el ENFEN, el estado es de Alerta de El Niño Costero. El Niño sería fuerte hasta enero de 2027. "
              "El Niño traería lluvias moderadas.\nEl Niño sería débil, dijo otro.")  # fmt: skip
    afs = a.afirmaciones("Titular sin dato alguno aquí", "", cuerpo, "2026-08-01")
    fuentes = [(x["atribucion"], x["heredada"]) for x in afs]
    assert fuentes[0] == ("enfen", False) and fuentes[1] == ("enfen", True)
    assert all(f != ("enfen", True) for f in fuentes[2:])


@pytest.mark.parametrize(
    ("frase", "esperado"),
    [
        ("El Niño continuaría hasta el verano.", "condicional"),
        ("¿Llegará El Niño a Lima?", "pregunta"),
        ("El Niño ya está presente en la costa.", "afirma"),
        ("La categoría de El Niño es fuerte.", "afirma"),
        ("La declaratoria de emergencia por El Niño rige hoy.", "afirma"),
    ],
)
def test_modalidad(frase, esperado):
    assert a.modalidad(frase) == esperado


def test_momento_cita_y_explicativa():
    assert a.momento("El Niño de 1997-1998 fue extraordinario.", "2026-08-01") == "historico"
    assert a.momento("El Niño de 2026 sería fuerte, como en 1998.", "2026-08-01") == "actual"
    assert a.es_cita("El ENFEN dijo: «El Niño costero se mantendrá fuerte».")
    assert not a.es_cita("El ENFEN usa la palabra «fuerte».")
    assert a.explicativa("El Niño es un fenómeno de calentamiento del mar.")
    assert not a.explicativa("El Niño será fuerte.")


def test_region():
    assert a.region("El Niño costero sería fuerte.") == "costa"
    assert a.region("En el Pacífico central, El Niño sería muy fuerte.") == "central"
    assert a.region("El Niño sería fuerte.") == "ambigua"


def test_frases_y_subtitulos():
    lista = a.frases(
        "Titular de prueba con cinco palabras", "", "Subtítulo corto\nPrimera frase aquí. Segunda “frase.” Tercera."
    )
    assert [f for _, _, f, _ in lista][1:] == ["Subtítulo corto", "Primera frase aquí.", "Segunda “frase.”", "Tercera."]
    assert lista[1][3] and not lista[2][3]


def test_afirmacion_necesita_el_nino_y_un_dato():
    cuerpo = "El Niño costero sería fuerte hasta enero de 2027.\nLa pesca sería fuerte este año, sí."
    afs = a.afirmaciones("", "", cuerpo, "2026-08-01")
    assert len(afs) == 1 and afs[0]["magnitudes"] == ["fuerte"] and afs[0]["plazos"] == ["2027-01"]
    assert "_texto" not in a.a_fila("rpp", "1", afs[0])


def ref(estado, mags, plazos):
    return {"estado": estado, "magnitudes": set(mags), "plazos": set(plazos)}


def test_comparar_con_la_union_del_vigente_y_el_anterior():
    af = {"estado": "alerta", "magnitudes": ["fuerte", "fuerte"], "plazos": ["2027-03"]}
    salida = a.comparar(af, [ref("alerta", ["moderada"], ["2027-02"]), ref("alerta", ["fuerte"], ["2027-03"])])
    assert salida == [("estado", "alerta", True), ("magnitud", "fuerte", True), ("plazo", "2027-03", True)]
    assert a.comparar(af, [ref("vigilancia", [], [])])[0] == ("estado", "alerta", False)


def test_evaluable():
    base = {"atribucion": "enfen", "region": "costa", "momento": "actual", "explicativa": False, "modalidad": "afirma"}
    assert a.evaluable(base)
    assert not a.evaluable({**base, "region": "central"})
    assert not a.evaluable({**base, "atribucion": "tercero"})
    assert not a.evaluable({**base, "modalidad": "pregunta"})


def test_wilson():
    bajo, alto = a.wilson(90, 100)
    assert 0.82 < bajo < 0.84 and 0.94 < alto < 0.95


def test_muestra_toma_las_que_citan_y_30_por_medio(monkeypatch):
    monkeypatch.setattr(a, "POR_MEDIO", 2)
    notas = [{"medio": m, "id": str(i), "sobre_nino": "1", "comunicados": "enfen-2026-01:numero" if i == 0 else "",
              "actores": "ENFEN"} for m in ("andina", "rpp") for i in range(5)]  # fmt: skip
    elegidas = a.muestra(notas, {("rpp", "1")})
    claves = [(n["medio"], n["id"]) for n in elegidas]
    assert claves[:2] == [("andina", "0"), ("rpp", "0")] and len(claves) == 6 and ("rpp", "1") not in claves
