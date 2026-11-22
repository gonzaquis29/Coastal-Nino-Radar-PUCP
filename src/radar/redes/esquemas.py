"""Columnas de los archivos de data/processed/red/."""

ARISTAS = ("origen", "destino", "tipo", "medio", "mes", "macroregion")
NODOS = ("nodo", "clase", "medio", "grado_entrada", "grado_salida", "pagerank")
# Por grupo (medio, mes o macro-región) y actor: cuántas notas sobre El Niño lo enlazan, lo mencionan o cualquiera
CITAS = ("grupo", "valor", "actor", "notas", "enlazan", "mencionan", "enlazan_o_mencionan", "proporcion")
# Red social de YouTube (docs/redes/youtube.md): por canal con seudónimo (vence con YouTube) y agregados sin ids
YOUTUBE_CANALES = (
    "canal", "tipo", "pais", "autores", "en_componente", "comunidad", "fuerza", "pagerank", "intermediacion",
    "cercania", "videos_cercania", "cruce", "cruce_nulo", "cruce_sin_mayor", "cruce_nulo_sin_mayor",
)  # fmt: skip
YOUTUBE_TIPOS = ("tipo", "canales", "autores_mediana", "fuerza_mediana", "pagerank_mediana", "intermediacion_mediana")
YOUTUBE_COMUNIDADES = (
    "comunidad", "canales", "medios", "otros", "oficiales", "peru", "sin_pais", "otros_paises", "pais_principal",
    "autores_mediana",
)  # fmt: skip
