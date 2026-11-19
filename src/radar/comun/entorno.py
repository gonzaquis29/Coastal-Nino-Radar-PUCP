"""Secretos locales: la variable de entorno manda; si no está, se busca en el `.env` de la raíz del repo (ignorado
por git). Nunca se imprimen ni se registran."""

from radar import config


def leer_env(ruta=None):
    ruta = ruta or config.ARCHIVO_ENTORNO
    valores = {}
    if not ruta.exists():
        return valores
    for linea in ruta.read_text(encoding="utf-8").splitlines():
        linea = linea.strip()
        if not linea or linea.startswith("#") or "=" not in linea:
            continue
        nombre, valor = linea.split("=", 1)
        valores[nombre.strip()] = valor.strip().strip("\"'")
    return valores


def valor(nombre, ruta=None):
    import os

    return (os.environ.get(nombre) or "").strip() or leer_env(ruta).get(nombre, "")
