"""Lectura de las páginas del Senamhi: tabla de avisos, panel de detalle y mapa por día."""

import re
from urllib.parse import parse_qs, urlsplit

from lxml import html

from radar.comun.texto import fecha_hora_es, norm, sin_tildes

COLUMNAS_TABLA = 7  # Aviso, Nro., Emisión, Inicio, Fin, Duración, Nivel


def leer_tabla(contenido):
    """Filas de la tabla de ?p=aviso-meteorologico (año, b, número, estado, título, fechas, duración y nivel)."""
    filas = []
    for tr in html.fromstring(contenido).xpath("//table[@id='table_id']/tbody/tr"):
        celdas = [norm(td.text_content()) for td in tr.xpath("./td")]
        enlace = tr.xpath("./td[1]//a/@href")
        if len(celdas) < COLUMNAS_TABLA or not enlace:
            continue
        q = {k: v[0] for k, v in parse_qs(urlsplit(enlace[0]).query).items()}
        m = re.match(r"(\d+)\s*(?:\((\w+)\))?", celdas[1])
        if not (q.get("a", "").isdigit() and q.get("b", "").isdigit() and m):
            continue
        filas.append(
            {
                "anio": q["a"],
                "b": q["b"],
                "numero": int(m.group(1)),
                "estado_tabla": (m.group(2) or "").lower(),
                "titulo": celdas[0],
                "emision": celdas[2],
                "inicio": celdas[3],
                "fin": celdas[4],
                "duracion": celdas[5],
                "nivel": celdas[6],
            }
        )
    return filas


def panel_aviso(contenido, fila):
    """Panel del aviso en la página de detalle: id tabs-<número><año> si está vigente, tabs-<b><año> si no."""
    doc = html.fromstring(contenido)
    panel = doc.xpath(f"//div[@id='tabs-{fila['numero']}{fila['anio']}']") or doc.xpath(
        f"//div[@id='tabs-{fila['b']}{fila['anio']}']"
    )
    return panel[0] if panel else None


def mapas_del_panel(panel):
    """[(número de mapa, nivel del día)] según los iframes del panel."""
    mapas = {}
    for src in panel.xpath(".//iframe[contains(@src,'index.php')]/@src"):
        q = parse_qs(urlsplit(src).query)
        if q.get("mp", [""])[0].isdigit():
            mapas[int(q["mp"][0])] = q.get("nl", [""])[0]
    return sorted(mapas.items())


def leer_detalle(contenido, fila):
    """Campos y textos del aviso; None si la página no trae su panel."""
    panel = panel_aviso(contenido, fila)
    if panel is None:
        return None
    titulo_nivel = norm(panel.xpath(".//h2")[0].text_content()) if panel.xpath(".//h2") else ""
    fechas = [norm(x.text_content()) for x in panel.xpath(".//span[contains(@class,'text-info')]")]
    emision = [
        norm(x.text_content()) for x in panel.xpath(".//strong[contains(.,'emisi')]/../following-sibling::span[1]")
    ]
    generales = [
        norm(x.text_content())
        for x in panel.xpath(".//div[@class='col-lg-12 col-md-12 col-sm-12 col-xs-12']")
        if re.match(r"El Senamhi informa", norm(x.text_content()), re.I)
    ]
    dias = [norm(x.text_content()) for x in panel.xpath(".//div[starts-with(@id,'v-pills-tab-')]//p")]
    m = re.match(r"Aviso N°\s*(\d+)\s+(\w+)", titulo_nivel)
    return {
        "numero": int(m.group(1)) if m else None,
        "nivel": m.group(2) if m else None,
        "titulo": " ".join(norm(x.text_content()) for x in panel.xpath(".//h1")),
        "emision": fecha_hora_es(emision[0]) if emision else None,
        "inicio": fecha_hora_es(fechas[0]) if fechas else None,
        "fin": fecha_hora_es(fechas[1]) if len(fechas) > 1 else None,
        "general": generales[0] if generales else "",
        "dias": [t for t in dias if t],
        "mapas": mapas_del_panel(panel),
    }


def leer_mapa(contenido):
    """Fecha y departamentos de posible afectación de un mapa diario."""
    texto = norm(html.fromstring(contenido).text_content())
    fecha = re.search(r"Fecha:\s*\w+\s*,\s*(\d{1,2} de \w+ de \d{4})", texto)
    deps = re.search(r"DEPARTAMENTOS DE POSIBLE AFECTACI[ÓO]N:\s*(.*?)\s*PROVINCIAS", texto)
    return {
        "fecha": fecha_hora_es(fecha.group(1)) if fecha else None,
        "deps": sorted({sin_tildes(x.strip()).upper() for x in deps.group(1).split(",") if x.strip()}) if deps else [],
    }
