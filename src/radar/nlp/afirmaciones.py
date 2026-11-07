"""Capa 3 del índice: frases y afirmaciones (docs/nlp/discrepancia.md, definición del 28-oct y ajustes del 7-nov).

Parte el texto en frases y, de cada frase que nombra a El Niño, saca qué dato afirma (magnitud, estado, plazo,
probabilidad, región del océano) y marca quién lo dice, de cuándo, con qué seguridad y si es explicativa. No compara
con lo oficial: eso es la capa 5.

Uso: python -m radar.nlp.afirmaciones muestra   # elige las notas nuevas de la validación y las agrega a notas_vistas
     python -m radar.nlp.afirmaciones validar   # pide páginas: lee la muestra en memoria y calcula los criterios
"""

import argparse
import collections
import datetime as dt
import logging
import math
import re
import sys
import threading

from radar import config
from radar.comun.archivos import escribir_csv, leer_csv
from radar.comun.candado import exclusivo
from radar.comun.energia import sin_suspension
from radar.comun.registro import configurar, describir
from radar.comun.texto import MESES, ahora, sha1_corto
from radar.nlp import esquemas, tfidf, viabilidad
from radar.noticias import rasgos
from radar.noticias.medios import MEDIOS
from radar.noticias.validar_texto import marcar_vistas, notas_vistas, reservada_capa3
from radar.noticias.viabilidad import _muestra, criterio, guardar, reporte
from radar.oficial import enfen
from radar.oficial.vigencia import Corpus

log = logging.getLogger(__name__)

PRUEBA = "Capa 3: afirmaciones"
PALABRAS_SUBTITULO = 5  # líneas más cortas son subtítulos: no son afirmación
PALABRAS_FRASE_LARGA = 60
FRASES_LARGAS_MAXIMO = 0.02
ESTADO_OFICIAL_MINIMO = 0.95
ACIERTO_MINIMO = 0.90
SEMILLA = "capa3-validacion-7nov"
RONDAS = {"a": SEMILLA, "b": "capa3-validacion-7nov-b"}  # b: tras los 4 arreglos del 7-nov
POR_MEDIO = 30
Z_WILSON = 1.96

# ---------------------------------------------------------------- frases

FRASE = re.compile(r"(?<=[.!?;])\s+(?=[\"“«¿¡A-ZÁÉÍÓÚÑ0-9•])|(?<=[.!?][\"”»])\s+")


def frases(titular, resumen, cuerpo):
    """[(origen, número de línea, frase, es_subtitulo)] en orden; el número de línea agrupa las frases de un párrafo."""
    salida, linea_n = [], 0
    for origen, texto in (("titular", titular), ("resumen", resumen), ("cuerpo", cuerpo)):
        for linea in (texto or "").split("\n"):
            linea = linea.strip()
            if not linea:
                continue
            linea_n += 1
            corta = len(linea.split()) < PALABRAS_SUBTITULO
            salida += [(origen, linea_n, f, corta) for f in FRASE.split(linea) if f.strip()]
    return salida


# ---------------------------------------------------------------- estado

ESTADOS = {"no activo": "no_activo", "vigilancia": "vigilancia", "alerta": "alerta"}
# "(estado del) sistema de alerta (ante El Niño Costero/La Niña Costera)" es el nombre del sistema, no un valor
SISTEMA = re.compile(
    r"(?:(?:el\s+)?estado\s+del?\s+)?sistema\s+de\s+alerta(?:\s+ante\s+(?:el\s+)?(?:fen[óo]meno\s+)?(?:El\s+)?Niño"
    r"(?:\s+Costero)?(?:\s*/\s*(?:la\s+)?Niña(?:\s+Costera)?)?)?",
    re.I,
)
_VALOR = r"[«“\"']?\s*(no\s+activo|vigilancia|alerta)\b"
NO_ES_ESTADO = re.compile(r"^\s*[»”\"']?\s*(?:roja|naranja|amarilla|verde|temprana|meteorol|m[áa]xima|sanitaria)", re.I)
DE_A = re.compile(rf"\bde\s+{_VALOR}[^.;]{{0,40}}?\s+a(?:l)?\s+(?:la\s+)?(?:fase\s+de\s+)?{_VALOR}", re.I)
VALOR_DE_NINO = re.compile(rf"{_VALOR}\s*[»”\"']?\s+(?:de|del|ante|por)\s+(?:un\s+|el\s+)?(?:fen[óo]meno\s+)?"
                           r"(?:de\s+)?(?:El\s+)?Niño", re.I)  # fmt: skip
NINO_EN = re.compile(rf"Niño(?:\s+[Cc]ostero)?\s+(?:en|a)\s+(?:estado\s+de\s+)?{_VALOR}", re.I)
VALOR_DEL_SISTEMA = re.compile(rf"\bSISTEMA\b[^.;]{{0,50}}?\b(?:de|en|a|como)\s+(?:la\s+)?(?:fase\s+de\s+)?{_VALOR}"
                               rf"|\bestado\s+de\s+{_VALOR}", re.I)  # fmt: skip


def _valores(regex, texto):
    for m in regex.finditer(texto):
        for g in range(1, (m.lastindex or 0) + 1):
            if m.group(g) and not NO_ES_ESTADO.search(texto[m.end(g) :]):
                yield m.start(g), ESTADOS[re.sub(r"\s+", " ", m.group(g).lower())]


def estado(frase):
    """El estado del sistema que la frase afirma; en "de X a Y" vale Y. '' si no hay o si se contradice."""
    texto = SISTEMA.sub("SISTEMA", frase)
    cambio = [m for m in DE_A.finditer(texto) if not NO_ES_ESTADO.search(texto[m.end(2) :])]
    if cambio:
        return ESTADOS[re.sub(r"\s+", " ", cambio[-1].group(2).lower())]
    hallados = {v for regex in (VALOR_DE_NINO, NINO_EN, VALOR_DEL_SISTEMA) for _, v in _valores(regex, texto)}
    return hallados.pop() if len(hallados) == 1 else ""


# ---------------------------------------------------------------- plazo

# Estaciones del hemisferio sur: (inicios, mediados, fines); sin modificador vale el último mes (ajuste del 7-nov)
ESTACIONES = {"verano": (1, 2, 3), "otoño": (4, 5, 6), "invierno": (7, 8, 9), "primavera": (10, 11, 12)}
MODIFICADOR = {"inicio": 0, "comienzo": 0, "principio": 0, "mediado": 1, "fin": 2, "final": 2}
_MES = "|".join(MESES)
_EST = "|".join(ESTACIONES)
PLAZO = re.compile(
    r"\bhasta\s+(?:el\s+|la\s+|los\s+)?(?:(?P<mod>inicios?|comienzos?|principios?|mediados|fin(?:es|ales?)?)\s+"
    r"(?:de\s+|del\s+)?(?:el\s+|la\s+)?)?(?:(?P<rel>pr[óo]ximo|presente|este)\s+)?"
    rf"(?:(?P<mes>{_MES})|(?P<est>{_EST})|(?P<anio_solo>año|20\d\d))"
    r"(?:\s+(?:de\s+|del\s+)?(?P<anio>20\d\d|presente\s+año|este\s+año|próximo\s+año))?",
    re.I,
)


def _mes_y_anio(mes, anio, fecha):
    """Con año explícito se usa; sin año, la primera vez que llega ese mes desde la fecha."""
    if anio:
        return anio, mes
    return (fecha.year if mes >= fecha.month else fecha.year + 1), mes


def plazo_de(m, fecha):
    """'AAAA-MM' de una coincidencia de PLAZO, con la fecha del texto para lo que no trae año."""
    fecha = dt.date.fromisoformat(fecha[:10])
    texto_anio = (m.group("anio") or "").lower()
    anio = int(texto_anio) if texto_anio.isdigit() else None
    if "presente" in texto_anio or "este" in texto_anio:
        anio = fecha.year
    elif "próximo" in texto_anio:
        anio = fecha.year + 1
    mod = MODIFICADOR.get(re.sub(r"(es|s|al|ales)$", "", (m.group("mod") or "").lower()) or "", None)
    if m.group("mes"):
        a, mes = _mes_y_anio(MESES[m.group("mes").lower()], anio, fecha)
    elif m.group("est"):
        meses = ESTACIONES[m.group("est").lower()]
        a, mes = _mes_y_anio(meses[2 if mod is None else mod], anio, fecha)
        if anio is None and mes < fecha.month:  # "hasta el verano" dicho en agosto: el verano siguiente
            a = fecha.year + 1
    else:
        solo = m.group("anio_solo").lower()
        proximo = (m.group("rel") or "").lower().startswith("pr")
        a = int(solo) if solo.isdigit() else (anio or fecha.year + proximo)
        if mod is None:  # "hasta 2027": solo el año (arreglo del 7-nov)
            return f"{a:04d}"
        mes = (1, 6, 12)[mod]
    return f"{a:04d}-{mes:02d}"


# El plazo cuenta solo si va pegado a El Niño (arreglo del 7-nov): "lluvias que podrían extenderse hasta marzo" no
ANCLA_PLAZO = re.compile(r"Niño|evento|fen[óo]meno|condici[óo]n|magnitud|alerta|vigilancia|calentamiento|nivel"
                         r"|intensidad|anomal", re.I)  # fmt: skip
CLIMA_PLAZO = re.compile(r"lluvi|precipitaci|caudal|crecid|viento|olea|temperatura|calor|fr[íi]o|sequ[íi]a|huaico"
                         r"|emergencia|declaratoria|bono|vigencia|plazo|medida", re.I)  # fmt: skip
PALABRAS_ANTES_DEL_PLAZO = 10


def anclado(antes):
    """En las palabras previas a "hasta", lo último que se nombra es El Niño (o su grado) y no un fenómeno del clima."""
    ventana = " ".join(antes.split()[-PALABRAS_ANTES_DEL_PLAZO:])
    clima = [m.start() for m in CLIMA_PLAZO.finditer(ventana)]
    ancla = [m.start() for m in ANCLA_PLAZO.finditer(ventana)]
    return not clima or (bool(ancla) and ancla[-1] > clima[-1])


def plazos(frase, fecha):
    return [plazo_de(m, fecha) for m in PLAZO.finditer(frase) if anclado(frase[: m.start()])]


def mismo_plazo(a, b):
    """Iguales, o uno es solo un año y el otro cae en ese año."""
    return a == b or (len(a) == 4 or len(b) == 4) and a[:4] == b[:4]


# ---------------------------------------------------------------- probabilidad y región

PORCENTAJE = re.compile(r"(\d{1,3}(?:[.,]\d+)?)\s*(?:%|por\s*ciento)", re.I)
# El % es una probabilidad si su cláusula habla de probabilidad, de una condición o de una magnitud
CONDICION = re.compile(r"Niña|condici[óo]n|c[áa]lid|neutr|fr[íi]a|magnitud|d[ée]bil|moderad|fuerte|extraordinari"
                       r"|probab", re.I)  # fmt: skip


def probabilidades(frase):
    """Porcentajes en una cláusula que nombra a El Niño y a una condición o magnitud: un % económico no cuenta."""
    salida = []
    for clausula in re.split(r"[;]|\.\s", frase):
        if CONDICION.search(PORCENTAJE.sub("", clausula)) and re.search(r"Niñ[oa]|condici", clausula, re.I):
            salida += [int(float(p.replace(",", "."))) for p in PORCENTAJE.findall(clausula)]
    return salida


def region(frase):
    central, costa = enfen.MENCIONA_CENTRAL.search(frase), enfen.MENCIONA_COSTERA.search(frase)
    return "ambas" if central and costa else "central" if central else "costa" if costa else "ambigua"


# ---------------------------------------------------------------- marcas

ATRIBUCION_ENFEN = re.compile(r"\bENFEN\b|\bEnfen\b|Comisi[óo]n Multisectorial|Estudio Nacional del Fen[óo]meno")
ATRIBUCION_OFICIAL = re.compile(r"\bSenamhi\b|\bSENAMHI\b|\bImarpe\b|\bIMARPE\b|\bIGP\b|Instituto Geof[íi]sico|\bDHN\b"
                                r"|Direcci[óo]n de Hidrograf[íi]a|\bIndeci\b|\bINDECI\b|\bCenepred\b|\bCENEPRED\b"
                                r"|\bANA\b|Autoridad Nacional del Agua", re.I)  # fmt: skip
ATRIBUCION_AGENCIA = re.compile(r"\bNOAA\b|\bOMM\b|Organizaci[óo]n Meteorol[óo]gica Mundial|\bBoM\b|Bureau of Meteor"
                                r"|Copernicus|\bIRI\b|\bCPC\b|Centro de Predicci[óo]n Clim[áa]tica|\bNASA\b|\bECMWF\b"
                                r"|\bINAMHI\b|\bWMO\b|\bCIIFEN\b", re.I)  # fmt: skip
ATRIBUCION_TERCERO = re.compile(r"\bseg[úu]n\b|\b(?:dijo|afirm[óa]|indic[óa]|explic[óa]|señal[óa]|advirti[óo]|sostuvo"
                                r"|precis[óo]|coment[óo]|declar[óo]|anunci[óo]|alert[óo]|manifest[óo]|aseguró|refirió)\b"
                                r"|\b(?:experto|especialista|científico|climatólogo|meteorólogo|investigador|ingenier)",
                                re.I)  # fmt: skip
OTRO_PAIS = re.compile(r"\bEcuador|\becuatorian|\bChile\b|\bchilen|\bColombia|\bcolombian|\bBolivia|\bArgentina"
                       r"|\bMéxico|\bEstados Unidos|\bAustralia|\bBrasil|\bCentroamérica", re.I)  # fmt: skip
CITA = re.compile(r"[\"“«]([^\"”»]{3,})[\"”»]")
PALABRAS_CITA = 4
ANIO = re.compile(r"\b(19[5-9]\d|20[0-2]\d)\b")
ANIO_ACTUAL = re.compile(r"\b202[5-7]\b")
HISTORICO = re.compile(r"\b(?:el|los)\s+(?:último|últimos|anteriores?|pasados?)\s+(?:fen[óo]menos?\s+)?(?:de\s+)?"
                       r"(?:El\s+)?Niños?\b|\bNiños?\s+(?:de|del)\s+(?:19|20[01]|202[0-4])|\bhist[óo]ric|"
                       r"\ben\s+(?:19[5-9]\d|20[01]\d|202[0-4])\b", re.I)  # fmt: skip
NO_SON_VERBOS = {"categoría", "categorías", "mayoría", "maría", "energía", "economía", "geografía", "batería",
                 "alcaldía", "policía", "hidrografía", "meteorología", "ingeniería", "ganadería", "minería",
                 "galería"}  # fmt: skip
CONDICIONAL_VERBO = re.compile(r"\b\w{2,}rían?\b", re.I)  # "continuaría", "serían": el condicional lleva tilde
CONDICIONAL = re.compile(r"\bpodr[íi]|\bpuede[n]?\b|\bpodr[áa]n?\b|\bposible|\bprobab|\bse\s+prev[ée]"
                         r"|\bse\s+espera|\bpron[óo]stic|\bestima|\bproyect|\bno se descarta|\bsi\s+(?:se|el|la|llega)",
                         re.I)  # fmt: skip
EXPLICATIVA = re.compile(r"\bse\s+(?:define|denomina|llama|caracteriza|produce|origina|forma)\b|\bes\s+un\s+fen[óo]meno"
                         r"|\bconsiste\s+en|\bse\s+trata\s+de|\bocurre\s+cuando|\bse\s+presenta\s+cuando|\bqu[ée]\s+es\b"
                         r"|\bescala\b|\bse\s+(?:clasifica|mide|considera)\b|\bsegún\s+su\s+(?:magnitud|intensidad)",
                         re.I)  # fmt: skip


def atribucion(frase):
    """(fuente, otro_pais) por la primera regla que coincide, de la más específica a la más amplia."""
    pais = bool(OTRO_PAIS.search(frase))
    if ATRIBUCION_ENFEN.search(frase):
        return "enfen", pais
    if ATRIBUCION_OFICIAL.search(frase):
        return "oficial", pais
    if ATRIBUCION_AGENCIA.search(frase):
        return "agencia", pais
    if pais or ATRIBUCION_TERCERO.search(frase):
        return "tercero", pais
    return "sin", pais


def es_cita(frase):
    return any(len(m.group(1).split()) >= PALABRAS_CITA for m in CITA.finditer(frase))


# "En su comunicado de julio, el ENFEN indicó…": cuenta un comunicado pasado (arreglo del 7-nov)
COMUNICADO_PASADO = re.compile(rf"\b(?:comunicados?|bolet[íi]n(?:es)?|informes?|reportes?)\b[^.;]{{0,40}}?\b(?:de|del)"
                               rf"\s+(?P<mes>{_MES})\b(?:\s+(?:de|del)\s+(?P<anio>20\d\d))?", re.I)  # fmt: skip
MESES_ATRAS_PASADO = 2  # el de hace un mes puede seguir vigente; desde dos meses atrás ya es pasado

# "Enfen descarta un Niño muy fuerte", "es prematuro afirmar…": la frase niega el dato (arreglo del 7-nov)
NEGACION = re.compile(r"\bdescart\w*|\bprematuro\b|\bno\s+(?:existen?|hay|habr[áa]|se\s+prev[ée]|se\s+espera"
                      r"|evolucionar[íi]?[áa]|alcanzar[íi]?[áa]|llegar[íi]?[áa]|ser[íi]?[áa]|tendr[íi]?[áa]"
                      r"|pasar[íi]?[áa])\b", re.I)  # fmt: skip


def negada(frase):
    """Niega un dato; "no se descarta" y "sin descartar" son lo posible, no una negación."""
    return bool(NEGACION.search(enfen.POSIBLE.sub(" ", frase)))


def _cuenta_pasado(frase, fecha):
    hoy = dt.date.fromisoformat(fecha[:10])
    for m in COMUNICADO_PASADO.finditer(frase):
        anio = int(m.group("anio")) if m.group("anio") else hoy.year
        if (hoy.year - anio) * 12 + hoy.month - MESES[m.group("mes").lower()] >= MESES_ATRAS_PASADO:
            return True
    return False


def momento(frase, fecha):
    """Histórico si cuenta un comunicado pasado, o si habla de un Niño pasado sin nombrar los años del actual
    ("como en 1998" compara)."""
    if _cuenta_pasado(frase, fecha):
        return "historico"
    if ANIO_ACTUAL.search(frase):
        return "actual"
    return "historico" if HISTORICO.search(frase) or ANIO.search(frase) else "actual"


def modalidad(frase):
    if "¿" in frase or frase.rstrip().endswith("?"):
        return "pregunta"
    verbos = [v for v in CONDICIONAL_VERBO.findall(frase) if v.lower() not in NO_SON_VERBOS]
    return "condicional" if verbos or CONDICIONAL.search(frase) else "afirma"


def explicativa(frase):
    return bool(EXPLICATIVA.search(frase))


# ---------------------------------------------------------------- afirmaciones


def datos(frase, fecha):
    mags = enfen.magnitudes_de_frase(frase)
    return {
        "magnitudes": [v for v, _ in mags],
        "magnitudes_posibles": [v for v, p in mags if p],
        "estado": estado(frase),
        "plazos": plazos(frase, fecha),
        "probabilidades": probabilidades(frase),
    }


def tiene_dato(d):
    return bool(d["magnitudes"] or d["estado"] or d["plazos"] or d["probabilidades"])


def afirmaciones(titular, resumen, cuerpo, fecha):
    """Filas de las frases que nombran a El Niño con algún dato; la atribución pasa a la frase siguiente del párrafo."""
    salida, anterior = [], (None, "sin")
    for n, (origen, linea, frase, corta) in enumerate(frases(titular, resumen, cuerpo)):
        fuente, pais = atribucion(frase)
        heredada = False
        if fuente == "sin" and anterior[0] == linea and anterior[1] != "sin":
            fuente, heredada = anterior[1], True
        anterior = (linea, fuente if not heredada else "sin")
        if corta or not rasgos.menciones(frase):
            continue
        d = datos(frase, fecha)
        if not tiene_dato(d):
            continue
        salida.append({
            "frase": n, "origen": origen, "sha1_frase": sha1_corto(frase), "palabras": len(frase.split()), **d,
            "region": region(frase), "atribucion": fuente, "heredada": heredada, "otro_pais": pais,
            "cita": es_cita(frase), "momento": momento(frase, fecha), "modalidad": modalidad(frase),
            "negada": negada(frase),
            "explicativa": explicativa(frase), "_texto": frase,
        })  # fmt: skip
    return salida


def a_fila(medio, id_, a):
    """Fila de afirmaciones.csv: sin el texto de la frase."""
    fila = {k: v for k, v in a.items() if not k.startswith("_")}
    for k in ("magnitudes", "magnitudes_posibles", "plazos", "probabilidades"):
        fila[k] = "|".join(map(str, fila[k]))
    return {"medio": medio, "id": id_, **fila}


# ---------------------------------------------------------------- referencia oficial (solo para validar)


def _plazo_comunicado(c):
    """El plazo de comunicados.csv convertido con la función compartida."""
    m = PLAZO.search(c["plazo"] or "")
    return plazo_de(m, c["vigente_desde"] or c["fecha_emision"]) if m else None


def referencia(corpus):
    """{id: {estado, magnitudes, plazos}} con lo que cada comunicado dice para la costa."""
    por_doc = collections.defaultdict(list)
    for p in corpus.parrafos:
        if p["fuente"] == "enfen" and p["seccion"] in ("titular", "resumen", "cuerpo"):
            por_doc[p["doc_id"]].append(p["texto"])
    salida = {}
    for c in corpus.comunicados:
        fecha = c["vigente_desde"] or c["fecha_emision"]
        costeras = list(enfen._frases_costeras(por_doc[c["id"]]))
        plazos_ = {x for f in costeras for x in plazos(f, fecha)} | ({p} if (p := _plazo_comunicado(c)) else set())
        salida[c["id"]] = {
            "estado": ESTADO_DE_ENCABEZADO.get(c["estado"], ""),
            "magnitudes": set(filter(None, c["magnitudes_mencionadas"].split("|"))),
            "plazos": plazos_,
        }
    return salida


ESTADO_DE_ENCABEZADO = {"No Activo": "no_activo", "Vigilancia de El Niño Costero": "vigilancia",
                        "Alerta de El Niño Costero": "alerta"}  # fmt: skip


def comparables(corpus, fecha):
    """El comunicado vigente en la fecha y el anterior (ajuste del 7-nov)."""
    vigente = corpus.comunicado_vigente(fecha)
    if vigente is None:
        return []
    i = corpus.comunicados.index(vigente)
    return [vigente["id"]] + ([corpus.comunicados[i - 1]["id"]] if i > 0 else [])


def evaluable(a):
    """Afirmación atribuida al ENFEN, de la costa o sin región, actual, no negada, no explicativa ni pregunta."""
    return (
        a["atribucion"] == "enfen"
        and a["region"] in ("costa", "ambigua")
        and a["momento"] == "actual"
        and not a.get("negada")
        and not a["explicativa"]
        and a["modalidad"] != "pregunta"
    )


def comparar(a, refs):
    """[(dato, valor, acierta)] de una afirmación frente a la unión de los comunicados comparables."""
    estados = {r["estado"] for r in refs}
    mags = set().union(*(r["magnitudes"] for r in refs)) if refs else set()
    plazos_ = set().union(*(r["plazos"] for r in refs)) if refs else set()
    salida = [("estado", a["estado"], a["estado"] in estados)] if a["estado"] else []
    salida += [("magnitud", m, m in mags) for m in dict.fromkeys(a["magnitudes"])]
    salida += [("plazo", p, any(mismo_plazo(p, x) for x in plazos_)) for p in dict.fromkeys(a["plazos"])]
    return salida


def wilson(aciertos, n, z=Z_WILSON):
    if not n:
        return (float("nan"), float("nan"))
    p = aciertos / n
    centro = (p + z * z / (2 * n)) / (1 + z * z / n)
    margen = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return (round(centro - margen, 3), round(centro + margen, 3))


# ---------------------------------------------------------------- criterios


CASOS_PLAZO = (  # (texto, fecha del texto, esperado): los plazos de comunicados.csv y los titulares, fijados el 7-nov
    ("hasta octubre de 2026", "2026-01-15", "2026-10"),
    ("hasta noviembre del presente año", "2026-02-13", "2026-11"),
    ("hasta diciembre del presente año", "2026-03-13", "2026-12"),
    ("hasta enero de 2027", "2026-04-16", "2027-01"),
    ("hasta febrero de 2027", "2026-05-15", "2027-02"),
    ("hasta el próximo verano de 2027", "2026-06-15", "2027-03"),
    ("hasta el verano de 2027", "2026-06-26", "2027-03"),
    ("hasta abril de 2027", "2026-07-17", "2027-04"),
    ("hasta el verano", "2026-08-14", "2027-03"),
    ("hasta mediados de otoño de 2027", "2026-09-14", "2027-05"),
    ("hasta enero 2027", "2026-09-28", "2027-01"),
    ("hasta el otoño de 2027", "2026-09-28", "2027-06"),
    ("hasta fines de otoño de 2027", "2026-10-30", "2027-06"),
    ("hasta inicios de otoño 2027", "2026-08-14", "2027-04"),
    ("hasta finales de año", "2026-05-01", "2026-12"),
)


def criterio_plazos():
    malos = []
    for texto, fecha, esperado in CASOS_PLAZO:
        obtenido = plazos(texto, fecha)
        if obtenido != [esperado]:
            malos.append(f"{texto} ({fecha}): {obtenido} en vez de {esperado}")
    n = len(CASOS_PLAZO)
    return criterio(PRUEBA, "conversión de plazos (casos conocidos)", n - len(malos), n, not malos, "; ".join(malos))


def criterio_estado_oficial(corpus):
    """Estado de las frases de cada comunicado frente a su encabezado (referencia independiente)."""
    aciertos, n, malos = 0, 0, []
    for c in corpus.comunicados:
        esperado = ESTADO_DE_ENCABEZADO.get(c["estado"], "")
        for p in corpus.parrafos:
            if p["doc_id"] != c["id"] or p["seccion"] not in ("resumen", "cuerpo", "titular"):
                continue
            for f in enfen.FRASE.split(p["texto"]):
                e = estado(f)
                if e:
                    n += 1
                    aciertos += e == esperado
                    if e != esperado:
                        malos.append(f"{c['id']}: {e} (encabezado {esperado}): {f[:120]}")
    for m in malos:
        print("  [estado oficial]", m)
    return criterio(PRUEBA, "estado en los textos oficiales", f"{aciertos}/{n}", f">= {ESTADO_OFICIAL_MINIMO:.0%}",
                    n > 0 and aciertos / n >= ESTADO_OFICIAL_MINIMO,
                    f"{aciertos / n:.3f} IC {wilson(aciertos, n)}" if n else "sin frases")  # fmt: skip


def criterios_notas(filas):
    """filas: [{medio, id, fecha, error, frases, largas, afirmaciones: [...]}] de la muestra."""
    validas = [f for f in filas if not f["error"]]
    total = sum(f["frases"] for f in validas)
    largas = sum(f["largas"] for f in validas)
    salida = [
        criterio(PRUEBA, "notas leídas", len(validas), len(filas), True,
                 str(collections.Counter(f["medio"] for f in validas))),
        criterio(PRUEBA, f"frases de más de {PALABRAS_FRASE_LARGA} palabras", f"{largas}/{total}",
                 f"<= {FRASES_LARGAS_MAXIMO:.0%}", total > 0 and largas / total <= FRASES_LARGAS_MAXIMO,
                 f"{largas / total:.4f}" if total else ""),
    ]  # fmt: skip
    todas = [a for f in validas for a in f["afirmaciones"]]
    fuentes = dict(collections.Counter(a["atribucion"] for a in todas))
    salida.append(criterio(PRUEBA, "afirmaciones (informativo)", len(todas), "", True,
                           f"por nota {len(todas) / max(1, len(validas)):.2f}; evaluables "
                           f"{sum(map(evaluable, todas))}; atribución {fuentes}"))  # fmt: skip
    por_dato = collections.defaultdict(lambda: [0, 0])
    for f in validas:
        for a in f["afirmaciones"]:
            for dato, _, ok in a.get("_comparacion", []):
                por_dato[dato][0] += ok
                por_dato[dato][1] += 1
    for dato in ("estado", "magnitud", "plazo"):
        ok, n = por_dato[dato]
        salida.append(criterio(PRUEBA, f"{dato} de lo atribuido al ENFEN frente al vigente o el anterior",
                               f"{ok}/{n}", f">= {ACIERTO_MINIMO:.0%}", n > 0 and ok / n >= ACIERTO_MINIMO,
                               f"{ok / n:.3f} IC {wilson(ok, n)}" if n else "sin casos"))  # fmt: skip
    return salida


# ---------------------------------------------------------------- muestra y lectura


def muestra(notas, vistas):
    """Las que citan un comunicado sin ver, más POR_MEDIO por medio de las que nombran al ENFEN (sin ver)."""
    pool = [n for n in notas if reservada_capa3(n) and (n["medio"], n["id"]) not in vistas]
    citan = sorted((n for n in pool if n["comunicados"]), key=lambda n: (n["medio"], n["id"]))
    resto = [n for n in pool if not n["comunicados"]]
    return citan + [m for nombre in MEDIOS for m in _muestra([n for n in resto if n["medio"] == nombre], POR_MEDIO,
                                                               SEMILLA, nombre)]  # fmt: skip


def muestra_b(notas, vistas):
    """Ronda b, tras los arreglos: todas las reservadas que siguen sin ver."""
    return sorted((n for n in notas if reservada_capa3(n) and (n["medio"], n["id"]) not in vistas),
                  key=lambda n: (n["medio"], n["id"]))  # fmt: skip


def elegir_muestra(ronda):
    semilla = RONDAS[ronda]
    if viabilidad.registrada(semilla):
        log.info(f"La muestra {semilla} ya está en notas_vistas.csv; no se elige otra.")
        return []
    elegir = muestra if ronda == "a" else muestra_b
    elegidas = elegir(leer_csv(config.DIR_NOTICIAS / "notas.csv"), notas_vistas())
    marcar_vistas(elegidas, semilla)
    log.info(f"Muestra: {len(elegidas)} · {collections.Counter(n['medio'] for n in elegidas)}")
    return []


def fila_validacion(nota, campos, corpus, refs):
    fila = {"medio": nota["medio"], "id": nota["id"], "fecha": nota["fecha_publicacion"][:10], "error": "",
            "frases": 0, "largas": 0, "afirmaciones": []}  # fmt: skip
    if not isinstance(campos, dict):
        return {**fila, "error": describir(campos)[:200]}
    if campos["sin_texto"]:
        return {**fila, "error": "sin texto"}
    lista = frases(campos["titular"], campos["resumen"], campos["cuerpo"])
    fila["frases"] = sum(not corta for *_, corta in lista)
    fila["largas"] = sum(not corta and len(f.split()) > PALABRAS_FRASE_LARGA for *_, f, corta in lista)
    afs = afirmaciones(campos["titular"], campos["resumen"], campos["cuerpo"], fila["fecha"])
    ids = comparables(corpus, fila["fecha"])
    for a in afs:
        if evaluable(a):
            a["_comparacion"] = comparar(a, [refs[i] for i in ids])
            for dato, valor, ok in a["_comparacion"]:
                if not ok:  # solo a pantalla, para el diagnóstico: el texto no se guarda
                    print(f"  [desacuerdo] {nota['medio']} {nota['id']} {fila['fecha']} {ids} {dato}={valor} "
                          f"| {a['_texto'][:220]}")  # fmt: skip
    fila["afirmaciones"] = afs
    return fila


@exclusivo("radar.nlp.afirmaciones")
def _validar(parar, ronda):
    elegidas = set(viabilidad.registrada(RONDAS[ronda]))
    if not elegidas:
        raise SystemExit(f"Falta la muestra: python -m radar.nlp.afirmaciones muestra --ronda {ronda}")
    notas = [n for n in leer_csv(config.DIR_NOTICIAS / "notas.csv") if (n["medio"], n["id"]) in elegidas]
    corpus = Corpus()
    refs = referencia(corpus)
    filas = []
    lectura = config.DIR_NLP / "afirmaciones-lectura.csv"
    lectura.unlink(missing_ok=True)  # una sola pasada: las afirmaciones se juntan en memoria
    with sin_suspension():
        tfidf.leer_cuerpos(
            [(n, "") for n in notas],
            lectura,
            esquemas.AFIRMACIONES_LECTURA,
            lambda nota, _e, campos: _guardar_y_resumir(nota, campos, corpus, refs, filas),
            parar,
        )
    escribir_csv(config.DIR_NLP / "afirmaciones.csv", esquemas.AFIRMACIONES,
                 [a_fila(f["medio"], f["id"], a) for f in filas for a in f["afirmaciones"]])  # fmt: skip
    return [criterio_plazos(), criterio_estado_oficial(corpus), *criterios_notas(filas)]


def _guardar_y_resumir(nota, campos, corpus, refs, filas):
    fila = fila_validacion(nota, campos, corpus, refs)
    filas.append(fila)
    resumen = {k: fila[k] for k in esquemas.AFIRMACIONES_LECTURA if k != "afirmaciones"}
    return resumen | {"afirmaciones": len(fila["afirmaciones"])}


def main(argv=None):
    ap = argparse.ArgumentParser(description="Capa 3: frases y afirmaciones.")
    ap.add_argument("paso", choices=("muestra", "validar"))
    ap.add_argument("--ronda", choices=tuple(RONDAS), default="b", help="a: primera validación; b: tras los arreglos")
    args = ap.parse_args(argv)
    registro = configurar(f"nlp-afirmaciones-{args.paso}-{args.ronda}")
    inicio, parar = ahora(), threading.Event()
    config.DIR_NLP.mkdir(parents=True, exist_ok=True)
    try:
        filas = elegir_muestra(args.ronda) if args.paso == "muestra" else _validar(parar, args.ronda)
    except KeyboardInterrupt:
        parar.set()
        return 1
    if isinstance(filas, int):
        return filas
    if filas:
        guardar(filas, config.DIR_NLP / "validacion.csv")
        reporte(filas, [], inicio)
    log.info(
        f"Duración: {(ahora() - inicio).total_seconds() / 60:.1f} min · registro: {registro.relative_to(config.RAIZ)}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
