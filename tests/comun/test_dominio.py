"""Vocabulario del tema compartido por Preguntar y Verificar (docs/app/definicion.md, sección 9). Textos inventados."""

import pytest

from radar.comun import dominio


@pytest.mark.parametrize(
    "texto",
    ["Niño de 5 años fue rescatado en Lima", "Día del Niño: ideas de regalos", "Teletón: niños reciben ayuda",
     "Minería peruana: empleo femenino crece", "Sin Bandera llega a Costa 21", "Viaje barato a Costa Rica",
     "Mejoran la calidad del servicio de buses", "La selección peruana jugará el martes en Lima"],
)  # fmt: skip
def test_textos_de_otros_temas_no_pasan(texto):
    assert not dominio.en_texto(texto, largo=False)


@pytest.mark.parametrize(
    "texto",
    ["El ENFEN prevé un Niño costero débil", "Fenómeno El Niño: sigue la alerta", "el fenómeno del niño llega",
     "el niño costero será fuerte", "Lluvias intensas en Piura", "Oleaje anómalo en la Costa Verde",
     "Verano más cálido en la costa norte", "La anchoveta se aleja"],
)  # fmt: skip
def test_textos_del_tema_pasan(texto):
    assert dominio.en_texto(texto, largo=False)


def test_un_texto_largo_pide_dos_palabras_o_el_fenomeno():
    relleno = " ".join(["palabra"] * 120)
    assert not dominio.en_texto(f"{relleno} alerta", largo=True)
    assert dominio.en_texto(f"{relleno} alerta por lluvias", largo=True)
    assert dominio.en_texto(f"{relleno} El Niño", largo=True)


def test_en_una_pregunta_el_nino_en_minusculas_cuenta():
    assert dominio.en_pregunta("¿llegará el niño este verano?")
    assert dominio.en_pregunta("que dice el enfen")
    assert not dominio.en_pregunta("¿Quién ganó el clásico?")
    assert not dominio.en_pregunta("empleo femenino en la minería")
