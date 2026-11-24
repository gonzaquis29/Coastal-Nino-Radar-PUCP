"""Bloque 8: validación con controles automáticos (sin etiquetado manual).

Control positivo: titulares de Andina que mencionan ENFEN / El Niño (regla por palabras clave).
Control negativo: titulares de otros temas. Se compara la distancia al párrafo oficial más cercano.
Umbrales del semáforo = percentiles de esas distribuciones. Compara TF-IDF vs embeddings (AUC).
"""
import json

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score
from sklearn.metrics.pairwise import cosine_similarity

import radar

df = radar.cargar_comunicados()
noticias = pd.read_csv(radar.DATA / "noticias.csv")
ctrl = noticias[noticias.grupo.isin(["positivo", "negativo"])].reset_index(drop=True)
print(ctrl.grupo.value_counts().to_string())

# embeddings: distancia coseno mínima a cualquier párrafo oficial
E_par = radar.embeber(df.texto.tolist())
E_tit = radar.embeber(ctrl.titular.tolist())
d_emb = 1 - (E_tit @ E_par.T).max(axis=1)

# TF-IDF base
vec, X_par = radar.tfidf_base(df)
d_tfidf = 1 - cosine_similarity(vec.transform(ctrl.titular), X_par).max(axis=1)

y = (ctrl.grupo == "positivo").astype(int).values
res = {}
if 0 < y.sum() < len(y):
    # menor distancia = más oficial, así que el score del positivo es -distancia
    res["auc_embeddings"] = round(roc_auc_score(y, -d_emb), 3)
    res["auc_tfidf"] = round(roc_auc_score(y, -d_tfidf), 3)
res["n_positivos"], res["n_negativos"] = int(y.sum()), int((1 - y).sum())

pos, neg = d_emb[y == 1], d_emb[y == 0]
if len(pos) >= 3 and len(neg) >= 3:
    verde, rojo = float(np.percentile(pos, 75)), float(np.percentile(neg, 25))
    if verde >= rojo:  # distribuciones solapadas: usar el punto medio de las medianas
        verde = rojo = float((np.median(pos) + np.median(neg)) / 2)
    origen = "P75 de controles positivos y P25 de negativos"
else:
    verde, rojo = 0.45, 0.65
    origen = "pocos controles; valores provisionales"
res.update({"verde": round(verde, 3), "rojo": round(rojo, 3), "origen": origen,
            "mediana_pos": round(float(np.median(pos)), 3) if len(pos) else None,
            "mediana_neg": round(float(np.median(neg)), 3)})
radar.UMBRALES.parent.mkdir(exist_ok=True)
radar.UMBRALES.write_text(json.dumps(res, indent=2, ensure_ascii=False))

# gráfico y tabla
fig, ax = plt.subplots(figsize=(7, 4))
if len(pos):
    ax.hist(pos, bins=10, alpha=.7, label=f"positivo (n={len(pos)})", color="#2a9d8f")
ax.hist(neg, bins=15, alpha=.6, label=f"negativo (n={len(neg)})", color="#e76f51")
ax.axvline(res["verde"], ls="--", c="g"); ax.axvline(res["rojo"], ls="--", c="r")
ax.set_xlabel("distancia coseno al párrafo oficial más cercano"); ax.set_ylabel("titulares")
ax.set_title("Controles: titulares sobre El Niño vs. otros temas"); ax.legend()
fig.tight_layout(); fig.savefig("results/controles.png", dpi=150)
ctrl.assign(dist_emb=d_emb.round(3), dist_tfidf=d_tfidf.round(3)).sort_values("dist_emb").to_csv(
    "results/controles.csv", index=False, encoding="utf8")
print(json.dumps(res, indent=2, ensure_ascii=False))
