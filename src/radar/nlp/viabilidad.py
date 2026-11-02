"""Pruebas de viabilidad de los modelos, con criterios fijados antes de correrlas (docs/nlp/viabilidad-modelos.md).

Uso: python -m radar.nlp.viabilidad emociones   # A: pysentimiento sobre titulares (E2 y revisión cualitativa)
     python -m radar.nlp.viabilidad memoria     # B, D1: pico de memoria, un proceso por configuración
     python -m radar.nlp.viabilidad d2          # B, D2: ONNX cuantizado frente a float32, y control del instrumento
Requiere pip install -e ".[nlp]" y los modelos en la caché de Hugging Face (no se descargan aquí).

Las muestras de A se guardan en config/notas_vistas.csv con el nombre de su semilla; si esa semilla ya está, se
vuelven a usar las mismas notas en vez de sortear otras, para que la prueba se pueda reproducir.
"""

import argparse
import collections
import json
import logging
import os
import random
import re
import subprocess
import sys

import numpy as np

from radar import config
from radar.comun.archivos import leer_csv
from radar.comun.registro import configurar
from radar.comun.texto import ahora
from radar.noticias.medios import MEDIOS
from radar.noticias.validar_texto import marcar_vistas, notas_vistas, reservada_capa3
from radar.noticias.viabilidad import _azar, _muestra, _si, criterio, guardar, reporte

log = logging.getLogger(__name__)

# ---------------------------------------------------------------- A: pysentimiento
PRUEBA_A = "Emociones en titulares (informativo)"
SEMILLA_E2 = "pysentimiento-e2-31oct"
POR_MEDIO_E2 = 25
SEMILLA_REVISION = "pysentimiento-e1-31oct"
POR_GRUPO_REVISION = 10  # titulares con emoción y, aparte, "others"
# ---------------------------------------------------------------- B: memoria y ONNX
PRUEBA_D1 = "Memoria para Streamlit Cloud (D1)"
PRUEBA_D2 = "ONNX cuantizado frente a float32 (D2)"
PRUEBA_INSTRUMENTO = "ONNX float32 frente a torch (control del instrumento)"
MEMORIA_MAXIMA_GB = 2.0  # D1: 25 % de margen bajo 2,7 GB
ETIQUETAS_IGUALES_MINIMO = 0.99  # D2
DELTA_P_MAXIMO = 0.05  # D2: |Δp| por par
DELTA_P_EN_RANGO_MINIMO = 0.99  # D2: parte de los pares con |Δp| ≤ DELTA_P_MAXIMO
COSENO_MINIMO = 0.99  # D2: todos los párrafos del ENFEN
DELTA_INSTRUMENTO_MAXIMO = 0.001
N_PARES = 300
N_PARES_INSTRUMENTO = 60
PALABRAS_MINIMAS_HIPOTESIS = 6
SEMILLA_D2 = "b-d2-31oct"
LARGO_EMBEDDING, LARGO_NLI = 256, 512  # tokens
# Archivos ONNX de cada modelo en su repositorio de Hugging Face: float32 y cuantizado
ONNX = {
    "minilm": {"onnx32": "onnx/model.onnx", "onnxq": "onnx/model_quint8_avx2.onnx"},
    "e5": {"onnxq": "onnx/model_qint8_avx512_vnni.onnx"},
    "nli": {"onnx32": "onnx/model.onnx", "onnxq": "onnx/model_quantized.onnx"},
}
PREFIJO = {"minilm": "", "e5": "query: "}
# (embedding, motor del embedding, motor del NLI o None): las cuatro definidas antes y las cuatro del diagnóstico
CONFIGURACIONES = (
    ("minilm", "torch", "torch"),
    ("e5", "torch", "torch"),
    ("minilm", "onnxq", "onnxq"),
    ("e5", "onnxq", "onnxq"),
    ("minilm", "onnx32", "onnx32"),
    ("e5", "onnxq", "onnx32"),
    ("minilm", "onnx32", None),
    ("e5", "onnxq", None),
)


# ---------------------------------------------------------------- A: muestras


def disponibles(notas, vistas):
    """Notas sobre El Niño que ninguna validación vio ni están reservadas para la capa 3."""
    return [n for n in notas if _si(n["sobre_nino"]) and (n["medio"], n["id"]) not in vistas and not reservada_capa3(n)]


def registrada(muestra):
    """Notas que una muestra anterior ya guardó en config/notas_vistas.csv, en el orden en que se guardaron."""
    return [(f["medio"], f["id"]) for f in leer_csv(config.ARCHIVO_NOTAS_VISTAS) if f["muestra"] == muestra]


def muestra_e2(notas, vistas, anterior):
    """POR_MEDIO_E2 notas por medio; si la semilla ya tiene muestra, esa misma."""
    if anterior:
        por_clave = {(n["medio"], n["id"]): n for n in notas}
        return [por_clave[c] for c in anterior if c in por_clave], False
    pool = disponibles(notas, vistas)
    elegidas = [
        m
        for nombre in MEDIOS
        for m in _muestra([n for n in pool if n["medio"] == nombre], POR_MEDIO_E2, SEMILLA_E2, nombre)
    ]
    return elegidas, True


def muestra_revision(salidas, anterior):
    """POR_GRUPO_REVISION titulares con emoción y otros tantos "others", mezclados. salidas: [(nota, emoción)]."""
    if anterior:
        claves = set(anterior)
        return [x for x in salidas if (x[0]["medio"], x[0]["id"]) in claves], False
    azar = _azar(SEMILLA_REVISION)
    con = [x for x in salidas if x[1] != "others"]
    sin = [x for x in salidas if x[1] == "others"]
    elegidas = azar.sample(con, min(POR_GRUPO_REVISION, len(con))) + azar.sample(sin, min(POR_GRUPO_REVISION, len(sin)))
    azar.shuffle(elegidas)
    return elegidas, True


def resumen_e2(salidas):
    """salidas: [(nota, emoción, polaridad)] → filas de criterio (informativas)."""
    emociones = collections.Counter(e for _, e, _ in salidas)
    polaridad = collections.Counter(p for _, _, p in salidas)
    por_medio = collections.defaultdict(collections.Counter)
    for n, e, _ in salidas:
        por_medio[n["medio"]][e] += 1
    detalle = "; ".join(f"{m} {c['others']}/{sum(c.values())}" for m, c in por_medio.items())
    return [
        criterio(PRUEBA_A, "E2: titulares 'others'", emociones["others"], len(salidas), True, detalle),
        criterio(PRUEBA_A, "E2: polaridad", dict(polaridad), "", True),
    ]


def prueba_emociones():
    import transformers
    from pysentimiento import create_analyzer

    transformers.logging.set_verbosity_error()
    emocion = create_analyzer(task="emotion", lang="es")
    sentimiento = create_analyzer(task="sentiment", lang="es")
    notas, vistas = leer_csv(config.DIR_NOTICIAS / "notas.csv"), notas_vistas()

    elegidas, nueva = muestra_e2(notas, vistas, registrada(SEMILLA_E2))
    salidas = [(n, emocion.predict(n["titular"]).output, sentimiento.predict(n["titular"]).output) for n in elegidas]
    if nueva:
        marcar_vistas(elegidas, SEMILLA_E2)
    filas = resumen_e2(salidas)

    anterior = registrada(SEMILLA_REVISION)
    vistas = notas_vistas()
    pool = [n for n in notas if (n["medio"], n["id"]) in set(anterior)] if anterior else disponibles(notas, vistas)
    pool.sort(key=lambda n: (n["medio"], n["id"]))
    predicciones = [(n, emocion.predict(n["titular"])) for n in pool]
    revision, nueva = muestra_revision([(n, p.output) for n, p in predicciones], anterior)
    probas = {(n["medio"], n["id"]): p.probas for n, p in predicciones}
    if not anterior:
        con = sum(p.output != "others" for _, p in predicciones)
        filas.append(criterio(PRUEBA_A, "titulares con emoción en lo no visto", con, len(predicciones), True))
    log.info("\nRevisión cualitativa (sin cifra de exactitud):")
    for i, (n, e) in enumerate(revision, 1):
        log.info(f"{i:2}. [{e} {probas[(n['medio'], n['id'])][e]:.2f}] {n['titular']}")
    if nueva:
        marcar_vistas([n for n, _ in revision], SEMILLA_REVISION)
    return filas


# ---------------------------------------------------------------- B: modelos


def _ruta_hf(repo, archivo):
    from huggingface_hub import hf_hub_download

    return hf_hub_download(repo, archivo, local_files_only=True)


def _normalizar(v):
    return v / np.linalg.norm(v, axis=1, keepdims=True)


def _promedio(h, mascara):
    m = mascara[..., None].astype(np.float32)
    return (h * m).sum(1) / m.sum(1)


def _softmax(z):
    z = np.exp(z - z.max(-1, keepdims=True))
    return z / z.sum(-1, keepdims=True)


class Torch:
    """Modelo de transformers en float32 (CLAUDE.md): embedding por promedio de tokens o NLI."""

    def __init__(self, repo, prefijo=""):
        import torch
        from transformers import AutoModel, AutoModelForSequenceClassification, AutoTokenizer

        self.torch, self.prefijo = torch, prefijo
        self.tok = AutoTokenizer.from_pretrained(repo)
        clase = AutoModelForSequenceClassification if repo == config.MODELO_NLI else AutoModel
        self.modelo = clase.from_pretrained(repo, dtype=torch.float32).eval()

    def embeber(self, textos):
        e = self.tok(
            [self.prefijo + t for t in textos],
            padding=True,
            truncation=True,
            max_length=LARGO_EMBEDDING,
            return_tensors="pt",
        )
        with self.torch.no_grad():
            h = self.modelo(**e).last_hidden_state.numpy()
        return _normalizar(_promedio(h, e["attention_mask"].numpy()))

    def nli(self, premisas, hipotesis):
        e = self.tok(premisas, hipotesis, padding=True, truncation=True, max_length=LARGO_NLI, return_tensors="pt")
        with self.torch.no_grad():
            return self.torch.softmax(self.modelo(**e).logits, -1).numpy()


class Onnx:
    """El mismo cálculo que Torch con onnxruntime."""

    def __init__(self, repo, archivo, prefijo="", sesion=None, tok=None):
        self.prefijo = prefijo
        if sesion is None:
            import onnxruntime as ort
            from transformers import AutoTokenizer

            tok = AutoTokenizer.from_pretrained(repo)
            sesion = ort.InferenceSession(_ruta_hf(repo, archivo), providers=["CPUExecutionProvider"])
        self.tok, self.sesion = tok, sesion
        self.entradas = {i.name for i in sesion.get_inputs()}

    def correr(self, e):
        feed = {k: np.asarray(v).astype(np.int64) for k, v in e.items() if k in self.entradas}
        # El tokenizador de MiniLM no siempre devuelve token_type_ids y el grafo los exige: sin ellos falla
        if "token_type_ids" in self.entradas and "token_type_ids" not in feed:
            feed["token_type_ids"] = np.zeros_like(feed["input_ids"])
        return self.sesion.run(None, feed)[0]

    def embeber(self, textos):
        e = self.tok(
            [self.prefijo + t for t in textos],
            padding=True,
            truncation=True,
            max_length=LARGO_EMBEDDING,
            return_tensors="np",
        )
        return _normalizar(_promedio(self.correr(e), e["attention_mask"]))

    def nli(self, premisas, hipotesis):
        e = self.tok(premisas, hipotesis, padding=True, truncation=True, max_length=LARGO_NLI, return_tensors="np")
        return _softmax(self.correr(e))


def modelo(nombre, motor):
    """nombre: 'nli' o una clave de config.MODELOS_EMBEDDING; motor: 'torch', 'onnx32' u 'onnxq'."""
    repo = config.MODELO_NLI if nombre == "nli" else config.MODELOS_EMBEDDING[nombre]
    prefijo = PREFIJO.get(nombre, "")
    return Torch(repo, prefijo) if motor == "torch" else Onnx(repo, ONNX[nombre][motor], prefijo)


# ---------------------------------------------------------------- B: D1, memoria


def pico_memoria_gb():
    """Pico de memoria del proceso: peak working set en Windows, ru_maxrss en Linux (en KB)."""
    import psutil

    info = psutil.Process().memory_info()
    if hasattr(info, "peak_wset"):
        return info.peak_wset / 2**30, info.rss / 2**30
    import resource

    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 2**20, info.rss / 2**30


def nombre_configuracion(emb, motor_emb, motor_nli):
    return f"{emb} {motor_emb}" + (f" + NLI {motor_nli}" if motor_nli else " (solo embedding)")


def medir(emb, motor_emb, motor_nli):
    """Lo que hace la app al arrancar: importa streamlit, carga modelos y párrafos, una inferencia de cada modelo."""
    import streamlit  # noqa: F401  la app lo importa siempre

    e = modelo(emb, motor_emb)
    n = modelo("nli", motor_nli) if motor_nli else None
    textos = [p["texto"] for p in leer_csv(config.DIR_OFICIAL / "parrafos.csv")]
    e.embeber(textos[:1])
    if n:
        n.nli([textos[0]], [textos[1]])
    pico, estable = pico_memoria_gb()
    return {"pico_gb": round(pico, 3), "estable_gb": round(estable, 3), "parrafos": len(textos)}


def criterio_d1(configuracion, medida):
    pico = medida["pico_gb"]
    detalle = f"estable {medida['estable_gb']} GB; {medida['parrafos']} párrafos"
    return criterio(PRUEBA_D1, configuracion, pico, MEMORIA_MAXIMA_GB, pico <= MEMORIA_MAXIMA_GB, detalle)


def prueba_memoria():
    """Un proceso por configuración, para que el pico de una no se sume al de otra."""
    filas = []
    for emb, motor_emb, motor_nli in CONFIGURACIONES:
        nombre = nombre_configuracion(emb, motor_emb, motor_nli)
        orden = [sys.executable, "-m", "radar.nlp.viabilidad", "medir", emb, motor_emb, motor_nli or "-"]
        salida = subprocess.run(orden, capture_output=True, text=True, encoding="utf-8", cwd=config.RAIZ)
        lineas = [x for x in salida.stdout.splitlines() if x.startswith("{")]
        if salida.returncode or not lineas:
            log.warning(f"{nombre}: falló (código {salida.returncode}); {salida.stderr[-300:]}")
            filas.append(criterio(PRUEBA_D1, nombre, "falló", MEMORIA_MAXIMA_GB, False, salida.stderr[-200:]))
            continue
        filas.append(criterio_d1(nombre, json.loads(lineas[-1])))
    return filas


# ---------------------------------------------------------------- B: D2, equivalencia


def parrafos_enfen():
    return [p for p in leer_csv(config.DIR_OFICIAL / "parrafos.csv") if p["fuente"] == "enfen"]


def pares(parrafos, n=N_PARES, semilla=SEMILLA_D2):
    """(premisa, hipótesis): un párrafo y una frase de otro comunicado, de al menos PALABRAS_MINIMAS_HIPOTESIS."""
    azar, salida = random.Random(semilla), []
    while len(salida) < n:
        a, b = azar.sample(parrafos, 2)
        if a["doc_id"] == b["doc_id"]:
            continue
        frases = [f for f in re.split(r"(?<=\.)\s+", b["texto"]) if len(f.split()) >= PALABRAS_MINIMAS_HIPOTESIS]
        if frases:
            salida.append((a["texto"], azar.choice(frases)))
    return salida


def comparar_nli(a, b):
    """Probabilidades de referencia y de prueba (pares × 3) → parte de etiquetas iguales y |Δp| máximo por par."""
    return (a.argmax(1) == b.argmax(1)).mean(), np.abs(a - b).max(1)


def criterios_nli(prueba, a, b, minimo_iguales, delta_maximo, minimo_en_rango):
    iguales, delta = comparar_nli(a, b)
    en_rango = (delta <= delta_maximo).mean()
    detalle = f"|Δp| máx {delta.max():.4f}; mediana {np.median(delta):.4f}; {len(a)} pares"
    return [
        criterio(prueba, "NLI: etiqueta igual", round(float(iguales), 4), minimo_iguales, iguales >= minimo_iguales),
        criterio(
            prueba,
            f"NLI: |Δp| ≤ {delta_maximo}",
            round(float(en_rango), 4),
            minimo_en_rango,
            en_rango >= minimo_en_rango,
            detalle,
        ),
    ]


def criterio_coseno(prueba, nombre, u, v, minimo=COSENO_MINIMO):
    cos = (u * v).sum(1)
    detalle = f"mediana {np.median(cos):.4f}; {len(cos)} párrafos"
    return criterio(
        prueba, f"{nombre}: coseno mínimo", round(float(cos.min()), 4), minimo, cos.min() >= minimo, detalle
    )


def _uno_a_uno(metodo, entradas):
    """Una entrada por llamada, sin relleno, como en la app."""
    return np.vstack([metodo(*x) for x in entradas])


def prueba_d2():
    ps = parrafos_enfen()
    lista = pares(ps)
    premisas = [([x], [y]) for x, y in lista]
    referencia = _uno_a_uno(modelo("nli", "torch").nli, premisas)
    filas = criterios_nli(
        PRUEBA_D2, referencia, _uno_a_uno(modelo("nli", "onnxq").nli, premisas),
        ETIQUETAS_IGUALES_MINIMO, DELTA_P_MAXIMO, DELTA_P_EN_RANGO_MINIMO,
    )  # fmt: skip
    control = premisas[:N_PARES_INSTRUMENTO]
    filas += criterios_nli(
        PRUEBA_INSTRUMENTO, referencia[:N_PARES_INSTRUMENTO], _uno_a_uno(modelo("nli", "onnx32").nli, control),
        1.0, DELTA_INSTRUMENTO_MAXIMO, 1.0,
    )  # fmt: skip
    textos = [([p["texto"]],) for p in ps]
    for emb, motores in ONNX.items():
        if emb == "nli":
            continue
        u = _uno_a_uno(modelo(emb, "torch").embeber, textos)
        filas.append(
            criterio_coseno(PRUEBA_D2, f"{emb} cuantizado", u, _uno_a_uno(modelo(emb, "onnxq").embeber, textos))
        )
        if "onnx32" in motores:
            v = _uno_a_uno(modelo(emb, "onnx32").embeber, textos)
            filas.append(criterio_coseno(PRUEBA_INSTRUMENTO, f"{emb} float32", u, v, 1 - DELTA_INSTRUMENTO_MAXIMO))
    return filas


# ---------------------------------------------------------------- principal


def main(argv=None):
    ap = argparse.ArgumentParser(description="Pruebas de viabilidad de los modelos.")
    ap.add_argument("prueba", choices=("emociones", "memoria", "d2", "medir"))
    ap.add_argument("config", nargs="*", help="solo con medir: embedding, motor del embedding y del NLI (o -)")
    args = ap.parse_args(argv)
    os.environ.setdefault("HF_HUB_OFFLINE", "1")  # solo la caché: sin consultas al Hub (los hijos lo heredan)
    if args.prueba == "medir":  # proceso hijo de memoria: solo imprime la medida
        emb, motor_emb, motor_nli = args.config
        print(json.dumps(medir(emb, motor_emb, None if motor_nli == "-" else motor_nli)))
        return 0
    registro = configurar(f"nlp-viabilidad-{args.prueba}")
    inicio = ahora()
    filas = {"emociones": prueba_emociones, "memoria": prueba_memoria, "d2": prueba_d2}[args.prueba]()
    ruta = config.DIR_NLP / "validacion.csv"
    guardar(filas, ruta)
    reporte(filas, [], inicio)
    log.info(f"Escrito: {ruta.relative_to(config.RAIZ)} · registro: {registro.relative_to(config.RAIZ)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
