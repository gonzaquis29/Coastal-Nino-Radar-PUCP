"""Arranque sin torch (docs/app/definicion.md, sección 14): criterios H1 a H5 y H7, una sola vez.

python -m radar.app.validar_arranque [--repetir]  ->  data/processed/app/validacion.csv

Compara el motor ONNX con el de torch en el mismo proceso (mismos vectores, mismo Verificar y mismo Preguntar) y mide
tres arranques en frío en procesos nuevos, como en la sección 14.1. H6 son las pruebas de la app de siempre
(radar.app.validar, npm run medir y radar.app.validar_interfaz).
"""

import argparse
import contextlib
import json
import logging
import random
import statistics
import subprocess
import sys

import numpy as np
from fastapi.encoders import jsonable_encoder

from radar import config
from radar.agente import agente, herramientas
from radar.app import servicio as sv
from radar.app import validar as va
from radar.comun.archivos import leer_csv
from radar.comun.avance import Avance
from radar.comun.registro import configurar
from radar.nlp import candidatos, embeddings, motor, semaforo
from radar.noticias.validar_texto import marcar_vistas, notas_vistas, reservada_capa3
from radar.noticias.viabilidad import criterio, guardar

log = logging.getLogger(__name__)
PRUEBA = "App: arranque sin torch"
MUESTRA = "arranque-20261123"
SEMILLA = "arranque-notas-20261123"
POR_MEDIO = 75  # 300 notas entre los 4 medios (H2)
DESDE, HASTA = "2026-01-01", config.FIN_CORTE.isoformat()  # con párrafos oficiales vigentes
ARRANQUES = 3

# Umbrales fijados en la sección 14.4 antes de construir
COSENO_MINIMO = embeddings.COSENO_INSTRUMENTO  # H1, el de E2
ARRANQUE_MAXIMO, ARRANQUE_HOY = 8.0, 17.7  # H4
PRIMERA_HOY = 4.1  # H5
MODULOS_TORCH = ("torch", "transformers", "sentence_transformers")

# Sintéticos nuevos, escritos el 23-nov antes de medir. Inventados: varían espacios, tildes, signos y largo.
TEXTOS = (
    "El Niño costero sigue en vigilancia",
    "el niño costero  sigue   en vigilancia",
    "EL NIÑO COSTERO SIGUE EN VIGILANCIA",
    "Lluvias de moderada intensidad en la sierra de Piura este fin de semana",
    "¿Llegará un Niño fuerte en el verano de 2027?",
    "Temperatura del mar 2,5 °C sobre lo normal frente a Paita",
    "Pescadores de Sechura reportan menos pota por el agua cálida",
    "Oleaje anómalo: cierran 40 puertos del litoral",
    "Huaico en la quebrada de Chosica deja viviendas afectadas",
    "Friaje en la selva sur: temperaturas de hasta 8 °C",
    "Alerta roja por lluvias intensas en Tumbes 🌧️",
    "El mar se calienta 🌊 y los pescadores esperan",
    "Comunicado oficial N.° 21: se mantiene la alerta",
    "ENFEN: magnitud débil hasta marzo; moderada no se descarta",
    "Senamhi prevé calor intenso en Lima y Callao",
    "Indeci recomienda limpiar techos y canales",
    "Agricultores de Lambayeque temen perder la cosecha de arroz",
    "Anchoveta: la primera temporada empieza con cuota reducida",
    "Desborde del río Tumbes afecta cultivos de plátano",
    "Sequía en el sur andino preocupa a los ganaderos",
    "Hola, ¿qué tal?",
    "Resultado del partido de anoche",
    "Precio del pollo sube en los mercados",
    "Tráfico intenso en la Vía Expresa",
    "Nuevo ministro jura en Palacio",
    "x",
    "123 456 789",
    "   espacios al inicio y al final   ",
    "línea uno\nlínea dos\n\nlínea cuatro",
    "tabulación\tentre\tpalabras",
    "¡¿Será verdad que viene el fenómeno?!",
    "La NOAA y el ENFEN coinciden en un Niño débil",
    "Golpe de calor en Trujillo: recomiendan beber agua",
    "Varazón de peces en la bahía de Chimbote",
    "Lluvias de verano en Arequipa activan quebradas",
    "Clima en Lima hoy: nublado parcial y 19 °C",
    "Alerta por radiación UV extrema en la costa",
    "Plan multisectorial ante El Niño costero 2026-2027",
    ("El comité multisectorial informó que el Niño costero continúa con condiciones cálidas en el mar. " * 25),
    ("Pescadores, agricultores y autoridades regionales evalúan medidas ante las lluvias del verano. " * 40),
)  # fmt: skip
CONSULTAS = (
    "¿El Niño costero ya empezó?",
    "¿Qué tan fuerte será el Niño este verano?",
    "¿Qué dice el ENFEN hoy?",
    "¿Hay alerta en la costa norte?",
    "¿Va a llover en Piura la próxima semana?",
    "¿Qué debo hacer si vivo cerca de una quebrada?",
    "¿Cómo afecta El Niño a la pesca de anchoveta?",
    "¿Cuándo sale el próximo comunicado?",
    "¿Qué significa estado de vigilancia?",
    "¿Está más caliente el mar frente a Paita?",
    "Este texto dice que viene un Niño extraordinario, ¿es cierto?",
    "¿Qué recomiendan a los agricultores de Lambayeque?",
    "¿La magnitud prevista es débil o moderada?",
    "¿Hay avisos del Senamhi vigentes en Lima?",
    "¿Qué pasó con El Niño en 2017?",
    "¿Cuál es la temperatura del mar hoy?",
    "¿Quién ganó las elecciones?",
    "¿Cómo está el tráfico?",
    "niño costero",
    "¿Debo preocuparme por las lluvias en Tumbes?",
)


def ruta():
    return config.DIR_APP / "arranque.json"


# ---------------------------------------------------------------- dos motores en el mismo proceso


class Entorno:
    """El semáforo, el buscador y el enrutador del agente con un motor ("onnx32" o "torch")."""

    def __init__(self, nombre):
        self.nombre = nombre
        previo, config.MOTOR_APP = config.MOTOR_APP, nombre
        try:
            repo, prefijo, largo = motor.modelos_app()[0]
            self.st = motor.para_app(repo, prefijo, largo) or candidatos.cargar(semaforo.MODELO)
            self.semaforo = semaforo.Semaforo(st=self.st)
            with self.activo(enrutador=False):
                self.oficial = herramientas.Oficial()
                self.enrutador = agente.Enrutador()
        finally:
            config.MOTOR_APP = previo
        self.e5 = self.enrutador.e5
        self.servicio = sv.Servicio(self.semaforo)

    @contextlib.contextmanager
    def activo(self, enrutador=True):
        guardados = semaforo._semaforo, herramientas.oficial, agente.enrutador
        semaforo._semaforo = lambda: self.semaforo
        if hasattr(self, "oficial"):
            herramientas.oficial = lambda: self.oficial
        if enrutador:
            agente.enrutador = lambda: self.enrutador
        try:
            yield
        finally:
            semaforo._semaforo, herramientas.oficial, agente.enrutador = guardados


def coseno_minimo(a, b):
    return float((np.asarray(a) * np.asarray(b)).sum(1).min())


def h1(onnx, torch_):
    parrafos = [p["texto"] for p in onnx.servicio.corpus.parrafos if p["texto"].strip()]
    preguntas = [agente.normal(c["pregunta"]) for c in agente.casos_congelados(leer_csv(agente.ARCHIVO_DESARROLLO))]
    minimos = {
        "MiniLM párrafos": coseno_minimo(onnx.st.encode(parrafos),
                                         torch_.st.encode(parrafos, normalize_embeddings=True)),
        "MiniLM sintéticos": coseno_minimo(onnx.st.encode(list(TEXTOS)),
                                           torch_.st.encode(list(TEXTOS), normalize_embeddings=True)),
        "e5 párrafos": coseno_minimo(onnx.e5.embeber(parrafos), torch_.e5.embeber(parrafos)),
        "e5 preguntas de desarrollo": coseno_minimo(onnx.e5.embeber(preguntas), torch_.e5.embeber(preguntas)),
        "e5 sintéticos": coseno_minimo(onnx.e5.embeber(list(TEXTOS)), torch_.e5.embeber(list(TEXTOS))),
    }  # fmt: skip
    peor = min(minimos.values())
    detalle = f"{len(parrafos)} párrafos, {len(preguntas)} preguntas, {len(TEXTOS)} sintéticos; " + "; ".join(
        f"{k} {v:.7f}" for k, v in minimos.items()
    )
    return criterio(PRUEBA, "H1. Mismos vectores (coseno mínimo ONNX frente a torch)", f"{peor:.7f}",
                    f"≥ {COSENO_MINIMO}", peor >= COSENO_MINIMO, detalle)  # fmt: skip


def muestra_notas():
    vistas = notas_vistas()
    por_medio = {}
    for n in leer_csv(config.DIR_NOTICIAS / "notas.csv"):
        if (n["medio"], n["id"]) in vistas or reservada_capa3(n) or not n["titular"].strip():
            continue
        if DESDE <= n["fecha_publicacion"][:10] <= HASTA:
            por_medio.setdefault(n["medio"], []).append(n)
    azar = random.Random(SEMILLA)
    salida = []
    for medio in sorted(por_medio):
        notas = sorted(por_medio[medio], key=lambda n: n["id"])
        salida += azar.sample(notas, min(POR_MEDIO, len(notas)))
    return salida


def sin_coseno(r):
    r = jsonable_encoder(r)
    if r.get("medidor"):
        r["medidor"] = {k: v for k, v in r["medidor"].items() if k != "valor"}
    return r


def h2(onnx, torch_, notas):
    pedidos = [(" ".join(x for x in (n["titular"], n["resumen"]) if x), n["fecha_publicacion"][:10],
                va.MACROREGIONES[i % 3]) for i, n in enumerate(notas)]  # fmt: skip
    pedidos += [(t, va.FECHA, va.MACROREGIONES[i % 3]) for i, t in enumerate(va.TEXTOS)]
    iguales = completos = 0
    distintos, dif_coseno = [], 0.0
    avance = Avance("H2 Verificar", len(pedidos), cada=50)
    for texto, fecha, region in pedidos:
        with onnx.activo():
            a = onnx.servicio.verificar(texto, fecha, region)
        with torch_.activo():
            b = torch_.servicio.verificar(texto, fecha, region)
        clave = lambda r: (r["tipo"], r["nivel"], (r["oficial_cercano"] or {}).get("id"))  # noqa: E731
        iguales += clave(a) == clave(b)
        completos += sin_coseno(a) == sin_coseno(b)
        if clave(a) != clave(b):
            distintos.append(texto[:40])
        if a.get("medidor") and b.get("medidor"):
            dif_coseno = max(dif_coseno, abs(a["medidor"]["valor"] - b["medidor"]["valor"]))
        avance.paso()
    n = len(pedidos)
    detalle = (f"{len(notas)} notas nuevas y {len(va.TEXTOS)} textos de P1; salida completa igual en {completos} de "
               f"{n}; diferencia máxima del coseno mostrado {dif_coseno:.4f}; distintos: {distintos[:5]}")  # fmt: skip
    return criterio(PRUEBA, "H2. Verificar igual (tipo, nivel y párrafo más cercano)", f"{iguales}/{n}", "100 %",
                    iguales == n, detalle)  # fmt: skip


def h3(onnx, torch_):
    consultas = [c["texto"] for c in leer_csv(agente.ARCHIVO_PRUEBA_C)] + list(CONSULTAS) + list(va.CONSULTAS)
    iguales, distintos = 0, []
    avance = Avance("H3 Preguntar", len(consultas), cada=50)
    for i, c in enumerate(consultas):
        region = va.MACROREGIONES[i % 3]
        with onnx.activo():
            a = jsonable_encoder(onnx.servicio.preguntar(c, va.FECHA, region))
        with torch_.activo():
            b = jsonable_encoder(torch_.servicio.preguntar(c, va.FECHA, region))
        if a == b:
            iguales += 1
        else:
            distintos.append(c[:40])
        avance.paso()
    n = len(consultas)
    detalle = (f"{n - len(CONSULTAS) - len(va.CONSULTAS)} de la ronda c, {len(CONSULTAS)} sintéticas nuevas y "
               f"{len(va.CONSULTAS)} de P1; distintas: {distintos[:5]}")  # fmt: skip
    return criterio(PRUEBA, "H3. Preguntar igual (herramienta y texto de la respuesta)", f"{iguales}/{n}", "100 %",
                    iguales == n, detalle)  # fmt: skip


def h7_respaldo():
    """Sin el tokenizador del motor, para_app devuelve None y la app arma el semáforo con torch."""
    original = motor._ruta_tokenizador
    motor._ruta_tokenizador = lambda repo: config.DIR_MOTOR_APP / "no-existe.json"
    try:
        return motor.para_app(*motor.modelos_app()[0]) is None
    finally:
        motor._ruta_tokenizador = original


# ---------------------------------------------------------------- arranques en frío, en procesos nuevos

ARRANQUE = r"""
import json, logging, sys, time
peticiones = []
class Contar(logging.Handler):
    def emit(self, r):
        if "huggingface" in r.getMessage():
            peticiones.append(1)
for n in ("httpx", "urllib3", "huggingface_hub"):
    l = logging.getLogger(n); l.setLevel(logging.DEBUG); l.addHandler(Contar())
t0 = time.perf_counter()
import radar.app.api
from radar.app import servicio
s = servicio.servicio(); servicio.panorama(); s.verificar("El Niño costero", "2026-11-20", "lima")
t1 = time.perf_counter()
cargados = [m for m in ("torch", "transformers", "sentence_transformers") if m in sys.modules]
s.preguntar("¿Qué dice el último comunicado del ENFEN?", "2026-11-20", "lima")
t2 = time.perf_counter()
al_final = [m for m in ("torch", "transformers", "sentence_transformers") if m in sys.modules]
print(json.dumps({"arranque": t1 - t0, "primera": t2 - t1, "cargados": cargados, "peticiones": len(peticiones),
                  "cargados_al_final": al_final}))
"""


def arranques():
    salida = []
    for i in range(ARRANQUES):
        r = subprocess.run([sys.executable, "-c", ARRANQUE], capture_output=True, text=True, encoding="utf-8",
                           check=True)  # fmt: skip
        salida.append(json.loads(r.stdout.strip().splitlines()[-1]))
        log.info(f"arranque {i + 1}: {salida[-1]}")
    return salida


def h4_h5_h7(medidos, respaldo):
    arranque = statistics.median(m["arranque"] for m in medidos)
    primera = statistics.median(m["primera"] for m in medidos)
    cargados = sorted({x for m in medidos for x in m["cargados"] + m["cargados_al_final"]})
    peticiones = sum(m["peticiones"] for m in medidos)
    tiempos = ", ".join(f"{m['arranque']:.1f}" for m in medidos)
    return [
        criterio(PRUEBA, "H4. Arranque: mediana de 3 en frío; módulos de torch cargados",
                 f"{arranque:.1f} s; {len(cargados)}",
                 f"≤ {ARRANQUE_MAXIMO:.0f} s (hoy {ARRANQUE_HOY}) y 0", arranque <= ARRANQUE_MAXIMO and not cargados,
                 f"arranques {tiempos} s; cargados {cargados or 'ninguno'}"),
        criterio(PRUEBA, "H5. Primera pregunta después del arranque: mediana de 3", f"{primera:.2f} s",
                 f"≤ {PRIMERA_HOY} s (hoy)", primera <= PRIMERA_HOY,
                 ", ".join(f"{m['primera']:.2f}" for m in medidos) + " s"),
        criterio(PRUEBA, "H7. Sin internet / sin el archivo del motor vuelve a torch", f"{peticiones} peticiones / "
                 f"{'sí' if respaldo else 'no'}", "0 / sí", peticiones == 0 and respaldo,
                 "peticiones a Hugging Face en los 3 arranques y sus primeras preguntas"),
    ]  # fmt: skip


def registrada():
    return MUESTRA in {f["muestra"] for f in leer_csv(config.ARCHIVO_NOTAS_VISTAS)}


def validar(repetir=False):
    if registrada() and not repetir:
        raise SystemExit(f"La prueba ya se miró ({MUESTRA} en notas_vistas.csv). Usa --repetir y decláralo.")
    medidos = arranques()  # primero, para que los procesos nuevos no compitan con este por la CPU
    notas = muestra_notas()
    log.info(f"Muestra: {len(notas)} notas nuevas")
    onnx, torch_ = Entorno("onnx32"), Entorno("torch")
    if not isinstance(onnx.st, motor.Onnx32) or not isinstance(onnx.e5.motor, motor.Onnx32):
        raise SystemExit("El motor ONNX no cargó: python -m radar.nlp.motor preparar")
    filas = [h1(onnx, torch_), h2(onnx, torch_, notas), h3(onnx, torch_), *h4_h5_h7(medidos, h7_respaldo())]
    if repetir:
        for f in filas:
            f["criterio"] = "(repetida) " + f["criterio"]
    guardar(filas, config.DIR_APP / "validacion.csv")
    if not registrada():
        marcar_vistas(notas, MUESTRA)
    for f in filas:
        print(f"[{'ok' if f['pasa'] else 'NO'}] {f['criterio']}: {f['valor']} (umbral {f['umbral']}) {f['detalle']}")


def main(argv=None):
    ap = argparse.ArgumentParser(description="Arranque sin torch (sección 14): H1 a H5 y H7.")
    ap.add_argument("--repetir", action="store_true", help="volver a medir una prueba ya mirada (se declara)")
    a = ap.parse_args(argv)
    configurar("app-arranque")
    validar(a.repetir)


if __name__ == "__main__":
    main()
