"""Columnas de los archivos de data/processed/red/."""

ARISTAS = ("origen", "destino", "tipo", "medio", "mes", "macroregion")
NODOS = ("nodo", "clase", "medio", "grado_entrada", "grado_salida", "pagerank")
# Por grupo (medio, mes o macro-región) y actor: cuántas notas sobre El Niño lo enlazan, lo mencionan o cualquiera
CITAS = ("grupo", "valor", "actor", "notas", "enlazan", "mencionan", "enlazan_o_mencionan", "proporcion")
