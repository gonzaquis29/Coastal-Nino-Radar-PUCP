"""Límites y lugares del mapa -> web/public/mapa/base.json y lugares.json. Ya están en el repo: no hace falta correrlo.

Fuentes: geoBoundaries PER ADM2 (IGN / OCHA, CC BY 3.0 IGO) en data/raw/limites/adm2.geojson y
github.com/jmcastagnetto/ubigeo-peru-aumentado (MIT) en data/raw/ubigeo/distrito.csv.

Uso: python -m radar.monitoreo.mapa_base
"""

import collections
import json

from shapely import STRtree, make_valid, set_precision
from shapely.geometry import Point, box, mapping, shape
from shapely.ops import unary_union

from radar import config
from radar.comun.archivos import escribir_atomico, leer_csv

MARCO = (-130, -60, -20, 40)  # lo que se oscurece fuera del Perú
CIERRE = 0.004  # grados: une las provincias vecinas sin dejar rendijas


def rasgo(geometria, **propiedades):
    geometria = set_precision(make_valid(geometria.simplify(0.006)), 0.001)
    return {"type": "Feature", "properties": propiedades, "geometry": mapping(geometria)}


def coleccion(rasgos):
    return {"type": "FeatureCollection", "features": rasgos}


def escribir(nombre, datos):
    texto = json.dumps(datos, ensure_ascii=False, separators=(",", ":"))
    escribir_atomico(config.DIR_WEB / "public" / "mapa" / nombre, texto.encode("utf-8"))


def main():
    crudo = json.loads((config.DIR_RAW / "limites" / "adm2.geojson").read_text(encoding="utf-8"))["features"]
    poligonos = [shape(f["geometry"]).buffer(0) for f in crudo]
    arbol = STRtree(poligonos)
    lugares = [
        [
            d["departamento"],
            d["provincia"],
            d["distrito"],
            round(float(d["latitude"]), 3),
            round(float(d["longitude"]), 3),
        ]
        for d in leer_csv(config.DIR_RAW / "ubigeo" / "distrito.csv")
        if d["latitude"] not in ("", "NA") and d["longitude"] not in ("", "NA")
    ]
    votos = [collections.Counter() for _ in poligonos]
    for dep, _, _, lat, lon in lugares:
        for i in arbol.query(Point(lon, lat), predicate="within"):
            votos[i][dep] += 1
    provincias, por_dep = [], {}
    for g, v in zip(poligonos, votos, strict=True):
        if v:
            dep = v.most_common(1)[0][0]
            por_dep.setdefault(dep, []).append(g)
            provincias.append(rasgo(g, dep=dep))
    departamentos = []
    for dep, gs in sorted(por_dep.items()):
        union = unary_union(gs).buffer(CIERRE).buffer(-CIERRE)
        mayor = max(getattr(union, "geoms", [union]), key=lambda p: p.area)
        c = mayor.centroid if mayor.contains(mayor.centroid) else mayor.representative_point()
        limites = [round(x, 3) for x in union.bounds]
        departamentos.append(rasgo(union, id=dep, c=[round(c.x, 3), round(c.y, 3)], b=limites))
    mascara = rasgo(box(*MARCO).difference(unary_union(poligonos).buffer(CIERRE)))
    escribir("base.json", {"deps": coleccion(departamentos), "provs": coleccion(provincias), "mascara": mascara})
    escribir("lugares.json", lugares)


if __name__ == "__main__":
    main()
