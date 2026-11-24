"""Bloques 4-6: normalizar (spaCy), TF-IDF base, embeddings + ChromaDB y evaluar(titular, fecha).

El índice mide CERCANÍA a lo oficial; no es un detector de desinformación.
"""
import json
import re
from datetime import date
from pathlib import Path

import chromadb
import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer

DATA = Path("data/processed")
CHROMA_DIR = "data/chroma"
UMBRALES = Path("results/umbrales.json")
MODELO = "paraphrase-multilingual-MiniLM-L12-v2"
COLECCION = "comunicados_enfen"
MAGNITUDES = ["extraordinaria", "muy fuerte", "fuerte", "moderada", "débil"]
RANGO = {m: len(MAGNITUDES) - i for i, m in enumerate(MAGNITUDES)}  # extraordinaria=5 ... débil=1

_nlp = _modelo = None


def normalizar(texto: str) -> str:
    """minúsculas, sin puntuación/stopwords, lematizado (spaCy es_core_news_sm)."""
    global _nlp
    if _nlp is None:
        import spacy
        _nlp = spacy.load("es_core_news_sm", disable=["ner", "parser"])
    doc = _nlp(texto.lower())
    return " ".join(t.lemma_ for t in doc if t.is_alpha and not t.is_stop)


def modelo():
    global _modelo
    if _modelo is None:
        from sentence_transformers import SentenceTransformer
        _modelo = SentenceTransformer(MODELO)
    return _modelo


def embeber(textos: list[str]) -> np.ndarray:
    return modelo().encode(textos, normalize_embeddings=True, show_progress_bar=False)


def cargar_comunicados() -> pd.DataFrame:
    df = pd.read_csv(DATA / "comunicados.csv")
    df["id"] = df.comunicado.astype(str) + "-" + df.parrafo.astype(str)
    return df


def construir_indice(df: pd.DataFrame):
    """ChromaDB persistente con distancia coseno; upsert idempotente."""
    cli = chromadb.PersistentClient(path=CHROMA_DIR)
    col = cli.get_or_create_collection(COLECCION, metadata={"hnsw:space": "cosine"})
    col.upsert(ids=df.id.tolist(), documents=df.texto.tolist(), embeddings=embeber(df.texto.tolist()).tolist(),
               metadatas=[{"comunicado": int(r.comunicado), "fecha": r.fecha, "parrafo": int(r.parrafo)}
                          for r in df.itertuples()])
    return col


def tfidf_base(df: pd.DataFrame):
    vec = TfidfVectorizer(preprocessor=normalizar, ngram_range=(1, 2), sublinear_tf=True)
    return vec, vec.fit_transform(df.texto)


def magnitud_en(texto: str):
    t = texto.lower().replace("muy fuerte", "muy_fuerte")
    for m in MAGNITUDES:
        if m.replace(" ", "_") in t or (m == "extraordinaria" and "extraordinari" in t):
            return m
    return None


def umbrales() -> dict:
    if UMBRALES.exists():
        return json.loads(UMBRALES.read_text())
    return {"verde": 0.35, "rojo": 0.60, "origen": "valores por defecto (sin controles calculados)"}


def comunicado_vigente(df: pd.DataFrame, fecha: str):
    previos = df[df.fecha <= fecha]
    return None if previos.empty else int(previos.comunicado.max())


def evaluar(titular: str, fecha: str | None = None, col=None, df=None) -> dict:
    fecha = fecha or date.today().isoformat()
    df = cargar_comunicados() if df is None else df
    col = col or construir_indice(df)
    vig = comunicado_vigente(df, fecha)
    if vig is None:
        return {"semaforo": "sin dato", "motivo": f"No hay comunicado ENFEN cargado vigente al {fecha}.",
                "fecha": fecha}
    r = col.query(query_embeddings=embeber([titular]).tolist(), n_results=1, where={"comunicado": vig})
    dist = float(r["distances"][0][0])
    meta = r["metadatas"][0][0]
    vig_df = df[df.comunicado == vig]
    mag_oficial = vig_df.magnitud.dropna().iloc[0] if vig_df.magnitud.notna().any() else None
    mag_titular = magnitud_en(titular)
    discrepa = bool(mag_oficial and mag_titular and mag_titular != mag_oficial)
    u = umbrales()
    sem = "verde" if dist <= u["verde"] else "rojo" if dist >= u["rojo"] else "amarillo"
    if discrepa and sem == "verde":
        sem = "amarillo"
    return {"semaforo": sem, "distancia": round(dist, 3), "fecha": fecha, "comunicado": vig,
            "fecha_comunicado": meta["fecha"], "parrafo_oficial": r["documents"][0][0],
            "magnitud_oficial": mag_oficial, "magnitud_titular": mag_titular, "magnitud_distinta": discrepa,
            "umbrales": u}
