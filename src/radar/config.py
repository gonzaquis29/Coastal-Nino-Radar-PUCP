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

# ---------------------------------------------------------------- fechas del proyecto (README, "Ventana de datos")
LIMA = dt.timezone(dt.timedelta(hours=-5))  # el Perú no tiene horario de verano
INICIO = dt.date(2026, 1, 1)
CORTE = dt.datetime(2026, 11, 20, 23, 59, tzinfo=LIMA)
CONGELAMIENTO = dt.date(2026, 11, 27)

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
