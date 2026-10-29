"""Validación de la regla de magnitud por cercanía en notas nuevas, con un instrumento independiente: el análisis
sintáctico de spaCy dice de qué sustantivo depende cada término. Criterios fijados antes de correr
(docs/nlp/magnitud.md). Los cuerpos solo viven en memoria; las frases de los casos se muestran en pantalla para
diagnosticarlos y no se guardan.

Uso: python -m radar.noticias.validar_magnitud [--semilla S]   (requiere pip install -e ".[nlp]" y es_core_news_sm)
"""

import argparse
import collections
import logging
import re
import sys

from radar import config
from radar.comun.archivos import leer_csv
from radar.comun.candado import exclusivo
from radar.comun.http import Cliente
from radar.comun.registro import configurar
from radar.comun.texto import ahora, clave
from radar.noticias import rasgos
from radar.noticias.medios import MEDIOS
from radar.noticias.validar_texto import marcar_vistas, notas_vistas, reservada_capa3
from radar.noticias.viabilidad import _muestra, _si, criterio, guardar, reporte
from radar.oficial import enfen
from radar.oficial.vocabulario import REGION_CENTRAL, REGION_COSTERA

log = logging.getLogger(__name__)

PRUEBA = "Regla de magnitud por cercanía"
SEMILLA = "magnitud-cercania"
POR_MEDIO = 25  # notas con magnitud (regla anterior) y, aparte, notas sobre El Niño sin magnitud
MODELO = "es_core_news_sm"
CLIMA_MAXIMO = 0.02  # C3a
OTRO_NUCLEO_MAXIMO = 0.05  # C3a′
RECHAZADOS_MAXIMO = 0.10  # C3b
# Lemas del instrumento, escritos aparte de las expresiones de la regla
NUCLEOS_ENSO = {
    "niño", "evento", "episodio", "fenómeno", "fen", "magnitud", "intensidad", "categoría", "nivel", "fase",
    "condición", "magnitudes", "eventos", "episodios", "fenómenos", "condiciones",
}  # fmt: skip
GRADOS = {"magnitud", "intensidad", "categoría", "nivel", "fase", "condición"}
NUCLEOS_CLIMA = {"lluvia", "precipitación", "caudal", "crecida", "viento", "oleaje", "temperatura", "calor", "llovizna"}
# Comparativos, que la definición excluye ("el más fuerte", "tan fuerte como"); corregido el 28-oct-2026 tras la
# 2.ª muestra: antes solo tomaba "más"
COMPARA = re.compile(r"\b(?:m[áa]s|menos|tan)\s+(?:fuerte|d[ée]bil|intens|moderad|extraordinari)", re.I)
# Regla anterior (hasta el 28-oct-2026), reproducida para comparar: término en una frase que nombra a El Niño y habla
# de magnitud, intensidad o categoría
CONTEXTO_ANTERIOR = re.compile(r"magnitud|intensidad|categor[íi]a", re.I)


def regla_anterior(frase):
    if rasgos.NINO.search(frase) and CONTEXTO_ANTERIOR.search(frase):
        return {enfen.magnitud_canonica(m.group(1)) for m in enfen.TERMINO.finditer(frase)}
    return set()


def regla_nueva(frase):
    return {valor for valor, _ in enfen.magnitudes_de_frase(frase)}


def frases_de_diseno():
    """Frases de titulares y resúmenes (con ellas se diseñó la regla): se excluyen de la validación."""
    return {
        clave(f)
        for nombre in MEDIOS
        for n in leer_csv(config.DIR_RAW_NOTICIAS / nombre / "notas.csv")
        for texto in (n["titular"], n["resumen"])
        for f in enfen.FRASE.split(texto)
    }


def frases_evaluables(cuerpo, vistas):
    """Frases del cuerpo que la regla mira (nombran a El Niño en la línea y no son del Pacífico central), con algún
    término de magnitud y que no repiten una frase del diseño."""
    for linea in cuerpo.split("\n"):
        region, nombra = None, False
        for frase in enfen.FRASE.split(linea):
            if enfen.MENCIONA_CENTRAL.search(frase):
                region = REGION_CENTRAL
            elif enfen.MENCIONA_COSTERA.search(frase):
                region = REGION_COSTERA
            nombra = nombra or rasgos.menciones(frase) > 0
            if nombra and region != REGION_CENTRAL and enfen.TERMINO.search(frase) and clave(frase) not in vistas:
                yield frase


def _lema(token):
    return "niño" if token.text.lower() == "niño" else token.lemma_.lower()


def nucleos(nlp, frase):
    """[(magnitud, núcleo, es_sustantivo)] por término: el núcleo es el lema del que depende directamente (saltando
    las enumeraciones); 'clima' si es un grado de lluvias; '' si es atributo de una copulativa o la raíz."""
    doc = nlp(frase)
    salida = []
    for tok in doc:
        if not enfen.TERMINO.fullmatch(tok.text):
            continue
        muy = tok.i > 0 and doc[tok.i - 1].text.lower() == "muy"
        valor = enfen.magnitud_canonica(("muy " if muy else "") + tok.text)
        t = tok
        while t.dep_ == "conj" and t.head is not t:
            t = t.head
        if t.head is t or any(c.dep_.startswith("nsubj") for c in t.children):
            salida.append((valor, "", False))
            continue
        h = t.head
        if _lema(h) in NUCLEOS_CLIMA or (_lema(h) in GRADOS and h.head is not h and _lema(h.head) in NUCLEOS_CLIMA):
            salida.append((valor, "clima", True))
        else:
            salida.append((valor, _lema(h), h.pos_ in ("NOUN", "PROPN")))
    return salida


def medir(casos, regla):
    """Cuentas de C3a, C3a′ y C3b para una regla. casos: [(nota, frase, núcleos)]."""
    c, ejemplos = collections.Counter(), collections.defaultdict(list)
    for nota, frase, lista in casos:
        aceptados = regla(frase)
        for valor, nucleo, sustantivo in lista:
            if valor in aceptados and nucleo:
                c["aceptados"] += 1
                if nucleo == "clima":
                    c["clima"] += 1
                    ejemplos["clima"].append((nota, valor, nucleo, frase))
                elif sustantivo and nucleo not in NUCLEOS_ENSO:
                    c["otro"] += 1
                    ejemplos["otro"].append((nota, valor, nucleo, frase))
            if nucleo in NUCLEOS_ENSO and not COMPARA.search(frase):
                c["directos"] += 1
                if valor not in aceptados:
                    c["rechazados"] += 1
                    ejemplos["rechazados"].append((nota, valor, nucleo, frase))
    return c, ejemplos


def _parte(a, b):
    return round(a / b, 3) if b else 0.0


def validar(casos):
    nueva, ejemplos = medir(casos, regla_nueva)
    anterior, _ = medir(casos, regla_anterior)
    detalle = {k: "; ".join(f"{n['medio']} {n['id']}: {v}→{h}" for n, v, h, _ in e[:20]) for k, e in ejemplos.items()}
    clima, otro = _parte(nueva["clima"], nueva["aceptados"]), _parte(nueva["otro"], nueva["aceptados"])
    rechazados = _parte(nueva["rechazados"], nueva["directos"])
    clima_ant, rechazados_ant = (
        _parte(anterior["clima"], anterior["aceptados"]),
        _parte(anterior["rechazados"], anterior["directos"]),
    )
    distingue = rechazados_ant > rechazados and clima_ant >= clima
    filas = [
        criterio(
            PRUEBA,
            "C3a: términos aceptados que dependen de un sustantivo de clima",
            clima,
            f"≤ {CLIMA_MAXIMO}",
            clima <= CLIMA_MAXIMO,
            f"{nueva['clima']}/{nueva['aceptados']}; {detalle.get('clima', '')}",
        ),
        criterio(
            PRUEBA,
            "C3a′: términos aceptados que dependen de otro sustantivo (no El Niño ni su grado)",
            otro,
            f"≤ {OTRO_NUCLEO_MAXIMO}",
            otro <= OTRO_NUCLEO_MAXIMO,
            f"{nueva['otro']}/{nueva['aceptados']}; {detalle.get('otro', '')}",
        ),
        criterio(
            PRUEBA,
            "C3b: términos que dependen de El Niño o de su grado y la regla rechaza",
            rechazados,
            f"≤ {RECHAZADOS_MAXIMO}",
            rechazados <= RECHAZADOS_MAXIMO,
            f"{nueva['rechazados']}/{nueva['directos']}; {detalle.get('rechazados', '')}",
        ),
        criterio(
            PRUEBA,
            "C4: con la regla anterior, C3a y C3b salen peores (el instrumento distingue)",
            distingue,
            "sí",
            distingue,
            f"anterior: C3a {anterior['clima']}/{anterior['aceptados']} = {clima_ant}, "
            f"C3b {anterior['rechazados']}/{anterior['directos']} = {rechazados_ant}",
        ),
    ]
    return filas, ejemplos


def muestra(semilla):
    vistas = notas_vistas()
    elegidas = []
    for nombre in MEDIOS:
        notas = [
            n
            for n in leer_csv(config.DIR_RAW_NOTICIAS / nombre / "notas.csv")
            if not _si(n["sin_texto"]) and (nombre, n["id"]) not in vistas and not reservada_capa3(n)
        ]
        con = [n for n in notas if n["magnitudes"]]
        sin = [n for n in notas if not n["magnitudes"] and _si(n["sobre_nino"])]
        elegidas += _muestra(con, POR_MEDIO, semilla, nombre, "con") + _muestra(sin, POR_MEDIO, semilla, nombre, "sin")
    return elegidas


def leer(elegidas):
    """(nota, cuerpo) de cada nota, leída una vez y en memoria."""
    for nombre in MEDIOS:
        filas = [n for n in elegidas if n["medio"] == nombre]
        medio = MEDIOS[nombre](Cliente(hosts_permitidos={config.HOSTS_MEDIOS[nombre]}))
        for fila, campos in medio.descargar(filas):
            if isinstance(campos, dict):
                yield next(n for n in filas if n["id"] == fila["id"]), campos["cuerpo"]
            else:
                log.info("%s %s: %s", nombre, fila["id"], campos)


@exclusivo("radar.noticias.validar_magnitud")
def main(argv=None):
    ap = argparse.ArgumentParser(description="Validación de la regla de magnitud por cercanía.")
    ap.add_argument("--semilla", default=SEMILLA)
    args = ap.parse_args(argv)
    import spacy  # solo este instrumento lo necesita

    nlp = spacy.load(MODELO)
    registro = configurar("noticias-validar-magnitud")
    inicio = ahora()
    elegidas = muestra(args.semilla)
    diseno = frases_de_diseno()
    casos, leidas = [], 0
    for nota, cuerpo in leer(elegidas):
        leidas += 1
        casos += [(nota, f, nucleos(nlp, f)) for f in frases_evaluables(cuerpo, diseno)]
    marcar_vistas(elegidas, f"magnitud-{args.semilla}")
    filas, ejemplos = validar(casos)
    guardar(filas)
    reporte(filas, [], inicio)
    print("\nCasos para diagnosticar (solo en pantalla; las frases no se guardan):")
    for tipo, lista in ejemplos.items():
        for nota, valor, nucleo, frase in lista:
            print(f"  [{tipo}] {nota['medio']} {nota['id']} {valor}→{nucleo}: {frase[:220]}")
    log.info(
        f"Muestra: {len(elegidas)} notas, {leidas} leídas, {len(casos)} frases (semilla {args.semilla}) · "
        f"registro: {registro.relative_to(config.RAIZ)}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
