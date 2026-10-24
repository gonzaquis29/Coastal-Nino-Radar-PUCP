"""Geometría mínima sobre GeoJSON (sin dependencias): punto dentro de un polígono."""


def _en_anillo(x, y, anillo):
    """Regla del rayo (par-impar) para un anillo [(lon, lat), …]."""
    dentro = False
    for (x1, y1), (x2, y2) in zip(anillo, [*anillo[1:], anillo[0]], strict=True):
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1:
            dentro = not dentro
    return dentro


def poligonos(geometria):
    """Lista de polígonos (cada uno, lista de anillos) de una geometría Polygon o MultiPolygon."""
    geometria = geometria or {}
    if geometria.get("type") == "MultiPolygon":
        return geometria.get("coordinates", [])
    if geometria.get("type") == "Polygon":
        return [geometria.get("coordinates", [])]
    return []


def punto_en_geometria(x, y, geometria):
    """True si (lon, lat) cae dentro de algún polígono y fuera de sus huecos."""
    return any(
        pol and _en_anillo(x, y, pol[0]) and not any(_en_anillo(x, y, h) for h in pol[1:])
        for pol in poligonos(geometria)
    )
