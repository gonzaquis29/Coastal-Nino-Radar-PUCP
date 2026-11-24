"""Bloque 2: HTML de comunicados ENFEN -> data/processed/comunicados.csv (un párrafo por fila).

Reglas (sin etiquetado manual):
- fecha: de la URL de la entrada (/AAAA/MM/DD/) que se guarda en el nombre del archivo o se pasa por argumento.
- magnitud: términos de la escala oficial hallados junto a "magnitud".
- estado: solo si el texto declara explícitamente "Alerta/Vigilancia/No activo"; si no, "no declarado".
No se guarda el autor de la entrada (privacidad).
"""
import re
import sys
from pathlib import Path

import pandas as pd
from bs4 import BeautifulSoup

RAW = Path("data/raw/enfen")
OUT = Path("data/processed/comunicados.csv")
MAGNITUDES = ["extraordinaria", "muy fuerte", "fuerte", "moderada", "débil"]  # de mayor a menor
ESTADO_RE = re.compile(r"(alerta|vigilancia|no activo)\s+de\s+el\s+ni[ñn]o\s+costero", re.I)


def magnitud(texto: str):
    t = texto.lower()
    for m in MAGNITUDES:
        if re.search(rf"magnitud\s+{m}", t):
            return m
    return None


def estado(texto: str) -> str:
    m = ESTADO_RE.search(texto)
    return m.group(0).lower() if m else "no declarado"


def parsear(html_path: Path, fecha: str) -> list[dict]:
    soup = BeautifulSoup(html_path.read_text(encoding="utf8"), "html.parser")
    titulo = soup.find("h2", class_="entry_title").get_text(" ", strip=True)
    numero = re.search(r"N°\s*(\d+)", titulo).group(1)
    cuerpo = soup.find("div", class_="post_text_inner") or soup.find("h2", class_="entry_title").parent
    filas = []
    for p in cuerpo.find_all("p"):
        texto = re.sub(r"\s+", " ", p.get_text(" ", strip=True))
        if len(texto) < 60 or texto.startswith("Comisión Multisectorial") or texto.startswith("Para más información"):
            continue
        filas.append({"comunicado": int(numero), "fecha": fecha, "parrafo": len(filas) + 1,
                      "texto": texto, "magnitud": magnitud(texto), "estado": estado(texto)})
    return filas


if __name__ == "__main__":
    # uso: python src/comunicados.py n20.html 2026-11-13 [n19.html 2026-10-30 ...]
    args = sys.argv[1:] or ["n20.html", "2026-11-13"]
    filas = []
    for arch, fecha in zip(args[::2], args[1::2]):
        filas += parsear(RAW / arch, fecha)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame(filas)
    df.to_csv(OUT, index=False, encoding="utf8")
    print(df[["comunicado", "fecha", "parrafo", "magnitud", "estado"]].to_string())
    print(f"\n{len(df)} párrafos -> {OUT}")
