"""Macro-regiones del README, leídas de config/regiones.csv (único lugar donde se definen)."""

import functools
import re

from radar import config
from radar.comun.archivos import leer_csv
from radar.comun.texto import sin_tildes

COSTA_NORTE, COSTA_CENTRO, LIMA_Y_CALLAO, OTRAS = "costa_norte", "costa_centro", "lima", "otras"
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


@functools.cache
def departamentos_litoral():
    """Departamentos con litoral (columna litoral de config/regiones.csv)."""
    return frozenset(d["departamento"] for d in departamentos() if d["litoral"] == "1")


# Expresiones que nombran una macro-región sin nombrar un lugar. "Norte del país" y "costa sur" no aparecen en los
# textos oficiales de 2026 con otro sentido; se usan para las notas (docs/region/definicion.md).
EXPRESIONES_MACROREGION = (
    (
        re.compile(r"costa norte|norte del (?:mar|litoral|pais)|zona norte del (?:pais|mar)|norte peruano"),
        {COSTA_NORTE},
    ),
    (re.compile(r"costa (?:centro|central)"), {COSTA_CENTRO}),
    (re.compile(r"costa sur|sur del pais"), {OTRAS}),
    (
        re.compile(r"toda la costa|costa peruana|litoral peruano|a lo largo (?:de toda )?(?:la costa|del litoral)"),
        {COSTA_NORTE, COSTA_CENTRO, LIMA_Y_CALLAO},
    ),
)


def macroregiones_explicitas(texto):
    """[(posición, {macro-regiones})] de las expresiones de macro-región del texto ('costa norte', 'toda la costa')."""
    t = sin_tildes(texto or "").lower()
    return sorted((m.start(), macros) for patron, macros in EXPRESIONES_MACROREGION for m in patron.finditer(t))


def regiones_mencionadas(texto):
    """Macro-regiones que nombra un texto oficial (conjunto vacío = nacional)."""
    t = sin_tildes(texto).lower()
    encontradas = set().union(*(macros for _, macros in macroregiones_explicitas(t))) - {OTRAS}
    for macro, deps in deps_por_macroregion().items():
        if macro == OTRAS:
            continue
        if any(re.search(r"\b" + d.lower() + r"\b", t) for d in deps):
            encontradas.add(macro)
    return encontradas
