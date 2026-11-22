"""Validación de la cercanía en videos (docs/modelos/engagement.md, sección 8, aprobada el 22-nov): la misma variable
del modelo frente a un control positivo (canales oficiales) y uno negativo (videos sin El Niño ni términos del filtro).
Se corre con `python -m radar.modelos.engagement cercania`; no guarda textos."""

import logging
import os
import statistics
import time

import numpy as np

from radar import config
from radar.comun.archivos import leer_csv
from radar.modelos import rasgos as rg
from radar.noticias.rasgos import terminos_cuerpo
from radar.noticias.viabilidad import criterio
from radar.youtube import almacen, canales, filtro

log = logging.getLogger(__name__)

PRUEBA = "Cercanía en videos"
INFO = "Cercanía en videos (informativo)"
AUC_MINIMO = 0.80  # V1: el umbral de E3
PERCENTIL_POSITIVO, PERCENTIL_NEGATIVO = 25, 75  # V2: sin cruce, como S2
REPLICAS = 1000
SEMILLA = config.SEMILLA_MUESTRAS
AVANCE = 200


def controles():
    """{control: [video]} con los videos de cada control (un video puede estar en P2 y no en P, nunca en P y en N)."""
    videos, por_id, tipos = almacen.ultimos("videos"), almacen.ultimos("canales"), canales.tipos()
    salida = {"P": [], "P2": [], "N": [], "N2": []}
    for v in videos.values():
        if not filtro.en_periodo(v):
            continue
        tipo = (tipos.get(v["canal"]) or {}).get("tipo", canales.OTROS)
        if filtro.pasa(v, por_id.get(v["canal"])):
            if tipo == canales.OFICIAL:
                salida["P"].append(v)
            elif rg.enlaza_gob(v.get("enlaces")):
                salida["P2"].append(v)
        elif not filtro.sobre_el_nino(v):
            salida["N2"].append(v)
            if not terminos_cuerpo(f"{v.get('titulo') or ''}\n{v.get('descripcion') or ''}"):
                salida["N"].append(v)
    return salida


def cosenos(videos_por_control):
    """{control: (cosenos, canales, insuficientes)}; cada video se mide una sola vez."""
    os.environ.setdefault("HF_HUB_OFFLINE", "1")
    from radar.nlp import semaforo

    medidor = semaforo.Semaforo()
    unicos = {v["id"]: v for vs in videos_por_control.values() for v in vs}
    medidos, inicio = {}, time.monotonic()
    for k, v in enumerate(unicos.values(), 1):
        texto = rg.texto_para_distancia(v.get("titulo"), v.get("descripcion"))
        medidos[v["id"]] = medidor.medir(texto, filtro.fecha_lima(v["publicado"]).isoformat())["coseno"]
        if k % AVANCE == 0 or k == len(unicos):
            ritmo = (time.monotonic() - inicio) / k
            log.info(f"  {k}/{len(unicos)} videos; faltan ~{ritmo * (len(unicos) - k) / 60:.1f} min")
    salida = {}
    for control, vs in videos_por_control.items():
        con = [v for v in vs if medidos[v["id"]] is not None]
        salida[control] = (np.array([medidos[v["id"]] for v in con]), [v["canal"] for v in con], len(vs) - len(con))
    return salida


def mediana_variables(tipo):
    previos = almacen.archivos("engagement-variables", bases=(config.DIR_YOUTUBE,))
    valores = (
        [float(f["coseno"]) for f in leer_csv(previos[-1]) if f["tipo"] == tipo and f["coseno"]] if previos else []
    )
    return statistics.median(valores) if valores else float("nan")


def validar():
    medidas = cosenos(controles())
    p, canales_p, fuera_p = medidas["P"]
    n, canales_n, fuera_n = medidas["N"]

    def comparar(a, b):
        return rg.auc_por_grupo(medidas[a][0], medidas[a][1], medidas[b][0], medidas[b][1], REPLICAS, SEMILLA)

    v1, (i1, s1) = comparar("P", "N")
    p25, p75 = float(np.percentile(p, PERCENTIL_POSITIVO)), float(np.percentile(n, PERCENTIL_NEGATIVO))
    v3, (i3, s3) = comparar("P", "N2")
    v4, (i4, s4) = comparar("P2", "N")
    medianas = {"oficial": float(np.median(p)), "medio": mediana_variables(canales.MEDIO),
                "otros": mediana_variables(canales.OTROS), "negativo": float(np.median(n))}  # fmt: skip
    orden = medianas["oficial"] > max(medianas["medio"], medianas["otros"]) > medianas["negativo"]
    detalle = f"P {len(p)} videos de {len(set(canales_p))} canales; N {len(n)} de {len(set(canales_n))}"
    return [
        criterio(PRUEBA, "V1 AUC del positivo (oficiales) frente al negativo", round(v1, 3), f">= {AUC_MINIMO}",
                 v1 >= AUC_MINIMO, f"IC 95 % por canal {i1:.3f} a {s1:.3f}; {detalle}; "
                 f"insuficientes: P {fuera_p}, N {fuera_n}"),
        criterio(PRUEBA, "V2 p25 del positivo frente al p75 del negativo", f"{p25:.3f} / {p75:.3f}", "p25 > p75",
                 p25 > p75),
        criterio(INFO, "V3 AUC del positivo frente al negativo difícil (todos los descartados)", round(v3, 3),
                 "informativo", True, f"IC 95 % {i3:.3f} a {s3:.3f}; N2 {len(medidas['N2'][0])} videos"),
        criterio(INFO, "V4 AUC de los que enlazan a .gob.pe (no oficiales) frente al negativo", round(v4, 3),
                 "informativo", True, f"IC 95 % {i4:.3f} a {s4:.3f}; P2 {len(medidas['P2'][0])} videos"),
        criterio(INFO, "V5 orden de las medianas: oficial > medio y otros > negativo", "sí" if orden else "no",
                 "informativo", True, "; ".join(f"{k} {v:.3f}" for k, v in medianas.items())),
    ]  # fmt: skip
