"""Columnas de los archivos de data/processed/nlp/."""

# Una fila por nota leída (la última vale si se repite): bolsa de lemas y controles de la lectura
CONTEOS = (
    "medio", "id", "estrato", "sha1_cuerpo", "sha1_igual", "n_palabras", "usa_resumen", "menciones",
    "terminos_fenomeno", "error", "lemas",
)  # fmt: skip
# Filas de las matrices conteos.npz y tfidf.npz, en orden
DOCUMENTOS = ("fila", "tipo", "medio", "id", "estrato")
VOCABULARIO = ("columna", "termino", "df")

# embeddings: una fila por nota leída y por modelo (la última vale si se repite). "con" es el texto completo y "sin",
# sin los términos del fenómeno; max es el coseno máximo de los tramos con los párrafos del ENFEN, parrafo el id del
# párrafo más parecido, prom el máximo del vector promedio de la nota y centroide su coseno con el centroide del ENFEN
MODELOS_EMBEDDING = ("minilm", "e5", "e5q")  # e5q: e5-small cuantizado en ONNX, el que usaría la app
PUNTAJES = tuple(f"{v}_{c}" for v in ("con", "sin") for c in ("max", "parrafo", "prom", "centroide"))
EMBEDDINGS = (
    "medio", "id", "estrato", "positivo", "sha1_cuerpo", "sha1_igual", "n_palabras", "error",
    *(f"{m}_{c}" for m in MODELOS_EMBEDDING for c in ("tramos", "truncados", *PUNTAJES)),
)  # fmt: skip
# El vector promedio de cada nota (texto completo), en base64 de float32: nunca los vectores de cada tramo
VECTORES = ("medio", "id", "modelo", "vector")
