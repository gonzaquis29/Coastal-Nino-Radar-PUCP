"""Consolida las fuentes en un esquema único -> data/processed/eventos.csv

Esquema: id, fuente, peligro, titulo, texto, publicado, inicio, fin, nivel, departamentos ('|'), lat, lon,
         recomendaciones ('||'), url
Todo por reglas transparentes (palabras clave + catálogo geográfico); no hay etiquetado manual.
"""
import re
from pathlib import Path

import pandas as pd

import geo

PROC = Path("data/processed")

# prioridad: el primero que coincida en el título (o, si no, en el texto) define el peligro principal
PELIGROS = [
    ("sismo", r"sismo|temblor|terremoto|tsunami"),
    ("lluvias e inundaciones", r"lluvia|precipitaci|llovizna|huaico|inundaci|deslizamiento|movimientos? en masa|crecida|desborde|aluvi"),
    ("oleaje anómalo", r"oleaje|marejada"),
    ("calor", r"temperatura diurna|calor|radiaci[oó]n ultravioleta"),
    ("viento", r"viento"),
    ("frío y heladas", r"helada|friaje|descenso de (la )?temperatura|nevada|bajas temperaturas"),
    ("El Niño Costero", r"ni[ñn]o costero|enfen|fen[oó]meno el ni[ñn]o"),
]
FRASE_REC = re.compile(r"recomienda a la poblaci|se recomienda|se sugiere|exhorta|se debe|se insta", re.I)
INTRO = re.compile(r"recomienda adoptar medidas de preparaci", re.I)


def peligro(titulo: str, texto: str = "") -> str:
    for p, rx in PELIGROS:
        if re.search(rx, titulo, re.I):
            return p
    for p, rx in PELIGROS:
        if re.search(rx, texto[:1500], re.I):
            return p
    return "otro"


def recomendaciones(texto: str) -> list[str]:
    frases = re.split(r"(?<=[\.;])\s+(?=[A-ZÁÉÍÓÚ])", texto)
    return [f.strip() for f in frases if FRASE_REC.search(f) and not INTRO.search(f)][:6]


def _num(x):
    return pd.to_datetime(x, errors="coerce")


def _url_enfen(num) -> str:
    """Enlace canónico del comunicado, tomado del HTML descargado."""
    f = Path(f"data/raw/enfen/n{num}.html")
    m = re.search(r'rel="canonical" href="([^"]+)"', f.read_text(encoding="utf8")) if f.exists() else None
    return m.group(1) if m else "https://enfen.imarpe.gob.pe/"


def construir() -> pd.DataFrame:
    filas = []
    # --- Senamhi
    p = PROC / "senamhi.csv"
    if p.exists():
        for r in pd.read_csv(p).itertuples():
            filas.append(dict(id=r.id, fuente="SENAMHI", peligro=peligro(r.titulo, r.texto), titulo=r.titulo,
                              texto=r.texto, publicado=r.publicado, inicio=r.inicio, fin=r.fin, nivel=r.nivel,
                              departamentos="|".join(geo.departamentos_aviso(r.titulo, r.texto)), url=r.url,
                              recomendaciones="||".join(recomendaciones(r.texto))))
    # --- INDECI
    p = PROC / "indeci.csv"
    if p.exists():
        for r in pd.read_csv(p).itertuples():
            filas.append(dict(id=r.id, fuente="INDECI", peligro=peligro(r.titulo, r.texto), titulo=r.titulo,
                              texto=r.texto, publicado=r.publicado, inicio=None, fin=None, nivel=None,
                              departamentos="|".join(geo.departamentos_en_texto(r.titulo + ". " + r.texto)),
                              url=r.url, recomendaciones="||".join(recomendaciones(r.texto))))
    # --- ENFEN (comunicado oficial)
    p = PROC / "comunicados.csv"
    if p.exists():
        c = pd.read_csv(p)
        for num, g in c.groupby("comunicado"):
            tx = " ".join(g.texto)
            filas.append(dict(id=f"enfen-{num}", fuente="ENFEN", peligro="El Niño Costero",
                              titulo=f"Comunicado Oficial ENFEN N.° {num}", texto=tx, publicado=g.fecha.iloc[0],
                              inicio=g.fecha.iloc[0], fin=None, nivel=g.magnitud.dropna().iloc[0] if g.magnitud.notna().any() else None,
                              departamentos="|".join(geo.departamentos_en_texto(tx, solo_regiones=True)),
                              url=_url_enfen(num), recomendaciones="||".join(recomendaciones(tx))))
    # --- USGS (sismos, con coordenadas)
    p = PROC / "sismos.csv"
    if p.exists():
        for r in pd.read_csv(p).itertuples():
            f = _num(r.fecha_utc) - pd.Timedelta(hours=5)  # hora de Perú
            filas.append(dict(id=f"usgs-{r.id}", fuente="USGS", peligro="sismo",
                              titulo=f"Sismo M{r.mag:.1f} · {r.lugar}", texto=f"Profundidad {r.prof_km:.0f} km.",
                              publicado=f, inicio=f, fin=None, nivel=None, departamentos="", lat=r.lat, lon=r.lon,
                              url=r.url, recomendaciones=""))
    df = pd.DataFrame(filas)
    for c_ in ("publicado", "inicio", "fin"):
        df[c_] = _num(df[c_])
    df.to_csv(PROC / "eventos.csv", index=False, encoding="utf8")
    return df
