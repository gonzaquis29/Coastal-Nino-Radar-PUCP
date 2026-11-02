"""TF-IDF de las notas sobre El Niño, del control negativo y de los párrafos oficiales (docs/nlp/tfidf.md).

Uso: python -m radar.nlp.tfidf leer       # pide páginas: vuelve a leer los cuerpos en memoria y guarda solo la bolsa
                                          # de lemas de cada nota en conteos.csv; se puede cortar y relanzar
     python -m radar.nlp.tfidf vectores   # sin red: matrices de conteos y TF-IDF, y criterios T1, T2, T4 y T5
Requiere pip install -e ".[nlp]" y es_core_news_sm.
"""

import argparse
import collections
import concurrent.futures
import logging
import queue
import sys
import threading

from radar import config
from radar.comun.archivos import anexar_csv, escribir_csv, leer_csv, reparar_csv
from radar.comun.candado import exclusivo
from radar.comun.energia import sin_suspension
from radar.comun.http import Cliente, Rechazado
from radar.comun.registro import configurar, describir
from radar.comun.texto import ahora, sha1_corto
from radar.nlp import esquemas, preproceso
from radar.noticias.medios import DETENER, MEDIOS
from radar.noticias.nota import proporcion_en_cuerpo
from radar.noticias.viabilidad import _si, criterio, guardar, reporte

log = logging.getLogger(__name__)

PRUEBA = "Preprocesamiento y TF-IDF"
ESTRATO_NINO = "sobre_nino"
ESTRATO_NEGATIVO = "otros_temas"  # decide T4; "cercano" es informativo
LEIDAS_MINIMO = 0.98  # T1
SHA1_IGUAL_MINIMO = 0.95  # T1
TERMINOS_IGUALES_MINIMO = 0.99  # T2
AUC_MINIMO = 0.90  # T4, sin los términos del fenómeno
TOP_TERMINOS = 50  # T5
RESUMEN_EN_CUERPO = 0.9  # con menos, el resumen se agrega al texto (no está repetido en el cuerpo)
MIN_DF = 3  # el término aparece en al menos 3 documentos del ajuste
MAX_DF = 0.9
# Fuera del vocabulario para T4: nombran el fenómeno, que es justo lo que define "sobre El Niño"
TERMINOS_DE_LA_ETIQUETA = (*preproceso.TERMINOS_FENOMENO, "enfen", "fen", "niño", "niña", "costero")
LOTE_LECTURA = 100  # filas por medio que se mandan a descargar de una vez (El Tiempo pide de a 100 en su API)
ARCHIVO_CONTEOS = "conteos.csv"


# ---------------------------------------------------------------- corpus


def corpus(notas, control):
    """[(nota, estrato)]: las notas sobre El Niño y las del control negativo (que no lo son)."""
    por_clave = {(n["medio"], n["id"]): n for n in notas}
    salida = [(n, ESTRATO_NINO) for n in notas if _si(n["sobre_nino"])]
    salida += [(por_clave[(c["medio"], c["id"])], c["estrato"]) for c in control if (c["medio"], c["id"]) in por_clave]
    return salida


def leidos(ruta):
    """{(medio, id): fila} con la última fila de cada nota."""
    return {(f["medio"], f["id"]): f for f in leer_csv(ruta)}


def texto_de(campos):
    """Titular, resumen si no está ya en el cuerpo, y cuerpo."""
    resumen, cuerpo = campos["resumen"], campos["cuerpo"]
    usa_resumen = bool(resumen) and (proporcion_en_cuerpo(resumen, cuerpo) or 0) < RESUMEN_EN_CUERPO
    return "\n".join([campos["titular"], *([resumen] if usa_resumen else []), cuerpo]), usa_resumen


def fila_conteo(nota, estrato, campos):
    """Lo que se guarda de una nota leída: la bolsa de lemas y los controles. El cuerpo se descarta aquí."""
    if not isinstance(campos, dict):
        return {"medio": nota["medio"], "id": nota["id"], "estrato": estrato, "error": describir(campos)[:200]}
    texto, usa_resumen = texto_de(campos)
    marcado, menciones = preproceso.marcar_fenomeno(texto)
    bolsa = preproceso.bolsas([marcado])[0]
    sha1 = sha1_corto(campos["cuerpo"])
    return {
        "medio": nota["medio"], "id": nota["id"], "estrato": estrato, "sha1_cuerpo": sha1,
        "sha1_igual": sha1 == nota["sha1_cuerpo"], "n_palabras": campos["n_palabras"], "usa_resumen": usa_resumen,
        "menciones": menciones, "terminos_fenomeno": sum(bolsa[t] for t in preproceso.TERMINOS_FENOMENO),
        "error": "" if not campos["sin_texto"] else "sin texto", "lemas": preproceso.a_celda(bolsa),
    }  # fmt: skip


def _descargar_medio(nombre, pendientes, cola, parar):
    """Descarga las notas de un medio y las pone en la cola; un bloqueo detiene solo a ese medio."""
    medio = MEDIOS[nombre](Cliente(hosts_permitidos={config.HOSTS_MEDIOS[nombre]}), parar)
    try:
        for i in range(0, len(pendientes), LOTE_LECTURA):
            if parar.is_set():
                return
            lote = pendientes[i : i + LOTE_LECTURA]
            filas = [medio.lista.get(n["id"]) or {**n, "titulo": ""} for n, _ in lote]
            estratos = {n["id"]: (n, e) for n, e in lote}
            try:
                for fila, resultado in medio.descargar(filas):
                    cola.put((*estratos[fila["id"]], resultado))
            except Rechazado as e:
                for n, e_ in lote:
                    cola.put((n, e_, e))
    except DETENER as e:
        log.warning(f"{nombre}: detenido ({describir(e)})")
    finally:
        cola.put((nombre, None, None))


def leer(parar, limite=None):
    ruta = config.DIR_NLP / ARCHIVO_CONTEOS
    reparar_csv(ruta, esquemas.CONTEOS)
    hechos = {k for k, f in leidos(ruta).items() if not f["error"] or f["error"] == "sin texto"}
    todo = corpus(leer_csv(config.DIR_NOTICIAS / "notas.csv"), leer_csv(config.DIR_NOTICIAS / "control_negativo.csv"))
    por_medio = collections.defaultdict(list)
    for nota, estrato in todo:
        if (nota["medio"], nota["id"]) not in hechos:
            por_medio[nota["medio"]].append((nota, estrato))
    if limite:
        por_medio = {m: p[:limite] for m, p in por_medio.items()}
    log.info(f"Corpus {len(todo)} notas · ya leídas {len(hechos)} · por leer {sum(map(len, por_medio.values()))}")
    preproceso.modelo()
    cola, abiertos, conteo = (
        queue.Queue(),
        len(por_medio),
        collections.Counter(),
    )  # sin tope: nadie se bloquea al cortar
    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, len(por_medio))) as hilos:
        for nombre, pendientes in por_medio.items():
            hilos.submit(_descargar_medio, nombre, pendientes, cola, parar)
        while abiertos:
            nota, estrato, resultado = cola.get()
            if estrato is None:
                abiertos -= 1
                continue
            fila = fila_conteo(nota, estrato, resultado)
            anexar_csv(ruta, esquemas.CONTEOS, [fila])
            conteo["con error" if fila["error"] else "leídas"] += 1
            if sum(conteo.values()) % 200 == 0:
                log.info(f"  {dict(conteo)}")
    log.info(f"Lectura: {dict(conteo)} · {ruta.relative_to(config.RAIZ)}")
    return []


# ---------------------------------------------------------------- vectores


def documentos(filas_conteo, parrafos):
    """Documentos con bolsa: notas leídas con texto y párrafos oficiales."""
    docs = [
        ({"tipo": "nota", "medio": f["medio"], "id": f["id"], "estrato": f["estrato"]}, preproceso.de_celda(f["lemas"]))
        for f in filas_conteo
        if not f["error"]
    ]
    bolsas = preproceso.bolsas([preproceso.marcar_fenomeno(p["texto"])[0] for p in parrafos])
    docs += [
        ({"tipo": "oficial", "medio": p["fuente"], "id": p["id"], "estrato": ""}, b)
        for p, b in zip(parrafos, bolsas, strict=True)
    ]
    return docs


def matrices(docs):
    """Conteos de todos los documentos y TF-IDF ajustado con las notas sobre El Niño y los párrafos oficiales."""
    from scipy import sparse
    from sklearn.feature_extraction.text import TfidfTransformer

    ajuste = [i for i, (d, _) in enumerate(docs) if d["tipo"] == "oficial" or d["estrato"] == ESTRATO_NINO]
    df = collections.Counter(t for i in ajuste for t in docs[i][1])
    vocabulario = sorted(t for t, n in df.items() if n >= MIN_DF and n / len(ajuste) <= MAX_DF)
    columna = {t: j for j, t in enumerate(vocabulario)}
    filas, columnas, valores = [], [], []
    for i, (_, b) in enumerate(docs):
        for t, n in b.items():
            if t in columna:
                filas.append(i), columnas.append(columna[t]), valores.append(n)
    conteos = sparse.csr_matrix((valores, (filas, columnas)), shape=(len(docs), len(vocabulario)), dtype=float)
    modelo = TfidfTransformer(sublinear_tf=True).fit(conteos[ajuste])
    return conteos, modelo.transform(conteos), vocabulario, df


def _sin_terminos(x, vocabulario, quitar):
    from sklearn.preprocessing import normalize

    x = x.tolil(copy=True)
    for j in [j for j, t in enumerate(vocabulario) if t in quitar]:
        x[:, j] = 0
    return normalize(x.tocsr())


def similitud_maxima(x, docs, de_quien):
    """Coseno máximo de cada nota con los párrafos del ENFEN (las filas ya tienen norma 1)."""
    oficiales = [i for i, (d, _) in enumerate(docs) if d["tipo"] == "oficial" and d["medio"] == "enfen"]
    notas = [i for i, (d, _) in enumerate(docs) if d["tipo"] == "nota" and d["estrato"] in de_quien]
    sim = (x[notas] @ x[oficiales].T).max(axis=1).toarray().ravel()
    return [docs[i][0]["estrato"] for i in notas], sim


def auc(x, docs, negativo):
    from sklearn.metrics import roc_auc_score

    estratos, sim = similitud_maxima(x, docs, {ESTRATO_NINO, negativo})
    return round(float(roc_auc_score([e == ESTRATO_NINO for e in estratos], sim)), 4)


def criterios_lectura(todo, filas_conteo):
    n = len(todo)
    con_texto = [f for f in filas_conteo if not f["error"]]
    errores = collections.Counter(f["error"] for f in filas_conteo if f["error"])
    leidas = round(len(con_texto) / n, 4) if n else 0.0
    igual = round(sum(_si(f["sha1_igual"]) for f in con_texto) / len(con_texto), 4) if con_texto else 0.0
    iguales = sum(int(f["menciones"]) == int(f["terminos_fenomeno"]) for f in con_texto)
    t2 = round(iguales / len(con_texto), 4) if con_texto else 0.0
    sin_leer = n - len(filas_conteo)
    distinto = collections.Counter(f["medio"] for f in con_texto if not _si(f["sha1_igual"]))
    return [
        criterio(
            PRUEBA,
            "T1: notas leídas con texto",
            leidas,
            LEIDAS_MINIMO,
            leidas >= LEIDAS_MINIMO,
            f"{len(con_texto)}/{n}; sin leer {sin_leer}; errores {dict(errores)}",
        ),
        criterio(
            PRUEBA,
            "T1: cuerpo igual al de notas.csv (sha1)",
            igual,
            SHA1_IGUAL_MINIMO,
            igual >= SHA1_IGUAL_MINIMO,
            f"distinto por medio: {dict(distinto)}",
        ),
        criterio(
            PRUEBA,
            "T2: términos del fenómeno = menciones",
            t2,
            TERMINOS_IGUALES_MINIMO,
            t2 >= TERMINOS_IGUALES_MINIMO,
            f"{iguales}/{len(con_texto)}",
        ),
    ]


def top_por_medio(x, docs, vocabulario, k=TOP_TERMINOS):
    import numpy as np

    salida = {}
    for medio in MEDIOS:
        filas = [i for i, (d, _) in enumerate(docs) if d["medio"] == medio and d["estrato"] == ESTRATO_NINO]
        if filas:
            media = np.asarray(x[filas].mean(axis=0)).ravel()
            salida[medio] = [vocabulario[j] for j in media.argsort()[::-1][:k]]
    return salida


def criterios_vectores(x, docs, vocabulario):
    sin = _sin_terminos(x, vocabulario, set(TERMINOS_DE_LA_ETIQUETA))
    t4 = auc(sin, docs, ESTRATO_NEGATIVO)
    top = top_por_medio(x, docs, vocabulario)
    nombres = {m: sorted(set(t) & preproceso.NOMBRES_MEDIOS) for m, t in top.items()}
    hay = any(nombres.values())
    informativo = f"{PRUEBA} (informativo)"
    return [
        criterio(
            PRUEBA, "T4: AUC sin los términos del fenómeno (frente a otros temas)", t4, AUC_MINIMO, t4 >= AUC_MINIMO
        ),
        criterio(
            PRUEBA,
            f"T5: nombres de medios entre los {TOP_TERMINOS} términos de cada medio",
            int(hay),
            0,
            not hay,
            str({m: n for m, n in nombres.items() if n}),
        ),
        criterio(
            informativo, "AUC con todo el vocabulario (frente a otros temas)", auc(x, docs, ESTRATO_NEGATIVO), "", True
        ),
        criterio(
            informativo, "AUC sin los términos del fenómeno (frente a cercano)", auc(sin, docs, "cercano"), "", True
        ),
        criterio(informativo, "AUC con todo el vocabulario (frente a cercano)", auc(x, docs, "cercano"), "", True),
        criterio(
            informativo,
            "documentos y vocabulario",
            f"{x.shape[0]} × {x.shape[1]}",
            "",
            True,
            str(collections.Counter(d["estrato"] or d["medio"] for d, _ in docs)),
        ),
        *[criterio(informativo, f"términos de {m}", "", "", True, ", ".join(t[:25])) for m, t in top.items()],
    ]


def vectores():
    from scipy import sparse

    todo = corpus(leer_csv(config.DIR_NOTICIAS / "notas.csv"), leer_csv(config.DIR_NOTICIAS / "control_negativo.csv"))
    claves = {(n["medio"], n["id"]) for n, _ in todo}
    filas_conteo = [f for k, f in leidos(config.DIR_NLP / ARCHIVO_CONTEOS).items() if k in claves]
    docs = documentos(filas_conteo, leer_csv(config.DIR_OFICIAL / "parrafos.csv"))
    conteos, x, vocabulario, df = matrices(docs)
    sparse.save_npz(config.DIR_NLP / "conteos.npz", conteos.tocsr())
    sparse.save_npz(config.DIR_NLP / "tfidf.npz", x.tocsr())
    escribir_csv(
        config.DIR_NLP / "documentos.csv",
        esquemas.DOCUMENTOS,
        [{"fila": i, **d} for i, (d, _) in enumerate(docs)],
    )
    escribir_csv(
        config.DIR_NLP / "vocabulario.csv",
        esquemas.VOCABULARIO,
        [{"columna": j, "termino": t, "df": df[t]} for j, t in enumerate(vocabulario)],
    )
    return criterios_lectura(todo, filas_conteo) + criterios_vectores(x, docs, vocabulario)


# ---------------------------------------------------------------- principal


@exclusivo("radar.nlp.tfidf")
def _leer_exclusivo(parar, limite):
    with sin_suspension():
        return leer(parar, limite)


def main(argv=None):
    ap = argparse.ArgumentParser(description="Preprocesamiento y TF-IDF de las notas.")
    ap.add_argument("paso", choices=("leer", "vectores"))
    ap.add_argument("--limite", type=int, help="con leer: como máximo N notas por medio (ensayo corto)")
    args = ap.parse_args(argv)
    registro = configurar(f"nlp-tfidf-{args.paso}")
    inicio, parar = ahora(), threading.Event()
    config.DIR_NLP.mkdir(parents=True, exist_ok=True)
    try:
        filas = _leer_exclusivo(parar, args.limite) if args.paso == "leer" else vectores()
    except KeyboardInterrupt:
        parar.set()
        log.info("Cortado: lo leído quedó en conteos.csv; al relanzar sigue desde ahí.")
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
