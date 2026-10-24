"""Avisos meteorológicos del Senamhi: tabla, detalle, mapas por día y polígonos oficiales (definición en docs/oficial/definicion.md)."""
import datetime as dt
import json
import re
from urllib.parse import parse_qs, urlencode, urlsplit

from lxml import html

from oficial.comun import (DEPS_AVISO, DIR_RAW, INICIO, escribir_atomico, fecha_hora_es, guardar_gz, leer_gz, norm,
                           ruta_segura, sha1_corto, sin_tildes)

BASE = "https://www.senamhi.gob.pe/"
WFS = ("https://idesep.senamhi.gob.pe/geoserver/g_aviso/ows?service=WFS&version=1.0.0&request=GetFeature"
       "&typeName=g_aviso:view_aviso&viewparams=qry:{num}_{mapa}_{anio}&outputFormat=application/json"
       "&propertyName=nivel,nro_mapa,geom&cql_filter=nivel%3C%3E%27Nivel%201%27")  # solo zonas con aviso (niveles 2-4)
DIR = DIR_RAW / "senamhi"
NIVELES = ["", "VERDE", "AMARILLO", "NARANJA", "ROJO"]

# Puntos de referencia de la costa: estaciones del Senamhi (lista de ?p=estaciones, 24-oct-2026) en zonas bajas de la costa.
# Supuesto declarado: la elección de estas estaciones como "costa" es nuestra; las coordenadas son oficiales.
ESTACIONES = {
    "costa_norte": [("PUENTE TUMBES", -80.4609, -3.5709), ("RICA PLAYA", -80.4575, -3.81333), ("EL ALTO", -81.21815, -4.26198),
                    ("LA ESPERANZA", -81.05969, -4.92114), ("MALLARES", -80.73556, -4.85574), ("MIRAFLORES", -80.61654, -5.17528),
                    ("CHULUCANAS", -80.16954, -5.10844), ("MORROPON", -79.97107, -5.19465), ("LAMBAYEQUE", -79.90894, -6.73438),
                    ("REQUE", -79.8355, -6.88613), ("TINAJONES", -79.4279, -6.65493), ("TRUJILLO", -78.9851, -8.11203)],
    "costa_centro": [("HUARMEY", -78.16232, -10.06812), ("UNJF SANCHEZ CARRION - HUACHO", -77.60603, -11.12386),
                     ("CAMPO DE MARTE", -77.04317, -12.07053), ("VON HUMBOLDT", -76.93944, -12.08221), ("CAÑETE", -76.33042, -13.07475),
                     ("SOCSI CAÑETE", -76.20027, -13.03051), ("FONAGRO (CHINCHA)", -76.15243, -13.45935), ("SAN CAMILO", -75.71101, -14.07331),
                     ("PALPA", -75.18921, -14.54935)],
}


# ---------------------------------------------------------------- tabla de avisos

def leer_tabla(contenido):
    """Filas de la tabla de ?p=aviso-meteorologico."""
    filas = []
    for tr in html.fromstring(contenido).xpath("//table[@id='table_id']/tbody/tr"):
        c = [norm(td.text_content()) for td in tr.xpath("./td")]
        enlace = tr.xpath("./td[1]//a/@href")
        if len(c) < 7 or not enlace:
            continue
        q = {k: v[0] for k, v in parse_qs(urlsplit(enlace[0]).query).items()}
        m = re.match(r"(\d+)\s*(?:\((\w+)\))?", c[1])
        if not (q.get("a", "").isdigit() and q.get("b", "").isdigit() and m):
            continue
        filas.append({"anio": q["a"], "b": q["b"], "numero": int(m.group(1)), "estado_tabla": (m.group(2) or "").lower(),
                      "titulo": c[0], "emision": c[2], "inicio": c[3], "fin": c[4], "duracion": c[5], "nivel": c[6]})
    return filas


def firma(f):
    """Lo que identifica el contenido de una fila, sin el sufijo (emitido)/(vigente), que cambia solo con el tiempo."""
    return "|".join(str(f[k]) for k in ["titulo", "emision", "inicio", "fin", "duracion", "nivel"])


def tipo(titulo):
    t = re.sub(r"\s*\(.*?\)", "", titulo)
    if re.search(r"PRECIPITACION|LLUVIA", t):
        return "precipitaciones"
    if re.search(r"INCREMENTO DE TEMPERATURA", t):
        return "temperatura"
    return None  # llovizna, viento, friaje, nevada, descensos de temperatura: fuera del alcance


def segmentos(texto):
    """Tramos de costa que nombra un texto: norte, centro, sur ('COSTA' sin calificar = los tres)."""
    t = sin_tildes(texto).upper()
    seg = set()
    for m in re.finditer(r"COSTA((?:\s*(?:,|\bY\b)?\s*\b(?:NORTE|CENTRO|CENTRAL|SUR)\b)*)", t):
        q = m.group(1)
        if not q.strip():
            seg |= {"norte", "centro", "sur"}
        for k, v in [("NORTE", "norte"), ("CENTR", "centro"), ("SUR", "sur")]:
            if k in q:
                seg.add(v)
    for dep in ["TUMBES", "PIURA", "LAMBAYEQUE", "LA LIBERTAD"]:
        if re.search(r"\b" + dep + r"\b", t):
            seg.add("norte")
    return seg


def candidato(f):
    """'alcance': precipitaciones/temperatura con costa en el título; 'control': sin costa en el título (para validar el filtro)."""
    if not tipo(f["titulo"]) or not (f["emision"][:4] >= INICIO[:4] or f["fin"] >= INICIO):
        return None
    titulo = re.sub(r"\s*\(.*?\)", "", f["titulo"])
    if segmentos(titulo):
        return "alcance"
    if re.search(r"SIERRA", titulo):
        return "control"
    return None  # avisos solo de selva


def dias_tabla(f):
    a, b = dt.date.fromisoformat(f["inicio"]), dt.date.fromisoformat(f["fin"])
    return (b - a).days + 1


# ---------------------------------------------------------------- descarga

def ruta(nombre):
    return ruta_segura(DIR, nombre)


def descargar(cli, f, clase, estado):
    """Detalle, mapas por día y polígonos de un aviso. Solo vuelve a pedir si cambió la fila o seguía emitido/vigente."""
    clave_av = f"{f['anio']}-{f['numero']:03d}"
    previo = estado.get(clave_av, {})
    if previo.get("firma") == firma(f) and previo.get("estado_tabla") not in ("emitido", "vigente") and previo.get("completo"):
        return False
    completo = True
    mapas = []
    if clase == "alcance":
        url = BASE + "?" + urlencode({"p": "aviso-meteorologico-detalle", "a": f["anio"], "b": f["b"], "c": "00", "d": "SENA"})
        r = cli.traer(url)
        guardar_gz(ruta(f"detalle-{clave_av}.html.gz"), r.content)
        panel = panel_aviso(r.content, f)
        if panel is None:
            completo = False
        else:
            for src in sorted(set(panel.xpath(".//iframe[contains(@src,'index.php')]/@src"))):
                q = {k: v[0] for k, v in parse_qs(urlsplit(src).query).items()}
                if not q.get("mp", "").isdigit():
                    continue
                mapas.append(int(q["mp"]))
                rm = cli.traer(BASE + "mapas/mapa-avisos-meteorologicos/index.php?" + urlencode(
                    {"av": f["numero"], "nl": q.get("nl", ""), "mp": q["mp"], "fc": f["anio"]}))
                guardar_gz(ruta(f"mapa-{clave_av}-{int(q['mp'])}.html.gz"), rm.content)
    else:
        mapas = list(range(1, dias_tabla(f) + 1))
    for mp in sorted(set(mapas)):
        try:
            rp = cli.traer(WFS.format(num=f["numero"], mapa=mp, anio=f["anio"]))
            json.loads(rp.content)
            guardar_gz(ruta(f"poligono-{clave_av}-{mp}.json.gz"), rp.content)
        except Exception:  # sin polígono se usa la regla de título y departamentos (metodo=regla)
            completo = False
    estado[clave_av] = {"firma": firma(f), "estado_tabla": f["estado_tabla"], "completo": completo,
                        "descargado": dt.datetime.now().isoformat(timespec="seconds")}
    return True


# ---------------------------------------------------------------- lectura de páginas

def panel_aviso(contenido, f):
    """Panel del aviso en la página de detalle: id tabs-<número><año> si está vigente, tabs-<b><año> si no."""
    d = html.fromstring(contenido)
    p = d.xpath(f"//div[@id='tabs-{f['numero']}{f['anio']}']") or d.xpath(f"//div[@id='tabs-{f['b']}{f['anio']}']")
    return p[0] if p else None


def leer_detalle(contenido, f):
    p = panel_aviso(contenido, f)
    if p is None:
        return None
    h2 = norm(p.xpath(".//h2")[0].text_content()) if p.xpath(".//h2") else ""
    info = [norm(x.text_content()) for x in p.xpath(".//span[contains(@class,'text-info')]")]
    emis = [norm(x.text_content()) for x in p.xpath(".//strong[contains(.,'emisi')]/../following-sibling::span[1]")]
    general = [norm(x.text_content()) for x in p.xpath(".//div[@class='col-lg-12 col-md-12 col-sm-12 col-xs-12']")
               if re.match(r"El Senamhi informa", norm(x.text_content()), re.I)]
    dias = [norm(x.text_content()) for x in p.xpath(".//div[starts-with(@id,'v-pills-tab-')]//p")]
    m = re.match(r"Aviso N°\s*(\d+)\s+(\w+)", h2)
    return {"numero": int(m.group(1)) if m else None, "nivel": m.group(2) if m else None,
            "titulo": " ".join(norm(x.text_content()) for x in p.xpath(".//h1")),
            "emision": fecha_hora_es(emis[0]) if emis else None,
            "inicio": fecha_hora_es(info[0]) if info else None, "fin": fecha_hora_es(info[1]) if len(info) > 1 else None,
            "general": general[0] if general else "", "dias": [t for t in dias if t],
            "mapas": sorted({int(q["mp"][0]): q.get("nl", [""])[0] for q in
                             (parse_qs(urlsplit(s).query) for s in p.xpath(".//iframe[contains(@src,'index.php')]/@src")) if "mp" in q}.items())}


def leer_mapa(contenido):
    t = norm(html.fromstring(contenido).text_content())
    fe = re.search(r"Fecha:\s*\w+\s*,\s*(\d{1,2} de \w+ de \d{4})", t)
    deps = re.search(r"DEPARTAMENTOS DE POSIBLE AFECTACI[ÓO]N:\s*(.*?)\s*PROVINCIAS", t)
    return {"fecha": fecha_hora_es(fe.group(1)) if fe else None,
            "deps": sorted({sin_tildes(x.strip()).upper() for x in deps.group(1).split(",") if x.strip()}) if deps else []}


def _en_anillo(x, y, anillo):
    dentro = False
    for (x1, y1), (x2, y2) in zip(anillo, anillo[1:] + anillo[:1]):
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1:
            dentro = not dentro
    return dentro


def cobertura(geojson):
    """Nivel máximo (2-4) del polígono oficial sobre cada estación de referencia de la costa."""
    out = {}
    for ft in geojson.get("features", []):
        g = ft.get("geometry") or {}
        polis = g.get("coordinates", []) if g.get("type") == "MultiPolygon" else [g.get("coordinates", [])] if g.get("type") == "Polygon" else []
        niv = int(re.sub(r"\D", "", ft["properties"].get("nivel", "")) or 0)
        for macro, ests in ESTACIONES.items():
            for nom, x, y in ests:
                if any(pol and _en_anillo(x, y, pol[0]) and not any(_en_anillo(x, y, h) for h in pol[1:]) for pol in polis):
                    out[nom] = (macro, max(out.get(nom, (macro, 0))[1], niv))
    return out


# ---------------------------------------------------------------- construcción de filas

def relacion(titulo):
    m = re.search(r"\((EXTENSI[OÓ]N|ACTUALIZACI[OÓ]N) DEL AVISO (\d+)\)", titulo)
    return (("extension" if m.group(1).startswith("EXT") else "actualizacion"), int(m.group(2))) if m else ("", None)


def construir(tabla):
    """Filas de avisos, días por macro-región y párrafos desde data/raw (determinista)."""
    avisos, dias, pars, val = [], [], [], []
    for f in tabla:
        clase = candidato(f)
        if not clase:
            continue
        clave_av = f"{f['anio']}-{f['numero']:03d}"
        ident = f"senamhi-{clave_av}"
        titulo_base = re.sub(r"\s*\(.*?\)", "", f["titulo"])
        if clase == "control":  # solo polígonos, para medir si el filtro por título pierde avisos de costa
            for mp in range(1, dias_tabla(f) + 1):
                rp = DIR / f"poligono-{clave_av}-{mp}.json.gz"
                if rp.exists():
                    cub = cobertura(json.loads(leer_gz(rp)))
                    val.append({"clase": "control", "aviso_id": ident, "mapa": mp, "cubre": sorted({m for m, _ in cub.values()})})
            continue
        rd = DIR / f"detalle-{clave_av}.html.gz"
        det = leer_detalle(leer_gz(rd), f) if rd.exists() else None
        if det is None:
            val.append({"clase": "alcance", "aviso_id": ident, "error": "sin panel de detalle"})
            continue
        st = segmentos(titulo_base)
        if st == {"norte", "centro", "sur"}:  # título genérico: los tramos que nombran la descripción y los días
            st = segmentos(det["general"] + " " + " ".join(det["dias"])) or st
        macros_aviso, filas_dia = set(), []
        for mp, nl in det["mapas"]:
            rm = DIR / f"mapa-{clave_av}-{mp}.html.gz"
            mapa = leer_mapa(leer_gz(rm)) if rm.exists() else {"fecha": None, "deps": []}
            regla = {m for m, seg in [("costa_norte", "norte"), ("costa_centro", "centro")] if seg in st and set(mapa["deps"]) & DEPS_AVISO[m]}
            rp = DIR / f"poligono-{clave_av}-{mp}.json.gz"
            if rp.exists():
                cub = cobertura(json.loads(leer_gz(rp)))
                poli = {}
                for macro, niv in cub.values():
                    poli[macro] = max(poli.get(macro, 0), niv)
                metodo, macros = "poligono", set(poli)
            else:
                cub, poli, metodo, macros = {}, {}, "regla", regla
            nivel_dia = NIVELES[int(nl)] if nl.isdigit() and int(nl) < len(NIVELES) else ""
            for macro in sorted(macros):
                filas_dia.append({"aviso_id": ident, "fecha": mapa["fecha"], "mapa": mp, "macroregion": macro, "nivel_dia": nivel_dia,
                                  "nivel_macroregion": NIVELES[poli[macro]] if macro in poli else nivel_dia,
                                  "estaciones": sorted(n for n, (m, _) in cub.items() if m == macro),
                                  "departamentos": sorted(set(mapa["deps"]) & DEPS_AVISO[macro]), "metodo": metodo})
            macros_aviso |= macros
            val.append({"clase": "alcance", "aviso_id": ident, "mapa": mp, "fecha": mapa["fecha"], "regla": sorted(regla),
                        "poligono": sorted(poli) if metodo == "poligono" else None, "nivel_dia": nivel_dia,
                        "nivel_max_poligono": NIVELES[max(poli.values())] if poli else ""})
        val.append({"clase": "detalle", "aviso_id": ident, "tabla": f, "detalle": {k: det[k] for k in ["numero", "nivel", "titulo", "emision", "inicio", "fin"]},
                    "niveles_mapas": [nl for _, nl in det["mapas"]], "fechas_mapas": [r["fecha"] for r in filas_dia]})
        if not macros_aviso:
            continue  # el polígono no toca la costa norte ni la centro (p. ej., solo costa sur)
        rel, rel_num = relacion(f["titulo"])
        estado_av = "cancelado" if "CANCELADO" in f["titulo"] else (f["estado_tabla"] or "vencido")
        avisos.append({"id": ident, "anio": int(f["anio"]), "numero": f["numero"], "b": f["b"], "titulo": f["titulo"], "tipo": tipo(f["titulo"]),
                       "nivel": f["nivel"], "estado": estado_av, "relacion": rel,
                       "aviso_relacionado": f"senamhi-{f['anio']}-{rel_num:03d}" if rel_num else "",
                       "emision": f["emision"], "inicio": det["inicio"], "fin": det["fin"], "duracion": f["duracion"],
                       "macroregiones": sorted(macros_aviso), "metodo_macroregion": "poligono" if all(r["metodo"] == "poligono" for r in filas_dia) else "regla",
                       "url": BASE + "?" + urlencode({"p": "aviso-meteorologico-detalle", "a": f["anio"], "b": f["b"], "c": "00", "d": "SENA"})})
        dias += filas_dia
        tema = {"precipitaciones": {"lluvias"}, "temperatura": {"calor"}}[tipo(f["titulo"])]
        textos = [("titulo", f["titulo"])] + ([("descripcion", det["general"])] if det["general"] else []) + [("dia", t) for t in det["dias"]]
        for i, (sec, t) in enumerate(textos):
            pars.append({"id": f"{ident}-p{i + 1:02d}", "doc_id": ident, "fuente": "senamhi", "orden": i + 1, "seccion": sec, "texto": t,
                         "fecha_doc": f["emision"], "vigente_desde": f["emision"], "vigente_hasta": (det["fin"] or f["fin"])[:10],
                         "macroregiones": sorted(macros_aviso), "temas": tema,
                         "duplicado_de": "", "sha1": sha1_corto(t)})
    avisos.sort(key=lambda a: (a["anio"], a["numero"]))
    dias.sort(key=lambda d: (d["aviso_id"], d["mapa"], d["macroregion"]))
    return avisos, dias, pars, val


def cargar_estado():
    r = DIR / "estado.json"
    return json.loads(r.read_text(encoding="utf-8")) if r.exists() else {}


def guardar_estado(estado):
    escribir_atomico(DIR / "estado.json", json.dumps(estado, ensure_ascii=False, indent=1, sort_keys=True).encode("utf-8"))

