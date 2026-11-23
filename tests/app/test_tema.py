"""Clasificador de tema (docs/app/definicion.md, sección 10), con vectores sintéticos y sin el modelo real."""

import joblib
import numpy as np

from radar.app import tema


class ModeloFalso:
    """Vector de 2 dimensiones: [1, 0] si el texto dice «oleaje», [0, 1] si no."""

    def tramos(self, texto):
        return [texto]

    def embeber(self, textos):
        return np.array([[1.0, 0.0] if "oleaje" in t else [0.0, 1.0] for t in textos])


def test_inicio_corta_los_textos_largos():
    largo = " ".join(f"p{i}" for i in range(300))
    assert len(tema.inicio(largo).split()) == tema.semaforo.PALABRAS_CORTO
    assert tema.inicio("corto") == "corto"


def test_el_umbral_deja_pasar_a_lo_sumo_el_uno_por_ciento():
    negativos = np.linspace(0, 1, 1000)
    tau = tema.umbral_de(negativos)
    assert (negativos >= tau).mean() <= tema.MAX_PASAN_NEGATIVOS_CV + 1e-9


def test_clasificador_decide_con_el_vector_y_el_fenomeno_siempre_pasa(tmp_path):
    ruta = tmp_path / "m.joblib"
    joblib.dump({"coef": np.array([5.0, -5.0]), "intercepto": 0.0, "tau": 0.5}, ruta)
    k = tema.Clasificador(ruta, modelo=ModeloFalso())
    assert k.en_tema("hay oleaje fuerte")
    assert not k.en_tema("la selección jugará el martes")
    assert k.en_tema("El Niño costero llega")  # nombra el fenómeno: no depende del vector
    assert not k.en_tema("Niño de 5 años rescatado")


def test_las_etiquetas_dejan_fuera_la_zona_gris():
    notas = [
        {"medio": "andina", "id": "1", "sobre_nino": "1", "menciona_nino": "1", "terminos_cuerpo": "lluvia",
         "sin_texto": "0", "fecha_publicacion": "2026-03-01T00:00:00", "via": "", "muestra": ""},
        {"medio": "andina", "id": "2", "sobre_nino": "0", "menciona_nino": "0", "terminos_cuerpo": "lluvia",
         "sin_texto": "0", "fecha_publicacion": "2026-03-01T00:00:00", "via": "", "muestra": ""},
    ]  # fmt: skip
    g = tema.grupos(notas)
    assert g[("andina", "1")] == tema.TEMA and g[("andina", "2")] == tema.GRIS
