"""Embeddings (MiniLM y e5-small) de las notas sobre El Niño y de los controles frente a los párrafos del ENFEN
(docs/nlp/embeddings.md).

Uso: python -m radar.nlp.embeddings leer        # pide páginas: vuelve a leer los cuerpos en memoria y guarda, por
                                                # nota y modelo, los puntajes y el vector promedio; se puede cortar y
                                                # relanzar
     python -m radar.nlp.embeddings criterios   # sin red: titulares, criterios E1 a E5 e informativos
     python -m radar.nlp.embeddings revision    # sin red: 10 notas nuevas con su párrafo más cercano (informativo)
Requiere pip install -e ".[nlp]" y los modelos en la caché de Hugging Face.
"""

import argparse
import base64
import collections
import logging
import os
import re
import sys
import threading

import numpy as np

from radar import config
from radar.comun.archivos import anexar_csv, leer_csv
from radar.comun.candado import exclusivo
from radar.comun.energia import sin_suspension
from radar.comun.registro import configurar, describir
from radar.comun.texto import ahora
from radar.nlp import esquemas, preproceso, tfidf, viabilidad
from radar.noticias.validar_texto import marcar_vistas, notas_vistas
from radar.noticias.viabilidad import _azar, _si, criterio, guardar, reporte

log = logging.getLogger(__name__)

PRUEBA = "Embeddings"
COMPARACION = "Embeddings (informativo)"
# nombre: (modelo de config.MODELOS_EMBEDDING, motor de viabilidad.modelo)
MODELOS = {"minilm": ("minilm", "torch"), "e5": ("e5", "torch"), "e5q": ("e5", "onnxq")}
CANDIDATOS = ("minilm", "e5")  # e5q solo entra en E5
LARGOS = {"minilm": 128, "e5": 512}  # tokens con que se entrenó cada modelo (MiniLM: su sentence_bert_config)
MARGEN_TOKENS = 2  # al juntar piezas, el conteo por separado puede diferir en uno o dos tokens del conteo del tramo
ESTRATO_NINO, ESTRATO_NEGATIVO = tfidf.ESTRATO_NINO, tfidf.ESTRATO_NEGATIVO
ESTRATO_POSITIVO = "positivo"  # notas del control positivo que no son "sobre El Niño"
AUC_SEMAFORO = 0.80  # E3 (README)
AUC_MINIMO = tfidf.AUC_MINIMO  # E4, el mismo umbral que T4
COSENO_INSTRUMENTO = 0.9999  # E2
DELTA_CUANTIZADO = 0.01  # E5
EMPATE = 0.02  # con menos diferencia en E4 se elige e5, que en la app ocupa menos
PREFERIDO_EN_EMPATE = "e5"
BOOTSTRAP = 1000
SEMILLA_BOOTSTRAP = "embeddings-bootstrap-1nov"
SEMILLA_REVISION, POR_REVISION = "embeddings-revision-1nov", 10
# Los mismos términos que T4 quita del vocabulario, aquí como palabras del texto
TERMINOS = re.compile(r"\b(?:enfen|fen|coster[oa]s?|niñ[oa]s?)\b", re.I)
ORACION = re.compile(r"(?<=[.!?;:])\s+")
ARCHIVO, ARCHIVO_VECTORES = "embeddings.csv", "vectores.csv"


# ---------------------------------------------------------------- corpus y texto


def positivas(notas):
    """Control positivo (README): {(medio, id): comunicados citados} de las notas de Andina que citan alguno."""
    return {
        (n["medio"], n["id"]): {c.split(":")[0] for c in n["comunicados"].split("|") if c}
        for n in notas
        if n["medio"] == "andina" and n["comunicados"]
    }


def corpus(notas, control):
    """El del TF-IDF más las notas del control positivo que no son "sobre El Niño"."""
    todo = tfidf.corpus(notas, control)
    dentro = {(n["medio"], n["id"]) for n, _ in todo}
    pos = positivas(notas)
    return todo + [(n, ESTRATO_POSITIVO) for n in notas if (n["medio"], n["id"]) in pos.keys() - dentro]


def sin_fenomeno(texto):
    """El texto sin las menciones de El Niño o La Niña (regla de noticias.rasgos) ni los términos de T4."""
    marcado, _ = preproceso.marcar_fenomeno(texto)
    for marcador in ("xfenninox", "xfenninax"):
        marcado = marcado.replace(marcador, " ")
    return "\n".join(re.sub(r"[ \t]+", " ", TERMINOS.sub(" ", linea)).strip() for linea in marcado.split("\n"))


VARIANTES = {"con": lambda t: t, "sin": sin_fenomeno}


def _partir(linea, n, contar, maximo):
    """Una línea que no cabe se parte por oraciones y, la oración que tampoco cabe, por palabras."""
    if n <= maximo:
        return [(linea, n)]
    oraciones = ORACION.split(linea)
    if len(oraciones) > 1:
        return [p for o, m in zip(oraciones, contar(oraciones), strict=True) for p in _partir(o, m, contar, maximo)]
    piezas, actual = [], []
    for palabra, m in zip(linea.split(), contar(linea.split()), strict=True):
        if actual and sum(x for _, x in actual) + m > maximo:
            piezas.append(actual)
            actual = []
        actual.append((palabra, m))
    piezas.append(actual)
    return [(" ".join(w for w, _ in p), sum(x for _, x in p)) for p in piezas if p]


def tramos(texto, contar, maximo):
    """Junta líneas completas mientras quepan en maximo tokens. contar(textos) → tokens de cada uno, sin especiales."""
    lineas = [linea.strip() for linea in texto.split("\n") if linea.strip()]
    piezas = [p for linea, n in zip(lineas, contar(lineas), strict=True) for p in _partir(linea, n, contar, maximo)]
    salida, actual, usados = [], [], 0
    for pieza, n in piezas:
        if actual and usados + 1 + n > maximo:  # +1: el salto de línea que las une
            salida.append("\n".join(actual))
            actual, usados = [], 0
        usados += n + (1 if actual else 0)
        actual.append(pieza)
    if actual:
        salida.append("\n".join(actual))
    return salida


def _normalizar(v):
    return v / np.linalg.norm(v, axis=-1, keepdims=True)


def a_base64(vector):
    return base64.b64encode(np.asarray(vector, dtype=np.float32).tobytes()).decode("ascii")


def de_base64(celda):
    return np.frombuffer(base64.b64decode(celda), dtype=np.float32)


# ---------------------------------------------------------------- modelos


class Modelo:
    """Un embedding con su largo propio: parte el texto en tramos que caben sin truncar y los embebe."""

    def __init__(self, nombre, motor=None):
        base, tipo = MODELOS[nombre]
        repo, prefijo = config.MODELOS_EMBEDDING[base], viabilidad.PREFIJO[base]
        self.nombre, self.repo, self.prefijo, self.largo = nombre, repo, prefijo, LARGOS[base]
        if motor is None:
            largo = self.largo
            motor = (
                viabilidad.Torch(repo, prefijo, largo)
                if tipo == "torch"
                else viabilidad.Onnx(repo, viabilidad.ONNX[base][tipo], prefijo, largo=largo)
            )
        self.motor, self.tok = motor, motor.tok
        prefijo_tokens = self.contar([prefijo])[0] if prefijo else 0
        self.maximo = self.largo - 2 - prefijo_tokens - MARGEN_TOKENS  # 2: los tokens especiales

    def contar(self, textos):
        return [len(x) for x in self.tok(list(textos), add_special_tokens=False)["input_ids"]] if textos else []

    def tramos(self, texto):
        return tramos(texto, self.contar, self.maximo)

    def truncados(self, textos):
        """Tramos que con el prefijo y los especiales pasan del largo del modelo (E2: deben ser 0)."""
        return (
            sum(len(x) > self.largo for x in self.tok([self.prefijo + t for t in textos])["input_ids"]) if textos else 0
        )

    def embeber(self, textos, lote=16):
        if not textos:
            return np.zeros((0, 1), dtype=np.float32)
        return np.vstack([self.motor.embeber(textos[i : i + lote]) for i in range(0, len(textos), lote)])


class Oficial:
    """Los párrafos del ENFEN embebidos por tramos con un modelo, con y sin los términos del fenómeno."""

    def __init__(self, modelo, parrafos):
        self.ids = [p["id"] for p in parrafos]
        self.doc = {p["id"]: p["doc_id"] for p in parrafos}
        self.por, self.truncados, self.textos = {}, 0, {}
        for v, f in VARIANTES.items():
            textos, de = [], []
            for i, p in enumerate(parrafos):
                t = modelo.tramos(f(p["texto"]))
                textos += t
                de += [i] * len(t)
            vectores, de = modelo.embeber(textos), np.array(de)
            por_parrafo = _normalizar(np.vstack([vectores[de == i].mean(0) for i in range(len(parrafos))]))
            self.por[v] = (vectores, de, por_parrafo, _normalizar(por_parrafo.mean(0)))
            self.truncados += modelo.truncados(textos)
            self.textos[v] = textos


def puntajes(modelo, oficial, texto):
    """({variante_puntaje: valor}, tramos, truncados, vector promedio del texto completo o None)."""
    por_variante = {v: modelo.tramos(f(texto)) for v, f in VARIANTES.items()}
    todos = [t for ts in por_variante.values() for t in ts]
    vectores, fila, promedio, i = modelo.embeber(todos), {}, None, 0
    for v, ts in por_variante.items():
        mios = vectores[i : i + len(ts)]
        i += len(ts)
        if not ts:
            continue
        tramos_oficiales, de, por_parrafo, centroide = oficial.por[v]
        sim = mios @ tramos_oficiales.T
        mejor = int(sim.max(0).argmax())
        prom = _normalizar(mios.mean(0))
        fila |= {
            f"{v}_max": round(float(sim.max()), 4),
            f"{v}_parrafo": oficial.ids[de[mejor]],
            f"{v}_prom": round(float((por_parrafo @ prom).max()), 4),
            f"{v}_centroide": round(float(prom @ centroide), 4),
        }
        if v == "con":
            promedio = prom
    return fila, len(por_variante["con"]), modelo.truncados(todos), promedio


def parrafos_enfen():
    return [p for p in leer_csv(config.DIR_OFICIAL / "parrafos.csv") if p["fuente"] == "enfen"]


def cargar(nombres=tuple(MODELOS)):
    os.environ.setdefault("HF_HUB_OFFLINE", "1")
    parrafos = parrafos_enfen()
    modelos = {n: Modelo(n) for n in nombres}
    return modelos, {n: Oficial(m, parrafos) for n, m in modelos.items()}


# ---------------------------------------------------------------- lectura


def fila_embeddings(nota, estrato, campos, modelos, oficiales, positivos, ruta_vectores):
    """Lo que se guarda de una nota leída: puntajes, controles y el vector promedio. El cuerpo se descarta aquí."""
    clave = (nota["medio"], nota["id"])
    fila = {"medio": nota["medio"], "id": nota["id"], "estrato": estrato, "positivo": clave in positivos}
    if not isinstance(campos, dict):
        return {**fila, "error": describir(campos)[:200]}
    sha1, igual = tfidf.sha1_de(nota, campos)
    fila |= {"sha1_cuerpo": sha1, "sha1_igual": igual, "n_palabras": campos["n_palabras"], "error": ""}
    if campos["sin_texto"]:
        return {**fila, "error": "sin texto"}
    texto, _ = tfidf.texto_de(campos)
    vectores = []
    for nombre, modelo in modelos.items():
        p, n, truncados, promedio = puntajes(modelo, oficiales[nombre], texto)
        fila |= {f"{nombre}_{k}": x for k, x in p.items()} | {f"{nombre}_tramos": n, f"{nombre}_truncados": truncados}
        if promedio is not None:
            vectores.append({"medio": nota["medio"], "id": nota["id"], "modelo": nombre, "vector": a_base64(promedio)})
    anexar_csv(ruta_vectores, esquemas.VECTORES, vectores)
    return fila


def leer(parar, limite=None):
    notas = leer_csv(config.DIR_NOTICIAS / "notas.csv")
    todo = corpus(notas, leer_csv(config.DIR_NOTICIAS / "control_negativo.csv"))
    modelos, oficiales = cargar()
    positivos, ruta_vectores = positivas(notas), config.DIR_NLP / ARCHIVO_VECTORES

    def fila_de(nota, estrato, campos):
        return fila_embeddings(nota, estrato, campos, modelos, oficiales, positivos, ruta_vectores)

    return tfidf.leer_cuerpos(todo, config.DIR_NLP / ARCHIVO, esquemas.EMBEDDINGS, fila_de, parar, limite)


# ---------------------------------------------------------------- criterios


def _numero(valor):
    return float(valor) if valor not in ("", None) else None


def valores(filas, clave, cuales):
    return np.array([v for f in filas if cuales(f) and (v := _numero(f.get(clave))) is not None])


def auc(positivos, negativos, semilla=SEMILLA_BOOTSTRAP):
    """(AUC, (límite inferior, superior) del 95 % por bootstrap estratificado)."""
    from sklearn.metrics import roc_auc_score

    if not len(positivos) or not len(negativos):
        return None, (None, None)

    def calcular(a, b):
        return float(roc_auc_score(np.r_[np.ones(len(a)), np.zeros(len(b))], np.r_[a, b]))

    azar = np.random.default_rng(_azar(semilla).getrandbits(32))
    muestras = [
        calcular(azar.choice(positivos, len(positivos)), azar.choice(negativos, len(negativos)))
        for _ in range(BOOTSTRAP)
    ]
    return round(calcular(positivos, negativos), 4), tuple(np.percentile(muestras, [2.5, 97.5]).round(4))


def _texto_auc(valor, ic, a, b):
    return f"IC95 {ic[0]}-{ic[1]}; n {len(a)} frente a {len(b)}" if valor is not None else "sin datos"


def es(estrato):
    return lambda f: f["estrato"] == estrato


def es_positivo(f):
    return _si(f["positivo"])


def semaforo(filas, modelo, tipo, prueba):
    """E3: AUC del control positivo frente a otros temas con el texto completo, y que los umbrales no se crucen."""
    clave = f"{modelo}_con_max"
    a, b = valores(filas, clave, es_positivo), valores(filas, clave, es(ESTRATO_NEGATIVO))
    valor, ic = auc(a, b)
    cruce = valor is None or np.percentile(a, 25) <= np.percentile(b, 75)
    detalle = _texto_auc(valor, ic, a, b)
    if valor is not None:
        detalle += f"; p25 positivo {np.percentile(a, 25):.3f}, p75 otros temas {np.percentile(b, 75):.3f}"
    pasa = valor is not None and valor >= AUC_SEMAFORO and not cruce
    return criterio(
        prueba, f"E3 {tipo} ({modelo}): AUC control positivo, sin cruce", valor, AUC_SEMAFORO, pasa, detalle
    )


def representacion(filas, modelo, tipo, prueba, negativo=ESTRATO_NEGATIVO, variante="sin", puntaje="max", nombre=None):
    """E4: notas sobre El Niño frente al negativo, sin los términos del fenómeno."""
    clave = f"{modelo}_{variante}_{puntaje}"
    a, b = valores(filas, clave, es(ESTRATO_NINO)), valores(filas, clave, es(negativo))
    valor, ic = auc(a, b)
    nombre = nombre or f"E4 {tipo} ({modelo}): AUC sin los términos del fenómeno"
    pasa = valor is not None and valor >= AUC_MINIMO
    return criterio(prueba, nombre, valor, AUC_MINIMO if prueba == PRUEBA else "", pasa, _texto_auc(valor, ic, a, b))


def elegir(e4):
    """El de mayor E4 en cuerpos; si la diferencia es menor que EMPATE, el preferido."""
    mejor = max(e4, key=lambda m: e4[m] or 0)
    otros = [m for m in e4 if m != mejor]
    if PREFERIDO_EN_EMPATE in e4 and all(abs((e4[mejor] or 0) - (e4[m] or 0)) < EMPATE for m in otros):
        return PREFERIDO_EN_EMPATE
    return mejor


def criterios_lectura(todo, filas):
    n = len(todo)
    con_texto = [f for f in filas if not f["error"]]
    errores = collections.Counter(f["error"] for f in filas if f["error"])
    leidas = round(len(con_texto) / n, 4) if n else 0.0
    igual = round(sum(_si(f["sha1_igual"]) for f in con_texto) / len(con_texto), 4) if con_texto else 0.0
    distinto = collections.Counter(f["medio"] for f in con_texto if not _si(f["sha1_igual"]))
    return [
        criterio(
            PRUEBA,
            "E1: notas leídas con texto",
            leidas,
            tfidf.LEIDAS_MINIMO,
            leidas >= tfidf.LEIDAS_MINIMO,
            f"{len(con_texto)}/{n}; sin leer {n - len(filas)}; errores {dict(errores)}",
        ),
        criterio(
            PRUEBA,
            "E1: cuerpo igual al de notas.csv (sha1)",
            igual,
            tfidf.SHA1_IGUAL_MINIMO,
            igual >= tfidf.SHA1_IGUAL_MINIMO,
            f"distinto por medio: {dict(distinto)}",
        ),
    ]


def instrumento(modelos, oficiales):
    """E2: el promedio de tokens reproduce a sentence-transformers en los tramos de los párrafos del ENFEN."""
    from sentence_transformers import SentenceTransformer

    minimos = {}
    for nombre in CANDIDATOS:
        modelo, textos = modelos[nombre], oficiales[nombre].textos["con"]
        st = SentenceTransformer(modelo.repo, device="cpu")
        st.max_seq_length = modelo.largo
        referencia = st.encode([modelo.prefijo + t for t in textos], normalize_embeddings=True, batch_size=16)
        propio = oficiales[nombre].por["con"][0]
        minimos[nombre] = round(float((referencia * propio).sum(1).min()), 6)
    peor = min(minimos.values())
    return criterio(
        PRUEBA,
        "E2: coseno mínimo con sentence-transformers (párrafos del ENFEN)",
        peor,
        COSENO_INSTRUMENTO,
        peor >= COSENO_INSTRUMENTO,
        str(minimos),
    )


def filas_titulares(todo, positivos, modelos, oficiales):
    """Los mismos puntajes con el titular solo (sin red: los titulares están en notas.csv)."""
    filas = []
    for nota, estrato in todo:
        fila = {"medio": nota["medio"], "id": nota["id"], "estrato": estrato}
        fila["positivo"] = (nota["medio"], nota["id"]) in positivos
        for nombre, modelo in modelos.items():
            p, n, truncados, _ = puntajes(modelo, oficiales[nombre], nota["titular"])
            fila |= {f"{nombre}_{k}": x for k, x in p.items()} | {f"{nombre}_truncados": truncados}
        filas.append(fila)
    return filas


def acierto_comunicado(filas, modelo, positivos, oficial):
    """Positivos cuyo párrafo más parecido (texto completo) es del comunicado que citan."""
    casos = [f for f in filas if es_positivo(f) and f.get(f"{modelo}_con_parrafo")]
    bien = sum(oficial.doc[f[f"{modelo}_con_parrafo"]] in positivos[(f["medio"], f["id"])] for f in casos)
    return f"{bien}/{len(casos)}"


def informativos(cuerpos, titulares, menciones, positivos, oficiales):
    filas = []
    for modelo in MODELOS:
        filas.append(semaforo(titulares, modelo, "titulares", COMPARACION))
        filas.append(semaforo(cuerpos, modelo, "cuerpos", COMPARACION))
        filas.append(representacion(titulares, modelo, "titulares", COMPARACION))
        filas.append(representacion(cuerpos, modelo, "cuerpos", COMPARACION))
    for modelo in CANDIDATOS:

        def cuerpo(nombre, modelo=modelo, **opciones):
            return representacion(cuerpos, modelo, "cuerpos", COMPARACION, nombre=f"{nombre} ({modelo})", **opciones)

        filas += [
            cuerpo("cuerpos, frente a cercano, sin términos", negativo="cercano"),
            cuerpo("cuerpos, frente a otros temas, con todo", variante="con"),
            cuerpo("cuerpos, vector promedio, sin términos", puntaje="prom"),
            cuerpo("cuerpos, centroide del ENFEN, sin términos", puntaje="centroide"),
        ]
        for medio in sorted({f["medio"] for f in cuerpos}):
            del_medio = [f for f in cuerpos if f["medio"] == medio]
            filas.append(
                representacion(del_medio, modelo, "cuerpos", COMPARACION, nombre=f"cuerpos de {medio} ({modelo})")
            )
        for desde, hasta in ((1, 2), (3, 5), (6, None)):
            tramo = [
                f
                for f in cuerpos
                if f["estrato"] != ESTRATO_NINO
                or desde <= menciones.get((f["medio"], f["id"]), 0) <= (hasta or float("inf"))
            ]
            texto = f"{desde}-{hasta}" if hasta else f"{desde} o más"
            filas.append(
                representacion(
                    tramo, modelo, "cuerpos", COMPARACION, nombre=f"cuerpos con {texto} menciones ({modelo})"
                )
            )
        andina = [f for f in cuerpos if f["medio"] == "andina"]
        fila = semaforo(andina, modelo, "cuerpos de Andina frente a Andina", COMPARACION)
        filas.append(fila)
        for tipo, grupo in (("titulares", titulares), ("cuerpos", cuerpos)):
            filas.append(
                criterio(
                    COMPARACION,
                    f"positivos con el párrafo más parecido del comunicado citado, {tipo} ({modelo})",
                    acierto_comunicado(grupo, modelo, positivos, oficiales[modelo]),
                    "",
                    True,
                )
            )
    return filas


def criterios():
    notas = leer_csv(config.DIR_NOTICIAS / "notas.csv")
    todo = corpus(notas, leer_csv(config.DIR_NOTICIAS / "control_negativo.csv"))
    positivos, claves = positivas(notas), {(n["medio"], n["id"]) for n, _ in todo}
    filas = [f for k, f in tfidf.leidos(config.DIR_NLP / ARCHIVO).items() if k in claves]
    cuerpos = [f for f in filas if not f["error"]]
    menciones = {(n["medio"], n["id"]): int(n["menciones_nino"] or 0) for n in notas}
    modelos, oficiales = cargar()
    titulares = filas_titulares(todo, positivos, modelos, oficiales)

    e4 = {m: representacion(cuerpos, m, "cuerpos", PRUEBA)["valor"] for m in CANDIDATOS}
    elegido = elegir(e4)
    truncados = {
        "cuerpos": sum(int(f.get(f"{m}_truncados") or 0) for f in cuerpos for m in MODELOS),
        "titulares": sum(int(f.get(f"{m}_truncados") or 0) for f in titulares for m in MODELOS),
        "párrafos": sum(o.truncados for o in oficiales.values()),
    }
    deltas = {
        tipo: round(abs((funcion(cuerpos, "e5q")["valor"] or 0) - (funcion(cuerpos, "e5")["valor"] or 0)), 4)
        for tipo, funcion in (
            ("E3", lambda f, m: semaforo(f, m, "cuerpos", COMPARACION)),
            ("E4", lambda f, m: representacion(f, m, "cuerpos", COMPARACION)),
        )
    }
    delta = max(deltas.values())
    resultado = criterios_lectura(todo, filas) + [
        instrumento(modelos, oficiales),
        criterio(
            PRUEBA, "E2: tramos truncados", sum(truncados.values()), 0, not sum(truncados.values()), str(truncados)
        ),
        semaforo(titulares, elegido, "titulares", PRUEBA),
        semaforo(cuerpos, elegido, "cuerpos", PRUEBA),
        representacion(cuerpos, elegido, "cuerpos", PRUEBA),
        criterio(
            PRUEBA if elegido == "e5" else COMPARACION,
            "E5: |ΔAUC| de e5 cuantizado frente a float32 (cuerpos)",
            delta,
            DELTA_CUANTIZADO,
            delta <= DELTA_CUANTIZADO,
            str(deltas),
        ),
        criterio(COMPARACION, "modelo elegido (mayor E4 en cuerpos)", elegido, "", True, f"E4 {e4}; empate < {EMPATE}"),
        criterio(
            COMPARACION,
            "documentos",
            len(cuerpos),
            "",
            True,
            f"{collections.Counter(f['estrato'] for f in cuerpos)}; positivos {sum(map(es_positivo, cuerpos))}",
        ),
    ]
    return resultado + informativos(cuerpos, titulares, menciones, positivos, oficiales)


# ---------------------------------------------------------------- revisión cualitativa


def elegido_guardado():
    filas = leer_csv(config.DIR_NLP / "validacion.csv")
    return next((f["valor"] for f in filas if f["criterio"].startswith("modelo elegido")), PREFERIDO_EN_EMPATE)


def muestra_revision(cuerpos, notas, anterior, vistas):
    """POR_REVISION notas sobre El Niño leídas que ninguna validación vio; si la semilla ya tiene muestra, esa."""
    por_clave = {(n["medio"], n["id"]): n for n in notas}
    if anterior:
        return [por_clave[c] for c in anterior if c in por_clave], False
    leidas = {(f["medio"], f["id"]) for f in cuerpos if f["estrato"] == ESTRATO_NINO}
    pool = sorted((n for n in viabilidad.disponibles(notas, vistas) if (n["medio"], n["id"]) in leidas), key=_orden)
    return _azar(SEMILLA_REVISION).sample(pool, min(POR_REVISION, len(pool))), True


def _orden(n):
    return n["medio"], n["id"]


def revision():
    """Muestra el párrafo del ENFEN más parecido a cada nota de la muestra, para leerlo (no decide nada)."""
    notas = leer_csv(config.DIR_NOTICIAS / "notas.csv")
    cuerpos = [f for f in tfidf.leidos(config.DIR_NLP / ARCHIVO).values() if not f["error"]]
    por_clave = {(f["medio"], f["id"]): f for f in cuerpos}
    elegidas, nueva = muestra_revision(cuerpos, notas, viabilidad.registrada(SEMILLA_REVISION), notas_vistas())
    if nueva:
        marcar_vistas(elegidas, SEMILLA_REVISION)
    modelo = elegido_guardado()
    textos = {p["id"]: p for p in parrafos_enfen()}
    for n in elegidas:
        f = por_clave[(n["medio"], n["id"])]
        p = textos[f[f"{modelo}_con_parrafo"]]
        log.info(f"\n{n['medio']} {n['id']} · {n['titular']}")
        log.info(f"  {modelo}: coseno {f[f'{modelo}_con_max']} (sin términos {f[f'{modelo}_sin_max']})")
        log.info(f"  {p['doc_id']} [{p['tipo']}] {p['texto'][:400]}")
    return []


# ---------------------------------------------------------------- principal


@exclusivo("radar.nlp.embeddings")
def _leer_exclusivo(parar, limite):
    with sin_suspension():
        return leer(parar, limite)


def main(argv=None):
    ap = argparse.ArgumentParser(description="Embeddings de las notas frente a los párrafos del ENFEN.")
    ap.add_argument("paso", choices=("leer", "criterios", "revision"))
    ap.add_argument("--limite", type=int, help="con leer: como máximo N notas por medio (ensayo corto)")
    args = ap.parse_args(argv)
    registro = configurar(f"nlp-embeddings-{args.paso}")
    inicio, parar = ahora(), threading.Event()
    config.DIR_NLP.mkdir(parents=True, exist_ok=True)
    try:
        if args.paso == "leer":
            filas = _leer_exclusivo(parar, args.limite)
        else:
            filas = criterios() if args.paso == "criterios" else revision()
    except KeyboardInterrupt:
        parar.set()
        log.info(f"Cortado: lo leído quedó en {ARCHIVO}; al relanzar sigue desde ahí.")
        return 1
    if isinstance(filas, int):  # otro proceso tenía el candado
        return filas
    if filas:
        guardar(filas, config.DIR_NLP / "validacion.csv")
        reporte(filas, [], inicio)
    log.info(
        f"Duración: {(ahora() - inicio).total_seconds() / 60:.1f} min · registro: {registro.relative_to(config.RAIZ)}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
