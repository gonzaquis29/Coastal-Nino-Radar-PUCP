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

# candidatos (plan del 2-nov): una fila por nota leída en cada pasada; las columnas de cada modelo son
# {modelo}_{puntaje}. "vig" compara solo con los párrafos del ENFEN vigentes en la fecha de la nota, "todo" con los 865
# párrafos (ENFEN y Senamhi) y "tit" usa solo el titular
CANDIDATOS_BASE = ("medio", "id", "estrato", "positivo", "sha1_igual", "error")
PUNTAJES_CANDIDATO = (
    "con_max", "sin_max", "con_parrafo", "vig_con_max", "vig_sin_max", "vig_con_parrafo", "todo_con_max",
    "todo_sin_max", "tit_con_max", "tit_sin_max", "tit_vig_con_max", "tramos", "truncados",
)  # fmt: skip


RERANKER = ("medio", "id", "estrato", "positivo", "nueva", "con", "sin", "parrafo", "pares", "truncados", "error")


HIBRIDO = ("medio", "id", "estrato", "positivo", "nueva", "con", "sin", "cos_con", "cos_sin", "parrafo", "error")
HIBRIDO_REFERENCIA = ("medio", "id", "cos_con", "bm25_con", "cos_sin", "bm25_sin", "error")


def columnas_candidatos(modelos):
    return CANDIDATOS_BASE + tuple(f"{m}_{p}" for m in modelos for p in PUNTAJES_CANDIDATO)
