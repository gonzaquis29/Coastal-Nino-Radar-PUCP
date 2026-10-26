"""Macro-región de un texto a partir de los lugares de config/lugares.csv (definición en docs/region/definicion.md).

Cada mención suma el peso de la zona donde aparece (titular, resumen, inicio o resto del cuerpo); una macro-región se
asigna si llega al umbral, y sin ninguna el texto es "nacional".
"""

import collections
import functools
import re

from radar import config
from radar.comun import regiones
from radar.comun.archivos import leer_csv
from radar.comun.texto import sha1_corto, sin_tildes
from radar.noticias.rasgos import PALABRAS_PRIMER_PARRAFO

NACIONAL = "nacional"
PESO_TITULAR = 3
PESO_RESUMEN = 2
PESO_INICIO = 2  # primeras PALABRAS_PRIMER_PARRAFO palabras del cuerpo
PESO_RESTO = 1
UMBRAL_MACROREGION = 2  # una mención fuera del resto del cuerpo, o dos dentro de él
# Palabras de un nombre que no tienen que ir con mayúscula ("Santiago de Chuco", "la Libertad")
CONECTORES = {"de", "del", "la", "las", "los", "el", "y"}
# "provincia del Santa", "distrito de Castilla", "región San Martín": el nivel desambigua un nombre excluido
CONTEXTO = re.compile(
    r"(?P<nivel>region|departamento|gobierno regional|provincia|municipalidad provincial|distrito|"
    r"municipalidad distrital)\s+(?:de\s+|del\s+)?(?:la\s+)?$",
    re.I,
)
NIVEL_DE_CONTEXTO = {
    "region": "departamento",
    "departamento": "departamento",
    "gobierno regional": "departamento",
    "provincia": "provincia",
    "municipalidad provincial": "provincia",
    "distrito": "distrito",
    "municipalidad distrital": "distrito",
}
LARGO_CONTEXTO = 40


def clave(nombre):
    """Forma de comparación de un nombre: sin tildes, en mayúsculas y con espacios simples ('Cañete' → 'CANETE')."""
    return " ".join(sin_tildes(nombre).upper().split())


def es_nombre_propio(texto):
    """Cada palabra significativa empieza con mayúscula: 'La Libertad' sí, 'la libertad de prensa' no."""
    return all(p[0].isupper() for p in texto.split() if p.lower() not in CONECTORES)


@functools.cache
def macro_de_departamento():
    return {d["departamento"]: d["macroregion"] for d in regiones.departamentos()}


class Asignador:
    """Reconoce lugares en un texto. Se emparejan todos los nombres del INEI, del más largo al más corto, para que
    'San Martín de Porres' no cuente como 'San Martín'; solo asignan región los marcados con usar=1."""

    def __init__(self, lugares):
        self.por_clave = collections.defaultdict(list)
        for lugar in lugares:
            self.por_clave[lugar["clave"]].append(lugar)
        self.usables = {
            c: next(lugar for lugar in ls if lugar["usar"] in ("1", True))
            for c, ls in self.por_clave.items()
            if any(lugar["usar"] in ("1", True) for lugar in ls)
        }
        nombres = sorted(self.por_clave, key=len, reverse=True)
        alternativas = "|".join(r"\s+".join(re.escape(p) for p in n.split()) for n in nombres)
        self.patron = re.compile(rf"(?<!\w)(?:{alternativas})(?!\w)", re.I)

    def ocurrencias(self, texto):
        """(posición, clave, es nombre propio) de cada nombre del INEI en el texto ya sin tildes."""
        return [(m.start(), clave(m.group(0)), es_nombre_propio(m.group(0))) for m in self.patron.finditer(texto)]

    def _por_contexto(self, t, inicio, nombre):
        """Macro-región y departamento del nombre en el nivel que dice el texto, si ese nivel lo resuelve."""
        previo = CONTEXTO.search(t[max(0, inicio - LARGO_CONTEXTO) : inicio])
        if not previo:
            return None
        nivel = NIVEL_DE_CONTEXTO[" ".join(previo.group("nivel").lower().split())]
        candidatos = [lugar for lugar in self.por_clave[nombre] if lugar["nivel"] == nivel]
        macros = {macro_de_departamento()[lugar["departamento"]] for lugar in candidatos}
        if len(macros) != 1:
            return None
        deps = {lugar["departamento"] for lugar in candidatos}
        return macros.pop(), deps.pop() if len(deps) == 1 else ""

    def menciones(self, texto):
        """[(posición, macro-regiones, departamento, nombre)] de lugares y expresiones de macro-región."""
        out, t = [], sin_tildes(texto or "")
        for inicio, nombre, propio in self.ocurrencias(t):
            if not propio:
                continue
            if resuelto := self._por_contexto(t, inicio, nombre):
                out.append((inicio, {resuelto[0]}, resuelto[1], nombre))
            elif lugar := self.usables.get(nombre):
                out.append((inicio, {macro_de_departamento()[lugar["departamento"]]}, lugar["departamento"], nombre))
        out += [(inicio, macros, "", "") for inicio, macros in regiones.macroregiones_explicitas(texto)]
        return sorted(out, key=lambda m: m[0])

    def asignar(self, zonas):
        """Macro-regiones de un texto partido en zonas [(texto, peso)]."""
        puntajes, primera, deps, lugares = collections.Counter(), {}, collections.Counter(), []
        for orden, (texto, peso) in enumerate(zonas):
            for inicio, macros, dep, nombre in self.menciones(texto):
                for macro in macros:
                    puntajes[macro] += peso
                    primera.setdefault(macro, (orden, inicio))
                if dep:
                    deps[dep] += peso
                if nombre and nombre not in lugares:
                    lugares.append(nombre)
        asignadas = sorted(m for m, p in puntajes.items() if p >= UMBRAL_MACROREGION)
        principal = min(asignadas, key=lambda m: (-puntajes[m], primera[m])) if asignadas else NACIONAL
        return {
            "macroregiones": asignadas or [NACIONAL],
            "macroregion_principal": principal,
            "departamentos": sorted(d for d, p in deps.items() if p >= UMBRAL_MACROREGION),
            "lugares": lugares,
            "puntajes": [f"{m}:{p}" for m, p in sorted(puntajes.items())],
        }


def zonas_nota(titular, resumen, cuerpo=None):
    """Zonas de una nota con su peso; sin cuerpo (lo guardado en notas.csv) quedan titular y resumen."""
    zonas = [(titular, PESO_TITULAR), (resumen, PESO_RESUMEN)]
    if cuerpo:
        palabras = cuerpo.split()
        zonas += [
            (" ".join(palabras[:PALABRAS_PRIMER_PARRAFO]), PESO_INICIO),
            (" ".join(palabras[PALABRAS_PRIMER_PARRAFO:]), PESO_RESTO),
        ]
    return zonas


@functools.cache
def lugares():
    return tuple(leer_csv(config.ARCHIVO_LUGARES))


@functools.cache
def asignador():
    """Asignador con la lista vigente de config/lugares.csv."""
    return Asignador(lugares())


def version_lugares():
    """Huella de config/lugares.csv: dice con qué lista se asignó cada fila."""
    return sha1_corto(config.ARCHIVO_LUGARES.read_text(encoding="utf-8"))


def asignar_nota(titular, resumen, cuerpo=None):
    return asignador().asignar(zonas_nota(titular, resumen, cuerpo))
