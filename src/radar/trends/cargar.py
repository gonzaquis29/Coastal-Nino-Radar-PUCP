"""Carga y prueba de viabilidad de Google Trends (criterios fijados el 16-nov; docs/youtube/definicion.md, §8).

Cada exportación va en data/raw/trends/<departamento>_<AAAA-MM-DD>.csv, con la fecha en que se exportó y un
departamento de config.DEPARTAMENTOS_TRENDS: el CSV "Interés a lo largo del tiempo" de una consulta de una sola serie
(el tema El Niño), del 1-ene al 20-nov-2026, en la región del departamento. Las consultas de contexto ("lluvias",
"huaico") van como <departamento>-contexto_<fecha>.csv y no entran en G1 ni en G2.

- G1: ≥ 3 de los 4 departamentos con dato (valor ≥ 1; "<1" y 0 no cuentan) en ≥ 50 % de las semanas completas.
- G2: dos exportaciones de la misma consulta en días distintos tienen ρ de Spearman ≥ 0,8 en cada departamento. Si un
  departamento no llega, su serie es el promedio de las dos exportaciones en las semanas comunes (regla fijada antes).

Se niega a cargar una exportación cuya región o cuyas fechas no coinciden con el nombre del archivo.

Uso: python -m radar.trends.cargar
"""

import csv
import datetime as dt
import io
import logging
import re
import sys

from radar import config
from radar.comun.archivos import escribir_csv, leer_csv
from radar.comun.registro import configurar
from radar.comun.texto import ahora, clave
from radar.noticias.viabilidad import criterio, reporte

log = logging.getLogger(__name__)

PRUEBA = "Trends: viabilidad"
INFO = "Trends (informativo)"
DEPARTAMENTOS_MINIMOS = 3  # G1
SEMANAS_CON_DATO = 0.50  # G1
RHO_MINIMO = 0.80  # G2
ENCABEZADOS_FECHA = {"week", "semana", "time", "tiempo", "dia", "day"}
NOMBRE = re.compile(r"^([a-z-]+?)(-contexto)?_(\d{4}-\d{2}-\d{2})\.csv$")
REGION_EN_COLUMNA = re.compile(r"\(([^()]+)\)\s*$")
COLUMNAS_INTERES = ("departamento", "semana", "valor", "menor_que_1", "exportacion")
COLUMNAS_VALIDACION = ("prueba", "criterio", "valor", "umbral", "pasa", "detalle")


class ExportacionInvalida(ValueError):
    pass


def leer_exportacion(texto, departamento):
    """[(inicio de semana, valor, menor_que_1)] de un CSV de Trends; comprueba la región del encabezado."""
    filas = list(csv.reader(io.StringIO(texto.lstrip("﻿"))))
    try:
        i = next(n for n, f in enumerate(filas) if f and clave(f[0]) in ENCABEZADOS_FECHA)
    except StopIteration:
        raise ExportacionInvalida("no tiene la fila de encabezado (Semana/Week)") from None
    encabezado = filas[i]
    if len(encabezado) < 2:
        raise ExportacionInvalida("no tiene columna de interés")
    region = REGION_EN_COLUMNA.search(encabezado[1])
    if region and clave(region.group(1)).replace(" ", "-") != departamento:
        raise ExportacionInvalida(f"la región del archivo es {region.group(1)!r}, no {departamento}")
    serie = []
    for f in filas[i + 1 :]:
        if len(f) < 2 or not f[0].strip():
            continue
        valor = f[1].strip()
        menor = valor.startswith("<")
        serie.append((dt.date.fromisoformat(f[0].strip()[:10]), 0.5 if menor else float(valor or 0), menor))
    if not serie:
        raise ExportacionInvalida("no tiene semanas")
    return serie


def semanas_completas(serie, exportado):
    """Semanas que terminan dentro del período y antes del día de la exportación (la última incompleta se descarta)."""
    limite = min(config.FIN_CORTE, exportado - dt.timedelta(days=1))
    return [s for s in serie if s[0] + dt.timedelta(days=6) >= config.INICIO and s[0] + dt.timedelta(days=6) <= limite]


def comprobar_fechas(serie):
    primera = serie[0][0]
    if not (config.INICIO - dt.timedelta(days=6) <= primera <= config.INICIO + dt.timedelta(days=6)):
        raise ExportacionInvalida(f"empieza el {primera}: la consulta debe ir del 1-ene-2026 al 20-nov-2026")
    if any(b[0] - a[0] != dt.timedelta(days=7) for a, b in zip(serie, serie[1:], strict=False)):
        raise ExportacionInvalida("no es semanal (¿período menor a 9 meses?)")


def rangos(valores):
    orden = sorted(range(len(valores)), key=lambda i: valores[i])
    r = [0.0] * len(valores)
    i = 0
    while i < len(orden):
        j = i
        while j + 1 < len(orden) and valores[orden[j + 1]] == valores[orden[i]]:
            j += 1
        for k in range(i, j + 1):
            r[orden[k]] = (i + j) / 2 + 1
        i = j + 1
    return r


def spearman(x, y):
    if len(x) < 3:
        return float("nan")
    rx, ry = rangos(x), rangos(y)
    mx, my = sum(rx) / len(rx), sum(ry) / len(ry)
    cov = sum((a - mx) * (b - my) for a, b in zip(rx, ry, strict=True))
    vx = sum((a - mx) ** 2 for a in rx) ** 0.5
    vy = sum((b - my) ** 2 for b in ry) ** 0.5
    return cov / (vx * vy) if vx and vy else float("nan")


def exportaciones(base=None):
    """{departamento: [(fecha de exportación, ruta)]} de las consultas principales, de la más antigua a la más nueva."""
    salida = {}
    base = base or config.DIR_RAW_TRENDS
    if not base.exists():
        return salida
    for r in sorted(base.iterdir()):
        m = NOMBRE.match(r.name)
        if not m or m.group(2):
            continue
        if m.group(1) not in config.DEPARTAMENTOS_TRENDS:
            log.warning(f"{r.name}: departamento desconocido (usa {', '.join(config.DEPARTAMENTOS_TRENDS)})")
            continue
        salida.setdefault(m.group(1), []).append((dt.date.fromisoformat(m.group(3)), r))
    return {d: sorted(v) for d, v in salida.items()}


def medir(series):
    """series: {departamento: [(fecha de exportación, semanas completas)]}."""
    filas, con_dato = [], 0
    for d in config.DEPARTAMENTOS_TRENDS:
        if d not in series:
            filas.append(criterio(INFO, f"semanas con dato en {d}", "sin exportación", f">= {SEMANAS_CON_DATO}", False))
            continue
        semanas = series[d][-1][1]
        proporcion = sum(v >= 1 and not menor for _, v, menor in semanas) / len(semanas) if semanas else 0.0
        con_dato += proporcion >= SEMANAS_CON_DATO
        filas.append(criterio(INFO, f"semanas con dato en {d}", round(proporcion, 3), f">= {SEMANAS_CON_DATO}",
                              proporcion >= SEMANAS_CON_DATO, f"{len(semanas)} semanas completas"))  # fmt: skip
    filas.append(criterio(PRUEBA, "G1 departamentos con dato en >= 50 % de las semanas", con_dato,
                          f">= {DEPARTAMENTOS_MINIMOS}", con_dato >= DEPARTAMENTOS_MINIMOS))  # fmt: skip
    r = rhos(series)
    if r:
        minimo = min(r.values())
        filas.append(criterio(PRUEBA, "G2 ρ de Spearman entre exportaciones (mínimo)", round(minimo, 3),
                              f">= {RHO_MINIMO}", len(r) == len(series) and minimo >= RHO_MINIMO,
                              str({d: round(x, 3) for d, x in r.items()})))  # fmt: skip
        promediados = sorted(d for d, x in r.items() if not x >= RHO_MINIMO)
        if promediados:
            filas.append(criterio(INFO, "G2 departamentos con las dos exportaciones promediadas", len(promediados),
                                  "-", True, ", ".join(promediados)))  # fmt: skip
    return filas


def _comunes(a, b):
    return sorted({s for s, *_ in a} & {s for s, *_ in b})


def rhos(series):
    """{departamento: ρ de Spearman entre la primera y la última exportación} de los que tienen dos o más."""
    salida = {}
    for d, v in series.items():
        if len({f for f, _ in v}) < 2:
            continue
        (_, a), (_, b) = v[0], v[-1]
        va, vb = {s: x for s, x, _ in a}, {s: x for s, x, _ in b}
        comunes = _comunes(a, b)
        salida[d] = spearman([va[s] for s in comunes], [vb[s] for s in comunes])
    return salida


def serie_final(v, rho):
    """[(semana, valor, menor_que_1, exportación)]: la última exportación, o el promedio de la primera y la última si
    G2 no llega en ese departamento."""
    fecha, ultima = v[-1]
    if rho is None or rho >= RHO_MINIMO:
        return [(s, x, m, fecha.isoformat()) for s, x, m in ultima]
    (f0, a), (f1, b) = v[0], v[-1]
    da, db = {s: (x, m) for s, x, m in a}, {s: (x, m) for s, x, m in b}
    etiqueta = f"promedio {f0.isoformat()} y {f1.isoformat()}"
    return [(s, (da[s][0] + db[s][0]) / 2, da[s][1] and db[s][1], etiqueta) for s in _comunes(a, b)]


def guardar(filas, ruta):
    corridas = {f["prueba"] for f in filas}
    previas = [f for f in leer_csv(ruta) if f["prueba"] not in corridas]
    escribir_csv(ruta, COLUMNAS_VALIDACION, previas + filas)


def main(argv=None):
    inicio = ahora()
    configurar("trends-cargar")
    series, alertas, interes = {}, [], []
    for d, lista in exportaciones().items():
        for fecha, ruta in lista:
            try:
                serie = leer_exportacion(ruta.read_text(encoding="utf-8"), d)
                comprobar_fechas(serie)
            except (ExportacionInvalida, ValueError) as e:
                alertas.append(f"{ruta.name}: no se carga ({e})")
                continue
            semanas = semanas_completas(serie, fecha)
            series.setdefault(d, []).append((fecha, semanas))
    if not series:
        log.error(f"No hay exportaciones válidas en {config.DIR_RAW_TRENDS} (<departamento>_<AAAA-MM-DD>.csv).")
        for a in alertas:
            log.error("- " + a)
        return 1
    r = rhos(series)
    for d, v in series.items():
        interes += [{"departamento": d, "semana": s, "valor": x, "menor_que_1": m, "exportacion": e}
                    for s, x, m, e in serie_final(v, r.get(d))]  # fmt: skip
    config.DIR_TRENDS.mkdir(parents=True, exist_ok=True)
    escribir_csv(config.DIR_TRENDS / "interes.csv", COLUMNAS_INTERES, interes)
    filas = medir(series)
    if not any(f["criterio"].startswith("G2") for f in filas):
        alertas.append("G2 se mide con la segunda exportación (en el corte).")
    guardar(filas, config.DIR_TRENDS / "validacion.csv")
    reporte(filas, alertas, inicio)
    return 0


if __name__ == "__main__":
    sys.exit(main())
