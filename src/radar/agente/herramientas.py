"""Las cuatro herramientas del agente (docs/agente/definicion.md) y sus respuestas con plantilla y citas literales.

Ninguna redacta con un LLM: cada respuesta es una plantilla fija más fragmentos copiados tal cual de los párrafos
oficiales, y `citas_literales` comprueba que cada fragmento exista en su párrafo.
"""

import functools
import re

import numpy as np

from radar.analitica import recomendador
from radar.nlp import semaforo
from radar.oficial.vigencia import Corpus

CITAS = 3  # párrafos citados por respuesta
LARGO_CITA = 320  # caracteres como máximo; se corta en el final de una oración
TIPOS_FUERA = {"definicion"}
FIN_ORACION = re.compile(r"(?<=[.;:])\s")
EXPLICACION = {
    "rojo": "contradice algún dato del comunicado vigente",
    "amarillo": "tiene datos desactualizados, sin respaldo o de otra escala",
    "verde": "coincide con lo oficial o habla de lo mismo",
    "gris": "no habla de lo mismo que los textos oficiales vigentes",
}


@functools.cache
def corpus():
    return Corpus()


class Oficial:
    """buscar_oficial: los párrafos vigentes en la fecha más parecidos a la consulta (minilm, índice en memoria)."""

    def __init__(self, base=None):
        self.base = base or corpus()
        self.modelo = semaforo._semaforo().modelo  # el mismo minilm del semáforo: se carga una sola vez
        self.parrafos = [p for p in self.base.parrafos if p["tipo"] not in TIPOS_FUERA and p["texto"].strip()]
        self.indice = {p["id"]: i for i, p in enumerate(self.parrafos)}
        self.vectores = np.asarray(self.modelo.embeber([p["texto"] for p in self.parrafos]))

    def embeber(self, textos):
        return np.asarray(self.modelo.embeber(list(textos)))

    def buscar(self, consulta, fecha, macroregion=None, k=CITAS):
        vigentes = [self.indice[p["id"]] for p in self.base.parrafos_vigentes(fecha, macroregion)
                    if p["id"] in self.indice]  # fmt: skip
        if not vigentes:
            return []
        q = self.embeber([consulta])[0]
        puntajes = self.vectores[vigentes] @ q
        orden = np.argsort(-puntajes, kind="stable")[:k]
        return [dict(self.parrafos[vigentes[i]], puntaje=round(float(puntajes[i]), 4)) for i in orden]


@functools.cache
def oficial():
    return Oficial()


def cita(texto, largo=LARGO_CITA):
    """El comienzo del párrafo hasta el último final de oración dentro de `largo`: siempre un fragmento literal."""
    if len(texto) <= largo:
        return texto
    cortes = [m.start() for m in FIN_ORACION.finditer(texto) if m.start() <= largo]
    return texto[: cortes[-1]] if cortes else texto[:largo]


def _fuente(p):
    return {"cita": cita(p["texto"]), "parrafo": p["id"], "documento": p["doc_id"], "fuente": p["fuente"]}


def citas_literales(respuesta, parrafos):
    """(citas que existen tal cual en su párrafo, citas)."""
    textos = {p["id"]: p["texto"] for p in parrafos}
    citas = respuesta["citas"]
    return sum(c["cita"] in textos.get(c["parrafo"], "") for c in citas), len(citas)


# ---------------------------------------------------------------- respuestas por herramienta


def estado_vigente(fecha, macroregion):
    e = corpus().estado_vigente(fecha, macroregion)
    c = e["comunicado"]
    if not c:
        return {"herramienta": "estado_vigente", "texto": f"No hay comunicado del ENFEN vigente el {fecha}.",
                "citas": [], "datos": e}  # fmt: skip
    avisos = e["avisos"]
    lineas = [f"Estado vigente el {fecha} según el comunicado {c['id']} del ENFEN (emitido el {c['fecha_emision']}): "
              f"{c['estado']}."]  # fmt: skip
    if c["magnitud_max_prevista"]:
        lineas.append(f"Magnitud máxima prevista: {c['magnitud_max_prevista']}.")
    if avisos:
        lineas.append(f"Avisos del Senamhi que aplican en {macroregion}: "
                      + "; ".join(f"N.° {a['numero']} ({a['tipo']}, nivel {a['nivel']}, {a['estado_en_fecha']})"
                                  for a in avisos) + ".")  # fmt: skip
    else:
        lineas.append(f"No hay avisos del Senamhi que apliquen en {macroregion} ese día.")
    return {"herramienta": "estado_vigente", "texto": " ".join(lineas), "citas": [], "datos": e}


def buscar_oficial(consulta, fecha, macroregion=None):
    parrafos = oficial().buscar(consulta, fecha, macroregion)
    if not parrafos:
        return {"herramienta": "buscar_oficial", "texto": f"No hay textos oficiales vigentes el {fecha}.", "citas": []}
    return {"herramienta": "buscar_oficial", "texto": f"Lo que dicen los textos oficiales vigentes el {fecha}:",
            "citas": [_fuente(p) for p in parrafos]}  # fmt: skip


def medir_discrepancia(texto, fecha):
    r = semaforo.medir_discrepancia("", fecha, titular=texto)
    citas = []
    if r["parrafo"]:
        p = next(p for p in corpus().parrafos if p["id"] == r["parrafo"])
        citas.append(_fuente(p))
    explicacion = EXPLICACION.get(r["color"], r["color"])
    texto_r = f"Semáforo: {r['color']} ({r['origen']}). El texto {explicacion}. Párrafo oficial más cercano:"
    return {"herramienta": "medir_discrepancia", "texto": texto_r, "citas": citas, "datos": r}


def recomendar(fecha, macroregion, interes, texto=""):
    q = oficial().embeber([texto])[0] if texto else None
    puntaje = (lambda textos: oficial().embeber(textos) @ q) if q is not None else None
    r = recomendador.oficial(corpus(), fecha, macroregion, interes, puntaje)
    citas = [_fuente(p) for p in r["parrafos"][:CITAS]]
    c = r["comunicado"]
    avisos = "; ".join(f"N.° {a['numero']} ({a['tipo']}, {a['nivel']})" for a in r["avisos"]) or "ninguno"
    cabecera = (f"Para {interes} en {macroregion} el {fecha}: comunicado {c['id'] if c else 'ninguno'} del ENFEN; "
                f"avisos del Senamhi: {avisos}. Párrafos del comunicado sobre {interes}:")  # fmt: skip
    return {"herramienta": "recomendar", "texto": cabecera, "citas": citas, "datos": r}


FUERA_DE_ALCANCE = ("Solo respondo sobre El Niño costero, el clima y lo que dicen el ENFEN y el Senamhi. Esta consulta "
                    "no trata de eso.")  # fmt: skip
