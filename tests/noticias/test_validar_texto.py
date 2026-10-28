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


def test_detector_de_enlaces_en_el_resumen_es_mas_amplio_que_el_corte():
    from radar.noticias.nota import ENLACE_EN_RESUMEN
    from radar.noticias.validar_texto import ENLACE_RESTANTE

    for texto in ("Puedes leer otra nota", "lee también esto", "► Otra"):
        assert ENLACE_RESTANTE.search(texto)
    assert not ENLACE_EN_RESUMEN.search("Puedes leer otra nota")  # sin "|", ":" ni "►": el corte no lo toca
    assert not ENLACE_RESTANTE.search("La historia puede leerse también en sus archivos.")


def test_cambio_de_sobre_el_nino_se_atribuye_al_resumen():
    from radar.noticias.validar_texto import validar_resumen

    cuerpo = "Un adolescente se ahogó en el río Chira. " * 10
    guardada = {"id": "1", "sobre_nino": "1", "resumen": "Se ahogó. PUEDES LEER ► El Niño Costero sería fuerte"}
    leida = {
        "titular": "Sullana: adolescente se ahoga",
        "resumen": "Se ahogó.",
        "cuerpo": cuerpo,
        "resumen_en_cuerpo": 1.0,
    }
    informativo = validar_resumen([(guardada, leida)])[-1]
    assert informativo["valor"] == 1 and "1→0 (resumen)" in informativo["detalle"]
