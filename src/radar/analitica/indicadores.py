"""Reglas puras de la analítica web (docs/analitica/web.md, aprobada el 22-nov): correlación parcial dentro del canal,
sustitutas IAAFT y correlación cruzada para Trends, tiempo de reacción de los medios y embudo del registro de uso.
Sin archivos ni datos reales."""

import datetime as dt
import math
import statistics

import numpy as np
from scipy.stats import rankdata

DESFASES = (-2, -1, 0, 1, 2)  # semanas; positivo: Trends va detrás de las notas
ITERACIONES_IAAFT = 100
EMBUDO = (("vista",), ("verificar",), ("ver_por_que", "clic_que_hacer"), ("compartir",))
NOMBRES_EMBUDO = ("vista", "verificar", "ver por qué o qué hacer", "compartir")


# ---------------------------------------------------------------- A. engagement dentro del canal


def restar_mediana(valores, celdas):
    """Cada valor menos la mediana de su celda (tipo de canal y mes)."""
    valores, celdas = np.asarray(valores, float), np.asarray(celdas)
    salida = np.empty_like(valores)
    for c in np.unique(celdas):
        m = celdas == c
        salida[m] = valores[m] - np.median(valores[m])
    return salida


def rangos_centrados(valores, grupos):
    """Rango dentro del grupo, centrado y dividido por el tamaño del grupo (Spearman estratificado)."""
    valores, grupos = np.asarray(valores, float), np.asarray(grupos)
    salida = np.empty_like(valores)
    for g in np.unique(grupos):
        m = grupos == g
        n = m.sum()
        salida[m] = (rankdata(valores[m]) - (n + 1) / 2) / n
    return salida


def _quitar(y, x):
    if x is None or not x.shape[1]:
        return y
    coef, *_ = np.linalg.lstsq(x, y, rcond=None)
    return y - x @ coef


def correlacion_dentro(x, y, grupos, covariables=None):
    """Spearman parcial estratificado por grupo: Pearson de los rangos centrados en cada grupo, después de quitar
    las covariables (también en rangos centrados) con una regresión lineal."""
    grupos = np.asarray(grupos)
    rx, ry = rangos_centrados(x, grupos), rangos_centrados(y, grupos)
    if covariables is not None and len(covariables):
        z = np.column_stack([rangos_centrados(c, grupos) for c in covariables])
        z = z[:, np.ptp(z, axis=0) > 0]
        rx, ry = _quitar(rx, z), _quitar(ry, z)
    if len(rx) < 3 or not rx.std() or not ry.std():
        return float("nan")
    return float(np.corrcoef(rx, ry)[0, 1])


def remuestras_de_grupos(grupos, veces, semilla):
    """(índices, grupos nuevos) por réplica: se sortean grupos con reemplazo y cada copia es un grupo distinto."""
    grupos = np.asarray(grupos)
    unicos = np.unique(grupos)
    por_grupo = [np.flatnonzero(grupos == g) for g in unicos]
    azar = np.random.default_rng(semilla)
    for _ in range(veces):
        elegidos = azar.integers(0, len(unicos), len(unicos))
        indices = np.concatenate([por_grupo[k] for k in elegidos])
        nuevos = np.repeat(np.arange(len(elegidos)), [len(por_grupo[k]) for k in elegidos])
        yield indices, nuevos


def correlacion_dentro_ic(x, y, grupos, covariables, veces, semilla):
    """(ρ, réplicas del bootstrap por grupo)."""
    x, y = np.asarray(x, float), np.asarray(y, float)
    covariables = [np.asarray(c, float) for c in covariables or ()]
    rho = correlacion_dentro(x, y, grupos, covariables)
    replicas = [
        correlacion_dentro(x[i], y[i], g, [c[i] for c in covariables])
        for i, g in remuestras_de_grupos(grupos, veces, semilla)
    ]
    return rho, replicas


def con_minimo_por_grupo(grupos, minimo):
    """Máscara de los elementos cuyo grupo tiene al menos `minimo` elementos."""
    grupos = np.asarray(grupos)
    unicos, cuenta = np.unique(grupos, return_counts=True)
    grandes = set(unicos[cuenta >= minimo].tolist())
    return np.array([g in grandes for g in grupos.tolist()], dtype=bool)


def respuesta(ic, signos):
    """'sí' (lo más alejado tiene más engagement), 'no' o 'no concluyente' (docs/analitica/web.md, A.6). `ic` es el
    de ρ entre la cercanía y el engagement; `signos`, los de los períodos y de las búsquedas por fecha."""
    inferior, superior = ic
    if math.isnan(inferior) or math.isnan(superior) or inferior <= 0 <= superior:
        return "no concluyente"
    signo = 1 if inferior > 0 else -1
    if any(math.isnan(s) or np.sign(s) != signo for s in signos):
        return "no concluyente"
    return "no" if signo > 0 else "sí"


def terciles(valores):
    """Índice de tercil (0, 1, 2) de cada valor."""
    valores = np.asarray(valores, float)
    cortes = np.percentile(valores, [100 / 3, 200 / 3])
    return np.searchsorted(cortes, valores, side="right")


# ---------------------------------------------------------------- B. Trends


def semana_de(fecha):
    """Domingo que abre la semana de Trends (domingo a sábado)."""
    fecha = fecha if isinstance(fecha, dt.date) else dt.date.fromisoformat(str(fecha)[:10])
    return fecha - dt.timedelta((fecha.weekday() + 1) % 7)


def diferencias_log(valores):
    return np.diff(np.log1p(np.asarray(valores, float)))


def correlacion_cruzada(notas, trends, desfases=DESFASES):
    """{desfase: r de Pearson entre notas[t] y trends[t + desfase]}."""
    notas, trends = np.asarray(notas, float), np.asarray(trends, float)
    salida = {}
    for k in desfases:
        a, b = (notas[: len(notas) - k], trends[k:]) if k >= 0 else (notas[-k:], trends[: len(trends) + k])
        salida[k] = float(np.corrcoef(a, b)[0, 1]) if len(a) > 2 and a.std() and b.std() else float("nan")
    return salida


def maximo_absoluto(correlaciones):
    validos = [abs(r) for r in correlaciones.values() if not math.isnan(r)]
    return max(validos) if validos else float("nan")


def iaaft(serie, azar, iteraciones=ITERACIONES_IAAFT):
    """Sustituta con el espectro y la distribución de la serie (Schreiber y Schmitz, 1996)."""
    serie = np.asarray(serie, float)
    ordenados, amplitudes = np.sort(serie), np.abs(np.fft.rfft(serie))
    sustituta = azar.permutation(serie)
    for _ in range(iteraciones):
        fases = np.angle(np.fft.rfft(sustituta))
        espectral = np.fft.irfft(amplitudes * np.exp(1j * fases), n=len(serie))
        nueva = np.empty_like(serie)
        nueva[np.argsort(espectral, kind="stable")] = ordenados
        if np.array_equal(nueva, sustituta):
            break
        sustituta = nueva
    return sustituta


def nulo_cruzado(notas_dif, trends, veces, semilla, desfases=DESFASES):
    """Máximo de |r| en los desfases con `veces` sustitutas IAAFT de la serie de Trends (en niveles)."""
    azar = np.random.default_rng(semilla)
    return np.array(
        [
            maximo_absoluto(correlacion_cruzada(notas_dif, diferencias_log(iaaft(trends, azar)), desfases))
            for _ in range(veces)
        ]
    )


def sube_tras_comunicado(valor_por_semana, fecha, semanas_antes=3):
    """True o False si el promedio de la semana del comunicado y la siguiente supera al de las 3 anteriores; None si
    falta alguna de esas semanas."""
    semana = semana_de(fecha)
    despues = [semana, semana + dt.timedelta(7)]
    antes = [semana - dt.timedelta(7 * k) for k in range(1, semanas_antes + 1)]
    if any(s not in valor_por_semana for s in despues + antes):
        return None
    return statistics.fmean(valor_por_semana[s] for s in despues) > statistics.fmean(valor_por_semana[s] for s in antes)


# ---------------------------------------------------------------- C. medios


def dias_de_reaccion(emision, fechas_de_cita, ventana):
    """(días hasta la primera cita dentro de la ventana o None, hay citas después de la ventana, citas anteriores)."""
    dias = sorted((f - emision).days for f in fechas_de_cita)
    dentro = [d for d in dias if 0 <= d <= ventana]
    return (dentro[0] if dentro else None), any(d > ventana for d in dias), sum(d < 0 for d in dias)


def proporciones_principales(cuenta, primeras):
    """[(clave, proporción)] de las `primeras` claves más frecuentes y 'otras'."""
    total = sum(cuenta.values())
    if not total:
        return []
    orden = sorted(cuenta.items(), key=lambda kv: (-kv[1], kv[0]))
    salida = [(k, v / total) for k, v in orden[:primeras]]
    resto = sum(v for _, v in orden[primeras:])
    return salida + ([("otras", resto / total)] if resto else [])


# ---------------------------------------------------------------- D. registro de uso


def por_sesion(eventos):
    salida = {}
    for e in eventos:
        salida.setdefault(e["sesion"], []).append(e)
    return salida


def pasos_alcanzados(eventos_de_sesion):
    """Cuántos pasos del embudo alcanza una sesión, en orden."""
    paso = 0
    for e in eventos_de_sesion:
        if paso < len(EMBUDO) and e["evento"] in EMBUDO[paso]:
            paso += 1
    return paso


def embudo(eventos):
    """[(paso, sesiones que llegan, proporción del total de sesiones)]."""
    sesiones = por_sesion(eventos)
    alcanzados = [pasos_alcanzados(v) for v in sesiones.values()]
    total = len(alcanzados)
    return [
        (nombre, sum(a > k for a in alcanzados), sum(a > k for a in alcanzados) / total if total else float("nan"))
        for k, nombre in enumerate(NOMBRES_EMBUDO)
    ]


def tiempo_por_pantalla(eventos):
    """{pantalla: (mediana de segundos, n)}: en cada `vista`, `segundos` es el tiempo en la pantalla `anterior`."""
    tiempos = {}
    for e in eventos:
        if e["evento"] == "vista" and e.get("anterior") and str(e.get("segundos", "")).strip() != "":
            tiempos.setdefault(e["anterior"], []).append(float(e["segundos"]))
    return {p: (statistics.median(v), len(v)) for p, v in sorted(tiempos.items())}
