"""Columnas de los archivos de data/processed/nlp/."""

# Una fila por nota leída (la última vale si se repite): bolsa de lemas y controles de la lectura
CONTEOS = (
    "medio", "id", "estrato", "sha1_cuerpo", "sha1_igual", "n_palabras", "usa_resumen", "menciones",
    "terminos_fenomeno", "error", "lemas",
)  # fmt: skip
# Filas de las matrices conteos.npz y tfidf.npz, en orden
DOCUMENTOS = ("fila", "tipo", "medio", "id", "estrato")
VOCABULARIO = ("columna", "termino", "df")
