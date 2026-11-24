"""Descarga las fuentes del mapa y deja todo listo para la API.

Uso: python -m radar.monitoreo.actualizar      # unos 2 minutos; si una fuente falla, conserva su último dato
"""

import datetime as dt
import logging
import sys

from radar import config
from radar.comun.archivos import guardar_json, leer_json
from radar.comun.candado import exclusivo
from radar.comun.http import Cliente
from radar.monitoreo import fuentes, zonas

log = logging.getLogger(__name__)
HOSTS = (config.HOST_SENAMHI, config.HOST_SENAMHI_GIS, config.HOST_GOB, config.HOST_USGS)
VACIO = {"avisos": [], "notas": [], "sismos": [], "zonas": {}, "fuentes": {}}


def actualizar(cliente, ahora):
    guardado = {**VACIO, **(leer_json(config.ARCHIVO_MONITOREO) or {})}
    marca = ahora.strftime("%Y-%m-%dT%H:%M:%S")

    def leer(clave, funcion):
        estado = guardado["fuentes"].setdefault(clave, {"ok": "", "n": 0, "error": ""})
        try:
            guardado[clave] = funcion()
            estado.update(ok=marca, n=len(guardado[clave]), error="")
        except Exception as e:  # una fuente caída no tumba al resto: se conserva su último dato y se declara
            log.warning("%s: %s", clave, e)
            estado["error"] = marca

    leer("sismos", lambda: fuentes.sismos(cliente, ahora))
    leer("avisos", lambda: fuentes.avisos(cliente, ahora.year))
    leer("notas", lambda: fuentes.notas_indeci(cliente))
    indice, leidos, fallos = zonas.construir(cliente, guardado["avisos"], ahora.date())
    estado = guardado["fuentes"].setdefault("zonas", {"ok": "", "n": 0, "error": ""})
    if fallos:
        log.warning("mapas sin descargar: %s", ", ".join(fallos))
        estado["error"] = marca
        guardado["zonas"] = {**guardado["zonas"], **indice}
    else:
        estado.update(ok=marca, n=leidos, error="")
        guardado["zonas"] = indice
    guardado["actualizado"] = marca
    guardar_json(config.ARCHIVO_MONITOREO, guardado)
    return guardado


@exclusivo("monitoreo")
def main():
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    g = actualizar(Cliente(HOSTS), dt.datetime.now(config.LIMA))
    for clave, e in g["fuentes"].items():
        falla = " (falló ahora)" if e["error"] else ""
        print(f"{clave}: {e['n']} registros, último correcto {e['ok'] or 'nunca'}{falla}")
    return 1 if any(e["error"] for e in g["fuentes"].values()) else 0


if __name__ == "__main__":
    sys.exit(main())
