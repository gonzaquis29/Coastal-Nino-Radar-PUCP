"""Recolectores de fuentes oficiales -> data/processed/*.csv

Ética: User-Agent identificable, 2 s entre peticiones, solo páginas permitidas por robots.txt
(IGP prohíbe /api/ -> no se usa; sismos vienen de USGS, API pública). No se guardan autores ni datos personales.
"""
import re
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
import requests
from bs4 import BeautifulSoup

UA = {"User-Agent": "RadarDesastres-PUCP (proyecto academico)"}
PROC = Path("data/processed")
PAUSA = 2.0
MESES = {"enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6, "julio": 7, "agosto": 8,
         "septiembre": 9, "setiembre": 9, "octubre": 10, "noviembre": 11, "diciembre": 12}


def get(url, **kw):
    time.sleep(PAUSA)
    r = requests.get(url, headers=UA, timeout=40, **kw)
    r.raise_for_status()
    return r


def limpio(html: str) -> str:
    s = BeautifulSoup(html, "html.parser")
    for t in s(["script", "style", "nav", "footer"]):
        t.decompose()
    return re.sub(r"\s+", " ", s.get_text(" ", strip=True))


def fecha_es(txt: str):
    """'19 de Noviembre de 2026 a las 23:59' -> datetime (hora local Perú, sin tz) o None."""
    m = re.search(r"(\d{1,2})\s+de\s+([A-Za-zñÑ]+)\s+de\s+(\d{4})(?:\s+a\s+las\s+(\d{1,2}):(\d{2}))?", txt)
    if not m or m.group(2).lower() not in MESES:
        return None
    h, mi = (int(m.group(4)), int(m.group(5))) if m.group(4) else (0, 0)
    return datetime(int(m.group(3)), MESES[m.group(2).lower()], int(m.group(1)), h, mi)


# ---------------------------------------------------------------- USGS (sismos)
def sismos_usgs(dias: int = 45, mag_min: float = 3.5) -> pd.DataFrame:
    ini = (datetime.now(timezone.utc) - timedelta(days=dias)).strftime("%Y-%m-%d")
    url = ("https://earthquake.usgs.gov/fdsnws/event/1/query?format=geojson&orderby=time&limit=500"
           f"&minlatitude=-19&maxlatitude=0.5&minlongitude=-82&maxlongitude=-68&minmagnitude={mag_min}&starttime={ini}")
    feats = get(url).json()["features"]
    filas = [{"id": f["id"], "fecha_utc": datetime.fromtimestamp(f["properties"]["time"] / 1000, timezone.utc)
              .strftime("%Y-%m-%d %H:%M"), "mag": f["properties"]["mag"], "prof_km": f["geometry"]["coordinates"][2],
              "lat": f["geometry"]["coordinates"][1], "lon": f["geometry"]["coordinates"][0],
              "lugar": f["properties"]["place"], "url": f["properties"]["url"]} for f in feats]
    df = pd.DataFrame(filas)
    df.to_csv(PROC / "sismos.csv", index=False, encoding="utf8")
    return df


# ---------------------------------------------------------------- Senamhi (avisos meteorológicos)
SEN = "https://www.senamhi.gob.pe/"


def avisos_senamhi() -> pd.DataFrame:
    """Una sola página de detalle contiene TODOS los avisos vigentes; se parsea cada bloque 'Aviso N°### COLOR TÍTULO'."""
    lista = get(SEN + "?p=aviso-meteorologico").text
    anio = datetime.now().year
    # enlace propio de cada aviso: <a href="./?p=aviso-meteorologico-vigente&a=2026&b=29379...">479 (vigente)
    enlaces = {int(n): f"{SEN}?p=aviso-meteorologico-{t}&a={a}&b={b}&c=00&d=SENA" for t, a, b, n in re.findall(
        r'p=aviso-meteorologico-(vigente|detalle)&(?:amp;)?a=(\d{4})&(?:amp;)?b=(\d+)[^"]*">\s*(\d+)\s*(?:\(|</td|<)', lista) if int(a) == anio}
    b = max(int(x) for x in re.findall(rf"a={anio}&(?:amp;)?b=(\d+)", lista))
    url = f"{SEN}?p=aviso-meteorologico-detalle&a={anio}&b={b}&c=00&d=SENA"
    t = limpio(get(url).text)
    marcas = list(re.finditer(r"Aviso N°(\d+)\s+(AMARILLO|NARANJA|ROJO)\s+", t))
    vistos, filas = set(), []
    for k, m in enumerate(marcas):
        num = int(m.group(1))
        if num in vistos:
            continue
        vistos.add(num)
        bloque = t[m.end(): marcas[k + 1].start() if k + 1 < len(marcas) else len(t)]
        i = bloque.find("Fecha de emisi")
        ini = re.search(r"Inicio del evento:\s*(.*?)\s*Fecha de emisi", bloque)
        fin = re.search(r"Fin del evento:\s*(.*?)\s*Periodo", bloque)
        emi = re.search(r"Fecha de emisi.n:\s*(.*?)\s*Inicio", bloque)
        texto = re.search(r"(El SENAMHI.*)", bloque)
        texto = re.sub(r"(\d{1,2} de [A-Za-z]+\s*)+$", "", texto.group(1)).strip() if texto else ""
        filas.append({"id": f"senamhi-{num}", "titulo": bloque[:i].strip(), "publicado": fecha_es(emi.group(1)) if emi else None,
                      "inicio": fecha_es(ini.group(1)) if ini else None, "fin": fecha_es(fin.group(1)) if fin else None,
                      "nivel": m.group(2).lower(), "texto": texto[:2500], "url": enlaces.get(num, url)})
    df = pd.DataFrame(filas)
    df.to_csv(PROC / "senamhi.csv", index=False, encoding="utf8")
    return df

# ---------------------------------------------------------------- INDECI (notas de prensa en gob.pe)
GOB = "https://www.gob.pe"


def notas_indeci(maximo: int = 20) -> pd.DataFrame:
    lista = get(GOB + "/institucion/indeci/noticias").text
    rutas = list(dict.fromkeys(re.findall(r'href="(/institucion/indeci/noticias/\d+-[^"]+)"', lista)))[:maximo]
    filas = []
    for ruta in rutas:
        html = get(GOB + ruta).text
        s = BeautifulSoup(html, "html.parser")
        h1 = s.find("h1")
        t = limpio(html)
        tit = h1.get_text(" ", strip=True) if h1 else ""
        ini = t.rfind(tit) + len(tit) if tit and t.rfind(tit) >= 0 else 0  # última aparición = el h1 (antes hay migas de pan)
        cuerpo = t[ini:].strip()
        for corte in ("Imprimir", "Compartir", "Documentos", "Noticias relacionadas", "Descargar", "Ir al inicio"):
            j = cuerpo.find(corte, 200)
            if j > 0:
                cuerpo = cuerpo[:j]
        filas.append({"id": "indeci-" + ruta.split("/")[-1].split("-")[0],
                      "titulo": h1.get_text(" ", strip=True) if h1 else ruta,
                      "publicado": fecha_es(t[:3000]), "texto": cuerpo[:4000], "url": GOB + ruta})
    df = pd.DataFrame(filas)
    df.to_csv(PROC / "indeci.csv", index=False, encoding="utf8")
    return df
