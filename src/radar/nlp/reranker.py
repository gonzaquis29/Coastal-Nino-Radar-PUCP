"""C: reranker en texto corto, frente a los párrafos vigentes del ENFEN (docs/nlp/embeddings.md, definición del 6-nov).

Uso: python -m radar.nlp.reranker tiempo               # paso 1: tiempo por consulta y memoria
     python -m radar.nlp.reranker medir NOMBRE         # proceso hijo del paso 1: imprime la medida de un candidato
     python -m radar.nlp.reranker puntuar NOMBRE...    # pasos 2 a 4; se puede cortar y relanzar
     python -m radar.nlp.reranker criterios            # decide con lo que ya esté puntuado

No lee cuerpos: el texto es el titular y el resumen de notas.csv.
"""

import argparse
import collections
import json
import logging
import statistics
import subprocess
import sys
import time

import numpy as np

from radar import config
from radar.comun.archivos import anexar_csv, leer_csv, reparar_csv
from radar.comun.energia import sin_suspension
from radar.comun.registro import configurar, describir
from radar.comun.texto import ahora
from radar.nlp import candidatos, embeddings, esquemas, tfidf
from radar.noticias.viabilidad import criterio, guardar, reporte

log = logging.getLogger(__name__)

PRUEBA_TIEMPO = "Reranker: tiempo y memoria"
PRUEBA_C = "Reranker: texto corto"
INFO_C = "Reranker (informativo)"
BASE = "minilm"
CONSULTA_MAXIMA_S = 2.0
MEMORIA_MAXIMA_GB = 6.0
CONSULTAS = 20
LARGO_MAXIMO = 512
LOTE = 16
MARGEN = 0.02  # E4 en texto corto: mejora mínima frente a la base, sin solape de los IC del 95 %
AUC_SEMAFORO = embeddings.AUC_SEMAFORO
REFERENCIA_BASE = 0.8651  # E4 de minilm medido antes de definir C: control del instrumento
TOLERANCIA_REFERENCIA = 0.005
NOMBRES = tuple(config.CANDIDATOS_RERANKER)


def archivo(nombre):
    return config.DIR_NLP / f"reranker-{nombre}.csv"


def texto_corto(nota):
    return "\n".join(x for x in (nota["titular"], nota["resumen"]) if x.strip())


def variantes_de(estrato, positivo):
    """Variantes que usan los criterios: E4 compara sin términos; E3, con ellos."""
    salida = []
    if estrato in (tfidf.ESTRATO_NINO, tfidf.ESTRATO_NEGATIVO):
        salida.append("sin")
    if positivo or estrato == tfidf.ESTRATO_NEGATIVO:
        salida.append("con")
    return salida


def universo(notas, control, lista_b):
    """[(nota, estrato, positivo, nueva)]: la lista de notas de B, más las notas sobre El Niño que no estaban en ella.
    lista_b es {(medio, id): fila de candidatos-p1.csv}; se excluyen sus notas con error."""
    salida = []
    for nota, estrato in embeddings.corpus(notas, control):
        clave = (nota["medio"], nota["id"])
        if clave in lista_b:
            fila = lista_b[clave]
            positivo = fila["positivo"] in ("1", "True")
            if not fila["error"] and variantes_de(estrato, positivo):
                salida.append((nota, estrato, positivo, False))
        elif estrato == tfidf.ESTRATO_NINO:
            salida.append((nota, estrato, False, True))
    return salida


def pares_de(texto, parrafos, variante):
    """Pares (texto, párrafo) con los párrafos en la misma variante que el texto."""
    limpiar = embeddings.VARIANTES[variante]
    return [(limpiar(texto), limpiar(p["texto"])) for p in parrafos]


def cargar_reranker(nombre):
    """El candidato con sentence-transformers, siempre en float32 (CLAUDE.md)."""
    import torch
    from sentence_transformers import CrossEncoder

    return CrossEncoder(
        config.CANDIDATOS_RERANKER[nombre],
        device="cpu",
        max_length=LARGO_MAXIMO,
        model_kwargs={"dtype": torch.float32},
    )


def pares_truncados(modelo, pares):
    largos = modelo.tokenizer([a for a, _ in pares], [b for _, b in pares], add_special_tokens=True)["input_ids"]
    return sum(len(x) > LARGO_MAXIMO for x in largos)


def puntuador_cruzado(nombre, parrafos):
    modelo = cargar_reranker(nombre)

    def puntuar(texto, mascara, variante):
        elegidos = [p for p, m in zip(parrafos, mascara, strict=True) if m]
        pares = pares_de(texto, elegidos, variante)
        return modelo.predict(pares, batch_size=LOTE, show_progress_bar=False), pares_truncados(modelo, pares)

    return puntuar


def puntuador_base(parrafos):
    """La base: el coseno máximo por tramos de B, con el mismo código."""
    st = candidatos.cargar(BASE)
    pre_nota, pre_oficial = candidatos.prefijos(BASE)
    modelo = candidatos.Candidato(BASE, st, pre_nota)
    oficial = embeddings.Oficial(candidatos.Candidato(BASE, st, pre_oficial), parrafos)

    def puntuar(texto, mascara, variante):
        tramos = modelo.tramos(embeddings.VARIANTES[variante](texto))
        if not tramos:
            return np.array([]), 0
        vectores = modelo.embeber(tramos)
        return candidatos.maximos_por_parrafo(vectores, oficial, variante)[mascara], modelo.truncados(tramos)

    return puntuar


def fila_puntuada(nota, estrato, positivo, nueva, puntuar, parrafos):
    """Lo que se guarda de una nota: puntajes y controles, nunca su texto."""
    fila = {"medio": nota["medio"], "id": nota["id"], "estrato": estrato, "positivo": positivo, "nueva": nueva}
    fecha = nota["fecha_publicacion"][:10]
    mascara = candidatos.vigentes(parrafos, fecha)
    elegidos = [p for p, m in zip(parrafos, mascara, strict=True) if m]
    fila |= {"pares": len(elegidos), "truncados": 0, "error": ""}
    if not elegidos:
        return {**fila, "error": "sin párrafos vigentes"}
    for variante in variantes_de(estrato, positivo):
        puntajes, truncados = puntuar(texto_corto(nota), mascara, variante)
        fila["truncados"] += truncados
        if len(puntajes):
            fila[variante] = round(float(np.max(puntajes)), 5)
            fila.setdefault("parrafo", elegidos[int(np.argmax(puntajes))]["id"])
    return fila


def puntuar_candidato(nombre, lista):
    ruta = archivo(nombre)
    reparar_csv(ruta, esquemas.RERANKER)
    hechos = {(f["medio"], f["id"]) for f in leer_csv(ruta) if not f["error"]}
    pendientes = [x for x in lista if (x[0]["medio"], x[0]["id"]) not in hechos]
    log.info(f"{nombre}: {len(lista)} notas · ya puntuadas {len(hechos)} · por puntuar {len(pendientes)}")
    if not pendientes:
        return
    parrafos = embeddings.parrafos_enfen()
    puntuar = puntuador_base(parrafos) if nombre == BASE else puntuador_cruzado(nombre, parrafos)
    inicio = time.perf_counter()
    for i, (nota, estrato, positivo, nueva) in enumerate(pendientes, 1):
        try:
            fila = fila_puntuada(nota, estrato, positivo, nueva, puntuar, parrafos)
        except Exception as error:  # una nota que falla no detiene a las demás
            base = {"medio": nota["medio"], "id": nota["id"], "estrato": estrato}
            fila = {**base, "positivo": positivo, "nueva": nueva, "error": describir(error)[:200]}
        anexar_csv(ruta, esquemas.RERANKER, [fila])
        if i % 100 == 0:
            ritmo = i / (time.perf_counter() - inicio)
            log.info(f"  {nombre}: {i}/{len(pendientes)} · {ritmo * 60:.0f} notas/min")


def lista_de_notas():
    notas = leer_csv(config.DIR_NOTICIAS / "notas.csv")
    control = leer_csv(config.DIR_NOTICIAS / "control_negativo.csv")
    return universo(notas, control, tfidf.leidos(candidatos.archivo_pasada(1)))


# ---------------------------------------------------------------- paso 1


def medir(nombre):
    from radar.nlp.viabilidad import pico_memoria_gb

    inicio = time.perf_counter()
    modelo = cargar_reranker(nombre)
    carga = time.perf_counter() - inicio
    parrafos = embeddings.parrafos_enfen()
    notas = sorted(
        (n for n in leer_csv(config.DIR_NOTICIAS / "notas.csv") if n["sobre_nino"] == "1"),
        key=lambda n: (n["medio"], n["id"]),
    )[:CONSULTAS]
    tiempos, pares_por_consulta = [], []
    for n in notas:
        mascara = candidatos.vigentes(parrafos, n["fecha_publicacion"][:10])
        pares = pares_de(texto_corto(n), [p for p, m in zip(parrafos, mascara, strict=True) if m], "con")
        pares_por_consulta.append(len(pares))
        inicio = time.perf_counter()
        modelo.predict(pares, batch_size=LOTE, show_progress_bar=False)
        tiempos.append(time.perf_counter() - inicio)
    pico, _ = pico_memoria_gb()
    return {
        "carga_s": round(carga, 1), "consulta_s": round(statistics.median(tiempos), 3),
        "primera_s": round(tiempos[0], 3), "pico_gb": round(pico, 2), "pares": max(pares_por_consulta),
    }  # fmt: skip


def criterio_tiempo(nombre, medida):
    pasa = medida["consulta_s"] <= CONSULTA_MAXIMA_S and medida["pico_gb"] <= MEMORIA_MAXIMA_GB
    detalle = (
        f"memoria {medida['pico_gb']} GB; la primera {medida['primera_s']} s; carga {medida['carga_s']} s; "
        f"hasta {medida['pares']} pares"
    )
    umbral = f"≤ {CONSULTA_MAXIMA_S} s y ≤ {MEMORIA_MAXIMA_GB} GB"
    return criterio(PRUEBA_TIEMPO, nombre, medida["consulta_s"], umbral, pasa, detalle)


def prueba_tiempo(nombres):
    """Un proceso por candidato, para que la memoria de uno no se sume a la de otro."""
    filas = []
    for nombre in nombres:
        orden = [sys.executable, "-m", "radar.nlp.reranker", "medir", nombre]
        salida = subprocess.run(orden, capture_output=True, text=True, encoding="utf-8", cwd=config.RAIZ)
        lineas = [x for x in salida.stdout.splitlines() if x.startswith("{")]
        if salida.returncode or not lineas:
            log.warning(f"{nombre}: falló (código {salida.returncode}); {salida.stderr[-400:]}")
            filas.append(criterio(PRUEBA_TIEMPO, nombre, "falló", "", False, salida.stderr[-200:]))
            continue
        filas.append(criterio_tiempo(nombre, json.loads(lineas[-1])))
        log.info(f"  {nombre}: {filas[-1]['valor']} s; {filas[-1]['detalle']}")
    return filas


# ---------------------------------------------------------------- pasos 2 a 4


def es_si(valor):
    return valor in ("1", "True", True)


def medidas_de(filas):
    """{e4, e3, nuevas}: (AUC, IC) de las filas de un candidato."""
    filas = [f for f in filas if not f["error"]]

    def otros(f):
        return f["estrato"] == tfidf.ESTRATO_NEGATIVO

    def nino(f):
        return f["estrato"] == tfidf.ESTRATO_NINO and not es_si(f["nueva"])

    def nuevas(f):
        return es_si(f["nueva"])

    def positivo(f):
        return es_si(f["positivo"])

    auc = candidatos.auc_de
    return {
        "e4": auc(filas, "sin", nino, otros),
        "e3": auc(filas, "con", positivo, otros),
        "nuevas": auc(filas, "sin", nuevas, otros),
    }


def pasa_candidato(medida, base):
    """(pasa, motivo) según los pasos 2 a 4."""
    (e4, (bajo, _)), (ref, (_, alto)) = medida["e4"], base["e4"]
    if e4 < ref + MARGEN:
        return False, f"E4 {e4} < {ref + MARGEN:.4f}"
    if bajo <= alto:
        return False, f"los IC se solapan: {bajo} ≤ {alto}"
    if medida["e3"][0] < AUC_SEMAFORO:
        return False, f"E3 {medida['e3'][0]} < {AUC_SEMAFORO}"
    if medida["nuevas"][0] <= base["nuevas"][0]:
        return False, f"notas nuevas {medida['nuevas'][0]} ≤ {base['nuevas'][0]}"
    return True, "pasa"


def elegir(medidas, base, tiempos):
    """El más rápido de los que pasan, o None: el semáforo sigue con la base."""
    pasan = [m for m, x in medidas.items() if m in tiempos and pasa_candidato(x, base)[0]]
    return min(pasan, key=lambda m: tiempos[m]) if pasan else None


def tiempos_validados():
    filas = leer_csv(config.DIR_NLP / "validacion.csv")
    return {f["criterio"]: float(f["valor"]) for f in filas if f["prueba"] == PRUEBA_TIEMPO and f["pasa"] == "True"}


def tipos_elegidos(filas, parrafos):
    tipo = {p["id"]: p["tipo"] for p in parrafos}
    elegidos = [f["parrafo"] for f in filas if f["estrato"] == tfidf.ESTRATO_NINO and f.get("parrafo")]
    conteo = collections.Counter(tipo[x] for x in elegidos)
    return {k: round(v / len(elegidos), 3) for k, v in conteo.most_common()} if elegidos else {}


def criterios():
    filas_base = leer_csv(archivo(BASE))
    if not filas_base:
        raise SystemExit(f"Falta puntuar la base: python -m radar.nlp.reranker puntuar {BASE}")
    total = len(lista_de_notas())
    base = medidas_de(filas_base)
    resultado = [
        criterio(
            PRUEBA_C,
            f"control del instrumento: E4 de {BASE}",
            base["e4"][0],
            f"{REFERENCIA_BASE} ± {TOLERANCIA_REFERENCIA}",
            abs(base["e4"][0] - REFERENCIA_BASE) <= TOLERANCIA_REFERENCIA,
            f"IC95 {base['e4'][1][0]}-{base['e4'][1][1]}; E3 {base['e3'][0]}; notas nuevas {base['nuevas'][0]}",
        )
    ]
    parrafos, tiempos = embeddings.parrafos_enfen(), tiempos_validados()
    medidas, pendientes = {}, []
    informativos = [criterio(INFO_C, f"tipo elegido ({BASE})", str(tipos_elegidos(filas_base, parrafos)), "", True)]
    for nombre in NOMBRES:
        if nombre not in tiempos:
            continue
        filas = leer_csv(archivo(nombre))
        if sum(not f["error"] for f in filas) < total:
            pendientes.append(nombre)
            continue
        m = medidas[nombre] = medidas_de(filas)
        pasa, motivo = pasa_candidato(m, base)
        truncados = sum(int(f["truncados"] or 0) for f in filas)
        detalle = (
            f"IC95 {m['e4'][1][0]}-{m['e4'][1][1]}; E3 {m['e3'][0]}; notas nuevas {m['nuevas'][0]}; "
            f"pares truncados {truncados}; {motivo}"
        )
        umbral = f"≥ {base['e4'][0] + MARGEN:.4f}, sobre {base['e4'][1][1]}"
        resultado.append(criterio(PRUEBA_C, f"{nombre}: E4 en texto corto", m["e4"][0], umbral, pasa, detalle))
        informativos.append(
            criterio(INFO_C, f"tipo elegido ({nombre})", str(tipos_elegidos(filas, parrafos)), "", True)
        )
    elegido = elegir(medidas, base, tiempos)
    falta = f" (provisional: falta {', '.join(pendientes)})" if pendientes else ""
    resultado.append(criterio(PRUEBA_C, "elección" + falta, elegido or BASE, "pasos 1 a 4", True, f"tiempos {tiempos}"))
    return resultado + informativos


def main(argv=None):
    ap = argparse.ArgumentParser(description="C: reranker en texto corto.")
    ap.add_argument("paso", choices=("tiempo", "medir", "puntuar", "criterios"))
    ap.add_argument("nombres", nargs="*", help="candidatos; con puntuar, también la base")
    args = ap.parse_args(argv)
    validos = {*NOMBRES, BASE}
    if not set(args.nombres) <= validos:
        ap.error(f"nombres válidos: {sorted(validos)}")
    if args.paso == "medir":  # proceso hijo: solo imprime la medida
        print(json.dumps(medir(args.nombres[0])))
        return 0
    registro = configurar(f"nlp-reranker-{args.paso}")
    inicio = ahora()
    config.DIR_NLP.mkdir(parents=True, exist_ok=True)
    filas = []
    try:
        if args.paso == "tiempo":
            filas = prueba_tiempo(args.nombres or NOMBRES)
        elif args.paso == "puntuar":
            lista = lista_de_notas()
            with sin_suspension():
                for nombre in args.nombres:
                    puntuar_candidato(nombre, lista)
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
