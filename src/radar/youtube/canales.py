"""Tipo de canal (README, "Tipo de canal"): por enlaces verificables, sin listas de terceros ni etiquetado manual.

1. Oficial: el canal está enlazado desde un sitio `.gob.pe`. Se leen los sitios de las instituciones de
   config/instituciones_web.csv (y su página en gob.pe) y las páginas `.gob.pe` que enlazan el canal o sus videos.
2. Medio: un sitio que enlaza el canal (en su descripción o en las de sus videos, los SITIOS_DE_VIDEOS más
   frecuentes) enlaza de vuelta al canal en su portada y tiene NewsArticle o un sitemap de noticias en su robots.txt.
3. Otros: todo lo demás.

Ambiguo: algún sitio candidato no se pudo leer (error, robots.txt o bloqueo) y ningún otro clasifica el canal como
oficial o medio. La API no entrega la sección de enlaces del canal: un medio que no enlaza su sitio en ninguna
descripción queda como "otros" (error declarado).

Corrección del 16-nov (después del día 1): la primera versión exigía que el canal enlazara al sitio (al revés del
README) y aceptaba "datePublished" como metadato de noticia; dejaba como "otros" al SENAMHI, RPP y Andina, y como
"medio" a blogs y academias.

Cómo corre:
- Los sitios se leen en paralelo, HILOS hosts a la vez; dentro de un mismo host, de a uno y con la pausa de siempre
  (config.PAUSA_POR_HOST), con robots.txt y reintentos de `radar.comun.http.Cliente`.
- De cada página se guarda solo lo que hace falta para clasificar (las referencias a YouTube que contiene, si tiene
  metadatos de noticia y si su robots.txt declara un sitemap de noticias), nunca el HTML, en
  data/raw/youtube/AAAA-MM-DD_portadas.jsonl, en cuanto termina cada host. Si el proceso se corta (Ctrl+C, apagón,
  laptop apagada), al volver a correrlo retoma desde el último host terminado.
- Muestra el avance y el tiempo que falta cada 15 s.

Uso: python -m radar.youtube.canales
"""

import collections
import concurrent.futures
import logging
import re
import sys
import threading
from urllib.parse import urlsplit

from radar import config
from radar.comun.archivos import escribir_csv, leer_csv
from radar.comun.avance import Avance
from radar.comun.candado import exclusivo
from radar.comun.energia import sin_suspension
from radar.comun.http import Cliente, ErrorDescarga
from radar.comun.registro import configurar, describir
from radar.youtube import almacen

log = logging.getLogger(__name__)

OFICIAL, MEDIO, OTROS = "oficial", "medio", "otros"
COLUMNAS = ("canal", "tipo", "ambiguo", "motivo", "sitio")
HILOS = 8  # hosts distintos a la vez; nunca más de una petición a la vez al mismo host
# Enlaces que no dicen nada de la organización del canal
HOSTS_IGNORADOS = re.compile(
    r"(^|\.)(youtube\.com|youtu\.be|google\.com|goo\.gl|facebook\.com|fb\.com|fb\.me|instagram\.com|twitter\.com|"
    r"x\.com|tiktok\.com|whatsapp\.com|wa\.me|t\.me|telegram\.me|linktr\.ee|linkedin\.com|spotify\.com|"
    r"bit\.ly|tinyurl\.com|patreon\.com|paypal\.com|paypal\.me|threads\.net|kick\.com|twitch\.tv|discord\.gg)$",
    re.I,
)
METADATOS_NOTICIA = re.compile(r"NewsArticle", re.I)
SITIOS_DE_VIDEOS = 3  # hosts más enlazados en las descripciones de los videos de cada canal
REFERENCIA_YOUTUBE = re.compile(r"youtube\.com/((?:channel/|c/|user/|@)[\w.\-]+)", re.I)
# youtube.com/<nombre>: la dirección personalizada antigua (la usa el SENAMHI); no las páginas de YouTube
REFERENCIA_SIN_PREFIJO = re.compile(
    r"youtube\.com/(?!(?:watch|embed|playlist|shorts|results|live|feed|redirect|channel|c|user|hashtag|t|v)\b)"
    r"([A-Za-z0-9][\w.\-]*)(?=[\"'/?#\s<]|$)",
    re.I,
)
VERSION_PORTADAS = 3  # sube cuando cambia lo que se extrae de cada página: las anteriores se vuelven a leer
_PARAR = threading.Event()  # Ctrl+C: los hilos terminan la página en curso y no empiezan otra


def es_gob_pe(host):
    return host == "gob.pe" or host.endswith(".gob.pe")


def _direccion(enlace):
    """La página exacta si es .gob.pe, la portada en los demás; None si es una red social o un acortador."""
    partes = urlsplit(enlace.rstrip(".,;"))
    host = partes.netloc.lower().split(":")[0]
    if not host or HOSTS_IGNORADOS.search(host):
        return None
    return f"https://{host}{partes.path}" if es_gob_pe(host) else f"https://{host}/"


def sitios(canal, enlaces_videos=()):
    """Direcciones candidatas de un canal: las de su descripción y los hosts más enlazados en sus videos."""
    salida = [d for d in map(_direccion, canal.get("enlaces") or []) if d]
    conteo = collections.Counter()
    for enlaces in enlaces_videos:
        conteo.update({d for d in map(_direccion, enlaces) if d})
    salida += [d for d, _ in conteo.most_common(SITIOS_DE_VIDEOS)]
    return list(dict.fromkeys(salida))


def sitios_oficiales():
    """Sitios .gob.pe de las instituciones de config/instituciones_web.csv y su página en www.gob.pe."""
    salida = []
    for fila in leer_csv(config.ARCHIVO_INSTITUCIONES_WEB):
        for alternativa in fila["patron"].replace("(^|\\.)", "").split("|"):
            host = alternativa.replace("\\.", ".")
            if re.fullmatch(r"[a-z0-9.\-]+\.gob\.pe", host):
                salida.append(f"https://{'www.' if host.count('.') == 2 else ''}{host}/")
        salida.append(f"https://www.gob.pe/institucion/{fila['actor'].lower()}")
    return list(dict.fromkeys(salida))


def resumen_pagina(html):
    """Lo único que se conserva de una página: sus referencias a YouTube y si tiene metadatos de noticia."""
    return {
        "youtube": sorted(
            {r.lower().rstrip(".") for r in REFERENCIA_YOUTUBE.findall(html)}
            | {"/" + r.lower().rstrip(".") for r in REFERENCIA_SIN_PREFIJO.findall(html)}
        ),
        "version": VERSION_PORTADAS,
        "news_article": bool(METADATOS_NOTICIA.search(html)),
    }


def referencias_del_canal(canal):
    refs = {f"channel/{canal['id'].lower()}"}
    usuario = (canal.get("custom_url") or "").lower().lstrip("@")
    if usuario:
        refs |= {f"@{usuario}", f"c/{usuario}", f"user/{usuario}", f"/{usuario}"}
    return refs


def leer_host(host, urls, cliente=None):
    """Lee las direcciones de un host, de a una. Devuelve un registro por dirección (sin el HTML)."""
    cliente = cliente or Cliente()
    salida = []
    for url in urls:
        if _PARAR.is_set():
            return None  # host a medias: no se guarda y se vuelve a leer completo la próxima vez
        registro = {"id": url, "host": host, "leido": False, "youtube": [], "news_article": False,
                    "sitemap_noticias": False}  # fmt: skip
        try:
            registro.update(resumen_pagina(cliente.get(url).text), leido=True)
            sitemaps = cliente.robots.get(host, ((), []))[1]
            registro["sitemap_noticias"] = any("news" in s.lower() for s in sitemaps)
        except (ErrorDescarga, OSError) as e:
            registro.update(error=describir(e)[:120], version=VERSION_PORTADAS)
            log.debug("no se pudo leer %s: %s", url, describir(e))
        salida.append(registro)
    return salida


def referencias_oficiales(paginas):
    """{referencia a YouTube: host} de las páginas .gob.pe leídas."""
    salida = {}
    for p in paginas.values():
        if p["leido"] and es_gob_pe(p["host"]):
            for r in p["youtube"]:
                salida.setdefault(r, p["host"])
    return salida


def clasificar(canal, paginas, revisados=None, oficiales=None):
    """paginas: {url: registro de leer_host}; revisados: sitios candidatos del canal; oficiales: de
    referencias_oficiales."""
    refs = referencias_del_canal(canal)
    oficiales = referencias_oficiales(paginas) if oficiales is None else oficiales
    comunes = sorted(refs & set(oficiales))
    if comunes:
        return {"canal": canal["id"], "tipo": OFICIAL, "ambiguo": False, "motivo": "gob.pe enlaza",
                "sitio": oficiales[comunes[0]]}  # fmt: skip
    revisados = sitios(canal) if revisados is None else revisados
    if not revisados:
        return {"canal": canal["id"], "tipo": OTROS, "ambiguo": False, "motivo": "sin enlaces", "sitio": ""}
    fallidos = []
    for url in revisados:
        p = paginas.get(url)
        if p is None or not p["leido"]:
            fallidos.append(url)
            continue
        if not refs & set(p["youtube"]):
            continue
        host = urlsplit(url).netloc
        if es_gob_pe(host):
            return {"canal": canal["id"], "tipo": OFICIAL, "ambiguo": False, "motivo": "gob.pe enlaza", "sitio": host}
        if p["news_article"] or p["sitemap_noticias"]:
            return {"canal": canal["id"], "tipo": MEDIO, "ambiguo": False, "motivo": "sitio de noticias", "sitio": host}
    if fallidos:
        return {"canal": canal["id"], "tipo": OTROS, "ambiguo": True, "motivo": "sitio sin leer",
                "sitio": urlsplit(fallidos[0]).netloc}  # fmt: skip
    return {"canal": canal["id"], "tipo": OTROS, "ambiguo": False, "motivo": "sin enlace de vuelta", "sitio": ""}


def por_host(urls):
    grupos = {}
    for url in urls:
        grupos.setdefault(urlsplit(url).netloc, []).append(url)
    return grupos


def leer_portadas(urls, leer=leer_host, hilos=HILOS):
    """Lee las direcciones que faltan, en paralelo por host, guardando cada host apenas termina."""
    previas = {u for u, r in almacen.ultimos("portadas").items() if r.get("version") == VERSION_PORTADAS}
    todas = sorted(set(urls))
    grupos = por_host(u for u in todas if u not in previas)
    avance = Avance("Sitios", len(grupos), previos=len(por_host(todas)) - len(grupos))
    _PARAR.clear()
    ejecutor = concurrent.futures.ThreadPoolExecutor(max_workers=hilos)
    try:
        futuros = [ejecutor.submit(leer, host, urls) for host, urls in grupos.items()]
        for futuro in concurrent.futures.as_completed(futuros):
            registros = futuro.result()
            if registros:
                almacen.anexar("portadas", registros)  # solo el hilo principal escribe
            avance.paso()
    except BaseException:
        _PARAR.set()
        ejecutor.shutdown(wait=True, cancel_futures=True)
        raise
    ejecutor.shutdown()
    return almacen.ultimos("portadas")


def tipos():
    """Tipo vigente de cada canal (el archivo más reciente)."""
    almacen.comprobar_vigencia()
    previos = almacen.archivos("tipos", bases=(config.DIR_YOUTUBE,))
    return {f["canal"]: f for f in leer_csv(previos[-1])} if previos else {}


@exclusivo("radar.youtube.canales")
def main(argv=None):
    configurar("youtube-canales")
    try:
        canales = sorted(almacen.ultimos("canales").values(), key=lambda c: c["id"])
    except almacen.Vencido as e:
        log.error(str(e))
        return 1
    enlaces_videos = collections.defaultdict(list)
    for v in almacen.ultimos("videos").values():
        enlaces_videos[v["canal"]].append(v.get("enlaces") or [])
    candidatos = {c["id"]: sitios(c, enlaces_videos[c["id"]]) for c in canales}
    log.info(f"{len(canales)} canales; {sum(bool(s) for s in candidatos.values())} con algún sitio candidato")
    try:
        with sin_suspension():
            paginas = leer_portadas(sitios_oficiales() + [u for s in candidatos.values() for u in s])
    except KeyboardInterrupt:
        log.info("Cortado: lo leído quedó guardado; vuelve a correrlo para seguir.")
        return 130
    oficiales = referencias_oficiales(paginas)
    filas = [clasificar(c, paginas, candidatos[c["id"]], oficiales) for c in canales]
    destino = almacen.ruta("tipos", extension="csv", base=config.DIR_YOUTUBE)
    escribir_csv(destino, COLUMNAS, filas)
    conteo = {t: sum(f["tipo"] == t for f in filas) for t in (OFICIAL, MEDIO, OTROS)}
    ambiguos = sum(f["ambiguo"] for f in filas)
    log.info(f"{len(filas)} canales: {conteo}; ambiguos: {ambiguos}. Guardado en {destino.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
