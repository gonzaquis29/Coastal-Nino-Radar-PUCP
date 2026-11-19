"""Avance de un proceso largo en pantalla: hechos, porcentaje, ritmo y tiempo que falta (aprox.)."""

import logging
import time

log = logging.getLogger(__name__)

CADA_SEGUNDOS = 15.0


def duracion(segundos):
    segundos = max(0, int(segundos))
    if segundos < 60:
        return f"{segundos} s"
    if segundos < 3600:
        return f"{segundos // 60} min {segundos % 60:02d} s"
    return f"{segundos // 3600} h {segundos % 3600 // 60:02d} min"


class Avance:
    """`paso()` por cada unidad hecha; informa cada CADA_SEGUNDOS y al terminar. `previos` son los ya hechos en una
    ejecución anterior (se muestran, pero no cuentan para el ritmo)."""

    def __init__(self, nombre, total, previos=0, cada=CADA_SEGUNDOS, reloj=time.monotonic, salida=None):
        self.nombre, self.total, self.previos = nombre, total, previos
        self.hechos = 0
        self.cada, self.reloj = cada, reloj
        self.salida = salida or log.info
        self.inicio = self.ultimo = reloj()
        if previos:
            self.salida(f"{nombre}: {previos} de {previos + total} ya hechos antes; faltan {total}")

    def texto(self):
        transcurrido = self.reloj() - self.inicio
        hechos, total = self.previos + self.hechos, self.previos + self.total
        porcentaje = 100 * hechos / total if total else 100.0
        partes = [f"{self.nombre}: {hechos} de {total} ({porcentaje:.0f} %)"]
        if self.hechos and transcurrido > 0:
            ritmo = self.hechos / transcurrido
            partes.append(f"{ritmo * 60:.0f}/min")
            if self.hechos < self.total:
                partes.append(f"faltan ~{duracion((self.total - self.hechos) / ritmo)}")
        partes.append(f"van {duracion(transcurrido)}")
        return ", ".join(partes)

    def paso(self, n=1):
        self.hechos += n
        ahora = self.reloj()
        if self.hechos >= self.total or ahora - self.ultimo >= self.cada:
            self.ultimo = ahora
            self.salida(self.texto())
