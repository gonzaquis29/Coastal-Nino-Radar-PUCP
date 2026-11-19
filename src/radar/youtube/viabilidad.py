"""Prueba de viabilidad de YouTube (criterios fijados el 16-nov antes de ver datos; docs/youtube/definicion.md, §7).

Y1, Y2 y Y4 se miden desde el día 1; Y3 y Y5, con la descarga del corte. Solo se guardan agregados, sin ids ni
nombres, en data/processed/youtube/validacion.csv (no vence: no tiene datos de la API por video).

Uso: python -m radar.youtube.viabilidad
"""

import collections
import datetime as dt
import logging
import sys

from radar import config
from radar.comun.archivos import escribir_csv, leer_csv
from radar.comun.registro import configurar
from radar.comun.texto import ahora
from radar.noticias.viabilidad import criterio, reporte
from radar.youtube import almacen, canales, filtro

log = logging.getLogger(__name__)

PRUEBA = "YouTube: viabilidad"
INFO = "YouTube (informativo)"
VIDEOS_MINIMOS = 300  # Y1
COMENTARIOS_MINIMOS = 30  # Y2
VIDEOS_CON_COMENTARIOS = 100  # Y2
COMPONENTE_MINIMO = 30  # Y3
SIN_AMBIGUEDAD = 0.70  # Y4
DIAS_MINIMOS = 14  # Y5: la tasa de engagement de un video más nuevo todavía es inestable
ENTRENAMIENTO_MINIMO, PRUEBA_MINIMA = 150, 50  # Y5
FIN_ENTRENAMIENTO = dt.date(2026, 8, 31)
COLUMNAS = ("prueba", "criterio", "valor", "umbral", "pasa", "detalle")


def componente_mayor(aristas_autor_canal):
    """Tamaño del mayor componente conectado de la red canal–canal (dos canales se unen si comparten un
    comentarista). Unión-búsqueda sobre los canales que comentó cada autor."""
    padre = {}

    def raiz(x):
        while padre[x] != x:
            padre[x] = padre[padre[x]]
            x = padre[x]
        return x

    por_autor = collections.defaultdict(set)
    for autor, canal in aristas_autor_canal:
        if autor:
            por_autor[autor].add(canal)
    for canales_autor in por_autor.values():
        lista = sorted(canales_autor)
        for c in lista:
            padre.setdefault(c, c)
        for c in lista[1:]:
            a, b = raiz(lista[0]), raiz(c)
            if a != b:
                padre[b] = a
    conteo = collections.Counter(raiz(c) for c in padre)
    # canales sin ninguna arista no cuentan: un componente de un solo canal no es red
    return max((n for n in conteo.values() if n > 1), default=0)


def medir(videos, canales_por_id, comentarios, tipos, corte_hecho):
    filas = []
    del_periodo = [v for v in videos.values() if filtro.pasa(v, canales_por_id.get(v["canal"]))]
    filas.append(criterio(PRUEBA, "Y1 videos que pasan el filtro", len(del_periodo), f">= {VIDEOS_MINIMOS}",
                          len(del_periodo) >= VIDEOS_MINIMOS))  # fmt: skip

    ids = {v["id"] for v in del_periodo}
    por_video = collections.Counter(c["video"] for c in comentarios.values() if c["video"] in ids)
    con_comentarios = sum(n >= COMENTARIOS_MINIMOS for n in por_video.values())
    segun_conteo = sum((v["comentarios"] or 0) >= COMENTARIOS_MINIMOS for v in del_periodo)
    nombre_y2 = f"Y2 videos con >= {COMENTARIOS_MINIMOS} comentarios descargados (con respuestas)"
    pasa_y2 = con_comentarios >= VIDEOS_CON_COMENTARIOS
    detalle_y2 = f"según el conteo de la API serían {segun_conteo}"
    filas.append(criterio(PRUEBA, nombre_y2, con_comentarios, f">= {VIDEOS_CON_COMENTARIOS}", pasa_y2, detalle_y2))

    canales_muestra = {v["canal"] for v in del_periodo}
    clasificados = [tipos[c] for c in canales_muestra if c in tipos]
    claros = sum(f["ambiguo"] in ("0", False) for f in clasificados)
    proporcion = claros / len(clasificados) if clasificados else 0.0
    por_tipo = collections.Counter(f["tipo"] for f in clasificados)
    filas.append(criterio(PRUEBA, "Y4 canales sin ambigüedad", round(proporcion, 3), f">= {SIN_AMBIGUEDAD}",
                          bool(clasificados) and proporcion >= SIN_AMBIGUEDAD,
                          f"{len(clasificados)} de {len(canales_muestra)} clasificados; {dict(por_tipo)}"))  # fmt: skip

    if corte_hecho:
        canal_de = {v["id"]: v["canal"] for v in del_periodo}
        mayor = componente_mayor((c["autor"], canal_de[c["video"]]) for c in comentarios.values() if c["video"] in ids)
        filas.append(criterio(PRUEBA, "Y3 componente conectado de la red canal–canal", mayor,
                              f">= {COMPONENTE_MINIMO}", mayor >= COMPONENTE_MINIMO))  # fmt: skip
        entrenamiento = prueba = 0
        for v in del_periodo:
            publicado = filtro.fecha_lima(v["publicado"])
            if (dt.date.fromisoformat(v["descargado"]) - publicado).days < DIAS_MINIMOS:
                continue
            if publicado <= FIN_ENTRENAMIENTO:
                entrenamiento += 1
            else:
                prueba += 1
        filas.append(criterio(PRUEBA, "Y5 videos para el modelo (entrenamiento / prueba)",
                              f"{entrenamiento} / {prueba}", f">= {ENTRENAMIENTO_MINIMO} / >= {PRUEBA_MINIMA}",
                              entrenamiento >= ENTRENAMIENTO_MINIMO and prueba >= PRUEBA_MINIMA))  # fmt: skip
    return filas


def informativo(busquedas, videos, canales_por_id):
    filas = []
    for orden in ("date", "relevance"):
        grupo = [b for b in busquedas if b["orden"] == orden]
        if grupo:
            saturadas = sum(b["saturada"] for b in grupo)
            filas.append(criterio(INFO, f"búsquedas saturadas ({orden})", f"{saturadas} de {len(grupo)}", "-", True))
    total = len(videos)
    if total:
        motivos = collections.Counter()
        for v in videos.values():
            c = canales_por_id.get(v["canal"])
            if not filtro.en_periodo(v):
                motivos["fuera del período"] += 1
            elif not filtro.sobre_el_nino(v):
                motivos["no menciona El Niño"] += 1
            elif not filtro.de_peru(v, c):
                motivos["no es de Perú"] += 1
        filas.append(criterio(INFO, "videos encontrados y descartes", total, "-", True, str(dict(motivos))))
    return filas


def guardar(filas, ruta=None):
    ruta = ruta or config.DIR_YOUTUBE / "validacion.csv"
    corridas = {f["prueba"] for f in filas}
    previas = [f for f in leer_csv(ruta) if f["prueba"] not in corridas]
    escribir_csv(ruta, COLUMNAS, previas + filas)


def main(argv=None):
    inicio = ahora()
    configurar("youtube-viabilidad")
    try:
        busquedas = list(almacen.leer("busquedas"))
        videos = almacen.ultimos("videos")
        canales_por_id = almacen.ultimos("canales")
        comentarios = almacen.ultimos("comentarios")
        tipos = canales.tipos()
    except almacen.Vencido as e:
        log.error(str(e))
        return 1
    if not videos:
        log.error("No hay videos descargados: corre antes python -m radar.youtube.descarga dia1")
        return 1
    alertas = []
    if not tipos:
        alertas.append("Sin tipos de canal: corre python -m radar.youtube.canales (Y4 queda en 0).")
    corte_hecho = any(b.get("etapa") == "corte" for b in busquedas)
    if not corte_hecho:
        alertas.append("Y3 y Y5 se miden con la descarga del corte.")
    filas = medir(videos, canales_por_id, comentarios, tipos, corte_hecho) + informativo(
        busquedas, videos, canales_por_id
    )
    guardar(filas)
    reporte(filas, alertas, inicio)
    return 0


if __name__ == "__main__":
    sys.exit(main())
