"""Analítica web (docs/analitica/web.md, aprobada el 22-nov): engagement frente a la cercanía, Trends alrededor de cada
comunicado, indicadores de los medios y registro de uso, con los criterios W1 a W11.

    python -m radar.analitica.web engagement|trends|medios|uso|todo
"""

import argparse
import collections
import copy
import datetime as dt
import functools
import logging
import math
import statistics
import sys

import numpy as np

from radar import config
from radar.analitica import indicadores as ind
from radar.app import eventos as registro_uso
from radar.comun.archivos import escribir_csv, leer_csv, leer_json
from radar.comun.registro import configurar
from radar.comun.texto import ahora
from radar.modelos import rasgos as rg
from radar.noticias import esquemas
from radar.noticias.viabilidad import criterio, reporte
from radar.youtube import almacen

log = logging.getLogger(__name__)

PRUEBA = "Analítica web"
RESPUESTAS = "Analítica web: respuestas (informativo)"
INFO = "Analítica web (informativo)"
SEMILLA = config.SEMILLA_MUESTRAS
REPLICAS = 1000
SUSTITUTAS = 1000
ALFA = 0.05

TIPOS_A = ("medio", "otros")  # W2: los oficiales quedan fuera, como en M1
VIDEOS_POR_CANAL = 3
CANALES_MINIMOS, VIDEOS_MINIMOS = 30, 300  # W1
DURACION_SHORT = 180  # segundos
TIPO_VARIABLES = "engagement-variables"
TIPO_PUNTOS = "analitica-puntos"
NO_COINCIDE = ("rojo", "amarillo")

DEPARTAMENTOS_MINIMOS = 3  # W6 (= G1)
SEMANAS_ANTES = 3

VENTANA_REACCION = 14  # días
COMUNICADOS_MINIMOS = 5
CITAS_PREVIAS_MAXIMAS = 0.02  # W9
TIPOS_CITA = frozenset({"informe", "enlace", "numero"})
SECCIONES_PRINCIPALES = 5

COLUMNAS = ("parte", "indicador", "grupo", "valor", "ic_inf", "ic_sup", "n")
COLUMNAS_PUNTOS = ("tipo", "mes", "coseno", "objetivo", "tasa")
COLUMNAS_PROHIBIDAS = frozenset({"id", "canal", "titulo", "autor", "seudonimo", "sesion", "url", "titular"})


def ruta(nombre):
    return config.DIR_ANALITICA / f"web-{nombre}.csv"


def _celda(valor):
    if isinstance(valor, float | np.floating):
        return "" if math.isnan(valor) else round(float(valor), 4)
    return valor


def fila(parte, indicador, grupo="", valor="", ic=(math.nan, math.nan), n=""):
    return {
        "parte": parte,
        "indicador": indicador,
        "grupo": grupo,
        "valor": _celda(valor),
        "ic_inf": _celda(ic[0]),
        "ic_sup": _celda(ic[1]),
        "n": n,
    }


def _num(valor):
    return float(valor) if str(valor).strip() != "" else math.nan


# ---------------------------------------------------------------- A. engagement


def cargar_variables():
    almacen.comprobar_vigencia(bases=(config.DIR_YOUTUBE,))
    previos = almacen.archivos(TIPO_VARIABLES, bases=(config.DIR_YOUTUBE,))
    if not previos:
        raise FileNotFoundError("no hay variables del modelo: python -m radar.modelos.engagement variables")
    eleccion = leer_json(config.DIR_MODELOS / "engagement-eleccion.json")
    if not eleccion:
        raise FileNotFoundError("falta el prior del modelo: python -m radar.modelos.engagement entrenar")
    return almacen.fecha_de(previos[-1]), leer_csv(previos[-1]), eleccion["alfa"], eleccion["beta"]


def videos_por_fecha():
    """Ids de los videos que salieron en alguna búsqueda ordenada por fecha."""
    return {v for b in almacen.leer("busquedas") if b.get("orden") == "date" for v in b.get("videos", ())}


class Muestra:
    """Columnas de los videos con cercanía, como arreglos."""

    def __init__(self, filas, alfa, beta):
        self.filas = filas
        exitos = np.array([_num(f["likes"]) + _num(f["comentarios"]) for f in filas])
        vistas = np.array([_num(f["vistas"]) for f in filas])
        self.objetivo = rg.objetivo(exitos, vistas, alfa, beta)
        self.tasa = exitos / vistas
        self.coseno = np.array([_num(f["coseno"]) for f in filas])
        self.canal = np.array([f["canal"] for f in filas])
        self.tipo = np.array([f["tipo"] for f in filas])
        self.mes = np.array([f["fecha"][:7] for f in filas])
        self.short = np.array([_num(f["duracion"]) <= DURACION_SHORT for f in filas], dtype=float)
        self.palabras = np.log1p(np.array([_num(f["palabras_texto"]) for f in filas]))

    def parte(self, mascara):
        sub = copy.copy(self)
        sub.filas = [f for f, m in zip(self.filas, mascara, strict=True) if m]
        for k in ("objetivo", "tasa", "coseno", "canal", "tipo", "mes", "short", "palabras"):
            setattr(sub, k, getattr(self, k)[mascara])
        return sub

    def dentro(self, quitar_mes=True, veces=0):
        """(ρ parcial dentro del canal, réplicas) con los canales de ≥ 3 videos de esta muestra."""
        m = ind.con_minimo_por_grupo(self.canal, VIDEOS_POR_CANAL)
        x, y = self.coseno[m], self.objetivo[m]
        if quitar_mes:
            celdas = np.char.add(np.char.add(self.tipo[m], "|"), self.mes[m])
            x, y = ind.restar_mediana(x, celdas), ind.restar_mediana(y, celdas)
        covariables = [self.short[m], self.palabras[m]]
        if not veces:
            return ind.correlacion_dentro(x, y, self.canal[m], covariables), []
        return ind.correlacion_dentro_ic(x, y, self.canal[m], covariables, veces, SEMILLA)


def bootstrap_por_canal(canales, estadistico):
    return [estadistico(i) for i in rg.remuestras_por_grupo(canales, REPLICAS, SEMILLA)]


def engagement():
    corte, variables, alfa, beta = cargar_variables()
    todos = Muestra([f for f in variables if f["coseno"] and _num(f["vistas"]) > 0], alfa, beta)
    puntos = sorted(
        (
            {"tipo": t, "mes": m, "coseno": round(c, 4), "objetivo": round(o, 4), "tasa": round(r, 6)}
            for t, m, c, o, r in zip(todos.tipo, todos.mes, todos.coseno, todos.objetivo, todos.tasa, strict=True)
        ),
        key=lambda p: (p["tipo"], p["mes"], p["coseno"]),
    )
    escribir_csv(config.DIR_YOUTUBE / f"{corte.isoformat()}_{TIPO_PUNTOS}.csv", COLUMNAS_PUNTOS, puntos)

    a = todos.parte(np.isin(todos.tipo, TIPOS_A))
    con_canal = ind.con_minimo_por_grupo(a.canal, VIDEOS_POR_CANAL)
    n_canales, n_videos = len(set(a.canal[con_canal])), int(con_canal.sum())
    w1 = n_canales >= CANALES_MINIMOS and n_videos >= VIDEOS_MINIMOS
    filas = [
        criterio(
            PRUEBA,
            "W1 canales de medios y otros con >= 3 videos con cercanía, y sus videos",
            f"{n_canales} / {n_videos}",
            f">= {CANALES_MINIMOS} / >= {VIDEOS_MINIMOS}",
            w1,
        )
    ]
    salida = []

    if w1:
        log.info(f"W2: bootstrap por canal ({REPLICAS} réplicas)")
        rho, replicas = a.dentro(veces=REPLICAS)
        ic = rg.intervalo(replicas)
        por_fecha = videos_por_fecha()
        signos = {
            "entrenamiento": a.parte(np.array([f["particion"] == "entrenamiento" for f in a.filas])).dentro()[0],
            "prueba": a.parte(np.array([f["particion"] == "prueba" for f in a.filas])).dentro()[0],
            "búsquedas por fecha": a.parte(np.array([f["id"] in por_fecha for f in a.filas])).dentro()[0],
        }
        decision = ind.respuesta(ic, list(signos.values()))
        sin_mes = a.dentro(quitar_mes=False)[0]
        detalle = "; ".join(f"{k} {v:+.3f}" for k, v in signos.items())
        filas += [
            criterio(
                RESPUESTAS,
                "W2 ρ parcial dentro del canal entre la cercanía y el engagement",
                round(rho, 3),
                "IC sin 0 y el mismo signo en los dos períodos y por fecha",
                decision != "no concluyente",
                f"IC 95 % por canal {ic[0]:.3f} a {ic[1]:.3f}; {detalle}; respuesta: {decision}",
            ),
            criterio(INFO, "W2 sin quitar el mes (informativo)", round(sin_mes, 3), "informativo", True),
        ]
        salida += [
            fila("A", "respuesta", "", decision, n=n_videos),
            fila("A", "rho_dentro_del_canal", "", rho, ic, n_videos),
            fila("A", "rho_sin_quitar_mes", "", sin_mes, n=n_videos),
        ]
        salida += [fila("A", "rho_dentro_del_canal", k, v) for k, v in signos.items()]

    rho_tipo = rg.spearman_por_tipo(a.coseno, a.objetivo, a.tipo)
    ic_tipo = rg.intervalo(
        bootstrap_por_canal(a.canal, lambda i: rg.spearman_por_tipo(a.coseno[i], a.objetivo[i], a.tipo[i]))
    )
    filas.append(
        criterio(
            INFO,
            "W3 Spearman dentro de medios y de otros, ponderado",
            round(rho_tipo, 3),
            "informativo",
            True,
            f"IC 95 % por canal {ic_tipo[0]:.3f} a {ic_tipo[1]:.3f}",
        )
    )
    salida.append(fila("A", "spearman_por_tipo", "", rho_tipo, ic_tipo, len(a.filas)))

    tercil = ind.terciles(todos.coseno)
    for k, nombre in enumerate(("baja", "media", "alta")):
        m = tercil == k
        for medida, valores in (("objetivo", todos.objetivo), ("tasa", todos.tasa)):
            ic = rg.intervalo(bootstrap_por_canal(todos.canal[m], lambda i, v=valores[m]: float(np.median(v[i]))))
            salida.append(
                fila("A", f"mediana_{medida}_por_tercil", nombre, float(np.median(valores[m])), ic, int(m.sum()))
            )
    medianas = {r["grupo"]: r["valor"] for r in salida if r["indicador"] == "mediana_tasa_por_tercil"}
    filas.append(
        criterio(
            INFO,
            "W4 mediana de la tasa por tercil de cercanía (baja / media / alta)",
            " / ".join(f"{medianas[g]:.4f}" for g in ("baja", "media", "alta")),
            "informativo",
            True,
            "mezcla canales y tipos: solo para leer la dispersión",
        )
    )

    colores = np.array([f["color_reglas"] for f in todos.filas])
    grupos = {"rojo o amarillo": np.isin(colores, NO_COINCIDE), "verde": colores == "verde"}
    for nombre, m in grupos.items():
        salida.append(
            fila(
                "A",
                "mediana_tasa_por_color",
                nombre,
                float(np.median(todos.tasa[m])) if m.any() else math.nan,
                n=int(m.sum()),
            )
        )
    filas.append(
        criterio(
            INFO,
            "W5 mediana de la tasa: rojo o amarillo / verde",
            " / ".join(f"{float(np.median(todos.tasa[m])):.4f} (n {int(m.sum())})" for m in grupos.values()),
            "informativo (n pequeño)",
            True,
        )
    )

    for tipo in sorted(set(todos.tipo)):
        for mes in sorted(set(todos.mes)):
            m = (todos.tipo == tipo) & (todos.mes == mes)
            if not m.any():
                continue
            sub = [f for f, x in zip(todos.filas, m, strict=True) if x]
            for kpi in ("vistas", "likes", "comentarios"):
                salida.append(
                    fila(
                        "KPI",
                        f"mediana_{kpi}",
                        f"{tipo}|{mes}",
                        statistics.median(_num(f[kpi]) for f in sub),
                        n=len(sub),
                    )
                )
            salida.append(fila("KPI", "mediana_tasa", f"{tipo}|{mes}", float(np.median(todos.tasa[m])), n=len(sub)))
    for tipo in sorted(set(todos.tipo)):
        m = todos.tipo == tipo
        salida.append(fila("KPI", "mediana_tasa", tipo, float(np.median(todos.tasa[m])), n=int(m.sum())))
    escribir_csv(ruta("engagement"), COLUMNAS, salida)
    return filas


# ---------------------------------------------------------------- B. Trends


@functools.cache
def notas_validas():
    """Las notas con fecha confiable (se leen una sola vez por corrida)."""
    return tuple(
        n for n in leer_csv(config.DIR_NOTICIAS / "notas.csv") if n["fecha_publicacion"] and n["fecha_dudosa"] != "1"
    )


def fechas_comunicados():
    """{id: fecha de emisión} de los comunicados oficiales del período."""
    salida = {}
    for c in leer_csv(config.DIR_OFICIAL / "comunicados.csv"):
        fecha = dt.date.fromisoformat(c["fecha_emision"]) if c["fecha_emision"] else None
        if c["tipo"] == "oficial" and fecha and config.INICIO <= fecha <= config.FIN_CORTE:
            salida[c["id"]] = fecha
    return salida


def niveles_nacionales():
    archivos = sorted((config.DIR_RAW_TRENDS / "nacional").glob("peru-regiones_*.csv"))
    if not archivos:
        return {}
    salida = {}
    for linea in archivos[-1].read_text(encoding="utf-8-sig").splitlines()[3:]:
        region, _, valor = linea.rpartition(",")
        if region and valor.strip().isdigit():
            salida[region.strip()] = int(valor)
    return salida


def trends():
    interes = collections.defaultdict(dict)
    for f in leer_csv(config.DIR_TRENDS / "interes.csv"):
        interes[f["departamento"]][dt.date.fromisoformat(f["semana"])] = float(f["valor"])
    if not interes:
        raise FileNotFoundError("no hay interés de Trends: python -m radar.trends.cargar")
    g1 = {
        f["criterio"].removeprefix("semanas con dato en "): f["pasa"] == "1"
        for f in leer_csv(config.DIR_TRENDS / "validacion.csv")
        if f["criterio"].startswith("semanas con dato en ")
    }
    entran = sorted(d for d in interes if g1.get(d))
    filas = [
        criterio(
            PRUEBA,
            "W6 departamentos que entran a B (G1)",
            len(entran),
            f">= {DEPARTAMENTOS_MINIMOS}",
            len(entran) >= DEPARTAMENTOS_MINIMOS,
            ", ".join(entran),
        )
    ]

    sobre = [n for n in notas_validas() if n["sobre_nino"] == "1"]
    por_semana = collections.Counter(ind.semana_de(n["fecha_publicacion"]) for n in sobre)
    nombres = {(n["medio"], n["id"]) for n in sobre}
    por_departamento = collections.defaultdict(collections.Counter)
    for r in leer_csv(config.DIR_NOTICIAS / "regiones.csv"):
        if (r["medio"], r["id"]) in nombres:
            for d in filter(None, r["departamentos"].split("|")):
                por_departamento[d.lower().replace(" ", "-")][(r["medio"], r["id"])] = 1
    semana_de_nota = {(n["medio"], n["id"]): ind.semana_de(n["fecha_publicacion"]) for n in sobre}
    comunicados = fechas_comunicados()
    salida = []

    for d in sorted(interes):
        valores = interes[d]
        resultados = [ind.sube_tras_comunicado(valores, f, SEMANAS_ANTES) for f in comunicados.values()]
        evaluados = [r for r in resultados if r is not None]
        salida.append(fila("B", "comunicados_en_que_sube", d, sum(evaluados), n=len(evaluados)))
        filas.append(
            criterio(
                INFO,
                f"W7 comunicados en que sube el interés en {d}",
                f"{sum(evaluados)} de {len(evaluados)}",
                "descriptivo",
                True,
            )
        )

    for k, d in enumerate(entran):
        semanas = sorted(interes[d])
        trends_niveles = np.array([interes[d][s] for s in semanas])
        notas_dif = ind.diferencias_log([por_semana.get(s, 0) for s in semanas])
        cruzada = ind.correlacion_cruzada(notas_dif, ind.diferencias_log(trends_niveles))
        observado = ind.maximo_absoluto(cruzada)
        nulo = ind.nulo_cruzado(notas_dif, trends_niveles, SUSTITUTAS, SEMILLA + k)
        umbral = float(np.quantile(nulo, 1 - ALFA / len(entran)))
        desfase = max(cruzada, key=lambda j: abs(cruzada[j]) if not math.isnan(cruzada[j]) else -1)
        propias = collections.Counter(semana_de_nota[c] for c in por_departamento.get(d, ()))
        cruzada_propia = ind.correlacion_cruzada(
            ind.diferencias_log([propias.get(s, 0) for s in semanas]), ind.diferencias_log(trends_niveles)
        )
        relacion = observado > umbral
        filas.append(
            criterio(
                RESPUESTAS,
                f"W8 máximo de |r| entre notas y Trends en {d}",
                round(observado, 3),
                f"> p{100 * (1 - ALFA / len(entran)):.1f} del nulo ({umbral:.3f})",
                relacion,
                f"desfase {desfase:+d} (r {cruzada[desfase]:+.3f}); "
                f"{'relación medible' if relacion else 'sin relación medible'}; con las notas que lo "
                f"nombran: {ind.maximo_absoluto(cruzada_propia):.3f} (informativo)",
            )
        )
        salida += [fila("B", "correlacion_cruzada", f"{d}|{j:+d}", r, n=len(notas_dif)) for j, r in cruzada.items()]
        salida += [
            fila("B", "maximo_abs", d, observado, n=len(notas_dif)),
            fila("B", "umbral_nulo", d, umbral, n=SUSTITUTAS),
            fila("B", "relacion", d, "relación medible" if relacion else "sin relación medible"),
            fila("B", "maximo_abs_notas_del_departamento", d, ind.maximo_absoluto(cruzada_propia)),
        ]

    for i, a in enumerate(entran):
        for b in entran[i + 1 :]:
            comunes = sorted(set(interes[a]) & set(interes[b]))
            r = rg.spearman([interes[a][s] for s in comunes], [interes[b][s] for s in comunes])
            salida.append(fila("B", "parecido_entre_departamentos", f"{a}|{b}", r, n=len(comunes)))
    salida += [fila("B", "nivel_nacional", region, valor) for region, valor in niveles_nacionales().items()]
    escribir_csv(ruta("trends"), COLUMNAS, salida)
    return filas


# ---------------------------------------------------------------- C. medios


def medios():
    notas = notas_validas()
    sobre = [n for n in notas if n["sobre_nino"] == "1"]
    salida = []
    volumen = collections.Counter((n["medio"], n["fecha_publicacion"][:7]) for n in sobre)
    salida += [fila("C", "notas_sobre_el_nino", f"{m}|{mes}", v) for (m, mes), v in sorted(volumen.items())]
    for medio in sorted({n["medio"] for n in sobre}):
        secciones = collections.Counter(n["seccion"] or "sin sección" for n in sobre if n["medio"] == medio)
        salida += [
            fila("C", "proporcion_seccion", f"{medio}|{s}", p, n=sum(secciones.values()))
            for s, p in ind.proporciones_principales(secciones, SECCIONES_PRINCIPALES)
        ]

    emision = fechas_comunicados()
    citas = collections.defaultdict(list)
    for n in notas:
        for cita in filter(None, n["comunicados"].split("|")):
            comunicado, _, tipo = cita.partition(":")
            if tipo in TIPOS_CITA and comunicado in emision:
                citas[(n["medio"], comunicado)].append(dt.date.fromisoformat(n["fecha_publicacion"][:10]))
    total = sum(len(v) for v in citas.values())
    previas = sum(ind.dias_de_reaccion(emision[c], f, VENTANA_REACCION)[2] for (_, c), f in citas.items())
    proporcion = previas / total if total else math.nan
    w9 = total > 0 and proporcion <= CITAS_PREVIAS_MAXIMAS
    filas = [
        criterio(
            PRUEBA,
            "W9 citas con fecha anterior a la emisión de su comunicado",
            round(proporcion, 4),
            f"<= {CITAS_PREVIAS_MAXIMAS}",
            w9,
            f"{previas} de {total} citas",
        )
    ]
    if w9:
        for medio in sorted({m for m, _ in citas}):
            propias = {c: f for (m, c), f in citas.items() if m == medio}
            if len(propias) < COMUNICADOS_MINIMOS:
                filas.append(
                    criterio(
                        INFO,
                        f"Reacción de {medio}",
                        "sin reportar",
                        f">= {COMUNICADOS_MINIMOS} comunicados",
                        True,
                        f"citó {len(propias)}",
                    )
                )
                continue
            reacciones = [ind.dias_de_reaccion(emision[c], f, VENTANA_REACCION) for c, f in propias.items()]
            dias = [r[0] for r in reacciones if r[0] is not None]
            solo_despues = sum(r[0] is None and r[1] for r in reacciones)
            mediana = statistics.median(dias) if dias else math.nan
            salida += [
                fila("C", "mediana_dias_de_reaccion", medio, mediana, n=len(dias)),
                fila("C", "comunicados_citados", medio, len(propias)),
                fila("C", "citados_solo_despues_de_14_dias", medio, solo_despues),
            ]
            filas.append(
                criterio(
                    INFO,
                    f"Reacción de {medio} (mediana de días)",
                    mediana,
                    "descriptivo",
                    True,
                    f"{len(dias)} comunicados citados en 14 días; {solo_despues} solo después; "
                    f"{len(propias)} citados",
                )
            )
    escribir_csv(ruta("medios"), COLUMNAS, salida)
    return filas


# ---------------------------------------------------------------- D. registro de uso


def registros_sinteticos():
    """(eventos, sesiones esperadas, embudo esperado, tiempos esperados) para W10."""

    def e(sesion, evento, anterior="", segundos=""):
        return {"sesion": sesion, "evento": evento, "anterior": anterior, "segundos": segundos}

    eventos = [
        e("completa", "vista"),
        e("completa", "verificar"),
        e("completa", "ver_por_que"),
        e("completa", "compartir"),
        e("completa", "vista", "verificar", 30),
        e("abandono", "vista"),
        e("abandono", "vista", "verificar", 10),
        e("mezcla-a", "vista"),
        e("mezcla-b", "vista"),
        e("mezcla-b", "compartir"),
        e("mezcla-a", "verificar"),
        e("mezcla-a", "clic_que_hacer"),
        e("mezcla-b", "verificar"),
    ]
    return eventos, 4, [4, 3, 2, 1], {"verificar": (20, 2)}


def resumen_uso(eventos):
    return (len(ind.por_sesion(eventos)), [n for _, n, _ in ind.embudo(eventos)], ind.tiempo_por_pantalla(eventos))


def uso():
    eventos, sesiones, pasos, tiempos = registros_sinteticos()
    obtenido = resumen_uso(eventos)
    w10 = obtenido == (sesiones, pasos, tiempos)
    filas = [
        criterio(
            PRUEBA,
            "W10 registro de uso con 3 registros sintéticos de resultado conocido",
            "sí" if w10 else "no",
            "100 %",
            w10,
            f"obtenido {obtenido}",
        )
    ]
    reales = registro_uso.leer()
    salida = [fila("D", "sesiones", "", len(ind.por_sesion(reales)))]
    salida += [fila("D", "embudo", paso, p, n=n) for paso, n, p in ind.embudo(reales)]
    salida += [fila("D", "segundos_por_pantalla", p, m, n=n) for p, (m, n) in ind.tiempo_por_pantalla(reales).items()]
    filas.append(
        criterio(
            INFO,
            "Uso real de la app",
            f"{salida[0]['valor']} sesiones",
            "descriptivo",
            True,
            "el uso real llega con la presentación (1-dic)",
        )
    )
    escribir_csv(ruta("uso"), COLUMNAS, salida)
    return filas


# ---------------------------------------------------------------- W11 y línea de comandos


def privacidad():
    archivos = [ruta(n) for n in ("engagement", "trends", "medios", "uso")]
    archivos += almacen.archivos(TIPO_PUNTOS, bases=(config.DIR_YOUTUBE,))[-1:]
    presentes = [r for r in archivos if r.exists()]
    malas = sorted(
        {f"{r.name}:{c}" for r in presentes for c in (leer_csv(r)[:1] or [{}])[0] if c in COLUMNAS_PROHIBIDAS}
    )
    return [
        criterio(
            PRUEBA,
            "W11 columnas con id, nombre, título o seudónimo en las salidas",
            len(malas),
            "0",
            not malas,
            ", ".join(malas) or f"{len(presentes)} archivos revisados",
        )
    ]


ETAPAS = {"engagement": engagement, "trends": trends, "medios": medios, "uso": uso}
UNA_SOLA_VEZ = {"engagement": "W2", "trends": "W8"}  # sección 5: si se repiten, se declara


def guardar_validacion(filas):
    """Reemplaza solo los criterios que se volvieron a calcular: correr una etapa no borra las demás."""
    nuevos = {f["criterio"] for f in filas}
    previas = (
        [f for f in leer_csv(ruta("validacion")) if f["criterio"] not in nuevos] if ruta("validacion").exists() else []
    )
    escribir_csv(ruta("validacion"), esquemas.ARCHIVOS["validacion.csv"], previas + filas)


def ya_corridas(etapas):
    hechos = {f["criterio"].split()[0] for f in leer_csv(ruta("validacion"))} if ruta("validacion").exists() else set()
    return [e for e in etapas if UNA_SOLA_VEZ.get(e) in hechos]


def main(argv=None):
    ap = argparse.ArgumentParser(description="Analítica web (docs/analitica/web.md).")
    ap.add_argument("etapa", choices=(*ETAPAS, "todo"))
    ap.add_argument("--repetir", action="store_true", help="vuelve a calcular W2 o W8 (se declara)")
    args = ap.parse_args(argv)
    inicio = ahora()
    configurar("analitica-web")
    config.DIR_ANALITICA.mkdir(parents=True, exist_ok=True)
    etapas = list(ETAPAS) if args.etapa == "todo" else [args.etapa]
    repetidas = ya_corridas(etapas)
    if repetidas and not args.repetir:
        log.error(f"{', '.join(repetidas)} ya se calcularon una vez; para repetirlas, --repetir (y se declara).")
        return 1
    filas, alertas = [], []
    for nombre in etapas:
        log.info(f"Etapa {nombre}")
        try:
            filas += ETAPAS[nombre]()
        except (FileNotFoundError, KeyError, ValueError, almacen.Vencido) as e:
            log.exception(f"{nombre}: no se completó")
            alertas.append(f"{nombre}: {e}")
    filas += privacidad()
    guardar_validacion(filas)
    reporte(filas, alertas, inicio)
    return 1 if alertas else 0


if __name__ == "__main__":
    sys.exit(main())
