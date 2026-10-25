"""Filtro por título, rasgos de las notas y lectura de HTML sintético (sin red; ninguna nota real)."""

import json

import pytest

from radar.noticias import filtro, rasgos
from radar.noticias.nota import NotaInvalida, decodificar, leer_api, leer_html

# ---------------------------------------------------------------- filtro


def test_palabras_exactas_sin_plurales():
    assert filtro.terminos_en("https://andina.pe/agencia/noticia-gobierno-alista-plan-ante-nino-1097190.aspx") == [
        "nino"
    ]
    assert filtro.terminos_en("https://rpp.pe/lima/actualidad/campana-para-ninos-noticia-1") == []
    assert filtro.terminos_en("https://eltiempo.pe/local/x/", "Fuertes lluvias en Piura") == ["lluvias"]


def test_ingles_de_andina():
    assert filtro.es_ingles(
        "https://andina.pe/agencia/noticia-peru-president-lands-in-tumbes-to-oversee-actions-1.aspx"
    )
    assert not filtro.es_ingles("https://andina.pe/agencia/noticia-presidenta-llega-a-tumbes-para-supervisar-1.aspx")


def test_candidatas_por_seccion(monkeypatch):
    monkeypatch.setitem(filtro.config.CANDIDATAS, "rpp", "secciones")
    assert filtro.candidata_por("rpp", "https://rpp.pe/politica/congreso/x-noticia-1") == "seccion"
    assert filtro.candidata_por("rpp", "https://rpp.pe/futbol/liga/x-noticia-2") == ""
    assert filtro.candidata_por("rpp", "https://rpp.pe/futbol/liga/lluvias-suspenden-partido-noticia-3") == "titulo"
    assert filtro.candidata_por("andina", "https://andina.pe/agencia/noticia-the-nino-is-in-the-news-4.aspx") == ""


# ---------------------------------------------------------------- rasgos


def test_menciones_de_el_nino_y_exclusiones():
    texto = "El Niño Costero sigue. El Hospital del Niño atendió a un niño. Según el ENFEN, el Fenómeno El Niño crece."
    assert rasgos.menciones(texto) == 3
    assert rasgos.menciones("El Instituto Nacional de Salud del Niño y el Día del Niño") == 0


def test_nino_en_inicio_mira_resumen_y_primer_parrafo():
    relleno = " ".join(["palabra"] * 80)
    assert rasgos.nino_en_inicio("Medidas ante El Niño", relleno)
    assert rasgos.nino_en_inicio("", "El Gobierno ante El Niño. " + relleno)
    assert not rasgos.nino_en_inicio("Sueldo mínimo", relleno + " también por El Niño")


def test_magnitudes_y_actores():
    texto = "El ENFEN prevé que El Niño Costero alcance magnitud fuerte a extraordinaria. Fuertes lluvias en Lima."
    assert rasgos.magnitudes(texto) == ["fuerte", "extraordinaria"]
    assert rasgos.actores("Según el ENFEN y el Senamhi, la PCM coordina.") == {"ENFEN": 1, "SENAMHI": 1, "PCM": 1}


@pytest.fixture
def comunicados(monkeypatch):
    filas = (
        {"id": "enfen-2026-09", "tipo": "oficial", "numero": "9", "anio": "2026", "fecha_emision": "2026-05-15",
         "proximo_anunciado": "2026-05-29", "slug": "comunicado-oficial-enfen-n-09-2026"},
        {"id": "enfen-2026-03", "tipo": "oficial", "numero": "3", "anio": "2026", "fecha_emision": "2026-02-13",
         "proximo_anunciado": "2026-02-27", "slug": "comunicado-oficial-enfen-n-03-2026"},
    )  # fmt: skip
    monkeypatch.setattr(rasgos, "_comunicados", lambda: filas)


def test_comunicado_por_enlace_numero_proximo_e_informe(comunicados):
    pdf = "https://enfen.imarpe.gob.pe/download/comunicado-oficial-enfen-n-09-2026/?wpdmdl=2053&refresh=x"
    informe = "https://enfen.imarpe.gob.pe/download/informe-tecnico-enfen-ano-12-n03-al-12-de-febrero-de2026/?wpdmdl=1"
    assert rasgos.comunicado_de_enlace(pdf) == ("enfen-2026-09", "enlace")
    assert rasgos.comunicado_de_enlace(informe) == ("enfen-2026-03", "informe")
    assert rasgos.comunicado_de_enlace("https://www.gob.pe/x.pdf") is None
    texto = (
        "Según el Comunicado Oficial N° 09-2026, … El próximo comunicado oficial será el viernes 27 de febrero de 2026."
    )
    assert rasgos.comunicados(texto, []) == ["enfen-2026-03:proximo", "enfen-2026-09:numero"]


# ---------------------------------------------------------------- lectura


def pagina(cuerpo, ld=None, charset="utf-8", metas=""):
    ld = ld or {
        "@type": "NewsArticle",
        "headline": "Lluvias &amp; El Niño",
        "datePublished": "2026-03-01T10:00:00-05:00",
    }
    return (
        f'<html><head><meta charset="{charset}"><meta name="description" content="Resumen de El Niño en la costa">'
        f'{metas}<script type="application/ld+json">{json.dumps(ld)}</script></head><body>{cuerpo}</body></html>'
    ).encode(charset)


def test_lee_html_con_fecha_enlaces_y_sin_compartir():
    cuerpo = (
        '<div class="col paddingnota">Lluvias & El Niño Texto de la costa con El Niño. '
        + "x " * 60
        + '<a href="https://enfen.imarpe.gob.pe/download/a/">pdf</a>'
        '<a href="http://www.facebook.com/sharer/sharer.php?u=1">f</a><script>no</script></div>'
    )
    campos = leer_html("andina", pagina(cuerpo), "https://andina.pe/agencia/noticia-x-1.aspx")
    assert campos["titular"] == "Lluvias & El Niño"
    assert campos["fecha_publicacion"] == "2026-03-01T10:00:00-05:00"
    assert campos["cuerpo"].startswith("Texto de la costa")  # sin el titular repetido
    assert campos["enlaces"] == ["https://enfen.imarpe.gob.pe/download/a/"]
    assert not campos["sin_texto"]


def test_charset_declarado_y_respaldo_del_articlebody():
    assert decodificar("Fenómeno".encode("iso-8859-1"), "text/html; charset=ISO-8859-1") == "Fenómeno"
    ld = {"@type": "NewsArticle", "headline": "T", "datePublished": "2026-03-01T10:00:00-05:00",
          "articleBody": "Cuerpo " * 60}  # fmt: skip
    campos = leer_html("rpp", pagina("<div>nada</div>", ld), "https://rpp.pe/capital/x-noticia-1")
    assert campos["n_palabras"] == 60 and campos["cuerpo_vs_ld"] == 1.0


def test_sin_fecha_no_es_nota():
    with pytest.raises(NotaInvalida):
        leer_html(
            "rpp", pagina("<div class='body'>x</div>", {"@type": "NewsArticle", "headline": "T"}), "https://rpp.pe/a"
        )


def test_lee_api_de_wordpress():
    entrada = {
        "id": 7,
        "link": "https://eltiempo.pe/local/rio-piura/",
        "date_gmt": "2026-10-24T17:00:55",
        "title": {"rendered": "Río Piura"},
        "excerpt": {"rendered": "<p>Limpieza del cauce</p>"},
        "content": {"rendered": "<p>Ante El Niño, " + "y " * 60 + '<a href="https://www.gob.pe/x">x</a></p>'},
    }
    campos = leer_api(entrada)
    assert campos["fecha_publicacion"] == "2026-10-24T12:00:55-05:00"
    assert campos["enlaces"] == ["https://www.gob.pe/x"] and campos["seccion"] == "local"
