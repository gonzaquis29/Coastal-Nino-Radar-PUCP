"""Archivos: rutas seguras, escritura atómica, CSV, gzip, JSON y estado de descargas."""

import csv
import gzip
import hashlib
import io
import json
import os
import re
import tempfile

NOMBRE_SEGURO = re.compile(r"^[a-z0-9][a-z0-9._-]{0,150}$")


class NombreInvalido(ValueError):
    """Un nombre de archivo que viene de datos externos no es seguro."""


def ruta_segura(base, nombre):
    """Ruta dentro de base para un nombre que viene de datos externos (evita salir de la carpeta)."""
    if not NOMBRE_SEGURO.match(nombre):
        raise NombreInvalido(f"nombre de archivo no válido: {nombre!r}")
    return base / nombre


def escribir_atomico(ruta, datos):
    """Escribe en un temporal de la misma carpeta y lo renombra: si se corta, queda el archivo anterior."""
    ruta.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporal = tempfile.mkstemp(dir=ruta.parent, prefix=".tmp-")
    try:
        with os.fdopen(descriptor, "wb") as archivo:
            archivo.write(datos)
        os.replace(temporal, ruta)
    except BaseException:
        if os.path.exists(temporal):
            os.remove(temporal)
        raise


def guardar_gz(ruta, datos):
    escribir_atomico(ruta, gzip.compress(datos, mtime=0))


def leer_gz(ruta):
    return gzip.decompress(ruta.read_bytes())


def sha256(datos):
    return hashlib.sha256(datos).hexdigest()


def a_celda(valor):
    """Valor de Python → texto de una celda CSV (listas y conjuntos unidos con '|', booleanos como 1/0)."""
    if isinstance(valor, set):
        return "|".join(str(x) for x in sorted(valor))
    if isinstance(valor, list | tuple):
        return "|".join(str(x) for x in valor)
    if isinstance(valor, bool):
        return "1" if valor else "0"
    return "" if valor is None else valor


def escribir_csv(ruta, columnas, filas):
    """CSV UTF-8 con saltos LF, de forma atómica. Una columna que no está en el esquema es un error."""
    texto = io.StringIO()
    escritor = csv.DictWriter(texto, fieldnames=columnas, lineterminator="\n", extrasaction="raise")
    escritor.writeheader()
    for fila in filas:
        escritor.writerow({k: a_celda(v) for k, v in fila.items()})
    escribir_atomico(ruta, texto.getvalue().encode("utf-8"))


def anexar_csv(ruta, columnas, filas):
    """Agrega filas (con encabezado si el archivo es nuevo)."""
    nuevo = not ruta.exists()
    ruta.parent.mkdir(parents=True, exist_ok=True)
    with open(ruta, "a", encoding="utf-8", newline="") as archivo:
        escritor = csv.DictWriter(archivo, fieldnames=columnas, lineterminator="\n")
        if nuevo:
            escritor.writeheader()
        escritor.writerows({k: a_celda(v) for k, v in fila.items()} for fila in filas)


def leer_csv(ruta):
    if not ruta.exists():
        return []
    with open(ruta, encoding="utf-8", newline="") as archivo:
        return list(csv.DictReader(archivo))


def leer_json(ruta, defecto=None):
    return json.loads(ruta.read_text(encoding="utf-8")) if ruta.exists() else defecto


def guardar_json(ruta, datos):
    escribir_atomico(ruta, json.dumps(datos, ensure_ascii=False, indent=1, sort_keys=True).encode("utf-8"))


class EstadoDescargas:
    """Qué se descargó y con qué huella. Se guarda cada `cada` cambios y al salir, aunque sea por un error."""

    def __init__(self, ruta, cada=20):
        self.ruta, self.cada, self.pendientes = ruta, cada, 0
        self.datos = leer_json(ruta, {})

    def get(self, clave):
        """Lo registrado para una clave ({} si nunca se descargó)."""
        return self.datos.get(clave, {})

    def __iter__(self):
        return iter(self.datos)

    def marcar(self, clave, valor):
        self.datos[clave] = valor
        self.pendientes += 1
        if self.pendientes >= self.cada:
            self.guardar()

    def guardar(self):
        guardar_json(self.ruta, self.datos)
        self.pendientes = 0

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.guardar()
        return False
