import pytest

from radar.agente import agente as ag
from radar.agente import herramientas as h


@pytest.mark.parametrize(
    ("texto", "esperada"),
    [
        ("¿Qué pasará el 15 de marzo?", "2026-03-15"),
        ("lluvias del 31 de diciembre", "2026-12-31"),  # sin año: dentro de los 60 días siguientes
        ("lluvias del 1 de febrero", "2026-02-01"),  # sin año: dentro de los 300 días anteriores
        ("¿y el 20 de diciembre?", "2026-12-20"),  # dentro de los 60 días siguientes
        ("el 3 de abril de 2026", "2026-04-03"),
        ("¿hay aviso hoy?", "2026-11-09"),
        ("¿y mañana?", "2026-11-10"),
        ("¿qué dice el ENFEN?", None),
    ],
)
def test_fecha_de(texto, esperada):
    assert ag.fecha_de(texto, "2026-11-09") == esperada


def test_macroregion_e_interes():
    assert ag.macroregion_de("lluvias en la costa norte") == "costa_norte"
    assert ag.macroregion_de("calor en Piura") == "costa_norte"
    assert ag.macroregion_de("en Lima") == "lima"
    assert ag.macroregion_de("en la costa norte y en Lima") is None
    assert ag.interes_de("soy pescador") == "pesca"
    assert ag.interes_de("me preocupan los huaicos") == "lluvias"
    assert ag.interes_de("nada") is None


def test_texto_a_contrastar():
    assert (
        ag.texto_a_contrastar('Verifica: "El Niño será extraordinario en 2027"')
        == "El Niño será extraordinario en 2027"
    )
    assert ag.texto_a_contrastar("¿Es cierto que El Niño terminó?") == "El Niño terminó"


class EnrutadorSinModelo(ag.Enrutador):
    def __init__(self):  # solo las reglas: el modelo no se carga
        pass


@pytest.mark.parametrize(
    ("consulta", "esperada"),
    [
        ("¿Cuál es el precio del dólar?", ag.FUERA),
        ("¿Es cierto que El Niño será extraordinario?", "medir_discrepancia"),
        ("El Niño costero traerá lluvias intensas a toda la costa norte desde enero", "medir_discrepancia"),
        ("¿Qué me recomiendan leer sobre el oleaje?", "recomendar"),
        ("Sugiéranme algo sobre los avisos de lluvia", "recomendar"),
        ("Muéstrame el último aviso del Senamhi para la costa sur del país", None),  # orden: no es afirmación
        ("¿Qué aconseja el Senamhi ante el calor?", None),  # fuente oficial que recomienda: no es recomendar
    ],
)
def test_reglas(consulta, esperada):
    if esperada is None:  # ninguna regla decide: pasa a los embeddings
        with pytest.raises(AttributeError):
            EnrutadorSinModelo().elegir(consulta)
    else:
        assert EnrutadorSinModelo().elegir(consulta)[0] == esperada


def test_cita_es_literal_y_corta_en_oracion():
    texto = "Primera oración. " * 30
    c = h.cita(texto)
    assert c in texto and len(c) <= h.LARGO_CITA and c.endswith(".")
    assert h.cita("corto") == "corto"
    respuesta = {"citas": [{"cita": "Primera oración.", "parrafo": "p1"}, {"cita": "otra", "parrafo": "p1"}]}
    assert h.citas_literales(respuesta, [{"id": "p1", "texto": texto}]) == (1, 2)


def test_casos_congelados_expande_valores():
    filas = [{"id": "X1", "herramienta": "estado_vigente", "aceptables": "", "interes": "",
              "texto": "¿Hay aviso en {region} el {dia}?"}]  # fmt: skip
    casos = ag.casos_congelados(filas)
    assert len(casos) == len(ag.VALORES_REGION) * len(ag.VALORES_DIA)
    assert casos[0]["esperado"] == {"macroregion": "costa_norte", "fecha": "2026-03-15", "interes": None}
    hoy = ag.casos_congelados([{**filas[0], "texto": "¿Qué avisos rigen hoy?"}])[0]
    assert ag.parametros_bien(hoy, {"fecha": hoy["hoy"], "macroregion": "x", "interes": "y"}) == [("fecha", True)]
