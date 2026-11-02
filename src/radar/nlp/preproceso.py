"""Preprocesamiento de textos para TF-IDF y tópicos (docs/nlp/tfidf.md): El Niño y La Niña como un solo término,
lemas de spaCy en minúsculas, sin stopwords, números, signos ni nombres de los medios. Devuelve bolsas de lemas
(lema → veces): nunca la secuencia, que permitiría reconstruir el texto.
"""

import collections
import functools

from radar import config
from radar.noticias import rasgos

EL_NINO, LA_NINA = "el_niño", "la_niña"
TERMINOS_FENOMENO = (EL_NINO, LA_NINA)
# Marcadores que spaCy deja como una sola palabra (un guion bajo la partiría); se cambian por el término después de
# lematizar, sin pasar por el lematizador
_MARCADORES = {"xfenninox": EL_NINO, "xfenninax": LA_NINA}
_SIGLAS_ENFEN = {"ENFEN", "Enfen"}  # NINO las cuenta como mención, pero aquí siguen siendo el lema "enfen"
# Nombres de los medios y de sus secciones de marca: dirían de qué medio es la nota, no de qué trata
NOMBRES_MEDIOS = frozenset({"andina", "rpp", "exitosa", "eltiempo", "rotafono"})
LARGO_MINIMO = 2
_LOTE_SPACY = 32


@functools.cache
def modelo():
    import spacy

    return spacy.load(config.MODELO_SPACY, disable=["parser", "ner"])


@functools.cache
def stopwords():
    return frozenset(modelo().Defaults.stop_words)


def marcar_fenomeno(texto):
    """Cambia cada mención de El Niño o La Niña (según noticias.rasgos) por su marcador. Devuelve (texto, menciones)."""
    texto = texto or ""
    partes, ultimo, n = [], 0, 0
    for m in rasgos.menciones_en(texto):
        if m.group(0) in _SIGLAS_ENFEN:
            continue
        marcador = "xfenninax" if m.group(0).endswith("Niña") else "xfenninox"
        partes += [texto[ultimo : m.start()], f" {marcador} "]
        ultimo, n = m.end(), n + 1
    return "".join(partes) + texto[ultimo:], n


def _lema(token):
    if (marcado := _MARCADORES.get(token.text.lower())) is not None:
        return marcado
    if not token.is_alpha or token.is_stop or token.like_num:
        return None
    lema = token.lemma_.lower().split(" ")[0]  # "adelantarse" → "adelantar él": el clítico no es un término
    if len(lema) < LARGO_MINIMO or lema in NOMBRES_MEDIOS or lema in stopwords():
        return None
    return lema


def bolsa_de(doc):
    return collections.Counter(lema for t in doc if (lema := _lema(t)))


def bolsas(textos):
    """Una bolsa por texto, en orden. Los textos ya traen los marcadores de marcar_fenomeno."""
    return [bolsa_de(doc) for doc in modelo().pipe(textos, batch_size=_LOTE_SPACY)]


def bolsa(texto):
    return bolsas([marcar_fenomeno(texto)[0]])[0]


def a_celda(bolsa_):
    """'lema veces|…' en orden alfabético: lo único que se guarda de cada texto."""
    return "|".join(f"{lema} {n}" for lema, n in sorted(bolsa_.items()))


def de_celda(celda):
    return collections.Counter({lema: int(n) for lema, n in (p.rsplit(" ", 1) for p in celda.split("|") if p)})
