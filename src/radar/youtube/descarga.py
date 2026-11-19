"""Descarga de YouTube por días de cupo (docs/youtube/definicion.md, secciones 2, 3 y 6).

- dia1: 100 búsquedas (meses de enero a octubre × 5 términos × orden por fecha y por relevancia), metadatos de los
  videos y sus canales, y la primera página de comentarios de los que pasan el filtro con ≥ 30 → viabilidad.
- dia2: parte en dos quincenas cada búsqueda por fecha que llegó saturada (50), solo por fecha, hasta 100.
- corte: noviembre (del 1 al 20), métricas de todos los videos en una sola fecha y comentarios: una página para
  todos y luego más, hasta 10 por video, mientras quede cupo (deja config.MARGEN_CUPO sin gastar).

Cada etapa se puede cortar y volver a correr: no repite búsquedas, metadatos ni páginas ya descargadas. Si se acaba
el cupo, se vuelve a correr al día de cupo siguiente (desde las 03:00 de Lima).

Uso: python -m radar.youtube.descarga dia1 | dia2 | corte
"""

import argparse
import datetime as dt
import logging
import re
import sys

from radar import config
from radar.comun.archivos import guardar_json, leer_json
from radar.comun.avance import Avance
from radar.comun.candado import Ocupado, candado
from radar.comun.registro import configurar, describir
from radar.youtube import almacen, filtro
from radar.youtube.api import POR_PAGINA, Api, CupoAgotado, ErrorApi, SinClave, SinComentarios, dia_de_cupo
from radar.youtube.privacidad import SinSal, limpiar_texto, seudonimo

log = logging.getLogger(__name__)

ORDENES = ("date", "relevance")
SATURADA = 50  # una búsqueda que devuelve la página completa probablemente dejó videos fuera
COMENTARIOS_Y2 = 30
PAGINAS_MAXIMAS = 10  # 1.000 comentarios principales por video
PAGINAS_RESPUESTAS = 5  # hasta 500 respuestas por hilo
ULTIMO_MES_DIA1 = 10  # octubre
ENLACE = re.compile(r"https?://[^\s<>\"')\]]+")


# ---------------------------------------------------------------- plan de búsquedas


def meses(desde_mes, hasta_mes, anio=2026):
    for m in range(desde_mes, hasta_mes + 1):
        inicio = dt.date(anio, m, 1)
        fin = (dt.date(anio + (m == 12), m % 12 + 1, 1)) - dt.timedelta(days=1)
        yield inicio, fin


def clave(termino, desde, hasta, orden):
    return f"{termino}|{desde}|{hasta}|{orden}"


def busqueda(termino, desde, hasta, orden):
    return {"id": clave(termino, desde, hasta, orden), "termino": termino, "desde": desde, "hasta": hasta,
            "orden": orden}  # fmt: skip


def plan_dia1():
    return [
        busqueda(t, d, h, o) for d, h in meses(1, ULTIMO_MES_DIA1) for t in config.TERMINOS_YOUTUBE for o in ORDENES
    ]


def plan_dia2(previas):
    """Quincenas de cada búsqueda mensual por fecha que llegó saturada (regla fijada antes de ver los datos)."""
    plan = []
    for b in previas:
        desde, hasta = dt.date.fromisoformat(str(b["desde"])), dt.date.fromisoformat(str(b["hasta"]))
        if b["orden"] == "date" and len(b["videos"]) >= SATURADA and desde.day == 1 and (hasta - desde).days > 20:
            mitad = desde.replace(day=15)
            plan += [busqueda(b["termino"], desde, mitad, "date"),
                     busqueda(b["termino"], mitad + dt.timedelta(days=1), hasta, "date")]  # fmt: skip
    plan.sort(key=lambda x: (x["desde"], config.TERMINOS_YOUTUBE.index(x["termino"])))
    return plan[: config.BUSQUEDAS_POR_DIA]


def plan_corte():
    inicio = dt.date(config.FIN_CORTE.year, config.FIN_CORTE.month, 1)
    return [busqueda(t, inicio, config.FIN_CORTE, o) for t in config.TERMINOS_YOUTUBE for o in ORDENES]


# ---------------------------------------------------------------- registros (solo lo de la definición)


def _entero(valor):
    return int(valor) if valor not in (None, "") else None


def registro_video(item):
    s, st, cd = item.get("snippet", {}), item.get("statistics", {}), item.get("contentDetails", {})
    descripcion = s.get("description", "")
    return {
        "id": item["id"], "titulo": s.get("title", ""), "descripcion": descripcion,
        "enlaces": ENLACE.findall(descripcion), "canal": s.get("channelId", ""), "publicado": s.get("publishedAt", ""),
        "duracion": cd.get("duration", ""), "categoria": s.get("categoryId", ""),
        "vistas": _entero(st.get("viewCount")), "likes": _entero(st.get("likeCount")),  # ocultos: None
        "comentarios": _entero(st.get("commentCount")),  # desactivados: None
    }  # fmt: skip


def registro_canal(item):
    s, st = item.get("snippet", {}), item.get("statistics", {})
    descripcion = s.get("description", "")
    return {
        "id": item["id"], "titulo": s.get("title", ""), "pais": s.get("country", ""),
        "custom_url": s.get("customUrl", ""), "descripcion": descripcion, "enlaces": ENLACE.findall(descripcion),
        "suscriptores": None if st.get("hiddenSubscriberCount") else _entero(st.get("subscriberCount")),
        "videos": _entero(st.get("videoCount")),
    }  # fmt: skip


def registro_comentario(hilo, video):
    """Solo texto limpio, fecha, likes, n.° de respuestas y seudónimos: nunca nombre, foto ni canal del autor."""
    principal = hilo.get("snippet", {}).get("topLevelComment", {}).get("snippet", {})
    autor = (principal.get("authorChannelId") or {}).get("value", "")
    return {
        "id": seudonimo(hilo["id"]), "video": video, "autor": seudonimo(autor),
        "texto": limpiar_texto(principal.get("textOriginal") or principal.get("textDisplay") or ""),
        "publicado": principal.get("publishedAt", ""), "likes": _entero(principal.get("likeCount")),
        "respuestas": _entero(hilo.get("snippet", {}).get("totalReplyCount")), "hilo": "",
    }  # fmt: skip


def registro_respuesta(item, video):
    """Una respuesta, con los mismos campos que un comentario y el seudónimo de su hilo."""
    s = item.get("snippet", {})
    autor = (s.get("authorChannelId") or {}).get("value", "")
    return {
        "id": seudonimo(item["id"]), "video": video, "autor": seudonimo(autor),
        "texto": limpiar_texto(s.get("textOriginal") or s.get("textDisplay") or ""),
        "publicado": s.get("publishedAt", ""), "likes": _entero(s.get("likeCount")), "respuestas": None,
        "hilo": seudonimo(s.get("parentId", "")),
    }  # fmt: skip


def bajar_respuestas(api, hilos, video):
    """Respuestas de los hilos de una página: las que vienen incluidas y, si faltan, las demás con comments.list.
    El id real del hilo solo se usa aquí, en memoria; lo guardado es su seudónimo."""
    registros = []
    for h in hilos:
        total = _entero(h.get("snippet", {}).get("totalReplyCount")) or 0
        incluidas = h.get("replies", {}).get("comments", [])
        if total <= len(incluidas):
            registros += [registro_respuesta(r, video) for r in incluidas]
            continue
        pagina = None
        for _ in range(PAGINAS_RESPUESTAS):
            items, pagina = api.respuestas(h["id"], pagina)
            registros += [registro_respuesta(r, video) for r in items]
            if not pagina:
                break
    return registros


# ---------------------------------------------------------------- etapas


def _estado(etapa):
    previos = almacen.archivos(f"estado-{etapa}", bases=(config.DIR_RAW_YOUTUBE,))
    ruta = previos[-1] if previos else almacen.ruta(f"estado-{etapa}", extension="json")
    return ruta, leer_json(ruta, {}) or {}


def buscar(api, plan, etapa):
    hechas = {r["id"] for r in almacen.leer("busquedas")}
    pendientes = [b for b in plan if b["id"] not in hechas]
    avance = Avance("Búsquedas", len(pendientes), previos=len(plan) - len(pendientes))
    for i, b in enumerate(pendientes, 1):
        try:
            ids = api.buscar(b["termino"], dt.date.fromisoformat(str(b["desde"])),
                             dt.date.fromisoformat(str(b["hasta"])), b["orden"])  # fmt: skip
        except CupoAgotado:
            log.warning(f"Se acabó el cupo de búsquedas tras {i - 1}: vuelve a correr la etapa mañana (03:00).")
            return False
        except ErrorApi as e:
            log.warning(f"Búsqueda {b['id']} falló: {describir(e)}")
            avance.paso()
            continue
        registro = {**b, "desde": str(b["desde"]), "hasta": str(b["hasta"]), "etapa": etapa, "videos": ids,
                    "saturada": len(ids) >= SATURADA, "dia_cupo": dia_de_cupo().isoformat()}  # fmt: skip
        almacen.anexar("busquedas", [registro])
        avance.paso()
    return True


def por_lotes(nombre, falta, descargar, registrar):
    """Descarga de a POR_PAGINA ids y guarda cada lote apenas llega: un corte solo pierde el lote en curso."""
    lotes = [falta[i : i + POR_PAGINA] for i in range(0, len(falta), POR_PAGINA)]
    avance = Avance(nombre, len(falta))
    for lote in lotes:
        almacen.anexar(nombre.lower(), [registrar(x) for x in descargar(lote)])
        avance.paso(len(lote))


def metadatos(api, desde_fecha=None):
    """Videos y canales sin metadatos (o, en el corte, sin metadatos desde `desde_fecha`)."""
    ids = list(dict.fromkeys(v for r in almacen.leer("busquedas") for v in r["videos"]))
    videos = almacen.ultimos("videos")
    falta = [v for v in ids if v not in videos or (desde_fecha and videos[v]["descargado"] < desde_fecha)]
    log.info(f"Videos: {len(ids)} encontrados, {len(falta)} por descargar")
    por_lotes("Videos", falta, api.videos, registro_video)
    videos = almacen.ultimos("videos")
    canales = almacen.ultimos("canales")
    ids_canales = {v["canal"] for v in videos.values() if v["canal"]}
    falta = sorted(
        c for c in ids_canales if c not in canales or (desde_fecha and canales[c]["descargado"] < desde_fecha)
    )
    log.info(f"Canales: {len(ids_canales)}, {len(falta)} por descargar")
    por_lotes("Canales", falta, api.canales, registro_canal)


def candidatos(minimo_comentarios):
    videos, canales = almacen.ultimos("videos"), almacen.ultimos("canales")
    elegidos = (v for v in videos.values() if (v["comentarios"] or 0) >= minimo_comentarios)
    return sorted((v for v in elegidos if filtro.pasa(v, canales.get(v["canal"]))), key=lambda v: v["id"])


def comentarios(api, etapa, minimo, paginas_maximas):
    """Ronda a ronda: una página más para cada video pendiente, hasta `paginas_maximas` o hasta que no haya cupo."""
    ruta, estado = _estado(etapa)
    por_video = estado.setdefault("comentarios", {})
    lista = candidatos(minimo)
    log.info(f"Comentarios: {len(lista)} videos candidatos (≥ {minimo} comentarios), hasta {paginas_maximas} página(s)")

    def falta_paginas(v):
        e = por_video.get(v["id"], {})
        return 0 if e.get("fin") else paginas_maximas - e.get("paginas", 0)

    avance = Avance("Páginas de comentarios (máximo)", sum(falta_paginas(v) for v in lista))
    for ronda in range(paginas_maximas):
        pendientes = [v for v in lista if not por_video.get(v["id"], {}).get("fin")
                      and por_video.get(v["id"], {}).get("paginas", 0) == ronda]  # fmt: skip
        for v in pendientes:
            e = por_video.setdefault(v["id"], {"paginas": 0, "siguiente": None, "fin": False})
            if api.cupo.unidades_libres() <= 0:
                guardar_json(ruta, estado)
                log.warning("Se llegó al tope de unidades del día (con margen): vuelve a correr la etapa mañana.")
                return False
            try:
                hilos, siguiente = api.comentarios(v["id"], e["siguiente"])
            except SinComentarios:
                avance.paso(falta_paginas(v))
                e.update(fin=True, cerrado=True)
                guardar_json(ruta, estado)
                continue
            except CupoAgotado:
                guardar_json(ruta, estado)
                log.warning("La API dio el cupo por agotado: vuelve a correr la etapa mañana.")
                return False
            except ErrorApi as error:
                log.warning(f"Comentarios de un video fallaron: {describir(error)}")
                avance.paso(falta_paginas(v))
                e["fin"] = True
                guardar_json(ruta, estado)
                continue
            try:
                respuestas = bajar_respuestas(api, hilos, v["id"])
            except CupoAgotado:
                guardar_json(ruta, estado)
                log.warning("La API dio el cupo por agotado: vuelve a correr la etapa mañana.")
                return False
            except (ErrorApi, SinComentarios) as error:
                log.warning(f"Respuestas de un video fallaron: {describir(error)}")
                respuestas = []
            almacen.anexar("comentarios", [registro_comentario(h, v["id"]) for h in hilos] + respuestas)
            antes = falta_paginas(v)
            if e["paginas"] == 0:
                e["con_respuestas"] = True
            e.update(paginas=e["paginas"] + 1, siguiente=siguiente, fin=not siguiente)
            avance.paso(antes - falta_paginas(v))  # 1, o todas las que ya no hacen falta si no hay más
            guardar_json(ruta, estado)  # después de guardar los comentarios: un corte repite a lo más una página
    return True


def completar_respuestas(api, etapa):
    """Corrección del 16-nov: las primeras páginas del día 1 se bajaron sin respuestas, y los ids de los hilos solo
    quedaron seudonimizados. Se vuelve a pedir la página 1 de esos videos, ahora con sus respuestas (1 unidad más por
    video y 1 por hilo con respuestas que no vienen incluidas). Retoma por video."""
    ruta, estado = _estado(etapa)
    por_video = estado.get("comentarios", {})
    faltan = sorted(v for v, e in por_video.items() if e.get("paginas", 0) > 0 and not e.get("con_respuestas"))
    if not faltan:
        return True
    avance = Avance("Respuestas de la página 1", len(faltan))
    for video in faltan:
        if api.cupo.unidades_libres() <= 0:
            log.warning("Se llegó al tope de unidades del día (con margen): vuelve a correr la etapa mañana.")
            return False
        try:
            hilos, _ = api.comentarios(video)
            registros = [registro_comentario(h, video) for h in hilos] + bajar_respuestas(api, hilos, video)
        except CupoAgotado:
            log.warning("La API dio el cupo por agotado: vuelve a correr la etapa mañana.")
            return False
        except (ErrorApi, SinComentarios) as error:
            log.warning(f"Respuestas de un video fallaron: {describir(error)}")
            registros = None
        if registros:
            almacen.anexar("comentarios", registros)
        por_video[video]["con_respuestas"] = True
        guardar_json(ruta, estado)
        avance.paso()
    return True


def correr(etapa, api=None):
    almacen.comprobar_vigencia()
    seudonimo("prueba")  # sin la sal no se guardan comentarios: se avisa antes de gastar cupo
    api = api or Api()
    ruta, estado = _estado(etapa)
    estado.setdefault("fecha", almacen.hoy().isoformat())
    guardar_json(ruta, estado)
    if etapa == "dia1":
        plan = plan_dia1()
    elif etapa == "dia2":
        plan = plan_dia2([r for r in almacen.leer("busquedas") if r["etapa"] == "dia1"])
    else:
        plan = plan_corte()
    completo = buscar(api, plan, etapa)
    try:
        metadatos(api, estado["fecha"] if etapa == "corte" else None)
    except CupoAgotado:
        log.warning("Sin cupo para los metadatos: vuelve a correr la etapa mañana.")
        return False
    completo &= completar_respuestas(api, etapa)
    if etapa == "corte":
        completo &= comentarios(api, etapa, 1, PAGINAS_MAXIMAS)
    else:
        completo &= comentarios(api, etapa, COMENTARIOS_Y2, 1)
    log.info(f"Cupo de hoy: {api.cupo.busquedas_libres()} búsquedas y {api.cupo.unidades_libres()} unidades libres")
    return completo


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("etapa", choices=("dia1", "dia2", "corte"))
    args = parser.parse_args(argv)
    configurar(f"youtube-{args.etapa}")
    try:
        with candado(f"radar.youtube.descarga {args.etapa}", config.DIR_RAW_YOUTUBE / "api.lock"):
            completo = correr(args.etapa)
    except (SinClave, SinSal, almacen.Vencido) as e:
        log.error(str(e))
        return 1
    except Ocupado as e:
        log.error(f"Otra descarga de YouTube está corriendo: {e}")
        return 2
    log.info("Etapa completa." if completo else "Etapa incompleta: vuelve a correrla cuando haya cupo.")
    return 0 if completo else 3


if __name__ == "__main__":
    sys.exit(main())
