"""Lectura de las fuentes del mapa con el cliente del proyecto (robots.txt, ritmo y hosts permitidos)."""

import datetime as dt
import re

import lxml.html

from radar import config
from radar.monitoreo import vocabulario as vo

MESES = ("enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre",
         "noviembre", "diciembre")  # fmt: skip
NOTAS_INDECI = 20
DIAS_SISMOS = 30
MAGNITUD_MINIMA = 3.5
LARGO_TEXTO_AVISO = 2500
FECHA_ES = re.compile(r"(\d{1,2})\s+de\s+([a-zñ]+)\s+de\s+(\d{4})(?:\s+a\s+las\s+(\d{1,2}):(\d{2}))?", re.I)
MARCA_AVISO = re.compile(r"Aviso N°(\d+)\s+(AMARILLO|NARANJA|ROJO)\s+")
ENLACE_AVISO = re.compile(
    r'p=aviso-meteorologico-(vigente|detalle)&(?:amp;)?a=(\d{4})&(?:amp;)?b=(\d+)[^"]*">\s*(\d+)\s*(?:\(|<)'
)
CORTES_INDECI = ("Imprimir", "Compartir", "Documentos", "Noticias relacionadas", "Descargar", "Ir al inicio")


def texto_visible(pagina):
    arbol = lxml.html.fromstring(pagina)
    for nodo in arbol.xpath("//script|//style|//nav|//footer"):
        nodo.drop_tree()
    return re.sub(r"\s+", " ", " ".join(arbol.itertext())).strip()


def fecha_es(texto):
    """'19 de Noviembre de 2026 a las 23:59' -> '2026-11-19T23:59:00'; '' si no hay fecha."""
    m = FECHA_ES.search(texto or "")
    mes = m.group(2).lower().replace("setiembre", "septiembre") if m else ""
    if mes not in MESES:
        return ""
    hora, minuto = int(m.group(4) or 0), int(m.group(5) or 0)
    return dt.datetime(int(m.group(3)), MESES.index(mes) + 1, int(m.group(1)), hora, minuto).isoformat()


def _campo(bloque, inicio, fin):
    m = re.search(rf"{inicio}:\s*(.*?)\s*{fin}", bloque)
    return m.group(1) if m else ""


# ---------------------------------------------------------------- Senamhi


def leer_avisos(texto, enlaces, url):
    """Una página de detalle del Senamhi trae todos los avisos vigentes y próximos."""
    marcas = list(MARCA_AVISO.finditer(texto))
    avisos = {}
    for k, m in enumerate(marcas):
        numero = int(m.group(1))
        if numero in avisos:
            continue
        bloque = texto[m.end() : marcas[k + 1].start() if k + 1 < len(marcas) else len(texto)]
        titulo = bloque[: bloque.find("Fecha de emisi")].strip()
        cuerpo = re.search(r"El SENAMHI.*", bloque)
        cuerpo = re.sub(r"(\d{1,2} de [A-Za-z]+\s*)+$", "", cuerpo.group()).strip() if cuerpo else ""
        avisos[numero] = {
            "numero": numero,
            "peligro": vo.peligro(titulo),
            "titulo": titulo,
            "texto": cuerpo[:LARGO_TEXTO_AVISO],
            "nivel": m.group(2).lower(),
            "emision": fecha_es(_campo(bloque, r"Fecha de emisi.n", "Inicio"))[:10],
            "inicio": fecha_es(_campo(bloque, "Inicio del evento", "Fecha de emisi")),
            "fin": fecha_es(_campo(bloque, "Fin del evento", "Periodo")),
            "url": enlaces.get(numero, url),
        }
    return [a for a in avisos.values() if a["inicio"] and a["fin"]]


def avisos(cliente, anio):
    lista = cliente.get(config.URL_SENAMHI + "?p=aviso-meteorologico").text
    filas = [x for x in ENLACE_AVISO.findall(lista) if int(x[1]) == anio]
    if not filas:
        raise ValueError("la tabla de avisos del Senamhi no trae filas del año")
    enlaces = {
        int(n): f"{config.URL_SENAMHI}?p=aviso-meteorologico-{t}&a={a}&b={b}&c=00&d=SENA" for t, a, b, n in filas
    }
    ultimo = max(int(b) for _, _, b, _ in filas)
    url = f"{config.URL_SENAMHI}?p=aviso-meteorologico-detalle&a={anio}&b={ultimo}&c=00&d=SENA"
    return leer_avisos(texto_visible(cliente.get(url).text), enlaces, url)


# ---------------------------------------------------------------- INDECI


def leer_nota(pagina, url):
    h1 = lxml.html.fromstring(pagina).xpath("//h1")
    titulo = re.sub(r"\s+", " ", h1[0].text_content()).strip() if h1 else ""
    texto = texto_visible(pagina)
    cuerpo = texto[texto.rfind(titulo) + len(titulo) :] if titulo else texto
    for corte in CORTES_INDECI:
        j = cuerpo.find(corte, 200)
        cuerpo = cuerpo[:j] if j > 0 else cuerpo
    return {
        "titulo": titulo,
        "fecha": fecha_es(texto[:3000])[:10],
        "url": url,
        "peligro": vo.peligro(titulo),
        "departamentos": vo.departamentos_nombrados(f"{titulo}. {cuerpo}"),
        "recomendaciones": vo.recomendaciones(cuerpo),
    }


def notas_indeci(cliente):
    base = f"https://{config.HOST_GOB}"
    lista = cliente.get(f"{base}/institucion/indeci/noticias").text
    rutas = list(dict.fromkeys(re.findall(r'href="(/institucion/indeci/noticias/\d+-[^"]+)"', lista)))
    if not rutas:
        raise ValueError("la página del INDECI no trae notas")
    notas = [leer_nota(cliente.get(base + r).text, base + r) for r in rutas[:NOTAS_INDECI]]
    return [n for n in notas if n["titulo"] and n["fecha"] and n["peligro"] != vo.OTRO]


# ---------------------------------------------------------------- USGS


def lugar_es(lugar):
    """'9 km N of Carhuamayo, Peru' -> '9 km al N de Carhuamayo'."""
    lugar = re.sub(r", Peru$", "", lugar or "")
    return re.sub(r"(\d+ km) ([NSEW]+) of ", lambda m: f"{m[1]} al {m[2].replace('W', 'O')} de ", lugar)


def leer_sismos(geojson):
    salida = []
    for f in geojson["features"]:
        p, (lon, lat, profundidad) = f["properties"], f["geometry"]["coordinates"]
        momento = dt.datetime.fromtimestamp(p["time"] / 1000, config.LIMA)
        salida.append({"id": f["id"], "magnitud": round(p["mag"], 1), "lugar": lugar_es(p["place"]), "lat": lat,
                       "momento": momento.strftime("%Y-%m-%dT%H:%M:%S"), "lon": lon,
                       "profundidad": round(profundidad or 0), "url": p["url"]})  # fmt: skip
    return salida


def sismos(cliente, ahora):
    desde = (ahora - dt.timedelta(days=DIAS_SISMOS)).date().isoformat()
    parametros = {"format": "geojson", "orderby": "time", "limit": 500, "starttime": desde, "minlatitude": -19,
                  "minmagnitude": MAGNITUD_MINIMA, "maxlatitude": 0.5, "minlongitude": -82,
                  "maxlongitude": -68}  # fmt: skip
    return leer_sismos(cliente.get(f"https://{config.HOST_USGS}/fdsnws/event/1/query", params=parametros).json())
