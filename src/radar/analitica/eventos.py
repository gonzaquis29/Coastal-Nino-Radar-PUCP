"""Estudio de eventos: ¿cambia la cobertura de El Niño alrededor de cada comunicado del ENFEN? (definición aprobada el
8-nov, docs/analitica/eventos.md).

Serie diaria desde el 1-ene. Regresión de Poisson con tendencia lineal por tramos (un nodo cada 28 días), día de la
semana y una variable por cada día relativo al comunicado (−3 a +7). El efecto es la media de los coeficientes de los
días 0 a +2 frente a los días −3 a −1 de la misma ventana (ronda b), con errores robustos a la sobredispersión y a la
autocorrelación (Newey-West). La ronda a comparaba con los días fuera de las ventanas y usaba permutación de fechas,
que con un comunicado cada ~14 días deja el efecto real dentro de la nula. Solo usa metadatos de notas.csv (fecha,
"sobre El Niño", citas): no pide páginas ni lee cuerpos.

Ronda c (la vigente; si no pasa, el estudio queda descriptivo): cada comunicado contra sí mismo, días 0 a +2 frente a
los mismos días de la semana una semana antes (−7 a −5), con la prueba de rangos con signo de Wilcoxon sobre los
eventos. Iguala el día de la semana (12 de 18 comunicados salen un viernes) y casi cancela la tendencia.

Uso: python -m radar.analitica.eventos validar [--ronda a|b|c]   # V1 a V4 y los resultados (informativos)
"""

import argparse
import datetime as dt
import logging
import math
import random
import sys

import numpy as np
from scipy import stats

from radar import config
from radar.comun.archivos import escribir_csv, leer_csv
from radar.comun.registro import configurar
from radar.comun.texto import ahora
from radar.noticias.viabilidad import criterio, guardar, reporte

log = logging.getLogger(__name__)

PRUEBA = "Estudio de eventos: validación"
INFO = "Estudio de eventos (informativo)"
INICIO = "2026-01-01"
ANTES, DESPUES = 3, 7  # ventana −3 a +7
DIAS_EFECTO = (0, 1, 2)  # el efecto: media de los coeficientes de estos días
NODO_DIAS = 28  # tendencia lineal por tramos: un nodo cada 4 semanas (más lento que el ciclo de ~14 días)
PERMUTACIONES = 999
ALFA = 0.05
SEMILLA = "eventos-8nov"
# V1: tamaño con fechas falsas sobre la serie real; V1b (informativo): serie simulada sin efecto con la estructura real
CASOS_TAMANO, NULAS_POR_CASO = 1000, 199
TAMANO_MAXIMO = 0.07
# V2: potencia con un pico conocido sumado a la serie real en fechas falsas
CASOS_POTENCIA, PICO = 200, 0.50
POTENCIA_MINIMA = 0.80
BLOQUE_DIAS = 7  # V1b: remuestreo de residuos por semanas
# Ronda b (aprobada el 8-nov, tras el diagnóstico de la a)
DIAS_ANTES = (-3, -2, -1)  # el contraste: días 0 a +2 frente a estos
RETARDO_HAC = 7  # Newey-West con pesos de Bartlett hasta una semana
CASOS_B = 1000  # V1 y V2 de la ronda b, sobre series simuladas sin efecto con las fechas reales
# Ronda c (aprobada el 8-nov, último intento)
DIAS_SEMANA_ANTES = (-7, -6, -5)  # los mismos días de la semana que 0 a +2, una semana antes
SUAVIZADO = 0.5  # en log((después + 0,5) / (antes + 0,5)), por los días sin notas

SERIES = {
    "proporcion_nino": "Proporción de notas sobre El Niño entre las del día",
    "notas_nino": "Notas sobre El Niño por día",
    "citan_comunicado": "Notas que citan un comunicado y mencionan El Niño (V3, control positivo)",
    "otros_temas": "Notas de otros temas por día (V4, control negativo)",
}
CON_OFFSET = {"proporcion_nino", "citan_comunicado"}  # el total de notas del día como exposición


# ---------------------------------------------------------------- series


def series(notas, inicio, fin):
    """{nombre: np.array por día} y la lista de días, de inicio a fin (incluidos)."""
    dias = [dt.date.fromisoformat(inicio) + dt.timedelta(k)
            for k in range((dt.date.fromisoformat(fin) - dt.date.fromisoformat(inicio)).days + 1)]  # fmt: skip
    indice = {d.isoformat(): i for i, d in enumerate(dias)}
    salida = {n: np.zeros(len(dias)) for n in ("total", "nino", "citan", "otros")}
    for n in notas:
        i = indice.get(n["fecha_publicacion"][:10])
        if i is None or n["fecha_dudosa"] == "1":
            continue
        salida["total"][i] += 1
        nino, menciona = n["sobre_nino"] == "1", n["menciona_nino"] == "1"
        salida["nino"][i] += nino
        salida["citan"][i] += bool(n["comunicados"]) and menciona  # sin las citas falsas (regla del 8-nov)
        salida["otros"][i] += not nino and not menciona
    return dias, salida


def objetivo(nombre, s):
    """(y, exposición o None) de cada serie."""
    y = {"proporcion_nino": s["nino"], "notas_nino": s["nino"], "citan_comunicado": s["citan"],
         "otros_temas": s["otros"]}[nombre]  # fmt: skip
    return y, (s["total"] if nombre in CON_OFFSET else None)


def eventos_completos(fechas, dias):
    """Las fechas de emisión con la ventana entera dentro de la serie."""
    primero, ultimo = dias[0] + dt.timedelta(ANTES), dias[-1] - dt.timedelta(DESPUES)
    return sorted(f for f in fechas if primero <= f <= ultimo)


# ---------------------------------------------------------------- modelo


def relativos(dias, eventos):
    """Día relativo (−3 a +7) de cada día, o None fuera de las ventanas; error si dos ventanas se tocan."""
    salida = [None] * len(dias)
    posicion = {d: i for i, d in enumerate(dias)}
    for e in eventos:
        for k in range(-ANTES, DESPUES + 1):
            i = posicion.get(e + dt.timedelta(k))
            if i is None:
                continue
            if salida[i] is not None:
                raise ValueError(f"ventanas que se tocan en {dias[i]}")
            salida[i] = k
    return salida


def base(dias):
    """Intercepto, tendencia lineal por tramos y día de la semana."""
    n = len(dias)
    t = np.arange(n) / NODO_DIAS
    columnas = [np.ones(n), t] + [np.maximum(0, t - k) for k in range(1, int(t[-1]) + 1)]
    columnas += [np.array([d.weekday() == w for d in dias], dtype=float) for w in range(1, 7)]
    return np.column_stack(columnas)


def diseno(fija, rel):
    dias_ev = list(range(-ANTES, DESPUES + 1))
    ev = np.array([[r == k for k in dias_ev] for r in rel], dtype=float)
    return np.hstack([fija, ev])


def poisson(X, y, exposicion=None, iteraciones=100, tol=1e-9):
    """Coeficientes de Poisson por IRLS con log(exposición) como offset; días con exposición 0 fuera."""
    if exposicion is not None:
        validos = exposicion > 0
        X, y, offset = X[validos], y[validos], np.log(exposicion[validos])
    else:
        offset = np.zeros(len(y))
    beta = np.zeros(X.shape[1])
    beta[0] = np.log(max(y.sum(), 1e-9) / np.exp(offset).sum())
    ridge = 1e-6 * np.eye(X.shape[1])
    for _ in range(iteraciones):
        eta = np.clip(X @ beta + offset, -30, 30)
        mu = np.exp(eta)
        nuevo = beta + np.linalg.solve(X.T @ (mu[:, None] * X) + ridge, X.T @ (y - mu) - ridge @ beta)
        if np.max(np.abs(nuevo - beta)) < tol:
            return nuevo
        beta = nuevo
    return beta


def perfil(fija, y, exposicion, rel):
    """{día relativo: coeficiente} y el efecto (media de los días 0 a +2)."""
    beta = poisson(diseno(fija, rel), y, exposicion)
    coef = dict(zip(range(-ANTES, DESPUES + 1), beta[fija.shape[1] :], strict=True))
    return coef, float(np.mean([coef[k] for k in DIAS_EFECTO]))


def efecto(fija, y, exposicion, rel):
    return perfil(fija, y, exposicion, rel)[1]


# ---------------------------------------------------------------- fechas falsas e inferencia


def falsas(eventos, dias, azar):
    """Mismos intervalos entre comunicados, barajados, con un inicio al azar dentro de la serie."""
    huecos = [(b - a).days for a, b in zip(eventos, eventos[1:], strict=False)]
    azar.shuffle(huecos)
    largo = sum(huecos)
    primero, ultimo = dias[0] + dt.timedelta(ANTES), dias[-1] - dt.timedelta(DESPUES)
    holgura = (ultimo - primero).days - largo
    if holgura < 0:
        raise ValueError("los comunicados no caben en la serie")
    fechas = [primero + dt.timedelta(azar.randint(0, holgura))]
    for h in huecos:
        fechas.append(fechas[-1] + dt.timedelta(h))
    return fechas


def nulas(fija, y, exposicion, eventos, dias, n, azar):
    return np.array([efecto(fija, y, exposicion, relativos(dias, falsas(eventos, dias, azar))) for _ in range(n)])


def valor_p(observado, nula):
    """Bilateral, con la corrección +1 de las pruebas de permutación."""
    return (1 + np.sum(np.abs(nula) >= abs(observado))) / (1 + len(nula))


def con_pico(y, rel, pico, azar):
    """La serie con un aumento de `pico` en los días 0 a +2 de rel (Poisson sobre lo añadido: sigue siendo entera)."""
    y = y.copy()
    rng = np.random.default_rng(azar.randrange(2**32))
    for i, r in enumerate(rel):
        if r in DIAS_EFECTO:
            y[i] += rng.poisson(pico * y[i])
    return y


def nula_simulada(fija, y, exposicion, azar):
    """Serie sin efecto con la estructura real: lo ajustado sin ventanas por residuos multiplicativos de la serie,
    remuestreados por semanas (conserva la autocorrelación corta)."""
    validos = exposicion > 0 if exposicion is not None else np.ones(len(y), bool)
    beta = poisson(fija, y, exposicion)
    offset = np.log(np.where(validos, exposicion, 1)) if exposicion is not None else 0
    mu = np.exp(fija @ beta + offset)
    razon = (y + 0.5) / (mu + 0.5)
    n = len(y)
    inicios = list(range(0, n - BLOQUE_DIAS + 1))
    nueva = []
    while len(nueva) < n:
        i = azar.choice(inicios)
        nueva.extend(razon[i : i + BLOQUE_DIAS])
    lam = mu * np.array(nueva[:n])
    rng = np.random.default_rng(azar.randrange(2**32))
    return np.where(validos, rng.poisson(lam), 0).astype(float)


# ---------------------------------------------------------------- criterios


def criterio_tamano(fija, y, exposicion, eventos, dias, azar, nula_real):
    """V1: fechas falsas como si fueran las reales, frente a la nula de la serie real."""
    falsos = nulas(fija, y, exposicion, eventos, dias, CASOS_TAMANO, azar)
    tasa = float(np.mean([valor_p(e, nula_real) < ALFA for e in falsos]))
    return criterio(PRUEBA, "V1. Tamaño: fechas falsas significativas al 5 %", round(tasa, 3), f"≤ {TAMANO_MAXIMO}",
                    tasa <= TAMANO_MAXIMO, f"{CASOS_TAMANO} conjuntos frente a {len(nula_real)}")  # fmt: skip


def criterio_tamano_simulado(fija, y, exposicion, eventos, dias, azar, casos):
    """V1b (informativo): series sin efecto con la estructura real, probadas con las fechas reales."""
    rel = relativos(dias, eventos)
    rechazos = 0
    for _ in range(casos):
        ys = nula_simulada(fija, y, exposicion, azar)
        rechazos += valor_p(efecto(fija, ys, exposicion, rel),
                            nulas(fija, ys, exposicion, eventos, dias, NULAS_POR_CASO, azar)) < ALFA  # fmt: skip
    return criterio(INFO, "V1b. Tamaño en series simuladas sin efecto (fechas reales)", round(rechazos / casos, 3),
                    f"≈ {ALFA}", True, f"{casos} series, {NULAS_POR_CASO} fechas falsas cada una")  # fmt: skip


def criterio_potencia(fija, y, exposicion, eventos, dias, azar, casos):
    """V2: +50 % en los días 0 a +2 de fechas falsas sobre la serie real: ¿se detecta?"""
    detectados = 0
    for _ in range(casos):
        rel = relativos(dias, falsas(eventos, dias, azar))
        yp = con_pico(y, rel, PICO, azar)
        e = efecto(fija, yp, exposicion, rel)
        detectados += e > 0 and valor_p(e, nulas(fija, yp, exposicion, eventos, dias, NULAS_POR_CASO, azar)) < ALFA
    tasa = detectados / casos
    return criterio(PRUEBA, f"V2. Potencia: pico de +{PICO:.0%} detectado", round(tasa, 3), f"≥ {POTENCIA_MINIMA}",
                    tasa >= POTENCIA_MINIMA, f"{casos} casos, {NULAS_POR_CASO} fechas falsas cada uno")  # fmt: skip


def resultado(nombre, fija, s, eventos, dias, azar):
    """Efecto, valor p, perfil por día y rango sin cada comunicado."""
    y, exposicion = objetivo(nombre, s)
    rel = relativos(dias, eventos)
    coef, e = perfil(fija, y, exposicion, rel)
    nula = nulas(fija, y, exposicion, eventos, dias, PERMUTACIONES, azar)
    sin_uno = [efecto(fija, y, exposicion, relativos(dias, [x for x in eventos if x != quitado]))
               for quitado in eventos]  # fmt: skip
    return {"serie": nombre, "efecto": e, "p": float(valor_p(e, nula)), "coef": coef, "nula": nula,
            "sin_uno": (min(sin_uno), max(sin_uno))}  # fmt: skip


def _pct(b):
    return f"{np.expm1(b):+.0%}"


def fila_resultado(r, prueba, nombre_criterio, pasa, umbral):
    perfil_txt = " ".join(f"{k:+d}:{_pct(b)}" for k, b in r["coef"].items())
    rango = f"{_pct(r['sin_uno'][0])} a {_pct(r['sin_uno'][1])}"
    return criterio(prueba, nombre_criterio, f"{_pct(r['efecto'])} (p = {r['p']:.3f})", umbral, pasa,
                    f"sin cada comunicado: {rango}; perfil {perfil_txt}")  # fmt: skip


def validar():
    """Ronda a: permutación de fechas frente a los días fuera de las ventanas (no pasa V2 ni V3)."""
    fin, dias, s, eventos = _datos()
    fija = base(dias)
    azar = random.Random(SEMILLA)
    resultados = {n: resultado(n, fija, s, eventos, dias, azar) for n in SERIES}

    y, exposicion = objetivo("proporcion_nino", s)
    filas = [
        criterio_tamano(fija, y, exposicion, eventos, dias, azar, resultados["proporcion_nino"]["nula"]),
        criterio_potencia(fija, y, exposicion, eventos, dias, azar, CASOS_POTENCIA),
    ]
    v3, v4 = resultados["citan_comunicado"], resultados["otros_temas"]
    filas.append(fila_resultado(v3, PRUEBA, "V3. Control positivo: citas al comunicado suben (días 0 a +2)",
                                v3["efecto"] > 0 and v3["p"] < ALFA, f"> 0 y p < {ALFA}"))  # fmt: skip
    filas.append(fila_resultado(v4, PRUEBA, "V4. Control negativo: otros temas sin efecto", v4["p"] >= ALFA,
                                f"p ≥ {ALFA}"))  # fmt: skip
    filas.append(criterio_tamano_simulado(fija, y, exposicion, eventos, dias, azar, CASOS_POTENCIA))
    for n in ("proporcion_nino", "notas_nino"):
        filas.append(fila_resultado(resultados[n], INFO, SERIES[n], True, ""))
    filas.append(criterio(INFO, "Comunicados con la ventana completa", len(eventos), "", True,
                          f"{eventos[0]} a {eventos[-1]}; serie de {len(dias)} días hasta {fin}"))  # fmt: skip
    escribir_salidas(dias, s, eventos, {r["serie"]: r["coef"] for r in resultados.values()})
    return filas


# ---------------------------------------------------------------- ronda b: contraste antes y después con Newey-West


def ajuste(X, y, exposicion=None):
    """(beta, X, y, mu) de Poisson, solo con los días con exposición."""
    if exposicion is not None:
        validos = exposicion > 0
        X, y, offset = X[validos], y[validos], np.log(exposicion[validos])
    else:
        offset = np.zeros(len(y))
    beta = poisson(X, y, np.exp(offset))
    return beta, X, y, np.exp(np.clip(X @ beta + offset, -30, 30))


def covarianza_hac(X, y, mu, retardo=RETARDO_HAC):
    """Sándwich de Newey-West para Poisson: inv(A) B inv(A), con A = X' diag(mu) X y B de los puntajes x (y - mu)."""
    a = np.linalg.inv(X.T @ (mu[:, None] * X) + 1e-9 * np.eye(X.shape[1]))
    puntajes = X * (y - mu)[:, None]
    b = puntajes.T @ puntajes
    for k in range(1, retardo + 1):
        g = puntajes[k:].T @ puntajes[:-k]
        b += (1 - k / (retardo + 1)) * (g + g.T)
    return a @ b @ a


def vector_contraste(fija):
    """c tal que c'beta = media de los días 0 a +2 menos media de los días −3 a −1."""
    c = np.zeros(fija.shape[1] + ANTES + DESPUES + 1)
    for k in DIAS_EFECTO:
        c[fija.shape[1] + k + ANTES] += 1 / len(DIAS_EFECTO)
    for k in DIAS_ANTES:
        c[fija.shape[1] + k + ANTES] -= 1 / len(DIAS_ANTES)
    return c


def prueba_b(fija, y, exposicion, rel):
    """(contraste, valor p bilateral, coeficientes por día) con el error de Newey-West."""
    beta, X, yv, mu = ajuste(diseno(fija, rel), y, exposicion)
    c = vector_contraste(fija)
    error = math.sqrt(max(float(c @ covarianza_hac(X, yv, mu) @ c), 1e-12))
    z = float(c @ beta) / error
    coef = dict(zip(range(-ANTES, DESPUES + 1), beta[fija.shape[1] :], strict=True))
    return float(c @ beta), math.erfc(abs(z) / math.sqrt(2)), coef


def criterios_b(fija, y, exposicion, rel, azar, casos=CASOS_B):
    """V1 (tamaño) y V2 (potencia) en series simuladas sin efecto, con la estructura real y las fechas reales."""
    rechazos = detectados = 0
    for _ in range(casos):
        ys = nula_simulada(fija, y, exposicion, azar)
        rechazos += prueba_b(fija, ys, exposicion, rel)[1] < ALFA
        e, p, _ = prueba_b(fija, con_pico(ys, rel, PICO, azar), exposicion, rel)
        detectados += e > 0 and p < ALFA
    return [
        criterio(PRUEBA, "V1. Tamaño: series simuladas sin efecto, significativas al 5 %", round(rechazos / casos, 3),
                 f"≤ {TAMANO_MAXIMO}", rechazos / casos <= TAMANO_MAXIMO, f"{casos} series, fechas reales"),
        criterio(PRUEBA, f"V2. Potencia: pico de +{PICO:.0%} detectado", round(detectados / casos, 3),
                 f"≥ {POTENCIA_MINIMA}", detectados / casos >= POTENCIA_MINIMA, f"{casos} series, fechas reales"),
    ]  # fmt: skip


def fila_b(nombre, fija, s, dias, eventos, prueba, nombre_criterio, pasa_de, umbral):
    y, exposicion = objetivo(nombre, s)
    e, p, coef = prueba_b(fija, y, exposicion, relativos(dias, eventos))
    sin_uno = [prueba_b(fija, y, exposicion, relativos(dias, [x for x in eventos if x != q]))[0] for q in eventos]
    perfil_txt = " ".join(f"{k:+d}:{_pct(b)}" for k, b in coef.items())
    detalle = f"sin cada comunicado: {_pct(min(sin_uno))} a {_pct(max(sin_uno))}; perfil {perfil_txt}"
    return criterio(prueba, nombre_criterio, f"{_pct(e)} (p = {p:.3f})", umbral, pasa_de(e, p), detalle), coef


def _datos():
    notas = leer_csv(config.DIR_NOTICIAS / "notas.csv")
    fin = max(n["fecha_publicacion"][:10] for n in notas)
    dias, s = series(notas, INICIO, fin)
    emision = [dt.date.fromisoformat(c["fecha_emision"]) for c in leer_csv(config.DIR_OFICIAL / "comunicados.csv")]
    eventos = eventos_completos(emision, dias)
    log.info(f"Serie {INICIO} a {fin} ({len(dias)} días) · {len(eventos)} comunicados con la ventana completa")
    return fin, dias, s, eventos


def validar_b():
    fin, dias, s, eventos = _datos()
    fija = base(dias)
    rel = relativos(dias, eventos)
    y, exposicion = objetivo("proporcion_nino", s)
    filas = criterios_b(fija, y, exposicion, rel, random.Random(SEMILLA + "-b"))
    v3, _ = fila_b("citan_comunicado", fija, s, dias, eventos, PRUEBA,
                   "V3. Control positivo: citas al comunicado suben (días 0 a +2 frente a −3 a −1)",
                   lambda e, p: e > 0 and p < ALFA, f"> 0 y p < {ALFA}")  # fmt: skip
    v4, _ = fila_b("otros_temas", fija, s, dias, eventos, PRUEBA, "V4. Control negativo: otros temas sin efecto",
                   lambda e, p: p >= ALFA, f"p ≥ {ALFA}")  # fmt: skip
    filas += [v3, v4]
    perfiles = {}
    for n in SERIES:
        fila, perfiles[n] = fila_b(n, fija, s, dias, eventos, INFO, SERIES[n], lambda e, p: True, "")
        if n in ("proporcion_nino", "notas_nino"):
            filas.append(fila)
    filas.append(criterio(INFO, "Comunicados con la ventana completa", len(eventos), "", True,
                          f"{eventos[0]} a {eventos[-1]}; serie de {len(dias)} días hasta {fin}"))  # fmt: skip
    escribir_salidas(dias, s, eventos, perfiles)
    return filas


def escribir_salidas(dias, s, eventos, perfiles):
    escribir_csv(config.DIR_ANALITICA / "eventos-perfil.csv", ("serie", "dia_relativo", "coeficiente", "cambio"),
                 [{"serie": n, "dia_relativo": k, "coeficiente": round(b, 4), "cambio": round(np.expm1(b), 4)}
                  for n, coef in perfiles.items() for k, b in coef.items()])  # fmt: skip
    columnas = ("total", "nino", "citan", "otros")
    escribir_csv(config.DIR_ANALITICA / "eventos-series.csv", ("fecha", *columnas, "dia_relativo"),
                 [{"fecha": d.isoformat(), **{k: int(s[k][i]) for k in columnas},
                   "dia_relativo": r if r is not None else ""}
                  for i, (d, r) in enumerate(zip(dias, relativos(dias, eventos), strict=True))])  # fmt: skip


# ---------------------------------------------------------------- ronda c: cada evento contra su semana anterior


def diferencias(y, exposicion, dias, eventos):
    """Por evento: log del cociente entre los días 0 a +2 y los días −7 a −5 (de la proporción si hay exposición)."""
    posicion = {d: i for i, d in enumerate(dias)}
    salida = []
    for e in eventos:
        despues = [posicion[e + dt.timedelta(k)] for k in DIAS_EFECTO]
        antes = [posicion.get(e + dt.timedelta(k)) for k in DIAS_SEMANA_ANTES]
        if None in antes:
            raise ValueError(f"sin semana anterior para {e}")
        d = math.log((y[despues].sum() + SUAVIZADO) / (y[antes].sum() + SUAVIZADO))
        if exposicion is not None:
            d -= math.log((exposicion[despues].sum() + SUAVIZADO) / (exposicion[antes].sum() + SUAVIZADO))
        salida.append(d)
    return np.array(salida)


def prueba_c(y, exposicion, dias, eventos):
    """(mediana de las diferencias, valor p bilateral de Wilcoxon, diferencias)."""
    d = diferencias(y, exposicion, dias, eventos)
    if not np.any(d):
        return 0.0, 1.0, d
    p = stats.wilcoxon(d, zero_method="wilcox", alternative="two-sided").pvalue
    return float(np.median(d)), float(p), d


def criterios_c(fija, y, exposicion, dias, eventos, azar, casos=CASOS_B):
    """V1 (tamaño) y V2 (potencia) en series simuladas sin efecto, con la estructura real y las fechas reales."""
    rel = relativos(dias, eventos)
    rechazos = detectados = 0
    for _ in range(casos):
        ys = nula_simulada(fija, y, exposicion, azar)
        rechazos += prueba_c(ys, exposicion, dias, eventos)[1] < ALFA
        e, p, _ = prueba_c(con_pico(ys, rel, PICO, azar), exposicion, dias, eventos)
        detectados += e > 0 and p < ALFA
    return [
        criterio(PRUEBA, "V1. Tamaño: series simuladas sin efecto, significativas al 5 %", round(rechazos / casos, 3),
                 f"≤ {TAMANO_MAXIMO}", rechazos / casos <= TAMANO_MAXIMO, f"{casos} series, fechas reales"),
        criterio(PRUEBA, f"V2. Potencia: pico de +{PICO:.0%} detectado", round(detectados / casos, 3),
                 f"≥ {POTENCIA_MINIMA}", detectados / casos >= POTENCIA_MINIMA, f"{casos} series, fechas reales"),
    ]  # fmt: skip


def fila_c(nombre, s, dias, eventos, prueba, nombre_criterio, pasa_de, umbral):
    y, exposicion = objetivo(nombre, s)
    e, p, d = prueba_c(y, exposicion, dias, eventos)
    detalle = (f"suben {int(np.sum(d > 0))} de {len(d)} comunicados; cuartiles {_pct(np.percentile(d, 25))} a "
               f"{_pct(np.percentile(d, 75))}")  # fmt: skip
    return criterio(prueba, nombre_criterio, f"{_pct(e)} (p = {p:.3f})", umbral, pasa_de(e, p), detalle)


def validar_c():
    fin, dias, s, eventos = _datos()
    fija = base(dias)
    y, exposicion = objetivo("proporcion_nino", s)
    filas = criterios_c(fija, y, exposicion, dias, eventos, random.Random(SEMILLA + "-c"))
    filas.append(fila_c("citan_comunicado", s, dias, eventos, PRUEBA,
                        "V3. Control positivo: citas al comunicado suben (0 a +2 frente a −7 a −5)",
                        lambda e, p: e > 0 and p < ALFA, f"> 0 y p < {ALFA}"))  # fmt: skip
    filas.append(fila_c("otros_temas", s, dias, eventos, PRUEBA, "V4. Control negativo: otros temas sin efecto",
                        lambda e, p: p >= ALFA, f"p ≥ {ALFA}"))  # fmt: skip
    for n in ("proporcion_nino", "notas_nino"):
        filas.append(fila_c(n, s, dias, eventos, INFO, SERIES[n] + " (mediana por comunicado)", lambda e, p: True, ""))
    filas.append(criterio(INFO, "Comunicados con la ventana completa", len(eventos), "", True,
                          f"{eventos[0]} a {eventos[-1]}; serie de {len(dias)} días hasta {fin}"))  # fmt: skip
    escribir_csv(config.DIR_ANALITICA / "eventos-por-comunicado.csv", ("fecha", *SERIES),
                 [{"fecha": e.isoformat(), **{n: round(float(v), 4) for n, v in fila.items()}}
                  for e, fila in zip(eventos, ({n: diferencias(*objetivo(n, s), dias, eventos)[i] for n in SERIES}
                                              for i in range(len(eventos))), strict=True)])  # fmt: skip
    return filas


def main(argv=None):
    ap = argparse.ArgumentParser(description="Estudio de eventos: efecto de cada comunicado del ENFEN.")
    ap.add_argument("paso", choices=("validar",))
    ap.add_argument("--ronda", choices=("a", "b", "c"), default="c",
                    help="a: permutación; b: Newey-West (no pasan); c: Wilcoxon por comunicado")  # fmt: skip
    args = ap.parse_args(argv)
    registro = configurar(f"analitica-eventos-{args.ronda}")
    inicio = ahora()
    config.DIR_ANALITICA.mkdir(parents=True, exist_ok=True)
    filas = {"a": validar, "b": validar_b, "c": validar_c}[args.ronda]()
    guardar(filas, config.DIR_ANALITICA / "validacion.csv")
    reporte(filas, [], inicio)
    log.info(f"Registro: {registro.relative_to(config.RAIZ)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
