"""Validación de la capa 1 (texto limpio del cuerpo) con una muestra nueva, comparando con la extracción anterior.
Criterios fijados antes de correrla (docs/noticias/texto.md). El HTML y los cuerpos solo viven en memoria.

Uso: python -m radar.noticias.validar_texto [--semilla S]
"""

import argparse
import collections
import json
import logging
import re
import sys
from typing import NamedTuple

from lxml import html

from radar import config
from radar.comun.archivos import leer_csv
from radar.comun.http import Cliente
from radar.comun.registro import configurar
from radar.comun.texto import ahora, norm
from radar.noticias import rasgos
from radar.noticias.medios import MEDIOS
from radar.noticias.nota import (
    BAJADA,
    CUERPO,
    _sin_bloques_ajenos,
    decodificar,
    leer_api,
    leer_html,
    proporcion_en_cuerpo,
)
from radar.noticias.viabilidad import _muestra, _si, criterio, guardar, reporte

log = logging.getLogger(__name__)

PRUEBA = "Texto limpio del cuerpo"
POR_MEDIO = 25
SEMILLA = "texto-limpio"  # otra que la del piloto y la revisión de estructura; --semilla para confirmar
COBERTURA_LD_MINIMA = 0.90  # RPP: parte del articleBody que debe estar en el cuerpo (como la prueba de calidad)
NOTAS_CON_COBERTURA = 0.95
CONSERVA_MINIMO = 0.90  # palabras del contenedor sin bloques ajenos que siguen tras las reglas de línea
PEGADAS_POR_MIL = 0.5
# Detector independiente de las reglas de limpieza: frases de interfaz al inicio de una línea y botones, no palabras
# que la redacción usa ("compartir con los ciudadanos", "canales en YouTube", "en el poema puede leerse").
# Corregido el 28-oct-2026 antes de la 3.ª y de la 6.ª muestra.
RESTOS = re.compile(
    r"^[\s\[(«\"“¡]*(Te recomendamos|Le[ae] también|Lee más|Puede?s? leer|Más en Andina|Mira .{0,30}YouTube)"
    r"|►|googletag|pic\.twitter|\d{1,2}:\d{2}\s*·|^\d{1,2}:\d{2} \|",
    re.I | re.M,
)
BOTONES = re.compile(r"\b(Compartir|Share)\b")  # con mayúscula, como botón
# Fin de frase pegado a la siguiente: después del punto viene una mayúscula (con o sin comilla de apertura), no una
# comilla de cierre. Corregido el 28-oct-2026 antes de la 3.ª muestra.
PEGADA = re.compile(r"[a-záéíóúñ0-9)\"”»][.!?](?=[¿¡“\"]?[A-ZÁÉÍÓÚ])")
CONTEXTO_PEGADA = 6  # caracteres a cada lado con que se busca la unión en el texto original del medio
# Extracción anterior (hasta el 28-oct-2026), reproducida para comparar
CUERPO_ANTERIOR = {
    "andina": "//div[contains(concat(' ', @class, ' '), ' paddingnota ')]",
    "rpp": "//div[contains(concat(' ', @class, ' '), ' body ')]",
    "exitosa": "//article[contains(concat(' ', @class, ' '), ' content ')]",
}
FUERA_ANTERIOR = "//script|//style|//noscript|//blockquote|//figcaption|//iframe"


class Lectura(NamedTuple):
    medio: str
    nota: dict  # fila de notas.csv (valores anteriores)
    campos: dict  # lectura nueva
    antes: str  # cuerpo como se extraía antes
    referencia: str  # contenedor nuevo sin bloques ajenos, sin reglas de línea
    original: str  # textos del contenedor tal como los escribió el medio, uno por nodo


def _raiz(contenido, tipo, entrada):
    if entrada is not None:
        return html.fromstring(f"<div>{entrada['content']['rendered']}</div>")
    return html.fromstring(decodificar(contenido, tipo))


def _textos_de_referencia(medio, contenido, tipo, entrada=None):
    """(antes, referencia, original) de la misma página. La referencia aísla las reglas de línea: lo que falte ahí lo
    quitaron ellas, no los selectores de bloques."""
    raiz = _raiz(contenido, tipo, entrada)
    viejo = [raiz] if entrada is not None else raiz.xpath(CUERPO_ANTERIOR[medio])
    antes, original = "", ""
    if viejo:
        original = "\n".join(viejo[0].itertext())
        for basura in viejo[0].xpath(FUERA_ANTERIOR.replace("//", ".//")):
            basura.drop_tree()
        antes = norm(viejo[0].text_content())
    raiz = _raiz(contenido, tipo, entrada)
    nuevo = [raiz] if entrada is not None else next((n for x in CUERPO[medio] if (n := raiz.xpath(x))), [])
    if not nuevo:
        return antes, "", original
    _sin_bloques_ajenos(nuevo[0], medio)
    bajada = " ".join(t.text_content() for t in raiz.xpath(BAJADA[medio])) if medio in BAJADA else ""
    return antes, norm(f"{bajada} {nuevo[0].text_content()}"), original


def _por_mil(cuenta, palabras):
    return round(1000 * cuenta / palabras, 2) if palabras else 0.0


def leer_muestra(semilla=SEMILLA):
    """Una Lectura por nota; cada página se pide una sola vez."""
    notas = [
        n
        for n in leer_csv(config.DIR_NOTICIAS / "notas.csv")
        if n["muestra"] == "candidata" and not _si(n["sin_texto"])
    ]
    for nombre in MEDIOS:
        medio = MEDIOS[nombre](Cliente(hosts_permitidos={config.HOSTS_MEDIOS[nombre]}))
        elegidas = _muestra([n for n in notas if n["medio"] == nombre], POR_MEDIO, semilla, nombre)
        if nombre == "eltiempo":
            r = medio.cliente.get(
                medio.api,
                params={
                    "include": ",".join(n["id"] for n in elegidas),
                    "per_page": POR_MEDIO,
                    "_fields": medio.CAMPOS_NOTA,
                },
            )
            for entrada in json.loads(r.content):
                nota = next(n for n in elegidas if n["id"] == str(entrada["id"]))
                yield Lectura(nombre, nota, leer_api(entrada), *_textos_de_referencia(nombre, None, "", entrada))
            continue
        for nota in elegidas:
            try:
                r = medio.cliente.get(nota["url"])
                tipo = r.headers.get("Content-Type", "")
                campos = leer_html(nombre, r.content, r.url, tipo)
            except Exception as e:  # una nota que falla no detiene la muestra
                log.info("%s %s: %s", nombre, nota["id"], e)
                continue
            yield Lectura(nombre, nota, campos, *_textos_de_referencia(nombre, r.content, tipo))


def uniones_de_la_extraccion(lectura):
    """Uniones pegadas del cuerpo nuevo que no están así en el texto original (las del medio no cuentan)."""
    cuerpo, propias, del_medio = lectura.campos["cuerpo"], 0, 0
    for m in PEGADA.finditer(cuerpo):
        trozo = cuerpo[max(0, m.start() - CONTEXTO_PEGADA) : m.end() + CONTEXTO_PEGADA]
        if "\n" not in trozo and trozo in lectura.original:
            del_medio += 1
        else:
            propias += 1
    return propias, del_medio


def restos(lectura):
    cuerpo = lectura.campos["cuerpo"]
    return [m.group(1) or m.group(0) for m in RESTOS.finditer(cuerpo)] + [m.group(0) for m in BOTONES.finditer(cuerpo)]


def _criterios_del_medio(nombre, grupo):
    palabras = sum(len(x.campos["cuerpo"].split()) for x in grupo)
    referencia = sum(len(x.referencia.split()) for x in grupo)
    conserva = round(palabras / referencia, 3) if referencia else 0.0
    uniones = [uniones_de_la_extraccion(x) for x in grupo]
    propias, del_medio = sum(u[0] for u in uniones), sum(u[1] for u in uniones)
    antes = _por_mil(sum(len(PEGADA.findall(x.antes)) for x in grupo), sum(len(x.antes.split()) for x in grupo))
    salida = [
        criterio(
            PRUEBA,
            f"{nombre}: las reglas de línea conservan el texto",
            conserva,
            f"≥ {CONSERVA_MINIMO}",
            conserva >= CONSERVA_MINIMO,
            f"{palabras} de {referencia} palabras en {len(grupo)} notas",
        ),
        criterio(
            PRUEBA,
            f"{nombre}: uniones pegadas por la extracción, por 1.000 palabras",
            _por_mil(propias, palabras),
            f"≤ {PEGADAS_POR_MIL}",
            _por_mil(propias, palabras) <= PEGADAS_POR_MIL,
            f"antes {antes}; ya pegadas en el original del medio: {del_medio}",
        ),
    ]
    if nombre == "rpp":
        ld = [x.campos["cuerpo_vs_ld"] for x in grupo if x.campos["cuerpo_vs_ld"] is not None]
        bien = sum(v >= COBERTURA_LD_MINIMA for v in ld)
        parte = round(bien / len(ld), 3) if ld else 0.0
        salida.append(
            criterio(
                PRUEBA,
                f"rpp: notas con ≥ {COBERTURA_LD_MINIMA} del articleBody",
                parte,
                f"≥ {NOTAS_CON_COBERTURA}",
                parte >= NOTAS_CON_COBERTURA,
                f"{bien}/{len(ld)}",
            )
        )
    return salida


def _efectos(nombre, grupo):
    """Informativo: qué cambia respecto de la extracción anterior."""
    resumen = [
        (proporcion_en_cuerpo(x.campos["resumen"], x.antes) or 0, x.campos["resumen_en_cuerpo"])
        for x in grupo
        if x.campos["resumen_en_cuerpo"] is not None
    ]
    cambia_nino = sum(
        rasgos.nino_en_inicio(x.campos["resumen"], x.antes)
        != rasgos.nino_en_inicio(x.campos["resumen"], x.campos["cuerpo"])
        for x in grupo
    )
    quitadas = sum(len(x.antes.split()) for x in grupo) - sum(len(x.referencia.split()) for x in grupo)
    sin_texto = (sum(_si(x.nota["sin_texto"]) for x in grupo), sum(x.campos["sin_texto"] for x in grupo))
    enlaces = (sum(int(x.nota["n_enlaces"] or 0) for x in grupo), sum(len(x.campos["enlaces"]) for x in grupo))
    detalle = (
        f"sin texto antes/ahora {sin_texto[0]}/{sin_texto[1]}; "
        f"resumen en cuerpo (media) antes {sum(a for a, _ in resumen) / max(1, len(resumen)):.3f} "
        f"ahora {sum(b for _, b in resumen) / max(1, len(resumen)):.3f}; "
        f"'El Niño en el inicio' cambia en {cambia_nino}; enlaces antes/ahora {enlaces[0]}/{enlaces[1]}; "
        f"palabras de bloques quitados (citas recuperadas restan) {quitadas}"
    )
    return criterio(PRUEBA + " (informativo)", f"{nombre}: efectos", len(grupo), "", True, detalle)


def validar(lecturas):
    por_medio = collections.defaultdict(list)
    for x in lecturas:
        por_medio[x.medio].append(x)
    salida, encontrados = [], []
    for nombre, grupo in por_medio.items():
        salida += _criterios_del_medio(nombre, grupo)
        salida.append(_efectos(nombre, grupo))
        encontrados += [f"{nombre} {x.nota['id']}: «{t}»" for x in grupo for t in restos(x)]
    salida.append(
        criterio(
            PRUEBA,
            "restos de bloques ajenos (detector independiente)",
            len(encontrados),
            "= 0",
            not encontrados,
            "; ".join(encontrados[:20]),
        )
    )
    return salida


def main(argv=None):
    ap = argparse.ArgumentParser(description="Validación del texto limpio del cuerpo (capa 1).")
    ap.add_argument("--semilla", default=SEMILLA)
    args = ap.parse_args(argv)
    registro = configurar("noticias-validar-texto")
    inicio = ahora()
    lecturas = list(leer_muestra(args.semilla))
    resultado = validar(lecturas)
    guardar(resultado)
    reporte(resultado, [], inicio)
    log.info(f"Muestra: {len(lecturas)} notas (semilla {args.semilla}) · registro: {registro.relative_to(config.RAIZ)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
