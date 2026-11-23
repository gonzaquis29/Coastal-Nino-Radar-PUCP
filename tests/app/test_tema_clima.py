"""Clasificador de tema con clima y mar (docs/app/definicion.md, sección 12), con notas sintéticas."""

import numpy as np

from radar.app import tema, tema_clima
from radar.comun import dominio


def nota(id_, etiquetas="", sobre_nino="0", terminos_cuerpo="lluvia", titular="Titular", fecha="2026-03-01"):
    return {"medio": "andina", "id": id_, "sobre_nino": sobre_nino, "menciona_nino": sobre_nino,
            "terminos_cuerpo": terminos_cuerpo, "sin_texto": "0", "fecha_publicacion": f"{fecha}T00:00:00",
            "via": "", "muestra": "", "etiquetas": etiquetas, "titular": titular}  # fmt: skip


def test_etiquetas_completas_sin_tildes():
    assert dominio.etiquetada_clima_mar(nota("1", "Regionales, Lluvias Intensas, Piura"))
    assert dominio.etiquetada_clima_mar(nota("1", "Desborde de río"))
    assert not dominio.etiquetada_clima_mar(nota("1", "Mar, Pesca, Clima, Cambio climático"))  # otro sentido
    assert not dominio.etiquetada_clima_mar(nota("1", "lluvias de goles"))  # la etiqueta debe ser completa


def test_otro_tema_solo_si_no_hay_ninguna_de_clima():
    assert dominio.etiquetada_otro_tema(nota("1", "Política, Congreso"))
    assert not dominio.etiquetada_otro_tema(nota("1", "Política, Senamhi"))
    assert not dominio.etiquetada_otro_tema(nota("1", "Política, cambio climático"))
    assert not dominio.etiquetada_otro_tema(nota("1", "Salud, dengue"))  # pueden ser efectos del clima


def test_grupos_con_clima_y_duros():
    notas = [
        nota("1", "Lluvias", sobre_nino="1"),
        nota("2", "Senamhi"),
        nota("3", "Sismo"),
        nota("4", "Economía"),
        nota("5", "Deportes", terminos_cuerpo=""),
        nota("6", "Pesca", terminos_cuerpo=""),
        nota("7", "Senamhi"),
    ]
    g = tema_clima.grupos(notas, vistas={("andina", "7")})
    assert g[("andina", "1")] == tema_clima.TEMA
    assert g[("andina", "2")] == tema_clima.CLIMA
    assert g[("andina", "3")] == tema_clima.DURO
    assert ("andina", "4") not in g  # zona gris sin etiqueta de grupo
    assert g[("andina", "5")] == tema_clima.OTRO
    assert ("andina", "6") not in g  # otro tema con una etiqueta de clima con otro sentido
    assert ("andina", "7") not in g  # ya vista


def test_plantilla_cuenta_una_vez_los_pronosticos_diarios():
    a = nota("1", titular="SENAMHI: Pronóstico del clima hoy jueves 23 de julio 2026")
    b = nota("2", titular="SENAMHI: Pronóstico del clima hoy martes 07 de abril 2026")
    c = nota("3", titular="Huaico en Chosica")
    assert tema_clima.plantilla(a["titular"]) == tema_clima.plantilla(b["titular"])
    assert [n["id"] for n in tema_clima.una_por_plantilla([b, a, c])] == ["1", "3"]


def test_umbral_cumple_los_dos_topes():
    prob = np.r_[np.linspace(0, 0.5, 1000), np.linspace(0, 1, 100)]
    y = np.zeros(1100, dtype=int)
    duro = np.r_[np.zeros(1000, bool), np.ones(100, bool)]
    tau = tema_clima.umbral_de(prob, y, duro)
    assert (prob[~duro] >= tau).mean() <= tema_clima.MAX_OTROS_CV
    assert (prob[duro] >= tau).mean() <= tema_clima.MAX_DUROS_CV + 1e-9


def test_entrenamiento_hasta_agosto():
    assert tema_clima.en_entrenamiento(nota("1", fecha="2026-08-31"))
    assert not tema_clima.en_entrenamiento(nota("1", fecha="2026-09-01"))
    assert tema_clima.ULTIMO_DIA_ENTRENA[:7] == tema.ULTIMO_MES_ENTRENA


def test_sinteticos_completos():
    assert len(tema_clima.NINO_OTRO_SENTIDO) == len(tema_clima.FENOMENO_BIEN_ESCRITO) == 10
    assert len(tema_clima.DEL_TEMA_SIN_NINO) == 20 and len(tema_clima.OTRO_TEMA_CON_PALABRAS_DE_CLIMA) == 10
    assert not any(dominio.nombra_el_fenomeno(t) for t in tema_clima.NINO_OTRO_SENTIDO)
    assert all(dominio.nombra_el_fenomeno(t) for t in tema_clima.FENOMENO_BIEN_ESCRITO)
