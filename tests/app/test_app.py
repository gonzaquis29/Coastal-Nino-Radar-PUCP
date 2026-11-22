"""Pruebas de la app sin modelos: textos (U2, U3, U6), registro de uso (P5), notas (P3) y rutas de la API."""

import json
import re

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from radar import config
from radar.app import api, eventos, legibilidad, servicio, validar
from radar.app import textos as tx

SESION = "abc123def456gh78"


def palabras(texto):
    return set(re.findall(r"[a-záéíóúüñ]+", texto.lower()))


def test_u2_sin_jerga_en_los_textos_del_ciudadano():
    textos = tx.textos_del_ciudadano() + list(tx.CERCANIA.values()) + list(tx.INTERESES.values())
    assert not [t for t in textos if palabras(t) & set(tx.JERGA)]


def test_u3_textos_bastante_faciles():
    assert {t: round(legibilidad.inflesz(t)) for t in tx.textos_del_ciudadano() if legibilidad.inflesz(t) < 65} == {}


def test_u6_sin_promesas_en_resultados_sin_datos():
    sin_datos = [tx.SIN_DATOS, tx.INSUFICIENTE, *tx.CERCANIA_FRASE.values(), *tx.CERCANIA.values()]
    assert not [t for t in sin_datos if palabras(t) & set(tx.PROMESAS)]


SILABAS = [("comunicado", 5), ("ríos", 2), ("huaicos", 2), ("que", 1), ("país", 2), ("aéreo", 4)]


@pytest.mark.parametrize(("palabra", "esperadas"), SILABAS)
def test_silabas(palabra, esperadas):
    assert legibilidad.silabas(palabra) == esperadas


def test_p5_el_registro_no_acepta_texto_libre():
    assert validar.campos_libres(eventos.Evento) == []
    lote = {"sesion": SESION, "dispositivo": "celular", "eventos": [{"evento": "verificar", "texto": "hola"}]}
    with pytest.raises(ValidationError):
        eventos.Lote(**lote)
    with pytest.raises(ValidationError):
        eventos.Lote(sesion="Juan.Perez@correo", dispositivo="celular", eventos=[])
    with pytest.raises(ValidationError):
        eventos.Evento(evento="vista", pantalla="otra")


def test_p3_nota_reciente_solo_con_campos_permitidos(monkeypatch):
    nota = {"medio": "rpp", "id": "1", "titular": "T", "fecha": "2026-11-14", "url": "u", "macroregion": "lima",
            "macroregiones": {"lima"}, "sobre_nino": True, "color": "verde", "resumen": "no debe salir"}  # fmt: skip
    monkeypatch.setattr(servicio, "notas", lambda: {("rpp", "1"): nota})
    s = object.__new__(servicio.Servicio)
    salida = s.nota_reciente("2026-11-15", "lima")
    assert set(salida) <= validar.CAMPOS_PERMITIDOS


def test_notas_en_y_citas_en():
    r = {"que_hacer": {"oficiales": [{"texto": "Se recomienda X.", "parrafo": "p1"}], "nota": {"titular": "T"}},
         "oficial_cercano": None, "afirmaciones": []}  # fmt: skip
    assert list(validar.notas_en(r)) == [{"titular": "T"}]
    assert validar.citas_en(r, {"p1": "Texto. Se recomienda X."}) == (1, 1)
    assert validar.citas_en(r, {"p1": "Otra cosa."}) == (0, 1)


class Falso:
    def estado(self, fecha, macroregion):
        return {"fecha": fecha, "macroregion": macroregion}

    def verificar(self, texto, fecha, macroregion, interes=None):
        return {"tipo": "insuficiente", "fecha": fecha, "interes": interes}


@pytest.fixture
def cliente(monkeypatch, tmp_path):
    monkeypatch.setattr(servicio, "servicio", lambda: Falso())
    monkeypatch.setattr(config, "DIR_APP", tmp_path)
    monkeypatch.setattr(api, "DIST", tmp_path / "dist")
    return TestClient(api.crear(cargar=False))


def test_rutas_y_validacion_de_entrada(cliente):
    assert cliente.post("/api/verificar", json={"texto": "x", "fecha": "2026-11-15"}).json()["fecha"] == "2026-11-15"
    assert cliente.post("/api/verificar", json={"texto": "x", "macroregion": "marte"}).status_code == 422
    assert cliente.post("/api/verificar", json={"texto": "x", "otro": 1}).status_code == 422
    assert cliente.get("/api/estado", params={"fecha": "15/11/2026"}).status_code == 422
    assert cliente.get("/api/no-existe").status_code == 404
    assert cliente.get("/panorama").status_code == 503  # sin web/dist construido


def test_eventos_se_guardan_sin_texto(cliente):
    verificar = {"evento": "verificar", "tipo_resultado": "datos", "resultado": "coincide", "palabras": 12}
    lote = {"sesion": SESION, "dispositivo": "escritorio",
            "eventos": [{"evento": "vista", "pantalla": "verificar"}, verificar]}  # fmt: skip
    assert cliente.post("/api/eventos", json=lote).status_code == 204
    filas = eventos.leer()
    assert [f["evento"] for f in filas] == ["vista", "verificar"]
    assert set(filas[0]) == set(eventos.COLUMNAS)


def test_interfaz_sirve_index_y_no_sale_de_dist(cliente, tmp_path):
    (tmp_path / "dist").mkdir()
    (tmp_path / "dist" / "index.html").write_text("<html>app</html>", encoding="utf-8")
    (tmp_path / "secreto.txt").write_text("no", encoding="utf-8")
    assert "app" in cliente.get("/verificar").text
    assert cliente.get("/../secreto.txt").text != "no"


# ---------------------------------------------------------------- Panorama F, Metodología, cabeceras y topes

PUNTOS = (
    "tipo,mes,coseno,objetivo,tasa\nmedio,2026-01,0.5,-4.9,0.010\nmedio,2026-03,0.6,-4.8,0.020\n"
    "oficial,2026-02,0.8,-5.0,0.004\notros,2026-03,0.4,-4.1,0.030\notros,2026-04,0.3,-4.0,0.050\n"
    "otros,2026-04,0.2,-4.0,0.070\n"
)
WEB = (
    "parte,indicador,grupo,valor,ic_inf,ic_sup,n\nA,respuesta,,sí,,,968\n"
    "A,rho_dentro_del_canal,,-0.1683,-0.2602,-0.0995,968\nA,rho_dentro_del_canal,prueba,-0.2619,,,\n"
)


@pytest.fixture
def datos_youtube(monkeypatch, tmp_path):
    (tmp_path / "youtube").mkdir()
    (tmp_path / "analitica").mkdir()
    (tmp_path / "youtube" / "2026-11-22_analitica-puntos.csv").write_text(PUNTOS, encoding="utf-8")
    (tmp_path / "analitica" / "web-engagement.csv").write_text(WEB, encoding="utf-8")
    monkeypatch.setattr(config, "DIR_YOUTUBE", tmp_path / "youtube")
    monkeypatch.setattr(config, "DIR_ANALITICA", tmp_path / "analitica")
    return tmp_path


def youtube(**filtros):
    return servicio.Panorama.youtube(object.__new__(servicio.Panorama), **filtros)


def test_f_youtube_indicadores_y_puntos_sin_ids(datos_youtube, monkeypatch):
    monkeypatch.setattr(servicio.almacen, "hoy", lambda: servicio.dt.date(2026, 11, 25))
    r = youtube()
    assert r["disponible"] and r["total"] == 6 and len(r["puntos"]) == 6
    assert {k for p in r["puntos"] for k in p} == {"tipo", "mes", "cercania", "tasa"}  # sin ids ni nombres
    # P12: el orden de los tipos es fijo (medio, oficial, otros), nunca por tasa
    assert [i["tipo"] for i in r["indicador_tasa"]] == ["medio", "oficial", "otros"]
    assert [i["mediana"] for i in r["indicador_tasa"]] == [pytest.approx(0.015), 0.004, 0.05]
    i2 = r["indicador_respuesta"]
    assert (i2["respuesta"], i2["rho"], i2["ic_inf"], i2["ic_sup"], i2["n"]) == ("sí", -0.1683, -0.2602, -0.0995, 968)
    assert i2["texto"] == tx.RESPUESTA_YOUTUBE["sí"] and not r["por_region"]


def test_f_youtube_filtra_por_mes_y_no_cambia_los_indicadores(datos_youtube, monkeypatch):
    monkeypatch.setattr(servicio.almacen, "hoy", lambda: servicio.dt.date(2026, 11, 25))
    r = youtube(desde="2026-03-01", hasta="2026-03-31", macroregion="lima")
    assert [p["mes"] for p in r["puntos"]] == ["2026-03", "2026-03"]
    assert r["indicador_tasa"] == youtube()["indicador_tasa"]


def test_f_youtube_vencido_queda_sin_datos(datos_youtube, monkeypatch):
    monkeypatch.setattr(servicio.almacen, "hoy", lambda: servicio.dt.date(2026, 12, 22))
    r = youtube()
    assert not r["disponible"] and r["puntos"] == [] and r["indicador_respuesta"] is None


def test_textos_de_youtube_sin_promesas_y_faciles():
    textos = [*tx.RESPUESTA_YOUTUBE.values(), tx.CERCANIA_ES_TEMA]
    assert not [t for t in textos if palabras(t) & set(tx.PROMESAS)]
    assert not [t for t in textos if palabras(t) & set(tx.JERGA)]
    assert {t: round(legibilidad.inflesz(t)) for t in textos if legibilidad.inflesz(t) < 65} == {}


def test_metodologia_lee_rutas_y_cuenta_criterios(monkeypatch, tmp_path):
    from radar.app import metodologia

    (tmp_path / "processed" / "red").mkdir(parents=True)
    (tmp_path / "processed" / "red" / "youtube-validacion.csv").write_text(
        "prueba,criterio,valor,umbral,pasa,detalle\nRed social de YouTube,R1,1,1,1,\nRed social de YouTube,R3,0,1,0,\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(config, "DIR_DATOS", tmp_path)
    monkeypatch.setattr(metodologia, "TARJETAS", (("red/youtube-validacion.csv", "Red social de YouTube", "Red", "x"),))
    assert (
        metodologia.ruta_de("red/youtube-validacion.csv") == tmp_path / "processed" / "red" / "youtube-validacion.csv"
    )
    [t] = metodologia.tarjetas()
    assert (t["pasa"], t["pasan"], t["total"]) == (False, 1, 2)


def test_cabeceras_de_seguridad(cliente):
    r = cliente.get("/api/salud")
    assert "default-src 'self'" in r.headers["content-security-policy"]
    assert r.headers["x-content-type-options"] == "nosniff" and r.headers["referrer-policy"] == "no-referrer"
    assert r.headers["cache-control"] == "no-store"
    assert "content-security-policy" not in cliente.get("/api/openapi.json").headers


def test_topes_del_registro(monkeypatch):
    topes = eventos.Topes()
    assert all(topes.permite(SESION, ahora=0) for _ in range(eventos.LOTES_POR_MINUTO_SESION))
    assert not topes.permite(SESION, ahora=1)
    assert topes.permite("otra000000000000", ahora=1)
    assert topes.permite(SESION, ahora=61)  # pasó un minuto


def test_registro_lleno_no_crece(cliente, monkeypatch):
    lote = {"sesion": SESION, "dispositivo": "celular", "eventos": [{"evento": "vista", "pantalla": "verificar"}]}
    monkeypatch.setattr(eventos, "BYTES_MAXIMOS", 1)
    assert cliente.post("/api/eventos", json=lote).status_code == 204
    assert cliente.post("/api/eventos", json=lote).status_code == 204
    assert len(eventos.leer()) == 1  # el primero crea el archivo; el segundo ya no entra


def test_seccion_youtube_en_la_ruta(cliente, datos_youtube, monkeypatch):
    monkeypatch.setattr(servicio, "panorama", lambda: object.__new__(servicio.Panorama))
    monkeypatch.setattr(servicio.almacen, "hoy", lambda: servicio.dt.date(2026, 11, 25))
    r = cliente.get("/api/panorama/youtube", params={"desde": "2026-04-01"})
    assert r.status_code == 200 and {p["mes"] for p in r.json()["puntos"]} == {"2026-04"}


def test_u2_u3_u6_en_los_textos_de_la_interfaz():
    interfaz = tx.textos_de_la_interfaz()
    assert not [t for t in interfaz if palabras(t) & set(tx.JERGA)]
    assert not [t for t in interfaz if palabras(t) & set(tx.PROMESAS)]
    ayudas = [tx.INTERFAZ[p][k] for p, k in tx.AYUDAS]
    assert {t: round(legibilidad.inflesz(t)) for t in ayudas if legibilidad.inflesz(t) < 65} == {}


def test_textos_de_la_interfaz_al_dia():
    """web/src/generado/textos.json es una copia exacta de radar.app.textos (python -m radar.app.textos)."""
    import json

    generado = config.DIR_WEB / "src" / "generado" / "textos.json"
    assert json.loads(generado.read_text(encoding="utf-8")) == json.loads(json.dumps(tx.para_la_interfaz()))


def test_validar_interfaz_junta_los_criterios_del_navegador(monkeypatch, tmp_path):
    from radar.app import metodologia
    from radar.app import validar_interfaz as v

    ids = ("P6", "P7", "P8", "P10", "P12", "U1", "U2", "U4", "U5", "U6")
    navegador = {i: {"valor": 0, "umbral": "0", "pasa": i != "U5", "detalle": "x"} for i in ids}
    (tmp_path / v.ARCHIVO_NAVEGADOR).write_text(json.dumps({"criterios": navegador}), encoding="utf-8")
    guardadas = []
    monkeypatch.setattr(v.config, "DIR_APP", tmp_path)
    monkeypatch.setattr(v, "p8_api_contra_csv", lambda: (3, []))
    monkeypatch.setattr(v, "guardar", lambda filas, ruta: guardadas.extend(filas))
    v.main()
    assert len(guardadas) == 12 and {f["prueba"] for f in guardadas} == {v.PRUEBA}
    assert [f["criterio"][:3] for f in guardadas if not f["pasa"]] == ["U5."]
    assert next(f for f in guardadas if f["criterio"].startswith("P8"))["valor"] == "3/3"
    assert any(t[1] == v.PRUEBA for t in metodologia.TARJETAS)
