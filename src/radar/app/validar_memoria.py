"""Memoria de la API (docs/app/definicion.md, sección 16): criterios K1 a K7, una sola vez.

python -m radar.app.validar_memoria capturar antes     con el código anterior al cambio
python -m radar.app.validar_memoria capturar despues   con el cambio (K1 a K6)
python -m radar.app.validar_memoria comparar [--repetir]  ->  data/processed/app/validacion.csv
python -m radar.app.validar_memoria pareada --anterior CARPETA    K6b (16.6): CARPETA tiene el código anterior

Cada captura guarda las huellas de las respuestas (no su texto), los vectores y lo medido en 3 arranques de la API real,
en un puerto aparte. No envía eventos: no escribe en el registro de uso. P1 a P5 se miden con radar.app.validar.
"""

import argparse
import contextlib
import json
import logging
import os
import socket
import statistics
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import numpy as np
import psutil
from fastapi.encoders import jsonable_encoder

from radar import config
from radar.agente import agente
from radar.app import esquemas, metodologia
from radar.app import servicio as sv
from radar.app import validar as va
from radar.app import validar_arranque as arr
from radar.comun.archivos import guardar_json, leer_csv, leer_json, sha256
from radar.comun.avance import Avance
from radar.comun.candado import exclusivo
from radar.comun.registro import configurar
from radar.nlp import motor, semaforo
from radar.noticias.validar_texto import marcar_vistas
from radar.noticias.viabilidad import criterio, guardar

log = logging.getLogger(__name__)
PRUEBA = "App: memoria"
MUESTRA = "memoria-20261124"
SEMILLA = "memoria-notas-20261124"
ARRANQUES, CONSULTAS_POR_TIPO = 3, 30
PARES = 12  # K6b

# Umbrales fijados en la sección 16.4 antes de construir
DIFERENCIA_MAXIMA = 1e-6  # K1
MEMORIA_MAXIMA, PICO_MAXIMO = 1000, 1100  # K5, en MB
ARRANQUE_MAXIMO, PRIMERA_MAXIMA, LENTITUD_MAXIMA = 6.5, 2.5, 1.10  # K6

# Sintéticos nuevos, escritos el 24-nov antes de medir. Inventados: 20 base, 12 con rarezas y 8 largos.
_BASE = (
    "El mar de Paita amaneció dos grados más caliente",
    "Cosechas de mango en riesgo por el calor en Piura",
    "Niño costero: el próximo informe sale la otra semana",
    "Se prevé un Niño moderado, según un vocero",
    "Autoridades refuerzan las defensas del río Chira",
    "Colegios de Tumbes ajustan horarios por el calor",
    "Pota y perico: cambian las zonas de pesca",
    "Neblina y llovizna en Lima por la mañana",
    "Vientos fuertes levantan polvo en Ica",
    "Nevada en las alturas de Cusco",
    "El dengue aumenta con las lluvias en Loreto",
    "Aviso naranja por lluvias en la selva norte",
    "La alerta se mantiene hasta el otoño",
    "El fenómeno se debilita, dicen los científicos",
    "Simulacro de evacuación en Chiclayo",
    "Concierto gratuito en la plaza",
    "Suben los pasajes interprovinciales",
    "Final del torneo de vóley",
    "Receta de ceviche para el domingo",
    "Nueva aplicación para pedir citas médicas",
)
_RAROS = (
    "El <mask> costero",
    "hola  <mask>\t<mask> mundo",
    "<s>inicio</s> <pad> fin <unk>",
    "espacio duro y ancho​cero",
    "ＥＬ niño en ancho completo",
    "ñ y á con tildes sueltas",
    "漢字 en una línea",
    "🌊🌊🌊",
    "...!!!???",
    "\n\n\t ",
    "a" * 700,
    "0,5 °C; 1.5 °C; -2 °C; 10%",
)
TEXTOS = (*_BASE, *_RAROS, *((t + ". ") * 40 for t in _BASE[:8]))
CONSULTAS = (
    "¿Sigue la alerta del Niño costero?",
    "¿Se viene un Niño extraordinario?",
    "¿Cuándo termina el Niño costero?",
    "¿Qué recomiendan para los pescadores?",
    "¿Qué hago con mis cultivos si llueve mucho?",
    "¿Hay peligro de huaicos en Lima?",
    "¿Lloverá en Tumbes en enero?",
    "¿Qué dice Senamhi sobre la costa norte?",
    "¿Cuál es la magnitud esperada?",
    "Leí que el mar subió cuatro grados, ¿es verdad?",
    "Me dijeron que el Niño ya acabó",
    "¿Qué es el ENFEN?",
    "¿Qué es una alerta de Niño costero?",
    "¿Afecta al turismo en Máncora?",
    "¿Cuánto cuesta el dólar?",
    "¿Dónde juega la selección?",
    "lluvias",
    "recomendaciones para limpiar techos",
    "¿Por qué hace tanto calor en Piura?",
    "¿Qué decía el comunicado anterior?",
)
RESPALDO = len(va.TEXTOS)  # K7: los 20 textos de P1


def ruta(momento, extension):
    return config.DIR_APP / f"memoria-{momento}.{extension}"


def ordenado(objeto):
    """Los conjuntos, en un orden fijo: su orden cambia de un proceso a otro."""
    if isinstance(objeto, dict):
        return {k: ordenado(v) for k, v in objeto.items()}
    if isinstance(objeto, set | frozenset):
        return sorted(objeto)
    return [ordenado(x) for x in objeto] if isinstance(objeto, list | tuple) else objeto


def huella(objeto):
    datos = jsonable_encoder(ordenado(objeto))
    return sha256(json.dumps(datos, ensure_ascii=False, sort_keys=True).encode("utf-8"))


# ---------------------------------------------------------------- respuestas (K1 a K4)


def muestra():
    return arr.muestra_notas(SEMILLA)


def pedidos(notas):
    p = [(" ".join(x for x in (n["titular"], n["resumen"]) if x), n["fecha_publicacion"][:10],
          va.MACROREGIONES[i % 3]) for i, n in enumerate(notas)]  # fmt: skip
    return p + [(t, va.FECHA, va.MACROREGIONES[i % 3]) for i, t in enumerate(va.TEXTOS)]


def vectores(servicio):
    """Tokens (huella) y vectores de los dos modelos."""
    parrafos = [p["texto"] for p in servicio.corpus.parrafos if p["texto"].strip()]
    preguntas = [agente.normal(c["pregunta"]) for c in agente.casos_congelados(leer_csv(agente.ARCHIVO_DESARROLLO))]
    textos = parrafos + preguntas + list(TEXTOS)
    tokens, salida = {}, {}
    for repo, prefijo, largo in motor.modelos_app():
        m = motor.para_app(repo, prefijo, largo)
        tokens[repo] = [huella([m.tok(t)["input_ids"], m.tok.lote([prefijo + t], largo)[0].tolist()]) for t in textos]
        salida[repo.replace("/", "--")] = np.vstack([m.embeber(textos[i : i + 16]) for i in range(0, len(textos), 16)])
    return tokens, salida


def panoramas():
    """K4: todas las secciones (con y sin filtros), el estado y la metodología."""
    p, s = sv.panorama(), sv.servicio()
    filtros = [{}, {"desde": "2026-06-01"}, {"hasta": "2026-08-31"}, {"desde": "2026-03-01", "hasta": "2026-10-31"}]
    filtros += [{"macroregion": m} for m in va.MACROREGIONES]
    salida = {}
    for seccion in esquemas.Seccion.__args__:
        for f in filtros if seccion in esquemas.SECCIONES_CON_FILTRO else [{}]:
            salida[f"{seccion} {f}"] = huella(getattr(p, seccion)(**f))
    for region in va.MACROREGIONES:
        salida[f"estado {region}"] = huella(s.estado(va.FECHA, region))
    pagina = metodologia.metodologia()
    salida["metodologia"] = huella({k: v for k, v in pagina.items() if k != "uso"})  # el uso real cambia solo
    return salida


# ---------------------------------------------------------------- la API real (K5 y K6)


def _pedir(puerto, camino, cuerpo=None):
    datos = json.dumps(cuerpo).encode("utf-8") if cuerpo is not None else None
    pedido = urllib.request.Request(f"http://127.0.0.1:{puerto}{camino}", datos, {"Content-Type": "application/json"})
    with urllib.request.urlopen(pedido, timeout=60) as r:
        return json.loads(r.read())


def _memoria(proceso):
    """(residente, pico) en MB del proceso de la API; en un entorno virtual de Windows es hijo del lanzador."""
    infos = [p.memory_info() for p in (proceso, *proceso.children(recursive=True))]
    mayor = max(infos, key=lambda i: i.rss)
    return mayor.rss / 1e6, getattr(mayor, "peak_wset", mayor.rss) / 1e6


def medir_api(codigo=None):
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        puerto = s.getsockname()[1]
    orden = [sys.executable, "-m", "uvicorn", "radar.app.api:app", "--port", str(puerto), "--log-level", "warning"]
    entorno = {**os.environ, "HF_HUB_OFFLINE": "1"} | ({"PYTHONPATH": str(codigo)} if codigo else {})
    api = subprocess.Popen(orden, env=entorno, cwd=codigo)
    proceso = psutil.Process(api.pid)
    try:
        limite = time.time() + 120
        while time.time() < limite:
            with contextlib.suppress(OSError):
                if _pedir(puerto, "/api/salud")["listo"]:
                    break
            time.sleep(0.2)
        tiempos = []
        for i in range(CONSULTAS_POR_TIPO):
            inicio = time.perf_counter()
            _pedir(puerto, "/api/verificar", {"texto": va.TEXTOS[i % len(va.TEXTOS)], "fecha": va.FECHA})
            tiempos.append(time.perf_counter() - inicio)
            _pedir(puerto, "/api/preguntar", {"consulta": CONSULTAS[i % len(CONSULTAS)], "fecha": va.FECHA})
        residente, pico = _memoria(proceso)
        return {"residente": residente, "pico": pico, "verificar": statistics.median(tiempos)}
    finally:
        for p in (*proceso.children(recursive=True), proceso):
            with contextlib.suppress(psutil.NoSuchProcess):
                p.kill()
        api.wait()


def capturar(momento):
    medidos = arr.arranques()  # primero, para que no compitan con este proceso
    apis = [medir_api() for _ in range(ARRANQUES)]
    log.info(f"API: {apis}")
    s = sv.servicio()
    tokens, matrices = vectores(s)
    lista = pedidos(muestra())
    avance = Avance("Verificar", len(lista), cada=50)
    verificar = []
    for texto, fecha, region in lista:
        verificar.append(huella(s.verificar(texto, fecha, region)))
        avance.paso()
    consultas = [c["texto"] for c in leer_csv(agente.ARCHIVO_PRUEBA_C)] + list(CONSULTAS) + list(va.CONSULTAS)
    preguntar = [huella(s.preguntar(c, va.FECHA, va.MACROREGIONES[i % 3])) for i, c in enumerate(consultas)]
    datos = {"arranques": medidos, "apis": apis, "tokens": tokens, "verificar": verificar, "preguntar": preguntar,
             "panorama": panoramas(), "pedidos": huella(lista)}  # fmt: skip
    np.savez(ruta(momento, "npz"), **matrices)
    guardar_json(ruta(momento, "json"), datos)


# ---------------------------------------------------------------- comparación


def iguales(a, b):
    return sum(x == y for x, y in zip(a, b, strict=True)), len(a)


def medianas(datos):
    return {
        "arranque": statistics.median(m["arranque"] for m in datos["arranques"]),
        "primera": statistics.median(m["primera"] for m in datos["arranques"]),
        **{k: statistics.median(m[k] for m in datos["apis"]) for k in ("residente", "pico", "verificar")},
    }


def k1(antes, despues, matrices):
    tokens = [iguales(antes["tokens"][r], despues["tokens"][r]) for r in antes["tokens"]]
    diferencia = max(float(np.abs(a - b).max()) for a, b in matrices)
    igual, total = sum(t[0] for t in tokens), sum(t[1] for t in tokens)
    return criterio(PRUEBA, "K1. Mismos tokens y vectores en los dos modelos", f"{igual}/{total}; {diferencia:.1e}",
                    f"100 %; ≤ {DIFERENCIA_MAXIMA:.0e}", igual == total and diferencia <= DIFERENCIA_MAXIMA,
                    "párrafos oficiales, preguntas de desarrollo y 40 sintéticos nuevos")  # fmt: skip


def k_iguales(nombre, a, b, detalle):
    n, total = iguales(a, b)
    return criterio(PRUEBA, nombre, f"{n}/{total}", "100 %", n == total, detalle)


def k5_k6(antes, despues):
    a, d = medianas(antes), medianas(despues)
    lentitud = d["verificar"] / a["verificar"]
    pico = max(m["pico"] for m in despues["apis"])
    return [
        criterio(PRUEBA, "K5. Memoria de la API tras 60 consultas (mediana de 3) y pico",
                 f"{d['residente']:.0f} MB; {pico:.0f} MB", f"≤ {MEMORIA_MAXIMA} MB; ≤ {PICO_MAXIMO} MB",
                 d["residente"] <= MEMORIA_MAXIMA and pico <= PICO_MAXIMO,
                 f"antes {a['residente']:.0f} MB, pico {max(m['pico'] for m in antes['apis']):.0f} MB"),
        criterio(PRUEBA, "K6. Arranque, primera pregunta y Verificar (medianas)",
                 f"{d['arranque']:.1f} s; {d['primera']:.2f} s; x{lentitud:.2f}",
                 f"≤ {ARRANQUE_MAXIMO} s; ≤ {PRIMERA_MAXIMA} s; ≤ x{LENTITUD_MAXIMA:.2f}",
                 d["arranque"] <= ARRANQUE_MAXIMO and d["primera"] <= PRIMERA_MAXIMA and lentitud <= LENTITUD_MAXIMA,
                 f"antes {a['arranque']:.1f} s; {a['primera']:.2f} s; Verificar {a['verificar']:.3f} s y ahora "
                 f"{d['verificar']:.3f} s"),
    ]  # fmt: skip


def k7(despues):
    """Sin los pesos aparte, o con otra huella, el motor usa el ONNX de siempre y responde lo mismo."""
    repo, prefijo, largo = motor.modelos_app()[0]
    correctos = []
    for reemplazo in ({"_dir_pesos": lambda repo: config.DIR_MOTOR_APP / "no-existe"},
                      {"_origen": lambda ruta: {"revision": "otra"}}):  # fmt: skip
        previos = {k: getattr(motor, k) for k in reemplazo}
        for k, v in reemplazo.items():
            setattr(motor, k, v)
        try:
            m = motor.para_app(repo, prefijo, largo)
            s = sv.Servicio(semaforo.Semaforo(st=m))
            previo, semaforo._semaforo = semaforo._semaforo, lambda s=s: s.semaforo
            try:
                r = [huella(s.verificar(*p)) for p in pedidos([])]
            finally:
                semaforo._semaforo = previo
        finally:
            for k, v in previos.items():
                setattr(motor, k, v)
        correctos.append(m is not None and not m.pesos_aparte and r == despues["verificar"][-RESPALDO:])
    peticiones = sum(m["peticiones"] for m in despues["arranques"])
    return criterio(PRUEBA, "K7. Sin pesos aparte / con otra huella sigue igual; peticiones de red",
                    f"{' / '.join('sí' if c else 'no' for c in correctos)}; {peticiones}", "sí / sí; 0",
                    all(correctos) and peticiones == 0, f"{RESPALDO} textos; P1 a P5 en radar.app.validar")  # fmt: skip


def k6b(pares):
    """pares: [(segundos de Verificar antes, ahora)]."""
    razones = [ahora / antes for antes, ahora in pares]
    razon = statistics.median(razones)
    antes, ahora = (statistics.median(p[i] for p in pares) for i in (0, 1))
    return criterio(PRUEBA, "K6b. Verificar frente al código anterior (mediana de la razón por par)", f"x{razon:.2f}",
                    f"≤ x{LENTITUD_MAXIMA:.2f}", razon <= LENTITUD_MAXIMA and len(pares) == PARES,
                    f"{len(pares)} pares; antes {antes:.3f} s y ahora {ahora:.3f} s; razones de {min(razones):.2f} a "
                    f"{max(razones):.2f}")  # fmt: skip


def pareada(anterior):
    """K6b, una sola vez: arranques alternados del código anterior (src de otra carpeta) y del actual."""
    nombre = "K6b."
    if any(
        f["prueba"] == PRUEBA and f["criterio"].startswith(nombre) for f in leer_csv(config.DIR_APP / "validacion.csv")
    ):
        raise SystemExit("K6b ya se midió: la sección 16.6 pide una sola vez")
    carpeta = Path(anterior).resolve() / "src"
    actual = Path(__file__).resolve().parents[2]
    if not (carpeta / "radar" / "app" / "api.py").exists() or carpeta == actual:
        raise SystemExit(f"{carpeta} no tiene el código anterior")
    pares, avance = [], Avance("K6b", PARES, cada=1)
    for i in range(PARES):
        orden = (carpeta, actual) if i % 2 == 0 else (actual, carpeta)
        medido = {c: medir_api(c) for c in orden}
        pares.append((medido[carpeta]["verificar"], medido[actual]["verificar"]))
        log.info(f"par {i + 1}: {medido}")
        avance.paso()
    fila = k6b(pares)
    guardar_json(ruta("pareada", "json"), {"pares": pares})
    guardar([*(f for f in leer_csv(config.DIR_APP / "validacion.csv") if f["prueba"] == PRUEBA), fila],
            config.DIR_APP / "validacion.csv")  # fmt: skip
    print(f"[{'ok' if fila['pasa'] else 'NO'}] {fila['criterio']}: {fila['valor']} (umbral {fila['umbral']}) "
          f"{fila['detalle']}")  # fmt: skip


def registrada():
    return MUESTRA in {f["muestra"] for f in leer_csv(config.ARCHIVO_NOTAS_VISTAS)}


def comparar(repetir=False):
    if registrada() and not repetir:
        raise SystemExit(f"La prueba ya se miró ({MUESTRA} en notas_vistas.csv). Usa --repetir y decláralo.")
    antes, despues = leer_json(ruta("antes", "json")), leer_json(ruta("despues", "json"))
    if not antes or not despues or antes["pedidos"] != despues["pedidos"]:
        raise SystemExit("Faltan las capturas, o no usaron la misma muestra")
    with np.load(ruta("antes", "npz")) as a, np.load(ruta("despues", "npz")) as d:
        matrices = [(a[k], d[k]) for k in a.files]
    filas = [
        k1(antes, despues, matrices),
        k_iguales("K2. Verificar igual (salida completa)", antes["verificar"], despues["verificar"],
                  f"{len(antes['verificar']) - RESPALDO} notas nuevas y {RESPALDO} textos de P1"),
        k_iguales("K3. Preguntar igual (salida completa)", antes["preguntar"], despues["preguntar"],
                  f"ronda c, {len(CONSULTAS)} sintéticas nuevas y {len(va.CONSULTAS)} de P1"),
        k_iguales("K4. Panorama, estado y Metodología iguales", list(antes["panorama"].items()),
                  list(despues["panorama"].items()), "con y sin filtros"),
        *k5_k6(antes, despues), k7(despues),
    ]  # fmt: skip
    if repetir:
        for f in filas:
            f["criterio"] = "(repetida) " + f["criterio"]
    guardar(filas, config.DIR_APP / "validacion.csv")
    if not registrada():
        marcar_vistas(muestra(), MUESTRA)
    for f in filas:
        print(f"[{'ok' if f['pasa'] else 'NO'}] {f['criterio']}: {f['valor']} (umbral {f['umbral']}) {f['detalle']}")


@exclusivo("radar.app.validar_memoria")
def main(argv=None):
    ap = argparse.ArgumentParser(description="Memoria de la API (sección 16): K1 a K7.")
    ap.add_argument("accion", choices=("capturar", "comparar", "pareada"))
    ap.add_argument("momento", nargs="?", choices=("antes", "despues"))
    ap.add_argument("--repetir", action="store_true", help="volver a medir una prueba ya mirada (se declara)")
    ap.add_argument("--anterior", help="carpeta del repositorio con el código anterior (pareada)")
    a = ap.parse_args(argv)
    configurar("app-memoria")
    if a.accion == "capturar":
        if not a.momento:
            ap.error("falta antes o despues")
        capturar(a.momento)
    elif a.accion == "pareada":
        if not a.anterior:
            ap.error("falta --anterior")
        pareada(a.anterior)
    else:
        comparar(a.repetir)


if __name__ == "__main__":
    main()
