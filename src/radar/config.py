"""Valores del proyecto que pueden cambiar. Es el único lugar donde se definen; el resto del código los importa."""

import datetime as dt
from pathlib import Path

# ---------------------------------------------------------------- rutas
RAIZ = Path(__file__).resolve().parents[2]
DIR_CONFIG = RAIZ / "config"
DIR_DATOS = RAIZ / "data"
DIR_URLS = DIR_DATOS / "urls"
DIR_RAW = DIR_DATOS / "raw"
DIR_RAW_OFICIAL = DIR_RAW / "oficial"
DIR_OFICIAL = DIR_DATOS / "oficial"
DIR_REGISTROS = DIR_DATOS / "registros"
DIR_RAW_NOTICIAS = DIR_RAW / "noticias"  # listas descubiertas y estado; nunca el cuerpo de las notas
DIR_NOTICIAS = DIR_DATOS / "processed" / "noticias"
DIR_RAW_INEI = DIR_RAW / "inei"  # ubigeos descargados del INEI (la lista decidida queda en config/lugares.csv)
DIR_REGION = DIR_DATOS / "processed" / "region"  # validación de la asignación de macro-región
DIR_RED = DIR_DATOS / "processed" / "red"  # red de enlaces y citas de las notas
DIR_NLP = DIR_DATOS / "processed" / "nlp"  # vectores, conteos y validación del NLP (nunca la secuencia de lemas)
DIR_ANALITICA = DIR_DATOS / "processed" / "analitica"  # estudio de eventos y KPIs (solo agregados por día)
DIR_AGENTE = DIR_DATOS / "processed" / "agente"  # validación del agente (sin texto de notas)
DIR_RAW_YOUTUBE = DIR_RAW / "youtube"  # respuestas de la API (vencen a los 30 días; nunca se versionan)
DIR_YOUTUBE = DIR_DATOS / "processed" / "youtube"  # derivados por video (también vencen) y validación
DIR_RAW_TRENDS = DIR_RAW / "trends"  # CSV exportados a mano desde la web de Google Trends
DIR_TRENDS = DIR_DATOS / "processed" / "trends"
DIR_APP = DIR_DATOS / "processed" / "app"  # registro de uso de la app (anónimo, sin texto)
DIR_CACHE_VECTORES = DIR_DATOS / "processed" / "cache"  # vectores de textos oficiales; se recalculan si cambia algo
DIR_MODELOS = DIR_DATOS / "processed" / "modelos"  # resultados del modelo de engagement (solo agregados, sin ids)
DIR_WEB = RAIZ / "web"  # interfaz en React; la API sirve web/dist

# ---------------------------------------------------------------- fechas del proyecto (README, "Ventana de datos")
LIMA = dt.timezone(dt.timedelta(hours=-5))  # el Perú no tiene horario de verano
INICIO = dt.date(2026, 1, 1)
FIN_HISTORICO = dt.date(2026, 10, 24)  # primera recolección diaria: desde aquí las notas vienen de data/urls/
# Días que la recolección diaria no cubrió (alerta de hueco) y que se recuperan por el archivo por fecha de RPP.
# Andina no necesita lista: el histórico prueba todos los números hasta el mayor de data/urls/.
HUECOS_RPP = (
    dt.date(2026, 11, 10), dt.date(2026, 11, 11), dt.date(2026, 11, 12),  # 129 h sin correr (16-nov)
    dt.date(2026, 11, 19), dt.date(2026, 11, 20),  # 73 h sin correr (22-nov): web/futbol empieza el 20-nov
)  # fmt: skip

# ---------------------------------------------------------------- medios (definición en docs/noticias/definicion.md)
HOSTS_MEDIOS = {
    "andina": "andina.pe",
    "rpp": "rpp.pe",
    "exitosa": "www.exitosanoticias.pe",
    "eltiempo": "eltiempo.pe",
}
ANDINA_PRIMER_ID = 1057700  # el primer número con datePublished de 2026 es ≈ 1057710 (validado el 24-oct-2026)
# Qué notas se descargan además de las que pasan el filtro por título: "titulo" (ninguna más), "secciones"
# (todas las de secciones no excluidas en config/secciones_excluidas.csv) o "todo". Lo decide la prueba del filtro.
CANDIDATAS = {"andina": "todo", "rpp": "secciones", "exitosa": "secciones", "eltiempo": "todo"}
SEMILLA_MUESTRAS = 656

# ---------------------------------------------------------------- fuentes oficiales (recolector y corpus)
HOST_ENFEN = "enfen.imarpe.gob.pe"
HOST_SENAMHI = "www.senamhi.gob.pe"
HOST_SENAMHI_GIS = "idesep.senamhi.gob.pe"
URL_ENFEN = f"https://{HOST_ENFEN}"
URL_SENAMHI = f"https://{HOST_SENAMHI}/"
URL_AVISOS_SENAMHI = URL_SENAMHI + "?p=aviso-meteorologico"
# Ubigeos: WFS de la IDE del INEI (capas de límites "actualizado al 2023"; validado el 25-oct-2026)
HOST_INEI_GIS = "geoespacial.inei.gob.pe"
URL_WFS_INEI = f"https://{HOST_INEI_GIS}/geoserver/Interoperabilidad/ows"

# ---------------------------------------------------------------- modelos (docs/nlp/viabilidad-modelos.md)
MODELO_NLI = "MoritzLaurer/mDeBERTa-v3-base-xnli-multilingual-nli-2mil7"
MODELOS_EMBEDDING = {
    "minilm": "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
    "e5": "intfloat/multilingual-e5-small",
}
# Candidatos del mapa de alternativas (docs/nlp/embeddings.md, 2-nov)
CANDIDATOS_EMBEDDING = {
    "minilm": MODELOS_EMBEDDING["minilm"],
    "e5-small": MODELOS_EMBEDDING["e5"],
    "e5-base": "intfloat/multilingual-e5-base",
    "granite-107m": "ibm-granite/granite-embedding-107m-multilingual",
    "granite-278m": "ibm-granite/granite-embedding-278m-multilingual",
    "mpnet": "sentence-transformers/paraphrase-multilingual-mpnet-base-v2",
    "beto-es": "hiiamsid/sentence_similarity_spanish_es",
    "arctic-l": "Snowflake/snowflake-arctic-embed-l-v2.0",
    "bge-m3": "BAAI/bge-m3",
    "qwen3": "Qwen/Qwen3-Embedding-0.6B",
}
CANDIDATOS_RERANKER = {
    "mmarco": "cross-encoder/mmarco-mMiniLMv2-L12-H384-v1",
    "bge": "BAAI/bge-reranker-v2-m3",
    "mxbai": "mixedbread-ai/mxbai-rerank-base-v2",
    "qwen3": "Qwen/Qwen3-Reranker-0.6B",
}
MODELO_SPACY = "es_core_news_sm"

# ---------------------------------------------------------------- red
USER_AGENT = (
    "CoastalNinoRadar-PUCP/0.1 (proyecto academico INF656 PUCP; "
    "+https://github.com/gonzaquis29/Coastal-Nino-Radar-PUCP)"
)
TOKEN_ROBOTS = "coastalninoradar-pucp"  # nombre con el que nos buscan los grupos de robots.txt
PAUSA_POR_HOST = 1.0  # segundos entre peticiones al mismo host
TIEMPO_CONEXION = 15  # segundos
TIEMPO_LECTURA = 60
REINTENTOS = 2  # además del primer intento
ESPERA_BASE = 5  # segundos; crece en forma exponencial con algo de azar
ESPERA_MAXIMA = 120  # tope para Retry-After y para la espera exponencial
FALLOS_SEGUIDOS_POR_HOST = 5  # al llegar aquí, el host se salta en esa ejecución
MAX_BYTES = 30_000_000

# ---------------------------------------------------------------- personas que corren los scripts
PERSONAS = ("gonzalo", "joseph")

# ---------------------------------------------------------------- referencias editables (config/*.csv)
ARCHIVO_REGIONES = DIR_CONFIG / "regiones.csv"
ARCHIVO_ESTACIONES = DIR_CONFIG / "estaciones_costa.csv"
ARCHIVO_TERMINOS = DIR_CONFIG / "terminos_titulo.csv"
ARCHIVO_SECCIONES_EXCLUIDAS = DIR_CONFIG / "secciones_excluidas.csv"
ARCHIVO_ACTORES = DIR_CONFIG / "actores.csv"
ARCHIVO_INSTITUCIONES_WEB = DIR_CONFIG / "instituciones_web.csv"  # sitios de cada actor de actores.csv
ARCHIVO_LUGARES = DIR_CONFIG / "lugares.csv"
ARCHIVO_LUGARES_LA_NINA = DIR_CONFIG / "lugares_la_nina.csv"  # "laguna La Niña" no es el fenómeno
# Notas ya vistas en pilotos y validaciones (solo medio, id y muestra): ninguna muestra nueva las repite
ARCHIVO_NOTAS_VISTAS = DIR_CONFIG / "notas_vistas.csv"
ARCHIVO_UMBRALES_SEMAFORO = DIR_CONFIG / "semaforo_umbrales.csv"  # los usa la app: solo cosenos y AUC
# Un solo proceso a la vez pide páginas (medios y fuentes oficiales): así se respeta el ritmo por host entre procesos
ARCHIVO_CANDADO = DIR_DATOS / "red.lock"

# ---------------------------------------------------------------- YouTube y Trends (docs/youtube/definicion.md)
# La clave y la sal se leen de variables de entorno: nunca se escriben en el repo, en el registro ni en pantalla
VARIABLE_CLAVE_YOUTUBE = "YOUTUBE_API_KEY"
VARIABLE_SAL_YOUTUBE = "RADAR_YOUTUBE_SAL"
ARCHIVO_ENTORNO = RAIZ / ".env"  # si la variable no está en el entorno, se busca aquí (ignorado por git)
FIN_CORTE = dt.date(2026, 11, 20)  # corte de datos: hasta las 23:59 de Lima
TERMINOS_YOUTUBE = ("fenómeno El Niño", "Niño costero", "ENFEN", "El Niño Perú", "lluvias costa norte")
DIAS_VIDA_YOUTUBE = 30  # políticas de la API: borrar o refrescar los datos a los 30 días
BUSQUEDAS_POR_DIA = 100  # límite propio de search.list (página oficial de cuotas, revisada el 16-nov-2026)
CUPO_POR_DIA = 10_000  # unidades del resto de los métodos (1 por llamada)
MARGEN_CUPO = 1_000  # no se gasta: queda para reintentos y errores
HORAS_LIMA_A_PACIFICO = 3  # el cupo se reinicia a medianoche del Pacífico (03:00 de Lima en noviembre, horario PST)
PAUSA_API = 0.2  # segundos entre llamadas a la API
DEPARTAMENTOS_TRENDS = ("tumbes", "piura", "lambayeque", "la-libertad")
