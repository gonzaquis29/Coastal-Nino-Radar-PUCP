"""E: recuperador del agente, con preguntas por plantilla y filtro de fecha (docs/nlp/embeddings.md, 6-nov).

Uso: python -m radar.nlp.recuperador correr             # todos los candidatos, un proceso por cada uno
     python -m radar.nlp.recuperador puntuar NOMBRE     # proceso hijo: un candidato; se puede cortar y relanzar
     python -m radar.nlp.recuperador criterios          # decide con lo puntuado

Sin red de lectura de notas: solo usa los textos oficiales de data/oficial/.
"""

import argparse
import collections
import logging
import random
import re
import statistics
import subprocess
import sys
import time
from math import comb

import numpy as np

from radar import config
from radar.comun.archivos import anexar_csv, escribir_csv, leer_csv, reparar_csv
from radar.comun.energia import sin_suspension
from radar.comun.registro import configurar
from radar.comun.texto import ahora
from radar.nlp import candidatos, embeddings, esquemas, hibrido, preproceso, reranker
from radar.noticias.viabilidad import criterio, guardar, reporte

log = logging.getLogger(__name__)

PRUEBA_E = "Recuperador: preguntas por plantilla"
INFO_E = "Recuperador (informativo)"
BASE = "minilm"
K = 3  # el acierto que decide
KS_INFORMATIVOS = (1, 5, 10)
SOBRE_AZAR = 0.10
MEJORA = 0.05
RETROCESO = 0.05
ALFA = 0.05
CONSULTA_MAXIMA_S = 2.0
MEMORIA_MAXIMA_GB = 6.0
K_RRF = 60
LOTE = 16
FUSION, LEXICOS, CRUZADO = "rrf", ("tfidf", "bm25"), "mmarco"
CANDIDATOS = (*config.CANDIDATOS_EMBEDDING, *LEXICOS, FUSION, CRUZADO)
COMPARACIONES = len(CANDIDATOS) - 1
UMBRAL_P = ALFA / COMPARACIONES
GRUPOS = ("A", "B", "C")

QWEN_CONSULTA = "Instruct: Given a web search query, retrieve relevant passages that answer the query\nQuery:"
PREFIJOS = {  # (consulta, párrafo), fijados antes de correr
    "e5-small": ("query: ", "passage: "),
    "e5-base": ("query: ", "passage: "),
    "arctic-l": ("query: ", ""),
    "qwen3": (QWEN_CONSULTA, ""),
}
MESES = "enero febrero marzo abril mayo junio julio agosto septiembre octubre noviembre diciembre".split()
FECHA_EN_TEXTO = re.compile(r"(\d{1,2}) de (" + "|".join(MESES) + ")")
REGION_EN_PREGUNTA = {"costa_norte": "la costa norte", "costa_centro": "la costa centro"}
PLANTILLAS_A = {
    "pronostico": (
        "¿Cuál es el pronóstico del ENFEN para los próximos meses?",
        "¿Hasta cuándo se espera que dure El Niño costero según el ENFEN?",
        "¿Qué prevé el ENFEN sobre la evolución de las condiciones?",
    ),
    "impactos": (
        "¿Qué impactos se esperan según el ENFEN?",
        "¿Cómo afectará El Niño costero a las lluvias y a la población?",
        "¿Qué efectos anuncia el ENFEN en las regiones?",
    ),
    "pesca": (
        "¿Cómo afecta a la pesca y a la anchoveta según el ENFEN?",
        "¿Qué pasa con la anchoveta y los recursos del mar?",
        "¿Qué dice el ENFEN sobre la actividad pesquera?",
    ),
    "recomendacion": (
        "¿Qué recomienda el ENFEN a las autoridades?",
        "¿Qué medidas de prevención pide tomar el ENFEN?",
        "¿Qué deben hacer los tomadores de decisiones según el ENFEN?",
    ),
    "seguimiento": (
        "¿Qué muestra el monitoreo del ENFEN?",
        "¿Cómo está la temperatura del mar según el ENFEN?",
        "¿Qué condiciones observó el ENFEN en el mar?",
    ),
}
PLANTILLAS_B = (
    "¿Qué aviso del Senamhi hay por {tipo} en {region} el {dia}?",
    "¿Hay alerta por {tipo} en {region} para el {dia}?",
    "¿Qué advierte el Senamhi sobre {tipo} en {region} el {dia}?",
)
PLANTILLAS_C = (
    "¿Qué prevé el Senamhi por {tipo} el {dia}?",
    "¿Qué se espera el {dia} por {tipo} según el Senamhi?",
    "¿Cuál es el pronóstico de {tipo} para el {dia}?",
)


def dia_en_texto(fecha):
    anio, mes, dia = fecha.split("-")
    return f"{int(dia)} de {MESES[int(mes) - 1]}"


def vigente_en(parrafo, fecha):
    return parrafo["vigente_desde"] <= fecha <= (parrafo["vigente_hasta"] or "9999-12-31")


def fecha_del_parrafo(parrafo, inicio_aviso):
    """La fecha del párrafo diario de un aviso, o None; si el mes es anterior al inicio, es del año siguiente."""
    hallado = FECHA_EN_TEXTO.search(parrafo["texto"])
    if not hallado:
        return None
    anio, mes_inicio = int(inicio_aviso[:4]), int(inicio_aviso[5:7])
    mes = MESES.index(hallado.group(2)) + 1
    return f"{anio + (mes < mes_inicio)}-{mes:02d}-{int(hallado.group(1)):02d}"


def _con_redacciones(grupo, clave, redacciones, fecha, oro, **campos):
    return [
        {"id": f"{grupo}-{clave}-{i}", "grupo": grupo, "pregunta": r.format(**campos), "fecha": fecha, "oro": oro}
        for i, r in enumerate(redacciones)
    ]


def preguntas(parrafos, avisos, comunicados):
    """[{id, grupo, pregunta, fecha, oro}]: el oro son índices de párrafos y sale de los metadatos, no del texto."""
    por_doc = collections.defaultdict(list)
    for i, p in enumerate(parrafos):
        por_doc[p["doc_id"]].append(i)
    salida = []
    for c in comunicados:
        for tipo, redacciones in PLANTILLAS_A.items():
            oro = {i for i in por_doc[c["id"]] if parrafos[i]["tipo"] == tipo}
            if oro:
                salida += _con_redacciones("A", f"{c['id']}-{tipo}", redacciones, c["vigente_desde"], oro)
    activos = [a for a in avisos if a["estado"] != "cancelado"]
    vistos = set()
    por_dia = collections.defaultdict(set)
    for a in activos:
        macros = a["macroregiones"].split("|")
        fecha = a["inicio"][:10]
        for m in macros:
            if m not in REGION_EN_PREGUNTA or (a["tipo"], m, fecha) in vistos:
                continue
            vistos.add((a["tipo"], m, fecha))
            oro = {
                i
                for b in activos
                if b["tipo"] == a["tipo"]
                and m in b["macroregiones"].split("|")
                and b["inicio"][:10] <= fecha <= b["fin"][:10]
                for i in por_doc[b["id"]]
                if vigente_en(parrafos[i], fecha)
            }
            if oro:
                campos = {"tipo": a["tipo"], "region": REGION_EN_PREGUNTA[m], "dia": dia_en_texto(fecha)}
                salida += _con_redacciones("B", f"{a['tipo']}-{m}-{fecha}", PLANTILLAS_B, fecha, oro, **campos)
        for i in por_doc[a["id"]]:
            if parrafos[i]["seccion"] == "dia" and (dia := fecha_del_parrafo(parrafos[i], a["inicio"])):
                por_dia[(a["tipo"], dia)].add(i)
    for (tipo, dia), oro in sorted(por_dia.items()):
        salida += _con_redacciones("C", f"{tipo}-{dia}", PLANTILLAS_C, dia, oro, tipo=tipo, dia=dia_en_texto(dia))
    return salida


def orden_de(puntajes, candidatos_idx, semilla):
    """Los candidatos de mayor a menor; los empates se rompen al azar, pero siempre igual para la misma pregunta."""
    azar = random.Random(semilla)
    mezcla = list(range(len(candidatos_idx)))
    azar.shuffle(mezcla)
    return [candidatos_idx[i] for i in sorted(mezcla, key=lambda i: -puntajes[i])]


def rangos(puntaje_a, puntaje_b):
    """Rango (1 es el mejor) de cada puntaje; para fusionar."""
    return np.argsort(np.argsort(-np.asarray(puntaje_a))) + 1, np.argsort(np.argsort(-np.asarray(puntaje_b))) + 1


def fusion_rangos(puntaje_a, puntaje_b, k=K_RRF):
    a, b = rangos(puntaje_a, puntaje_b)
    return 1 / (k + a) + 1 / (k + b)


def azar_en(k, total, oro):
    """Probabilidad exacta de que al menos un párrafo correcto salga entre k al azar."""
    if total - oro < k:
        return 1.0
    return 1 - comb(total - oro, k) / comb(total, k)


def fila_de(pregunta, orden, tiempo):
    oro = pregunta["oro"]
    primero = next((i for i, x in enumerate(orden, 1) if x in oro), "")
    en5 = sum(x in oro for x in orden[:5])
    return {
        "id": pregunta["id"],
        "grupo": pregunta["grupo"],
        "primero": primero,
        "en5": en5,
        "oro": len(oro),
        "candidatos": len(orden),
        "tiempo_s": round(tiempo, 4),
    }


# ---------------------------------------------------------------- candidatos


def _bi_encoder(nombre, parrafos):
    st = candidatos.cargar(nombre)
    pre_q, pre_p = PREFIJOS.get(nombre, ("", ""))
    consulta = candidatos.Candidato(nombre, st, pre_q)
    oficial = embeddings.Oficial(candidatos.Candidato(nombre, st, pre_p), parrafos)
    if oficial.truncados:
        raise ValueError(f"{nombre}: {oficial.truncados} tramos oficiales truncados")

    def puntuar(texto, idx):
        return candidatos.maximos_por_parrafo(consulta.embeber(consulta.tramos(texto)), oficial, "con")[idx]

    return puntuar


def _bm25(parrafos):
    modelo = hibrido.Bm25([hibrido.limpia(preproceso.bolsa(p["texto"]), "con") for p in parrafos])

    def puntuar(texto, idx):
        return modelo.puntajes(hibrido.limpia(preproceso.bolsa(texto), "con"))[idx]

    return puntuar


def _tfidf(parrafos):
    from sklearn.feature_extraction import DictVectorizer
    from sklearn.feature_extraction.text import TfidfTransformer

    bolsas = [dict(preproceso.bolsa(p["texto"])) for p in parrafos]
    vector, peso = DictVectorizer(), TfidfTransformer(sublinear_tf=True)
    matriz = peso.fit_transform(vector.fit_transform(bolsas))

    def puntuar(texto, idx):
        consulta = peso.transform(vector.transform([dict(preproceso.bolsa(texto))]))
        return (matriz[idx] @ consulta.T).toarray().ravel()

    return puntuar


def _fusion(parrafos):
    semantico, lexico = _bi_encoder(BASE, parrafos), _bm25(parrafos)

    def puntuar(texto, idx):
        return fusion_rangos(semantico(texto, idx), lexico(texto, idx))

    return puntuar


def _cruzado(parrafos):
    modelo = reranker.cargar_reranker(CRUZADO)

    def puntuar(texto, idx):
        pares = [(texto, parrafos[i]["texto"]) for i in idx]
        return modelo.predict(pares, batch_size=LOTE, show_progress_bar=False)

    return puntuar


def puntuador(nombre, parrafos):
    if nombre == FUSION:
        return _fusion(parrafos)
    if nombre == CRUZADO:
        return _cruzado(parrafos)
    if nombre == "tfidf":
        return _tfidf(parrafos)
    if nombre == "bm25":
        return _bm25(parrafos)
    return _bi_encoder(nombre, parrafos)


def archivo(nombre):
    return config.DIR_NLP / f"recuperador-{nombre}.csv"


def datos():
    parrafos = leer_csv(config.DIR_OFICIAL / "parrafos.csv")
    avisos = leer_csv(config.DIR_OFICIAL / "avisos.csv")
    comunicados = leer_csv(config.DIR_OFICIAL / "comunicados.csv")
    return parrafos, preguntas(parrafos, avisos, comunicados)


def puntuar(nombre):
    from radar.nlp.viabilidad import pico_memoria_gb

    parrafos, lista = datos()
    ruta = archivo(nombre)
    reparar_csv(ruta, esquemas.RECUPERADOR)
    hechas = {f["id"] for f in leer_csv(ruta)}
    pendientes = [p for p in lista if p["id"] not in hechas]
    if not pendientes:
        return
    funcion = puntuador(nombre, parrafos)
    vigencia = {}
    for i, pregunta in enumerate(pendientes, 1):
        idx = vigencia.setdefault(pregunta["fecha"], np.where(candidatos.vigentes(parrafos, pregunta["fecha"]))[0])
        inicio = time.perf_counter()
        puntajes = funcion(pregunta["pregunta"], idx)
        tiempo = time.perf_counter() - inicio
        orden = orden_de(puntajes, [int(x) for x in idx], f"{config.SEMILLA_MUESTRAS}-{pregunta['id']}")
        fila = fila_de({**pregunta, "oro": pregunta["oro"] & set(orden)}, orden, tiempo)
        fila["pico_gb"] = round(pico_memoria_gb()[0], 2)
        anexar_csv(ruta, esquemas.RECUPERADOR, [fila])
        if i % 300 == 0:
            log.info(f"  {nombre}: {i}/{len(pendientes)}")


def correr():
    parrafos, lista = datos()
    lineas = [
        {"id": p["id"], "grupo": p["grupo"], "pregunta": p["pregunta"], "fecha": p["fecha"], "oro": len(p["oro"])}
        for p in lista
    ]
    escribir_csv(config.DIR_NLP / "recuperador-preguntas.csv", esquemas.RECUPERADOR_PREGUNTAS, lineas)
    log.info(f"{len(lista)} preguntas: {collections.Counter(p['grupo'] for p in lista)}")
    for nombre in CANDIDATOS:
        orden = [sys.executable, "-m", "radar.nlp.recuperador", "puntuar", nombre]
        salida = subprocess.run(orden, capture_output=True, text=True, encoding="utf-8", cwd=config.RAIZ)
        log.info(f"  {nombre}: código {salida.returncode}" + (f"; {salida.stderr[-300:]}" if salida.returncode else ""))


# ---------------------------------------------------------------- criterios


def acierto(fila, k):
    return bool(fila["primero"]) and int(fila["primero"]) <= k


def medidas_de(filas):
    """{grupo: {hit@k, recall5, mrr, azar3, n}} y el promedio de acierto@K entre grupos, con el mismo peso."""
    grupos = {}
    for g in GRUPOS:
        fs = [f for f in filas if f["grupo"] == g and int(f["oro"])]
        if not fs:
            continue
        grupos[g] = {
            "n": len(fs),
            **{f"hit{k}": statistics.fmean(acierto(f, k) for f in fs) for k in (K, *KS_INFORMATIVOS)},
            "recall5": statistics.fmean(min(1, int(f["en5"]) / min(5, int(f["oro"]))) for f in fs),
            "mrr": statistics.fmean(1 / int(f["primero"]) if f["primero"] else 0 for f in fs),
            "azar": statistics.fmean(azar_en(K, int(f["candidatos"]), int(f["oro"])) for f in fs),
        }
    promedio = statistics.fmean(x[f"hit{K}"] for x in grupos.values()) if grupos else 0.0
    return grupos, promedio


def tiempo_y_memoria(filas):
    return statistics.median(float(f["tiempo_s"]) for f in filas), max(float(f["pico_gb"]) for f in filas)


def pasa_candidato(medida, base, p_valor, tiempo, memoria):
    """(pasa, motivo) según los pasos 2 a 5."""
    grupos, promedio = medida
    grupos_base, promedio_base = base
    if promedio < promedio_base + MEJORA:
        return False, f"promedio {promedio:.4f} < {promedio_base + MEJORA:.4f}"
    if p_valor >= UMBRAL_P:
        return False, f"McNemar p = {p_valor:.4f} ≥ {UMBRAL_P:.4f}"
    for g, x in grupos.items():
        if x[f"hit{K}"] < grupos_base[g][f"hit{K}"] - RETROCESO:
            return False, f"el grupo {g} retrocede"
    if tiempo > CONSULTA_MAXIMA_S or memoria > MEMORIA_MAXIMA_GB:
        return False, f"tiempo {tiempo:.3f} s o memoria {memoria:.2f} GB"
    return True, "pasa"


def minimos(grupos):
    """{grupo: alcanza acierto@K ≥ azar + SOBRE_AZAR}."""
    return {g: x[f"hit{K}"] >= x["azar"] + SOBRE_AZAR for g, x in grupos.items()}


def criterios():
    filas = {n: leer_csv(archivo(n)) for n in CANDIDATOS}
    _, lista = datos()
    total = len(lista)
    completos = {n: f for n, f in filas.items() if len(f) == total}
    if BASE not in completos:
        raise SystemExit(f"Falta puntuar la base {BASE}: {len(filas[BASE])} de {total}")
    base = medidas_de(completos[BASE])
    aciertos_base = {f["id"]: acierto(f, K) for f in completos[BASE]}
    resultado, informativos, pasan = [], [], {}
    for nombre, fs in completos.items():
        medida = medidas_de(fs)
        tiempo, memoria = tiempo_y_memoria(fs)
        detalle_grupos = "; ".join(
            f"{g}: @1 {x['hit1']:.3f} @3 {x['hit3']:.3f} @5 {x['hit5']:.3f} @10 {x['hit10']:.3f} "
            f"recall@5 {x['recall5']:.3f} MRR {x['mrr']:.3f} azar@3 {x['azar']:.3f} (n {x['n']})"
            for g, x in medida[0].items()
        )
        informativos.append(
            criterio(
                INFO_E, nombre, round(medida[1], 4), "", True, f"{tiempo:.3f} s; {memoria:.2f} GB; {detalle_grupos}"
            )
        )
        if nombre == BASE:
            continue
        p_valor = candidatos.mcnemar(aciertos_base, {f["id"]: acierto(f, K) for f in fs})
        pasa, motivo = pasa_candidato(medida, base, p_valor, tiempo, memoria)
        if pasa:
            pasan[nombre] = tiempo
        umbral = f"≥ {base[1] + MEJORA:.4f}; p < {UMBRAL_P:.4f}"
        resultado.append(
            criterio(
                PRUEBA_E,
                f"{nombre}: promedio de acierto@{K}",
                round(medida[1], 4),
                umbral,
                pasa,
                f"McNemar p {p_valor:.4f}; {motivo}",
            )
        )
    elegido = min(pasan, key=pasan.get) if pasan else BASE
    alcanza = minimos(medidas_de(completos[elegido])[0])
    faltan = [n for n in CANDIDATOS if n not in completos]
    nota = f" (provisional: falta {', '.join(faltan)})" if faltan else ""
    resultado.append(
        criterio(PRUEBA_E, "elección" + nota, elegido, "pasos 2 a 5", True, f"promedio de {BASE}: {base[1]:.4f}")
    )
    resultado += [
        criterio(
            PRUEBA_E,
            f"{elegido}, grupo {g}: acierto@{K} ≥ azar + {SOBRE_AZAR}",
            ok,
            "sí",
            ok,
            "si no alcanza, ese tipo de consulta va por metadatos",
        )
        for g, ok in alcanza.items()
    ]
    return resultado + informativos


def main(argv=None):
    ap = argparse.ArgumentParser(description="E: recuperador del agente.")
    ap.add_argument("paso", choices=("correr", "puntuar", "criterios"))
    ap.add_argument("nombre", nargs="?", choices=CANDIDATOS, help="solo con puntuar")
    args = ap.parse_args(argv)
    if args.paso == "puntuar":
        if not args.nombre:
            ap.error("puntuar necesita un candidato")
        puntuar(args.nombre)
        return 0
    registro = configurar(f"nlp-recuperador-{args.paso}")
    inicio = ahora()
    config.DIR_NLP.mkdir(parents=True, exist_ok=True)
    filas = []
    try:
        if args.paso == "correr":
            with sin_suspension():
                correr()
        else:
            filas = criterios()
    except KeyboardInterrupt:
        log.info("Cortado: lo puntuado quedó guardado; al relanzar sigue desde ahí.")
        return 1
    if filas:
        guardar(filas, config.DIR_NLP / "validacion.csv")
        reporte(filas, [], inicio)
    duracion = (ahora() - inicio).total_seconds() / 60
    log.info(f"Duración: {duracion:.1f} min · registro: {registro.relative_to(config.RAIZ)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
