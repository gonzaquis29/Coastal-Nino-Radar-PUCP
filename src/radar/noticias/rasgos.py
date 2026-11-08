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
    # tras "fenómeno" o "evento" vale el artículo en cualquier forma ("Fenómeno el Niño", "fenómeno de EL Niño")
    r"\b(?:[Ff]en[óo]meno|[Ee]vento)\s+(?:de\s+)?(?:[Ee][Ll]|del)\s+Niño\b"
    r"|\b(?:El|del|de El)\s+Niño\b(?!\s+(?:Jesús|Dios))"
    # "el"/"al" en minúscula solo con "Costero": "el Niño Guerrero" o "al Niño Quemado" no son el fenómeno
    r"|\b(?:el|al)\s+Niño\s+[Cc]ostero\b"
    r"|\bNiño\s+[Cc]ostero\b|\bNiño\s+[Gg]lobal\b|\b[Mm]ega\s?-?[Nn]iño\b|\bLa\s+Niña\b|\bENFEN\b|\bEnfen\b|\bFEN\b"
)
# "Hospital del Niño", "Instituto Nacional de Salud del Niño", "Día del Niño", "Código del Niño": no son el fenómeno
NO_ES_EL_FENOMENO = re.compile(r"(?:Hospital|Salud|Día|Dia|Instituto|Derechos|Casa|Juzgado|Código|Codigo)\s+$", re.I)
SIGLA_TRAS_MENCION = re.compile(r"Niño(?:\s+[Cc]ostero)?\s*\($")  # "Fenómeno El Niño (FEN)" es una sola mención
VENTANA_ANTES = 25  # caracteres antes de una mención en que se buscan las palabras que la anulan
CITA_NUMERO = re.compile(
    r"[Cc]omunicado\s+(?:(?P<tipo>[Oo]ficial|[Ee]xtraordinario)\s+)?(?:(?:del?\s+)?(?:ENFEN|Enfen)\s+)?"
    r"(?:N\.?\s*[°º]?\s*|n[úu]mero\s+)?0?(?P<numero>\d{1,2})\s*[-–]\s*(?P<anio>20\d\d)"
)
CITA_PROXIMO = re.compile(r"pr[óo]ximo\s+[Cc]omunicado[^.]{0,80}?(\d{1,2}\s+de\s+\w+\s+(?:de|del)\s+\d{4})")
# Una cita por número es del ENFEN solo si cerca se nombra al ENFEN o a El Niño: "Comunicado N.° 5-2026" también lo
# emiten la FAP, la PNP o el Minedu (arreglo del 8-nov-2026, definicion.md)
VENTANA_CITA = 300  # caracteres antes y después de la cita
COMISION = re.compile(r"Comisi[óo]n\s+Multisectorial")
SLUG_COMUNICADO = re.compile(r"comunicado-(oficial|extraordinario)-enfen-n-?0?(\d{1,2})-(20\d\d)")


@functools.cache
def _lugar_antes():
    """ "laguna La Niña", "sector La Niña": palabras de config/lugares_la_nina.csv justo antes de "La Niña"."""
    palabras = "|".join(re.escape(f["palabra"]) for f in leer_csv(config.ARCHIVO_LUGARES_LA_NINA))
    return re.compile(rf"(?<!\w)(?:{palabras})\s+$", re.I)


def _es_el_fenomeno(texto, m):
    antes = texto[max(0, m.start() - VENTANA_ANTES) : m.start()]
    if NO_ES_EL_FENOMENO.search(antes):
        return False
    if m.group(0) == "FEN":
        return not SIGLA_TRAS_MENCION.search(antes)
    return not (m.group(0).endswith("Niña") and _lugar_antes().search(antes))


def menciones_en(texto):
    """Coincidencias de NINO que son el fenómeno, en orden (el preprocesamiento las une en un solo término)."""
    texto = texto or ""
    return [m for m in NINO.finditer(texto) if _es_el_fenomeno(texto, m)]


def menciones(texto):
    return len(menciones_en(texto))


def nino_en_inicio(resumen, cuerpo, contar=menciones):
    """El Niño aparece en el resumen o en el primer párrafo. No mira el titular: es la referencia con que se mide
    lo que pierde el filtro por título. `contar` solo cambia en el recálculo, para separar causas."""
    inicio = " ".join((cuerpo or "").split()[:PALABRAS_PRIMER_PARRAFO])
    return bool(contar(resumen) or contar(inicio))


def terminos_cuerpo(cuerpo):
    return sorted(palabras(cuerpo) & terminos())


@functools.cache
def _actores():
    return tuple((f["actor"], re.compile(f["patron"])) for f in leer_csv(config.ARCHIVO_ACTORES))


def actores(texto):
    """{actor: menciones} de los actores de config/actores.csv que aparecen en el texto."""
    return {actor: n for actor, patron in _actores() if (n := len(patron.findall(texto or "")))}


def magnitudes(texto, contar=menciones):
    """Magnitudes de El Niño que menciona el texto, con la regla del ENFEN (enfen.magnitudes_de_frase). Cuenta la frase
    que nombra a El Niño o sigue a una que lo nombra en la misma línea; no las del Pacífico central ("Niño global").
    `contar` solo cambia en el recálculo, para separar causas."""
    encontradas = set()
    for linea in (texto or "").split("\n"):
        region, nombra = None, False
        for frase in enfen.FRASE.split(linea):
            if enfen.MENCIONA_CENTRAL.search(frase):
                region = REGION_CENTRAL
            elif enfen.MENCIONA_COSTERA.search(frase):
                region = REGION_COSTERA
            nombra = nombra or contar(frase) > 0
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


def cita_del_enfen(texto, m):
    """La cita por número nombra al ENFEN, o a menos de VENTANA_CITA caracteres aparece el ENFEN o El Niño."""
    cerca = texto[max(0, m.start() - VENTANA_CITA) : m.end() + VENTANA_CITA]
    return menciones(cerca) > 0 or bool(COMISION.search(cerca))


def comunicados_citados(texto):
    """[(id, nivel)] por el número citado ('Comunicado Oficial N° 09-2026') o la fecha del próximo anunciado."""
    texto = texto or ""
    hallados = [(i, "numero") for m in CITA_NUMERO.finditer(texto)
                if cita_del_enfen(texto, m) and (i := _por_numero(*m.groups()))]  # fmt: skip
    for m in CITA_PROXIMO.finditer(texto or ""):
        fecha = fecha_es(m.group(1))
        hallados += [(c["id"], "proximo") for c in _comunicados() if fecha and c["proximo_anunciado"] == fecha]
    return hallados


def comunicados(texto, enlaces):
    """'id:nivel' únicos de la nota, ordenados por id y nivel."""
    pares = set(comunicados_citados(texto)) | {p for u in enlaces if (p := comunicado_de_enlace(u))}
    return sorted(f"{i}:{n}" for i, n in pares)
