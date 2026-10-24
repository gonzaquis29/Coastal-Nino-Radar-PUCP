"""Avisos meteorológicos del Senamhi: alcance, descarga y filas del corpus (ver docs/oficial/definicion.md)."""

import datetime as dt
import json
import logging
import re
from urllib.parse import quote, urlencode

from radar import config
from radar.comun.archivos import guardar_gz, leer_gz, ruta_segura
from radar.comun.geo import punto_en_geometria
from radar.comun.regiones import COSTA_CENTRO, COSTA_NORTE, deps_por_macroregion_avisos, estaciones_costa
from radar.comun.registro import describir
from radar.comun.texto import sha1_corto, sin_tildes
from radar.oficial.senamhi_paginas import leer_detalle, leer_mapa, mapas_del_panel, panel_aviso
from radar.oficial.vocabulario import (
    CANCELADO,
    EMITIDO,
    NIVEL_MINIMO_AVISO,
    PRECIPITACIONES,
    TEMA_DE_TIPO_AVISO,
    TEMPERATURA,
    VENCIDO,
    VIGENTE,
    nivel_por_numero,
)

log = logging.getLogger(__name__)

BASE = config.URL_SENAMHI
SOLO_ZONAS_CON_AVISO = quote(f"nivel<>'Nivel {NIVEL_MINIMO_AVISO - 1}'", safe="")
WFS = (  # polígonos oficiales de cada día
    f"https://{config.HOST_SENAMHI_GIS}/geoserver/g_aviso/ows?service=WFS&version=1.0.0&request=GetFeature"
    "&typeName=g_aviso:view_aviso&viewparams=qry:{num}_{mapa}_{anio}&outputFormat=application/json"
    f"&propertyName=nivel,nro_mapa,geom&cql_filter={SOLO_ZONAS_CON_AVISO}"
)
DIR = config.DIR_RAW_OFICIAL / "senamhi"
ARCHIVO_TABLA = DIR / "tabla.html.gz"
ALCANCE, CONTROL = "alcance", "control"
SEGMENTO_DE_MACRO = {COSTA_NORTE: "norte", COSTA_CENTRO: "centro"}
TODA_LA_COSTA = {"norte", "centro", "sur"}
DEPARTAMENTOS_NORTE = ("TUMBES", "PIURA", "LAMBAYEQUE", "LA LIBERTAD")
RELACION = re.compile(r"\((EXTENSI[OÓ]N|ACTUALIZACI[OÓ]N) DEL AVISO (\d+)\)")


# ---------------------------------------------------------------- alcance


def sin_parentesis(titulo):
    return re.sub(r"\s*\(.*?\)", "", titulo)


def tipo(titulo):
    """precipitaciones, temperatura o None (llovizna, viento, friaje, nevada, descensos de temperatura)."""
    t = sin_parentesis(titulo)
    if re.search(r"PRECIPITACION|LLUVIA", t):
        return PRECIPITACIONES
    if re.search(r"INCREMENTO DE TEMPERATURA", t):
        return TEMPERATURA
    return None


def segmentos(texto):
    """Tramos de costa que nombra un texto: norte, centro, sur ('COSTA' sin calificar = los tres)."""
    t = sin_tildes(texto).upper()
    encontrados = set()
    for m in re.finditer(r"COSTA((?:\s*(?:,|\bY\b)?\s*\b(?:NORTE|CENTRO|CENTRAL|SUR)\b)*)", t):
        calificador = m.group(1)
        if not calificador.strip():
            encontrados |= TODA_LA_COSTA
        for palabra, segmento in (("NORTE", "norte"), ("CENTR", "centro"), ("SUR", "sur")):
            if palabra in calificador:
                encontrados.add(segmento)
    if any(re.search(r"\b" + d + r"\b", t) for d in DEPARTAMENTOS_NORTE):
        encontrados.add("norte")
    return encontrados


def candidato(fila):
    """ALCANCE: precipitación o temperatura con costa en el título; CONTROL: solo sierra (para medir el filtro)."""
    vigente_en_periodo = fila["emision"][:4] >= str(config.INICIO.year) or fila["fin"] >= config.INICIO.isoformat()
    if not tipo(fila["titulo"]) or not vigente_en_periodo:
        return None
    titulo = sin_parentesis(fila["titulo"])
    if segmentos(titulo):
        return ALCANCE
    if "SIERRA" in titulo:
        return CONTROL
    return None  # avisos solo de selva


def firma(fila):
    """Lo que identifica el contenido de una fila, sin el sufijo (emitido)/(vigente), que cambia solo con el tiempo."""
    return "|".join(str(fila[k]) for k in ("titulo", "emision", "inicio", "fin", "duracion", "nivel"))


def clave_aviso(fila):
    return f"{fila['anio']}-{fila['numero']:03d}"


def dias_segun_tabla(fila):
    return (dt.date.fromisoformat(fila["fin"]) - dt.date.fromisoformat(fila["inicio"])).days + 1


def url_detalle(fila):
    return (
        BASE
        + "?"
        + urlencode({"p": "aviso-meteorologico-detalle", "a": fila["anio"], "b": fila["b"], "c": "00", "d": "SENA"})
    )


def _ruta(prefijo, clave, mapa=None, extension="html.gz"):
    return ruta_segura(DIR, f"{prefijo}-{clave}{'' if mapa is None else f'-{mapa}'}.{extension}")


# ---------------------------------------------------------------- descarga


def _descargar_detalle_y_mapas(cliente, fila, clave):
    """Página de detalle y mapas diarios. Devuelve (números de mapa, completo)."""
    r = cliente.get(url_detalle(fila))
    guardar_gz(_ruta("detalle", clave), r.content)
    panel = panel_aviso(r.content, fila)
    if panel is None:
        return [], False
    mapas = mapas_del_panel(panel)
    for numero, nivel in mapas:
        url = (
            BASE
            + "mapas/mapa-avisos-meteorologicos/index.php?"
            + urlencode({"av": fila["numero"], "nl": nivel, "mp": numero, "fc": fila["anio"]})
        )
        guardar_gz(_ruta("mapa", clave, numero), cliente.get(url).content)
    return [numero for numero, _ in mapas], True


def descargar(cliente, fila, clase, estado):
    """Detalle, mapas y polígonos de un aviso; solo si cambió su fila, seguía emitido/vigente o quedó incompleto."""
    clave = clave_aviso(fila)
    previo = estado.get(clave)
    if (
        previo.get("firma") == firma(fila)
        and previo.get("estado_tabla") not in (EMITIDO, VIGENTE)
        and previo.get("completo")
    ):
        return False
    if clase == ALCANCE:
        mapas, completo = _descargar_detalle_y_mapas(cliente, fila, clave)
    else:
        mapas, completo = list(range(1, dias_segun_tabla(fila) + 1)), True
    for numero in mapas:
        try:
            r = cliente.get(WFS.format(num=fila["numero"], mapa=numero, anio=fila["anio"]))
            json.loads(r.content)
            guardar_gz(_ruta("poligono", clave, numero, "json.gz"), r.content)
        except Exception:  # sin polígono se usa la regla de título y departamentos (metodo=regla)
            log.debug("polígono %s-%s", clave, numero, exc_info=True)
            completo = False
    estado.marcar(
        clave,
        {
            "firma": firma(fila),
            "estado_tabla": fila["estado_tabla"],
            "completo": completo,
            "descargado": dt.datetime.now().isoformat(timespec="seconds"),
        },
    )
    return True


# ---------------------------------------------------------------- polígonos


def cobertura(geojson):
    """{estación: (macroregión, nivel máximo 2-4)} de las estaciones de referencia que cubre el polígono oficial."""
    cubiertas = {}
    for feature in geojson.get("features", []):
        nivel = int(re.sub(r"\D", "", feature["properties"].get("nivel", "")) or 0)
        for nombre, macro, x, y in estaciones_costa():
            if punto_en_geometria(x, y, feature.get("geometry")):
                cubiertas[nombre] = (macro, max(cubiertas.get(nombre, (macro, 0))[1], nivel))
    return cubiertas


def _leer_poligono(clave, mapa):
    ruta = _ruta("poligono", clave, mapa, "json.gz")
    return cobertura(json.loads(leer_gz(ruta))) if ruta.exists() else None


# ---------------------------------------------------------------- construcción de filas


def relacion(titulo):
    m = RELACION.search(titulo)
    if not m:
        return "", None
    return ("extension" if m.group(1).startswith("EXT") else "actualizacion"), int(m.group(2))


def _segmentos_del_aviso(fila, detalle):
    """Tramos del título; si dice solo 'COSTA', los que nombran la descripción y los párrafos diarios."""
    seg = segmentos(sin_parentesis(fila["titulo"]))
    if seg == TODA_LA_COSTA:
        seg = segmentos(detalle["general"] + " " + " ".join(detalle["dias"])) or seg
    return seg


def _dias(fila, detalle, ident, clave, control):
    """Filas de aviso_dias y registros de control (regla frente a polígono) de cada mapa del aviso."""
    seg = _segmentos_del_aviso(fila, detalle)
    deps_avisos = deps_por_macroregion_avisos()
    filas = []
    for mapa, nivel_mapa in detalle["mapas"]:
        ruta_mapa = _ruta("mapa", clave, mapa)
        dia = leer_mapa(leer_gz(ruta_mapa)) if ruta_mapa.exists() else {"fecha": None, "deps": []}
        regla = {m for m, s in SEGMENTO_DE_MACRO.items() if s in seg and set(dia["deps"]) & deps_avisos[m]}
        cubiertas = _leer_poligono(clave, mapa)
        if cubiertas is None:
            cubiertas, por_macro, metodo, macros = {}, {}, "regla", regla
        else:
            por_macro = {}
            for macro, nivel in cubiertas.values():
                por_macro[macro] = max(por_macro.get(macro, 0), nivel)
            metodo, macros = "poligono", set(por_macro)
        nivel_dia = nivel_por_numero(int(nivel_mapa)) if nivel_mapa.isdigit() else ""
        for macro in sorted(macros):
            filas.append(
                {
                    "aviso_id": ident,
                    "fecha": dia["fecha"],
                    "mapa": mapa,
                    "macroregion": macro,
                    "nivel_dia": nivel_dia,
                    "nivel_macroregion": nivel_por_numero(por_macro[macro]) if macro in por_macro else nivel_dia,
                    "estaciones": sorted(n for n, (m, _) in cubiertas.items() if m == macro),
                    "departamentos": sorted(set(dia["deps"]) & deps_avisos[macro]),
                    "metodo": metodo,
                }
            )
        control.append(
            {
                "clase": ALCANCE,
                "aviso_id": ident,
                "mapa": mapa,
                "fecha": dia["fecha"],
                "regla": sorted(regla),
                "poligono": sorted(por_macro) if metodo == "poligono" else None,
                "nivel_dia": nivel_dia,
            }
        )
    return filas


def _parrafos(fila, detalle, ident, macros):
    textos = [("titulo", fila["titulo"])]
    if detalle["general"]:
        textos.append(("descripcion", detalle["general"]))
    textos += [("dia", t) for t in detalle["dias"]]
    tema = {TEMA_DE_TIPO_AVISO[tipo(fila["titulo"])]}
    fin = (detalle["fin"] or fila["fin"])[:10]
    return [
        {
            "id": f"{ident}-p{i:02d}",
            "doc_id": ident,
            "fuente": "senamhi",
            "orden": i,
            "seccion": seccion,
            "texto": texto,
            "fecha_doc": fila["emision"],
            "vigente_desde": fila["emision"],
            "vigente_hasta": fin,
            "macroregiones": sorted(macros),
            "temas": tema,
            "duplicado_de": "",
            "sha1": sha1_corto(texto),
        }
        for i, (seccion, texto) in enumerate(textos, start=1)
    ]


def _aviso(fila, detalle, ident, macros, dias):
    rel, numero_rel = relacion(fila["titulo"])
    estado = CANCELADO if "CANCELADO" in fila["titulo"] else (fila["estado_tabla"] or VENCIDO)
    return {
        "id": ident,
        "anio": int(fila["anio"]),
        "numero": fila["numero"],
        "b": fila["b"],
        "titulo": fila["titulo"],
        "tipo": tipo(fila["titulo"]),
        "nivel": fila["nivel"],
        "estado": estado,
        "relacion": rel,
        "aviso_relacionado": f"senamhi-{fila['anio']}-{numero_rel:03d}" if numero_rel else "",
        "emision": fila["emision"],
        "inicio": detalle["inicio"],
        "fin": detalle["fin"],
        "duracion": fila["duracion"],
        "macroregiones": sorted(macros),
        "metodo_macroregion": "poligono" if all(d["metodo"] == "poligono" for d in dias) else "regla",
        "url": url_detalle(fila),
    }


def _control_sierra(fila, ident, clave, control):
    for mapa in range(1, dias_segun_tabla(fila) + 1):
        cubiertas = _leer_poligono(clave, mapa)
        if cubiertas is not None:
            control.append(
                {"clase": CONTROL, "aviso_id": ident, "mapa": mapa, "cubre": sorted({m for m, _ in cubiertas.values()})}
            )


def _filas_aviso(fila, clase, control):
    clave = clave_aviso(fila)
    ident = f"senamhi-{clave}"
    if clase == CONTROL:
        _control_sierra(fila, ident, clave, control)
        return None
    ruta = _ruta("detalle", clave)
    detalle = leer_detalle(leer_gz(ruta), fila) if ruta.exists() else None
    if detalle is None:
        raise ValueError("sin panel de detalle")
    dias = _dias(fila, detalle, ident, clave, control)
    control.append(
        {
            "clase": "detalle",
            "aviso_id": ident,
            "tabla": fila,
            "detalle": {k: detalle[k] for k in ("numero", "nivel", "titulo", "emision", "inicio", "fin")},
            "niveles_mapas": [n for _, n in detalle["mapas"]],
            "fechas_mapas": [d["fecha"] for d in dias],
        }
    )
    macros = {d["macroregion"] for d in dias}
    if not macros:
        return None  # el aviso no toca la costa norte ni la centro (p. ej., solo costa sur)
    return _aviso(fila, detalle, ident, macros, dias), dias, _parrafos(fila, detalle, ident, macros)


def construir(tabla):
    """Filas de avisos, días por macro-región y párrafos desde data/raw (determinista).

    Un aviso que falla no detiene al resto: queda en `errores`.
    """
    avisos, dias, parrafos, control, errores = [], [], [], [], {}
    for fila in tabla:
        clase = candidato(fila)
        if not clase:
            continue
        try:
            resultado = _filas_aviso(fila, clase, control)
        except Exception as e:
            ident = f"senamhi-{clave_aviso(fila)}"
            log.debug("Senamhi · %s", ident, exc_info=True)
            errores[ident] = describir(e)
            continue
        if resultado:
            aviso, filas_dias, filas_parrafos = resultado
            avisos.append(aviso)
            dias += filas_dias
            parrafos += filas_parrafos
    avisos.sort(key=lambda a: (a["anio"], a["numero"]))
    dias.sort(key=lambda d: (d["aviso_id"], d["mapa"], d["macroregion"]))
    return avisos, dias, parrafos, control, errores
