"""Comparación de los candidatos de embedding del mapa de alternativas (docs/nlp/embeddings.md, plan del 2-nov).

Uso: python -m radar.nlp.candidatos tiempo             # A: tiempo por consulta, rendimiento y memoria (sin red)
     python -m radar.nlp.candidatos medir NOMBRE       # proceso hijo de A: imprime la medida de un candidato
     python -m radar.nlp.candidatos leer --pasada N    # B: pide páginas; lee los cuerpos en memoria y guarda solo los
                                                       # puntajes de la pasada; se puede cortar y relanzar
     python -m radar.nlp.candidatos criterios          # B: sin red, con las pasadas que haya
"""

import argparse
import collections
import json
import logging
import os
import statistics
import subprocess
import sys
import threading
import time

import numpy as np

from radar import config
from radar.comun.archivos import leer_csv
from radar.comun.candado import exclusivo
from radar.comun.energia import sin_suspension
from radar.comun.registro import configurar, describir
from radar.comun.texto import ahora
from radar.nlp import embeddings, esquemas, tfidf
from radar.noticias.viabilidad import criterio, guardar, reporte

log = logging.getLogger(__name__)

PRUEBA_A = "Candidatos A: tiempo y memoria"
ESTRATO_NINO = tfidf.ESTRATO_NINO
# (prefijo de la nota, prefijo del párrafo oficial), fijados antes de correr
QWEN = "Instruct: Given a news article, retrieve the official bulletin paragraph about the same topic\nQuery:"
PREFIJOS = {"e5-small": ("query: ", "query: "), "e5-base": ("query: ", "query: "), "arctic-l": ("query: ", ""),
            "qwen3": (QWEN, "")}  # fmt: skip
LARGO_MAXIMO = 512  # tokens: el de cada modelo, con este tope
CONSULTA_MAXIMA_S = 2.0  # A1
MEMORIA_MAXIMA_GB = 6.0  # A3: el embedding junto al NLI en float32 (2,7 GB), Streamlit y el sistema en 16 GB
CONSULTAS = 20
TRAMOS_RENDIMIENTO, TOKENS_TRAMO = 32, 500
TRAMOS_B = 2 * 6400  # tramos de 512 tokens de una pasada de B (con y sin términos); e5 tuvo ~2 por nota en 3.190


def prefijos(nombre):
    return PREFIJOS.get(nombre, ("", ""))


def cargar(nombre):
    """El candidato con sentence-transformers (cada uno con su pooling), siempre en float32 (CLAUDE.md): granite y
    Qwen3 vienen guardados en bfloat16, y transformers los cargaría así, mucho más lento en CPU."""
    import torch
    from sentence_transformers import SentenceTransformer

    os.environ.setdefault("HF_HUB_OFFLINE", "1")
    modelo = SentenceTransformer(
        config.CANDIDATOS_EMBEDDING[nombre], device="cpu", model_kwargs={"dtype": torch.float32}
    )
    modelo.max_seq_length = min(modelo.max_seq_length or LARGO_MAXIMO, LARGO_MAXIMO)
    return modelo


def tramos_largos(modelo, textos, n=TRAMOS_RENDIMIENTO, tokens=TOKENS_TRAMO):
    """n tramos de unos `tokens` tokens hechos con texto oficial, para medir el rendimiento con cuerpos."""
    ids = modelo.tokenizer(" ".join(textos), add_special_tokens=False)["input_ids"]
    return [modelo.tokenizer.decode(ids[i * tokens : (i + 1) * tokens]) for i in range(n)]


def medir(nombre):
    """Lo que hace la app con una consulta, más el rendimiento offline y el pico de memoria."""
    from radar.nlp.viabilidad import pico_memoria_gb

    inicio = time.perf_counter()
    modelo = cargar(nombre)
    carga = time.perf_counter() - inicio
    pre_nota, pre_oficial = prefijos(nombre)
    parrafos = [p["texto"] for p in leer_csv(config.DIR_OFICIAL / "parrafos.csv")]
    inicio = time.perf_counter()
    oficiales = modelo.encode([pre_oficial + t for t in parrafos], normalize_embeddings=True, batch_size=16)
    tiempo_parrafos = time.perf_counter() - inicio
    notas = sorted(
        (n for n in leer_csv(config.DIR_NOTICIAS / "notas.csv") if n["sobre_nino"] == "1"),
        key=lambda n: (n["medio"], n["id"]),
    )[:CONSULTAS]
    tiempos = []
    for n in notas:
        inicio = time.perf_counter()
        v = modelo.encode([pre_nota + f"{n['titular']}\n{n['resumen']}"], normalize_embeddings=True)
        int((oficiales @ v[0]).argmax())
        tiempos.append(time.perf_counter() - inicio)
    largos = tramos_largos(modelo, parrafos)
    inicio = time.perf_counter()
    modelo.encode([pre_nota + t for t in largos], normalize_embeddings=True, batch_size=16)
    rendimiento = len(largos) / (time.perf_counter() - inicio)
    pico, estable = pico_memoria_gb()
    return {
        "carga_s": round(carga, 1), "parrafos_s": round(tiempo_parrafos, 1),
        "consulta_s": round(statistics.median(tiempos), 3), "primera_s": round(tiempos[0], 3),
        "tramos_por_s": round(rendimiento, 2), "pico_gb": round(pico, 2),
        "estable_gb": round(estable, 2), "tokens_maximos": modelo.max_seq_length,
    }  # fmt: skip


def criterio_a(nombre, medida):
    horas = TRAMOS_B / medida["tramos_por_s"] / 3600
    pasa = medida["consulta_s"] <= CONSULTA_MAXIMA_S and medida["pico_gb"] <= MEMORIA_MAXIMA_GB
    detalle = (
        f"consulta {medida['consulta_s']} s (la primera {medida['primera_s']}); memoria {medida['pico_gb']} GB; "
        f"{medida['tramos_por_s']} tramos de {TOKENS_TRAMO} tokens/s → B ~{horas:.1f} h; carga {medida['carga_s']} s; "
        f"865 párrafos {medida['parrafos_s']} s; largo {medida['tokens_maximos']}"
    )
    umbral = f"≤ {CONSULTA_MAXIMA_S} s y ≤ {MEMORIA_MAXIMA_GB} GB"
    return criterio(PRUEBA_A, nombre, medida["consulta_s"], umbral, pasa, detalle)


def prueba_tiempo():
    """Un proceso por candidato, para que la memoria de uno no se sume a la de otro."""
    filas = []
    for nombre in config.CANDIDATOS_EMBEDDING:
        orden = [sys.executable, "-m", "radar.nlp.candidatos", "medir", nombre]
        salida = subprocess.run(orden, capture_output=True, text=True, encoding="utf-8", cwd=config.RAIZ)
        lineas = [x for x in salida.stdout.splitlines() if x.startswith("{")]
        if salida.returncode or not lineas:
            log.warning(f"{nombre}: falló (código {salida.returncode}); {salida.stderr[-300:]}")
            filas.append(criterio(PRUEBA_A, nombre, "falló", "", False, salida.stderr[-200:]))
            continue
        filas.append(criterio_a(nombre, json.loads(lineas[-1])))
        log.info(f"  {nombre}: {filas[-1]['detalle']}")
    return filas


# ---------------------------------------------------------------- B: bi-encoders en cuerpos

PRUEBA_B = "Candidatos B: bi-encoders en cuerpos"
INFO_B = "Candidatos B (informativo)"
# Pasadas según la memoria: los modelos de una pasada se cargan juntos (el cuerpo no puede guardarse entre pasadas)
PASADAS = {
    1: ("minilm", "e5-small", "e5-base", "granite-107m", "granite-278m", "mpnet", "beto-es"),
    2: ("arctic-l", "bge-m3"),
    3: ("qwen3",),
}
MARGEN_REEMPLAZO = 0.02  # en B1 y B2, sin solape de los IC del 95 %
REFERENCIA_1NOV = {"minilm": 0.9129, "e5-small": 0.9122}  # E4 del 1-nov: control del instrumento
TOLERANCIA_REFERENCIA = 0.005


def archivo_pasada(pasada):
    return config.DIR_NLP / f"candidatos-p{pasada}.csv"


class Candidato(embeddings.Modelo):
    """Un lado (la nota o el párrafo oficial) de un candidato de sentence-transformers, con la interfaz de
    embeddings.Modelo para partir el texto en tramos sin truncar."""

    def __init__(self, nombre, st, prefijo):
        self.nombre, self.repo, self.prefijo = nombre, config.CANDIDATOS_EMBEDDING[nombre], prefijo
        self.st, self.tok, self.largo = st, st.tokenizer, st.max_seq_length
        especiales = len(self.tok("", add_special_tokens=True)["input_ids"])
        prefijo_tokens = self.contar([prefijo])[0] if prefijo else 0
        self.maximo = self.largo - especiales - prefijo_tokens - embeddings.MARGEN_TOKENS

    def embeber(self, textos, lote=16):
        if not textos:
            return np.zeros((0, 1), dtype=np.float32)
        return self.st.encode([self.prefijo + t for t in textos], normalize_embeddings=True, batch_size=lote)


def vigentes(parrafos, fecha):
    """Máscara de los párrafos vigentes en la fecha (aaaa-mm-dd)."""
    return np.array([p["vigente_desde"] <= fecha <= (p["vigente_hasta"] or "9999-12-31") for p in parrafos])


def maximos_por_parrafo(mios, oficial, variante):
    """Coseno máximo de los tramos de la nota con los tramos de cada párrafo oficial."""
    tramos_oficiales, de, _, _ = oficial.por[variante]
    por_tramo = (mios @ tramos_oficiales.T).max(0)
    salida = np.full(len(oficial.ids), -1.0)
    np.maximum.at(salida, de, por_tramo)
    return salida


def puntajes_candidato(modelo, enfen, todo, parrafos_enfen, texto, fecha):
    """({puntaje: valor}, tramos, truncados) de un texto frente al ENFEN, a lo vigente en la fecha y a los 865."""
    por_variante = {v: modelo.tramos(f(texto)) for v, f in embeddings.VARIANTES.items()}
    todos = [t for ts in por_variante.values() for t in ts]
    vectores, fila, i = modelo.embeber(todos), {}, 0
    mascara = vigentes(parrafos_enfen, fecha)
    for v, ts in por_variante.items():
        mios = vectores[i : i + len(ts)]
        i += len(ts)
        if not ts:
            continue
        maximos = maximos_por_parrafo(mios, enfen, v)
        fila[f"{v}_max"] = round(float(maximos.max()), 4)
        fila[f"todo_{v}_max"] = round(float((mios @ todo.por[v][0].T).max()), 4)
        if mascara.any():
            fila[f"vig_{v}_max"] = round(float(maximos[mascara].max()), 4)
        if v == "con":
            fila["con_parrafo"] = enfen.ids[int(maximos.argmax())]
            if mascara.any():
                fila["vig_con_parrafo"] = enfen.ids[int(np.where(mascara, maximos, -2).argmax())]
    return fila, len(por_variante["con"]), modelo.truncados(todos)


def fila_candidatos(nota, estrato, campos, cargados, parrafos_enfen, positivos):
    """Lo que se guarda de una nota leída: solo puntajes y controles. El cuerpo se descarta aquí."""
    fila = {"medio": nota["medio"], "id": nota["id"], "estrato": estrato}
    fila["positivo"] = (nota["medio"], nota["id"]) in positivos
    if not isinstance(campos, dict):
        return {**fila, "error": describir(campos)[:200]}
    fila |= {"sha1_igual": tfidf.sha1_de(nota, campos)[1], "error": "sin texto" if campos["sin_texto"] else ""}
    if campos["sin_texto"]:
        return fila
    texto, _ = tfidf.texto_de(campos)
    fecha = nota["fecha_publicacion"][:10]
    for nombre, (modelo, enfen, todo) in cargados.items():
        p, n, truncados = puntajes_candidato(modelo, enfen, todo, parrafos_enfen, texto, fecha)
        t, _, truncados_titular = puntajes_candidato(modelo, enfen, todo, parrafos_enfen, nota["titular"], fecha)
        fila |= {f"{nombre}_{k}": x for k, x in p.items()}
        fila |= {f"{nombre}_tit_{k}": t[k] for k in ("con_max", "sin_max", "vig_con_max") if k in t}
        fila |= {f"{nombre}_tramos": n, f"{nombre}_truncados": truncados + truncados_titular}
    return fila


def leer(pasada, parar, limite=None):
    notas = leer_csv(config.DIR_NOTICIAS / "notas.csv")
    todo = embeddings.corpus(notas, leer_csv(config.DIR_NOTICIAS / "control_negativo.csv"))
    positivos, parrafos_enfen = embeddings.positivas(notas), embeddings.parrafos_enfen()
    parrafos = leer_csv(config.DIR_OFICIAL / "parrafos.csv")
    cargados = {}
    for nombre in PASADAS[pasada]:
        st = cargar(nombre)
        pre_nota, pre_oficial = prefijos(nombre)
        oficial = Candidato(nombre, st, pre_oficial)
        enfen, todos = embeddings.Oficial(oficial, parrafos_enfen), embeddings.Oficial(oficial, parrafos)
        if enfen.truncados or todos.truncados:  # E2: ningún tramo truncado
            raise ValueError(f"{nombre}: {enfen.truncados + todos.truncados} tramos oficiales truncados")
        cargados[nombre] = (Candidato(nombre, st, pre_nota), enfen, todos)
        log.info(f"  {nombre} listo")

    def fila_de(nota, estrato, campos):
        return fila_candidatos(nota, estrato, campos, cargados, parrafos_enfen, positivos)

    columnas = esquemas.columnas_candidatos(PASADAS[pasada])
    return tfidf.leer_cuerpos(todo, archivo_pasada(pasada), columnas, fila_de, parar, limite)


def filas_unidas():
    """{(medio, id): fila} con las columnas de todas las pasadas leídas, y los modelos presentes."""
    unidas, modelos = {}, []
    for pasada, nombres in PASADAS.items():
        if not archivo_pasada(pasada).exists():
            continue
        modelos += nombres
        for clave, f in tfidf.leidos(archivo_pasada(pasada)).items():
            previa = unidas.setdefault(clave, {})
            previa |= {k: v for k, v in f.items() if v != "" or k not in previa}
    return unidas, modelos


def auc_de(filas, clave, positivos, negativos):
    return embeddings.auc(embeddings.valores(filas, clave, positivos), embeddings.valores(filas, clave, negativos))


def citado(filas, modelo, notas, doc):
    """B4: {(medio, id): acierta} en las notas sobre El Niño que citan un comunicado."""
    salida = {}
    for f in filas:
        citados = {c.split(":")[0] for c in notas[(f["medio"], f["id"])]["comunicados"].split("|") if c}
        if f["estrato"] == ESTRATO_NINO and citados and f.get(f"{modelo}_con_parrafo"):
            salida[(f["medio"], f["id"])] = doc[f[f"{modelo}_con_parrafo"]] in citados
    return salida


def vigencia(filas, modelo, notas, parrafos):
    """B5: (exacto, a ±1 comunicado) de notas sobre El Niño cuyo párrafo más parecido es de un comunicado vigente."""
    doc = {p["id"]: p["doc_id"] for p in parrafos}
    orden = sorted(set(doc.values()))
    periodo = {}
    for p in parrafos:
        periodo.setdefault(p["doc_id"], (p["vigente_desde"], p["vigente_hasta"] or "9999-12-31"))
    exacto = cerca = n = 0
    for f in filas:
        if f["estrato"] != ESTRATO_NINO or not f.get(f"{modelo}_con_parrafo"):
            continue
        fecha = notas[(f["medio"], f["id"])]["fecha_publicacion"][:10]
        vigente = [orden.index(d) for d, (desde, hasta) in periodo.items() if desde <= fecha <= hasta]
        elegido = orden.index(doc[f[f"{modelo}_con_parrafo"]])
        n += 1
        exacto += elegido in vigente
        cerca += any(abs(elegido - v) <= 1 for v in vigente)
    return (round(exacto / n, 4), round(cerca / n, 4)) if n else (None, None)


def concentracion(filas, modelo, parrafos):
    """B6: (párrafo más repetido, tipo definicion) como proporción de las notas sobre El Niño."""
    tipo = {p["id"]: p["tipo"] for p in parrafos}
    clave = f"{modelo}_con_parrafo"
    elegidos = [f[clave] for f in filas if f["estrato"] == ESTRATO_NINO and f.get(clave)]
    if not elegidos:
        return None, None
    repetido = collections.Counter(elegidos).most_common(1)[0][1]
    return round(repetido / len(elegidos), 4), round(sum(tipo[e] == "definicion" for e in elegidos) / len(elegidos), 4)


def mcnemar(aciertos_a, aciertos_b):
    """p exacto (binomial) de McNemar entre dos modelos en las mismas notas."""
    from scipy.stats import binomtest

    claves = aciertos_a.keys() & aciertos_b.keys()
    solo_a = sum(aciertos_a[k] and not aciertos_b[k] for k in claves)
    solo_b = sum(aciertos_b[k] and not aciertos_a[k] for k in claves)
    return 1.0 if not solo_a + solo_b else round(binomtest(min(solo_a, solo_b), solo_a + solo_b, 0.5).pvalue, 4)


def semaforos(filas, modelo):
    """B3: E3 en cuerpos y titulares, con todo el ENFEN y con lo vigente."""
    grupos = (("cuerpos", modelo), ("cuerpos vigentes", f"{modelo}_vig"), ("titulares", f"{modelo}_tit"),
              ("titulares vigentes", f"{modelo}_tit_vig"))  # fmt: skip
    return [embeddings.semaforo(filas, clave, tipo, INFO_B) for tipo, clave in grupos]


def elegir(medidas, consulta):
    """Mayor B1 entre los que pasan B3. Los que el líder no supera por el margen en B1 y en B2 (sin solape de IC)
    empatan con él, y entre ellos gana el más rápido en A1."""
    pasan = [m for m, x in medidas.items() if x["b3"] and x["b1"][0] is not None and x["b2"][0] is not None]
    if not pasan:
        return None, []
    lider = max(pasan, key=lambda m: medidas[m]["b1"][0])

    def supera(a, b, clave):
        (va, ica), (vb, icb) = medidas[a][clave], medidas[b][clave]
        return va - vb >= MARGEN_REEMPLAZO and ica[0] > icb[1]

    empatados = [m for m in pasan if m == lider or not (supera(lider, m, "b1") and supera(lider, m, "b2"))]
    return min(empatados, key=lambda m: consulta.get(m, float("inf"))), empatados


def consultas_a():
    ruta = config.DIR_NLP / "validacion.csv"
    filas = leer_csv(ruta) if ruta.exists() else []
    return {f["criterio"]: float(f["valor"]) for f in filas if f["prueba"] == PRUEBA_A and f["valor"] != "falló"}


def criterios():
    unidas, modelos = filas_unidas()
    notas = {(n["medio"], n["id"]): n for n in leer_csv(config.DIR_NOTICIAS / "notas.csv")}
    parrafos_enfen = embeddings.parrafos_enfen()
    doc = {p["id"]: p["doc_id"] for p in parrafos_enfen}
    cuerpos = [f for f in unidas.values() if not f["error"]]
    faltan = [str(p) for p in PASADAS if not archivo_pasada(p).exists()]
    nino, otros = embeddings.es(ESTRATO_NINO), embeddings.es(embeddings.ESTRATO_NEGATIVO)
    medidas, informativos, aciertos = {}, [], {}
    for m in modelos:
        b3 = semaforos(cuerpos, m)
        medidas[m] = {
            "b1": auc_de(cuerpos, f"{m}_sin_max", nino, otros),
            "b2": auc_de(cuerpos, f"{m}_vig_sin_max", nino, otros),
            "b3": all(f["pasa"] for f in b3),
        }
        aciertos[m] = citado(cuerpos, m, notas, doc)
        exacto, cerca = vigencia(cuerpos, m, notas, parrafos_enfen)
        repetido, definicion = concentracion(cuerpos, m, parrafos_enfen)
        b7 = auc_de(cuerpos, f"{m}_todo_sin_max", nino, otros)
        for nombre, (valor, ic) in (("B1 E4 cuerpos, todo el ENFEN", medidas[m]["b1"]),
                                    ("B2 E4 cuerpos, ENFEN vigente", medidas[m]["b2"]),
                                    ("B7 E4 cuerpos, 865 párrafos", b7)):  # fmt: skip
            informativos.append(criterio(INFO_B, f"{nombre} ({m})", valor, "", True, f"IC95 {ic[0]}-{ic[1]}"))
        informativos += [*b3, embeddings.semaforo(cuerpos, f"{m}_todo", "cuerpos, 865 párrafos", INFO_B)]
        informativos += [
            criterio(
                INFO_B, f"B4 comunicado citado ({m})", f"{sum(aciertos[m].values())}/{len(aciertos[m])}", "", True
            ),
            criterio(INFO_B, f"B5 vigente exacto / ±1 ({m})", f"{exacto} / {cerca}", "", True),
            criterio(INFO_B, f"B6 párrafo más repetido / definicion ({m})", f"{repetido} / {definicion}", "", True),
        ]
    consulta = consultas_a()
    elegido, empatados = elegir(medidas, consulta)
    truncados = sum(int(f.get(f"{m}_truncados") or 0) for f in cuerpos for m in modelos)
    provisional = f" (provisional: faltan las pasadas {', '.join(faltan)})" if faltan else ""
    resultado = [criterio(PRUEBA_B, "tramos truncados", truncados, 0, not truncados)]
    resultado += [
        criterio(
            PRUEBA_B,
            f"control del instrumento: B1 de {m} igual al E4 del 1-nov",
            medidas[m]["b1"][0],
            f"{ref} ± {TOLERANCIA_REFERENCIA}",
            medidas[m]["b1"][0] is not None and abs(medidas[m]["b1"][0] - ref) <= TOLERANCIA_REFERENCIA,
        )
        for m, ref in REFERENCIA_1NOV.items()
        if m in medidas
    ]
    resultado.append(
        criterio(
            PRUEBA_B,
            "modelo elegido" + provisional,
            elegido or "ninguno",
            "pasa B3; regla de reemplazo",
            elegido is not None,
            f"empatados con el líder {empatados}; A1 {({m: consulta.get(m) for m in empatados})}; "
            f"B1 {({m: x['b1'][0] for m, x in medidas.items()})}; B2 {({m: x['b2'][0] for m, x in medidas.items()})}",
        )
    )
    if elegido:
        informativos += [
            criterio(INFO_B, f"B4 McNemar frente a {elegido} ({m})", mcnemar(aciertos[elegido], aciertos[m]), "", True)
            for m in modelos
            if m != elegido
        ]
    return resultado + informativos


@exclusivo("radar.nlp.candidatos")
def _leer_exclusivo(pasada, parar, limite):
    with sin_suspension():
        return leer(pasada, parar, limite)


def main(argv=None):
    ap = argparse.ArgumentParser(description="Comparación de candidatos de embedding.")
    ap.add_argument("paso", choices=("tiempo", "medir", "leer", "criterios"))
    ap.add_argument("nombre", nargs="?", choices=tuple(config.CANDIDATOS_EMBEDDING), help="solo con medir")
    ap.add_argument("--pasada", type=int, choices=tuple(PASADAS), help="con leer")
    ap.add_argument("--limite", type=int, help="con leer: como máximo N notas por medio (ensayo corto)")
    args = ap.parse_args(argv)
    if args.paso == "medir":  # proceso hijo: solo imprime la medida
        print(json.dumps(medir(args.nombre)))
        return 0
    if args.paso == "leer" and not args.pasada:
        ap.error("leer necesita --pasada")
    registro = configurar(f"nlp-candidatos-{args.paso}" + (f"-p{args.pasada}" if args.pasada else ""))
    inicio, parar = ahora(), threading.Event()
    config.DIR_NLP.mkdir(parents=True, exist_ok=True)
    try:
        if args.paso == "leer":
            filas = _leer_exclusivo(args.pasada, parar, args.limite)
        else:
            filas = prueba_tiempo() if args.paso == "tiempo" else criterios()
    except KeyboardInterrupt:
        parar.set()
        log.info("Cortado: lo leído quedó guardado; al relanzar sigue desde ahí.")
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
