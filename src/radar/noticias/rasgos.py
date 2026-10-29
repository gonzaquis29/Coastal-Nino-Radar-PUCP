"""Rasgos de una nota calculados en memoria: menciones de El Niño, actores citados, comunicados del ENFEN
enlazados o citados, magnitudes y enlaces a sitios oficiales."""

import datetime as dt
import functools
import re
from urllib.parse import unquote, urlsplit

from radar import config
from radar.comun.archivos import leer_csv
from radar.comun.texto import fecha_es
from radar.noticias.filtro import palabras, terminos
from radar.oficial import enfen
from radar.oficial.vocabulario import ESCALA_MAGNITUD, REGION_CENTRAL, REGION_COSTERA

PALABRAS_PRIMER_PARRAFO = 60  # "sobre El Niño" = lo nombran el titular, el resumen o este inicio del cuerpo
DIAS_INFORME_A_COMUNICADO = 3  # el informe técnico sale entre 0 y 3 días antes de su comunicado
# Cómo se identificó el comunicado de una nota, del más estricto al más amplio (definicion.md, control positivo)
NIVELES_COMUNICADO = ("enlace", "numero", "proximo", "informe")

NINO = re.compile(
    r"\b(?:(?:[Ff]en[óo]meno|[Ee]vento)\s+(?:de\s+)?)?(?:El|del|de El)\s+Niño\b(?!\s+(?:Jesús|Dios))"
    r"|\bNiño\s+[Cc]ostero\b|\bNiño\s+[Gg]lobal\b|\b[Mm]ega\s?-?[Nn]iño\b|\bLa\s+Niña\b|\bENFEN\b|\bEnfen\b"
)
# "Hospital del Niño", "Instituto Nacional de Salud del Niño", "Día del Niño": no son el fenómeno
NO_ES_EL_FENOMENO = re.compile(r"(?:Hospital|Salud|Día|Dia|Instituto|Derechos|Casa|Juzgado)\s+$", re.I)
CITA_NUMERO = re.compile(
    r"[Cc]omunicado\s+(?:(?P<tipo>[Oo]ficial|[Ee]xtraordinario)\s+)?(?:(?:del?\s+)?(?:ENFEN|Enfen)\s+)?"
    r"(?:N\.?\s*[°º]?\s*|n[úu]mero\s+)?0?(?P<numero>\d{1,2})\s*[-–]\s*(?P<anio>20\d\d)"
)
CITA_PROXIMO = re.compile(r"pr[óo]ximo\s+[Cc]omunicado[^.]{0,80}?(\d{1,2}\s+de\s+\w+\s+(?:de|del)\s+\d{4})")
SLUG_COMUNICADO = re.compile(r"comunicado-(oficial|extraordinario)-enfen-n-?0?(\d{1,2})-(20\d\d)")


def menciones(texto):
    texto = texto or ""
    return sum(
        1 for m in NINO.finditer(texto) if not NO_ES_EL_FENOMENO.search(texto[max(0, m.start() - 20) : m.start()])
    )


def nino_en_inicio(resumen, cuerpo):
    """El Niño aparece en el resumen o en el primer párrafo. No mira el titular: es la referencia con que se mide
    lo que pierde el filtro por título."""
    inicio = " ".join((cuerpo or "").split()[:PALABRAS_PRIMER_PARRAFO])
    return bool(menciones(resumen) or menciones(inicio))


def terminos_cuerpo(cuerpo):
    return sorted(palabras(cuerpo) & terminos())


@functools.cache
def _actores():
    return tuple((f["actor"], re.compile(f["patron"])) for f in leer_csv(config.ARCHIVO_ACTORES))


def actores(texto):
    """{actor: menciones} de los actores de config/actores.csv que aparecen en el texto."""
    return {actor: n for actor, patron in _actores() if (n := len(patron.findall(texto or "")))}


def magnitudes(texto):
    """Magnitudes de El Niño que menciona el texto, con la regla del ENFEN (enfen.magnitudes_de_frase). Cuenta la frase
    que nombra a El Niño o sigue a una que lo nombra en la misma línea; no las del Pacífico central ("Niño global")."""
    encontradas = set()
    for linea in (texto or "").split("\n"):
        region, nombra = None, False
        for frase in enfen.FRASE.split(linea):
            if enfen.MENCIONA_CENTRAL.search(frase):
                region = REGION_CENTRAL
            elif enfen.MENCIONA_COSTERA.search(frase):
                region = REGION_COSTERA
            nombra = nombra or menciones(frase) > 0
            if nombra and region != REGION_CENTRAL:
                encontradas.update(valor for valor, _ in enfen.magnitudes_de_frase(frase))
    return sorted(encontradas, key=ESCALA_MAGNITUD.index)


def oficial(url):
    return urlsplit(url).netloc.lower().endswith("gob.pe")


# ---------------------------------------------------------------- comunicados del ENFEN


@functools.cache
def _comunicados():
    return tuple(leer_csv(config.DIR_OFICIAL / "comunicados.csv"))


def _por_numero(tipo, numero, anio):
    tipo = "extraordinario" if tipo and tipo.lower().startswith("extra") else "oficial"
    return next(
        (c["id"] for c in _comunicados() if (c["tipo"], c["numero"], c["anio"]) == (tipo, str(int(numero)), anio)),
        None,
    )


def _por_informe(fecha):
    """Comunicado emitido entre 0 y DIAS_INFORME_A_COMUNICADO días después de la fecha de un informe técnico."""
    if not fecha:
        return None
    dia = dt.date.fromisoformat(fecha)
    for c in _comunicados():
        if 0 <= (dt.date.fromisoformat(c["fecha_emision"]) - dia).days <= DIAS_INFORME_A_COMUNICADO:
            return c["id"]
    return None


def comunicado_de_enlace(url):
    """(id, nivel) del comunicado al que lleva un enlace: el PDF del comunicado o el informe técnico de su fecha."""
    ruta = unquote(urlsplit(url).path.lower())
    m = SLUG_COMUNICADO.search(ruta)
    if m and (ident := _por_numero(*m.groups())):
        return ident, "enlace"
    for c in _comunicados():
        if f"/download/{c['slug']}/" in ruta + "/":
            return c["id"], "enlace"
    if "informe-tecnico" in ruta:
        legible = re.sub(r"de(\d{4})", r"de \1", ruta.replace("-", " ").replace("_", " "))
        if ident := _por_informe(fecha_es(legible)):
            return ident, "informe"
    return None


def comunicados_citados(texto):
    """[(id, nivel)] por el número citado ('Comunicado Oficial N° 09-2026') o la fecha del próximo anunciado."""
    hallados = [(i, "numero") for m in CITA_NUMERO.finditer(texto or "") if (i := _por_numero(*m.groups()))]
    for m in CITA_PROXIMO.finditer(texto or ""):
        fecha = fecha_es(m.group(1))
        hallados += [(c["id"], "proximo") for c in _comunicados() if fecha and c["proximo_anunciado"] == fecha]
    return hallados


def comunicados(texto, enlaces):
    """'id:nivel' únicos de la nota, ordenados por id y nivel."""
    pares = set(comunicados_citados(texto)) | {p for u in enlaces if (p := comunicado_de_enlace(u))}
    return sorted(f"{i}:{n}" for i, n in pares)
