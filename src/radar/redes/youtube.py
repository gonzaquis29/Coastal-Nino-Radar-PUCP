"""Red social de audiencias en YouTube (pregunta 6 del README; docs/redes/youtube.md, aprobada el 22-nov).

Uso: python -m radar.redes.youtube   # sin red; usa la sal de los seudónimos y las variables del modelo de engagement

Por canal (con seudónimos) escribe data/processed/youtube/AAAA-MM-DD_red-canales.csv, que vence con los datos de
YouTube. Los agregados, sin ids, van a data/processed/red/youtube-*.csv.
"""

import argparse
import collections
import concurrent.futures
import datetime as dt
import logging
import os
import statistics
import sys
import time

import networkx as nx
import numpy as np

from radar import config
from radar.comun.archivos import escribir_csv, leer_csv
from radar.comun.registro import configurar
from radar.comun.texto import ahora
from radar.noticias.viabilidad import criterio, guardar, reporte
from radar.redes import audiencias as au
from radar.redes import esquemas
from radar.youtube import almacen, canales, filtro, privacidad

log = logging.getLogger(__name__)

PRUEBA = "Red social de YouTube"
INFO = "Red social de YouTube (informativo)"
SEMILLA = config.SEMILLA_MUESTRAS
MINIMO_AUTORES_NODO = 5
MINIMO_AUTORES_CRUCE = 10  # pregunta 6
COMPONENTE_MINIMO = 30  # R1
NULOS = 500  # R2 y R4
PERCENTIL_NULO = 95  # R2
NMI_MINIMO = 0.50  # R3
SEMILLAS_LOUVAIN = 10  # R3
MAXIMO_CANALES_POR_AUTOR = 10  # R4
REPLICAS = 1000  # bootstrap de R5 y R6
PERMUTACIONES = 1000  # R7
VIDEOS_MINIMOS_R6 = 3
FDR = 0.05  # R8
MEDIO, OTROS, OFICIAL = canales.MEDIO, canales.OTROS, canales.OFICIAL

_base_del_proceso = {}


# ---------------------------------------------------------------- datos


def autores_por_canal():
    """{canal: autores} sin los comentarios del dueño de algún canal de la muestra, y cuántos se quitaron."""
    videos, por_id = almacen.ultimos("videos"), almacen.ultimos("canales")
    canal_de = {v["id"]: v["canal"] for v in videos.values() if filtro.pasa(v, por_id.get(v["canal"]))}
    seudonimos_de_canales = {privacidad.seudonimo(c) for c in set(canal_de.values())}
    salida, duenos = collections.defaultdict(set), 0
    for c in almacen.ultimos("comentarios").values():
        canal = canal_de.get(c["video"])
        if canal is None or not c["autor"]:
            continue
        if c["autor"] in seudonimos_de_canales:
            duenos += 1
            continue
        salida[canal].add(c["autor"])
    return dict(salida), por_id, duenos


def cercania_por_canal():
    """{canal: (media del coseno, n.° de videos)} de las variables del modelo de engagement."""
    previos = almacen.archivos("engagement-variables", bases=(config.DIR_YOUTUBE,))
    if not previos:
        raise SystemExit("Faltan las variables del modelo de engagement: python -m radar.modelos.engagement variables")
    cosenos = collections.defaultdict(list)
    for f in leer_csv(previos[-1]):
        if f["coseno"]:
            cosenos[f["canal"]].append(float(f["coseno"]))
    return {c: (float(np.mean(v)), len(v)) for c, v in cosenos.items()}


# ---------------------------------------------------------------- nulos en paralelo


def _iniciar(bases):
    _base_del_proceso.update(bases)


def _un_nulo(tarea):
    nombre, semilla, objetivos = tarea
    return nombre, au.nulo(_base_del_proceso[nombre], semilla, objetivos)


def correr_nulos(bases, tareas):
    """{nombre: [resultado]}; usa núcleos − 1 procesos y muestra el avance con tiempo estimado."""
    procesos = max(1, (os.cpu_count() or 2) - 1)
    resultados, inicio, hechos = collections.defaultdict(list), time.monotonic(), 0
    with concurrent.futures.ProcessPoolExecutor(procesos, initializer=_iniciar, initargs=(bases,)) as ejecutor:
        for nombre, resultado in ejecutor.map(_un_nulo, tareas, chunksize=8):
            resultados[nombre].append(resultado)
            hechos += 1
            if hechos % 100 == 0 or hechos == len(tareas):
                ritmo = (time.monotonic() - inicio) / hechos
                log.info(f"  nulos {hechos}/{len(tareas)}; faltan ~{ritmo * (len(tareas) - hechos) / 60:.1f} min")
    return resultados


# ---------------------------------------------------------------- medidas


def centralidad(grafo):
    fuerza = dict(grafo.degree(weight=au.PESO))
    pagerank = nx.pagerank(grafo, weight=au.PESO)
    intermediacion = nx.betweenness_centrality(grafo, weight=au.DISTANCIA)
    return fuerza, pagerank, intermediacion


def _mediana(valores):
    return round(statistics.median(valores), 5) if valores else ""


def resumen_por_tipo(nodos, tipo_de, autores, fuerza, pagerank, intermediacion):
    filas = []
    for tipo in (MEDIO, OTROS, OFICIAL):
        grupo = [n for n in nodos if tipo_de[n] == tipo]
        filas.append({
            "tipo": tipo, "canales": len(grupo), "autores_mediana": _mediana([autores[n] for n in grupo]),
            "fuerza_mediana": _mediana([fuerza[n] for n in grupo]) if len(grupo) > 1 else "",
            "pagerank_mediana": _mediana([pagerank[n] for n in grupo]) if len(grupo) > 1 else "",
            "intermediacion_mediana": _mediana([intermediacion[n] for n in grupo]) if len(grupo) > 1 else "",
        })  # fmt: skip
    return filas


def resumen_comunidades(comunidades, tipo_de, pais_de, autores):
    filas = []
    for k, comunidad in enumerate(sorted(comunidades, key=len, reverse=True)):
        tipos = collections.Counter(tipo_de[n] for n in comunidad)
        paises = collections.Counter(pais_de[n] or "sin país" for n in comunidad)
        filas.append({
            "comunidad": k, "canales": len(comunidad), "medios": tipos[MEDIO], "otros": tipos[OTROS],
            "oficiales": tipos[OFICIAL], "peru": paises["PE"], "sin_pais": paises["sin país"],
            "otros_paises": len(comunidad) - paises["PE"] - paises["sin país"],
            "pais_principal": paises.most_common(1)[0][0], "autores_mediana": _mediana([autores[n] for n in comunidad]),
        })  # fmt: skip
    return filas


def texto_spearman(resultado):
    rho, (inf, sup), p, n = resultado
    return f"rho {rho:.3f}, IC 95 % {inf:.3f} a {sup:.3f}, p {p:.3f}, n {n}"


def pregunta_6(candidatos, cercania, cruce_obs, cruce_nulo, semilla):
    x = [cercania[c][0] for c in candidatos]
    y = [cruce_obs[c] - cruce_nulo[c] for c in candidatos]
    return au.spearman_con_ic(x, y, REPLICAS, semilla)


# ---------------------------------------------------------------- todo junto


def medir():
    crudos, por_id, duenos = autores_por_canal()
    tipos = canales.tipos()
    cercania = cercania_por_canal()
    filtrados = au.filtrar(crudos, MINIMO_AUTORES_NODO)
    bipartita = au.Bipartita.de_conjuntos(filtrados)
    nombres = bipartita.canales
    tipo_de = {i: (tipos.get(c) or {}).get("tipo", OTROS) for i, c in enumerate(nombres)}
    pais_de = {i: (por_id.get(c) or {}).get("pais", "") for i, c in enumerate(nombres)}
    autores = {i: len(filtrados[c]) for i, c in enumerate(nombres)}
    log.info(f"{len(crudos)} canales con comentarios; {duenos} comentarios de dueños quitados")
    log.info(f"{len(nombres)} canales con ≥ {MINIMO_AUTORES_NODO} autores; {len(bipartita.filas)} autores")

    grafo = au.proyectar(bipartita)
    componente = au.componente_mayor(grafo)
    nodos = sorted(componente)
    comunidades, q = au.louvain(componente, SEMILLA)

    medios = {i for i in nodos if tipo_de[i] == MEDIO}
    medio_mayor = max(medios, key=lambda i: autores[i]) if medios else None
    objetivos = (medios, medios - {medio_mayor})
    cruce_obs = [au.cruce(bipartita, o) for o in objetivos]

    sin_activos = au.Bipartita.de_conjuntos(au.filtrar(filtrados, 1, MAXIMO_CANALES_POR_AUTOR))
    grafo_sin = au.componente_mayor(au.proyectar(sin_activos))
    _, q_sin = au.louvain(grafo_sin, SEMILLA)

    tareas = [("completa", SEMILLA + k, objetivos) for k in range(NULOS)]
    tareas += [("sin_activos", SEMILLA + NULOS + k, ()) for k in range(NULOS)]
    nulos = correr_nulos({"completa": bipartita, "sin_activos": sin_activos}, tareas)
    q_nulo = np.array([r["q"] for r in nulos["completa"]])
    q_nulo_sin = np.array([r["q"] for r in nulos["sin_activos"]])
    cruce_nulo = [np.mean([r["cruces"][k] for r in nulos["completa"]], axis=0) for k in range(len(objetivos))]

    # R3
    lpa = au.propagacion(componente, SEMILLA)
    nmi_lpa = au.nmi(comunidades, lpa, nodos)
    por_semilla = [au.louvain(componente, SEMILLA + s)[0] for s in range(SEMILLAS_LOUVAIN)]
    nmi_semillas = statistics.median(
        au.nmi(a, b, nodos) for k, a in enumerate(por_semilla) for b in por_semilla[k + 1 :]
    )

    # R5 y R6
    nombre_de = dict(enumerate(nombres))
    cerca = {i: cercania[nombre_de[i]] for i in nodos if nombre_de[i] in cercania}
    candidatos = [i for i in nodos if tipo_de[i] == OTROS and autores[i] >= MINIMO_AUTORES_CRUCE and i in cerca]
    r5 = pregunta_6(candidatos, cerca, cruce_obs[0], cruce_nulo[0], SEMILLA)
    r6_sin_mayor = pregunta_6(candidatos, cerca, cruce_obs[1], cruce_nulo[1], SEMILLA)
    con_videos = [i for i in candidatos if cerca[i][1] >= VIDEOS_MINIMOS_R6]
    r6_videos = pregunta_6(con_videos, cerca, cruce_obs[0], cruce_nulo[0], SEMILLA)
    signos = {np.sign(r[0]) for r in (r5, r6_sin_mayor, r6_videos) if not np.isnan(r[0])}

    # R7 y R8
    r7, p7 = au.asortatividad_permutada(componente, {i: v[0] for i, v in cerca.items()}, PERMUTACIONES, SEMILLA)
    grados = np.asarray(bipartita.matriz().sum(axis=0)).ravel()
    fondo = au.backbone(componente, len(bipartita.filas), grados, FDR)
    comunidad_de = {n: k for k, c in enumerate(comunidades) for n in c}
    dentro = sum(comunidad_de[i] == comunidad_de[j] for i, j in fondo)

    fuerza, pagerank, intermediacion = centralidad(componente)
    p95, p95_sin = (float(np.percentile(v, PERCENTIL_NULO)) for v in (q_nulo, q_nulo_sin))
    filas = [
        criterio(PRUEBA, "R1 componente mayor (≥ 5 autores, sin dueños)", len(nodos), f">= {COMPONENTE_MINIMO}",
                 len(nodos) >= COMPONENTE_MINIMO, f"{componente.number_of_edges()} aristas; "
                 f"{dict(collections.Counter(tipo_de[n] for n in nodos))}"),
        criterio(PRUEBA, "R2 Q de Louvain frente a 500 nulos curveball", round(q, 4), f"> p95 del nulo ({p95:.4f})",
                 q > p95, f"nulo: media {q_nulo.mean():.4f}, máximo {q_nulo.max():.4f}; "
                 f"{len(comunidades)} comunidades"),
        criterio(PRUEBA, "R3 estabilidad (NMI con propagación de etiquetas / mediana entre semillas)",
                 f"{nmi_lpa:.3f} / {nmi_semillas:.3f}", f">= {NMI_MINIMO} en ambos",
                 nmi_lpa >= NMI_MINIMO and nmi_semillas >= NMI_MINIMO, f"{len(lpa)} comunidades por propagación"),
        criterio(PRUEBA, f"R4 sin autores de más de {MAXIMO_CANALES_POR_AUTOR} canales (componente / Q)",
                 f"{grafo_sin.number_of_nodes()} / {q_sin:.4f}", f">= {COMPONENTE_MINIMO} y > p95 ({p95_sin:.4f})",
                 grafo_sin.number_of_nodes() >= COMPONENTE_MINIMO and q_sin > p95_sin,
                 f"{len(bipartita.filas) - len(sin_activos.filas)} autores quitados"),
        criterio(INFO, "R5 cercanía media frente al cruce excedente con medios (otros)", round(r5[0], 3),
                 "se afirma solo si el IC no incluye el 0", True,
                 texto_spearman(r5) + ("; asociación medible" if r5[1][0] > 0 or r5[1][1] < 0 else
                                       "; sin asociación medible")),
        criterio(INFO, "R6 sin el medio más grande / solo con ≥ 3 videos con cercanía",
                 f"{r6_sin_mayor[0]:.3f} / {r6_videos[0]:.3f}", "mismo signo que R5", True,
                 f"{texto_spearman(r6_sin_mayor)} | {texto_spearman(r6_videos)}; "
                 + ("signo estable" if len(signos) == 1 else "cambia el signo: R5 no se interpreta")),
        criterio(INFO, "R7 asortatividad de la cercanía (Pearson ponderado)", round(r7, 3),
                 f"{PERMUTACIONES} permutaciones", True, f"valor p de dos colas {p7:.3f}; {len(cerca)} canales"),
        criterio(INFO, "R8 aristas del backbone (FDR 5 %) dentro de una comunidad", f"{dentro}/{len(fondo)}",
                 "informativo", True, f"{len({n for e in fondo for n in e})} canales en el backbone"),
    ]  # fmt: skip

    detalle_canal = []
    for i, c in enumerate(nombres):
        en = i in componente
        detalle_canal.append({
            "canal": privacidad.seudonimo(c), "tipo": tipo_de[i], "pais": pais_de[i], "autores": autores[i],
            "en_componente": en, "comunidad": comunidad_de.get(i, ""),
            "fuerza": round(fuerza[i], 5) if en else "", "pagerank": round(pagerank[i], 6) if en else "",
            "intermediacion": round(intermediacion[i], 6) if en else "",
            "cercania": round(cerca[i][0], 4) if i in cerca else "",
            "videos_cercania": cerca[i][1] if i in cerca else "",
            "cruce": round(float(cruce_obs[0][i]), 4), "cruce_nulo": round(float(cruce_nulo[0][i]), 4),
            "cruce_sin_mayor": round(float(cruce_obs[1][i]), 4),
            "cruce_nulo_sin_mayor": round(float(cruce_nulo[1][i]), 4),
        })  # fmt: skip
    return {
        "validacion": filas,
        "canales": detalle_canal,
        "tipos": resumen_por_tipo(nodos, tipo_de, autores, fuerza, pagerank, intermediacion),
        "comunidades": resumen_comunidades(comunidades, tipo_de, pais_de, autores),
    }


def main(argv=None):
    argparse.ArgumentParser(description="Red social de audiencias en YouTube.").parse_args(argv)
    registro = configurar("redes-youtube")
    inicio = ahora()
    try:
        resultado = medir()
    except (almacen.Vencido, privacidad.SinSal) as e:
        log.error(str(e))
        return 1
    except KeyboardInterrupt:
        log.info("Cortado: no se escribió nada (los nulos se recalculan completos, con semillas fijas).")
        return 130
    corte = max(dt.date.fromisoformat(r["descargado"]) for r in almacen.ultimos("videos").values())
    escribir_csv(almacen.ruta("red-canales", fecha=corte, extension="csv", base=config.DIR_YOUTUBE),
                 esquemas.YOUTUBE_CANALES, resultado["canales"])  # fmt: skip
    escribir_csv(config.DIR_RED / "youtube-tipos.csv", esquemas.YOUTUBE_TIPOS, resultado["tipos"])
    escribir_csv(config.DIR_RED / "youtube-comunidades.csv", esquemas.YOUTUBE_COMUNIDADES, resultado["comunidades"])
    guardar(resultado["validacion"], config.DIR_RED / "youtube-validacion.csv")
    reporte(resultado["validacion"], [], inicio)
    log.info(f"Escrito: {config.DIR_RED.relative_to(config.RAIZ)} · registro: {registro.relative_to(config.RAIZ)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
