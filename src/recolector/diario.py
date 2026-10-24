"""Recolección diaria de direcciones de notas (definición en docs/recoleccion/diaria.md).

Uso: python src/recolector/diario.py --persona joseph [--prueba] [--publicar]
"""
import argparse
import csv
import datetime as dt
import re
import subprocess
import sys
import time
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlsplit

import requests
from lxml import etree, html

RAIZ = Path(__file__).resolve().parents[2]
DIR_URLS = RAIZ / "data" / "urls"
LIMA = dt.timezone(dt.timedelta(hours=-5))  # el Perú no tiene horario de verano
INICIO = "2026-01-01"
UA = "CoastalNinoRadar-PUCP/0.1 (proyecto academico INF656 PUCP; +https://github.com/gonzaquis29/Coastal-Nino-Radar-PUCP)"
TOKEN_UA = "coastalninoradar-pucp"
NS = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9",
      "n": "http://www.google.com/schemas/sitemap-news/0.9"}
COLUMNAS = ["url", "medio", "id", "fecha", "tipo_fecha", "seccion", "origen", "recolectado"]
COLUMNAS_SITEMAPS = ["sitemap", "http", "entradas", "mas_antigua", "mas_reciente", "ventana_h", "recolectado"]
ARCHIVO_NOTAS = re.compile(r"^\d{4}-\d{2}-\d{2}_[a-z]+\.csv$")
PAUSA = 1.0  # segundos entre peticiones al mismo host
PARSER_XML = etree.XMLParser(resolve_entities=False, no_network=True)
AHORA = dt.datetime.now(LIMA).replace(microsecond=0)


# ---------------------------------------------------------------- robots.txt

def parsear_robots(texto):
    """Grupos de robots.txt: [{"agentes": [...], "reglas": [(permite, patron)]}]."""
    grupos, actual, en_reglas = [], None, False
    for linea in texto.splitlines():
        linea = linea.split("#", 1)[0].strip()
        if ":" not in linea:
            continue
        clave, valor = (x.strip() for x in linea.split(":", 1))
        clave = clave.lower()
        if clave == "user-agent":
            if actual is None or en_reglas:
                actual = {"agentes": [], "reglas": []}
                grupos.append(actual)
                en_reglas = False
            actual["agentes"].append(valor.lower())
        elif clave in ("allow", "disallow") and actual is not None:
            en_reglas = True
            if valor:
                actual["reglas"].append((clave == "allow", valor))
    return grupos


def reglas_para(grupos, token=TOKEN_UA):
    """Reglas del grupo que nombra a nuestro user-agent; si no hay, las de '*'."""
    propias = [g for g in grupos if any(a != "*" and a in token for a in g["agentes"])]
    elegidos = propias or [g for g in grupos if "*" in g["agentes"]]
    return [r for g in elegidos for r in g["reglas"]]


def _patron_a_regex(patron):
    fin = patron.endswith("$")
    cuerpo = re.escape(patron[:-1] if fin else patron).replace(r"\*", ".*")
    return re.compile(cuerpo + ("$" if fin else ""))


def permitido(reglas, ruta):
    """Gana la regla más larga que coincide; en empate, Allow (como Google)."""
    largo, permite = -1, True
    for es_allow, patron in reglas:
        if _patron_a_regex(patron).match(ruta) and (len(patron) > largo or (len(patron) == largo and es_allow)):
            largo, permite = len(patron), es_allow
    return permite


# ---------------------------------------------------------------- HTTP

class Bloqueado(Exception):
    pass


class Cliente:
    def __init__(self):
        self.sesion = requests.Session()
        self.sesion.headers["User-Agent"] = UA
        self.ultimo = {}
        self.robots = {}  # host -> (reglas, sitemaps declarados)

    def _esperar(self, host):
        falta = PAUSA - (time.monotonic() - self.ultimo.get(host, 0))
        if falta > 0:
            time.sleep(falta)
        self.ultimo[host] = time.monotonic()

    def _pedir(self, url, **kw):
        host = urlsplit(url).netloc
        for intento in range(3):
            self._esperar(host)
            try:
                r = self.sesion.get(url, timeout=60, **kw)
            except (requests.ConnectionError, requests.Timeout):
                if intento == 2:
                    raise
                time.sleep(5 * (intento + 1))
                continue
            reintentar = r.status_code >= 500 or (r.status_code == 429 and intento == 0)
            if reintentar and intento < 2:
                espera = r.headers.get("Retry-After", "")
                time.sleep(min(int(espera), 120) if espera.isdigit() else 5 * (intento + 1))
                continue
            return r
        return r

    def robots_de(self, host):
        if host not in self.robots:
            r = self._pedir(f"https://{host}/robots.txt")
            if r.status_code >= 500:
                raise Bloqueado(f"robots.txt de {host} respondió {r.status_code}")
            texto = r.text if r.status_code == 200 else ""
            sitemaps = re.findall(r"(?im)^\s*sitemap:\s*(\S+)", texto)
            self.robots[host] = (reglas_para(parsear_robots(texto)), sitemaps)
        return self.robots[host]

    def get(self, url, **kw):
        partes = urlsplit(url)
        ruta = partes.path + ("?" + partes.query if partes.query else "")
        if not permitido(self.robots_de(partes.netloc)[0], ruta):
            raise Bloqueado(f"robots.txt no permite {url}")
        r = self._pedir(url, **kw)
        r.raise_for_status()
        return r


# ---------------------------------------------------------------- fechas

def a_lima(texto):
    """ISO 8601 con zona → −05:00. Sin zona se asume UTC (solo se usa con date_gmt)."""
    texto = (texto or "").strip()
    if not texto:
        return ""
    fecha = dt.datetime.fromisoformat(texto.replace("Z", "+00:00"))
    if fecha.tzinfo is None:
        fecha = fecha.replace(tzinfo=dt.timezone.utc)
    return fecha.astimezone(LIMA).isoformat(timespec="seconds")


def antes_de_inicio(fecha):
    return bool(fecha) and fecha[:10] < INICIO


# ---------------------------------------------------------------- recolección

class Fuente:
    """Junta las filas de un medio y el registro de cada sitemap leído."""

    def __init__(self, medio, cliente):
        self.medio, self.cli = medio, cliente
        self.filas = {}      # clave -> fila
        self.registro = []   # filas del CSV de sitemaps
        self.fallos = []
        self.cobertura = []  # (sitemap, inicio de su ventana) para la alerta de hueco

    def agregar(self, url, ident, fecha, tipo, seccion, origen):
        if antes_de_inicio(fecha):
            return
        clave = ident or url
        fila = self.filas.get(clave)
        if fila is None:
            self.filas[clave] = {"url": url, "medio": self.medio, "id": ident, "fecha": fecha,
                                 "tipo_fecha": tipo if fecha else "", "seccion": {seccion} if seccion else set(),
                                 "origen": origen, "recolectado": AHORA.isoformat()}
            return
        if fecha and fila["tipo_fecha"] != "publicacion" and tipo == "publicacion":
            fila["fecha"], fila["tipo_fecha"] = fecha, tipo
        elif fecha and not fila["fecha"]:
            fila["fecha"], fila["tipo_fecha"] = fecha, tipo
        if seccion:
            fila["seccion"].add(seccion)

    def registrar(self, nombre, http, fechas, cobertura=False):
        fechas = sorted(f for f in fechas if f)
        ventana = ""
        if fechas:
            quinta = dt.datetime.fromisoformat(fechas[min(4, len(fechas) - 1)])
            ventana = round((AHORA - quinta).total_seconds() / 3600, 1)
            if cobertura:
                self.cobertura.append((nombre, quinta))
        self.registro.append({"sitemap": f"{self.medio}:{nombre}", "http": http, "entradas": len(fechas),
                              "mas_antigua": fechas[0] if fechas else "", "mas_reciente": fechas[-1] if fechas else "",
                              "ventana_h": ventana, "recolectado": AHORA.isoformat()})

    def fallo(self, nombre, error):
        http = getattr(getattr(error, "response", None), "status_code", "")
        self.registro.append({"sitemap": f"{self.medio}:{nombre}", "http": http or "error", "entradas": 0,
                              "mas_antigua": "", "mas_reciente": "", "ventana_h": "", "recolectado": AHORA.isoformat()})
        self.fallos.append(f"{nombre}: {type(error).__name__} {error}"[:200])

    def sitemap(self, url, nombre):
        """Entradas (loc, publication_date, lastmod) de un urlset; None si falla."""
        try:
            r = self.cli.get(url)
            raiz = etree.fromstring(r.content, PARSER_XML)
        except (requests.RequestException, Bloqueado, etree.XMLSyntaxError) as e:
            self.fallo(nombre, e)
            return None
        entradas = []
        for u in raiz.findall("s:url", NS):
            loc = (u.findtext("s:loc", namespaces=NS) or "").strip()
            pub = (u.findtext("n:news/n:publication_date", namespaces=NS) or "").strip()
            mod = (u.findtext("s:lastmod", namespaces=NS) or "").strip()
            if loc:
                entradas.append((loc, a_lima(pub), a_lima(mod)))
        return r.status_code, entradas

    def indice(self, url, nombre):
        try:
            raiz = etree.fromstring(self.cli.get(url).content, PARSER_XML)
        except (requests.RequestException, Bloqueado, etree.XMLSyntaxError) as e:
            self.fallo(nombre, e)
            return []
        return [(e.text or "").strip() for e in raiz.iter("{%s}loc" % NS["s"])]


def andina(f):
    base = "https://andina.pe/agencia/"
    secciones = [u for u in f.indice(base + "sitemap.xml", "sitemap.xml") if "/sitemap-seccion-" in u]
    for url in [base + "news-sitemap.xml", base + "sitemap-ultimo.xml"] + secciones:
        nombre = url.rsplit("/", 1)[1]
        leido = f.sitemap(url, nombre)
        if leido is None:
            continue
        http, entradas = leido
        m = re.search(r"sitemap-seccion-(.+?)-\d+\.xml$", nombre)
        seccion = m.group(1) if m else ""
        es_news = nombre == "news-sitemap.xml"
        for loc, pub, mod in entradas:
            nota = re.match(r"https://andina\.pe/agencia/noticia-.*-(\d+)\.aspx$", loc)
            if nota:
                f.agregar(loc, nota.group(1), pub or mod, "publicacion" if pub else "modificacion", seccion, f"andina:{nombre}")
        f.registrar(nombre, http, [p or m for _, p, m in entradas], cobertura=nombre == "sitemap-ultimo.xml")


def rpp(f):
    web = f.indice("https://rpp.pe/sitemap/web", "sitemap/web")
    declarados = [u for u in f.cli.robots_de("rpp.pe")[1] if u.startswith("https://rpp.pe/sitemap/web/")]
    urls = ["https://rpp.pe/sitemap/news"] + list(dict.fromkeys(web + declarados))
    for url in urls:
        nombre = url.replace("https://rpp.pe/sitemap/", "")
        leido = f.sitemap(url, nombre)
        if leido is None:
            continue
        http, entradas = leido
        for loc, pub, mod in entradas:
            m = re.search(r"-(noticias?|live)-(\d+)$", loc)
            ident = f"{'live' if m.group(1) == 'live' else 'noticia'}-{m.group(2)}" if m else ""
            partes = urlsplit(loc).path.strip("/").split("/")
            f.agregar(loc, ident, pub or mod, "publicacion" if pub else "modificacion", "/".join(partes[:-1]), f"rpp:{nombre}")
        f.registrar(nombre, http, [p or m for _, p, m in entradas], cobertura=nombre.startswith("web/"))


def exitosa(f):
    base = "https://www.exitosanoticias.pe/"
    mes = AHORA.date().replace(day=1)
    anterior = (mes - dt.timedelta(days=1)).replace(day=1)
    nombres = ["sitemapNews.xml", f"sitemapNoticias{anterior:%Y%m}.xml", f"sitemapNoticias{mes:%Y%m}.xml"]
    for nombre in nombres:
        try:
            r = f.cli.get(base + nombre)
        except requests.HTTPError as e:
            if e.response.status_code == 404 and nombre.endswith(f"{mes:%Y%m}.xml"):
                f.registrar(nombre, 404, [])  # el mensual del mes nuevo aún no existe
            else:
                f.fallo(nombre, e)
            continue
        except (requests.RequestException, Bloqueado) as e:
            f.fallo(nombre, e)
            continue
        try:
            raiz = etree.fromstring(r.content, PARSER_XML)
        except etree.XMLSyntaxError as e:
            f.fallo(nombre, e)
            continue
        fechas = []
        for u in raiz.findall("s:url", NS):
            loc = (u.findtext("s:loc", namespaces=NS) or "").strip()
            pub = a_lima(u.findtext("n:news/n:publication_date", namespaces=NS))
            m = re.search(r"-(n\d+)$", loc)
            if not m:
                continue
            fechas.append(pub)
            f.agregar(loc, m.group(1), pub, "publicacion", urlsplit(loc).path.strip("/").split("/")[0], f"exitosa:{nombre}")
        if fechas and any(fechas):
            f.registrar(nombre, r.status_code, fechas)
        else:  # el mensual no trae fechas: se registra solo el número de entradas
            f.registro.append({"sitemap": f"exitosa:{nombre}", "http": r.status_code, "entradas": len(fechas),
                               "mas_antigua": "", "mas_reciente": "", "ventana_h": "", "recolectado": AHORA.isoformat()})


def eltiempo(f):
    desde = (AHORA - dt.timedelta(days=10)).replace(tzinfo=None).isoformat()
    filas, pagina, paginas = [], 1, 1
    try:
        while pagina <= paginas:
            r = f.cli.get("https://eltiempo.pe/wp-json/wp/v2/posts",
                          params={"per_page": 100, "page": pagina, "after": desde, "_fields": "id,link,date_gmt"})
            paginas = int(r.headers.get("X-WP-TotalPages", 1))
            filas += r.json()
            pagina += 1
    except (requests.RequestException, Bloqueado, ValueError) as e:
        f.fallo("api", e)
        leido = f.sitemap("https://eltiempo.pe/news.xml", "news.xml")
        if leido is None:
            return
        http, entradas = leido
        for loc, pub, mod in entradas:
            f.agregar(loc, "", pub or mod, "publicacion" if pub else "modificacion",
                      urlsplit(loc).path.strip("/").split("/")[0], "eltiempo:news.xml")
        f.registrar("news.xml", http, [p or m for _, p, m in entradas], cobertura=True)
        return
    fechas = []
    for p in filas:
        fecha = a_lima(p["date_gmt"])
        fechas.append(fecha)
        f.agregar(p["link"], str(p["id"]), fecha, "publicacion", urlsplit(p["link"]).path.strip("/").split("/")[0], "eltiempo:api")
    f.registrar("api", 200, fechas)


def enfen(f):
    tipos = ["comunicado-oficial", "informe-tecnico", "nota-tecnica", "nota-de-prensa"]
    for nombre in ["wpdmpro-sitemap.xml", "post-sitemap.xml"]:
        leido = f.sitemap("https://enfen.imarpe.gob.pe/" + nombre, nombre)
        if leido is None:
            continue
        http, entradas = leido
        for loc, _, mod in entradas:
            m = re.match(r"https://enfen\.imarpe\.gob\.pe/(?:download|\d{4}/\d{2}/\d{2})/([^/]+)/?$", loc)
            if not m:
                continue
            slug = m.group(1)
            tipo = "entrada" if "/download/" not in loc else next((t for t in tipos if slug.startswith(t)), "otro")
            f.agregar(loc, slug, mod, "modificacion", tipo, f"enfen:{nombre}")
        f.registrar(nombre, http, [m for _, _, m in entradas])


def senamhi(f):
    try:
        r = f.cli.get("https://www.senamhi.gob.pe/?p=aviso-meteorologico")
        doc = html.fromstring(r.content)
    except (requests.RequestException, Bloqueado, etree.ParserError) as e:
        f.fallo("aviso-meteorologico", e)
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
        url = "https://www.senamhi.gob.pe/?" + urlencode({k: q[k] for k in ["p", "a", "b", "c", "d"] if k in q})
        fechas.append(emision)
        f.agregar(url, f"{q['a']}-{q['b']}", emision, "emision", "aviso", "senamhi:aviso-meteorologico")
    f.registrar("aviso-meteorologico", r.status_code, [x + "T00:00:00-05:00" for x in fechas if x >= INICIO])


FUENTES = {"andina": andina, "rpp": rpp, "exitosa": exitosa, "eltiempo": eltiempo, "enfen": enfen, "senamhi": senamhi}
PUBLICAN_A_DIARIO = {"andina", "rpp", "exitosa", "eltiempo"}
RECUPERACION = {"andina": "número de nota (noticia.aspx?id=N)", "rpp": "archivo por fecha (/archivo/<sección>/<fecha>)",
                "eltiempo": "API REST con after"}


# ---------------------------------------------------------------- archivos

def leer_existentes():
    """Claves y direcciones ya recolectadas, y la última fecha de recolección."""
    claves, urls, ultima = set(), set(), None
    for ruta in sorted(DIR_URLS.glob("*.csv")):
        if not ARCHIVO_NOTAS.match(ruta.name):
            continue
        with open(ruta, encoding="utf-8", newline="") as fh:
            for fila in csv.DictReader(fh):
                if fila.get("id"):
                    claves.add((fila["medio"], fila["id"]))
                urls.add(fila["url"])
                if fila.get("recolectado"):
                    fecha = dt.datetime.fromisoformat(fila["recolectado"])
                    ultima = max(ultima, fecha) if ultima else fecha
    return claves, urls, ultima


def anexar(ruta, columnas, filas):
    nuevo = not ruta.exists()
    ruta.parent.mkdir(parents=True, exist_ok=True)
    with open(ruta, "a", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=columnas, lineterminator="\n")
        if nuevo:
            w.writeheader()
        w.writerows(filas)


def git(*args):
    return subprocess.run(["git", *args], cwd=RAIZ, check=True, capture_output=True, text=True)


# ---------------------------------------------------------------- principal

def main(argv=None):
    ap = argparse.ArgumentParser(description="Recolección diaria de direcciones de notas.")
    ap.add_argument("--persona", required=True, choices=["gonzalo", "joseph"])
    ap.add_argument("--prueba", action="store_true", help="no escribe archivos ni toca git")
    ap.add_argument("--publicar", action="store_true", help="git pull, commit y push de los archivos de esta ejecución")
    args = ap.parse_args(argv)
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

    if args.publicar and not args.prueba:
        try:
            git("pull", "--ff-only")
        except subprocess.CalledProcessError as e:
            print("git pull falló; no se recolecta.\n" + (e.stderr or e.stdout))
            return 1

    claves, urls, ultima = leer_existentes()
    cli = Cliente()
    nuevas, registro, resumen = [], [], []
    for medio, funcion in FUENTES.items():
        f = Fuente(medio, cli)
        try:
            funcion(f)
        except Exception as e:  # una fuente que falla no detiene a las demás
            f.fallos.append(f"{type(e).__name__}: {e}"[:200])
        propias = []
        for fila in f.filas.values():
            if (medio, fila["id"]) in claves or fila["url"] in urls:
                continue
            fila["seccion"] = "|".join(sorted(fila["seccion"]))
            propias.append(fila)
            claves.add((medio, fila["id"]))
            urls.add(fila["url"])
        nuevas += propias
        registro += f.registro
        fechas = sorted(x["fecha"] for x in f.filas.values() if x["fecha"])
        resumen.append((f, len(f.filas), propias, fechas[0][:10] if fechas else "-"))

    # resumen
    print(f"\nRecolección {AHORA.isoformat()} ({args.persona}){' [PRUEBA]' if args.prueba else ''}")
    print(f"{'medio':10}{'sitemaps':>10}{'vistas':>8}{'nuevas':>8}  más antigua")
    for f, vistas, propias, antigua in resumen:
        ok = sum(1 for r in f.registro if r["http"] in (200, 404))
        print(f"{f.medio:10}{ok:>5}/{len(f.registro):<4}{vistas:>8}{len(propias):>8}  {antigua}")
    print(f"{'total':10}{'':>10}{sum(v for _, v, _, _ in resumen):>8}{len(nuevas):>8}")

    alertas = []
    for f, _, propias, _ in resumen:
        for falla in f.fallos:
            alertas.append(f"FALLO {f.medio} · {falla}")
    if ultima:
        horas = (AHORA - ultima).total_seconds() / 3600
        if horas > 36:
            alertas.append(f"Pasaron {horas:.0f} h desde la última ejecución (máximo 48 h).")
        for f, _, propias, _ in resumen:
            for nombre, inicio in f.cobertura:
                if inicio > ultima:
                    alertas.append(f"HUECO {f.medio}:{nombre} empieza {inicio:%d-%m %H:%M}, después de la última "
                                   f"recolección ({ultima:%d-%m %H:%M}). Recuperar por {RECUPERACION.get(f.medio, '-')}.")
            if f.medio in PUBLICAN_A_DIARIO and not propias and horas > 12:
                alertas.append(f"Sin novedades en {f.medio}.")
            if f.medio == "enfen":
                for fila in propias:
                    alertas.append(f"Nuevo documento del ENFEN: {fila['id']}")
    print("\n" + ("\n".join("- " + a for a in alertas) if alertas else "Sin alertas."))

    if args.prueba:
        return 0 if any(v for _, v, _, _ in resumen) else 1

    base = f"{AHORA:%Y-%m-%d}_{args.persona}"
    escritos = []
    if nuevas:
        anexar(DIR_URLS / f"{base}.csv", COLUMNAS, nuevas)
        escritos.append(DIR_URLS / f"{base}.csv")
    anexar(DIR_URLS / f"{base}_sitemaps.csv", COLUMNAS_SITEMAPS, registro)
    escritos.append(DIR_URLS / f"{base}_sitemaps.csv")
    print("\nEscrito: " + ", ".join(str(p.relative_to(RAIZ)) for p in escritos))

    if args.publicar:
        try:
            git("add", *[str(p.relative_to(RAIZ)) for p in escritos])
            git("commit", "-m", f"datos: recolección {AHORA:%Y-%m-%d} ({args.persona})")
            try:
                git("push")
            except subprocess.CalledProcessError:
                git("pull", "--rebase")
                git("push")
            print("Publicado.")
        except subprocess.CalledProcessError as e:
            print("git falló:\n" + (e.stderr or e.stdout))
            return 1
    return 0 if any(v for _, v, _, _ in resumen) else 1


if __name__ == "__main__":
    sys.exit(main())
