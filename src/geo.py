"""Capa geográfica: catálogo de ubigeos (departamento/provincia/distrito con coordenadas) y utilidades.

Fuente: github.com/jmcastagnetto/ubigeo-peru-aumentado (licencia MIT), copiado a data/raw/ubigeo/distrito.csv.
"""
import math
import re
import unicodedata
from functools import lru_cache
from pathlib import Path

import pandas as pd

UBIGEO = Path("data/raw/ubigeo/distrito.csv")


def norm(s: str) -> str:
    """MAYÚSCULAS sin tildes ni signos, para comparar nombres."""
    s = unicodedata.normalize("NFD", str(s))
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", " ", re.sub(r"[^A-Za-z0-9 ]", " ", s)).strip().upper()


@lru_cache(maxsize=1)
def distritos() -> pd.DataFrame:
    df = pd.read_csv(UBIGEO, dtype={"inei": str}, encoding="utf8")
    df = df.rename(columns={"latitude": "lat", "longitude": "lon"})
    df = df.dropna(subset=["lat", "lon"])
    return df[["inei", "departamento", "provincia", "distrito", "lat", "lon"]].reset_index(drop=True)


def departamentos() -> list[str]:
    return sorted(distritos().departamento.unique())


def haversine_km(lat1, lon1, lat2, lon2):
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def distrito_mas_cercano(lat: float, lon: float) -> dict:
    d = distritos()
    dist = d.apply(lambda r: haversine_km(lat, lon, r.lat, r.lon), axis=1)
    r = d.loc[dist.idxmin()]
    return {"departamento": r.departamento, "provincia": r.provincia, "distrito": r.distrito,
            "km": round(float(dist.min()), 1)}


# --- Regiones naturales (APROXIMACIÓN declarada) -------------------------------------------------
# Los avisos de Senamhi/INDECI hablan de "costa norte", "sierra sur"... Se asignan a departamentos con esta
# tabla simplificada. Un departamento puede aparecer en varias regiones. Solo se usa si el texto no nombra
# departamentos de forma explícita.
REGIONES = {
    "costa norte": ["TUMBES", "PIURA", "LAMBAYEQUE", "LA LIBERTAD"],
    "costa centro": ["ANCASH", "LIMA", "CALLAO"],
    "costa sur": ["ICA", "AREQUIPA", "MOQUEGUA", "TACNA"],
    "sierra norte": ["CAJAMARCA", "AMAZONAS", "LA LIBERTAD", "PIURA", "LAMBAYEQUE", "ANCASH"],
    "sierra centro": ["PASCO", "JUNIN", "HUANUCO", "LIMA", "HUANCAVELICA", "ANCASH"],
    "sierra sur": ["APURIMAC", "AYACUCHO", "CUSCO", "PUNO", "AREQUIPA", "MOQUEGUA", "TACNA", "HUANCAVELICA"],
    "selva norte": ["LORETO", "AMAZONAS", "SAN MARTIN", "CAJAMARCA"],
    "selva centro": ["HUANUCO", "PASCO", "JUNIN", "UCAYALI"],
    "selva sur": ["CUSCO", "MADRE DE DIOS", "PUNO"],
}


def departamentos_en_texto(texto: str, solo_regiones: bool = False) -> list[str]:
    """Departamentos nombrados explícitamente; si no hay, se infieren de 'costa norte', 'sierra sur', etc.

    solo_regiones=True ignora nombres propios (p. ej. ríos 'Piura', 'Ucayali' en un comunicado del ENFEN)."""
    t = " " + norm(texto) + " "
    deps = [] if solo_regiones else [d for d in departamentos() if f" {d} " in t]
    if "CALLAO" in t and not solo_regiones and "CALLAO" not in deps:
        deps.append("CALLAO")
    if deps:
        return sorted(set(deps))
    if solo_regiones and " TODA LA COSTA " in t:
        return sorted(set(REGIONES["costa norte"] + REGIONES["costa centro"] + REGIONES["costa sur"]))
    out = set()
    for reg, lista in REGIONES.items():
        if f" {norm(reg)} " in t:
            out.update(lista)
    return sorted(out)


def departamentos_aviso(titulo: str, texto: str) -> list[str]:
    """Avisos de Senamhi: zonas del TÍTULO (p. ej. 'COSTA NORTE Y SIERRA') + departamentos que nombre el texto.

    Antes bastaba un departamento nombrado en el texto para descartar el resto de la zona (subestimaba el alcance)."""
    t = norm(titulo)
    out = set(departamentos_en_texto(texto, solo_regiones=False)) if any(f" {d} " in f" {norm(texto)} " for d in departamentos()) else set()
    zona = None
    for tok in re.findall(r"COSTA|SIERRA|SELVA|NORTE|CENTRO|CENTRAL|SUR|[A-Z0-9]+", t):
        if tok in ("COSTA", "SIERRA", "SELVA"):
            if zona and not sub:
                out.update(_zona(zona))
            zona, sub = tok.lower(), False
        elif tok in ("NORTE", "CENTRO", "CENTRAL", "SUR") and zona:
            out.update(REGIONES[f"{zona} {'centro' if tok == 'CENTRAL' else tok.lower()}"])
            sub = True
    if zona and not sub:
        out.update(_zona(zona))
    return sorted(out) or departamentos_en_texto(f"{titulo}. {texto}")


def _zona(z):
    return [d for r, lista in REGIONES.items() if r.startswith(z) for d in lista]
