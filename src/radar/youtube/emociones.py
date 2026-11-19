"""Emociones de los comentarios de YouTube (docs/youtube/emociones.md; criterios M0 a M3 fijados el 16-nov).

pysentimiento (robertuito) es el instrumento; las referencias son los emojis del propio autor (M2) y un zero-shot
con NLI en dos pasos (M3). Solo se guardan probabilidades por comentario, con su seudónimo, en
data/processed/youtube/AAAA-MM-DD_emociones.csv (y _emociones-zs.csv), que vencen como los datos crudos: la fecha
del nombre es la del dato más antiguo usado. Se guarda por lote, así que si se corta se retoma donde quedó.

Uso: python -m radar.youtube.emociones
Requiere pip install -e ".[nlp]".
"""

import collections
import datetime as dt
import hashlib
import logging
import os
import random
import re
import statistics
import sys

from radar import config
from radar.comun.archivos import anexar_csv, leer_csv, reparar_csv
from radar.comun.avance import Avance
from radar.comun.candado import exclusivo
from radar.comun.energia import sin_suspension
from radar.comun.registro import configurar
from radar.comun.texto import ahora
from radar.noticias.viabilidad import criterio, reporte
from radar.youtube import almacen, canales, filtro, viabilidad
from radar.youtube.privacidad import seudonimo

os.environ.setdefault("HF_HUB_OFFLINE", "1")
log = logging.getLogger(__name__)

PRUEBA = "YouTube: emociones"
INFO = "YouTube: emociones (informativo)"

# ---------------------------------------------------------------- constantes (definición del 16-nov)
EMOCIONES = ("alegria", "tristeza", "enojo", "miedo", "sorpresa", "asco")
CLASES = ("others", *EMOCIONES)
DE_PYSENTIMIENTO = {"others": "others", "joy": "alegria", "sadness": "tristeza", "anger": "enojo",
                    "fear": "miedo", "surprise": "sorpresa", "disgust": "asco"}  # fmt: skip
POLARIDADES = ("negativo", "neutral", "positivo")
DE_POLARIDAD = {"NEG": "negativo", "NEU": "neutral", "POS": "positivo"}
NOMBRE_EMOCION = {"alegria": "alegría", "tristeza": "tristeza", "enojo": "enojo", "miedo": "miedo",
                  "sorpresa": "sorpresa", "asco": "asco"}  # fmt: skip

GRUPOS_EMOJI = {
    "alegria": "😂🤣😄😁😃😆😊🥰😍",
    "tristeza": "😢😭😞😔💔🥺",
    "enojo": "😡🤬😠👿",
    "miedo": "😱😨😰😧",
    "sorpresa": "😮😲🤯😯",
    "asco": "🤢🤮",
}
GRUPO_DE_EMOJI = {e: g for g, emojis in GRUPOS_EMOJI.items() for e in emojis}
EMOJI = re.compile(
    "[\U0001f000-\U0001faff\U00002600-\U000027bf\U00002300-\U000023ff\U00002b00-\U00002bff\U0000fe0f\U0000200d"
    "\U000020e3\U00003030\U0000303d\U00003297\U00003299]"
)

PALABRAS_MINIMAS = 3
POR_AUTOR_Y_VIDEO = 3
MARCADORES_CONTACTO = ("[enlace]", "[telefono]", "[correo]")
A_MODELO = {"[mencion]": "@usuario", "[enlace]": "url", "[correo]": "", "[telefono]": ""}
PALABRA = re.compile(r"[^\W\d_]+")
MARCADOR = re.compile(r"\[(?:mencion|enlace|correo|telefono)\]")
VACIAS_ES = frozenset(
    "de la que el en y los se del las un por con no una su para es al lo como más mas pero sus le ya o este sí si "
    "porque esta entre cuando muy sin sobre también tambien me hasta hay donde quien desde todo nos durante todos "
    "uno les ni contra otros ese eso ante ellos e esto mí antes algunos qué unos yo otro otras otra él tanto esa "
    "estos mucho quienes nada muchos cual poco ella estar estas algunas algo nosotros mi mis tú te ti tu tus "
    "ellas nosotras vosotros os mío mía tuyo suyo nuestro está están estamos son fue era va van hace".split()
)
VACIAS_EN = frozenset(
    "the and is of to in it you that this for with are was on be have not they what so my we but just all i "
    "your from at by he she his her them will would can there their been has had do does".split()
)
CON_ACENTO = re.compile(r"[ñáéíóúü¿¡]", re.I)

UMBRAL_M1 = 0.30
KAPPA_MINIMO = 0.40  # M2 y M3
GRUPO_MINIMO_M2 = 30
EVALUABLES_M2 = 100
MUESTRA_M3 = 400
POR_VIDEO_M3 = 5
POR_AUTOR_M3 = 1
SEMILLA_M3 = "emociones-yt-16nov"
MINIMO_POR_VIDEO = 20  # proporción de emociones por video (caso 16)
VENTANA_DIAS = 7  # reacción al video (caso 22)
HILOS_POR_PAGINA = 100  # commentThreads.list: con menos, la página trajo todos los comentarios
LARGO_ROBERTUITO = 128
LARGO_NLI = 400
CORTE_HAY_EMOCION = 0.5  # corte estándar de NLI, no se ajusta
HIPOTESIS_HAY = "Este comentario expresa una emoción."
HIPOTESIS_CUAL = "Este comentario expresa {}."
LOTE = 32

RELIGIOSO = re.compile(r"\b(dios|diosito|señor|jes[uú]s|am[eé]n|bendic|bendig|oremos|orar|oraci[oó]n|virgen|"
                       r"rezar|recemos|cristo|espíritu santo)", re.I)  # fmt: skip
SOBRE_EL_NINO = re.compile(r"\b(niñ[oa]|lluvi|llueve|huaic|fen[oó]meno|inundaci|desborde|enfen|senamhi)", re.I)

COLUMNAS = ("id", "huella", "unidad", "video", "fecha", "tramos", "truncados",
            *(f"p_{c}" for c in CLASES), "emocion", "emoji", *(f"se_{c}" for c in CLASES), "se_emocion",
            *(f"pol_{p}" for p in POLARIDADES), "polaridad")  # fmt: skip
COLUMNAS_ZS = ("id", "huella", "zs_hay", *(f"zs_{e}" for e in EMOCIONES), "zs_emocion")


# ---------------------------------------------------------------- texto


def sin_emojis(texto):
    return re.sub(r"[ \t]+", " ", EMOJI.sub(" ", texto or "")).strip()


def palabras(texto):
    return len(PALABRA.findall(MARCADOR.sub(" ", sin_emojis(texto))))


def idioma(texto):
    """'es', 'en' o 'dudoso', por palabras vacías (robertuito solo es para español)."""
    tokens = [t.lower() for t in PALABRA.findall(MARCADOR.sub(" ", texto or ""))]
    es, en = sum(t in VACIAS_ES for t in tokens), sum(t in VACIAS_EN for t in tokens)
    if es > en:
        return "es"
    if en > es:
        return "en"
    return "es" if CON_ACENTO.search(texto or "") else "dudoso"


def para_modelo(texto):
    """Cambia los marcadores de la limpieza por las formas con que se entrenó robertuito."""
    for marcador, forma in A_MODELO.items():
        texto = texto.replace(marcador, forma)
    return texto


def grupo_emoji(texto):
    """Grupo de los emojis del texto si todos los de los grupos son de uno solo; si no, ''."""
    grupos = {GRUPO_DE_EMOJI[c] for c in texto or "" if c in GRUPO_DE_EMOJI}
    return grupos.pop() if len(grupos) == 1 else ""


VERSION = "2"  # 2: cada tramo se comprueba con su largo real (la 1 truncaba 27 tramos)


def partir_hasta_caber(tramo, contar, maximo):
    """Parte por la mitad (en palabras) el tramo que, contado entero, no cabe. Hace falta porque el tokenizador de
    robertuito da menos tokens a las palabras sueltas que a la frase (los emojis traducidos son largas tiras de
    palabras), y el conteo por palabras de embeddings.tramos se queda corto."""
    palabras_ = tramo.split()
    if len(palabras_) < 2 or contar([tramo])[0] <= maximo:
        return [tramo]
    mitad = len(palabras_) // 2
    return [p for parte in (palabras_[:mitad], palabras_[mitad:])
            for p in partir_hasta_caber(" ".join(parte), contar, maximo)]  # fmt: skip


def huella(texto):
    """Cambia si cambia el texto o la versión del cálculo: así la retoma rehace lo que quedó viejo."""
    return hashlib.sha1((VERSION + texto).encode("utf-8")).hexdigest()[:10]


def _normal(texto):
    return " ".join((texto or "").lower().split())


# ---------------------------------------------------------------- población


def unidades(comentarios, videos, canales_por_id):
    """Comentarios a procesar, con su unidad ('principal' = población de M1 a M3, 'respuesta' o 'corto'), y los
    descartes por motivo. Solo comentarios de videos que pasan el filtro."""
    descartes = collections.Counter()
    pasan = {v["id"]: v for v in videos.values() if filtro.pasa(v, canales_por_id.get(v["canal"]))}
    candidatos = []
    orden = sorted(comentarios.values(), key=lambda c: (c["video"], c["autor"], c["publicado"], c["id"]))
    for c in orden:
        video = pasan.get(c["video"])
        if not video:
            continue
        texto = c.get("texto") or ""
        if c["autor"] and c["autor"] == seudonimo(video["canal"]):
            descartes["del dueño del canal"] += 1
        elif any(m in texto for m in MARCADORES_CONTACTO):
            descartes["con enlace o datos de contacto"] += 1
        elif palabras(texto) == 0:
            descartes["vacío o solo emojis"] += 1
        elif (lengua := idioma(texto)) != "es":
            descartes["en inglés" if lengua == "en" else "idioma dudoso"] += 1
        else:
            unidad = "respuesta" if c.get("hilo") else ("corto" if palabras(texto) < PALABRAS_MINIMAS else "principal")
            candidatos.append({**c, "unidad": unidad})
    salida, vistos, por_autor = [], set(), collections.Counter()
    for c in candidatos:
        if c["unidad"] == "principal" and c["autor"]:
            clave = (c["autor"], c["video"], _normal(c["texto"]))
            if clave in vistos:
                descartes["repetido del mismo autor"] += 1
                continue
            vistos.add(clave)
            por_autor[(c["autor"], c["video"])] += 1
            if por_autor[(c["autor"], c["video"])] > POR_AUTOR_Y_VIDEO:
                descartes[f"más de {POR_AUTOR_Y_VIDEO} por autor y video"] += 1
                continue
        salida.append(c)
    return salida, descartes, pasan


def items(unidades_, videos_pasan):
    """Lo que entra al modelo: el texto (con los marcadores cambiados) y, si tiene emojis, también sin ellos."""
    salida = []
    for c in unidades_:
        texto = para_modelo(c["texto"])
        limpio = sin_emojis(texto)
        salida.append({"id": c["id"], "unidad": c["unidad"], "video": c["video"], "fecha": c["publicado"],
                       "texto": texto, "sin_emoji": limpio if limpio != texto.strip() else None,
                       "emoji": grupo_emoji(c["texto"]), "huella": huella(texto)})  # fmt: skip
    for v in sorted(videos_pasan.values(), key=lambda v: v["id"]):
        texto = v.get("titulo") or ""
        if texto.strip():
            salida.append({"id": "titulo-" + v["id"], "unidad": "titulo", "video": v["id"], "fecha": v["publicado"],
                           "texto": texto, "sin_emoji": None, "emoji": "", "huella": huella(texto)})  # fmt: skip
    return salida


def muestra_m3(poblacion):
    """MUESTRA_M3 comentarios al azar con la semilla fija, máximo POR_VIDEO_M3 por video y POR_AUTOR_M3 por autor."""
    orden = sorted(poblacion, key=lambda c: c["id"])
    random.Random(SEMILLA_M3).shuffle(orden)
    por_video, por_autor, salida = collections.Counter(), collections.Counter(), []
    for c in orden:
        if len(salida) >= MUESTRA_M3:
            break
        if por_video[c["video"]] >= POR_VIDEO_M3 or (c["autor"] and por_autor[c["autor"]] >= POR_AUTOR_M3):
            continue
        por_video[c["video"]] += 1
        por_autor[c["autor"]] += 1
        salida.append(c)
    return salida


# ---------------------------------------------------------------- modelos


class Robertuito:
    """pysentimiento por tramos de hasta 128 tokens, sin truncar; probabilidades promediadas entre tramos."""

    def __init__(self, tarea, mapa):
        import torch
        import transformers
        from pysentimiento import create_analyzer
        from pysentimiento.preprocessing import preprocess_tweet

        from radar.nlp import embeddings

        transformers.logging.set_verbosity_error()
        self.torch, self.prep, self.embeddings = torch, preprocess_tweet, embeddings
        self.analizador = create_analyzer(task=tarea, lang="es")
        self.modelo, self.tok = self.analizador.model.float().eval(), self.analizador.tokenizer
        self.etiquetas = [mapa[self.modelo.config.id2label[i]] for i in range(len(mapa))]
        self.maximo = LARGO_ROBERTUITO - 2 - embeddings.MARGEN_TOKENS

    def _contar(self, textos):
        return [len(x) for x in self.tok(list(textos), add_special_tokens=False)["input_ids"]] if textos else []

    def tramos(self, texto):
        prep = self.analizador.preprocessing_args
        lineas = [" ".join(self.prep(linea, **prep).split()) for linea in texto.split("\n")]
        tramos = self.embeddings.tramos("\n".join(lineas), self._contar, self.maximo) or [""]
        return [p for t in tramos for p in partir_hasta_caber(t, self._contar, self.maximo)]

    def __call__(self, textos):
        """[(probabilidades, tramos, truncados)] de cada texto."""
        de, todos = [], []
        for i, t in enumerate(textos):
            partes = self.tramos(t)
            todos += partes
            de += [i] * len(partes)
        largos = [len(x) for x in self.tok(todos)["input_ids"]]
        probas = []
        for i in range(0, len(todos), LOTE):
            entrada = self.tok(todos[i : i + LOTE], padding=True, truncation=True, max_length=LARGO_ROBERTUITO,
                               return_tensors="pt")  # fmt: skip
            with self.torch.no_grad():
                probas += self.torch.softmax(self.modelo(**entrada).logits, dim=-1).tolist()
        salida = []
        for i in range(len(textos)):
            filas = [p for p, j in zip(probas, de, strict=True) if j == i]
            media = [sum(col) / len(filas) for col in zip(*filas, strict=True)]
            truncados = sum(n > LARGO_ROBERTUITO for n, j in zip(largos, de, strict=True) if j == i)
            salida.append((dict(zip(self.etiquetas, media, strict=True)), len(filas), truncados))
        return salida


class ZeroShot:
    """mDeBERTa NLI en dos pasos: ¿hay emoción? (implicación frente a contradicción) y ¿cuál? (softmax de la
    implicación entre las 6 hipótesis), como zero-shot-classification con y sin multi_label."""

    def __init__(self):
        import torch
        import transformers
        from transformers import AutoModelForSequenceClassification, AutoTokenizer

        from radar.nlp import embeddings

        transformers.logging.set_verbosity_error()
        self.torch, self.embeddings = torch, embeddings
        self.tok = AutoTokenizer.from_pretrained(config.MODELO_NLI)
        self.modelo = AutoModelForSequenceClassification.from_pretrained(config.MODELO_NLI, dtype=torch.float32).eval()
        ids = {k.lower(): v for k, v in self.modelo.config.label2id.items()}
        self.implica, self.contradice = ids["entailment"], ids["contradiction"]

    def _contar(self, textos):
        return [len(x) for x in self.tok(list(textos), add_special_tokens=False)["input_ids"]] if textos else []

    def __call__(self, texto):
        hipotesis = [HIPOTESIS_HAY] + [HIPOTESIS_CUAL.format(NOMBRE_EMOCION[e]) for e in EMOCIONES]
        hay, cual = [], []
        for t in self.embeddings.tramos(texto, self._contar, LARGO_NLI) or [texto]:
            entrada = self.tok([t] * len(hipotesis), hipotesis, padding=True, truncation="only_first",
                               max_length=512, return_tensors="pt")  # fmt: skip
            with self.torch.no_grad():
                logits = self.modelo(**entrada).logits
            par = logits[0, [self.contradice, self.implica]]
            hay.append(self.torch.softmax(par, dim=0)[1].item())
            cual.append(self.torch.softmax(logits[1:, self.implica], dim=0).tolist())
        media = [sum(col) / len(cual) for col in zip(*cual, strict=True)]
        return sum(hay) / len(hay), dict(zip(EMOCIONES, media, strict=True))


# ---------------------------------------------------------------- etiquetas


def argmax(probas, clases):
    return max(clases, key=lambda c: probas[c])


def etiqueta_zs(hay, cual):
    return "others" if hay < CORTE_HAY_EMOCION else argmax(cual, EMOCIONES)


def fila(item, emocion, sin_emoji, polaridad):
    p, tramos, truncados = emocion
    salida = {"id": item["id"], "huella": item["huella"], "unidad": item["unidad"], "video": item["video"],
              "fecha": item["fecha"], "tramos": tramos, "truncados": truncados,
              **{f"p_{c}": round(p[c], 5) for c in CLASES}, "emocion": argmax(p, CLASES),
              "emoji": item["emoji"]}  # fmt: skip
    q = sin_emoji[0] if sin_emoji else p  # sin emojis el texto es el mismo
    salida |= {**{f"se_{c}": round(q[c], 5) for c in CLASES}, "se_emocion": argmax(q, CLASES)}
    salida |= {**{f"pol_{x}": round(polaridad[0][x], 5) for x in POLARIDADES},
               "polaridad": argmax(polaridad[0], POLARIDADES)}  # fmt: skip
    return salida


# ---------------------------------------------------------------- lectura con retoma


def hechos(ruta, columnas):
    """Filas ya guardadas, por id (la última gana). Repara la última línea si un corte la dejó a medias."""
    reparar_csv(ruta, columnas)
    return {f["id"]: f for f in leer_csv(ruta)}


def pendientes(lista, previos):
    return [x for x in lista if previos.get(x["id"], {}).get("huella") != x["huella"]]


def procesar(lista, ruta, emocion, polaridad, lote=LOTE):
    """Pasa por pysentimiento lo que falta y lo guarda por lote."""
    previos = hechos(ruta, COLUMNAS)
    faltan = pendientes(lista, previos)
    avance = Avance("Emociones (pysentimiento)", len(faltan), previos=len(lista) - len(faltan))
    for i in range(0, len(faltan), lote):
        grupo = faltan[i : i + lote]
        e = emocion([x["texto"] for x in grupo])
        con_emoji = [j for j, x in enumerate(grupo) if x["sin_emoji"]]
        s = dict(zip(con_emoji, emocion([grupo[j]["sin_emoji"] for j in con_emoji]), strict=True)) if con_emoji else {}
        p = polaridad([x["texto"] for x in grupo])
        anexar_csv(ruta, COLUMNAS, [fila(x, e[j], s.get(j), p[j]) for j, x in enumerate(grupo)])
        avance.paso(len(grupo))
    return hechos(ruta, COLUMNAS)


def procesar_zs(lista, ruta, zero_shot):
    """Zero-shot sobre el texto sin emojis de la muestra de M3, guardando de a uno."""
    previos = hechos(ruta, COLUMNAS_ZS)
    faltan = pendientes(lista, previos)
    avance = Avance("Zero-shot (M3)", len(faltan), previos=len(lista) - len(faltan), cada=30)
    for x in faltan:
        hay, cual = zero_shot(x["sin_emoji"] or x["texto"])
        anexar_csv(ruta, COLUMNAS_ZS, [{"id": x["id"], "huella": x["huella"], "zs_hay": round(hay, 5),
                                        **{f"zs_{e}": round(cual[e], 5) for e in EMOCIONES},
                                        "zs_emocion": etiqueta_zs(hay, cual)}])  # fmt: skip
        avance.paso()
    return hechos(ruta, COLUMNAS_ZS)


# ---------------------------------------------------------------- medidas


def kappa(a, b, clases):
    from sklearn.metrics import cohen_kappa_score

    if not a or len(set(a) | set(b)) < 2:
        return float("nan")
    return float(cohen_kappa_score(a, b, labels=list(clases)))


def _r(x):
    return round(x, 3) if x == x else "nan"


def _reparto(filas, campo="emocion", clases=CLASES):
    n = len(filas)
    conteo = collections.Counter(f[campo] for f in filas)
    return {c: round(conteo[c] / n, 3) for c in clases if conteo[c]} if n else {}


def _con_emocion(filas, campo="emocion"):
    return sum(f[campo] != "others" for f in filas) / len(filas) if filas else 0.0


def medir(resultados, zs, ids_muestra):
    poblacion = [f for f in resultados if f["unidad"] == "principal"]
    filas = []
    truncados = sum(int(f["truncados"]) for f in poblacion)
    varios = sum(int(f["tramos"]) > 1 for f in poblacion)
    filas.append(criterio(PRUEBA, "M0 comentarios truncados (tramos de 128 tokens)", truncados, "0", truncados == 0,
                          f"{varios} comentarios en más de un tramo"))  # fmt: skip
    m1 = _con_emocion(poblacion)
    por_video = collections.defaultdict(list)
    for f in poblacion:
        por_video[f["video"]].append(f)
    medianas = [_con_emocion(g) for g in por_video.values() if len(g) >= MINIMO_POR_VIDEO]
    detalle = f"{len(poblacion)} comentarios; mediana por video {_r(statistics.median(medianas)) if medianas else '-'}"
    filas.append(criterio(PRUEBA, "M1 proporción con una emoción (no 'others')", _r(m1), f">= {UMBRAL_M1}",
                          bool(poblacion) and m1 >= UMBRAL_M1,
                          f"{detalle} ({len(medianas)} videos con >= {MINIMO_POR_VIDEO}); "
                          f"{_reparto(poblacion)}"))  # fmt: skip

    con_emoji = [f for f in poblacion if f["emoji"]]
    asignados = [f for f in con_emoji if f["se_emocion"] != "others"]
    por_grupo = collections.Counter(f["emoji"] for f in asignados)
    validos = {g for g, n in por_grupo.items() if n >= GRUPO_MINIMO_M2}
    evaluables = [f for f in asignados if f["emoji"] in validos]
    k2 = kappa([f["emoji"] for f in evaluables], [f["se_emocion"] for f in evaluables], EMOCIONES)
    filas.append(criterio(PRUEBA, "M2 κ pysentimiento (sin emojis) frente al grupo del emoji", _r(k2),
                          f">= {KAPPA_MINIMO}, con >= {EVALUABLES_M2} evaluables",
                          len(evaluables) >= EVALUABLES_M2 and k2 == k2 and k2 >= KAPPA_MINIMO,
                          f"{len(evaluables)} evaluables; por grupo {dict(por_grupo)}; grupos con >= "
                          f"{GRUPO_MINIMO_M2}: {sorted(validos)}"))  # fmt: skip

    pares = [
        (f["se_emocion"], zs[f["id"]]["zs_emocion"]) for f in poblacion if f["id"] in ids_muestra and f["id"] in zs
    ]
    a, b = [x for x, _ in pares], [y for _, y in pares]
    k3 = kappa(a, b, CLASES)
    filas.append(criterio(PRUEBA, "M3 κ pysentimiento frente al zero-shot (sin emojis, 7 clases)", _r(k3),
                          f">= {KAPPA_MINIMO}", len(pares) > 0 and k3 == k3 and k3 >= KAPPA_MINIMO,
                          f"{len(pares)} comentarios; zero-shot {_reparto([{'e': y} for y in b], 'e')}"))  # fmt: skip
    return filas, {"poblacion": poblacion, "con_emoji": con_emoji, "evaluables": evaluables, "pares": pares}


def decision(filas):
    pasa = {f["criterio"][:2]: f["pasa"] for f in filas}
    if all(pasa.get(m) for m in ("M0", "M1", "M2", "M3")):
        return "Pasan M0 a M3: las emociones entran en la analítica, el estudio de eventos y el modelo secundario"
    if pasa.get("M0") and pasa.get("M1"):
        return "Pasan M0 y M1, no M2 o M3: las emociones quedan solo descriptivas"
    return "No pasa M0 o M1: no se usan emociones; la polaridad queda como descriptiva"


def informativo(resultados, zs, medidas, comentarios, pasan, tipos, descartes):
    filas = []
    for unidad in ("respuesta", "corto", "titulo"):
        grupo = [f for f in resultados if f["unidad"] == unidad]
        filas.append(criterio(INFO, f"M1 en {unidad}s", _r(_con_emocion(grupo)), "-", True,
                              f"{len(grupo)}; {_reparto(grupo)}"))  # fmt: skip
    filas.append(criterio(INFO, "descartes de la población", sum(descartes.values()), "-", True, str(dict(descartes))))
    poblacion = medidas["poblacion"]
    tipo_de = {v["id"]: (tipos.get(v["canal"]) or {}).get("tipo", "sin tipo") for v in pasan.values()}
    for nombre, clave in (("tipo de canal", lambda f: tipo_de.get(f["video"], "sin tipo")),
                          ("mes del comentario", lambda f: filtro.fecha_lima(f["fecha"]).strftime("%Y-%m")),
                          ("largo", lambda f: _largo(comentarios, f["id"]))):  # fmt: skip
        grupos = collections.defaultdict(list)
        for f in poblacion:
            grupos[clave(f)].append(f)
        detalle = "; ".join(f"{k} (n={len(g)}): con emoción {_r(_con_emocion(g))}" for k, g in sorted(grupos.items()))
        filas.append(criterio(INFO, f"emociones por {nombre}", len(grupos), "-", True, detalle))
    ev = medidas["evaluables"]
    matriz = collections.Counter((f["emoji"], f["se_emocion"]) for f in ev)
    filas.append(criterio(INFO, "matriz emoji → pysentimiento (M2)", len(ev), "-", True,
                          "; ".join(f"{e}→{p}: {n}" for (e, p), n in sorted(matriz.items()))))  # fmt: skip
    con_zs = [f for f in medidas["con_emoji"] if f["id"] in zs and zs[f["id"]]["zs_emocion"] != "others"]
    kz = kappa([f["emoji"] for f in con_zs], [zs[f["id"]]["zs_emocion"] for f in con_zs], EMOCIONES)
    filas.append(criterio(INFO, "κ zero-shot frente al emoji (muestra de M3)", _r(kz), "-", True, f"{len(con_zs)}"))
    pares = medidas["pares"]
    binario = kappa([a != "others" for a, _ in pares], [b != "others" for _, b in pares], (False, True))
    ambos = [(a, b) for a, b in pares if a != "others" and b != "others"]
    k6 = kappa([a for a, _ in ambos], [b for _, b in ambos], EMOCIONES)
    filas.append(criterio(INFO, "M3 descompuesto: κ binario / κ entre 6 emociones", f"{_r(binario)} / {_r(k6)}", "-",
                          True, f"{len(pares)} / {len(ambos)} comentarios"))  # fmt: skip
    sin = [f for f in poblacion if not f["emoji"]]
    filas.append(criterio(INFO, "'others' con emoji de grupo / sin emoji",
                          f"{_r(1 - _con_emocion(medidas['con_emoji'], 'se_emocion'))} / {_r(1 - _con_emocion(sin))}",
                          "-", True, f"{len(medidas['con_emoji'])} / {len(sin)} comentarios"))  # fmt: skip
    filas.append(_ventana(comentarios, pasan))
    for nombre, patron in (("religiosos", RELIGIOSO), ("que mencionan El Niño o las lluvias", SOBRE_EL_NINO)):
        si = [f for f in poblacion if patron.search(comentarios[f["id"]]["texto"])]
        no = [f for f in poblacion if not patron.search(comentarios[f["id"]]["texto"])]
        filas.append(criterio(INFO, f"comentarios {nombre} / los demás", f"{len(si)} / {len(no)}", "-", True,
                              f"{_reparto(si)} / {_reparto(no)}"))  # fmt: skip
    filas.append(criterio(INFO, "polaridad de los comentarios", len(poblacion), "-", True,
                          str(_reparto(poblacion, "polaridad", POLARIDADES))))  # fmt: skip
    return filas


def _largo(comentarios, id_):
    n = palabras(comentarios[id_]["texto"])
    return "a) 3 a 9 palabras" if n < 10 else ("b) 10 a 29" if n < 30 else "c) 30 o más")


def _ventana(comentarios, pasan):
    """Videos cuya ventana de 7 días está completa: ya pasaron 7 días y la página trajo todos los comentarios."""
    principales = collections.Counter(c["video"] for c in comentarios.values() if not c.get("hilo"))
    con, completos, jovenes = 0, 0, 0
    for vid, n in principales.items():
        v = pasan.get(vid)
        if not v:
            continue
        con += 1
        edad = (dt.date.fromisoformat(v["descargado"]) - filtro.fecha_lima(v["publicado"])).days
        if edad < VENTANA_DIAS:
            jovenes += 1
        elif n < HILOS_POR_PAGINA:
            completos += 1
    return criterio(INFO, f"ventana de {VENTANA_DIAS} días completa", f"{completos} de {con} videos", "-", True,
                    f"{jovenes} con menos de {VENTANA_DIAS} días; el resto, con la página 1 llena "
                    "(order=time)")  # fmt: skip


# ---------------------------------------------------------------- principal


def rutas(fecha):
    base = config.DIR_YOUTUBE
    return almacen.ruta("emociones", fecha, "csv", base), almacen.ruta("emociones-zs", fecha, "csv", base)


@exclusivo("radar.youtube.emociones")
def main(argv=None):
    inicio = ahora()
    configurar("youtube-emociones")
    try:
        comentarios = almacen.ultimos("comentarios")
        videos = almacen.ultimos("videos")
        canales_por_id = almacen.ultimos("canales")
        tipos = canales.tipos()
    except almacen.Vencido as e:
        log.error(str(e))
        return 1
    if not comentarios:
        log.error("No hay comentarios: corre antes python -m radar.youtube.descarga dia1")
        return 1
    lista_u, descartes, pasan = unidades(comentarios, videos, canales_por_id)
    lista = items(lista_u, pasan)
    fecha = min(dt.date.fromisoformat(x["descargado"]) for x in [*comentarios.values(), *pasan.values()])
    ruta, ruta_zs = rutas(fecha)
    poblacion = [c for c in lista_u if c["unidad"] == "principal"]
    elegidos = {c["id"] for c in muestra_m3(poblacion)}
    muestra = [x for x in lista if x["id"] in elegidos]
    log.info(f"{len(lista)} textos ({len(poblacion)} en la población); muestra de M3: {len(muestra)}")
    with sin_suspension():
        if pendientes(lista, hechos(ruta, COLUMNAS)):
            emocion = Robertuito("emotion", DE_PYSENTIMIENTO)
            polaridad = Robertuito("sentiment", DE_POLARIDAD)
        else:
            emocion = polaridad = None
        resultados = procesar(lista, ruta, emocion, polaridad)
        zs = procesar_zs(muestra, ruta_zs, ZeroShot() if pendientes(muestra, hechos(ruta_zs, COLUMNAS_ZS)) else None)
    vigentes = {x["id"]: x["huella"] for x in lista}
    resultados = [f for f in resultados.values() if vigentes.get(f["id"]) == f["huella"]]
    filas, medidas = medir(resultados, zs, elegidos)
    filas.append(criterio(PRUEBA, "Decisión", "-", "-", True, decision(filas)))
    filas += informativo(resultados, zs, medidas, comentarios, pasan, tipos, descartes)
    viabilidad.guardar(filas)
    etapas = {b.get("etapa") for b in almacen.leer("busquedas")}
    alertas = [] if "dia2" in etapas else ["Preliminar: la decisión se toma con los días 1 y 2 (caso 18)."]
    if "corte" in etapas:
        alertas.append("Corte: la decisión ya está tomada; M1 a M3 solo se repiten como informativos (caso 18).")
    reporte(filas, alertas, inicio)
    return 0


if __name__ == "__main__":
    sys.exit(main())
