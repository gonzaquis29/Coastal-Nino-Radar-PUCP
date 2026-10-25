"""Vías del histórico por medio y descarga de notas (definición en docs/noticias/definicion.md).

Cada medio guarda en data/raw/noticias/<medio>/ lo descubierto (lista.csv), las notas leídas (notas.csv y
enlaces.csv, sin el cuerpo) y su estado (estado.json). Todo se agrega fila por fila: si se corta, la siguiente
ejecución sigue donde quedó sin repetir peticiones ni duplicar filas.
"""

import datetime as dt
import logging
import re
import threading
from urllib.parse import urlsplit

import requests

from radar import config
from radar.comun.archivos import anexar_csv, leer_csv
from radar.comun.http import Bloqueado, HostSuspendido
from radar.comun.registro import describir
from radar.comun.texto import a_lima, ahora, sha1_corto
from radar.comun.xml import NS_SITEMAP, XMLMalFormado, leer_xml
from radar.noticias import esquemas, filtro, rasgos
from radar.noticias.nota import NotaInvalida, leer_api, leer_html, limpiar
from radar.recoleccion.urls import filas_de_notas

log = logging.getLogger(__name__)

LOTE_LISTA = 50  # filas descubiertas que se escriben juntas
LOTE_API = 100  # entradas por petición a la API de WordPress (máximo que permite)
MAX_INTENTOS = 3  # ejecuciones con error antes de dar por perdida una nota
ERRORES_RED = (requests.RequestException,)
DETENER = (Bloqueado, HostSuspendido)  # no se eluden bloqueos: ese medio se detiene en esta ejecución


class NoExiste(Exception):
    """La nota no existe (404) o no está publicada (Andina redirige a su portada)."""


def _dias(desde, hasta):
    for i in range((hasta - desde).days + 1):
        yield desde + dt.timedelta(days=i)


class Medio:
    nombre = ""

    def __init__(self, cliente, parar=None):
        self.cliente = cliente
        self.host = config.HOSTS_MEDIOS[self.nombre]
        self.dir = config.DIR_RAW_NOTICIAS / self.nombre
        self.parar = parar or threading.Event()
        self.lista = {f["id"]: f for f in leer_csv(self.dir / "lista.csv")}
        self.hechas = {f["id"] for f in leer_csv(self.dir / "notas.csv")}

    # ------------------------------------------------------------ lista
    def fila(self, ident, url, via, titulo="", seccion="", fecha="", http=""):
        return {
            "medio": self.nombre,
            "id": ident,
            "url": url,
            "titulo": titulo,
            "seccion": seccion,
            "fecha_lista": fecha,
            "via": via,
            "http": http,
        }

    def agregar(self, filas):
        nuevas = list({f["id"]: f for f in filas if f["id"] not in self.lista}.values())
        if nuevas:
            anexar_csv(self.dir / "lista.csv", esquemas.LISTA, nuevas)
            self.lista.update((f["id"], f) for f in nuevas)
        return len(nuevas)

    def id_de_diaria(self, fila):
        return fila["id"]

    def agregar_diaria(self):
        """Las notas de data/urls/ entran a la lista sin pedir nada (sus números son la misma clave)."""
        filas = []
        for f in filas_de_notas(self.nombre):
            ident = self.id_de_diaria(f)
            if ident:
                filas.append(self.fila(ident, f["url"], "diaria", seccion=f["seccion"], fecha=f["fecha"]))
        return self.agregar(filas)

    def descubrir(self, estado):
        raise NotImplementedError

    def notas(self):
        """Filas de la lista que tienen una nota detrás."""
        return [f for f in self.lista.values() if f["url"]]

    def candidatas(self):
        return [f for f in self.notas() if filtro.candidata_por(self.nombre, f["url"], f["titulo"])]

    # ------------------------------------------------------------ descarga
    def leer(self, fila):
        r = self.cliente.get(fila["url"])
        return leer_html(self.nombre, r.content, r.url, r.headers.get("Content-Type", ""))

    def descargar(self, filas):
        """(fila, campos o excepción) por cada fila; los bloqueos se propagan."""
        for fila in filas:
            if self.parar.is_set():
                return
            try:
                yield fila, self.leer(fila)
            except DETENER:
                raise
            except requests.HTTPError as e:
                codigo = getattr(e.response, "status_code", None)
                yield fila, NoExiste(f"HTTP {codigo}") if codigo in (404, 410) else e
            except (NoExiste, NotaInvalida, *ERRORES_RED, ValueError) as e:
                yield fila, e

    def procesar(self, filas, muestra, estado):
        """Descarga las filas que faltan y agrega sus notas y enlaces. Devuelve (leídas, sin nota, con error)."""
        pendientes = []
        for f in filas:
            previo = estado.get(f"nota:{f['id']}")
            if f["id"] in self.hechas or previo.get("estado") == "no_existe":
                continue
            if previo.get("intentos", 0) >= MAX_INTENTOS:
                continue
            pendientes.append(f)
        leidas = sin_nota = errores = 0
        for fila, resultado in self.descargar(pendientes):
            clave = f"nota:{fila['id']}"
            if isinstance(resultado, dict):
                nota, enlaces = filas_de_nota(self.nombre, fila, resultado, muestra)
                anexar_csv(self.dir / "notas.csv", esquemas.NOTAS, [nota])
                if enlaces:
                    anexar_csv(self.dir / "enlaces.csv", esquemas.ENLACES, enlaces)
                self.hechas.add(fila["id"])
                leidas += 1
            elif isinstance(resultado, NoExiste):
                estado.marcar(clave, {"estado": "no_existe", "detalle": str(resultado)})
                sin_nota += 1
            else:
                previo = estado.get(clave)
                estado.marcar(clave, {"estado": "error", "intentos": previo.get("intentos", 0) + 1})
                log.debug("%s %s: %s", self.nombre, fila["url"], describir(resultado))
                errores += 1
        return leidas, sin_nota, errores


# ---------------------------------------------------------------- Andina: número de nota


class Andina(Medio):
    nombre = "andina"
    NOTA = re.compile(r"^https://andina\.pe/agencia/noticia-[^/]+-(\d+)\.aspx$")

    def id_de_diaria(self, fila):
        return fila["id"] if int(fila["id"]) >= config.ANDINA_PRIMER_ID else ""

    def ultimo_id(self):
        """El histórico llega hasta el mayor número que vio la recolección diaria; de ahí en adelante, data/urls."""
        diarias = [int(f["id"]) for f in self.lista.values() if f["via"] == "diaria"]
        if not diarias:
            raise RuntimeError("no hay notas de Andina en data/urls/: correr antes la recolección diaria")
        return max(diarias)

    def descubrir(self, estado):
        pendientes = []
        try:
            for numero in range(config.ANDINA_PRIMER_ID, self.ultimo_id() + 1):
                if self.parar.is_set():
                    break
                ident = str(numero)
                if ident in self.lista:
                    continue
                url = f"https://{self.host}/agencia/noticia.aspx?id={numero}"
                try:
                    r = self.cliente.get(url, allow_redirects=False)
                    codigo, destino = r.status_code, r.headers.get("Location", "")
                except requests.HTTPError as e:
                    codigo, destino = getattr(e.response, "status_code", ""), ""
                except ERRORES_RED as e:
                    log.debug("andina %s: %s", numero, describir(e))
                    continue
                m = self.NOTA.match(destino)
                valida = codigo == 301 and m and m.group(1) == ident
                pendientes.append(self.fila(ident, destino if valida else "", "numero", http=codigo))
                if len(pendientes) >= LOTE_LISTA:
                    self.agregar(pendientes)
                    pendientes = []
        finally:
            self.agregar(pendientes)

    def leer(self, fila):
        r = self.cliente.get(fila["url"])
        if not self.NOTA.match(r.url):  # la segunda petición confirma: sin publicar redirige a /agencia/inicio
            raise NoExiste(f"no publicada ({r.url})")
        return leer_html(self.nombre, r.content, r.url, r.headers.get("Content-Type", ""))


# ---------------------------------------------------------------- RPP: archivo por fecha, paginado


class Rpp(Medio):
    nombre = "rpp"
    ITEM = re.compile(
        r'<h2 class="news__title">\s*<a href="(https://rpp\.pe/[^"]+)">\s*(.*?)\s*</a>.*?data-x="([^"]+)"', re.S
    )
    NUMERO = re.compile(r"-(noticias?|live)-(\d+)$")
    MAX_PAGINAS = 100  # ningún día de 2026 pasa de 15 páginas

    @classmethod
    def ident(cls, url):
        m = cls.NUMERO.search(url)
        return f"{'live' if m.group(1) == 'live' else 'noticia'}-{m.group(2)}" if m else ""

    def _items(self, fragmento, dia):
        filas = []
        for url, titulo, fecha in self.ITEM.findall(fragmento):
            if ident := self.ident(url):
                seccion = "/".join(urlsplit(url).path.strip("/").split("/")[:-1])
                filas.append(self.fila(ident, url, f"archivo:{dia}", limpiar(titulo), seccion, a_lima(fecha), 200))
        return filas

    def archivo(self, dia):
        """Todas las notas del archivo de un día: la primera página en HTML y luego page-1, page-2… en JSON."""
        base = f"https://{self.host}/archivo/{dia.isoformat()}"
        texto = self.cliente.get(base).content.decode("utf-8", "replace")
        inicio = texto.find('id="container-news"')
        filas = self._items(texto[inicio : texto.find("column-fixed", inicio)], dia) if inicio >= 0 else []
        pagina = 1
        while pagina and pagina <= self.MAX_PAGINAS and not self.parar.is_set():
            datos = self.cliente.get(f"{base}/page-{pagina}").json()
            nuevas = self._items(datos.get("html", ""), dia)
            filas += nuevas
            pagina = datos.get("nextPage") if nuevas else None
        return filas

    def descubrir(self, estado):
        for dia in _dias(config.INICIO, config.FIN_HISTORICO):
            if self.parar.is_set():
                return
            clave = f"dia:{dia.isoformat()}"
            if estado.get(clave):
                continue
            try:
                filas = self.archivo(dia)
            except DETENER:
                raise
            except (*ERRORES_RED, ValueError) as e:
                log.debug("rpp archivo %s: %s", dia, describir(e))
                continue
            self.agregar(filas)
            if not self.parar.is_set():
                estado.marcar(clave, {"notas": len(filas)})


# ---------------------------------------------------------------- Exitosa: sitemaps mensuales y huecos por número


class Exitosa(Medio):
    nombre = "exitosa"
    NUMERO = re.compile(r"-n(\d+)$")

    def _meses(self):
        mes = config.INICIO.replace(day=1)
        while mes <= config.FIN_HISTORICO:
            yield mes
            mes = (mes + dt.timedelta(days=32)).replace(day=1)

    def descubrir(self, estado):
        for mes in self._meses():
            clave = f"mes:{mes:%Y%m}"
            if estado.get(clave) or self.parar.is_set():
                continue
            try:
                raiz = leer_xml(self.cliente.get(f"https://{self.host}/sitemapNoticias{mes:%Y%m}.xml").content)
            except DETENER:
                raise
            except (*ERRORES_RED, XMLMalFormado) as e:
                log.debug("exitosa sitemap %s: %s", mes, describir(e))
                continue
            filas = []
            for u in raiz.findall("s:url", NS_SITEMAP):
                url = (u.findtext("s:loc", namespaces=NS_SITEMAP) or "").strip()
                if m := self.NUMERO.search(url):
                    filas.append(
                        self.fila(f"n{m.group(1)}", url, f"sitemap:{mes:%Y%m}", seccion=filtro.seccion_principal(url))
                    )
            self.agregar(filas)
            estado.marcar(clave, {"notas": len(filas)})
        if not estado.get("huecos") and not self.parar.is_set():
            self.huecos(estado)

    def huecos(self, estado):
        """Números sin nota en los sitemaps (el hueco del 31-may y saltos sueltos): /actualidad/x-nN responde
        301 hacia la nota o 404."""
        numeros = [int(i[1:]) for i, f in self.lista.items() if f["via"].startswith("sitemap")]
        if not numeros:
            return
        conocidos = {int(i[1:]) for i in self.lista}
        pendientes = []
        for numero in range(min(numeros), max(numeros) + 1):
            if numero in conocidos:
                continue
            if self.parar.is_set():
                self.agregar(pendientes)
                return
            try:
                r = self.cliente.get(f"https://{self.host}/actualidad/x-n{numero}", allow_redirects=False)
                codigo, destino = r.status_code, r.headers.get("Location", "")
            except requests.HTTPError as e:
                codigo, destino = getattr(e.response, "status_code", ""), ""
            except ERRORES_RED as e:
                log.debug("exitosa x-n%s: %s", numero, describir(e))
                continue
            valida = codigo == 301 and urlsplit(destino).netloc == self.host and destino.endswith(f"-n{numero}")
            seccion = filtro.seccion_principal(destino) if valida else ""
            pendientes.append(
                self.fila(f"n{numero}", destino if valida else "", "numero", seccion=seccion, http=codigo)
            )
        self.agregar(pendientes)
        estado.marcar("huecos", {"fecha": ahora().isoformat()})


# ---------------------------------------------------------------- El Tiempo: API REST de WordPress


class ElTiempo(Medio):
    nombre = "eltiempo"
    CAMPOS_LISTA = "id,link,date_gmt,title"
    CAMPOS_NOTA = "id,link,date_gmt,modified_gmt,title,excerpt,content"

    @property
    def api(self):
        return f"https://{self.host}/wp-json/wp/v2/posts"

    def descubrir(self, estado):
        if estado.get("api") or self.parar.is_set():
            return
        antes = (config.FIN_HISTORICO + dt.timedelta(days=1)).isoformat() + "T00:00:00"
        pagina, paginas = 1, 1
        while pagina <= paginas:
            if self.parar.is_set():
                return
            r = self.cliente.get(
                self.api,
                params={
                    "after": config.INICIO.isoformat() + "T00:00:00",
                    "before": antes,
                    "orderby": "date",
                    "order": "asc",
                    "per_page": LOTE_API,
                    "page": pagina,
                    "_fields": self.CAMPOS_LISTA,
                },
            )
            paginas = int(r.headers.get("X-WP-TotalPages", 1))
            self.agregar(
                self.fila(
                    str(e["id"]),
                    e["link"],
                    "api",
                    limpiar(e["title"]["rendered"]),
                    filtro.seccion_principal(e["link"]),
                    a_lima(e["date_gmt"]),
                    200,
                )
                for e in r.json()
            )
            pagina += 1
        estado.marcar("api", {"fecha": ahora().isoformat()})

    def descargar(self, filas):
        """De a 100 entradas por petición (include=…): el cuerpo viene en la API y no hace falta la página."""
        for i in range(0, len(filas), LOTE_API):
            if self.parar.is_set():
                return
            lote = filas[i : i + LOTE_API]
            try:
                r = self.cliente.get(
                    self.api,
                    params={
                        "include": ",".join(f["id"] for f in lote),
                        "per_page": LOTE_API,
                        "_fields": self.CAMPOS_NOTA,
                    },
                )
                entradas = {str(e["id"]): e for e in r.json()}
            except DETENER:
                raise
            except (*ERRORES_RED, ValueError) as e:
                for fila in lote:
                    yield fila, e
                continue
            for fila in lote:
                if fila["id"] not in entradas:
                    yield fila, NoExiste("no está en la API")
                    continue
                try:
                    yield fila, leer_api(entradas[fila["id"]])
                except (NotaInvalida, KeyError, ValueError) as e:
                    yield fila, e


MEDIOS = {m.nombre: m for m in (Andina, Rpp, Exitosa, ElTiempo)}


# ---------------------------------------------------------------- filas de salida


def filas_de_nota(medio, fila, campos, muestra):
    """Fila de notas.csv y filas de enlaces.csv. Aquí se usa el cuerpo por última vez: no se guarda."""
    cuerpo, resumen, titular = campos["cuerpo"], campos["resumen"], campos["titular"]
    texto = f"{resumen} {cuerpo}"
    menciones = rasgos.menciones(texto)
    en_inicio = rasgos.nino_en_inicio(resumen, cuerpo)
    enlaces = [
        {
            "medio": medio,
            "id": fila["id"],
            "url": u,
            "dominio": urlsplit(u).netloc.lower(),
            "oficial": rasgos.oficial(u),
            "comunicado": ":".join(p) if (p := rasgos.comunicado_de_enlace(u)) else "",
        }
        for u in campos["enlaces"]
    ]
    nota = {
        "medio": medio,
        "id": fila["id"],
        "url": fila["url"],
        "via": fila["via"],
        "candidata_por": filtro.candidata_por(medio, fila["url"], fila["titulo"]),
        "muestra": muestra,
        "titular": titular,
        "resumen": resumen,
        "fecha_publicacion": campos["fecha_publicacion"],
        "fecha_modificacion": campos["fecha_modificacion"],
        "fecha_creacion": campos["fecha_creacion"],
        "fuente_fecha": campos["fuente_fecha"],
        "fecha_dudosa": "",
        "seccion": campos["seccion"],
        "etiquetas": campos["etiquetas"],
        "terminos_titulo": filtro.terminos_en(fila["url"], fila["titulo"]),
        "n_palabras": campos["n_palabras"],
        "sin_texto": campos["sin_texto"],
        "resumen_en_cuerpo": campos["resumen_en_cuerpo"],
        "cuerpo_vs_ld": campos["cuerpo_vs_ld"],
        "menciones_nino": menciones,
        "menciona_nino": bool(menciones + rasgos.menciones(titular)),
        "nino_en_inicio": en_inicio,
        "sobre_nino": en_inicio or rasgos.menciones(titular) > 0,
        "terminos_cuerpo": rasgos.terminos_cuerpo(cuerpo),
        "actores": [f"{a}:{n}" for a, n in rasgos.actores(texto).items()],
        "comunicados": rasgos.comunicados(texto, campos["enlaces"]),
        "magnitudes": rasgos.magnitudes(texto),
        "n_enlaces": len(enlaces),
        "n_enlaces_oficiales": sum(e["oficial"] for e in enlaces),
        "sha1_cuerpo": sha1_corto(cuerpo),
        "recolectado": ahora().isoformat(),
    }
    return nota, enlaces
