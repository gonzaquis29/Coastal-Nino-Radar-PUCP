"""Validación del arreglo de citas por número (8-nov-2026, docs/noticias/definicion.md): una cita "Comunicado N.° x"
solo es del ENFEN si cerca se nombra al ENFEN o a El Niño. Relee en memoria las notas con nivel `numero` y compara
la regla anterior con la nueva. Solo guarda conteos; nunca el texto.

Uso: python -m radar.noticias.validar_citas
"""

import argparse
import collections
import datetime as dt
import logging
import sys

from radar import config
from radar.comun.archivos import leer_csv
from radar.comun.candado import exclusivo
from radar.comun.http import Cliente
from radar.comun.registro import configurar
from radar.comun.texto import ahora
from radar.noticias import rasgos
from radar.noticias.medios import MEDIOS
from radar.noticias.validar_texto import marcar_vistas, notas_vistas
from radar.noticias.viabilidad import _si, criterio, guardar, reporte
from radar.oficial.vigencia import Corpus

log = logging.getLogger(__name__)

PRUEBA = "Citas por número del ENFEN"
INFO = "Citas por número del ENFEN (informativo)"
MUESTRA = "citas-numero-8nov"
DIAS_COHERENCIA = 60  # R2: el comunicado citado es el vigente o salió en los 60 días anteriores a la nota
COHERENCIA_MINIMA = 0.90  # R2
RETENCION_MINIMA = 0.95  # R3


def ids(celda, nivel=None):
    """Ids de comunicados de una celda `id:nivel|…`, de un nivel o de todos los demás (nivel='otros')."""
    pares = [p.split(":") for p in (celda or "").split("|") if p]
    if nivel == "otros":
        return {i for i, n in pares if n != "numero"}
    return {i for i, n in pares if nivel is None or n == nivel}


def con_numero(notas, vistas):
    """Las notas con nivel `numero`, sin las notas sobre El Niño que nadie ha visto (reservadas para T5)."""
    return [n for n in notas if ids(n["comunicados"], "numero")
            and not (_si(n["sobre_nino"]) and (n["medio"], n["id"]) not in vistas)]  # fmt: skip


def coherente(id_, fecha, corpus):
    """El comunicado citado es el vigente en la fecha de la nota o se emitió en los DIAS_COHERENCIA anteriores."""
    vigente = corpus.comunicado_vigente(fecha)
    emision = {c["id"]: c["fecha_emision"] for c in corpus.comunicados}.get(id_)
    if not emision:
        return False
    dias = (dt.date.fromisoformat(fecha) - dt.date.fromisoformat(emision)).days
    return bool(vigente and vigente["id"] == id_) or 0 <= dias <= DIAS_COHERENCIA


def comparar(nota, campos):
    """{antes, despues, otras}: las citas por número con la regla anterior (lo guardado) y con la nueva."""
    nuevos = rasgos.comunicados(f"{campos['resumen']} {campos['cuerpo']}", campos["enlaces"])
    return {"antes": ids(nota["comunicados"], "numero"), "despues": ids("|".join(nuevos), "numero"),
            "otras": ids("|".join(nuevos), "otros")}  # fmt: skip


def criterios(casos, corpus):
    """casos: [(nota, {antes, despues, otras})]."""
    quedan, salen, retenidas, con_otra = [], [], 0, 0
    por_sobre = collections.Counter()
    for nota, c in casos:
        fecha = nota["fecha_publicacion"][:10]
        for i in c["antes"]:
            (quedan if i in c["despues"] else salen).append(coherente(i, fecha, corpus))
            if i not in c["despues"]:
                por_sobre["sobre El Niño" if _si(nota["sobre_nino"]) else "otros temas"] += 1
            if i in c["otras"]:
                con_otra += 1
                retenidas += i in c["despues"]
    coh = sum(quedan) / len(quedan) if quedan else None
    ret = retenidas / con_otra if con_otra else None
    return [
        criterio(PRUEBA, "R2. Coherencia temporal de las citas que quedan", f"{sum(quedan)}/{len(quedan)}",
                 f"≥ {COHERENCIA_MINIMA:.0%}", coh is not None and coh >= COHERENCIA_MINIMA),
        criterio(PRUEBA, "R3. Retención con otra vía al mismo comunicado", f"{retenidas}/{con_otra}",
                 f"≥ {RETENCION_MINIMA:.0%}", ret is not None and ret >= RETENCION_MINIMA),
        criterio(INFO, "R4. Citas que salen", len(salen), "", True,
                 f"{dict(por_sobre)}; coherentes {sum(salen)}/{len(salen)}"),
    ]  # fmt: skip


def leer(elegidas):
    """(nota, campos) de cada nota, leída una vez y en memoria."""
    for nombre in MEDIOS:
        filas = [n for n in elegidas if n["medio"] == nombre]
        if not filas:
            continue
        medio = MEDIOS[nombre](Cliente(hosts_permitidos={config.HOSTS_MEDIOS[nombre]}))
        for fila, campos in medio.descargar(filas):
            if isinstance(campos, dict) and not campos["sin_texto"]:
                yield next(n for n in filas if n["id"] == fila["id"]), campos
            else:
                log.info(f"  sin texto o con error: {nombre} {fila['id']}")


@exclusivo("radar.noticias.validar_citas")
def main(argv=None):
    argparse.ArgumentParser(description="Validación del arreglo de citas por número.").parse_args(argv)
    registro = configurar("noticias-validar-citas")
    inicio = ahora()
    vistas = notas_vistas()
    elegidas = con_numero(leer_csv(config.DIR_NOTICIAS / "notas.csv"), vistas)
    log.info(f"Notas con citas por número: {len(elegidas)} · {collections.Counter(n['medio'] for n in elegidas)}")
    casos = [(nota, comparar(nota, campos)) for nota, campos in leer(elegidas)]
    marcar_vistas([n for n in elegidas if (n["medio"], n["id"]) not in vistas], MUESTRA)
    filas = [criterio(INFO, "notas leídas", f"{len(casos)}/{len(elegidas)}", "", True),
             *criterios(casos, Corpus())]  # fmt: skip
    guardar(filas)
    reporte(filas, [], inicio)
    log.info(f"Duración: {(ahora() - inicio).total_seconds() / 60:.1f} min · registro: {registro}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
