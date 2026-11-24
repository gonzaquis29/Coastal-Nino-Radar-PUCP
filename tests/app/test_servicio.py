"""Verificar, Preguntar y Panorama (radar.app.servicio) con datos sintéticos y sin modelos."""

import csv
import types

import pytest

from radar import config
from radar.agente import agente
from radar.app import servicio as s
from radar.app import textos as tx
from radar.nlp import discrepancia, semaforo

COMUNICADO = {"estado": "Alerta", "numero": 20, "fecha_texto": "13 de noviembre de 2026", "magnitud": "fuerte"}
ESTADO = {"comunicado": COMUNICADO, "avisos": [{"numero": 7, "titulo": "Lluvias", "nivel": "naranja"}]}
UMBRALES = {"lejano": 0.7, "cercano": 0.9, "con_color": True}


def comunicado(numero, fecha, magnitud):
    return {"id": f"enfen-2026-{numero}", "fecha_emision": fecha, "estado": "Alerta de El Niño costero",
            "tipo": "oficial", "magnitud_max_prevista": magnitud, "plazo": "hasta febrero", "url": "u",
            "proximo_anunciado": ""}  # fmt: skip


COMUNICADOS = {c["id"]: c for c in (comunicado(1, "2026-03-02", "débil"), comunicado(2, "2026-04-06", "fuerte"))}
HISTORIA = [{"id": "enfen-2026-1", "desde": "2026-03-02"}, {"id": "enfen-2026-2", "desde": "2026-04-06"}]


def escribir(ruta, columnas, filas):
    ruta.parent.mkdir(parents=True, exist_ok=True)
    with open(ruta, "w", encoding="utf-8", newline="") as archivo:
        escritor = csv.writer(archivo)
        escritor.writerow(columnas.split())
        escritor.writerows(filas)


# ---------------------------------------------------------------- utilidades

FECHAS = [
    ("fuerte:2026-04>2027-02", "la magnitud fuerte, de abril de 2026 a febrero de 2027"),
    ("débil:?>2026-07..2026-08", "la magnitud débil, hasta julio de 2026 a agosto de 2026"),
    ("débil:2026-07>?", "la magnitud débil, desde julio de 2026"),
]


@pytest.mark.parametrize(("celda", "esperado"), FECHAS)
def test_fecha_legible(celda, esperado):
    assert s.fecha_legible(celda) == esperado


def test_valor_legible_y_resaltado():
    assert s.valor_legible("estado", "no_activo") == "No activo"
    assert s.valor_legible("certeza", "x") == "lo afirma sin condicional"
    assert s.valor_legible("magnitud", "fuerte") == "fuerte"
    frase = "Será de magnitud fuerte en la costa"
    inicio, fin = s.resaltar(frase, "magnitud", "fuerte")
    assert frase[inicio:fin] == "fuerte"
    assert s.resaltar(frase, "magnitud", "débil") is None and s.resaltar(frase, "fecha", "fuerte") is None


# ---------------------------------------------------------------- Verificar


@pytest.fixture
def app(monkeypatch):
    """Un Servicio sin modelos: cada prueba fija lo que mide el semáforo."""
    a = object.__new__(s.Servicio)
    a.historia, a.comunicados = HISTORIA, COMUNICADOS
    a.parrafos = {"p1": {"id": "p1", "texto": "Texto oficial.", "doc_id": "enfen-2026-2"}}
    a.corpus = types.SimpleNamespace(avisos={"senamhi-7": {"url": "aviso"}}, parrafos=[])
    monkeypatch.setattr(a, "estado", lambda fecha, macroregion: ESTADO)
    monkeypatch.setattr(a, "que_hacer", lambda *args: {"interes": args[-1]})
    monkeypatch.setattr(a, "en_tema", lambda texto, largo: True)
    return a


def medir(monkeypatch, app, **r):
    base = {"palabras": 5, "parrafo": "p1", "umbrales": UMBRALES, "color_reglas": semaforo.SIN_AFIRMACIONES}
    monkeypatch.setattr(app, "medir", lambda texto, fecha: (base | r, (texto, "", "")))


def dato(categoria, anterior=None):
    oficial = {"comunicado": {}} | ({"anterior": {"id": anterior}} if anterior else {})
    return {"dato": "magnitud", "categoria": categoria, "oficial": oficial}


CON_DATOS = [
    ("verde", ["respaldada"], tx.COINCIDE, "respaldada"),
    ("amarillo", ["respaldada", "desactualizada"], tx.REVISAR, "desactualizada"),
    ("rojo", ["desactualizada", "contradice"], tx.NO_COINCIDE, "contradice"),
]


@pytest.mark.parametrize(("color", "categorias", "nivel", "titulo"), CON_DATOS)
def test_verificar_con_datos_titula_lo_mas_grave(monkeypatch, app, color, categorias, nivel, titulo):
    medir(monkeypatch, app, origen="reglas", color=color)
    datos = [dato(c, "enfen-2026-1" if c == "desactualizada" else None) for c in categorias]
    monkeypatch.setattr(app, "_afirmaciones", lambda *args: [{"frase": "f", "datos": datos}])
    r = app.verificar("texto", "2026-04-10", "lima")
    assert (r["tipo"], r["nivel"], r["titulo"]) == ("datos", nivel, tx.VEREDICTO_DATO[titulo][2])
    assert r["aviso"] == (tx.AVISO_NO_COINCIDE if color == "rojo" else None)
    assert [c["respaldo"] for c in r["linea_tiempo"]] == ([True, False] if "desactualizada" in categorias else [])
    assert r["oficial_cercano"]["comunicado"]["numero"] == 2 and r["que_hacer"]["interes"] == s.INTERES_POR_DEFECTO


def test_verificar_sin_datos_da_cercania_y_nunca_un_color(monkeypatch, app):
    medir(monkeypatch, app, origen="distancia", banda="cercano", color="verde", coseno=0.95)
    r = app.verificar("texto", "2026-04-10", "lima", "pesca")
    assert r["tipo"] == "cercania" and r["titulo"] == tx.SIN_DATO_TITULO and "color" not in r
    assert r["medidor"] == {"valor": 0.95, "media_desde": 0.7, "alta_desde": 0.9}
    assert r["que_hacer"]["interes"] == "pesca"


@pytest.mark.parametrize("origen", ["reglas", "distancia"])
def test_verificar_fuera_de_tema_no_da_veredicto(monkeypatch, app, origen):
    medir(monkeypatch, app, origen=origen, banda="cercano", color="verde", coseno=0.95)
    monkeypatch.setattr(app, "en_tema", lambda texto, largo: False)
    r = app.verificar("receta de cocina", "2026-04-10", "lima")
    assert (r["tipo"], r["nivel"], r["oficial_cercano"]) == ("fuera_de_tema", None, None) and "medidor" not in r


def test_verificar_texto_muy_corto(monkeypatch, app):
    medir(monkeypatch, app, origen="ninguno", parrafo=None)
    r = app.verificar("hola", "2026-04-10", "lima")
    assert r["tipo"] == "insuficiente" and r["titulo"] == tx.INSUFICIENTE


def test_medir_separa_titular_y_cuerpo():
    a = object.__new__(s.Servicio)
    a.semaforo = types.SimpleNamespace(medir=lambda texto, fecha, titular="": (texto, titular))
    largo = "palabra " * (semaforo.PALABRAS_CORTO + 1)
    assert a.medir("corto", "f") == (("", "corto"), ("corto", "", ""))
    assert a.medir(largo, "f") == ((largo, ""), ("", "", largo))


def test_afirmaciones_explican_cada_dato(monkeypatch, app):
    monkeypatch.setattr(s.af, "afirmaciones", lambda *args: [{"_texto": "Será débil."}, {"_texto": "Otra."}])
    filas = [{"dato": "magnitud", "valor": "débil", "categoria": "desactualizada", "atras": 1}]
    monkeypatch.setattr(discrepancia, "clasificar", lambda a, *args: filas if a["_texto"] == "Será débil." else [])
    (a,) = app._afirmaciones("t", "", "", "2026-04-10")
    (d,) = a["datos"]
    assert d["veredicto"] == tx.VEREDICTO_DATO["desactualizada"][2] and d["oficial"]["anterior"]["numero"] == 1
    assert d["oficial"]["dice"] == "magnitud máxima prevista para la costa: fuerte"


def test_frase_oficial_es_literal_y_prefiere_el_resumen(app):
    columnas = ("id", "doc_id", "seccion", "orden", "texto", "duplicado_de")
    filas = (
        ("a", "enfen-2026-2", "cuerpo", "1", "Cuerpo con magnitud fuerte.", ""),
        ("b", "enfen-2026-2", "resumen", "1", "El mar. Será fuerte.", ""),
        ("c", "enfen-2026-2", "titular", "1", "Titular débil.", "b"),
    )
    app.corpus.parrafos = [dict(zip(columnas, f, strict=True)) for f in filas]
    assert app._frase_oficial("enfen-2026-2", "fuerte") == {"cita": "Será fuerte.", "parrafo": "b"}
    assert app._frase_oficial("enfen-2026-2", "débil") is None and app._frase_oficial("enfen-2026-2", "") is None


def test_linea_de_tiempo_antes_del_primer_comunicado(app):
    assert app.linea_tiempo("2026-01-01") == []
    assert [c["vigente"] for c in app.linea_tiempo("2026-05-01")] == [False, True]


# ---------------------------------------------------------------- Preguntar

PARAMETROS = {"fecha": "2026-11-24", "macroregion": "lima", "interes": "pesca"}


def respuesta(app, herramienta, citas=(), **datos):
    return app.texto_de_respuesta({"herramienta": herramienta, "citas": list(citas), "datos": datos}, PARAMETROS)


def test_preguntar_estado(monkeypatch, app):
    texto = respuesta(app, "estado_vigente")
    assert "Alerta" in texto and "fuerte" in texto and "N.° 7, de lluvias, con nivel naranja" in texto
    monkeypatch.setattr(app, "estado", lambda *args: {"comunicado": COMUNICADO, "avisos": []})
    assert "No hay avisos del Senamhi" in respuesta(app, "estado_vigente")
    monkeypatch.setattr(app, "estado", lambda *args: {"comunicado": None, "avisos": []})
    assert respuesta(app, "estado_vigente") == "No hay un comunicado del ENFEN para el 24 de noviembre de 2026."


def test_preguntar_las_demas_herramientas(app):
    t = tx.PREGUNTAR
    assert respuesta(app, "buscar_oficial", ["c"]).startswith("Esto dicen")
    assert respuesta(app, "buscar_oficial").startswith("No hay textos")
    assert "pesca y mar" in respuesta(app, "recomendar") and "Lima y Callao" in respuesta(app, "recomendar")
    assert respuesta(app, "medir", ["c"], origen="reglas", color="rojo") == f"{t['medir_rojo']} {t['mas_cercano']}"
    assert "media" in respuesta(app, "medir", origen="distancia", banda="intermedio")
    assert respuesta(app, "medir") == t["medir_corto"]


def test_preguntar_arma_citas_con_su_enlace(monkeypatch, app):
    documentos = ("enfen-2026-2", "senamhi-7", "otro")
    citas = [{"cita": "x", "parrafo": "p", "fuente": "f", "documento": d} for d in documentos]
    r = {"herramienta": agente.FUERA, "texto": "fuera", "citas": citas, "parametros": PARAMETROS}
    monkeypatch.setattr(agente, "responder", lambda consulta, hoy, perfil: r)
    salida = app.preguntar("¿?", "2026-11-24", "lima")
    assert [c["url"] for c in salida["citas"]] == ["u", "aviso", None] and salida["texto"] == "fuera"
    assert salida["entendido"]["macroregion_texto"] == "Lima y Callao"


# ---------------------------------------------------------------- notas y Panorama

NOTAS = [
    ("1", "2026-04-07T10:00", "1"),
    ("2", "2026-04-08T10:00", "1"),
    ("3", "2026-05-08T10:00", "1"),
    ("4", "2026-05-08T10:00", "0"),
    ("5", "2025-12-31T10:00", "1"),
    ("6", "2026-05-09T10:00", "1"),
]
COLORES = [("1", "verde", ""), ("2", "amarillo", ""), ("3", "sin_afirmaciones", ""), ("6", "", "falló")]
DATOS = [
    ("1", "2026-04-07", "magnitud", "costa", "fuerte", "respaldada", "0"),
    ("2", "2026-04-08", "magnitud", "costa", "débil", "desactualizada", "1"),
    ("2", "2026-04-08", "magnitud", "pacifico", "fuerte", "respaldada", "0"),
    ("2", "2026-04-08", "magnitud", "costa", "fuerte", "otra_fuente", "0"),
]
CITAS = [
    ("medio", "rpp", "ENFEN", "10", "0.5"),
    ("medio", "andina", "ENFEN", "10", "0.5"),
    ("mes", "2026-04", "ENFEN", "10", "0.5"),
    ("medio", "rpp", "PCM", "10", "0.5"),
]


@pytest.fixture
def datos(monkeypatch, tmp_path):
    for nombre in ("NOTICIAS", "NLP", "ANALITICA", "RED"):
        monkeypatch.setattr(config, f"DIR_{nombre}", tmp_path / nombre)
    noticias, nlp = tmp_path / "NOTICIAS", tmp_path / "NLP"
    escribir(noticias / "notas.csv", "medio id fecha_publicacion sobre_nino url titular resumen",
             [("rpp", *n, "u", "T", "no sale") for n in NOTAS])  # fmt: skip
    regiones = [("1", "lima"), ("2", "costa_norte"), ("3", "lima")]
    escribir(noticias / "regiones.csv", "medio id macroregion_principal macroregiones",
             [("rpp", i, r, r) for i, r in regiones])  # fmt: skip
    escribir(nlp / "discrepancia-todas-notas.csv", "medio id color error", [("rpp", *c) for c in COLORES])
    escribir(nlp / "discrepancia-todas.csv", "medio id fecha dato escala valor categoria atras",
             [("rpp", *d) for d in DATOS])  # fmt: skip
    escribir(nlp / "topicos-nombres.csv", "topico categoria", [("0", "Pesca y mar"), ("1", "")])
    escribir(nlp / "topicos-notas.csv", "medio id topico", [("rpp", "1", "0"), ("rpp", "3", "1"), ("rpp", "9", "0")])
    escribir(tmp_path / "ANALITICA" / "eventos-por-comunicado.csv", "fecha proporcion_nino",
             [("2026-03-02", "0.6931472"), ("2026-04-06", "-0.5")])  # fmt: skip
    escribir(tmp_path / "RED" / "citas.csv", "grupo valor actor notas proporcion", CITAS)
    s.notas.cache_clear()
    yield s.Panorama(s.notas(), HISTORIA, COMUNICADOS)
    s.notas.cache_clear()


def test_notas_sin_campos_de_mas(datos):
    nota = s.notas()[("rpp", "1")]
    assert nota["color"] == "verde" and nota["macroregiones"] == {"lima"} and "resumen" not in nota
    assert s.notas()[("rpp", "6")]["color"] is None and s.notas()[("rpp", "6")]["macroregiones"] == set()


def test_panorama_linea_por_semana_y_filtros(datos):
    r = datos.linea()
    assert r["semanas"] == [
        {"semana": "2026-04-06", "coinciden": 1, "difieren": 1, "sin_datos": 0},
        {"semana": "2026-05-04", "coinciden": 0, "difieren": 0, "sin_datos": 1},
    ]
    assert [(c["desde"], c["hasta"]) for c in r["comunicados"]] == [("2026-03-02", "2026-04-06"), ("2026-04-06", None)]
    lima = datos.linea(hasta="2026-04-30", macroregion="lima")
    assert [(x["coinciden"], x["difieren"]) for x in lima["semanas"]] == [(1, 0)]
    assert [c["numero"] for c in datos.linea(desde="2026-05-01")["comunicados"]] == [2]


def test_panorama_magnitudes_solo_costa_y_categorias_comparables(datos):
    puntos = datos.magnitudes()["puntos"]
    assert [(p["magnitud"], p["grupo"]) for p in puntos] == [("fuerte", "respaldada"), ("débil", "desactualizada")]
    assert all(set(p) == {"fecha", "magnitud", "grupo"} for p in puntos)  # B, sin el medio (P12)


def test_panorama_temas_reaccion_y_citas(datos):
    meses = [(m["mes"], m["Pesca y mar"], m["Otros temas"]) for m in datos.temas()["meses"]]
    assert meses == [("2026-04", 1, 0), ("2026-05", 0, 1)]
    assert [(c["numero"], c["veces"]) for c in datos.reaccion()["comunicados"]] == [(1, 2.0), (2, 0.607)]
    citas = datos.citas()["medios"]
    assert [m["medio_texto"] for m in citas] == ["Andina", "RPP"] and "PCM" not in citas[1]


def test_panorama_hallazgos(datos):
    reaccion, coinciden, anteriores = datos.hallazgos()
    assert reaccion["valor"] == "1 de 2" and coinciden["valor"] == "50 %" and anteriores["valor"] == "1"
    assert "67 % de las 3 notas" in coinciden["texto"] and "1 comunicado atrás" in anteriores["texto"]
