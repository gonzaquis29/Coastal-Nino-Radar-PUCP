"""Comunicados del ENFEN: descarga (PDF + página de descarga), párrafos y campos (definición en docs/oficial/definicion.md)."""
import datetime as dt
import difflib
import json
import re

import fitz  # PyMuPDF
from lxml import etree, html

from oficial.comun import (DIR_RAW, INICIO, Rechazado, clave, escribir_atomico, fecha_es, filas_urls,
                           norm, regiones_mencionadas, ruta_segura, sha1_corto, sha256)

BASE = "https://enfen.imarpe.gob.pe"
DIR = DIR_RAW / "enfen"
SEMILLAS = ["comunicado-oficial-enfen-n13-2025"]  # vigente del 1 al 14-ene-2026 (No Activo)
SLUG = re.compile(r"^comunicado-(oficial|extraordinario)-enfen-[a-z0-9-]+$")
NS = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9"}
PARSER_XML = etree.XMLParser(resolve_entities=False, no_network=True)

ESTADOS = ["No Activo", "Vigilancia de El Niño Costero", "Alerta de El Niño Costero",
           "Vigilancia de La Niña Costera", "Alerta de La Niña Costera"]
ESCALA = ["débil", "moderada", "fuerte", "muy fuerte", "extraordinaria"]

CABECERA = re.compile(r"^(COMISIÓN MULTISECTORIAL ENCARGADA|DEL ESTUDIO NACIONAL DEL FENÓMENO|ENFEN$|Decreto Supremo N|"
                      r"[“\"]Año de|https?://enfen\.imarpe\.gob\.pe/?$)", re.I)
FIRMA = re.compile(r"^Comisión Multisectorial( encargada)?( del Estudio Nacional del Fenómeno.*)?$|^del Estudio Nacional del Fenómeno", re.I)
DESCARTE = re.compile(r"^(Figura|Tabla|Fuente)\s*\d*[.:)]|^Para más información|^https?://", re.I)
ENCAB = re.compile(r"^(COMUNICADO (OFICIAL|EXTRAORDINARIO) ENFEN|Estado del? sistema de alerta|RESUMEN EJECUTIVO$|"
                   r"\d{1,2} (de )?\w+ (de )?\d{4}$|(" + "|".join(ESTADOS) + r")$)", re.I)
ROTULO = re.compile(r"^(Lluvias|Caudales|Temperatura del [Aa]ire|Pesquero|Embalses)\s*:")
NUMERO = re.compile(r"COMUNICADO (OFICIAL|EXTRAORDINARIO) ENFEN\s*N\s*°\s*0?(\d{1,2})\s*[-–]\s*(\d{4})")


# ---------------------------------------------------------------- lista de documentos y descarga

def documentos(cli):
    """Slugs de comunicados: data/urls + semillas + los del sitemap con lastmod ≥ 2026 (con aviso si faltan en data/urls)."""
    slugs, avisos = [], []
    for f in filas_urls():
        if f["medio"] == "enfen" and "/download/" in f["url"] and SLUG.match(f["id"]):  # no las entradas del blog
            slugs.append(f["id"])
    lastmod = {}
    try:
        raiz = etree.fromstring(cli.traer(BASE + "/wpdmpro-sitemap.xml").content, PARSER_XML)
        for u in raiz.findall("s:url", NS):
            m = re.match(BASE + r"/download/([^/]+)/?$", (u.findtext("s:loc", namespaces=NS) or "").strip())
            if m and SLUG.match(m.group(1)):
                lastmod[m.group(1)] = (u.findtext("s:lastmod", namespaces=NS) or "").strip()
    except Exception as e:  # sin sitemap se trabaja con data/urls y lo ya descargado
        avisos.append(f"sitemap del ENFEN no disponible: {type(e).__name__} {e}"[:200])
    for s, mod in lastmod.items():
        if mod[:10] >= INICIO and s not in slugs:
            slugs.append(s)
            avisos.append(f"{s} está en el sitemap pero no en data/urls (¿se corrió diario.py?)")
    return list(dict.fromkeys(SEMILLAS + slugs)), lastmod, avisos


def descargar(cli, slug, lastmod, estado):
    """Página de descarga + PDF. Vuelve a descargar si cambió el lastmod; devuelve True si el PDF cambió."""
    previo = estado.get(slug, {})
    pdf = ruta_segura(DIR, slug + ".pdf")
    if pdf.exists() and previo.get("lastmod") == lastmod and previo.get("sha256"):
        return False
    pagina = cli.traer(f"{BASE}/download/{slug}/")
    enlaces = sorted({a for a in html.fromstring(pagina.content).xpath("//a/@href") if "wpdmdl=" in a and slug in a})
    m = re.search(r"wpdmdl=(\d+)", enlaces[0]) if enlaces else None
    if not m:
        raise Rechazado(f"{slug}: la página no tiene enlace de descarga")
    r = cli.traer(f"{BASE}/download/{slug}/?wpdmdl={m.group(1)}", tipo="pdf")
    escribir_atomico(ruta_segura(DIR, slug + ".html"), pagina.content)
    nuevo = sha256(r.content)
    cambio = nuevo != previo.get("sha256")
    if cambio:
        escribir_atomico(pdf, r.content)
    estado[slug] = {"lastmod": lastmod, "sha256": nuevo, "descargado": dt.datetime.now().isoformat(timespec="seconds")}
    return cambio


# ---------------------------------------------------------------- PDF → líneas → párrafos

def _texto_linea(linea):
    spans = [s for s in linea["spans"] if s["text"].strip()]
    base = max(s["size"] for s in spans)
    out, x_fin = "", None
    for s in spans:
        if re.fullmatch(r"\s*\d{1,2}\s*", s["text"]) and ((s["flags"] & 1) or s["size"] < 0.8 * base):
            x_fin = s["bbox"][2]  # marca de nota al pie pegada a la palabra ("Costero1")
            continue
        t = s["text"]
        if out and x_fin is not None and s["bbox"][0] - x_fin > 0.15 * s["size"] and not out.endswith(" ") and not t.startswith(" "):
            out += " "
        out += t
        x_fin = s["bbox"][2]
    return norm(out), base


def _lineas(doc, tablas):
    """Líneas con el tipo de su bloque: nota (al pie), leyenda (figura/tabla), tabla o texto."""
    out = []
    for p in doc:
        alto = p.rect.height
        encontradas = p.find_tables().tables
        cajas = [fitz.Rect(t.bbox) for t in encontradas]
        tablas.extend({"pag": p.number + 1, "filas": [f for f in t.extract() if any((c or "").strip() for c in f)]} for t in encontradas)
        bajo_nota, ley_fin = False, None
        for b in p.get_text("dict", sort=True)["blocks"]:
            if b["type"] != 0:
                continue
            ls = [l for l in b["lines"] if any(s["text"].strip() for s in l["spans"])]
            if not ls:
                continue
            primera = "".join(s["text"] for s in ls[0]["spans"]).strip()
            inicio_b = re.sub(r"^([a-d]\)?\s+)+", "", norm(" ".join("".join(s["text"] for s in l["spans"]) for l in ls)))  # sin rótulos de panel
            tam_b = max(s["size"] for l in ls for s in l["spans"] if s["text"].strip())
            if tam_b <= 9.5 and re.match(r"^\d{1,2}(\s|$|https?:)", primera) and b["bbox"][1] > 0.35 * alto:
                bajo_nota = True  # desde la primera nota al pie, lo de abajo con letra chica también es nota
            caja = fitz.Rect(b["bbox"])
            if bajo_nota and tam_b <= 9.5:
                tipo = "nota"
            elif any(caja.intersect(c).get_area() > 0.5 * caja.get_area() for c in cajas):
                tipo = "tabla"
            elif re.match(r"^(Figura|Tabla|Fuente)(\s*\d+\s*[.:)]|\s*:|$)", inicio_b, re.I) or \
                    (ley_fin is not None and 0 <= b["bbox"][1] - ley_fin < 1.5 * tam_b):
                tipo = "leyenda"
            else:
                tipo = "texto"
            ley_fin = b["bbox"][3] if tipo == "leyenda" else None
            for l in ls:
                t, base = _texto_linea(l)
                if re.match(r"^(\d{1,2}\.?\s*)?https?://\S+$", t) or "wpdmdl=" in t:  # notas "1. https://…" y enlaces partidos
                    tipo_l = "nota"
                elif re.match(r"^(Magnitud del evento|Probabilidad de Ocurrencia|El Niño( Costero)?\s*\(\w+ \d{4} -)", t):
                    tipo_l = "tabla"  # encabezado de tabla fuera del recuadro detectado
                else:
                    tipo_l = tipo
                if t:
                    out.append({"pag": p.number + 1, "x1": l["bbox"][2], "y0": l["bbox"][1], "y1": l["bbox"][3],
                                "tam": round(base), "texto": t, "tipo": tipo_l})
    return out


def _agrupar(ls):
    """Une líneas en párrafos; corta por espacio vertical, cambio de letra, línea corta con punto, viñeta o rótulo."""
    pars, prev = [], None
    for l in ls:
        nuevo = (prev is None
                 or (l["pag"] != prev["pag"] and re.search(r"[.:;”\"]$", prev["texto"]))
                 or (l["pag"] == prev["pag"] and (l["y0"] - prev["y1"] > 0.45 * l["tam"] or l["y0"] < prev["y0"] - 1))
                 or (l["tam"] != prev["tam"] and l["pag"] == prev["pag"])
                 or (re.search(r"[.:]$", prev["texto"]) and prev["x1"] < 480)
                 or ROTULO.match(l["texto"]) or l["texto"][:1] in "•−–"
                 or ENCAB.match(l["texto"]) or ENCAB.match(prev["texto"]))
        if nuevo:
            pars.append({"tam": l["tam"], "texto": l["texto"]})
        else:
            t = pars[-1]["texto"]
            pegar = re.search(r"[a-záéíóúñ]-$", t) and l["texto"][:1].islower()
            pars[-1]["texto"] = t + l["texto"] if pegar else t + " " + l["texto"]
        prev = l
    return pars


def extraer(ruta_pdf):
    """Párrafos (sección, texto), tablas de probabilidades y texto completo de un comunicado."""
    doc = fitz.open(ruta_pdf)
    tablas = []
    todas = _lineas(doc, tablas)
    cuerpo = [l for l in todas if l["tipo"] == "texto" and not CABECERA.match(l["texto"]) and not FIRMA.match(l["texto"])]
    tam_resumen = next((cuerpo[i + 1]["tam"] for i, l in enumerate(cuerpo[:-1]) if l["texto"].upper() == "RESUMEN EJECUTIVO"), 0)
    parrafos, seccion = [], "cuerpo"
    for p in _agrupar(cuerpo):
        t = re.sub(r"^[ab]\)\s+(?=[A-ZÁÉÍÓÚ])", "", p["texto"].lstrip("•−– ").strip())  # rótulo de panel de figura
        if t.upper() == "RESUMEN EJECUTIVO":
            seccion = "resumen"
            continue
        if ENCAB.match(t) or DESCARTE.match(t) or re.fullmatch(r"[\d\s.,%°|()ab-]*", t) or FIRMA.match(t):
            continue
        if re.fullmatch(r"[A-ZÁÉÍÓÚÑ0-9 ,.]+", t):
            if len(t) > 25:
                parrafos.append({"seccion": "titular", "texto": t})
            continue
        if len(t) < 25:
            continue
        if seccion == "resumen" and p["tam"] > tam_resumen:
            seccion = "cuerpo"
        parrafos.append({"seccion": seccion, "texto": t})
    notas = norm(" ".join(l["texto"] for l in todas if l["tipo"] == "nota"))
    for e in ESTADOS:  # nota al pie que define el estado del sistema de alerta
        m = re.search(r"\b" + re.escape(e) + r"\s*[:,]\s*(.+?)(?=\s\d{1,2}\s[A-ZÁÉÍÓÚ]|\s\d{1,2}\s?https?://|$)", notas, re.I)
        if m:
            parrafos.append({"seccion": "definicion", "texto": norm(e + ": " + re.sub(r"\(Nota Técnica.*", "", m.group(1)))})
            break
    for i, p in enumerate(parrafos):
        for j in range(i):
            if "duplicado_de" not in parrafos[j] and difflib.SequenceMatcher(None, clave(p["texto"]), clave(parrafos[j]["texto"])).ratio() >= 0.9:
                p["duplicado_de"] = j
                break
    texto = norm(" ".join(pg.get_text() for pg in doc))
    return parrafos, tablas, texto


# ---------------------------------------------------------------- campos

def campos(texto):
    f = {"tipo": None, "numero": None, "anio": None, "fecha_emision": None, "estado": None, "proximo_anunciado": None}
    m = NUMERO.search(texto)
    if not m:
        return f
    f["tipo"], f["numero"], f["anio"] = m.group(1).lower(), int(m.group(2)), int(m.group(3))
    f["fecha_emision"] = fecha_es(texto[m.end():m.end() + 80])
    cab = texto[m.end():m.end() + 120]
    est = [e for e in ESTADOS if re.search(re.escape(e).replace(r"\ ", r"\s+"), cab, re.I)]
    f["estado"] = est[0] if len(est) == 1 else None
    p = re.search(r"próximo Comunicado Oficial[^.]*?(\d{1,2}\s+de\s+\w+\s+del?\s+\d{4})", texto, re.I)
    f["proximo_anunciado"] = fecha_es(p.group(1)) if p else None
    return f


TERMINO = re.compile(r"\b(débil(?:es)?|moderad[ao]s?|muy fuertes?|fuertes?|extraordinari[ao]s?)\b", re.I)
R34 = re.compile(r"Niño 3\.4|Pacífico (ecuatorial )?central|\bONI\b|\bRONI\b", re.I)
R12 = re.compile(r"Niño 1\+2|Niño Costero|costa peruana|costero", re.I)
NO_MAGNITUD = re.compile(r"lluvia|precipitaci|intensidad|caudal|crecida|viento", re.I)
POSIBLE = re.compile(r"no se descarta|podría alcanzar|pudiendo|aunque podría|sin descartar|sin embargo", re.I)


def _canon(t):
    t = t.lower()
    if t.startswith("muy"):
        return "muy fuerte"
    return next(e for e in ESCALA if e != "muy fuerte" and t.startswith(e[:5]))


def magnitud(parrafos):
    """Magnitud de El Niño Costero (región Niño 1+2): máxima prevista (escenario principal) y todas las mencionadas."""
    principal, todas = [], set()
    for p in parrafos:
        region = None
        for s in re.split(r"(?<=[.;])\s+(?=[A-ZÁÉÍÓÚ¿•])", p):
            if R34.search(s):
                region = "3.4"
            elif R12.search(s):
                region = "1+2"
            if region != "1+2" or NO_MAGNITUD.search(s) or not re.search(r"magnitud|cálidas? débil|evento", s, re.I):
                continue
            for m in TERMINO.finditer(s):
                c = _canon(m.group(1))
                todas.add(c)
                if not POSIBLE.search(s[:m.start()][-80:]):
                    principal.append(c)
    orden = sorted(todas, key=ESCALA.index)
    return (max(principal, key=ESCALA.index) if principal else None), orden


def plazo(parrafos):
    for p in parrafos:
        for s in re.split(r"(?<=[.;])\s+", p):
            if R12.search(s) and not R34.search(s):
                m = re.search(r"hasta (?:el |la |los |inicios? del? |mediados del? |finales del? |fines del? )*(?:\w+ )?(?:de |del )?"
                              r"(?:\d{4}|presente año|verano|otoño|invierno|primavera)[^,.;]*", s)
                if m:
                    return re.split(r"\s+(?:con |\()", m.group(0))[0]
    return None


def probabilidades(tablas):
    """Filas (región, periodo, categoría, %) de las tablas de probabilidad por magnitud."""
    out = []
    for t in tablas:
        filas = t["filas"]
        if not filas or len(filas[0]) < 2 or "probabilidad" not in clave(" ".join(c or "" for c in filas[0])):
            continue
        cats = [clave(f[0] or "") for f in filas[1:]]
        region = "nino_1+2" if any("extraordinari" in c for c in cats) else "nino_3.4" if any("muy fuerte" in c for c in cats) else ""
        per = re.search(r"\(([^)]*\d{4}[^)]*)\)", norm(filas[0][0] or ""))
        for f in filas[1:]:
            if (f[1] or "").strip().isdigit():
                out.append({"region": region, "periodo": per.group(1) if per else "", "categoria": norm(f[0]), "probabilidad": int(f[1])})
    return out


TEMAS = {"pesca": r"pesquer|anchoveta|bonito|perico|jurel|caballa|especies|pez |atún|melva|barrilete|samasa|recursos hidrobiol|desembarque",
         "lluvias": r"lluvia|precipitaci|caudal|ríos?\b|quebrada|crecida|huaico|desborde|inundaci|embalse|hidrol|mm/día",
         "calor": r"temperatura(s)? del aire|temperaturas? (máximas|mínimas)|calor|récords?|temperaturas? (diurnas?|nocturnas?)|radiación ultravioleta",
         "prevencion": r"tomadores de decisiones|riesgo de desastres|preparación|prevención|autoridades|escenarios de riesgo|fuentes oficiales|canales oficiales"}
TEMA_ROTULO = {"lluvias": "lluvias", "caudales": "lluvias", "embalses": "lluvias", "temperatura del aire": "calor", "pesquero": "pesca"}


def temas(texto):
    """Categorías de interés del README: el rótulo del ENFEN si existe; si no, palabras clave."""
    m = ROTULO.match(texto)
    if m:
        return {TEMA_ROTULO[m.group(1).lower()]}
    return {k for k, rx in TEMAS.items() if re.search(rx, texto, re.I)}


# ---------------------------------------------------------------- página de descarga (referencia para validar)

MES_CORTO = {"Ene": 1, "Feb": 2, "Mar": 3, "Abr": 4, "May": 5, "Jun": 6, "Jul": 7, "Ago": 8, "Set": 9, "Sep": 9, "Oct": 10, "Nov": 11, "Dic": 12}


def pagina(ruta_html, anio):
    """Fecha publicada, estado y párrafos del resumen HTML de la página de descarga."""
    d = html.fromstring(ruta_html.read_bytes())
    for s in d.xpath("//script|//style"):
        s.drop_tree()
    art = d.xpath("//article")
    if not art:
        return {"fecha_web": None, "estado_web": None, "parrafos_web": []}
    t = norm(art[0].text_content())
    m = re.match(r"(\d{1,2}) (\w{3})", t)
    fecha = dt.date(anio, MES_CORTO[m.group(2)], int(m.group(1))).isoformat() if m and m.group(2) in MES_CORTO and anio else None
    e = re.search(r"Estado de sistema de alerta:\s*([^0-9]+?)\d", t)
    ps = [norm(x.text_content()) for x in art[0].xpath(".//p|.//li")]
    ps = [p for p in ps if len(p) > 30 and "Tamaño del archivo" not in p and "Posted at" not in p]
    return {"fecha_web": fecha, "estado_web": norm(e.group(1)) if e else None, "parrafos_web": ps}


# ---------------------------------------------------------------- construcción de filas

def construir(slugs, estado):
    """Filas de comunicados, probabilidades y párrafos desde data/raw (determinista)."""
    coms, probs, pars, val = [], [], [], {}
    for slug in slugs:
        pdf = DIR / f"{slug}.pdf"
        if not pdf.exists():
            continue
        fuente = "pdf"
        try:
            parrafos, tablas, texto = extraer(pdf)
            c = campos(texto)
            if not (c["numero"] and c["fecha_emision"] and c["estado"]):
                raise ValueError("faltan número, fecha o estado en el PDF")
        except Exception as e:  # respaldo: el resumen de la página de descarga (se marca fuente_texto=html)
            m = re.search(r"n-?(\d{1,2})-(\d{4})$", slug)
            web = pagina(DIR / f"{slug}.html", int(m.group(2)) if m else None)
            if not (m and web["fecha_web"] and web["estado_web"] and web["parrafos_web"]):
                val[slug] = {"error": f"{type(e).__name__}: {e}"[:200]}
                continue
            fuente, tablas, texto = "html", [], " ".join(web["parrafos_web"])
            parrafos = [{"seccion": "cuerpo", "texto": t} for t in web["parrafos_web"]]
            c = {"tipo": "extraordinario" if "extraordinario" in slug else "oficial", "numero": int(m.group(1)),
                 "anio": int(m.group(2)), "fecha_emision": web["fecha_web"], "estado": web["estado_web"],
                 "proximo_anunciado": campos("COMUNICADO OFICIAL ENFEN N° 1-2000 " + texto)["proximo_anunciado"]}
        ident = f"enfen-{'ext-' if c['tipo'] == 'extraordinario' else ''}{c['anio']}-{c['numero']:02d}"
        web = pagina(DIR / f"{slug}.html", c["anio"])
        txt = [p["texto"] for p in parrafos if p["seccion"] in ("titular", "resumen", "cuerpo")]
        mmax, menc = magnitud(txt)
        coms.append({"id": ident, "tipo": c["tipo"], "numero": c["numero"], "anio": c["anio"], "fecha_emision": c["fecha_emision"],
                     "fecha_web": web["fecha_web"], "estado": c["estado"], "magnitud_max_prevista": mmax,
                     "magnitudes_mencionadas": menc, "plazo": plazo(txt), "proximo_anunciado": c["proximo_anunciado"],
                     "titular": next((p["texto"] for p in parrafos if p["seccion"] == "titular"), ""),
                     "slug": slug, "url": f"{BASE}/download/{slug}/", "lastmod": estado.get(slug, {}).get("lastmod", ""),
                     "sha256_pdf": estado.get(slug, {}).get("sha256", ""), "fuente_texto": fuente, "n_parrafos": len(parrafos)})
        for r in probabilidades(tablas):
            probs.append({"comunicado_id": ident, **r})
        for i, p in enumerate(parrafos):
            pars.append({"id": f"{ident}-p{i + 1:02d}", "doc_id": ident, "fuente": "enfen", "orden": i + 1, "seccion": p["seccion"],
                         "texto": p["texto"], "fecha_doc": c["fecha_emision"], "macroregiones": regiones_mencionadas(p["texto"]),
                         "temas": temas(p["texto"]) if p["seccion"] != "definicion" else set(),
                         "duplicado_de": f"{ident}-p{p['duplicado_de'] + 1:02d}" if "duplicado_de" in p else "",
                         "sha1": sha1_corto(p["texto"])})
        val[ident] = {"slug": slug, "texto": texto, "parrafos": txt, "tablas": tablas, "web": web, "campos": c}
    coms.sort(key=lambda x: (x["fecha_emision"] or "", x["tipo"], x["numero"]))
    for a, b in zip(coms, coms[1:]):  # vigencia: desde la emisión hasta el día anterior al siguiente
        a["vigente_hasta"] = (dt.date.fromisoformat(b["fecha_emision"]) - dt.timedelta(days=1)).isoformat()
    for c in coms:
        c["vigente_desde"] = c["fecha_emision"]
        c.setdefault("vigente_hasta", "")
    vig = {c["id"]: (c["vigente_desde"], c["vigente_hasta"]) for c in coms}
    for p in pars:
        p["vigente_desde"], p["vigente_hasta"] = vig.get(p["doc_id"], ("", ""))
    return coms, probs, pars, val


def cargar_estado():
    ruta = DIR / "estado.json"
    return json.loads(ruta.read_text(encoding="utf-8")) if ruta.exists() else {}


def guardar_estado(estado):
    escribir_atomico(DIR / "estado.json", json.dumps(estado, ensure_ascii=False, indent=1, sort_keys=True).encode("utf-8"))

