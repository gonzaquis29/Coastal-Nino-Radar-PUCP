"""Metodología: cómo se validó cada parte (desde los validacion.csv) y el uso de la app (desde el registro)."""

import collections

from radar import config
from radar.app import eventos
from radar.app import textos as tx
from radar.comun.archivos import leer_csv

# (archivo, prueba, título, qué mide en palabras simples). El archivo es la carpeta de su validacion.csv o una ruta
# dentro de data/processed. El orden es el de la pantalla.
TARJETAS = (
    ("nlp", "Semáforo: distancia y reglas", "Semáforo",
     "Si separa las notas que siguen a un comunicado de las de otros temas, y si los colores salen bien en casos de"
     " prueba."),
    ("nlp", "Capa 5: comparación", "Comparación de datos con el ENFEN (T5)",
     "Con 445 notas que nadie había visto: si el dato vigente es el que respalda y si un cambio de dato se detecta."),
    ("nlp", "Capa 3: afirmaciones", "Lectura de las afirmaciones",
     "Si se extraen bien la magnitud, el estado y las fechas de cada frase."),
    ("nlp", "Capa 3: temporalidad", "Lectura de las fechas", "Si se entienden bien los plazos y las estaciones."),
    ("nlp", "Embeddings", "Representación con embeddings (e5)",
     "Si el modelo separa las notas sobre El Niño de otros temas sin usar las palabras del fenómeno."),
    ("nlp", "Preprocesamiento y TF-IDF", "Línea base TF-IDF", "Lo mismo, con TF-IDF. No llega al umbral (T4)."),
    ("nlp", "Tópicos", "Tópicos (BERTopic)", "Coherencia y estabilidad de los 12 tópicos."),
    ("nlp", "Polaridad", "Polaridad de las notas", "Acuerdo entre dos métodos independientes. No pasa: descriptiva."),
    ("analitica", "Recomendador: validación (ronda b)", "Recomendador",
     "Si la nota que el medio enlaza sale entre las primeras recomendadas, con notas nuevas."),
    ("agente", "Agente: validación (ronda c)", "Agente",
     "Si elige la herramienta correcta y si todas sus citas son literales."),
    ("analitica", "Estudio de eventos: validación", "Reacción a los comunicados",
     "Si el método distingue un efecto real del azar con 18 comunicados. No pasa: descriptivo."),
    ("red", "Red de enlaces y citas", "Red de enlaces y citas",
     "Si cada enlace oficial se asigna a su institución y si los medios que la enlazan también la mencionan."),
    ("region", "RPP regional (sin Lima)", "Macro-región de cada nota",
     "Si la región asignada coincide con la sección regional del medio."),
    ("noticias", "Volumen de noticias", "Volumen de notas", "Si hay suficientes notas sobre El Niño."),
    ("noticias", "Calidad de las notas", "Calidad de la lectura de notas", "Duplicados, fechas y texto completo."),
    ("youtube", "YouTube: viabilidad", "YouTube", "Si hay suficientes videos y comentarios."),
    ("youtube", "YouTube: emociones", "Emociones de los comentarios",
     "Acuerdo con dos referencias independientes. No pasa: descriptivas."),
    ("modelos/engagement-validacion.csv", "Cercanía en videos", "Cercanía de los videos con lo oficial",
     "Si la cercanía separa los videos de las instituciones oficiales de los de otros temas."),
    ("modelos/engagement-validacion.csv", "Modelo de engagement", "Modelo de engagement",
     "Si predice la interacción de videos nuevos mejor que las líneas base, y si el contenido agrega algo."),
    ("red/youtube-validacion.csv", "Red social de YouTube", "Red social de YouTube",
     "Si las comunidades de autores de comentarios son reales y estables. La estabilidad no pasa: descriptiva."),
    ("analitica/web-validacion.csv", "Analítica web", "Analítica web",
     "Si hay datos suficientes para la pregunta 5 y Trends, si las citas de los medios tienen fechas posibles y si el"
     " registro de uso cuenta bien."),
    ("trends", "Trends: viabilidad", "Google Trends", "Si hay datos por departamento."),
    ("app", "App: API", "API de esta app",
     "Si responde lo mismo que los cálculos, a tiempo, solo con los campos permitidos de las notas y sin texto libre"
     " en el registro de uso."),
    ("app", "App: interfaz", "Pantallas de esta app",
     "Si se pueden usar con teclado y lector de pantalla, si muestran las mismas cifras que los cálculos, si los"
     " textos se entienden y si cargan rápido en el celular."),
)  # fmt: skip


def _si(valor):
    return str(valor).strip().lower() in ("1", "true", "sí", "si")


def ruta_de(archivo):
    if archivo.endswith(".csv"):
        return config.DIR_DATOS / "processed" / archivo
    return getattr(config, f"DIR_{archivo.upper()}", config.DIR_DATOS / "processed" / archivo) / "validacion.csv"


def tarjetas():
    salida = []
    cache = {}
    for archivo, prueba, titulo, que_mide in TARJETAS:
        if archivo not in cache:
            ruta = ruta_de(archivo)
            cache[archivo] = leer_csv(ruta) if ruta.exists() else []
        filas = [f for f in cache[archivo] if f["prueba"] == prueba]
        if not filas:
            continue
        criterios = [{"criterio": f["criterio"], "valor": f["valor"], "umbral": f["umbral"], "pasa": _si(f["pasa"])}
                     for f in filas]  # fmt: skip
        salida.append({"titulo": titulo, "que_mide": que_mide, "pasa": all(c["pasa"] for c in criterios),
                       "pasan": sum(c["pasa"] for c in criterios), "total": len(criterios),
                       "criterios": criterios})  # fmt: skip
    return salida


def uso():
    """Indicadores del registro de uso: sesiones, embudo, colores consultados y herramientas del agente."""
    filas = eventos.leer()
    sesiones = {f["sesion"] for f in filas}
    por_evento = collections.Counter(f["evento"] for f in filas)
    con = {e: {f["sesion"] for f in filas if f["evento"] == e} for e in ("vista", "verificar", "ver_por_que",
                                                                       "clic_que_hacer", "compartir")}  # fmt: skip
    embudo = [{"paso": "Abrió la app", "sesiones": len(con["vista"] or sesiones)},
              {"paso": "Verificó un texto", "sesiones": len(con["verificar"])},
              {"paso": "Vio por qué o qué hacer", "sesiones": len(con["ver_por_que"] | con["clic_que_hacer"])},
              {"paso": "Compartió", "sesiones": len(con["compartir"])}]  # fmt: skip
    resultados = collections.Counter(f["resultado"] for f in filas if f["evento"] == "verificar" and f["resultado"])
    herramientas = collections.Counter(f["herramienta"] for f in filas if f["evento"] == "preguntar")
    tiempos = collections.defaultdict(list)
    for f in filas:
        if f["evento"] == "vista" and f["anterior"] and f["segundos"]:
            tiempos[f["anterior"]].append(int(f["segundos"]))
    return {"sesiones": len(sesiones), "eventos": dict(por_evento), "embudo": embudo,
            "resultados": dict(resultados), "herramientas": dict(herramientas),
            "segundos_por_pantalla": {p: round(sum(v) / len(v)) for p, v in tiempos.items()}}  # fmt: skip


def metodologia():
    return {"tarjetas": tarjetas(), "limitaciones": list(tx.LIMITACIONES), "uso": uso()}
