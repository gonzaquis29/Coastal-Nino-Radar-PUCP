"""Comunicados del ENFEN: lista, descarga, campos y filas del corpus (definición en docs/oficial/definicion.md)."""

import datetime as dt
import logging
import re

from lxml import etree, html

from radar import config
from radar.comun.archivos import escribir_atomico, leer_csv, ruta_segura, sha256
from radar.comun.http import Rechazado
from radar.comun.regiones import regiones_mencionadas
from radar.comun.texto import clave, fecha_es, norm, sha1_corto
from radar.oficial import enfen_pdf
from radar.oficial.vocabulario import (
    CALOR,
    ESCALA_MAGNITUD,
    ESTADOS_ENFEN,
    LLUVIAS,
    PESCA,
    PREVENCION,
    REGION_CENTRAL,
    REGION_COSTERA,
)

log = logging.getLogger(__name__)

HOST = "enfen.imarpe.gob.pe"
BASE = f"https://{HOST}"
DIR = config.DIR_RAW_OFICIAL / "enfen"
SEMILLAS = ["comunicado-oficial-enfen-n13-2025"]  # vigente del 1 al 14-ene-2026 (No Activo)
SLUG = re.compile(r"^comunicado-(oficial|extraordinario)-enfen-[a-z0-9-]+$")
SLUG_NUMERO = re.compile(r"n-?(\d{1,2})-(\d{4})$")
NS = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9"}
PARSER_XML = etree.XMLParser(resolve_entities=False, no_network=True)
NUMERO = re.compile(r"COMUNICADO (OFICIAL|EXTRAORDINARIO) ENFEN\s*N\s*°\s*0?(\d{1,2})\s*[-–]\s*(\d{4})")
PROXIMO = re.compile(r"próximo Comunicado Oficial[^.]*?(\d{1,2}\s+de\s+\w+\s+del?\s+\d{4})", re.I)
VENTANA_FECHA, VENTANA_ESTADO = 80, 120  # caracteres tras el número donde están la fecha y el estado
SECCIONES_TEXTO = ("titular", "resumen", "cuerpo")


# ---------------------------------------------------------------- lista de documentos y descarga


def _slugs_de_urls():
    slugs = []
    for ruta in sorted(config.DIR_URLS.glob("*.csv")):
        if not re.match(r"^\d{4}-\d{2}-\d{2}_[a-z]+\.csv$", ruta.name):
            continue
        for fila in leer_csv(ruta):
            if (
                fila["medio"] == "enfen" and "/download/" in fila["url"] and SLUG.match(fila["id"])
            ):  # no las entradas del blog
                slugs.append(fila["id"])
    return slugs


def documentos(cliente):
    """Slugs de comunicados (data/urls + semillas + sitemap), su lastmod y avisos para el reporte."""
    slugs, avisos, lastmod = _slugs_de_urls(), [], {}
    try:
        raiz = etree.fromstring(cliente.get(BASE + "/wpdmpro-sitemap.xml").content, PARSER_XML)
        for u in raiz.findall("s:url", NS):
            m = re.match(BASE + r"/download/([^/]+)/?$", (u.findtext("s:loc", namespaces=NS) or "").strip())
            if m and SLUG.match(m.group(1)):
                lastmod[m.group(1)] = (u.findtext("s:lastmod", namespaces=NS) or "").strip()
    except Exception as e:  # sin sitemap se trabaja con data/urls y lo ya descargado
        log.debug("sitemap del ENFEN", exc_info=True)
        avisos.append(f"sitemap del ENFEN no disponible: {type(e).__name__} {e}"[:200])
    for slug, mod in lastmod.items():
        if mod[:10] >= config.INICIO.isoformat() and slug not in slugs:
            slugs.append(slug)
            avisos.append(f"{slug} está en el sitemap pero no en data/urls (¿se corrió el recolector diario?)")
    return list(dict.fromkeys(SEMILLAS + slugs)), lastmod, avisos


def descargar(cliente, slug, lastmod, estado):
    """Página de descarga + PDF si es nuevo o cambió el lastmod. Devuelve True si cambió el PDF."""
    previo = estado.get(slug)
    pdf = ruta_segura(DIR, slug + ".pdf")
    if pdf.exists() and previo.get("lastmod") == lastmod and previo.get("sha256"):
        return False
    pagina = cliente.get(f"{BASE}/download/{slug}/")
    enlaces = sorted({a for a in html.fromstring(pagina.content).xpath("//a/@href") if "wpdmdl=" in a and slug in a})
    m = re.search(r"wpdmdl=(\d+)", enlaces[0]) if enlaces else None
    if not m:
        raise Rechazado(f"{slug}: la página no tiene enlace de descarga")
    r = cliente.get(f"{BASE}/download/{slug}/?wpdmdl={m.group(1)}", pdf=True)
    escribir_atomico(ruta_segura(DIR, slug + ".html"), pagina.content)
    huella = sha256(r.content)
    cambio = huella != previo.get("sha256")
    if cambio:
        escribir_atomico(pdf, r.content)
    estado.marcar(
        slug, {"lastmod": lastmod, "sha256": huella, "descargado": dt.datetime.now().isoformat(timespec="seconds")}
    )
    return cambio


# ---------------------------------------------------------------- campos


def proximo_anunciado(texto):
    m = PROXIMO.search(texto)
    return fecha_es(m.group(1)) if m else None


def campos(texto):
    """Tipo, número, año, fecha de emisión, estado y próximo comunicado anunciado."""
    c = {"tipo": None, "numero": None, "anio": None, "fecha_emision": None, "estado": None, "proximo_anunciado": None}
    m = NUMERO.search(texto)
    if not m:
        return c
    c["tipo"], c["numero"], c["anio"] = m.group(1).lower(), int(m.group(2)), int(m.group(3))
    c["fecha_emision"] = fecha_es(texto[m.end() : m.end() + VENTANA_FECHA])
    cabecera = texto[m.end() : m.end() + VENTANA_ESTADO]
    estados = [e for e in ESTADOS_ENFEN if re.search(re.escape(e).replace(r"\ ", r"\s+"), cabecera, re.I)]
    c["estado"] = estados[0] if len(estados) == 1 else None
    c["proximo_anunciado"] = proximo_anunciado(texto)
    return c


TERMINO = re.compile(r"\b(débil(?:es)?|moderad[ao]s?|muy fuertes?|fuertes?|extraordinari[ao]s?)\b", re.I)
MENCIONA_CENTRAL = re.compile(r"Niño 3\.4|Pacífico (ecuatorial )?central|\bONI\b|\bRONI\b", re.I)
MENCIONA_COSTERA = re.compile(r"Niño 1\+2|Niño Costero|costa peruana|costero", re.I)
NO_ES_MAGNITUD = re.compile(r"lluvia|precipitaci|intensidad|caudal|crecida|viento", re.I)
HABLA_DE_MAGNITUD = re.compile(r"magnitud|cálidas? débil|evento", re.I)
POSIBLE = re.compile(r"no se descarta|podría alcanzar|pudiendo|aunque podría|sin descartar|sin embargo", re.I)
ANTES_DEL_TERMINO = 80  # caracteres antes de una magnitud donde se busca "no se descarta" y similares


def magnitud_canonica(termino):
    """'Moderado', 'extraordinarios', 'Muy Fuerte' → término de ESCALA_MAGNITUD."""
    t = termino.lower()
    if t.startswith("muy"):
        return "muy fuerte"
    return next(e for e in ESCALA_MAGNITUD if e != "muy fuerte" and t.startswith(e[:5]))


def _frases_costeras(parrafos):
    """Frases de la región Niño 1+2 (la que no nombra región hereda la de la frase anterior del mismo párrafo)."""
    for p in parrafos:
        region = None
        for frase in re.split(r"(?<=[.;])\s+(?=[A-ZÁÉÍÓÚ¿•])", p):
            if MENCIONA_CENTRAL.search(frase):
                region = REGION_CENTRAL
            elif MENCIONA_COSTERA.search(frase):
                region = REGION_COSTERA
            if region == REGION_COSTERA:
                yield frase


def magnitud(parrafos):
    """(máxima prevista en el escenario principal, todas las mencionadas) para El Niño Costero."""
    principal, mencionadas = [], set()
    for frase in _frases_costeras(parrafos):
        if NO_ES_MAGNITUD.search(frase) or not HABLA_DE_MAGNITUD.search(frase):
            continue
        for m in TERMINO.finditer(frase):
            valor = magnitud_canonica(m.group(1))
            mencionadas.add(valor)
            if not POSIBLE.search(frase[: m.start()][-ANTES_DEL_TERMINO:]):
                principal.append(valor)
    maxima = max(principal, key=ESCALA_MAGNITUD.index) if principal else None
    return maxima, sorted(mencionadas, key=ESCALA_MAGNITUD.index)


PLAZO = re.compile(
    r"hasta (?:el |la |los |inicios? del? |mediados del? |finales del? |fines del? )*(?:\w+ )?(?:de |del )?"
    r"(?:\d{4}|presente año|verano|otoño|invierno|primavera)[^,.;]*"
)


def plazo(parrafos):
    """Primer 'hasta …' de una frase sobre El Niño Costero (texto libre, no se evalúa)."""
    for p in parrafos:
        for frase in re.split(r"(?<=[.;])\s+", p):
            if MENCIONA_COSTERA.search(frase) and not MENCIONA_CENTRAL.search(frase):
                m = PLAZO.search(frase)
                if m:
                    return re.split(r"\s+(?:con |\()", m.group(0))[0]
    return None


def probabilidades(tablas):
    """Filas {region, periodo, categoria, probabilidad} de las tablas de probabilidad por magnitud."""
    out = []
    for tabla in tablas:
        filas = tabla["filas"]
        if not filas or len(filas[0]) < 2 or "probabilidad" not in clave(" ".join(c or "" for c in filas[0])):
            continue
        categorias = [clave(f[0] or "") for f in filas[1:]]
        if any("extraordinari" in c for c in categorias):
            region = REGION_COSTERA
        elif any("muy fuerte" in c for c in categorias):
            region = REGION_CENTRAL
        else:
            region = ""
        periodo = re.search(r"\(([^)]*\d{4}[^)]*)\)", norm(filas[0][0] or ""))
        for f in filas[1:]:
            if (f[1] or "").strip().isdigit():
                out.append(
                    {
                        "region": region,
                        "periodo": periodo.group(1) if periodo else "",
                        "categoria": norm(f[0]),
                        "probabilidad": int(f[1]),
                    }
                )
    return out


PALABRAS_TEMA = {
    PESCA: r"pesquer|anchoveta|bonito|perico|jurel|caballa|especies|pez |atún|melva|barrilete|samasa|recursos hidrobiol"
    r"|desembarque",
    LLUVIAS: r"lluvia|precipitaci|caudal|ríos?\b|quebrada|crecida|huaico|desborde|inundaci|embalse|hidrol|mm/día",
    CALOR: r"temperatura(s)? del aire|temperaturas? (máximas|mínimas)|calor|récords?"
    r"|temperaturas? (diurnas?|nocturnas?)"
    r"|radiación ultravioleta",
    PREVENCION: r"tomadores de decisiones|riesgo de desastres|preparación|prevención|autoridades|escenarios de riesgo"
    r"|fuentes oficiales|canales oficiales",
}
TEMA_DE_ROTULO = {
    "lluvias": LLUVIAS,
    "caudales": LLUVIAS,
    "embalses": LLUVIAS,
    "temperatura del aire": CALOR,
    "pesquero": PESCA,
}


def temas_por_palabras(texto):
    return {tema for tema, patron in PALABRAS_TEMA.items() if re.search(patron, texto, re.I)}


def temas(texto):
    """Categorías de interés: el rótulo del ENFEN si existe ("Pesquero:"); si no, palabras clave."""
    m = enfen_pdf.ROTULO.match(texto)
    return {TEMA_DE_ROTULO[m.group(1).lower()]} if m else temas_por_palabras(texto)


# ---------------------------------------------------------------- página de descarga (referencia para validar)

MES_CORTO = {
    "Ene": 1,
    "Feb": 2,
    "Mar": 3,
    "Abr": 4,
    "May": 5,
    "Jun": 6,
    "Jul": 7,
    "Ago": 8,
    "Set": 9,
    "Sep": 9,
    "Oct": 10,
    "Nov": 11,
    "Dic": 12,
}
LARGO_MINIMO_WEB = 30


def pagina(ruta_html, anio):
    """Fecha publicada, estado y párrafos del resumen de la página de descarga."""
    vacia = {"fecha_web": None, "estado_web": None, "parrafos_web": []}
    if not ruta_html.exists():
        return vacia
    doc = html.fromstring(ruta_html.read_bytes())
    for nodo in doc.xpath("//script|//style"):
        nodo.drop_tree()
    articulo = doc.xpath("//article")
    if not articulo:
        return vacia
    texto = norm(articulo[0].text_content())
    m = re.match(r"(\d{1,2}) (\w{3})", texto)
    fecha = (
        dt.date(anio, MES_CORTO[m.group(2)], int(m.group(1))).isoformat()
        if m and m.group(2) in MES_CORTO and anio
        else None
    )
    estado = re.search(r"Estado de sistema de alerta:\s*([^0-9]+?)\d", texto)
    parrafos = [norm(x.text_content()) for x in articulo[0].xpath(".//p|.//li")]
    parrafos = [
        p for p in parrafos if len(p) > LARGO_MINIMO_WEB and "Tamaño del archivo" not in p and "Posted at" not in p
    ]
    return {"fecha_web": fecha, "estado_web": norm(estado.group(1)) if estado else None, "parrafos_web": parrafos}


# ---------------------------------------------------------------- construcción de filas


def _leer_pdf(slug):
    parrafos, tablas, texto = enfen_pdf.extraer(DIR / f"{slug}.pdf")
    c = campos(texto)
    if not (c["numero"] and c["fecha_emision"] and c["estado"]):
        raise ValueError("faltan número, fecha o estado en el PDF")
    return "pdf", parrafos, tablas, texto, c


def _leer_html(slug):
    """Respaldo cuando el PDF no se puede leer: el resumen de la página de descarga."""
    m = SLUG_NUMERO.search(slug)
    web = pagina(DIR / f"{slug}.html", int(m.group(2)) if m else None)
    if not (m and web["fecha_web"] and web["estado_web"] and web["parrafos_web"]):
        raise ValueError("ni el PDF ni la página de descarga tienen los campos")
    texto = " ".join(web["parrafos_web"])
    c = {
        "tipo": "extraordinario" if "extraordinario" in slug else "oficial",
        "numero": int(m.group(1)),
        "anio": int(m.group(2)),
        "fecha_emision": web["fecha_web"],
        "estado": web["estado_web"],
        "proximo_anunciado": proximo_anunciado(texto),
    }
    return "html", [{"seccion": "cuerpo", "texto": t} for t in web["parrafos_web"]], [], texto, c


def identificador(c):
    return f"enfen-{'ext-' if c['tipo'] == 'extraordinario' else ''}{c['anio']}-{c['numero']:02d}"


def _filas_documento(slug, estado):
    try:
        fuente, parrafos, tablas, texto, c = _leer_pdf(slug)
    except Exception:
        log.warning("ENFEN · %s: el PDF no se pudo leer, se usa la página de descarga", slug)
        log.debug("detalle", exc_info=True)
        fuente, parrafos, tablas, texto, c = _leer_html(slug)
    ident = identificador(c)
    web = pagina(DIR / f"{slug}.html", c["anio"])
    textos = [p["texto"] for p in parrafos if p["seccion"] in SECCIONES_TEXTO]
    maxima, mencionadas = magnitud(textos)
    previo = estado.get(slug)
    comunicado = {
        "id": ident,
        "tipo": c["tipo"],
        "numero": c["numero"],
        "anio": c["anio"],
        "fecha_emision": c["fecha_emision"],
        "fecha_web": web["fecha_web"],
        "estado": c["estado"],
        "magnitud_max_prevista": maxima,
        "magnitudes_mencionadas": mencionadas,
        "plazo": plazo(textos),
        "proximo_anunciado": c["proximo_anunciado"],
        "titular": next((p["texto"] for p in parrafos if p["seccion"] == "titular"), ""),
        "slug": slug,
        "url": f"{BASE}/download/{slug}/",
        "lastmod": previo.get("lastmod", ""),
        "sha256_pdf": previo.get("sha256", ""),
        "fuente_texto": fuente,
        "n_parrafos": len(parrafos),
    }
    probs = [{"comunicado_id": ident, **r} for r in probabilidades(tablas)]
    filas_parrafos = []
    for i, p in enumerate(parrafos, start=1):
        dup = p.get("duplicado_de")
        filas_parrafos.append(
            {
                "id": f"{ident}-p{i:02d}",
                "doc_id": ident,
                "fuente": "enfen",
                "orden": i,
                "seccion": p["seccion"],
                "texto": p["texto"],
                "fecha_doc": c["fecha_emision"],
                "macroregiones": regiones_mencionadas(p["texto"]),
                "temas": temas(p["texto"]) if p["seccion"] != "definicion" else set(),
                "duplicado_de": f"{ident}-p{dup + 1:02d}" if dup is not None else "",
                "sha1": sha1_corto(p["texto"]),
            }
        )
    control = {"slug": slug, "texto": texto, "parrafos": textos, "tablas": tablas, "web": web, "campos": c}
    return comunicado, probs, filas_parrafos, control


def _agregar_vigencia(comunicados, parrafos):
    """Cada comunicado rige desde su emisión hasta el día anterior al siguiente; el último queda abierto."""
    comunicados.sort(key=lambda c: (c["fecha_emision"] or "", c["tipo"], c["numero"]))
    for actual, siguiente in zip(comunicados, [*comunicados[1:], None], strict=True):
        actual["vigente_desde"] = actual["fecha_emision"]
        actual["vigente_hasta"] = (
            (dt.date.fromisoformat(siguiente["fecha_emision"]) - dt.timedelta(days=1)).isoformat() if siguiente else ""
        )
    vigencia = {c["id"]: (c["vigente_desde"], c["vigente_hasta"]) for c in comunicados}
    for p in parrafos:
        p["vigente_desde"], p["vigente_hasta"] = vigencia.get(p["doc_id"], ("", ""))


def construir(slugs, estado):
    """Filas de comunicados, probabilidades y párrafos desde data/raw (determinista).

    Un documento que falla no detiene al resto: queda en `errores`.
    """
    comunicados, probs, parrafos, control, errores = [], [], [], {}, {}
    for slug in slugs:
        if not (DIR / f"{slug}.pdf").exists():
            continue
        try:
            com, pr, pa, ctrl = _filas_documento(slug, estado)
        except Exception as e:
            log.debug("ENFEN · %s", slug, exc_info=True)
            errores[slug] = f"{type(e).__name__}: {e}"[:200]
            continue
        comunicados.append(com)
        probs += pr
        parrafos += pa
        control[com["id"]] = ctrl
    _agregar_vigencia(comunicados, parrafos)
    return comunicados, probs, parrafos, control, errores
