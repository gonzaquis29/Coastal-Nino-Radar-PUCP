"""Zonas oficiales de los avisos de Senamhi (polígonos por día y nivel) -> web/zonas/*.json

Fuente: WFS público de IDESEP-Senamhi, capa g_aviso:view_aviso (Fees: NONE, AccessConstraints: NONE).
Se descarta el campo 'respons' (identifica a una persona). 2 s entre peticiones; los mapas ya bajados no se repiten.
"""
import json
from datetime import date, datetime, timedelta
from pathlib import Path

import pandas as pd
from shapely import STRtree, make_valid, set_precision
from shapely.geometry import Point, mapping, shape
from shapely.ops import unary_union

import fuentes
import geo

PROC = Path("data/processed")
CRUDO = Path("data/raw/zonas")
WEB = Path("web/zonas")
WFS = "https://idesep.senamhi.gob.pe/geoserver/ows"
NIVEL = {"Nivel 2": 2, "Nivel 3": 3, "Nivel 4": 4}  # amarillo, naranja, rojo (Nivel 1 = sin aviso)


def _local(s):
    return pd.Timestamp(s).tz_convert("America/Lima").tz_localize(None)


def bajar(av: int, mp: int, anio: int, emision: str) -> dict:
    """{'ini','fin','niveles': {2: geom, ...}} de un mapa diario; {} si no existe."""
    f = CRUDO / f"{anio}_{av}_{mp}_{emision}.json"
    if f.exists():
        return json.loads(f.read_text(encoding="utf8"))
    r = fuentes.get(WFS, params={"service": "WFS", "version": "1.0.0", "request": "GetFeature", "outputFormat": "application/json",
                                 "typeName": "g_aviso:view_aviso", "viewparams": f"qry:{av}_{mp}_{anio}"})
    feats = [x for x in r.json()["features"] if x["geometry"]]
    if not feats:
        return {}
    por = {}
    for x in feats:
        n = NIVEL.get(x["properties"]["nivel"])
        if n:
            por.setdefault(n, []).append(make_valid(shape(x["geometry"])).simplify(0.004))
    p = feats[0]["properties"]
    out = {"ini": str(_local(p["fech_ini"])), "fin": str(_local(p["fech_fin"])),
           "niveles": {str(n): mapping(unary_union([make_valid(g) for g in gs])) for n, gs in por.items()}}
    CRUDO.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(out), encoding="utf8")
    return out


def _excluyentes(por: dict) -> dict:
    """Cada punto queda solo en su nivel más alto."""
    out, arriba = {}, None
    for n in (4, 3, 2):
        if n in por:
            g = make_valid(unary_union(por[n]))
            out[n] = g if arriba is None else g.difference(arriba)
            arriba = g if arriba is None else unary_union([arriba, g])
    return out


def _guardar(nombre: str, por: dict):
    fs = []
    for n, g in sorted(_excluyentes(por).items()):
        g = set_precision(make_valid(g.simplify(0.008)), 0.001)
        if not g.is_empty:
            fs.append({"type": "Feature", "properties": {"n": n}, "geometry": mapping(g)})
    (WEB / f"{nombre}.json").write_text(json.dumps({"type": "FeatureCollection", "features": fs}, separators=(",", ":")), encoding="utf8")


def construir(eventos: pd.DataFrame) -> int:
    """Baja los mapas de los avisos no vencidos y escribe zonas e índice por distrito. Devuelve mapas disponibles."""
    WEB.mkdir(parents=True, exist_ok=True)
    avisos = eventos[(eventos.fuente == "SENAMHI") & (pd.to_datetime(eventos.fin) >= pd.Timestamp(date.today()))]
    d = geo.distritos()
    puntos = [Point(x, y) for x, y in zip(d.lon, d.lat)]
    grupos, indice, n_mapas, fallos = {}, {}, 0, []
    for a in avisos.itertuples():
        num = int(a.id.split("-")[1])
        dias = (pd.Timestamp(a.fin).normalize() - pd.Timestamp(a.inicio).normalize()).days + 1
        for mp in range(1, min(dias, 7) + 1):
            try:
                z = bajar(num, mp, pd.Timestamp(a.inicio).year, str(a.publicado)[:10])
            except Exception as e:
                fallos.append(f"{num}/{mp}: {type(e).__name__}")
                continue
            if not z:
                continue
            n_mapas += 1
            dia = z["ini"][:10]
            por = {int(k): [make_valid(shape(g))] for k, g in z["niveles"].items()}
            _guardar(f"{a.id}_{dia}", por)
            for clave in (f"todo_{dia}", f"{a.peligro}_{dia}"):
                for n, gs in por.items():
                    grupos.setdefault(clave, {}).setdefault(n, []).extend(gs)
            niv = [0] * len(d)
            for n in sorted(por):
                for g in por[n]:
                    arb = STRtree(puntos)
                    for i in arb.query(g, predicate="intersects"):
                        niv[i] = max(niv[i], n)
            indice.setdefault(a.id, {})[dia] = {"ini": z["ini"], "fin": z["fin"], "d": "".join(map(str, niv))}
    for clave, por in grupos.items():
        _guardar(clave, por)
    validos = {f"{c}.json" for c in grupos} | {f"{a}_{x}.json" for a, v in indice.items() for x in v}
    if not fallos:
        for f in WEB.glob("*.json"):
            if f.name not in validos:
                f.unlink()
    (PROC / "zonas.json").write_text(json.dumps(indice), encoding="utf8")
    if fallos:
        raise RuntimeError("mapas sin descargar: " + ", ".join(fallos))
    return n_mapas
