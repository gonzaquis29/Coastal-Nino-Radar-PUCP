"""Pruebas sintéticas de radar.youtube: sin red, sin clave y sin datos reales."""

import datetime as dt
import json
import logging

import pytest
from googleapiclient.errors import HttpError

from radar import config
from radar.youtube import almacen, api, borrar, canales, descarga, filtro, privacidad, viabilidad

SAL = b"sal-de-prueba-0123456789"


@pytest.fixture
def carpetas(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DIR_RAW_YOUTUBE", tmp_path / "raw")
    monkeypatch.setattr(config, "DIR_YOUTUBE", tmp_path / "processed")
    monkeypatch.setattr(config, "PAUSA_API", 0)
    monkeypatch.setattr(config, "ESPERA_BASE", 0)
    monkeypatch.setattr(privacidad, "_sal", lambda: SAL)
    return tmp_path


# ---------------------------------------------------------------- servicio falso


class _Respuesta:
    def __init__(self, estado):
        self.status, self.reason = estado, "x"


def error_http(estado, motivo):
    contenido = json.dumps({"error": {"errors": [{"reason": motivo}]}}).encode()
    return HttpError(_Respuesta(estado), contenido, uri="https://youtube.googleapis.com/v3/search?key=SECRETO&q=x")


class Peticion:
    """Anota la llamada al ejecutarse, como la API real (armar la petición no gasta cupo)."""

    def __init__(self, servicio, nombre, kw):
        self.servicio, self.nombre, self.kw = servicio, nombre, kw

    def execute(self, num_retries=0):
        self.servicio.llamadas.append((self.nombre, self.kw))
        respuesta = self.servicio.responder(self.nombre, self.kw)
        if isinstance(respuesta, Exception):
            raise respuesta
        return respuesta


class Recurso:
    def __init__(self, servicio, nombre):
        self.servicio, self.nombre = servicio, nombre

    def list(self, **kw):
        return Peticion(self.servicio, self.nombre, kw)


class Servicio:
    def __init__(self, videos=None, canales=None, hilos=None, errores=None):
        self.llamadas, self.videos_, self.canales_ = [], videos or {}, canales or {}
        self.hilos, self.errores = hilos or {}, errores or {}
        self.respuestas_ = {}

    def search(self):
        return Recurso(self, "search")

    def videos(self):
        return Recurso(self, "videos")

    def channels(self):
        return Recurso(self, "channels")

    def commentThreads(self):  # noqa: N802 (nombre de la API)
        return Recurso(self, "commentThreads")

    def comments(self):
        return Recurso(self, "comments")

    def responder(self, nombre, kw):
        if nombre in self.errores:
            return self.errores[nombre]
        if nombre == "search":
            mes = int(kw["publishedAfter"][5:7])
            return {"items": [{"id": {"videoId": f"v{mes}"}}]}
        if nombre in ("videos", "channels"):
            fuente = self.videos_ if nombre == "videos" else self.canales_
            return {"items": [fuente[i] for i in kw["id"].split(",") if i in fuente]}
        if nombre == "comments":
            return {"items": self.respuestas_.get(kw["parentId"], [])}
        paginas = self.hilos.get(kw["videoId"], [])
        n = int(kw.get("pageToken") or 0)
        return {"items": paginas[n] if n < len(paginas) else [],
                "nextPageToken": str(n + 1) if n + 1 < len(paginas) else None}  # fmt: skip


def item_video(vid, titulo, canal="c1", publicado="2026-03-10T15:00:00Z", comentarios="40"):
    return {"id": vid, "snippet": {"title": titulo, "description": "Más en https://ejemplo.pe/x", "channelId": canal,
            "publishedAt": publicado}, "statistics": {"viewCount": "100", "commentCount": comentarios}}  # fmt: skip


def hilo(i, autor):
    return {"id": f"hilo{i}", "snippet": {"totalReplyCount": 0, "topLevelComment": {"snippet": {
        "textOriginal": f"escríbeme a ana@correo.com o @ana_99 #{i}", "authorChannelId": {"value": autor},
        "authorDisplayName": "Ana Pérez", "publishedAt": "2026-03-11T00:00:00Z", "likeCount": 1}}}}  # fmt: skip


# ---------------------------------------------------------------- plan de búsquedas


def test_plan_del_dia1_son_100_busquedas_de_enero_a_octubre():
    plan = descarga.plan_dia1()
    assert len(plan) == 100 == config.BUSQUEDAS_POR_DIA
    assert {p["desde"].month for p in plan} == set(range(1, 11))
    assert plan[0]["desde"] == dt.date(2026, 1, 1) and max(p["hasta"] for p in plan) == dt.date(2026, 10, 31)


def test_plan_del_dia2_parte_solo_las_saturadas_por_fecha():
    previas = [
        {"termino": "ENFEN", "desde": "2026-02-01", "hasta": "2026-02-28", "orden": "date", "videos": ["x"] * 50},
        {"termino": "ENFEN", "desde": "2026-03-01", "hasta": "2026-03-31", "orden": "date", "videos": ["x"] * 49},
        {"termino": "ENFEN", "desde": "2026-04-01", "hasta": "2026-04-30", "orden": "relevance", "videos": ["x"] * 50},
    ]
    plan = descarga.plan_dia2(previas)
    assert [(p["desde"], p["hasta"]) for p in plan] == [
        (dt.date(2026, 2, 1), dt.date(2026, 2, 15)), (dt.date(2026, 2, 16), dt.date(2026, 2, 28))]  # fmt: skip


def test_plan_del_corte_es_noviembre_hasta_el_20():
    plan = descarga.plan_corte()
    assert len(plan) == 10 and all(p["hasta"] == config.FIN_CORTE for p in plan)


# ---------------------------------------------------------------- privacidad


def test_seudonimo_estable_y_dependiente_de_la_sal():
    a = privacidad.seudonimo("UCabc", SAL)
    assert a == privacidad.seudonimo("UCabc", SAL) != privacidad.seudonimo("UCabc", b"otra-sal-0123456789")
    assert len(a) == 16 and "UCabc" not in a and privacidad.seudonimo("", SAL) == ""


def test_limpiar_texto_quita_correos_menciones_enlaces_y_telefonos():
    limpio = privacidad.limpiar_texto("Escribe a ana@correo.com, @ana_99, https://x.pe/a o al 987 654 321")
    assert limpio == "Escribe a [correo], [mencion], [enlace] o al [telefono]"


def test_sin_sal_avisa(monkeypatch, tmp_path):
    monkeypatch.delenv(config.VARIABLE_SAL_YOUTUBE, raising=False)
    monkeypatch.setattr(config, "ARCHIVO_ENTORNO", tmp_path / "no-existe.env")
    privacidad._sal.cache_clear()
    with pytest.raises(privacidad.SinSal):
        privacidad.seudonimo("x")
    privacidad._sal.cache_clear()


def test_secretos_del_entorno_o_del_env(monkeypatch, tmp_path):
    from radar.comun import entorno

    archivo = tmp_path / ".env"
    archivo.write_text("# comentario\nYOUTUBE_API_KEY = 'de-archivo'\nOTRA=1\n", encoding="utf-8")
    monkeypatch.delenv("YOUTUBE_API_KEY", raising=False)
    assert entorno.valor("YOUTUBE_API_KEY", archivo) == "de-archivo"
    monkeypatch.setenv("YOUTUBE_API_KEY", "del-entorno")
    assert entorno.valor("YOUTUBE_API_KEY", archivo) == "del-entorno"
    assert entorno.valor("NO_ESTA", archivo) == ""


def test_registro_de_comentario_no_guarda_al_autor(carpetas):
    r = descarga.registro_comentario(hilo(1, "UCautor"), "v1")
    texto = json.dumps(r, ensure_ascii=False)
    assert "Ana Pérez" not in texto and "UCautor" not in texto and "hilo1" not in texto and "ana@" not in texto
    assert r["autor"] == privacidad.seudonimo("UCautor", SAL)


# ---------------------------------------------------------------- API


def test_la_clave_no_aparece_en_los_errores(carpetas):
    servicio = Servicio(errores={"search": error_http(400, "badRequest")})
    cliente = api.Api(servicio, api.Cupo(carpetas / "cupo.json"), dormir=lambda s: None)
    cliente._clave = "SECRETO"
    with pytest.raises(api.ErrorApi) as e:
        cliente.buscar("ENFEN", dt.date(2026, 1, 1), dt.date(2026, 1, 31), "date")
    assert "SECRETO" not in str(e.value) and "key=***" in str(e.value)


def test_el_ocultador_limpia_el_registro_de_la_biblioteca(caplog):
    api.silenciar_biblioteca()
    lg = logging.getLogger("googleapiclient.discovery")
    with caplog.at_level(logging.WARNING, logger="googleapiclient.discovery"):
        lg.warning("URL being requested: GET %s", "https://x/v3/videos?id=1&key=SECRETO")
    assert "SECRETO" not in caplog.text and "key=***" in caplog.text


def test_cupo_agotado_detiene_y_queda_anotado(carpetas):
    cupo = api.Cupo(carpetas / "cupo.json")
    servicio = Servicio(errores={"search": error_http(403, "quotaExceeded")})
    cliente = api.Api(servicio, cupo, dormir=lambda s: None)
    with pytest.raises(api.CupoAgotado):
        cliente.buscar("ENFEN", dt.date(2026, 1, 1), dt.date(2026, 1, 31), "date")
    assert cupo.busquedas_libres() == 0
    with pytest.raises(api.CupoAgotado):  # ya no llama a la API
        cliente.buscar("ENFEN", dt.date(2026, 1, 1), dt.date(2026, 1, 31), "date")
    assert len(servicio.llamadas) == 1


def test_dia_de_cupo_empieza_a_las_tres_de_lima():
    assert api.dia_de_cupo(dt.datetime(2026, 11, 17, 2, 59, tzinfo=config.LIMA)) == dt.date(2026, 11, 16)
    assert api.dia_de_cupo(dt.datetime(2026, 11, 17, 3, 0, tzinfo=config.LIMA)) == dt.date(2026, 11, 17)


def test_busqueda_usa_fechas_de_lima_y_el_dia_final_incluido(carpetas):
    servicio = Servicio()
    api.Api(servicio, api.Cupo(carpetas / "c.json"), dormir=lambda s: None).buscar(
        "ENFEN", dt.date(2026, 2, 1), dt.date(2026, 2, 28), "date")  # fmt: skip
    kw = servicio.llamadas[0][1]
    assert kw["publishedAfter"] == "2026-02-01T00:00:00-05:00"
    assert kw["publishedBefore"] == "2026-03-01T00:00:00-05:00"
    assert kw["regionCode"] == "PE" and kw["maxResults"] == 50


# ---------------------------------------------------------------- filtro


def test_filtro_exige_el_nino_y_peru():
    canal_pe = {"pais": "PE"}
    assert filtro.pasa({"titulo": "Fenómeno El Niño en Piura", "publicado": "2026-03-01T12:00:00Z"})
    assert filtro.pasa({"titulo": "El Niño costero se acerca", "publicado": "2026-03-01T12:00:00Z"}, canal_pe)
    assert not filtro.pasa({"titulo": "El Niño costero se acerca", "publicado": "2026-03-01T12:00:00Z"})
    assert not filtro.pasa({"titulo": "Hospital del Niño en Lima", "publicado": "2026-03-01T12:00:00Z"})
    assert not filtro.pasa({"titulo": "El Niño en Perú", "publicado": "2025-12-31T12:00:00Z"})
    assert filtro.pasa({"titulo": "El Niño en Perú", "publicado": "2026-01-01T03:00:00Z"}) is False  # 31-dic en Lima


# ---------------------------------------------------------------- almacén y borrado


def test_leer_se_niega_con_datos_vencidos_y_borrar_los_quita(carpetas):
    viejo = dt.date(2026, 10, 1)
    almacen.anexar("videos", [{"id": "v1"}], fecha=viejo)
    almacen.anexar("videos", [{"id": "v2"}], fecha=dt.date(2026, 10, 20))
    with pytest.raises(almacen.Vencido):
        list(almacen.leer("videos", en=dt.date(2026, 10, 31)))
    borrados = borrar.borrar(en=dt.date(2026, 10, 31))
    assert [r.name for r in borrados] == ["2026-10-01_videos.jsonl"]
    assert [r["id"] for r in almacen.leer("videos", en=dt.date(2026, 10, 31))] == ["v2"]


def test_borrar_simulado_no_borra(carpetas):
    almacen.anexar("videos", [{"id": "v1"}], fecha=dt.date(2026, 1, 1))
    assert len(borrar.borrar(simular=True)) == 1 and almacen.archivos()


# ---------------------------------------------------------------- etapa completa con el servicio falso


def test_dia1_busca_descarga_y_guarda_comentarios_seudonimizados(carpetas):
    videos = {f"v{m}": item_video(f"v{m}", "Fenómeno El Niño en Piura", publicado=f"2026-{m:02d}-10T15:00:00Z")
              for m in range(1, 11)}  # fmt: skip
    canales_api = {"c1": {"id": "c1", "snippet": {"title": "Canal", "country": "PE"},
                          "statistics": {"hiddenSubscriberCount": True}}}  # fmt: skip
    hilos = {"v3": [[hilo(i, f"UC{i % 3}") for i in range(100)], [hilo(100 + i, "UCx") for i in range(5)]]}
    servicio = Servicio(videos, canales_api, hilos)
    cliente = api.Api(servicio, api.Cupo(carpetas / "cupo.json"), dormir=lambda s: None)
    assert descarga.correr("dia1", cliente)
    assert sum(n == "search" for n, _ in servicio.llamadas) == 100
    assert len(almacen.ultimos("videos")) == 10
    assert almacen.ultimos("canales")["c1"]["suscriptores"] is None
    comentarios = list(almacen.leer("comentarios"))
    assert len(comentarios) == 100  # el día 1 baja solo la primera página
    assert len({c["autor"] for c in comentarios}) == 3
    # volver a correr no repite nada
    antes = len(servicio.llamadas)
    assert descarga.correr("dia1", cliente)
    assert len(servicio.llamadas) == antes


def test_corte_baja_mas_paginas_y_respeta_el_tope_de_cupo(carpetas, monkeypatch):
    videos = {"v11": item_video("v11", "Fenómeno El Niño en Tumbes", publicado="2026-11-05T15:00:00Z")}
    canales_api = {"c1": {"id": "c1", "snippet": {"title": "Canal"}, "statistics": {"subscriberCount": "10"}}}
    hilos = {"v11": [[hilo(p * 10 + i, "UCa") for i in range(10)] for p in range(12)]}
    servicio = Servicio(videos, canales_api, hilos)
    cliente = api.Api(servicio, api.Cupo(carpetas / "cupo.json"), dormir=lambda s: None)
    assert descarga.correr("corte", cliente)
    assert sum(n == "commentThreads" for n, _ in servicio.llamadas) == descarga.PAGINAS_MAXIMAS
    monkeypatch.setattr(config, "CUPO_POR_DIA", config.MARGEN_CUPO)  # sin unidades libres
    assert api.Cupo(carpetas / "otro.json").unidades_libres() == 0


def test_comentarios_desactivados_no_detienen_la_etapa(carpetas):
    videos = {"v3": item_video("v3", "El Niño en Piura", publicado="2026-03-10T15:00:00Z")}
    servicio = Servicio(videos, {}, errores={"commentThreads": error_http(403, "commentsDisabled")})
    cliente = api.Api(servicio, api.Cupo(carpetas / "cupo.json"), dormir=lambda s: None)
    assert descarga.correr("dia1", cliente)
    assert list(almacen.leer("comentarios")) == []


# ---------------------------------------------------------------- tipo de canal


class ClienteFalso:
    def __init__(self, paginas, robots=None):
        self.paginas, self.pedidas, self.robots_ = paginas, [], robots or {}
        self.robots = {}

    def get(self, url):
        self.pedidas.append(url)
        host = url.split("/")[2]
        self.robots[host] = ([], self.robots_.get(host, []))
        if self.paginas.get(url) is None:
            raise OSError("no se pudo")
        return type("R", (), {"text": self.paginas[url]})()


def paginas_de(canales_lista, cliente):
    paginas = {}
    for host, urls in canales.por_host(u for c in canales_lista for u in canales.sitios(c)).items():
        paginas.update({r["id"]: r for r in canales.leer_host(host, urls, cliente)})
    return paginas


def test_tipo_de_canal_por_enlaces_verificables():
    oficial = {"id": "UCofi", "custom_url": "@senamhi", "enlaces": ["https://www.gob.pe/senamhi", "https://fb.com/x"]}
    medio = {"id": "UCmed", "custom_url": "@diario", "enlaces": ["https://diario.pe/seccion"]}
    blog = {"id": "UCblog", "custom_url": "@blog", "enlaces": ["https://blog.pe"]}
    roto = {"id": "UCroto", "custom_url": "", "enlaces": ["https://caido.pe"]}
    nada = {"id": "UCnada", "custom_url": "", "enlaces": ["https://instagram.com/yo"]}
    cliente = ClienteFalso({
        "https://www.gob.pe/senamhi": '<a href="https://www.youtube.com/@senamhi">YouTube</a>',
        "https://diario.pe/": '<script>{"@type":"NewsArticle"}</script><a href="https://youtube.com/channel/UCmed">',
        "https://blog.pe/": '<a href="https://youtube.com/@blog">',
        "https://caido.pe/": None,
    })  # fmt: skip
    lista = [oficial, medio, blog, roto, nada]
    paginas = paginas_de(lista, cliente)
    tipos = {c["id"]: canales.clasificar(c, paginas) for c in lista}
    assert tipos["UCofi"]["tipo"] == "oficial"
    assert tipos["UCmed"]["tipo"] == "medio"
    assert tipos["UCblog"]["tipo"] == "otros" and not tipos["UCblog"]["ambiguo"]  # sin metadatos de noticia
    assert tipos["UCroto"]["ambiguo"]
    assert tipos["UCnada"]["motivo"] == "sin enlaces"
    assert "https://fb.com/x" not in cliente.pedidas
    assert all("<" not in json.dumps(p) for p in paginas.values())  # nunca se guarda el HTML


def test_oficial_si_un_sitio_gob_pe_enlaza_al_canal_aunque_el_canal_no_enlace_nada():
    senamhi = {"id": "UCsen", "custom_url": "@senamhiperu", "enlaces": []}
    cliente = ClienteFalso({"https://www.senamhi.gob.pe/": '<a href="https://www.youtube.com/@SenamhiPeru">'})
    paginas = {r["id"]: r for r in canales.leer_host("www.senamhi.gob.pe", ["https://www.senamhi.gob.pe/"], cliente)}
    assert canales.clasificar(senamhi, paginas, [])["tipo"] == "oficial"


def test_medio_por_el_sitio_que_enlazan_sus_videos_y_sin_date_published():
    canal = {"id": "UCrpp", "custom_url": "@rpp", "enlaces": []}
    videos = [["https://rpp.pe/peru/nota-1"], ["https://rpp.pe/peru/nota-2", "https://otro.pe/x"]]
    candidatos = canales.sitios(canal, videos)
    assert candidatos[0] == "https://rpp.pe/"
    cliente = ClienteFalso({
        "https://rpp.pe/": '<script>{"@type":"NewsArticle"}</script><a href="https://youtube.com/@rpp">',
        "https://otro.pe/": '<script>{"datePublished":"2026"}</script><a href="https://youtube.com/@rpp">',
    })  # fmt: skip
    paginas = paginas_de([{"id": "x", "enlaces": candidatos}], cliente)
    assert canales.clasificar(canal, paginas, candidatos)["tipo"] == "medio"
    solo_blog = canales.clasificar(canal, paginas, ["https://otro.pe/"])
    assert solo_blog["tipo"] == "otros"  # datePublished ya no basta


def test_respuestas_incluidas_y_las_que_faltan(carpetas):
    hilo_largo = hilo(1, "UCa")
    hilo_largo["snippet"]["totalReplyCount"] = 3
    hilo_largo["replies"] = {"comments": [{"id": "r1", "snippet": {"parentId": "hilo1", "textOriginal": "sí"}}]}
    servicio = Servicio()
    servicio.respuestas_ = {"hilo1": [{"id": f"r{i}", "snippet": {"parentId": "hilo1", "textOriginal": "x",
                                       "authorChannelId": {"value": "UCb"}}} for i in range(1, 4)]}  # fmt: skip
    cliente = api.Api(servicio, api.Cupo(carpetas / "cupo.json"), dormir=lambda s: None)
    registros = descarga.bajar_respuestas(cliente, [hilo_largo, hilo(2, "UCc")], "v1")
    assert len(registros) == 3 and {r["hilo"] for r in registros} == {privacidad.seudonimo("hilo1", SAL)}
    assert all("UCb" not in json.dumps(r) and r["autor"] for r in registros)


def test_completar_respuestas_del_dia1_retoma_por_video(carpetas):
    videos = {"v3": item_video("v3", "El Niño en Piura", publicado="2026-03-10T15:00:00Z")}
    con_respuestas = hilo(1, "UCa")
    con_respuestas["snippet"]["totalReplyCount"] = 1
    con_respuestas["replies"] = {"comments": [{"id": "r1", "snippet": {"parentId": "hilo1", "textOriginal": "x"}}]}
    servicio = Servicio(videos, {}, {"v3": [[con_respuestas] + [hilo(i, "UCz") for i in range(2, 40)]]})
    cliente = api.Api(servicio, api.Cupo(carpetas / "cupo.json"), dormir=lambda s: None)
    ruta = almacen.ruta("estado-dia1", extension="json")
    guardar = __import__("radar.comun.archivos", fromlist=["guardar_json"]).guardar_json
    guardar(ruta, {"comentarios": {"v3": {"paginas": 1, "siguiente": None, "fin": True}}})
    assert descarga.completar_respuestas(cliente, "dia1")
    assert any(c["hilo"] for c in almacen.leer("comentarios"))
    antes = len(servicio.llamadas)
    assert descarga.completar_respuestas(cliente, "dia1")  # ya hecho: no vuelve a llamar
    assert len(servicio.llamadas) == antes


def test_medio_por_sitemap_de_noticias():
    canal = {"id": "UCm", "custom_url": "@m", "enlaces": ["https://m.pe"]}
    cliente = ClienteFalso({"https://m.pe/": '<a href="https://youtube.com/@m">'},
                           robots={"m.pe": ["https://m.pe/sitemap-news.xml"]})  # fmt: skip
    assert canales.clasificar(canal, paginas_de([canal], cliente))["tipo"] == "medio"


class Corte(Exception):
    pass


def test_leer_portadas_retoma_sin_repetir_hosts(carpetas):
    lista = [{"id": f"UC{i}", "custom_url": "", "enlaces": [f"https://sitio{i}.pe"]} for i in range(5)]
    leidos, cortar = [], [True]

    def leer(host, urls):
        leidos.append(host)
        if host == "sitio3.pe" and cortar:
            cortar.clear()
            raise Corte  # se cortó a mitad (como un Ctrl+C o un apagón)
        return [{"id": u, "host": host, "leido": True, "youtube": [], "news_article": False,
                 "sitemap_noticias": False, "version": canales.VERSION_PORTADAS} for u in urls]  # fmt: skip

    urls = [u for c in lista for u in canales.sitios(c)]
    with pytest.raises(Corte):
        canales.leer_portadas(urls, leer=leer, hilos=1)
    guardados = set(almacen.ultimos("portadas"))
    assert "https://sitio3.pe/" not in guardados and guardados  # lo terminado quedó guardado
    leidos.clear()
    paginas = canales.leer_portadas(urls, leer=leer, hilos=1)
    assert len(paginas) == 5 and "sitio3.pe" in leidos
    assert not set(leidos) & {u.split("/")[2] for u in guardados}  # no repite lo ya guardado


def test_avance_informa_porcentaje_y_lo_que_falta():
    from radar.comun.avance import Avance

    mensajes, reloj = [], iter([0, 0, 10, 20, 30, 40]).__next__
    a = Avance("Sitios", 4, previos=2, cada=5, reloj=reloj, salida=mensajes.append)
    a.paso()
    a.paso()
    assert mensajes[0] == "Sitios: 2 de 6 ya hechos antes; faltan 4"
    assert "4 de 6 (67 %)" in mensajes[-1] and "faltan ~20 s" in mensajes[-1]


# ---------------------------------------------------------------- viabilidad


def test_componente_mayor_de_la_red_canal_canal():
    aristas = [("a", "c1"), ("a", "c2"), ("b", "c2"), ("b", "c3"), ("z", "c9"), ("y", "c7"), ("y", "c8")]
    assert viabilidad.componente_mayor(aristas) == 3


def test_criterios_y1_y2_y4():
    videos = {f"v{i}": {"id": f"v{i}", "titulo": "El Niño en Piura", "descripcion": "", "canal": "c1",
                        "publicado": "2026-03-01T12:00:00Z", "comentarios": 40, "descargado": "2026-11-17"}
              for i in range(3)}  # fmt: skip
    comentarios = {f"h{i}": {"video": "v0", "autor": f"a{i}"} for i in range(30)}
    tipos = {"c1": {"tipo": "medio", "ambiguo": "0"}}
    filas = {f["criterio"][:2]: f for f in viabilidad.medir(videos, {}, comentarios, tipos, corte_hecho=False)}
    assert filas["Y1"]["valor"] == 3 and not filas["Y1"]["pasa"]
    assert filas["Y2"]["valor"] == 1
    assert filas["Y4"]["valor"] == 1.0 and filas["Y4"]["pasa"]
    assert "Y3" not in filas and "Y5" not in filas


def test_referencia_sin_prefijo_como_la_del_senamhi():
    html = '<a href="https://youtube.com/senamhiperu"> <a href="https://youtube.com/watch?v=1"> youtube.com/embed/x'
    resumen = canales.resumen_pagina(html)
    assert resumen["youtube"] == ["/senamhiperu"]
    canal = {"id": "UCsen", "custom_url": "@senamhiperu"}
    assert "/senamhiperu" in canales.referencias_del_canal(canal)
