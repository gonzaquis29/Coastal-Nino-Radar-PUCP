"""Reglas puras del modelo de engagement (docs/modelos/engagement.md, sección 3): qué videos entran, el objetivo
suavizado, los rasgos del título y del video, y las métricas por tipo de canal. Sin modelos ni archivos."""

import datetime as dt
import math
import re
from urllib.parse import urlsplit

import numpy as np
from scipy.stats import spearmanr

from radar import config
from radar.oficial.enfen import magnitudes_de_frase
from radar.youtube import filtro
from radar.youtube.canales import es_gob_pe

DIAS_MINIMOS = 14  # README: la tasa de un video más nuevo todavía es inestable (verificado con dos descargas)
FIN_ENTRENAMIENTO = dt.date(2026, 8, 31)  # README y Y5: entrenar con enero a agosto
PALABRAS_TEXTO = 100  # el tipo "corto" calibrado del semáforo
CATEGORIAS = ("25", "22", "28", "24", "27")  # las de ≥ 50 videos en el entrenamiento; el resto se junta
TIPOS_CANAL = ("oficial", "medio", "otros")
TIPOS_ORDEN = ("medio", "otros")  # M1 y M3: los oficiales no alcanzan para un Spearman propio
HORA_DIURNA = (6, 18)  # [desde, hasta) en hora de Lima

URL = re.compile(r"(?:https?://|www\.)\S+", re.I)
HASHTAG = re.compile(r"#\w+")
MENCION = re.compile(r"@\w+")
EMOJI = re.compile("[\U0001f000-\U0001faff☀-➿⬀-⯿\U0001f1e6-\U0001f1ff]")
EXCLAMACION = re.compile(r"[!¡]")
PREGUNTA = re.compile(r"[?¿]")
DURACION = re.compile(r"^P(?:(\d+)D)?(?:T(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?)?$")


# ---------------------------------------------------------------- muestra


def segundos(duracion):
    """Duración ISO 8601 de la API (PT1M51S) en segundos; None si no se reconoce."""
    m = DURACION.match(duracion or "")
    if not m:
        return None
    d, h, mi, s = (int(x or 0) for x in m.groups())
    return d * 86400 + h * 3600 + mi * 60 + s


def particion(fecha):
    return "entrenamiento" if fecha <= FIN_ENTRENAMIENTO else "prueba"


def motivo_fuera(video, canal, corte):
    """Por qué un video que pasa el filtro no entra al modelo; None si entra."""
    publicado = filtro.fecha_lima(video.get("publicado"))
    if video.get("descargado") != corte:
        return "descarga anterior al corte"
    if publicado is None or (dt.date.fromisoformat(corte) - publicado).days < DIAS_MINIMOS:
        return "menos de 14 días"
    if not video.get("vistas") or video.get("likes") is None or video.get("comentarios") is None:
        return "sin vistas, likes ocultos o comentarios desactivados"
    return None


# ---------------------------------------------------------------- objetivo


def beta_binomial(exitos, ensayos):
    """(α, β) por el método de momentos ponderado por las vistas (Kleinman). El prior sale solo del entrenamiento."""
    x, n = np.asarray(exitos, float), np.asarray(ensayos, float)
    p = x / n
    media = (n * p).sum() / n.sum()
    varianza = (n * (p - media) ** 2).sum() / n.sum()
    inv = np.mean(1 / n)
    rho = (varianza / (media * (1 - media)) - inv) / (1 - inv)
    rho = min(max(rho, 1e-6), 1 - 1e-6)
    suma = 1 / rho - 1
    return float(media * suma), float((1 - media) * suma)


def objetivo(exitos, ensayos, alfa, beta):
    """logit((x + α) / (n + α + β)): la tasa suavizada hacia el prior (sección 3)."""
    x, n = np.asarray(exitos, float), np.asarray(ensayos, float)
    x = np.minimum(x, n)
    return np.log((x + alfa) / (n - x + beta))


def tasa(logit):
    return 1 / (1 + np.exp(-np.asarray(logit, float)))


# ---------------------------------------------------------------- rasgos


def texto_para_distancia(titulo, descripcion):
    """Título y descripción sin enlaces, hashtags ni @menciones, cortados a 100 palabras (tipo corto)."""
    partes = []
    for t in (titulo, descripcion):
        limpio = MENCION.sub(" ", HASHTAG.sub(" ", URL.sub(" ", t or "")))
        limpio = " ".join(limpio.split())
        if limpio:
            partes.append(limpio)
    salida, cuenta = [], 0
    for linea in partes:
        resto = PALABRAS_TEXTO - cuenta
        if resto <= 0:
            break
        trozo = linea.split()[:resto]
        salida.append(" ".join(trozo))
        cuenta += len(trozo)
    return "\n".join(salida)


def rasgos_titulo(titulo):
    titulo = titulo or ""
    letras = [c for c in titulo if c.isalpha()]
    return {
        "mayusculas": round(sum(c.isupper() for c in letras) / len(letras), 4) if letras else 0.0,
        "exclamaciones": len(EXCLAMACION.findall(titulo)),
        "emojis": len(EMOJI.findall(titulo)),
        "pregunta": bool(PREGUNTA.search(titulo)),
        "palabras_titulo": len(titulo.split()),
        "magnitud": bool(magnitudes_de_frase(titulo)),
    }


def enlaza_gob(enlaces):
    for e in enlaces or ():
        host = urlsplit(e if "://" in e else "https://" + e).netloc.lower().split(":")[0]
        if host and es_gob_pe(host):
            return True
    return False


def momento(publicado):
    """(fin de semana, diurno) en hora de Lima."""
    hora = dt.datetime.fromisoformat(publicado.replace("Z", "+00:00")).astimezone(config.LIMA)
    return hora.weekday() >= 5, HORA_DIURNA[0] <= hora.hour < HORA_DIURNA[1]


def categoria(valor):
    return valor if valor in CATEGORIAS else "otra"


def log1p(valor):
    return math.log1p(valor or 0)


# ---------------------------------------------------------------- métricas


def spearman(a, b):
    a, b = np.asarray(a, float), np.asarray(b, float)
    if len(a) < 3 or np.ptp(a) == 0 or np.ptp(b) == 0:
        return float("nan")
    return float(spearmanr(a, b)[0])


def spearman_por_tipo(prediccion, y, tipos):
    """Spearman dentro de medios y dentro de otros, ponderado por el n.° de videos de cada tipo (M1 y M3)."""
    prediccion, y, tipos = np.asarray(prediccion), np.asarray(y), np.asarray(tipos)
    suma = peso = 0.0
    for t in TIPOS_ORDEN:
        m = tipos == t
        r = spearman(prediccion[m], y[m])
        if not math.isnan(r):
            suma, peso = suma + r * m.sum(), peso + m.sum()
    return suma / peso if peso else float("nan")


def mae(prediccion, y):
    return float(np.mean(np.abs(np.asarray(prediccion) - np.asarray(y))))


def r2(prediccion, y):
    y, prediccion = np.asarray(y, float), np.asarray(prediccion, float)
    total = ((y - y.mean()) ** 2).sum()
    return float(1 - ((y - prediccion) ** 2).sum() / total) if total else float("nan")


def remuestras_por_grupo(grupos, veces, semilla):
    """Índices de cada réplica del bootstrap por canal: se sortean canales con reemplazo y entran todos sus videos."""
    grupos = np.asarray(grupos)
    unicos = np.unique(grupos)
    por_grupo = {g: np.flatnonzero(grupos == g) for g in unicos}
    azar = np.random.default_rng(semilla)
    for _ in range(veces):
        elegidos = azar.choice(unicos, size=len(unicos), replace=True)
        yield np.concatenate([por_grupo[g] for g in elegidos])


def intervalo(valores, nivel=0.95):
    v = np.asarray([x for x in valores if not math.isnan(x)])
    if not len(v):
        return float("nan"), float("nan")
    cola = (1 - nivel) / 2 * 100
    return float(np.percentile(v, cola)), float(np.percentile(v, 100 - cola))
