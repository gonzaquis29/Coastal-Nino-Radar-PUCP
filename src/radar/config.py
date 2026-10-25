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

# ---------------------------------------------------------------- fechas del proyecto (README, "Ventana de datos")
LIMA = dt.timezone(dt.timedelta(hours=-5))  # el Perú no tiene horario de verano
INICIO = dt.date(2026, 1, 1)
FIN_HISTORICO = dt.date(2026, 10, 24)  # primera recolección diaria: desde aquí las notas vienen de data/urls/

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
