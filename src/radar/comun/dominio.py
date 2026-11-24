"""Vocabulario del tema (El Niño, el mar y el clima): un solo lugar para Preguntar y Verificar.

Preguntar (radar.agente) rechaza las consultas sin ninguna de estas palabras. Verificar (radar.app) no mide la
cercanía de un texto que no trata del tema (docs/app/definicion.md, sección 9). Se busca sobre el texto sin tildes.
"""

import re

from radar.comun.texto import sin_tildes
from radar.noticias import rasgos

# Las palabras del agente (ronda c), sin "niño": eso se decide aparte. Correcciones del 23-nov (sección 9.3):
# "calid" aceptaba "calidad" y "costa" aceptaba "Costa Rica"; el "nino\b" sin \b inicial, "femenino".
PALABRAS = re.compile(
    r"enfen|senamhi|clima|lluvi|precipitac|calor|temperatura|\bmar\b|pesca|pescador|anchoveta|aviso|"
    r"alerta|huaico|inundac|oleaje|friaje|sequ[ií]a|caudal|\brios?\b|desborde|verano|meteorol|comunicado|emergencia|"
    r"prevenci|tsm|fenomeno|costa(?!\s+(?:rica|21)\b)|"
    r"vigilancia|calid[oa]s?\b|pacifico|agricul|llov|llue|inunda|preven|quebrada|oceanic|anomal|evento|olas? de|"
    r"pronostic|huayco|desembarc|embarcac",
    re.I,
)
# En una pregunta a esta app, "el niño" casi siempre es el fenómeno (aunque esté en minúsculas)
NINO_EN_PREGUNTA = re.compile(r"\bni[nñ][oa]\b", re.I)
# En un texto pegado, "niño" cuenta solo si nombra el fenómeno: la regla de rasgos o estas formas en cualquier caja
NINO_FENOMENO = re.compile(
    r"\bni[nñ][oa]\s+(?:costero|global)\b|\bfen[oó]meno\s+(?:de\s+)?(?:el\s+|del\s+)?ni[nñ][oa]\b", re.I
)
MINIMO_LARGO = 2  # palabras distintas del tema en un texto largo, donde "alerta" o "costa" aparecen sueltas

# Etiquetas editoriales que pone cada medio (sección 12.3), fijadas antes de medir. Se compara la etiqueta completa,
# en minúsculas y sin tildes. Clima y mar sin «mar», «pesca», «clima» ni «cambio climático», que tienen otro sentido
# (surf, un TLC, un volcán, la COP); esas cuatro sí cuentan para que una nota no sea de otro tema.
ETIQUETAS_CLIMA_MAR = re.compile(
    r"senamhi|imarpe|dhn|lluvias?(?: intensas| fuertes)?|precipitaciones|temporada de lluvias|temperaturas?|calor|"
    r"ola de calor|friaje|heladas?|radiacion uv|huaicos?|huaycos?|inundacion(?:es)?|desbordes?(?: de rios?)?|sequia|"
    r"oleajes?|mar peruano|anchoveta|meteorologia|fenomenos? climaticos?"
)
ETIQUETAS_CON_OTRO_SENTIDO = re.compile(r"mar|pesca|clima|cambio climatico")
ETIQUETAS_OTRO_TEMA = re.compile(
    r"deportes|futbol|mundial 2026|elecciones(?: 2026)?|onpe|jne|congreso|keiko fujimori|papa leon xiv|sismos?|"
    r"terremoto|politica|mundo|estados unidos|policia|delincuencia|extorsion|seguridad ciudadana|educacion|cultura"
)
SEPARADOR_ETIQUETAS = re.compile(r"[,;|]")
# Palabras del tema que también usan los textos de emergencias, política o sismos (sección 13.3), fijadas antes de
# medir. Solas no anclan una «Alta» cuyo párrafo más cercano es una recomendación general del ENFEN.
PALABRAS_GENERICAS = re.compile(
    r"emergencia|alerta|evento|prevenci|preven|comunicado|costa|vigilancia|aviso|fenomeno|anomal"
)


def en_pregunta(consulta):
    """La consulta trata del tema (regla de Preguntar)."""
    llano = sin_tildes(consulta or "")
    return bool(PALABRAS.search(llano) or NINO_EN_PREGUNTA.search(llano))


def nombra_el_fenomeno(texto):
    texto = texto or ""
    return bool(rasgos.menciones(texto) or NINO_FENOMENO.search(texto))


def palabras_del_tema(texto):
    """Las palabras distintas del tema que aparecen (en minúsculas y sin tildes)."""
    return {m.group(0).lower() for m in PALABRAS.finditer(sin_tildes(texto or ""))}


def palabras_especificas(texto):
    """Las palabras del tema que no son genéricas (sección 13.3)."""
    return {p for p in palabras_del_tema(texto) if not PALABRAS_GENERICAS.fullmatch(p)}


def etiquetas(nota):
    """Las etiquetas editoriales de la nota, en minúsculas y sin tildes."""
    return {sin_tildes(e.strip().lower()) for e in SEPARADOR_ETIQUETAS.split(nota.get("etiquetas") or "") if e.strip()}


def etiquetada_clima_mar(nota):
    return any(ETIQUETAS_CLIMA_MAR.fullmatch(e) for e in etiquetas(nota))


def etiquetada_otro_tema(nota):
    """Solo etiquetas de otros temas: ninguna de clima o mar, ni siquiera de las que tienen otro sentido."""
    es = etiquetas(nota)
    if any(ETIQUETAS_CLIMA_MAR.fullmatch(e) or ETIQUETAS_CON_OTRO_SENTIDO.fullmatch(e) for e in es):
        return False
    return any(ETIQUETAS_OTRO_TEMA.fullmatch(e) for e in es)


def en_texto(texto, largo):
    """El texto pegado trata del tema (regla de Verificar): corto, una palabra; largo, dos o el fenómeno."""
    if nombra_el_fenomeno(texto):
        return True
    return len(palabras_del_tema(texto)) >= (MINIMO_LARGO if largo else 1)
