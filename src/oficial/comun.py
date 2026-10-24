"""Utilidades compartidas del corpus oficial: HTTP seguro, archivos, fechas, texto y regiones."""
import csv
import datetime as dt
import gzip
import hashlib
import os
import re
import sys
import tempfile
import unicodedata
from pathlib import Path
from urllib.parse import urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from recolector.diario import Cliente, LIMA  # noqa: E402  (mismo user-agent, ritmo y robots.txt)

RAIZ = Path(__file__).resolve().parents[2]
DIR_URLS = RAIZ / "data" / "urls"
DIR_RAW = RAIZ / "data" / "raw" / "oficial"
DIR_OFICIAL = RAIZ / "data" / "oficial"
INICIO = "2026-01-01"
HOSTS = {"enfen.imarpe.gob.pe", "www.senamhi.gob.pe", "idesep.senamhi.gob.pe"}
MAX_BYTES = 30_000_000  # ningún documento esperado pasa de ~3 MB
MESES = {m: i + 1 for i, m in enumerate(
    "enero febrero marzo abril mayo junio julio agosto setiembre octubre noviembre diciembre".split())}
MESES["septiembre"] = 9


# ---------------------------------------------------------------- HTTP

class Rechazado(Exception):
    """Respuesta que no cumple los controles (host, tamaño, tipo)."""


class ClienteOficial(Cliente):
    """Cliente de diario.py restringido a los hosts oficiales, sin redirecciones a otros hosts y con tope de tamaño."""

    def traer(self, url, tipo=None):
        if urlsplit(url).netloc not in HOSTS:
            raise Rechazado(f"host no permitido: {url}")
        r = self.get(url)
        for paso in r.history + [r]:
            if urlsplit(paso.url).netloc not in HOSTS:
                raise Rechazado(f"redirección fuera de los hosts oficiales: {paso.url}")
        if len(r.content) > MAX_BYTES:
            raise Rechazado(f"{len(r.content)} bytes en {url}")
        if tipo == "pdf" and not (r.content[:5] == b"%PDF-" and "pdf" in r.headers.get("Content-Type", "")):
            raise Rechazado(f"no es un PDF: {url} ({r.headers.get('Content-Type')})")
        return r


# ---------------------------------------------------------------- archivos

NOMBRE_SEGURO = re.compile(r"^[a-z0-9][a-z0-9._-]{0,150}$")


def ruta_segura(base, nombre):
    """Ruta dentro de base para un nombre derivado de datos externos (evita salir de la carpeta)."""
    if not NOMBRE_SEGURO.match(nombre):
        raise Rechazado(f"nombre de archivo no válido: {nombre!r}")
    return base / nombre


def escribir_atomico(ruta, datos):
    ruta.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=ruta.parent, prefix=".tmp-")
    with os.fdopen(fd, "wb") as fh:
        fh.write(datos)
    os.replace(tmp, ruta)


def guardar_gz(ruta, datos):
    escribir_atomico(ruta, gzip.compress(datos, mtime=0))


def leer_gz(ruta):
    return gzip.decompress(ruta.read_bytes())


def sha256(datos):
    return hashlib.sha256(datos).hexdigest()


def escribir_csv(ruta, columnas, filas):
    """CSV UTF-8 con saltos LF, escrito de forma atómica (si se corta, queda el anterior)."""
    ruta.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=ruta.parent, prefix=".tmp-", suffix=".csv")
    with os.fdopen(fd, "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=columnas, lineterminator="\n", extrasaction="ignore")
        w.writeheader()
        for f in filas:
            w.writerow({k: lista(v) for k, v in f.items()})
    os.replace(tmp, ruta)


def filas_urls():
    """Filas de los CSV de notas de data/urls (no los registros de sitemaps)."""
    return [f for r in sorted(DIR_URLS.glob("*.csv")) if re.match(r"^\d{4}-\d{2}-\d{2}_[a-z]+\.csv$", r.name) for f in leer_csv(r)]


def leer_csv(ruta):
    if not ruta.exists():
        return []
    with open(ruta, encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def lista(v):
    if isinstance(v, (list, tuple, set)):
        return "|".join(str(x) for x in (sorted(v) if isinstance(v, set) else v))
    if isinstance(v, bool):
        return "1" if v else "0"
    return "" if v is None else v


# ---------------------------------------------------------------- texto y fechas

def norm(t):
    t = unicodedata.normalize("NFC", t or "").replace(" ", " ").replace("­", "")
    return re.sub(r"\s+", " ", t).strip()


def sin_tildes(t):
    return "".join(c for c in unicodedata.normalize("NFKD", t) if not unicodedata.combining(c))


def clave(t):
    """Texto en minúsculas, sin tildes ni signos: para comparar textos de dos fuentes."""
    return re.sub(r"[^a-z0-9]+", " ", sin_tildes(t.lower())).strip()


def sha1_corto(t):
    return hashlib.sha1(t.encode("utf-8")).hexdigest()[:10]


def fecha_es(t):
    """'16 octubre 2026', '15 de enero de 2026' → '2026-10-16'."""
    m = re.search(r"(\d{1,2})\s+(?:de\s+)?(" + "|".join(MESES) + r")\s+(?:de\s+|del\s+)?(\d{4})", t or "", re.I)
    return f"{int(m.group(3)):04d}-{MESES[m.group(2).lower()]:02d}-{int(m.group(1)):02d}" if m else None


def fecha_hora_es(t):
    """'Viernes , 23 de Octubre de 2026 a las 00:00 horas' → '2026-10-23T00:00:00-05:00' (o solo la fecha)."""
    m = re.search(r"(\d{1,2}) de (\w+)\s+de (\d{4})(?: a las\s+(\d{1,2}):(\d{2}))?", norm(t), re.I)
    if not m or m.group(2).lower() not in MESES:
        return None
    f = f"{m.group(3)}-{MESES[m.group(2).lower()]:02d}-{int(m.group(1)):02d}"
    return f + (f"T{int(m.group(4)):02d}:{m.group(5)}:00-05:00" if m.group(4) else "")


def ahora():
    return dt.datetime.now(LIMA).replace(microsecond=0)


def mas_dias(fecha, n):
    return (dt.date.fromisoformat(fecha) + dt.timedelta(days=n)).isoformat()


# ---------------------------------------------------------------- regiones (README, "Región")

MACRO_DEPS = {"costa_norte": {"TUMBES", "PIURA", "LAMBAYEQUE", "LA LIBERTAD"},
              "costa_centro": {"ANCASH", "ICA"},
              "lima": {"LIMA", "CALLAO"}}
# En los avisos, Lima usa los de costa centro (README): por eso Lima y Callao cuentan como costa centro.
DEPS_AVISO = {"costa_norte": MACRO_DEPS["costa_norte"],
              "costa_centro": MACRO_DEPS["costa_centro"] | MACRO_DEPS["lima"]}


def regiones_mencionadas(texto):
    """Macro-regiones que nombra un párrafo oficial: costa_norte, costa_centro, lima (vacío = nacional)."""
    t = sin_tildes(texto).lower()
    r = set()
    if re.search(r"costa norte|norte del (mar|litoral)|zona norte del (pais|mar)", t):
        r.add("costa_norte")
    if re.search(r"costa (centro|central)", t):
        r.add("costa_centro")
    if re.search(r"toda la costa|costa peruana|litoral peruano|a lo largo (de toda )?(la costa|del litoral)", t):
        r |= {"costa_norte", "costa_centro", "lima"}
    for macro, deps in MACRO_DEPS.items():
        for d in deps:
            if re.search(r"\b" + d.lower() + r"\b", t):
                r.add(macro)
    return r
