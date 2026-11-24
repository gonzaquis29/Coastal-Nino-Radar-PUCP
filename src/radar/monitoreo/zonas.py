"""Zonas oficiales de los avisos del Senamhi: polígonos por día y nivel, sin solaparse, y el nivel de cada distrito.

El servicio trae el nombre de quien elaboró cada aviso: se descarta (privacidad).
"""

import datetime as dt
import json
import re

from shapely import STRtree, make_valid, set_precision
from shapely.geometry import Point, mapping, shape
from shapely.ops import unary_union

from radar import config
from radar.comun.archivos import escribir_atomico, guardar_json, leer_json
from radar.monitoreo import vocabulario as vo

CAPA = "g_aviso:view_aviso"
NIVELES = {2: "amarillo", 3: "naranja", 4: "rojo"}  # el 1 es «sin aviso»
DIAS_MAXIMOS = 7
SIMPLIFICAR_CRUDO = 0.004  # grados (unos 400 m): solo para guardar menos
SIMPLIFICAR_WEB = 0.008
TODOS = "todo"


def leer_mapa(geojson):
    """{'dia', 'inicio', 'fin', 'niveles': {nivel: geometría}} de la respuesta del servicio; None si viene vacía."""
    rasgos = [f for f in geojson.get("features", []) if f.get("geometry")]
    if not rasgos:
        return None
    por_nivel = {}
    for f in rasgos:
        nivel = int(re.sub(r"\D", "", f["properties"].get("nivel") or "") or 0)
        if nivel in NIVELES:
            por_nivel.setdefault(nivel, []).append(make_valid(shape(f["geometry"])).simplify(SIMPLIFICAR_CRUDO))
    inicio, fin = (
        dt.datetime.fromisoformat(rasgos[0]["properties"][c].replace("Z", "+00:00")).astimezone(config.LIMA)
        for c in ("fech_ini", "fech_fin")
    )
    return {
        "dia": inicio.date().isoformat(),
        "inicio": inicio.strftime("%Y-%m-%dT%H:%M:%S"),
        "fin": fin.strftime("%Y-%m-%dT%H:%M:%S"),
        "niveles": {str(n): mapping(unary_union([make_valid(g) for g in gs])) for n, gs in por_nivel.items()},
    }


def descargar_mapa(cliente, aviso, mapa):
    anio = int(aviso["inicio"][:4])
    ruta = config.DIR_RAW_ZONAS / f"{anio}-{aviso['numero']}-{mapa}-{aviso['emision']}.json"
    if ruta.exists():
        return leer_json(ruta)
    parametros = {"service": "WFS", "version": "1.0.0", "request": "GetFeature", "typeName": CAPA,
                  "outputFormat": "application/json", "viewparams": f"qry:{aviso['numero']}_{mapa}_{anio}"}  # fmt: skip
    leido = leer_mapa(cliente.get(f"https://{config.HOST_SENAMHI_GIS}/geoserver/ows", params=parametros).json())
    if leido:
        guardar_json(ruta, leido)
    return leido


def excluyentes(por_nivel):
    """Cada punto queda solo en su nivel más alto."""
    salida, arriba = {}, None
    for n in sorted(por_nivel, reverse=True):
        g = make_valid(unary_union(por_nivel[n]))
        salida[n] = g if arriba is None else g.difference(arriba)
        arriba = g if arriba is None else unary_union([arriba, g])
    return salida


def coleccion(por_nivel):
    rasgos = []
    for n, g in sorted(excluyentes(por_nivel).items()):
        g = set_precision(make_valid(g.simplify(SIMPLIFICAR_WEB)), 0.001)
        if not g.is_empty:
            rasgos.append({"type": "Feature", "properties": {"n": n}, "geometry": mapping(g)})
    return {"type": "FeatureCollection", "features": rasgos}


def niveles_por_distrito(por_nivel, arbol, total):
    """Un dígito por distrito: 0 sin aviso; 2, 3 o 4 según su punto de referencia."""
    niveles = [0] * total
    for n in sorted(por_nivel):
        for g in por_nivel[n]:
            for i in arbol.query(g, predicate="intersects"):
                niveles[i] = max(niveles[i], n)
    return "".join(map(str, niveles))


def construir(cliente, avisos, hoy):
    """Escribe las zonas y devuelve ({numero: {dia: {...}}}, mapas leídos, fallos)."""
    lugares = vo.distritos()
    arbol = STRtree([Point(x[4], x[3]) for x in lugares])
    grupos, indice, leidos, fallos = {}, {}, 0, []
    for a in avisos:
        inicio, fin = (dt.date.fromisoformat(a[c][:10]) for c in ("inicio", "fin"))
        if fin < hoy:
            continue
        for mapa in range(1, min((fin - inicio).days + 1, DIAS_MAXIMOS) + 1):
            try:
                z = descargar_mapa(cliente, a, mapa)
            except Exception as e:  # un mapa que falla no detiene a los demás
                fallos.append(f"{a['numero']}/{mapa}: {type(e).__name__}")
                continue
            if not z:
                continue
            leidos += 1
            por_nivel = {int(n): [make_valid(shape(g))] for n, g in z["niveles"].items()}
            for nombre in (TODOS, a["peligro"], f"aviso-{a['numero']}"):
                grupo = grupos.setdefault(f"{nombre}_{z['dia']}", {})
                for n, gs in por_nivel.items():
                    grupo.setdefault(n, []).extend(gs)
            codigos = niveles_por_distrito(por_nivel, arbol, len(lugares))
            indice.setdefault(str(a["numero"]), {})[z["dia"]] = {
                "inicio": z["inicio"], "fin": z["fin"], "distritos": codigos,
            }  # fmt: skip
    for clave, por_nivel in grupos.items():
        texto = json.dumps(coleccion(por_nivel), separators=(",", ":"))
        escribir_atomico(config.DIR_ZONAS / f"{clave}.json", texto.encode("utf-8"))
    if not fallos and config.DIR_ZONAS.exists():
        for viejo in config.DIR_ZONAS.glob("*.json"):
            if viejo.stem not in grupos:
                viejo.unlink()
    return indice, leidos, fallos
