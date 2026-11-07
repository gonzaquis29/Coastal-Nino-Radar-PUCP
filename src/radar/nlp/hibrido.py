"""D: minilm + BM25 en texto corto, frente a los párrafos vigentes del ENFEN (docs/nlp/embeddings.md, 6-nov).

Uso: python -m radar.nlp.hibrido puntuar     # sin red ni cuerpos; se puede cortar y relanzar
     python -m radar.nlp.hibrido tiempo      # paso 4: tiempo por consulta y memoria
     python -m radar.nlp.hibrido criterios   # decide con lo puntuado
"""

import argparse
import collections
import logging
import math
import statistics
import sys
import time

import numpy as np

from radar import config
from radar.comun.archivos import anexar_csv, leer_csv, reparar_csv
from radar.comun.energia import sin_suspension
from radar.comun.registro import configurar, describir
from radar.comun.texto import ahora
from radar.nlp import candidatos, embeddings, esquemas, preproceso, reranker, tfidf
from radar.noticias.viabilidad import criterio, guardar, reporte

log = logging.getLogger(__name__)

PRUEBA_D = "Híbrido: texto corto"
INFO_D = "Híbrido (informativo)"
K1, B = 1.5, 0.75  # BM25, valores habituales fijados antes de medir la fusión
ESTRATO_REFERENCIA = "cercano"  # no entra en E4 ni en E3
QUITAR = frozenset(tfidf.TERMINOS_DE_LA_ETIQUETA)
CONSULTA_MAXIMA_S = 2.0
MEMORIA_MAXIMA_GB = 6.0
CONSULTAS = 20
TOLERANCIA_CONTROL = 1e-3


def limpia(bolsa, variante):
    """La bolsa de lemas; sin los términos del fenómeno en la variante "sin", igual que T4."""
    return {t: n for t, n in bolsa.items() if variante == "con" or t not in QUITAR}


class Bm25:
    """BM25 sobre párrafos ya convertidos en bolsas de lemas."""

    def __init__(self, bolsas, k1=K1, b=B):
        self.n = len(bolsas)
        largos = np.array([sum(x.values()) for x in bolsas], dtype=float)
        promedio = largos.mean() if self.n else 1.0
        df = collections.Counter(t for x in bolsas for t in x)
        self.indice = collections.defaultdict(list)
        for i, x in enumerate(bolsas):
            freno = k1 * (1 - b + b * largos[i] / promedio)
            for t, f in x.items():
                idf = math.log(1 + (self.n - df[t] + 0.5) / (df[t] + 0.5))
                self.indice[t].append((i, idf * f * (k1 + 1) / (f + freno)))

    def puntajes(self, consulta):
        """BM25 de la consulta con cada párrafo, dividido por el largo de la consulta para comparar notas entre sí."""
        salida = np.zeros(self.n)
        for t in consulta:
            for i, valor in self.indice.get(t, ()):
                salida[i] += valor
        return salida / max(1, sum(consulta.values()))


def parametros(filas):
    """{variante: ((media, desviación) del coseno, (media, desviación) de BM25)} de los máximos de referencia."""
    salida = {}
    for v in ("con", "sin"):
        grupos = []
        for clave in (f"cos_{v}", f"bm25_{v}"):
            valores = [float(f[clave]) for f in filas if f.get(clave) not in (None, "")]
            grupos.append((statistics.fmean(valores), statistics.stdev(valores)))
        salida[v] = tuple(grupos)
    return salida


def fusion(cosenos, bm25, param):
    """Suma con el mismo peso de los dos puntajes normalizados con la referencia."""
    (m_cos, d_cos), (m_bm, d_bm) = param
    return (cosenos - m_cos) / d_cos + (bm25 - m_bm) / d_bm


class Puntuador:
    def __init__(self, parrafos):
        self.parrafos = parrafos
        self.coseno = reranker.puntuador_base(parrafos)
        self.bm25 = {
            v: Bm25([limpia(preproceso.bolsa(f(p["texto"])), v) for p in parrafos])
            for v, f in embeddings.VARIANTES.items()
        }

    def crudos(self, texto, mascara, variante):
        """(cosenos, BM25) en los párrafos vigentes, o None si el texto queda vacío."""
        cosenos, _ = self.coseno(texto, mascara, variante)
        if not len(cosenos):
            return None
        consulta = limpia(preproceso.bolsa(embeddings.VARIANTES[variante](texto)), variante)
        return cosenos, self.bm25[variante].puntajes(consulta)[mascara]


def base_de(nota, estrato, positivo, nueva=False):
    return {"medio": nota["medio"], "id": nota["id"], "estrato": estrato, "positivo": positivo, "nueva": nueva}


def fila_referencia(nota, puntuador):
    fila = {"medio": nota["medio"], "id": nota["id"], "error": ""}
    mascara = candidatos.vigentes(puntuador.parrafos, nota["fecha_publicacion"][:10])
    for v in ("con", "sin"):
        crudos = puntuador.crudos(reranker.texto_corto(nota), mascara, v)
        if crudos is not None:
            fila[f"cos_{v}"], fila[f"bm25_{v}"] = round(float(crudos[0].max()), 6), round(float(crudos[1].max()), 6)
    return fila


def fila_puntuada(nota, estrato, positivo, nueva, puntuador, param):
    """Puntajes y controles, nunca el texto."""
    fila = {**base_de(nota, estrato, positivo, nueva), "error": ""}
    mascara = candidatos.vigentes(puntuador.parrafos, nota["fecha_publicacion"][:10])
    elegidos = [p for p, m in zip(puntuador.parrafos, mascara, strict=True) if m]
    for v in reranker.variantes_de(estrato, positivo):
        crudos = puntuador.crudos(reranker.texto_corto(nota), mascara, v)
        if crudos is None:
            continue
        fusionado = fusion(*crudos, param[v])
        fila[v] = round(float(fusionado.max()), 6)
        fila[f"cos_{v}"] = round(float(crudos[0].max()), 6)
        fila.setdefault("parrafo", elegidos[int(fusionado.argmax())]["id"])
    return fila


def archivo():
    return config.DIR_NLP / "hibrido.csv"


def archivo_referencia():
    return config.DIR_NLP / "hibrido-referencia.csv"


def referencia_de_notas(notas, control, lista_b):
    """Las notas del estrato de referencia que tienen texto en la lista de B."""
    por_clave = {(n["medio"], n["id"]): n for n in notas}
    salida = []
    for c in control:
        clave = (c["medio"], c["id"])
        if (
            c["estrato"] == ESTRATO_REFERENCIA
            and clave in por_clave
            and clave in lista_b
            and not lista_b[clave]["error"]
        ):
            salida.append(por_clave[clave])
    return salida


def _anexar_pendientes(ruta, columnas, pendientes, hacer, nombre):
    """Anexa una fila por nota; una nota que falla no detiene a las demás."""
    for i, (nota, *resto) in enumerate(pendientes, 1):
        try:
            fila = hacer(nota, *resto)
        except Exception as error:
            fila = {"medio": nota["medio"], "id": nota["id"], "error": describir(error)[:200]}
        anexar_csv(ruta, columnas, [fila])
        if i % 200 == 0:
            log.info(f"  {nombre}: {i}/{len(pendientes)}")


def hechas(ruta, columnas):
    reparar_csv(ruta, columnas)
    return {(f["medio"], f["id"]) for f in leer_csv(ruta) if not f["error"]}


def puntuar():
    notas = leer_csv(config.DIR_NOTICIAS / "notas.csv")
    control = leer_csv(config.DIR_NOTICIAS / "control_negativo.csv")
    lista_b = tfidf.leidos(candidatos.archivo_pasada(1))
    puntuador = Puntuador(embeddings.parrafos_enfen())

    referencia = referencia_de_notas(notas, control, lista_b)
    listas = hechas(archivo_referencia(), esquemas.HIBRIDO_REFERENCIA)
    pendientes = [(n,) for n in referencia if (n["medio"], n["id"]) not in listas]
    log.info(f"Referencia: {len(referencia)} notas · por puntuar {len(pendientes)}")
    _anexar_pendientes(
        archivo_referencia(), esquemas.HIBRIDO_REFERENCIA, pendientes,
        lambda n: fila_referencia(n, puntuador), "referencia",
    )  # fmt: skip
    param = parametros(leer_csv(archivo_referencia()))
    log.info(f"Parámetros de la referencia: {param}")

    lista = reranker.universo(notas, control, lista_b)
    listas = hechas(archivo(), esquemas.HIBRIDO)
    pendientes = [x for x in lista if (x[0]["medio"], x[0]["id"]) not in listas]
    log.info(f"Notas: {len(lista)} · por puntuar {len(pendientes)}")
    _anexar_pendientes(
        archivo(), esquemas.HIBRIDO, pendientes,
        lambda n, e, p, nueva: fila_puntuada(n, e, p, nueva, puntuador, param), "notas",
    )  # fmt: skip


def medir_consulta():
    """Paso 4: lo que hace la app con una consulta, con los párrafos ya preparados."""
    from radar.nlp.viabilidad import pico_memoria_gb

    param = parametros(leer_csv(archivo_referencia()))
    puntuador = Puntuador(embeddings.parrafos_enfen())
    notas = sorted(
        (n for n in leer_csv(config.DIR_NOTICIAS / "notas.csv") if n["sobre_nino"] == "1"),
        key=lambda n: (n["medio"], n["id"]),
    )[:CONSULTAS]
    tiempos = []
    for n in notas:
        mascara = candidatos.vigentes(puntuador.parrafos, n["fecha_publicacion"][:10])
        inicio = time.perf_counter()
        crudos = puntuador.crudos(reranker.texto_corto(n), mascara, "con")
        float(fusion(*crudos, param["con"]).max())
        tiempos.append(time.perf_counter() - inicio)
    pico, _ = pico_memoria_gb()
    mediana = round(statistics.median(tiempos), 3)
    pasa = mediana <= CONSULTA_MAXIMA_S and pico <= MEMORIA_MAXIMA_GB
    umbral = f"≤ {CONSULTA_MAXIMA_S} s y ≤ {MEMORIA_MAXIMA_GB} GB"
    detalle = f"memoria {pico:.2f} GB; la primera {tiempos[0]:.3f} s"
    return [criterio(PRUEBA_D + ": tiempo", "consulta", mediana, umbral, pasa, detalle)]


def resultado_de(medida, base, tiempo_ok):
    """(pasa, motivo) con la misma regla de C más el tiempo."""
    pasa, motivo = reranker.pasa_candidato(medida, base)
    if pasa and not tiempo_ok:
        return False, "no cumple tiempo y memoria"
    return pasa, motivo


def diferencia_de_control(filas, filas_base):
    """Mayor diferencia del coseno con la base, que debe ser la misma medida."""
    base = {(f["medio"], f["id"]): f for f in filas_base}
    diferencias = [
        abs(float(f["cos_sin"]) - float(base[(f["medio"], f["id"])]["sin"]))
        for f in filas
        if f.get("cos_sin") and base.get((f["medio"], f["id"]), {}).get("sin")
    ]
    return max(diferencias) if diferencias else None


def criterios():
    filas, filas_base = leer_csv(archivo()), leer_csv(reranker.archivo(reranker.BASE))
    validacion = leer_csv(config.DIR_NLP / "validacion.csv")
    tiempo = [f for f in validacion if f["prueba"] == PRUEBA_D + ": tiempo"]
    tiempo_ok = bool(tiempo) and reranker.es_si(tiempo[0]["pasa"])
    base, medida = reranker.medidas_de(filas_base), reranker.medidas_de(filas)
    control = diferencia_de_control(filas, filas_base)
    pasa, motivo = resultado_de(medida, base, tiempo_ok)
    e4, (bajo, alto) = medida["e4"]
    errores = sum(bool(f["error"]) for f in filas)
    parrafos = embeddings.parrafos_enfen()
    return [
        criterio(
            PRUEBA_D,
            "control: el coseno es el de la base",
            control,
            f"≤ {TOLERANCIA_CONTROL}",
            control is not None and control <= TOLERANCIA_CONTROL,
        ),
        criterio(PRUEBA_D, "notas con error", errores, 0, not errores),
        criterio(
            PRUEBA_D,
            "E4 en texto corto (adopta si pasa)",
            e4,
            f"≥ {base['e4'][0] + reranker.MARGEN:.4f}, sobre {base['e4'][1][1]}",
            pasa,
            f"IC95 {bajo}-{alto}; E3 {medida['e3'][0]}; notas nuevas {medida['nuevas'][0]}; {motivo}",
        ),
        criterio(
            INFO_D, f"base {reranker.BASE}", base["e4"][0], "", True, f"E3 {base['e3'][0]}; nuevas {base['nuevas'][0]}"
        ),
        criterio(INFO_D, "tipo elegido", str(reranker.tipos_elegidos(filas, parrafos)), "", True),
    ]


def main(argv=None):
    ap = argparse.ArgumentParser(description="D: minilm + BM25 en texto corto.")
    ap.add_argument("paso", choices=("puntuar", "tiempo", "criterios"))
    args = ap.parse_args(argv)
    registro = configurar(f"nlp-hibrido-{args.paso}")
    inicio = ahora()
    config.DIR_NLP.mkdir(parents=True, exist_ok=True)
    filas = []
    try:
        if args.paso == "puntuar":
            with sin_suspension():
                puntuar()
        else:
            filas = medir_consulta() if args.paso == "tiempo" else criterios()
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
