"""Prueba externa de notas de 2025 (docs/app/definicion.md, sección 13.3): Andina y RPP, fuera del período.

python -m radar.noticias.externa prueba   ->  20 notas por medio: ¿funcionan las vías y traen etiquetas?
python -m radar.noticias.externa leer     ->  data/processed/externa/notas-2025.csv (reanudable)

Andina, uno de cada dos números de nota del rango de octubre a diciembre de 2025; RPP, todo su archivo por día. No se
filtra por palabras antes de leer, para que la prueba no favorezca al filtro de tema. El cuerpo se procesa en memoria y
no se guarda; nada se escribe en notas.csv.
"""

import argparse
import concurrent.futures
import datetime as dt
import logging
import random
import threading

import requests

from radar import config
from radar.comun.archivos import anexar_csv, leer_csv
from radar.comun.candado import exclusivo
from radar.comun.energia import sin_suspension
from radar.comun.http import Cliente
from radar.comun.registro import configurar, describir
from radar.noticias import esquemas
from radar.noticias.medios import DETENER, ERRORES_RED, Andina, NoExiste, Rpp, _dias, filas_de_nota
from radar.noticias.nota import NotaInvalida

log = logging.getLogger(__name__)

DESDE, HASTA = dt.date(2025, 10, 1), dt.date(2025, 12, 31)
# Andina numera unas 3.800 notas por mes (enero a abril de 2026); el rango cubre de octubre a diciembre de 2025 con
# margen, y las notas fuera de las fechas se descartan al leerlas. 1.046.700 ≈ 1-oct-2025 (prueba del 23-nov)
ANDINA_DESDE, ANDINA_HASTA = config.ANDINA_PRIMER_ID - 11_000, config.ANDINA_PRIMER_ID
ANDINA_CADA = 2  # uno de cada dos números
PRUEBA_POR_MEDIO = 20
SUBIR_TRAS = 200  # respuestas sin error seguidas para volver a subir un hilo
SEMILLA_PRUEBA = "externa-prueba-20261123"
MUESTRA = "externa-2025"  # columna muestra de las filas
DIR = config.DIR_DATOS / "processed" / "externa"
ARCHIVO = DIR / "notas-2025.csv"
INTENTOS = DIR / "intentos-2025.csv"  # números o direcciones sin nota, para no volver a pedirlos
COLUMNAS_INTENTOS = ("medio", "id", "estado", "detalle")


_ESCRITURA = threading.Lock()  # los dos medios escriben en los mismos archivos


def _anexar(ruta, columnas, filas):
    with _ESCRITURA:
        anexar_csv(ruta, columnas, filas)


def en_fechas(campos):
    return DESDE.isoformat() <= (campos.get("fecha_publicacion") or "")[:10] <= HASTA.isoformat()


def numeros_andina():
    return range(ANDINA_DESDE, ANDINA_HASTA, ANDINA_CADA)


class _Lector:
    """Lee las notas de un medio a su ritmo y anexa las filas; salta lo ya hecho."""

    def __init__(self, medio, parar, hechos):
        self.medio, self.parar, self.hechos = medio, parar, hechos
        self.leidas = self.fuera = self.sin_nota = self.errores = 0
        self.alto = threading.Event()  # un bloqueo detiene solo a este medio
        self._contar = threading.Lock()

        self.hilos, self._seguidos = config.HILOS_POR_HOST, 0  # en curso a la vez; baja si el servidor falla

    def contar(self, campo):
        with self._contar:
            setattr(self, campo, getattr(self, campo) + 1)
            if campo == "errores":  # 5xx agotados los reintentos o errores de red: menos peticiones a la vez
                self._seguidos = 0
                if self.hilos > 1:
                    self.hilos = max(1, self.hilos // 2)
                    log.warning(f"{self.medio.nombre}: errores del servidor, baja a {self.hilos} a la vez")
            else:
                self._seguidos += 1
                if self.hilos < config.HILOS_POR_HOST and self._seguidos >= SUBIR_TRAS:
                    self.hilos, self._seguidos = self.hilos + 1, 0
                    log.info(f"{self.medio.nombre}: responde bien, sube a {self.hilos} a la vez")

    def sigue(self):
        return not (self.parar.is_set() or self.alto.is_set())

    def guardar(self, fila, campos):
        clave = (self.medio.nombre, fila["id"])
        if not en_fechas(campos):
            fecha = campos.get("fecha_publicacion", "")[:10]
            _anexar(INTENTOS, COLUMNAS_INTENTOS, [{"medio": clave[0], "id": clave[1], "estado": "fuera_de_fechas",
                                                   "detalle": fecha}])  # fmt: skip
            self.contar("fuera")
        else:
            nota, _ = filas_de_nota(self.medio.nombre, fila, campos, MUESTRA)
            _anexar(ARCHIVO, esquemas.NOTAS, [nota])
            self.contar("leidas")
        self.hechos.add(clave)

    def sin(self, fila, e):
        _anexar(INTENTOS, COLUMNAS_INTENTOS, [{"medio": self.medio.nombre, "id": fila["id"], "estado": "sin_nota",
                                               "detalle": str(e)[:120]}])  # fmt: skip
        self.hechos.add((self.medio.nombre, fila["id"]))
        self.contar("sin_nota")

    def leer(self, fila):
        try:
            self.guardar(fila, self.medio.leer(fila))
        except DETENER:
            raise
        except requests.HTTPError as e:
            codigo = getattr(e.response, "status_code", None)
            if codigo in (404, 410):
                self.sin(fila, f"HTTP {codigo}")
            else:
                self.contar("errores")
        except (NoExiste, NotaInvalida) as e:
            self.sin(fila, e)
        except (*ERRORES_RED, ValueError) as e:
            log.debug("%s %s: %s", self.medio.nombre, fila["id"], describir(e))
            self.contar("errores")


def _en_paralelo(lector, funcion, elementos):
    """funcion(x) para cada elemento, con lector.hilos en curso; el ritmo por host lo lleva el cliente."""
    error = None
    with concurrent.futures.ThreadPoolExecutor(max_workers=config.HILOS_POR_HOST) as hilos:
        pendientes = set()

        def revisar(listos):
            nonlocal error
            for f in listos:
                try:
                    f.result()
                except DETENER as e:
                    lector.alto.set()
                    error = error or e

        for x in elementos:
            if not lector.sigue():
                break
            pendientes.add(hilos.submit(funcion, x))
            while len(pendientes) >= lector.hilos:
                listos, pendientes = concurrent.futures.wait(pendientes, return_when=concurrent.futures.FIRST_COMPLETED)
                revisar(listos)
        revisar(concurrent.futures.wait(pendientes).done)
    if error is not None:
        raise error


def _un_numero(lector, numero):
    medio, ident = lector.medio, str(numero)
    if not lector.sigue():
        return
    url = f"https://{medio.host}/agencia/noticia.aspx?id={numero}"
    try:
        r = medio.cliente.get(url, allow_redirects=False)
        codigo, destino = r.status_code, r.headers.get("Location", "")
    except DETENER:
        raise
    except requests.HTTPError as e:
        codigo, destino = getattr(e.response, "status_code", ""), ""
    except ERRORES_RED as e:
        log.debug("andina %s: %s", numero, describir(e))
        lector.contar("errores")
        return
    m = medio.NOTA.match(destino)
    fila = medio.fila(ident, destino, "externa-numero", http=codigo)
    if codigo == 301 and m and m.group(1) == ident:
        lector.leer(fila)
    else:
        lector.sin(fila, f"sin redirección ({codigo})")


def _andina(lector, numeros):
    faltan = (n for n in numeros if ("andina", str(n)) not in lector.hechos)
    _en_paralelo(lector, lambda n: _un_numero(lector, n), faltan)


def _rpp(lector, dias, limite=None):
    medio, vistos = lector.medio, 0
    for dia in dias:
        if not lector.sigue():
            return
        if limite is not None and vistos >= limite:
            return
        try:
            filas = medio.archivo(dia)
        except DETENER:
            raise
        except (*ERRORES_RED, ValueError) as e:
            log.warning("rpp archivo %s: %s", dia, describir(e))
            lector.contar("errores")
            continue
        faltan = [f for f in filas if ("rpp", f["id"]) not in lector.hechos]
        if limite is not None:
            faltan = faltan[: limite - vistos]
        vistos += len(faltan)
        _en_paralelo(lector, lambda f: lector.leer(f) if lector.sigue() else None, faltan)
        log.info(f"rpp {dia}: {len(faltan)} por leer")


class _SinLista:
    """Andina y RPP sin su lista del histórico: la prueba externa no la toca."""

    def __init__(self, cliente, parar):
        self.cliente, self.parar = cliente, parar
        self.host = config.HOSTS_MEDIOS[self.nombre]
        self.lista, self.hechas = {}, set()


class AndinaExterna(_SinLista, Andina):
    pass


class RppExterna(_SinLista, Rpp):
    pass


def hechos():
    return {(f["medio"], f["id"]) for f in leer_csv(ARCHIVO)} | {(f["medio"], f["id"]) for f in leer_csv(INTENTOS)}


def _correr(tareas):
    """Un hilo por medio (cada uno con su cliente y su ritmo); un bloqueo detiene solo a ese medio."""
    with sin_suspension(), concurrent.futures.ThreadPoolExecutor(max_workers=len(tareas)) as hilos:
        futuros = {hilos.submit(f): nombre for nombre, f in tareas.items()}
        for futuro in concurrent.futures.as_completed(futuros):
            try:
                futuro.result()
            except DETENER as e:
                log.warning(f"{futuros[futuro]}: detenido ({describir(e)})")


def _lectores(parar):
    h = hechos()
    a = _Lector(AndinaExterna(Cliente(hosts_permitidos={config.HOSTS_MEDIOS["andina"]}), parar), parar, h)
    r = _Lector(RppExterna(Cliente(hosts_permitidos={config.HOSTS_MEDIOS["rpp"]}), parar), parar, h)
    return a, r


def resumen(lectores):
    for x in lectores:
        log.info(f"{x.medio.nombre}: {x.leidas} leídas, {x.fuera} fuera de fechas, {x.sin_nota} sin nota, "
                 f"{x.errores} con error")  # fmt: skip


@exclusivo("radar.noticias.externa")
def prueba():
    """20 notas por medio, al azar en el rango: ¿responden las vías y traen etiquetas?"""
    parar = threading.Event()
    a, r = _lectores(parar)
    azar = random.Random(SEMILLA_PRUEBA)
    numeros = sorted(azar.sample(list(numeros_andina()), PRUEBA_POR_MEDIO * 2))
    dias = sorted(azar.sample(list(_dias(DESDE, HASTA)), 2))
    _correr({"andina": lambda: _andina(a, numeros), "rpp": lambda: _rpp(r, dias, PRUEBA_POR_MEDIO)})
    resumen((a, r))
    filas = [f for f in leer_csv(ARCHIVO)]
    for medio in ("andina", "rpp"):
        del_medio = [f for f in filas if f["medio"] == medio]
        con = sum(bool(f["etiquetas"]) for f in del_medio)
        log.info(f"{medio}: {len(del_medio)} notas en el archivo, {con} con etiquetas")


@exclusivo("radar.noticias.externa")
def leer():
    parar = threading.Event()
    a, r = _lectores(parar)
    _correr({"andina": lambda: _andina(a, numeros_andina()), "rpp": lambda: _rpp(r, list(_dias(DESDE, HASTA)))})
    resumen((a, r))


def main(argv=None):
    ap = argparse.ArgumentParser(description="Prueba externa de notas de 2025 (sección 13).")
    ap.add_argument("accion", choices=("prueba", "leer"))
    a = ap.parse_args(argv)
    configurar("noticias-externa")
    {"prueba": prueba, "leer": leer}[a.accion]()


if __name__ == "__main__":
    main()
