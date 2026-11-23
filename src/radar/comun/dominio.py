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


def en_texto(texto, largo):
    """El texto pegado trata del tema (regla de Verificar): corto, una palabra; largo, dos o el fenómeno."""
    if nombra_el_fenomeno(texto):
        return True
    return len(palabras_del_tema(texto)) >= (MINIMO_LARGO if largo else 1)
