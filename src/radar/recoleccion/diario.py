"""Recolección diaria de direcciones de notas (definición en docs/recoleccion/diaria.md).

Uso: python -m radar.recoleccion.diario --persona joseph [--prueba] [--publicar]
"""

import argparse
import datetime as dt
import logging
import re
import subprocess
import sys
from urllib.parse import parse_qs, urlencode, urlsplit

import requests
from lxml import html
from lxml.etree import ParserError

from radar import config
from radar.comun.archivos import anexar_csv, leer_csv
from radar.comun.http import Cliente, ErrorDescarga
from radar.comun.registro import configurar, describir
from radar.comun.texto import a_lima, ahora
from radar.comun.xml import NS_SITEMAP, XMLMalFormado, leer_xml
from radar.recoleccion.urls import archivos_de_notas

log = logging.getLogger(__name__)

COLUMNAS = ["url", "medio", "id", "fecha", "tipo_fecha", "seccion", "origen", "recolectado"]
COLUMNAS_SITEMAPS = ["sitemap", "http", "entradas", "mas_antigua", "mas_reciente", "ventana_h", "recolectado"]
ERRORES_FUENTE = (requests.RequestException, ErrorDescarga, XMLMalFormado, ParserError)
HORAS_SIN_NOVEDADES = 12
HORAS_ALERTA_EJECUCION = 36
HORAS_MAXIMO = 48
DIAS_API_ELTIEMPO = 10
ENTRADA_VENTANA = 5  # la ventana de un sitemap se mide desde su quinta entrada más antigua (ver diaria.md)
TIPOS_ENFEN = ["comunicado-oficial", "comunicado-extraordinario", "informe-tecnico", "nota-tecnica", "nota-de-prensa"]


def antes_de_inicio(fecha):
    return bool(fecha) and fecha[:10] < config.INICIO.isoformat()


# ---------------------------------------------------------------- recolección


class Fuente:
    """Junta las filas de un medio y el registro de cada sitemap leído."""

    def __init__(self, medio, cliente, momento):
        self.medio, self.cliente, self.momento = medio, cliente, momento
        self.recolectado = momento.isoformat()
        self.filas = {}  # clave -> fila
        self.registro = []  # filas del CSV de sitemaps
        self.fallos = []
        self.cobertura = []  # (sitemap, inicio de su ventana) para la alerta de hueco

    def agregar(self, url, ident, fecha, tipo, seccion, origen):
        if antes_de_inicio(fecha):
            return
        clave = ident or url
        fila = self.filas.get(clave)
        if fila is None:
            self.filas[clave] = {
                "url": url,
                "medio": self.medio,
                "id": ident,
                "fecha": fecha,
                "tipo_fecha": tipo if fecha else "",
                "seccion": {seccion} if seccion else set(),
                "origen": origen,
                "recolectado": self.recolectado,
            }
            return
        if fecha and fila["tipo_fecha"] != "publicacion" and tipo == "publicacion" or fecha and not fila["fecha"]:
            fila["fecha"], fila["tipo_fecha"] = fecha, tipo
        if seccion:
            fila["seccion"].add(seccion)

    def registrar(self, nombre, http, fechas, cobertura=False):
        fechas = sorted(fecha for fecha in fechas if fecha)
        ventana = ""
        if fechas:
            quinta = dt.datetime.fromisoformat(fechas[min(ENTRADA_VENTANA - 1, len(fechas) - 1)])
            ventana = round((self.momento - quinta).total_seconds() / 3600, 1)
            if cobertura:
                self.cobertura.append((nombre, quinta))
        self.registro.append(
            {
                "sitemap": f"{self.medio}:{nombre}",
                "http": http,
                "entradas": len(fechas),
                "mas_antigua": fechas[0] if fechas else "",
                "mas_reciente": fechas[-1] if fechas else "",
                "ventana_h": ventana,
                "recolectado": self.recolectado,
            }
        )

    def registrar_sin_fechas(self, nombre, http, entradas):
        self.registro.append(
            {
                "sitemap": f"{self.medio}:{nombre}",
                "http": http,
                "entradas": entradas,
                "mas_antigua": "",
                "mas_reciente": "",
                "ventana_h": "",
                "recolectado": self.recolectado,
            }
        )

    def fallo(self, nombre, error):
        http = getattr(getattr(error, "response", None), "status_code", "")
        self.registrar_sin_fechas(nombre, http or "error", 0)
        self.fallos.append(f"{nombre}: {describir(error)}")
        log.debug("fallo en %s:%s", self.medio, nombre, exc_info=error)

    def sitemap(self, url, nombre):
        """Entradas (loc, publication_date, lastmod) de un urlset; None si falla."""
        try:
            r = self.cliente.get(url)
            raiz = leer_xml(r.content)
        except ERRORES_FUENTE as e:
            self.fallo(nombre, e)
            return None
        entradas = []
        for u in raiz.findall("s:url", NS_SITEMAP):
            loc = (u.findtext("s:loc", namespaces=NS_SITEMAP) or "").strip()
            pub = (u.findtext("n:news/n:publication_date", namespaces=NS_SITEMAP) or "").strip()
            mod = (u.findtext("s:lastmod", namespaces=NS_SITEMAP) or "").strip()
            if loc:
                entradas.append((loc, a_lima(pub), a_lima(mod)))
        return r.status_code, entradas

    def indice(self, url, nombre):
        try:
            raiz = leer_xml(self.cliente.get(url).content)
        except ERRORES_FUENTE as e:
            self.fallo(nombre, e)
            return []
        return [(e.text or "").strip() for e in raiz.iter(f"{{{NS_SITEMAP['s']}}}loc")]


def andina(fuente):
    base = "https://andina.pe/agencia/"
    secciones = [u for u in fuente.indice(base + "sitemap.xml", "sitemap.xml") if "/sitemap-seccion-" in u]
    for url in [base + "news-sitemap.xml", base + "sitemap-ultimo.xml", *secciones]:
        nombre = url.rsplit("/", 1)[1]
        leido = fuente.sitemap(url, nombre)
        if leido is None:
            continue
        http, entradas = leido
        m = re.search(r"sitemap-seccion-(.+?)-\d+\.xml$", nombre)
        seccion = m.group(1) if m else ""
        for loc, pub, mod in entradas:
            nota = re.match(r"https://andina\.pe/agencia/noticia-.*-(\d+)\.aspx$", loc)
            if nota:
                fuente.agregar(
                    loc,
                    nota.group(1),
                    pub or mod,
                    "publicacion" if pub else "modificacion",
                    seccion,
                    f"andina:{nombre}",
                )
        fuente.registrar(nombre, http, [p or m for _, p, m in entradas], cobertura=nombre == "sitemap-ultimo.xml")


def rpp(fuente):
    web = fuente.indice("https://rpp.pe/sitemap/web", "sitemap/web")
    declarados = [u for u in fuente.cliente.robots_de("rpp.pe")[1] if u.startswith("https://rpp.pe/sitemap/web/")]
    for url in ["https://rpp.pe/sitemap/news", *dict.fromkeys(web + declarados)]:
        nombre = url.replace("https://rpp.pe/sitemap/", "")
        leido = fuente.sitemap(url, nombre)
        if leido is None:
            continue
        http, entradas = leido
        for loc, pub, mod in entradas:
            m = re.search(r"-(noticias?|live)-(\d+)$", loc)
            ident = f"{'live' if m.group(1) == 'live' else 'noticia'}-{m.group(2)}" if m else ""
            partes = urlsplit(loc).path.strip("/").split("/")
            fuente.agregar(
                loc, ident, pub or mod, "publicacion" if pub else "modificacion", "/".join(partes[:-1]), f"rpp:{nombre}"
            )
        fuente.registrar(nombre, http, [p or m for _, p, m in entradas], cobertura=nombre.startswith("web/"))


def exitosa(fuente):
    base = "https://www.exitosanoticias.pe/"
    mes = fuente.momento.date().replace(day=1)
    anterior = (mes - dt.timedelta(days=1)).replace(day=1)
    for nombre in ["sitemapNews.xml", f"sitemapNoticias{anterior:%Y%m}.xml", f"sitemapNoticias{mes:%Y%m}.xml"]:
        try:
            r = fuente.cliente.get(base + nombre)
            raiz = leer_xml(r.content)
        except requests.HTTPError as e:
            if e.response is not None and e.response.status_code == 404 and nombre.endswith(f"{mes:%Y%m}.xml"):
                fuente.registrar(nombre, 404, [])  # el mensual del mes nuevo aún no existe
            else:
                fuente.fallo(nombre, e)
            continue
        except ERRORES_FUENTE as e:
            fuente.fallo(nombre, e)
            continue
        fechas = []
        for u in raiz.findall("s:url", NS_SITEMAP):
            loc = (u.findtext("s:loc", namespaces=NS_SITEMAP) or "").strip()
            pub = a_lima(u.findtext("n:news/n:publication_date", namespaces=NS_SITEMAP))
            m = re.search(r"-(n\d+)$", loc)
            if not m:
                continue
            fechas.append(pub)
            fuente.agregar(
                loc, m.group(1), pub, "publicacion", urlsplit(loc).path.strip("/").split("/")[0], f"exitosa:{nombre}"
            )
        if any(fechas):
            fuente.registrar(nombre, r.status_code, fechas)
        else:  # el mensual no trae fechas: se registra solo el número de entradas
            fuente.registrar_sin_fechas(nombre, r.status_code, len(fechas))


def eltiempo(fuente):
    desde = (fuente.momento - dt.timedelta(days=DIAS_API_ELTIEMPO)).replace(tzinfo=None).isoformat()
    filas, pagina, paginas = [], 1, 1
    try:
        while pagina <= paginas:
            r = fuente.cliente.get(
                "https://eltiempo.pe/wp-json/wp/v2/posts",
                params={"per_page": 100, "page": pagina, "after": desde, "_fields": "id,link,date_gmt"},
            )
            paginas = int(r.headers.get("X-WP-TotalPages", 1))
            filas += r.json()
            pagina += 1
    except (*ERRORES_FUENTE, ValueError) as e:
        fuente.fallo("api", e)
        leido = fuente.sitemap("https://eltiempo.pe/news.xml", "news.xml")
        if leido is None:
            return
        http, entradas = leido
        for loc, pub, mod in entradas:
            fuente.agregar(
                loc,
                "",
                pub or mod,
                "publicacion" if pub else "modificacion",
                urlsplit(loc).path.strip("/").split("/")[0],
                "eltiempo:news.xml",
            )
        fuente.registrar("news.xml", http, [p or m for _, p, m in entradas], cobertura=True)
        return
    fechas = []
    for p in filas:
        fecha = a_lima(p["date_gmt"])
        fechas.append(fecha)
        fuente.agregar(
            p["link"],
            str(p["id"]),
            fecha,
            "publicacion",
            urlsplit(p["link"]).path.strip("/").split("/")[0],
            "eltiempo:api",
        )
    fuente.registrar("api", 200, fechas)


def enfen(fuente):
    for nombre in ["wpdmpro-sitemap.xml", "post-sitemap.xml"]:
        leido = fuente.sitemap(f"{config.URL_ENFEN}/{nombre}", nombre)
        if leido is None:
            continue
        http, entradas = leido
        for loc, _, mod in entradas:
            m = re.match(re.escape(config.URL_ENFEN) + r"/(?:download|\d{4}/\d{2}/\d{2})/([^/]+)/?$", loc)
            if not m:
                continue
            slug = m.group(1)
            tipo = (
                "entrada" if "/download/" not in loc else next((t for t in TIPOS_ENFEN if slug.startswith(t)), "otro")
            )
            fuente.agregar(loc, slug, mod, "modificacion", tipo, f"enfen:{nombre}")
        fuente.registrar(nombre, http, [m for _, _, m in entradas])


def senamhi(fuente):
    try:
        r = fuente.cliente.get(config.URL_AVISOS_SENAMHI)
        doc = html.fromstring(r.content)
    except ERRORES_FUENTE as e:
        fuente.fallo("aviso-meteorologico", e)
        return
    fechas = []
    for tr in doc.xpath("//table[@id='table_id']/tbody/tr"):
        celdas = tr.xpath("./td")
        enlace = tr.xpath("./td[1]//a/@href")
        if len(celdas) < 3 or not enlace:
            continue
        q = {k: v[0] for k, v in parse_qs(urlsplit(enlace[0]).query).items()}
        emision = celdas[2].text_content().strip()
        if not (q.get("a") and q.get("b") and re.match(r"\d{4}-\d{2}-\d{2}$", emision)):
            continue
        q["p"] = "aviso-meteorologico-detalle"
        url = config.URL_SENAMHI + "?" + urlencode({k: q[k] for k in ["p", "a", "b", "c", "d"] if k in q})
        fechas.append(emision)
        fuente.agregar(url, f"{q['a']}-{q['b']}", emision, "emision", "aviso", "senamhi:aviso-meteorologico")
    fuente.registrar(
        "aviso-meteorologico", r.status_code, [x + "T00:00:00-05:00" for x in fechas if x >= config.INICIO.isoformat()]
    )


FUENTES = {"andina": andina, "rpp": rpp, "exitosa": exitosa, "eltiempo": eltiempo, "enfen": enfen, "senamhi": senamhi}
PUBLICAN_A_DIARIO = {"andina", "rpp", "exitosa", "eltiempo"}
RECUPERACION = {
    "andina": "número de nota (noticia.aspx?id=N)",
    "rpp": "archivo por fecha (/archivo/<sección>/<fecha>)",
    "eltiempo": "API REST con after",
}


# ---------------------------------------------------------------- archivos


def leer_existentes():
    """Claves y direcciones ya recolectadas, y la última fecha de recolección."""
    claves, urls, ultima = set(), set(), None
    for ruta in archivos_de_notas():
        for fila in leer_csv(ruta):
            if fila.get("id"):
                claves.add((fila["medio"], fila["id"]))
            urls.add(fila["url"])
            if fila.get("recolectado"):
                fecha = dt.datetime.fromisoformat(fila["recolectado"])
                ultima = max(ultima, fecha) if ultima else fecha
    return claves, urls, ultima


def git(*args):
    return subprocess.run(["git", *args], cwd=config.RAIZ, check=True, capture_output=True, text=True)


# ---------------------------------------------------------------- principal


def recolectar(momento, claves, urls):
    cliente = Cliente()
    nuevas, registro, resumen = [], [], []
    for medio, funcion in FUENTES.items():
        fuente = Fuente(medio, cliente, momento)
        try:
            funcion(fuente)
        except Exception as e:  # una fuente que falla no detiene a las demás
            fuente.fallos.append(describir(e))
            log.debug("fallo inesperado en %s", medio, exc_info=True)
        propias = []
        for fila in fuente.filas.values():
            if (medio, fila["id"]) in claves or fila["url"] in urls:
                continue
            fila["seccion"] = "|".join(sorted(fila["seccion"]))
            propias.append(fila)
            claves.add((medio, fila["id"]))
            urls.add(fila["url"])
        nuevas += propias
        registro += fuente.registro
        fechas = sorted(x["fecha"] for x in fuente.filas.values() if x["fecha"])
        resumen.append((fuente, len(fuente.filas), propias, fechas[0][:10] if fechas else "-"))
    return nuevas, registro, resumen


def alertas_de(resumen, momento, ultima):
    alertas = [f"FALLO {fuente.medio} · {falla}" for fuente, _, _, _ in resumen for falla in fuente.fallos]
    if not ultima:
        return alertas
    horas = (momento - ultima).total_seconds() / 3600
    if horas > HORAS_ALERTA_EJECUCION:
        alertas.append(f"Pasaron {horas:.0f} h desde la última ejecución (máximo {HORAS_MAXIMO} h).")
    for fuente, _, propias, _ in resumen:
        for nombre, inicio in fuente.cobertura:
            if inicio > ultima:
                alertas.append(
                    f"HUECO {fuente.medio}:{nombre} empieza {inicio:%d-%m %H:%M}, después de la última "
                    f"recolección ({ultima:%d-%m %H:%M}). Recuperar por {RECUPERACION.get(fuente.medio, '-')}."
                )
        if fuente.medio in PUBLICAN_A_DIARIO and not propias and horas > HORAS_SIN_NOVEDADES:
            alertas.append(f"Sin novedades en {fuente.medio}.")
        if fuente.medio == "enfen":
            alertas += [f"Nuevo documento del ENFEN: {fila['id']}" for fila in propias]
    return alertas


def main(argv=None):
    ap = argparse.ArgumentParser(description="Recolección diaria de direcciones de notas.")
    ap.add_argument("--persona", required=True, choices=config.PERSONAS)
    ap.add_argument("--prueba", action="store_true", help="no escribe archivos ni toca git")
    ap.add_argument("--publicar", action="store_true", help="git pull, commit y push de los archivos de esta ejecución")
    args = ap.parse_args(argv)
    configurar("diario")
    momento = ahora()

    if args.publicar and not args.prueba:
        try:
            git("pull", "--ff-only")
        except subprocess.CalledProcessError as e:
            log.error("git pull falló; no se recolecta.\n%s", e.stderr or e.stdout)
            return 1

    claves, urls, ultima = leer_existentes()
    nuevas, registro, resumen = recolectar(momento, claves, urls)

    log.info(f"\nRecolección {momento.isoformat()} ({args.persona}){' [PRUEBA]' if args.prueba else ''}")
    log.info(f"{'medio':10}{'sitemaps':>10}{'vistas':>8}{'nuevas':>8}  más antigua")
    for fuente, vistas, propias, antigua in resumen:
        ok = sum(1 for r in fuente.registro if r["http"] in (200, 404))
        log.info(f"{fuente.medio:10}{ok:>5}/{len(fuente.registro):<4}{vistas:>8}{len(propias):>8}  {antigua}")
    log.info(f"{'total':10}{'':>10}{sum(v for _, v, _, _ in resumen):>8}{len(nuevas):>8}")
    alertas = alertas_de(resumen, momento, ultima)
    log.info("\n" + ("\n".join("- " + a for a in alertas) if alertas else "Sin alertas."))

    hubo_datos = any(v for _, v, _, _ in resumen)
    if args.prueba:
        return 0 if hubo_datos else 1

    base = f"{momento:%Y-%m-%d}_{args.persona}"
    escritos = []
    if nuevas:
        anexar_csv(config.DIR_URLS / f"{base}.csv", COLUMNAS, nuevas)
        escritos.append(config.DIR_URLS / f"{base}.csv")
    anexar_csv(config.DIR_URLS / f"{base}_sitemaps.csv", COLUMNAS_SITEMAPS, registro)
    escritos.append(config.DIR_URLS / f"{base}_sitemaps.csv")
    log.info("\nEscrito: " + ", ".join(str(p.relative_to(config.RAIZ)) for p in escritos))

    if args.publicar:
        try:
            git("add", *[str(p.relative_to(config.RAIZ)) for p in escritos])
            git("commit", "-m", f"datos: recolección {momento:%Y-%m-%d} ({args.persona})")
            try:
                git("push")
            except subprocess.CalledProcessError:
                git("pull", "--rebase")
                git("push")
            log.info("Publicado.")
        except subprocess.CalledProcessError as e:
            log.error("git falló:\n%s", e.stderr or e.stdout)
            return 1
    return 0 if hubo_datos else 1


if __name__ == "__main__":
    sys.exit(main())
