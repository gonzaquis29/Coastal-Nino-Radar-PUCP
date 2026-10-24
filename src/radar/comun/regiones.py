"""Macro-regiones del README, leídas de config/regiones.csv (único lugar donde se definen)."""

import functools
import re

from radar import config
from radar.comun.archivos import leer_csv
from radar.comun.texto import sin_tildes

COSTA_NORTE, COSTA_CENTRO, LIMA, OTRAS, NACIONAL = "costa_norte", "costa_centro", "lima", "otras", "nacional"
MACROREGIONES_COSTA = (COSTA_NORTE, COSTA_CENTRO)


@functools.cache
def departamentos():
    """Filas de config/regiones.csv: departamento, nombre, macroregion, macroregion_avisos."""
    return tuple(leer_csv(config.ARCHIVO_REGIONES))


@functools.cache
def deps_por_macroregion():
    """{macroregión: {departamentos}} según la macro-región del análisis."""
    out = {}
    for d in departamentos():
        out.setdefault(d["macroregion"], set()).add(d["departamento"])
    return out


@functools.cache
def deps_por_macroregion_avisos():
    """{macroregión de avisos: {departamentos}}: Lima y Callao cuentan como costa centro."""
    out = {}
    for d in departamentos():
        if d["macroregion_avisos"]:
            out.setdefault(d["macroregion_avisos"], set()).add(d["departamento"])
    return out


@functools.cache
def macroregion_de_avisos(macroregion):
    """Macro-región cuyos avisos aplican a una macro-región de consulta (None si no tiene avisos)."""
    for d in departamentos():
        if d["macroregion"] == macroregion and d["macroregion_avisos"]:
            return d["macroregion_avisos"]
    return None


@functools.cache
def estaciones_costa():
    """Estaciones de referencia: [(nombre, macroregión, longitud, latitud)] de config/estaciones_costa.csv."""
    return tuple(
        (e["nombre"], e["macroregion"], float(e["longitud"]), float(e["latitud"]))
        for e in leer_csv(config.ARCHIVO_ESTACIONES)
    )


def regiones_mencionadas(texto):
    """Macro-regiones que nombra un texto oficial (conjunto vacío = nacional)."""
    t = sin_tildes(texto).lower()
    encontradas = set()
    if re.search(r"costa norte|norte del (mar|litoral)|zona norte del (pais|mar)", t):
        encontradas.add(COSTA_NORTE)
    if re.search(r"costa (centro|central)", t):
        encontradas.add(COSTA_CENTRO)
    if re.search(r"toda la costa|costa peruana|litoral peruano|a lo largo (de toda )?(la costa|del litoral)", t):
        encontradas |= {COSTA_NORTE, COSTA_CENTRO, LIMA}
    for macro, deps in deps_por_macroregion().items():
        if macro == OTRAS:
            continue
        if any(re.search(r"\b" + d.lower() + r"\b", t) for d in deps):
            encontradas.add(macro)
    return encontradas
