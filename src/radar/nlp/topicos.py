"""Punto 4: tópicos (LDA y BERTopic) y polaridad de las notas sobre El Niño (docs/nlp/topicos.md, definición del 7-nov).

Uso: python -m radar.nlp.topicos muestra   # elige las 400 notas de P2 (100 por medio) y las agrega a notas_vistas.csv
     python -m radar.nlp.topicos leer      # pide páginas: lee los cuerpos en memoria y guarda solo la bolsa de lemas,
                                           # el vector minilm y la polaridad; se puede cortar y relanzar
     python -m radar.nlp.topicos ajustar   # sin red: grilla de tópicos, criterios T1, T2, P1 y P2, y agregados
Requiere pip install -e ".[nlp]" y es_core_news_sm.
"""

import argparse
import collections
import itertools
import logging
import os
import sys
import threading

import numpy as np

from radar import config
from radar.comun.archivos import escribir_csv, leer_csv
from radar.comun.candado import exclusivo
from radar.comun.energia import sin_suspension
from radar.comun.registro import configurar, describir
from radar.comun.texto import ahora
from radar.nlp import embeddings, esquemas, preproceso, tfidf, viabilidad
from radar.noticias.medios import MEDIOS
from radar.noticias.validar_texto import marcar_vistas, notas_vistas
from radar.noticias.viabilidad import _muestra, _si, criterio, guardar, reporte

log = logging.getLogger(__name__)

PRUEBA_T = "Tópicos"
PRUEBA_P = "Polaridad"
K_GRILLA = (6, 8, 10, 12, 15)
SEMILLAS = (0, 1, 2)
TOP = 10  # palabras por tópico para T1, T2 y los informativos
JACCARD_MINIMO = 0.50  # T1
EMPATE_CV = 0.01  # T2: con menos diferencia gana el de menos tópicos
CELDA_MINIMA = 20  # notas para mostrar una celda mes × región
KAPPA_MINIMO = 0.40  # P2
SEMILLA_P2 = "polaridad-7nov"
POR_MEDIO_P2 = 100
LARGO_POLARIDAD = 128  # tokens de robertuito (model_max_length de pysentimiento)
LARGO_NLI = 400  # tokens de la nota por tramo en el zero-shot; la hipótesis va aparte
HIPOTESIS = "El tono de este texto es {}."
ETIQUETAS = ("negativo", "neutral", "positivo")
DE_PYSENTIMIENTO = {"NEG": "negativo", "NEU": "neutral", "POS": "positivo"}
PASADAS_LDA = 10
ARCHIVO = "topicos-lectura.csv"

# Escritas antes de ajustar (definición del 7-nov). Un tópico va a la categoría con más palabras suyas, si son 2 o más.
CATEGORIAS = {
    "Pesca y mar": {"pesca", "pescador", "anchoveta", "pesquero", "pesquera", "mar", "oleaje", "marino", "captura",
                    "desembarque", "imarpe", "artesanal"},
    "Lluvias, ríos y huaicos": {"lluvia", "río", "huaico", "caudal", "inundación", "desborde", "precipitación",
                                "quebrada", "deslizamiento", "huaicos"},
    "Calor": {"calor", "temperatura", "térmico", "radiación", "ultravioleta", "bochorno", "golpe"},
    "Prevención y emergencias": {"emergencia", "prevención", "indeci", "damnificado", "vivienda", "afectado",
                                 "declaratoria", "simulacro", "reconstrucción", "cenepred", "respuesta"},
}  # fmt: skip


# ---------------------------------------------------------------- muestra


def disponibles(notas, vistas):
    return viabilidad.disponibles(notas, vistas)


def muestra(notas, vistas):
    """POR_MEDIO_P2 notas por medio entre las que ninguna validación vio."""
    pool = disponibles(notas, vistas)
    return [m for nombre in MEDIOS for m in _muestra([n for n in pool if n["medio"] == nombre], POR_MEDIO_P2,
                                                       SEMILLA_P2, nombre)]  # fmt: skip


def de_la_muestra():
    return set(viabilidad.registrada(SEMILLA_P2))


def elegir_muestra():
    if de_la_muestra():
        log.info(f"La muestra {SEMILLA_P2} ya está en notas_vistas.csv; no se elige otra.")
        return []
    elegidas = muestra(leer_csv(config.DIR_NOTICIAS / "notas.csv"), notas_vistas())
    marcar_vistas(elegidas, SEMILLA_P2)
    log.info(f"Muestra P2: {collections.Counter(n['medio'] for n in elegidas)}")
    return []


# ---------------------------------------------------------------- polaridad


def promedio(probas):
    """Promedio por etiqueta de las probabilidades de cada tramo."""
    return {e: float(np.mean([p[e] for p in probas])) for e in ETIQUETAS} if probas else {}


def etiqueta(probas):
    return max(ETIQUETAS, key=lambda e: probas[e]) if probas else ""


class Polaridad:
    """pysentimiento (robertuito) por tramos de hasta 128 tokens, sin truncar."""

    def __init__(self):
        import torch
        import transformers
        from pysentimiento import create_analyzer
        from pysentimiento.preprocessing import preprocess_tweet

        transformers.logging.set_verbosity_error()
        self.torch, self.prep = torch, preprocess_tweet
        self.analizador = create_analyzer(task="sentiment", lang="es")
        self.modelo, self.tok = self.analizador.model.float().eval(), self.analizador.tokenizer
        self.etiquetas = [DE_PYSENTIMIENTO[self.modelo.config.id2label[i]] for i in range(len(ETIQUETAS))]
        self.maximo = LARGO_POLARIDAD - 2 - embeddings.MARGEN_TOKENS

    def contar(self, textos):
        return [len(x) for x in self.tok(list(textos), add_special_tokens=False)["input_ids"]] if textos else []

    def tramos(self, texto):
        lineas = [self.prep(linea, **self.analizador.preprocessing_args) for linea in texto.split("\n")]
        return embeddings.tramos("\n".join(lineas), self.contar, self.maximo)

    def truncados(self, tramos):
        return sum(len(x) > LARGO_POLARIDAD for x in self.tok(tramos)["input_ids"]) if tramos else 0

    def probas(self, tramos, lote=16):
        salida = []
        for i in range(0, len(tramos), lote):
            entrada = self.tok(tramos[i : i + lote], padding=True, truncation=True, max_length=LARGO_POLARIDAD,
                               return_tensors="pt")  # fmt: skip
            with self.torch.no_grad():
                p = self.torch.softmax(self.modelo(**entrada).logits, dim=-1).numpy()
            salida += [dict(zip(self.etiquetas, fila.tolist(), strict=True)) for fila in p]
        return salida


class ZeroShot:
    """mDeBERTa NLI: por tramo, softmax de la implicación entre las tres etiquetas (como zero-shot-classification)."""

    def __init__(self):
        import torch
        import transformers
        from transformers import AutoModelForSequenceClassification, AutoTokenizer

        transformers.logging.set_verbosity_error()
        self.torch = torch
        self.tok = AutoTokenizer.from_pretrained(config.MODELO_NLI)
        self.modelo = AutoModelForSequenceClassification.from_pretrained(config.MODELO_NLI, dtype=torch.float32).eval()
        self.implica = {k.lower(): v for k, v in self.modelo.config.label2id.items()}["entailment"]

    def contar(self, textos):
        return [len(x) for x in self.tok(list(textos), add_special_tokens=False)["input_ids"]] if textos else []

    def tramos(self, texto):
        return embeddings.tramos(texto, self.contar, LARGO_NLI)

    def probas(self, tramos):
        salida = []
        for t in tramos:
            entrada = self.tok([t] * len(ETIQUETAS), [HIPOTESIS.format(e) for e in ETIQUETAS], padding=True,
                               truncation="only_first", max_length=512, return_tensors="pt")  # fmt: skip
            with self.torch.no_grad():
                logits = self.modelo(**entrada).logits[:, self.implica]
            salida.append(dict(zip(ETIQUETAS, self.torch.softmax(logits, dim=0).tolist(), strict=True)))
        return salida


# ---------------------------------------------------------------- lectura


def bolsa_sin_etiqueta(texto):
    marcado, _ = preproceso.marcar_fenomeno(texto)
    bolsa = preproceso.bolsas([marcado])[0]
    return collections.Counter({t: n for t, n in bolsa.items() if t not in tfidf.TERMINOS_DE_LA_ETIQUETA})


def fila_lectura(nota, estrato, campos, minilm, polaridad, zero_shot, muestra_p2):
    """Lo que se guarda de una nota leída: bolsa, vector y polaridad. El cuerpo se descarta aquí."""
    fila = {"medio": nota["medio"], "id": nota["id"], "estrato": estrato}
    if not isinstance(campos, dict):
        return {**fila, "error": describir(campos)[:200]}
    sha1, _ = tfidf.sha1_de(nota, campos)
    fila |= {"sha1_cuerpo": sha1, "n_palabras": campos["n_palabras"], "error": ""}
    if campos["sin_texto"]:
        return {**fila, "error": "sin texto"}
    texto, _ = tfidf.texto_de(campos)
    tramos = minilm.tramos(texto)
    vector = embeddings._normalizar(minilm.embeber(tramos).mean(axis=0))
    t_pol = polaridad.tramos(texto)
    p = promedio(polaridad.probas(t_pol))
    fila |= {"lemas": preproceso.a_celda(bolsa_sin_etiqueta(texto)), "vector": embeddings.a_base64(vector),
             "pol_tramos": len(t_pol), "pol_truncados": polaridad.truncados(t_pol),
             **{f"pol_{e}": round(v, 5) for e, v in p.items()}}  # fmt: skip
    if (nota["medio"], nota["id"]) in muestra_p2:
        t_zs = zero_shot.tramos(texto)
        fila |= {
            "zs_tramos": len(t_zs),
            **{f"zs_{e}": round(v, 5) for e, v in promedio(zero_shot.probas(t_zs)).items()},
        }
    return fila


def corpus(notas):
    return [(n, tfidf.ESTRATO_NINO) for n in notas if _si(n["sobre_nino"])]


def leer(parar, limite=None):
    os.environ.setdefault("HF_HUB_OFFLINE", "1")
    muestra_p2 = de_la_muestra()
    if not muestra_p2:
        raise SystemExit("Falta la muestra de P2: python -m radar.nlp.topicos muestra")
    preproceso.modelo()
    minilm, polaridad, zero_shot = embeddings.Modelo("minilm"), Polaridad(), ZeroShot()

    def fila_de(nota, estrato, campos):
        return fila_lectura(nota, estrato, campos, minilm, polaridad, zero_shot, muestra_p2)

    todo = corpus(leer_csv(config.DIR_NOTICIAS / "notas.csv"))
    return tfidf.leer_cuerpos(todo, config.DIR_NLP / ARCHIVO, esquemas.TOPICOS_LECTURA, fila_de, parar, limite)


# ---------------------------------------------------------------- tópicos


def vocabulario_de(bolsas):
    """El mismo corte que TF-IDF: al menos MIN_DF notas y como mucho MAX_DF de ellas."""
    df = collections.Counter(t for b in bolsas for t in b)
    return sorted(t for t, n in df.items() if n >= tfidf.MIN_DF and n / len(bolsas) <= tfidf.MAX_DF)


def matriz(bolsas, vocabulario):
    from scipy import sparse

    columna = {t: j for j, t in enumerate(vocabulario)}
    filas, columnas, valores = [], [], []
    for i, b in enumerate(bolsas):
        for t, n in b.items():
            if t in columna:
                filas.append(i), columnas.append(columna[t]), valores.append(n)
    return sparse.csr_matrix((valores, (filas, columnas)), shape=(len(bolsas), len(vocabulario)), dtype=float)


def ctfidf(x, asignacion, k):
    """c-TF-IDF como BERTopic: frecuencia por clase normalizada × log(1 + palabras promedio por clase / frecuencia)."""
    asignacion = np.asarray(asignacion)
    por_clase = np.vstack([np.asarray(x[asignacion == t].sum(axis=0)).ravel() for t in range(k)])
    total = por_clase.sum(axis=0)
    promedio_clase = por_clase.sum() / max(1, k)
    tf = por_clase / np.maximum(por_clase.sum(axis=1, keepdims=True), 1)
    return tf * np.log(1 + promedio_clase / np.maximum(total, 1))


def palabras(x, asignacion, k, vocabulario, top=TOP):
    """Las TOP palabras de cada tópico con alguna nota; los vacíos quedan como []."""
    pesos = ctfidf(x, asignacion, k)
    conteo = collections.Counter(asignacion)
    return [[vocabulario[j] for j in np.argsort(-pesos[t])[:top]] if conteo[t] else [] for t in range(k)]


def jaccard(a, b):
    a, b = set(a), set(b)
    return len(a & b) / len(a | b) if a | b else 0.0


def emparejado(tops_a, tops_b):
    """Jaccard promedio de los tópicos emparejados con el algoritmo húngaro."""
    from scipy.optimize import linear_sum_assignment

    m = np.array([[jaccard(a, b) for b in tops_b] for a in tops_a])
    filas, columnas = linear_sum_assignment(-m)
    return float(m[filas, columnas].mean())


def estabilidad(corridas):
    """Promedio del Jaccard emparejado entre cada par de semillas."""
    return float(np.mean([emparejado(a, b) for a, b in itertools.combinations(corridas, 2)]))


def coherencia(tops, bolsas):
    """c_v con la nota entera como ventana: solo se guardan bolsas, así que el orden de las palabras no importa."""
    from gensim.corpora import Dictionary
    from gensim.models.coherencemodel import CoherenceModel

    textos = [sorted(b) for b in bolsas]
    tops = [t for t in tops if t]
    diccionario = Dictionary(textos)
    ventana = max(len(t) for t in textos)
    modelo = CoherenceModel(topics=tops, texts=textos, dictionary=diccionario, coherence="c_v", window_size=ventana,
                            processes=1)  # fmt: skip
    return float(modelo.get_coherence())


def diversidad(tops):
    total = [p for t in tops for p in t]
    return len(set(total)) / len(total) if total else 0.0


def categoria(top):
    aciertos = {c: len(set(top) & lista) for c, lista in CATEGORIAS.items()}
    mejor = max(aciertos, key=aciertos.get)
    return mejor if aciertos[mejor] >= 2 else ""


def lda(x, k, semilla):
    from gensim.matutils import Sparse2Corpus
    from gensim.models import LdaModel

    bow = Sparse2Corpus(x, documents_columns=False)
    modelo = LdaModel(corpus=bow, num_topics=k, id2word={j: str(j) for j in range(x.shape[1])}, random_state=semilla,
                      passes=PASADAS_LDA, chunksize=2000)  # fmt: skip
    theta = np.zeros((x.shape[0], k))
    for i, d in enumerate(modelo.get_document_topics(bow, minimum_probability=0)):
        for t, p in d:
            theta[i, t] = p
    return theta.argmax(axis=1)


def bertopic(x, vectores, vocabulario, k, semilla):
    from bertopic import BERTopic
    from sklearn.cluster import KMeans
    from sklearn.feature_extraction.text import CountVectorizer
    from umap import UMAP

    textos = [" ".join(vocabulario[j] for j in fila.indices) for fila in x]
    modelo = BERTopic(
        embedding_model=None,
        umap_model=UMAP(n_neighbors=15, n_components=5, min_dist=0.0, metric="cosine", random_state=semilla),
        hdbscan_model=KMeans(n_clusters=k, random_state=semilla, n_init=10),
        vectorizer_model=CountVectorizer(vocabulary=vocabulario, token_pattern=r"\S+", lowercase=False),
        calculate_probabilities=False,
        language="multilingual",  # con "english" BERTopic borra las tildes antes de su c-TF-IDF
    )
    temas, _ = modelo.fit_transform(textos, embeddings=vectores)
    return np.asarray(temas)


def grilla(x, vectores, vocabulario, bolsas):
    """Una fila por método, k y semilla, con la asignación y las palabras de cada tópico."""
    corridas = []
    for metodo, k, semilla in itertools.product(("lda", "bertopic"), K_GRILLA, SEMILLAS):
        inicio = ahora()
        asignacion = lda(x, k, semilla) if metodo == "lda" else bertopic(x, vectores, vocabulario, k, semilla)
        tops = palabras(x, asignacion, k, vocabulario)
        cv = coherencia(tops, bolsas)
        corridas.append({"metodo": metodo, "k": k, "semilla": semilla, "asignacion": asignacion, "tops": tops,
                         "cv": cv, "vacios": sum(not t for t in tops)})  # fmt: skip
        log.info(f"  {metodo} k={k} semilla={semilla}: c_v {cv:.4f} · {(ahora() - inicio).total_seconds():.0f} s")
    return corridas


def resumen_grilla(corridas):
    """{(metodo, k): {estable, cv, diversidad}} promediando las semillas."""
    salida = {}
    for (metodo, k), grupo in itertools.groupby(corridas, key=lambda c: (c["metodo"], c["k"])):
        grupo = list(grupo)
        salida[(metodo, k)] = {
            "estable": estabilidad([c["tops"] for c in grupo]),
            "cv": float(np.mean([c["cv"] for c in grupo])),
            "diversidad": float(np.mean([diversidad([t for t in c["tops"] if t]) for c in grupo])),
            "vacios": max(c["vacios"] for c in grupo),
        }
    return salida


def elegir(resumen):
    """T1 y T2: entre los estables, el de mayor c_v; a menos de EMPATE_CV, el de menos tópicos. (elegido, estable)."""
    estables = {c: r for c, r in resumen.items() if r["estable"] >= JACCARD_MINIMO}
    if not estables:
        return max(resumen, key=lambda c: (resumen[c]["estable"], -c[1])), False
    mejor = max(r["cv"] for r in estables.values())
    cerca = [c for c, r in estables.items() if mejor - r["cv"] < EMPATE_CV]
    return min(cerca, key=lambda c: (c[1], -estables[c]["cv"])), True


def central(grupo):
    """La semilla más parecida a las otras: la que se reporta."""
    return max(grupo, key=lambda c: sum(emparejado(c["tops"], o["tops"]) for o in grupo if o is not c))


# ---------------------------------------------------------------- polaridad: criterios


def kappa(a, b):
    from sklearn.metrics import cohen_kappa_score

    return float(cohen_kappa_score(a, b, labels=list(ETIQUETAS)))


def probas_de(fila, prefijo):
    return {e: float(fila[f"{prefijo}_{e}"]) for e in ETIQUETAS} if fila.get(f"{prefijo}_{ETIQUETAS[0]}") else {}


def destilado(bolsas, etiquetas_pol, en_muestra, etiquetas_zs):
    """Informativo: TF-IDF + regresión logística entrenada con las etiquetas de pysentimiento fuera de la muestra."""
    from sklearn.feature_extraction import DictVectorizer
    from sklearn.feature_extraction.text import TfidfTransformer
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import make_pipeline

    entreno = [i for i, m in enumerate(en_muestra) if not m]
    prueba = [i for i, m in enumerate(en_muestra) if m]
    if len(set(etiquetas_pol[i] for i in entreno)) < 2 or not prueba:
        return None
    modelo = make_pipeline(DictVectorizer(), TfidfTransformer(sublinear_tf=True), LogisticRegression(max_iter=2000))
    modelo.fit([dict(bolsas[i]) for i in entreno], [etiquetas_pol[i] for i in entreno])
    pred = modelo.predict([dict(bolsas[i]) for i in prueba])
    return kappa(pred, [etiquetas_pol[i] for i in prueba]), kappa(pred, [etiquetas_zs[i] for i in prueba])


# ---------------------------------------------------------------- agregados


def agregados(claves, asignacion, etiquetas_pol, notas, regiones, k):
    """Filas por mes, por región y por mes × región (solo celdas con CELDA_MINIMA o más notas)."""
    por_clave = {(n["medio"], n["id"]): n for n in notas}
    region = {(r["medio"], r["id"]): r["macroregion_principal"] for r in regiones}
    filas = []
    celdas = collections.defaultdict(list)
    for c, t, p in zip(claves, asignacion, etiquetas_pol, strict=True):
        mes = por_clave[c]["fecha_publicacion"][:7]
        reg = region.get(c, "") or "sin_region"
        for dimension, valor in (("mes", mes), ("region", reg), ("mes_region", f"{mes}|{reg}")):
            celdas[(dimension, valor)].append((t, p))
    for (dimension, valor), lista in sorted(celdas.items()):
        n = len(lista)
        if dimension == "mes_region" and n < CELDA_MINIMA:
            continue
        temas, pol = collections.Counter(t for t, _ in lista), collections.Counter(p for _, p in lista)
        filas.append({"dimension": dimension, "valor": valor, "n": n,
                      **{f"topico_{t}": round(temas[t] / n, 4) for t in range(k)},
                      **{f"pol_{e}": round(pol[e] / n, 4) for e in ETIQUETAS}})  # fmt: skip
    return filas


# ---------------------------------------------------------------- ajuste


def ajustar():
    notas = leer_csv(config.DIR_NOTICIAS / "notas.csv")
    claves_nino = {(n["medio"], n["id"]) for n, _ in corpus(notas)}
    lectura = [f for k, f in tfidf.leidos(config.DIR_NLP / ARCHIVO).items() if k in claves_nino]
    validas = [f for f in lectura if not f["error"]]
    claves = [(f["medio"], f["id"]) for f in validas]
    bolsas = [preproceso.de_celda(f["lemas"]) for f in validas]
    vectores = np.vstack([embeddings.de_base64(f["vector"]) for f in validas])
    vocabulario = vocabulario_de(bolsas)
    x = matriz(bolsas, vocabulario)
    bolsas_vocab = [{t: n for t, n in b.items() if t in set(vocabulario)} for b in bolsas]
    log.info(f"Notas {len(validas)} · vocabulario {len(vocabulario)}")

    corridas = grilla(x, vectores, vocabulario, bolsas_vocab)
    resumen = resumen_grilla(corridas)
    (metodo, k), estable = elegir(resumen)
    elegida = central([c for c in corridas if (c["metodo"], c["k"]) == (metodo, k)])
    asignacion = elegida["asignacion"]

    medios = [c[0] for c in claves]
    pol = [probas_de(f, "pol") for f in validas]
    etiquetas_pol = [etiqueta(p) for p in pol]
    escribir_csv(config.DIR_NLP / "topicos-grilla.csv", esquemas.TOPICOS_GRILLA,
                 [{"metodo": c["metodo"], "k": c["k"], "semilla": c["semilla"], "cv": round(c["cv"], 4),
                   "vacios": c["vacios"], "estable": round(resumen[(c["metodo"], c["k"])]["estable"], 4),
                   "palabras": " | ".join(",".join(t) for t in c["tops"])} for c in corridas])  # fmt: skip
    escribir_csv(config.DIR_NLP / "topicos-notas.csv", esquemas.TOPICOS_NOTAS,
                 [{"medio": m, "id": i, "topico": int(t), "polaridad": p}
                  for (m, i), t, p in zip(claves, asignacion, etiquetas_pol, strict=True)])  # fmt: skip
    nombres = []
    for t, top in enumerate(elegida["tops"]):
        dentro = [i for i, a in enumerate(asignacion) if a == t]
        cuenta_medio = collections.Counter(medios[i] for i in dentro)
        cuenta_pol = collections.Counter(etiquetas_pol[i] for i in dentro)
        nombres.append({"topico": t, "n": len(dentro), "palabras": ",".join(top), "categoria": categoria(top),
                        **{f"medio_{m}": round(cuenta_medio[m] / max(1, len(dentro)), 4) for m in MEDIOS},
                        **{f"pol_{e}": round(cuenta_pol[e] / max(1, len(dentro)), 4) for e in ETIQUETAS}})  # fmt: skip
    escribir_csv(config.DIR_NLP / "topicos-nombres.csv", esquemas.topicos_nombres(MEDIOS), nombres)
    escribir_csv(config.DIR_NLP / "topicos-agregados.csv", esquemas.topicos_agregados(k),
                 agregados(claves, asignacion, etiquetas_pol, notas,
                           leer_csv(config.DIR_NOTICIAS / "regiones.csv"), k))  # fmt: skip
    return criterios_topicos(lectura, claves_nino, resumen, (metodo, k), estable, elegida) + criterios_polaridad(
        validas, bolsas, etiquetas_pol
    )


def criterios_topicos(lectura, claves_nino, resumen, eleccion, estable, elegida):
    metodo, k = eleccion
    r = resumen[eleccion]
    errores = sum(bool(f["error"]) for f in lectura)
    cubiertas = {c for c in claves_nino if c in {(f["medio"], f["id"]) for f in lectura}}
    categorias = sorted({categoria(t) for t in elegida["tops"] if t} - {""})
    return [
        criterio(PRUEBA_T, "notas leídas", len(lectura) - errores, len(claves_nino), True,
                 f"con error o sin texto {errores}; sin leer {len(claves_nino) - len(cubiertas)}"),
        *[criterio(PRUEBA_T, f"{m} k={kk}", f"Jaccard {v['estable']:.3f} · c_v {v['cv']:.4f}", "", True,
                   f"diversidad {v['diversidad']:.3f}; vacíos {v['vacios']}") for (m, kk), v in resumen.items()],
        criterio(PRUEBA_T, "T1: estabilidad del elegido", round(r["estable"], 4), f">= {JACCARD_MINIMO}", estable,
                 "" if estable else "ninguno pasa: se elige el más estable y se declara inestable"),
        criterio(PRUEBA_T, "T2: elegido", f"{metodo} k={k}", f"mayor c_v; empate < {EMPATE_CV}: menos tópicos", True,
                 f"c_v {r['cv']:.4f}; semilla {elegida['semilla']}"),
        criterio(PRUEBA_T, "categorías oficiales en las palabras (informativo)", len(categorias), len(CATEGORIAS),
                 True, ", ".join(categorias)),
        criterio(PRUEBA_T, "diversidad del elegido (informativo)", round(r["diversidad"], 4), "", True),
    ]  # fmt: skip


def criterios_polaridad(validas, bolsas, etiquetas_pol):
    truncados = sum(int(f["pol_truncados"] or 0) for f in validas)
    tramos = sum(int(f["pol_tramos"] or 0) for f in validas)
    en_muestra = [bool(f.get("zs_tramos")) for f in validas]
    etiquetas_zs = [etiqueta(probas_de(f, "zs")) for f in validas]
    a = [etiquetas_pol[i] for i, m in enumerate(en_muestra) if m]
    b = [etiquetas_zs[i] for i, m in enumerate(en_muestra) if m]
    k = kappa(a, b) if a else float("nan")
    pasa = len(a) > 0 and k >= KAPPA_MINIMO
    dist = collections.Counter(etiquetas_pol)
    filas = [
        criterio(PRUEBA_P, "P1: tramos truncados", truncados, "0", truncados == 0, f"de {tramos} tramos"),
        criterio(PRUEBA_P, "P2: kappa pysentimiento vs zero-shot", round(k, 4), f">= {KAPPA_MINIMO}", pasa,
                 f"n {len(a)}; pysentimiento {dict(collections.Counter(a))}; zero-shot {dict(collections.Counter(b))}"
                 + ("" if pasa else "; la polaridad queda solo descriptiva")),
        criterio(PRUEBA_P, "distribución en el corpus (informativo)", dict(dist), "", True),
    ]  # fmt: skip
    d = destilado(bolsas, etiquetas_pol, en_muestra, etiquetas_zs)
    if d:
        filas.append(criterio(PRUEBA_P, "destilado TF-IDF + LR (informativo)", f"κ vs pysentimiento {d[0]:.3f}", "",
                              True, f"κ vs zero-shot {d[1]:.3f}"))  # fmt: skip
    return filas


# ---------------------------------------------------------------- principal


@exclusivo("radar.nlp.topicos")
def _leer_exclusivo(parar, limite):
    with sin_suspension():
        return leer(parar, limite)


def main(argv=None):
    ap = argparse.ArgumentParser(description="Tópicos y polaridad de las notas sobre El Niño.")
    ap.add_argument("paso", choices=("muestra", "leer", "ajustar"))
    ap.add_argument("--limite", type=int, help="con leer: como máximo N notas por medio (ensayo corto)")
    args = ap.parse_args(argv)
    registro = configurar(f"nlp-topicos-{args.paso}")
    inicio, parar = ahora(), threading.Event()
    config.DIR_NLP.mkdir(parents=True, exist_ok=True)
    try:
        if args.paso == "muestra":
            filas = elegir_muestra()
        elif args.paso == "leer":
            filas = _leer_exclusivo(parar, args.limite)
        else:
            with sin_suspension():
                filas = ajustar()
    except KeyboardInterrupt:
        parar.set()
        log.info(f"Cortado: lo leído quedó en {ARCHIVO}; al relanzar sigue desde ahí.")
        return 1
    if isinstance(filas, int):
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
