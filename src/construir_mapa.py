"""Genera web/mapa.json (departamentos y provincias GeoJSON) y web/lugares.json (buscador).

Límites: geoBoundaries PER ADM2 (IGN / OCHA, CC BY 3.0 IGO) en data/raw/limites/adm2.geojson.
Se ejecuta una sola vez:  python src/construir_mapa.py   (requiere shapely)
"""
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from shapely import STRtree, make_valid, set_precision
from shapely.geometry import Point, box, mapping, shape
from shapely.ops import unary_union

import geo

def main():
    crudo = json.load(open("data/raw/limites/adm2.geojson", encoding="utf8"))["features"]
    polis = [shape(f["geometry"]).buffer(0) for f in crudo]
    arbol = STRtree(polis)
    d = geo.distritos()
    votos = [Counter() for _ in polis]
    for r in d.itertuples():
        for i in arbol.query(Point(r.lon, r.lat), predicate="within"):
            votos[i][(r.departamento, r.provincia)] += 1
    def rasgo(g, **props):
        g = set_precision(make_valid(g.simplify(0.006)), 0.001)
        return {"type": "Feature", "properties": props, "geometry": mapping(g)}

    provs, por_dep = [], {}
    for f, g, v in zip(crudo, polis, votos):
        if not v:
            print("sin distritos:", f["properties"]["shapeName"])
            continue
        dep = Counter()
        for (dd, _), n in v.items():
            dep[dd] += n
        dep = dep.most_common(1)[0][0]
        por_dep.setdefault(dep, []).append(g)
        provs.append(rasgo(g, dep=dep))
    deps = []
    for dep, gs in sorted(por_dep.items()):
        u = unary_union(gs).buffer(0.004).buffer(-0.004)
        p = max(getattr(u, "geoms", [u]), key=lambda q: q.area)
        c = p.centroid if p.contains(p.centroid) else p.representative_point()
        deps.append(rasgo(u, id=dep, c=[round(c.x, 3), round(c.y, 3)], b=[round(x, 3) for x in u.bounds]))
    fc = lambda fs: {"type": "FeatureCollection", "features": fs}
    Path("web/mapa.json").write_text(json.dumps({"deps": fc(deps), "provs": fc(provs), "mascara": rasgo(box(-130, -60, -20, 40).difference(unary_union(polis).buffer(0.004)))}, ensure_ascii=False, separators=(",", ":")), encoding="utf8")
    lug = [[r.departamento, r.provincia, r.distrito, round(r.lat, 3), round(r.lon, 3)] for r in d.itertuples()]
    Path("web/lugares.json").write_text(json.dumps(lug, ensure_ascii=False, separators=(",", ":")), encoding="utf8")
    print(len(deps), "departamentos,", len(provs), "provincias", len(lug), "distritos")


if __name__ == "__main__":
    main()
