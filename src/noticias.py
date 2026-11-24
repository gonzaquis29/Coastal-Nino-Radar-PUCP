"""Bloque 3 (MVP): titulares de Agencia Andina desde su news-sitemap -> data/processed/noticias.csv.

- Una sola petición (robots.txt de andina.pe: Allow: /, y declara el sitemap).
- Solo se guarda: id anónimo (hash de la URL), fecha, titular. Sin autores ni identificadores personales.
- Grupos de control por palabras clave (sin etiquetado manual):
    positivo = menciona ENFEN / "Niño costero" / "fenómeno El Niño"
    clima    = menciona lluvias, oleaje, Senamhi, huaico, etc. (tema cercano)
    negativo = ninguna de las anteriores (otros temas)
"""
import hashlib
import re
from pathlib import Path

import pandas as pd
import requests
from bs4 import BeautifulSoup

URL = "https://andina.pe/agencia/news-sitemap.xml"
UA = "RadarNinoCostero-PUCP (proyecto academico)"
OUT = Path("data/processed/noticias.csv")
POS = re.compile(r"enfen|ni[ñn]o costero|fen[óo]meno de? ?el ni[ñn]o|el ni[ñn]o", re.I)
CLIMA = re.compile(r"lluvia|oleaje|senamhi|huaico|inundaci|temperatura|calor|indeci|friaje|mar\b|caudal|r[ií]o", re.I)


def grupo(titulo: str) -> str:
    if POS.search(titulo):
        return "positivo"
    if CLIMA.search(titulo):
        return "clima"
    return "negativo"


def main():
    r = requests.get(URL, headers={"User-Agent": UA}, timeout=30)
    r.raise_for_status()
    soup = BeautifulSoup(r.content, "xml")
    filas = []
    for u in soup.find_all("url"):
        loc = u.find("loc").get_text()
        titulo = re.sub(r"\s+", " ", u.find("news:title").get_text()).strip()
        fecha = u.find("news:publication_date").get_text()[:10]
        filas.append({"id": hashlib.sha1(loc.encode()).hexdigest()[:10], "fecha": fecha,
                      "titular": titulo, "grupo": grupo(titulo)})
    df = pd.DataFrame(filas)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT, index=False, encoding="utf8")
    print(df.grupo.value_counts().to_string())
    print(f"{len(df)} titulares -> {OUT}")


if __name__ == "__main__":
    main()
