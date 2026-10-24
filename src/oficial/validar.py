"""Pruebas de viabilidad del corpus oficial con referencias externas (criterios fijados en docs/oficial/definicion.md)."""
import collections
import datetime as dt
import difflib
import re

import fitz
from pypdf import PdfReader

from oficial import enfen
from oficial.comun import clave

RESTOS = [("url", r"https?://|www\."), ("cabecera", r"Decreto Supremo|COMISIÓN MULTISECTORIAL|Año de la"),
          ("leyenda", r"\bFigura \d+\.|\bFuente:"), ("marca_pegada", r"[a-záéíóú]\d{1,2}\b(?![.,]\d)"), ("caracter_invalido", "�")]
APERTURAS = [("pesca", r"^En (relación|cuanto) (con |a )?(los |a los )?recursos pesqueros,?|^Pesquero:"),
             ("lluvias", r"^En cuanto al pronóstico hidrológico,?|^Caudales:|^Lluvias:"),
             ("prevencion", r"^Se recomienda a los tomadores de decisiones|^Se exhorta|^Se insta"),
             ("calor", r"^Temperatura del [Aa]ire:")]


def fila(prueba, criterio, ok, total, umbral, detalle="", minimo=None):
    """Una fila del reporte. minimo: proporción exigida; si es None se exige que ok == total."""
    valor = ok / total if total else 1.0
    pasa = (valor >= minimo) if minimo is not None else (ok == total)
    return {"prueba": prueba, "criterio": criterio, "valor": f"{ok}/{total}", "umbral": umbral, "pasa": pasa, "detalle": detalle[:300]}


def _acuerdo_extractores(ruta_pdf):
    a = collections.Counter(clave(" ".join(p.extract_text() or "" for p in PdfReader(ruta_pdf).pages)).split())
    b = collections.Counter(clave(" ".join(p.get_text() for p in fitz.open(ruta_pdf))).split())
    return 2 * sum((a & b).values()) / max(1, sum(a.values()) + sum(b.values()))


def _frases_html(parrafos_web, parrafos_pdf):
    ok, total, faltan = 0, 0, []
    pk = " ".join(clave(p) for p in parrafos_pdf)
    for p in parrafos_web:
        for s in re.split(r"(?<=[.;])\s+", p):
            k = clave(re.sub(r"\d+", " ", s))
            k = re.sub(r"\s+", " ", k).strip()
            if len(k) < 25 or "comunicado oficial enfen" in k or "estado de sistema" in k:
                continue
            total += 1
            pk2 = re.sub(r"\s+", " ", re.sub(r"\d+", " ", pk))
            if k in pk2:
                ok += 1
                continue
            m = difflib.SequenceMatcher(None, pk2, k, autojunk=False).find_longest_match(0, len(pk2), 0, len(k))
            a = max(0, m.a - m.b)
            if difflib.SequenceMatcher(None, pk2[a:a + len(k) + 10], k).ratio() >= 0.9:
                ok += 1
            else:
                faltan.append(s[:80])
    return ok, total, faltan


def validar_enfen(coms, pars, val):
    filas = []
    errores = {k: v["error"] for k, v in val.items() if "error" in v}
    pdf_ok = [c for c in coms if c["fuente_texto"] == "pdf"]
    filas.append(fila("enfen", "comunicados descargados y extraídos del PDF", len(pdf_ok), len(coms) + len(errores), "100 %",
                      "; ".join(f"{k}: {v}" for k, v in errores.items())))
    # número y año del PDF frente al slug (los slugs de 2025 traen errores conocidos; se reporta, no bloquea)
    mal = []
    for c in coms:
        m = re.search(r"n-?(\d{1,2})-(\d{4})$", c["slug"])
        if not m or (int(m.group(1)), int(m.group(2))) != (int(c["numero"]), int(c["anio"])):
            mal.append(f"{c['slug']}→{c['id']}")
    filas.append(fila("enfen", "número y año del PDF = slug", len(coms) - len(mal), len(coms), "100 %", ", ".join(mal)))
    # fecha de emisión frente a la fecha publicada en la página de descarga
    dif = [(c["id"], c["fecha_emision"], c["fecha_web"]) for c in coms if not c["fecha_web"] or
           abs((dt.date.fromisoformat(c["fecha_emision"]) - dt.date.fromisoformat(c["fecha_web"])).days) > 1]
    filas.append(fila("enfen", "fecha de emisión a ±1 día de la fecha de la página", len(coms) - len(dif), len(coms), "100 %", str(dif)))
    # cadena del "próximo comunicado" (también prueba que no falte ninguno)
    ofi = [c for c in coms if c["tipo"] == "oficial"]
    cadena = [(a, b) for a, b in zip(ofi, ofi[1:]) if a["proximo_anunciado"]]
    ok = [1 for a, b in cadena if abs((dt.date.fromisoformat(b["fecha_emision"]) - dt.date.fromisoformat(a["proximo_anunciado"])).days) <= 1]
    filas.append(fila("enfen", "emisión real a ±1 día de la anunciada en el comunicado anterior", len(ok), len(cadena), "≥ 90 %", minimo=0.9,
                      detalle=", ".join(f"{a['id']}→{b['id']}" for a, b in cadena if abs((dt.date.fromisoformat(b['fecha_emision']) - dt.date.fromisoformat(a['proximo_anunciado'])).days) > 1)))
    # estado frente al HTML
    mal = [(c["id"], c["estado"], val[c["id"]]["web"]["estado_web"]) for c in coms
           if (val[c["id"]]["web"]["estado_web"] or "").lower() != (c["estado"] or "").lower()]
    filas.append(fila("enfen", "estado = estado de la página de descarga", len(coms) - len(mal), len(coms), "100 %", str(mal)))
    # magnitud
    activos = [c for c in coms if c["estado"] and c["estado"] != "No Activo"]
    sin = [c["id"] for c in activos if not c["magnitud_max_prevista"]]
    filas.append(fila("enfen", "magnitud extraída (vigilancia o alerta)", len(activos) - len(sin), len(activos), "100 %", ", ".join(sin)))
    sub_ok = sub_n = 0
    det = []
    for c in coms:
        _, en_html = enfen.magnitud(val[c["id"]]["web"]["parrafos_web"])
        if en_html:
            sub_n += 1
            menc = set(c["magnitudes_mencionadas"])
            if set(en_html) <= menc:
                sub_ok += 1
            else:
                det.append(f"{c['id']}: {set(en_html) - menc}")
    filas.append(fila("enfen", "magnitudes del resumen HTML ⊆ magnitudes del PDF", sub_ok, sub_n, "100 %", "; ".join(det)))
    t_ok = t_n = 0
    det = []
    for c in coms:
        ps = [p for p in enfen.probabilidades(val[c["id"]]["tablas"]) if p["region"] == "nino_1+2"]
        if ps:
            t_n += 1
            arg = enfen._canon(re.sub(r"(?i)el niño\s*", "", max(ps, key=lambda p: p["probabilidad"])["categoria"]))
            if arg in c["magnitudes_mencionadas"]:
                t_ok += 1
            else:
                det.append(f"{c['id']}: {arg}")
    filas.append(fila("enfen", "categoría más probable de la tabla ∈ magnitudes mencionadas", t_ok, t_n, "100 %", "; ".join(det)))
    # texto
    bajos = []
    for c in pdf_ok:
        a = _acuerdo_extractores(enfen.DIR / f"{c['slug']}.pdf")
        if a < 0.98:
            bajos.append(f"{c['id']}={a:.3f}")
    filas.append(fila("enfen", "acuerdo PyMuPDF / pypdf ≥ 0,98 por documento", len(pdf_ok) - len(bajos), len(pdf_ok), "100 %", ", ".join(bajos)))
    ok = total = 0
    faltan = []
    for c in pdf_ok:
        o, t, f = _frases_html(val[c["id"]]["web"]["parrafos_web"], val[c["id"]]["parrafos"])
        ok, total, faltan = ok + o, total + t, faltan + f
    filas.append(fila("enfen", "frases del resumen HTML presentes en los párrafos (similitud ≥ 0,9)", ok, total, "≥ 95 %", "; ".join(faltan), minimo=0.95))
    restos = [f"{p['id']}:{n}" for p in pars if p["fuente"] == "enfen" and p["seccion"] != "definicion"
              for n, rx in RESTOS if re.search(rx, p["texto"])]
    texto_pars = sum(1 for p in pars if p["fuente"] == "enfen" and p["seccion"] != "definicion")
    filas.append(fila("enfen", "párrafos sin URL, encabezado, leyenda ni marca de nota", texto_pars - len(restos), texto_pars, "100 %", ", ".join(restos)))
    # temas (informativo): frase de apertura de cada sección como etiqueta, regla aplicada al resto del párrafo
    t_ok = t_n = 0
    for p in pars:
        if p["fuente"] != "enfen" or p["seccion"] not in ("resumen", "cuerpo"):
            continue
        for tema, rx in APERTURAS:
            m = re.match(rx, p["texto"])
            if m:
                t_n += 1
                t_ok += tema in {k for k, r in enfen.TEMAS.items() if re.search(r, p["texto"][m.end():], re.I)}
                break
    filas.append(fila("enfen (informativo)", "temas por palabras clave = tema de la frase de apertura", t_ok, t_n, "referencia", minimo=0.0))
    return filas


def validar_senamhi(avisos, dias, val):
    filas = []
    alc = [v for v in val if v["clase"] == "alcance" and "error" in v]
    det = [v for v in val if v["clase"] == "detalle"]
    filas.append(fila("senamhi", "avisos candidatos con panel de detalle", len(det), len(det) + len(alc), "100 %",
                      ", ".join(v["aviso_id"] for v in alc)))
    mal = []
    for v in det:
        t, d = v["tabla"], v["detalle"]
        chk = {"numero": d["numero"] == t["numero"], "nivel": d["nivel"] == t["nivel"], "titulo": d["titulo"] == t["titulo"],
               "emision": d["emision"] == t["emision"], "inicio": (d["inicio"] or "")[:10] == t["inicio"],
               "fin": (d["fin"] or "")[:10] == t["fin"],
               "dias": all(t["inicio"] <= f <= t["fin"] for f in v["fechas_mapas"] if f)}
        if not all(chk.values()):
            mal.append(f"{v['aviso_id']}:{[k for k, x in chk.items() if not x]}")
    filas.append(fila("senamhi", "número, nivel, título, emisión, inicio y fin del detalle = tabla", len(det) - len(mal), len(det), "100 %", ", ".join(mal)))
    mal = [v["aviso_id"] for v in det if v["niveles_mapas"] and
           max((int(n) for n in v["niveles_mapas"] if n.isdigit()), default=0) != ["", "VERDE", "AMARILLO", "NARANJA", "ROJO"].index(v["tabla"]["nivel"])]
    filas.append(fila("senamhi", "nivel máximo de los mapas diarios = nivel de la tabla", len(det) - len(mal), len(det), "100 %", ", ".join(mal)))
    cancelados = {a["id"] for a in avisos if a["estado"] == "cancelado"}
    for macro in ("costa_norte", "costa_centro"):
        n = ok = 0
        difs = []
        for v in val:
            if v["clase"] != "alcance" or "error" in v or v["poligono"] is None or v["aviso_id"] in cancelados:
                continue
            n += 1
            ok += (macro in v["regla"]) == (macro in v["poligono"])
            if (macro in v["regla"]) != (macro in v["poligono"]):
                difs.append(f"{v['aviso_id']}/{v['mapa']}:{'regla' if macro in v['regla'] else 'polígono'}")
        filas.append(fila("senamhi", f"{macro}: polígono oficial y regla de título/departamentos coinciden", ok, n, "≥ 95 %", ", ".join(difs), minimo=0.95))
    ctrl = [v for v in val if v["clase"] == "control"]
    cubren = [f"{v['aviso_id']}/{v['mapa']}" for v in ctrl if set(v["cubre"]) & {"costa_norte", "costa_centro"}]
    filas.append(fila("senamhi", "avisos sin costa en el título cuyo polígono no toca estaciones de costa norte o centro",
                      len(ctrl) - len(cubren), len(ctrl), "100 %", ", ".join(cubren)))
    dias_ok = {(d["aviso_id"], d["fecha"], d["macroregion"]) for d in dias if d["aviso_id"] not in cancelados}
    tipo = {a["id"]: a["tipo"] for a in avisos}
    sin_reemplazo = []
    for a in avisos:
        if a["estado"] != "cancelado":
            continue
        propios = [(d["fecha"], d["macroregion"]) for d in dias if d["aviso_id"] == a["id"]]
        for f, m in propios:
            if not any(x[1] == f and x[2] == m and tipo[x[0]] == a["tipo"] for x in dias_ok):
                sin_reemplazo.append(f"{a['id']} {f} {m}")
    filas.append(fila("senamhi", "días de avisos cancelados cubiertos por otro aviso del mismo tipo",
                      sum(1 for a in avisos if a["estado"] == "cancelado") - len({s.split()[0] for s in sin_reemplazo}),
                      sum(1 for a in avisos if a["estado"] == "cancelado"), "100 %", ", ".join(sin_reemplazo)))
    regla = [a["id"] for a in avisos if a["metodo_macroregion"] != "poligono"]
    filas.append(fila("senamhi (informativo)", "avisos con macro-región por polígono (el resto usa la regla de respaldo)",
                      len(avisos) - len(regla), len(avisos), "referencia", ", ".join(regla), minimo=0.0))
    return filas
