"""Referencias externas de lugar, sin etiquetado manual: la sección regional de la dirección de RPP, la sección local
de El Tiempo (Piura), las secciones regionales y locales de Andina (data/urls) y la sección de regiones de Exitosa.

Las notas se parten en dos mitades fijas (por el hash de su id): con una se decide qué nombres se usan
(lugares.py) y con la otra se evalúa (notas.py), para no medir el acierto sobre lo mismo que se ajustó.
"""

import functools
import hashlib
import logging
from urllib.parse import urlsplit

from radar import config
from radar.comun import regiones
from radar.comun.archivos import leer_csv
from radar.comun.texto import clave
from radar.noticias import esquemas
from radar.noticias.filtro import seccion_principal
from radar.noticias.medios import MEDIOS
from radar.recoleccion.urls import filas_de_notas

log = logging.getLogger(__name__)

CALIBRACION, EVALUACION = 0, 1
DEPARTAMENTO_ELTIEMPO = "PIURA"  # El Tiempo es un diario de Piura: su sección "local" es esa región
SECCION_LOCAL_ELTIEMPO = "local"
SECCIONES_ANDINA = {"regionales": "regional", "locales": "lima"}
SECCION_REGIONES_EXITOSA = "exitosa-peru"


def mitad(ident):
    """0 (calibración) o 1 (evaluación), fija para cada nota."""
    return int(hashlib.sha1(ident.encode("utf-8")).hexdigest(), 16) % 2


@functools.cache
def _macro_por_slug():
    return {clave(d["departamento"]).replace(" ", "-"): d["macroregion"] for d in regiones.departamentos()}


def macro_rpp(url):
    """Macro-región de la sección de RPP: /peru/<departamento>/… o /lima/… (Lima Metropolitana); None si no es
    una sección regional (/peru/actualidad/, /politica/…)."""
    partes = urlsplit(url).path.strip("/").split("/")
    if len(partes) < 3:
        return None
    if partes[0] == "lima":
        return regiones.LIMA_Y_CALLAO
    return _macro_por_slug().get(partes[1]) if partes[0] == "peru" else None


def notas_leidas():
    """Notas de 2026 ya leídas por el histórico (data/raw/noticias/<medio>/notas.csv), sin duplicados. Se leen
    mientras el histórico puede estar escribiendo: una última fila incompleta se salta."""
    notas, vistas = [], set()
    for medio in MEDIOS:
        for n in leer_csv(config.DIR_RAW_NOTICIAS / medio / "notas.csv"):
            if None in n.values() or len(n) != len(esquemas.NOTAS):
                log.debug("fila incompleta en %s/notas.csv: %s", medio, n.get("id"))
                continue
            if (n["medio"], n["id"]) not in vistas and n["fecha_publicacion"][:10] >= config.INICIO.isoformat():
                vistas.add((n["medio"], n["id"]))
                notas.append(n)
    return notas


def referencia_rpp(notas):
    """Todas las notas de RPP con su macro-región de sección (None si no es regional): las leídas con titular y
    resumen, y las de la lista del archivo que no se leyeron, con su título."""
    leidas = {n["id"]: n for n in notas if n["medio"] == "rpp"}
    filas = [
        {"id": n["id"], "titular": n["titular"], "resumen": n["resumen"], "url": n["url"]} for n in leidas.values()
    ]
    for f in leer_csv(config.DIR_RAW_NOTICIAS / "rpp" / "lista.csv"):
        if f.get("url") and f.get("titulo") and f["id"] not in leidas:
            filas.append({"id": f["id"], "titular": f["titulo"], "resumen": "", "url": f["url"]})
    for f in filas:
        f["macro"], f["seccion"] = macro_rpp(f["url"]), seccion_principal(f["url"])
    return filas


def secciones_andina():
    """{id: 'regional' o 'lima'} de las notas de Andina que la recolección diaria vio en esas secciones."""
    out = {}
    for f in filas_de_notas("andina"):
        tipos = {SECCIONES_ANDINA[s] for s in f["seccion"].split("|") if s in SECCIONES_ANDINA}
        if len(tipos) == 1:
            out[f["id"]] = tipos.pop()
    return out
