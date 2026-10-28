"""Instrumentos de la validación de la capa 1 (texto sintético; ninguna nota real)."""

from radar.noticias.validar_texto import Lectura, restos, uniones_de_la_extraccion


def lectura(cuerpo, original=""):
    return Lectura("rpp", {}, {"cuerpo": cuerpo}, "", "", original)


def test_uniones_no_cuentan_comillas_de_cierre_ni_lo_que_ya_pego_el_medio():
    assert uniones_de_la_extraccion(lectura('Dijo que "es un hecho."\nAgregó que sigue.')) == (0, 0)
    assert uniones_de_la_extraccion(lectura("Sigue hasta 2027.La Comisión indicó.")) == (1, 0)
    pegado_por_el_medio = "creadores de contenido.En el video difundido"
    assert uniones_de_la_extraccion(lectura(pegado_por_el_medio, original=pegado_por_el_medio)) == (0, 1)


def test_restos_son_frases_de_interfaz_no_palabras_de_la_redaccion():
    assert restos(lectura("El papa viene a compartir con los peruanos en los canales de YouTube.")) == []
    assert restos(lectura("En los versos finales del poema puede leerse su nombre.")) == []
    encontrados = restos(lectura("Compartir\n¡Mira RPP en YouTube! Noticias\n[Lea también: otra]"))
    assert sorted(encontrados) == ["Compartir", "Lea también", "Mira RPP en YouTube"]
