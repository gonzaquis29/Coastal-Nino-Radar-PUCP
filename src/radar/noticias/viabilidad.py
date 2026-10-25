"""Pruebas de viabilidad de noticias, con criterios fijados antes de correrlas (docs/noticias/definicion.md).

Uso: python -m radar.noticias.viabilidad filtro      # paso 1: pérdida del filtro en la recolección diaria
     python -m radar.noticias.viabilidad rpp         # cobertura del archivo de RPP (tras descubrir RPP)
     python -m radar.noticias.viabilidad resultados  # volumen, control positivo, calidad, pérdida histórica
                                                     # y control negativo (tras el histórico)
"""

import argparse
import collections
import datetime as dt
import logging
import random
import re
import sys
import threading

from radar import config
from radar.comun.archivos import EstadoDescargas, escribir_csv, leer_csv
from radar.comun.http import Cliente
from radar.comun.registro import configurar, describir
from radar.comun.texto import a_lima, ahora
from radar.comun.xml import NS_SITEMAP, leer_xml
from radar.noticias import esquemas, filtro, rasgos
from radar.noticias.historico import consolidar
from radar.noticias.medios import DETENER, MEDIOS, Rpp
from radar.noticias.nota import leer_html
from radar.recoleccion.urls import filas_de_notas

log = logging.getLogger(__name__)

# ---------------------------------------------------------------- umbrales (README, "Criterios de pasa / no pasa")
PERDIDA_MAXIMA = 0.20
COBERTURA_RPP_MINIMA = 0.95
VOLUMEN_MINIMO = 400
CONTROL_POSITIVO_MINIMO = 20
REFERENCIA_ETIQUETAS_MINIMA = 0.90  # parte de las notas que RPP etiqueta El Niño que la regla reconoce
MIN_ETIQUETADAS = 5  # con menos, la comparación con las etiquetas es solo informativa
CALIDAD_MINIMA = 0.95
CUERPO_RESUMEN_MINIMO = 0.40  # parte de las palabras del resumen que debe estar en el cuerpo extraído
CUERPO_LD_MINIMO = 0.90  # en RPP: parte del articleBody del JSON-LD presente en el cuerpo extraído
# ---------------------------------------------------------------- muestras
MUESTRA_SECCION = 300  # diaria: no candidatas por título en secciones de noticias (RPP, Exitosa)
MUESTRA_EXCLUIDA = 150  # diaria: no candidatas en secciones excluidas (RPP, Exitosa)
MUESTRA_RESTO = 400  # diaria: no candidatas de Andina y El Tiempo (no se separan por sección)
MUESTRA_HISTORICA_POR_MES = 15  # histórico: no candidatas por mes y medio
NEGATIVO_POR_MEDIO = 100
REPETICIONES_BOOTSTRAP = 2000
ETIQUETA_NINO = re.compile(
    r"(fen[oó]meno\s+(de\s+)?)?\b(el|del)\s+ni[ñn]o\b|ni[ñn]o\s+costero|enfen|la\s+ni[ñn]a\b", re.I
)
HOST_WAYBACK = "web.archive.org"


def etiqueta_nino(etiqueta):
    """La etiqueta editorial nombra el fenómeno (no 'Instituto Nacional de Salud del Niño')."""
    m = ETIQUETA_NINO.search(etiqueta)
    return bool(m) and not rasgos.NO_ES_EL_FENOMENO.search(etiqueta[: m.start()])


def criterio(prueba, nombre, valor, umbral, pasa, detalle=""):
    return {"prueba": prueba, "criterio": nombre, "valor": valor, "umbral": umbral, "pasa": pasa, "detalle": detalle}


def _azar(*partes):
    return random.Random("-".join(map(str, (config.SEMILLA_MUESTRAS, *partes))))


def _muestra(filas, n, *semilla):
    filas = sorted(filas, key=lambda f: f["id"])
    return filas if len(filas) <= n else _azar(*semilla).sample(filas, n)


def _si(valor):
    return valor in (True, "1", 1)


def notas_de(medio):
    return {n["id"]: n for n in leer_csv(config.DIR_RAW_NOTICIAS / medio / "notas.csv")}


# ---------------------------------------------------------------- estimación por estratos


class Estrato:
    """Un grupo de notas del que se leyó todo o una muestra: total del grupo e indicadores de la muestra."""

    def __init__(self, medio, nombre, total, indicadores, visto_por_filtro):
        self.medio, self.nombre, self.total = medio, nombre, total
        self.indicadores, self.visto = list(indicadores), visto_por_filtro

    def estimado(self, indicadores=None):
        indicadores = self.indicadores if indicadores is None else indicadores
        return self.total * sum(indicadores) / len(indicadores) if indicadores else 0.0


def perdida(estratos, perdidos, remuestras=None):
    """Parte estimada de las notas sobre El Niño que quedan en los estratos 'perdidos'."""
    total = perdida_ = 0.0
    for e in estratos:
        valor = e.estimado(remuestras.get(id(e)) if remuestras else None)
        total += valor
        perdida_ += valor if e.nombre in perdidos.get(e.medio, set()) else 0
    return perdida_ / total if total else 0.0


def intervalo(estratos, perdidos, medio=None):
    """Intervalo bootstrap al 95 % (se remuestrea dentro de cada estrato)."""
    azar, valores = _azar("bootstrap", medio or "todos"), []
    usados = [e for e in estratos if medio in (None, e.medio)]
    for _ in range(REPETICIONES_BOOTSTRAP):
        remuestras = {id(e): azar.choices(e.indicadores, k=len(e.indicadores)) for e in usados if e.indicadores}
        valores.append(perdida(usados, perdidos, remuestras))
    valores.sort()
    return valores[int(0.025 * len(valores))], valores[int(0.975 * len(valores)) - 1]


def _texto_perdida(estratos, perdidos, medio=None):
    usados = [e for e in estratos if medio in (None, e.medio)]
    bajo, alto = intervalo(estratos, perdidos, medio)
    partes = [f"{e.medio}/{e.nombre}: {sum(e.indicadores)}/{len(e.indicadores)} de {e.total}" for e in usados]
    return f"IC95 {bajo:.2f}-{alto:.2f}; " + "; ".join(partes)


# ---------------------------------------------------------------- paso 1: filtro en la recolección diaria


def _estratos_diarios(nombre):
    """Notas de data/urls/ de un medio, separadas como las ve el histórico."""
    medio = MEDIOS[nombre](cliente=None)
    universo = [
        f
        for f in filas_de_notas(nombre)
        if medio.id_de_diaria(f) and not (nombre == "andina" and filtro.es_ingles(f["url"]))
    ]
    grupos = collections.defaultdict(list)
    for f in universo:
        if filtro.terminos_en(f["url"]):
            grupos["titulo"].append(f)
        elif nombre in ("rpp", "exitosa"):
            excluida = (nombre, filtro.seccion_principal(f["url"])) in filtro.secciones_excluidas()
            grupos["excluida" if excluida else "seccion"].append(f)
        else:
            grupos["resto"].append(f)
    return grupos


TAMANO_MUESTRA = {"titulo": None, "seccion": MUESTRA_SECCION, "excluida": MUESTRA_EXCLUIDA, "resto": MUESTRA_RESTO}


def _perdidos_con_candidatas():
    """Estratos que el histórico no descarga con la configuración actual (config.CANDIDATAS)."""
    return {
        "andina": {"resto"} if config.CANDIDATAS["andina"] == "titulo" else set(),
        "rpp": {"excluida"},
        "exitosa": {"excluida"},
        "eltiempo": {"resto"} if config.CANDIDATAS["eltiempo"] == "titulo" else set(),
    }


def prueba_filtro(parar):
    estratos, etiquetadas, alertas = [], [], []
    for nombre in MEDIOS:
        grupos = _estratos_diarios(nombre)
        medio = MEDIOS[nombre](Cliente(hosts_permitidos={config.HOSTS_MEDIOS[nombre]}), parar)
        medio.agregar_diaria()
        with EstadoDescargas(medio.dir / "estado.json") as estado:
            for grupo, filas in grupos.items():
                muestra = (
                    filas if TAMANO_MUESTRA[grupo] is None else _muestra(filas, TAMANO_MUESTRA[grupo], nombre, grupo)
                )
                try:
                    medio.procesar([medio.lista[f["id"]] for f in muestra], f"diaria_{grupo}", estado)
                except DETENER as e:
                    alertas.append(f"{nombre}: {describir(e)}")
        notas = notas_de(nombre)
        for grupo, filas in grupos.items():
            leidas = [notas[f["id"]] for f in filas if f["id"] in notas]
            estratos.append(
                Estrato(nombre, grupo, len(filas), [_si(n["nino_en_inicio"]) for n in leidas], grupo == "titulo")
            )
            if nombre == "rpp":
                etiquetadas += [n for n in leidas if any(etiqueta_nino(t) for t in n["etiquetas"].split("|"))]
    solo_titulo = {e.medio: set() for e in estratos}
    for e in estratos:
        if not e.visto:
            solo_titulo[e.medio].add(e.nombre)
    con_candidatas = _perdidos_con_candidatas()
    prueba = "Filtro por título"
    filas = [
        criterio(
            prueba,
            "pérdida con solo el título (4 medios)",
            round(perdida(estratos, solo_titulo), 3),
            f"≤ {PERDIDA_MAXIMA}",
            perdida(estratos, solo_titulo) <= PERDIDA_MAXIMA,
            _texto_perdida(estratos, solo_titulo),
        ),
        criterio(
            prueba,
            "pérdida con las candidatas de config.CANDIDATAS (4 medios)",
            round(perdida(estratos, con_candidatas), 3),
            f"≤ {PERDIDA_MAXIMA}",
            perdida(estratos, con_candidatas) <= PERDIDA_MAXIMA,
            _texto_perdida(estratos, con_candidatas),
        ),
    ]
    reconocidas = sum(_si(n["nino_en_inicio"]) for n in etiquetadas)
    cobertura = reconocidas / len(etiquetadas) if etiquetadas else 0.0
    filas.append(
        criterio(
            prueba if len(etiquetadas) >= MIN_ETIQUETADAS else prueba + " (informativo)",
            "la regla 'sobre El Niño' reconoce las notas que RPP etiqueta El Niño",
            round(cobertura, 3),
            f"≥ {REFERENCIA_ETIQUETAS_MINIMA}",
            cobertura >= REFERENCIA_ETIQUETAS_MINIMA,
            f"{reconocidas} de {len(etiquetadas)} etiquetadas",
        )
    )
    for nombre in MEDIOS:
        valor = perdida([e for e in estratos if e.medio == nombre], solo_titulo)
        filas.append(
            criterio(
                prueba + " (informativo por medio)",
                f"{nombre}: pérdida con solo el título",
                round(valor, 3),
                f"≤ {PERDIDA_MAXIMA}",
                valor <= PERDIDA_MAXIMA,
                _texto_perdida(estratos, solo_titulo, nombre),
            )
        )
    return filas, alertas


# ---------------------------------------------------------------- cobertura del archivo de RPP


def _copias_wayback(cliente):
    r = cliente.get(
        f"https://{HOST_WAYBACK}/cdx/search/cdx",
        params={"url": "rpp.pe/sitemap/news", "from": config.INICIO.year, "output": "json", "filter": "statuscode:200"},
    )
    return [fila[1] for fila in r.json()[1:]]


def _referencias_wayback(cliente, alertas):
    """Notas de las copias de 2026 del sitemap de noticias de RPP; una copia que falla se salta y se avisa."""
    refs = {}
    for copia in _copias_wayback(cliente):
        try:
            raiz = leer_xml(cliente.get(f"https://{HOST_WAYBACK}/web/{copia}id_/https://rpp.pe/sitemap/news").content)
        except Exception as e:
            alertas.append(f"copia {copia} de Wayback no leída: {describir(e)}")
            continue
        for u in raiz.findall("s:url", NS_SITEMAP):
            url = (u.findtext("s:loc", namespaces=NS_SITEMAP) or "").strip()
            fecha = a_lima((u.findtext("n:news/n:publication_date", namespaces=NS_SITEMAP) or "").strip())
            if Rpp.ident(url) and config.INICIO.isoformat() <= fecha[:10] <= config.FIN_HISTORICO.isoformat():
                refs.setdefault(Rpp.ident(url), (url, fecha))
    return refs


def _referencias_diarias():
    return {
        f["id"]: (f["url"], f["fecha"])
        for f in filas_de_notas("rpp")
        if f["tipo_fecha"] == "publicacion" and f["fecha"][:10] <= config.FIN_HISTORICO.isoformat()
    }


def prueba_rpp(parar):
    """El archivo de cada día se vuelve a leer aquí: la lista guarda una fila por nota, así que una nota que llegó
    antes por la recolección diaria no queda registrada como vista en el archivo."""
    rpp = Rpp(Cliente(hosts_permitidos={config.HOSTS_MEDIOS["rpp"]}), parar)
    por_dia = {}

    def ids_del_dia(dia):
        if dia not in por_dia:
            try:
                por_dia[dia] = {f["id"] for f in rpp.archivo(dia)}
            except DETENER:
                raise
            except Exception as e:
                log.debug("rpp archivo %s: %s", dia, describir(e))
                por_dia[dia] = None
        return por_dia[dia]

    def en_archivo(ident, fecha):
        dia = dt.date.fromisoformat(fecha[:10])
        cercanos = [dia + dt.timedelta(days=d) for d in (0, -1, 1)]
        conjuntos = [ids_del_dia(c) for c in cercanos if config.INICIO <= c <= config.FIN_HISTORICO]
        if not conjuntos or None in conjuntos:
            return None  # fuera del histórico o el archivo no respondió
        return any(ident in c for c in conjuntos)

    alertas = []
    referencias = {
        "Wayback (sitemap de noticias)": _referencias_wayback(Cliente(), alertas),
        "recolección diaria": _referencias_diarias(),
    }
    filas = []
    for fuente, refs in referencias.items():
        conteo, por_seccion, vivas = collections.Counter(), collections.defaultdict(collections.Counter), 0
        for ident, (url, fecha) in refs.items():
            if ident.startswith("live-"):
                vivas += 1
                continue
            hallada = en_archivo(ident, fecha)
            if hallada is False:  # la fecha del sitemap puede ser la de una re-publicación: manda datePublished
                try:
                    r = rpp.cliente.get(url)
                    publicada = leer_html("rpp", r.content, r.url, r.headers.get("Content-Type", ""))[
                        "fecha_publicacion"
                    ]
                    hallada = (
                        en_archivo(ident, publicada) if publicada[:10] <= config.FIN_HISTORICO.isoformat() else None
                    )
                except Exception as e:
                    log.debug("rpp %s: %s", url, describir(e))
            if hallada is None:
                conteo["sin_dia"] += 1
                continue
            seccion = filtro.seccion_principal(url)
            conteo["total"] += 1
            por_seccion[seccion]["total"] += 1
            if hallada:
                conteo["en_archivo"] += 1
                por_seccion[seccion]["en_archivo"] += 1
        valor = conteo["en_archivo"] / conteo["total"] if conteo["total"] else 0.0
        secciones = ", ".join(
            f"{s} {c['en_archivo']}/{c['total']}" for s, c in sorted(por_seccion.items(), key=lambda x: -x[1]["total"])
        )
        filas.append(
            criterio(
                "Cobertura del archivo de RPP",
                f"notas de {fuente} en el archivo (±1 día de su datePublished)",
                round(valor, 4),
                f"≥ {COBERTURA_RPP_MINIMA}",
                valor >= COBERTURA_RPP_MINIMA and conteo["total"] > 0,
                f"{conteo['en_archivo']}/{conteo['total']}; live aparte: {vivas}; sin archivo: "
                f"{conteo['sin_dia']}; {secciones}",
            )
        )
    return filas, alertas


# ---------------------------------------------------------------- resultados del histórico


def _en_historico(n):
    return n["fecha_publicacion"][:10] <= config.FIN_HISTORICO.isoformat()


def prueba_volumen(notas):
    sobre = [n for n in notas if _en_historico(n) and _si(n["sobre_nino"])]
    por_medio = collections.Counter(n["medio"] for n in sobre)
    por_mes = collections.Counter(n["fecha_publicacion"][:7] for n in sobre)
    return [
        criterio(
            "Volumen de noticias",
            "notas sobre El Niño del 1-ene al 24-oct (4 medios)",
            len(sobre),
            f"≥ {VOLUMEN_MINIMO}",
            len(sobre) >= VOLUMEN_MINIMO,
            "; ".join(f"{m} {c}" for m, c in sorted(por_medio.items()))
            + " | "
            + ", ".join(f"{m} {c}" for m, c in sorted(por_mes.items())),
        )
    ]


def prueba_control_positivo(notas):
    andina = [n for n in notas if n["medio"] == "andina" and _en_historico(n)]
    filas, acumulado = [], set()
    nombres = {
        "enlace": "enlazan el PDF de un comunicado (README)",
        "numero": "… o citan su número en el texto (respaldo del README)",
        "proximo": "… o anuncian la fecha del próximo comunicado (extensión aprobada)",
        "informe": "… o enlazan el informe técnico de su fecha (extensión aprobada)",
    }
    for nivel in rasgos.NIVELES_COMUNICADO:
        acumulado |= {n["id"] for n in andina if any(c.endswith(":" + nivel) for c in n["comunicados"].split("|"))}
        comunicados = {
            c.split(":")[0] for n in andina if n["id"] in acumulado for c in n["comunicados"].split("|") if c
        }
        filas.append(
            criterio(
                "Control positivo" if nivel == "enlace" else "Control positivo (respaldos)",
                f"notas de Andina que {nombres[nivel]}",
                len(acumulado),
                f"≥ {CONTROL_POSITIVO_MINIMO}",
                len(acumulado) >= CONTROL_POSITIVO_MINIMO,
                f"{len(comunicados)} comunicados distintos",
            )
        )
    return filas


def prueba_calidad(notas):
    candidatas = [n for n in notas if n["muestra"] == "candidata"]
    claves = [(n["medio"], n["id"]) for n in notas]
    con_texto = [n for n in candidatas if not _si(n["sin_texto"])]
    buenas = [
        n for n in con_texto if n["resumen_en_cuerpo"] == "" or float(n["resumen_en_cuerpo"]) >= CUERPO_RESUMEN_MINIMO
    ]
    rpp = [n for n in con_texto if n["medio"] == "rpp" and n["cuerpo_vs_ld"]]
    rpp_bien = [n for n in rpp if float(n["cuerpo_vs_ld"]) >= CUERPO_LD_MINIMO]
    completas = [n for n in candidatas if n["titular"] and n["fecha_publicacion"]]

    def proporcion(parte, todo):
        return round(len(parte) / len(todo), 4) if todo else 0.0

    prueba = "Calidad de las notas"
    return [
        criterio(
            prueba,
            "candidatas con titular y datePublished",
            proporcion(completas, candidatas),
            "= 1",
            len(completas) == len(candidatas) > 0,
        ),
        criterio(
            prueba,
            "notas duplicadas (medio, id)",
            len(claves) - len(set(claves)),
            "= 0",
            len(claves) == len(set(claves)),
        ),
        criterio(
            prueba,
            f"cuerpo con ≥ {CUERPO_RESUMEN_MINIMO} de las palabras del resumen",
            proporcion(buenas, con_texto),
            f"≥ {CALIDAD_MINIMA}",
            proporcion(buenas, con_texto) >= CALIDAD_MINIMA,
            f"sin texto (galerías, videos): {len(candidatas) - len(con_texto)} de {len(candidatas)}",
        ),
        criterio(
            prueba,
            f"RPP: cuerpo con ≥ {CUERPO_LD_MINIMO} del articleBody",
            proporcion(rpp_bien, rpp),
            f"≥ {CALIDAD_MINIMA}",
            proporcion(rpp_bien, rpp) >= CALIDAD_MINIMA,
            f"{len(rpp_bien)}/{len(rpp)}",
        ),
    ]


def _mes_de_lista(fila):
    """Mes de una fila descubierta (archivo de RPP, sitemap de Exitosa); Andina se agrupa por número."""
    via = fila["via"]
    if via.startswith("archivo:"):
        return via[8:15]
    if via.startswith("sitemap:"):
        return f"{via[8:12]}-{via[12:14]}"
    return ""


def prueba_perdida_historica(parar):
    """Muestra mensual de las notas que el histórico no descarga, para estimar lo que se pierde de enero a octubre."""
    estratos, alertas = [], []
    perdidos = collections.defaultdict(set)
    for nombre in MEDIOS:
        medio = MEDIOS[nombre](Cliente(hosts_permitidos={config.HOSTS_MEDIOS[nombre]}), parar)
        historicas = [f for f in medio.notas() if f["via"] != "diaria"]
        if not historicas:
            continue
        no_descargadas = [f for f in historicas if not filtro.candidata_por(nombre, f["url"], f["titulo"])]
        no_descargadas = [f for f in no_descargadas if not (nombre == "andina" and filtro.es_ingles(f["url"]))]
        grupos = collections.defaultdict(list)
        if nombre == "andina":
            numeros = sorted(int(f["id"]) for f in no_descargadas) or [0]
            ancho = max(1, (numeros[-1] - numeros[0]) // 10 + 1)
            for f in no_descargadas:
                grupos[f"tramo {(int(f['id']) - numeros[0]) // ancho + 1:02d}"].append(f)
        else:
            for f in no_descargadas:
                grupos[_mes_de_lista(f)].append(f)
        with EstadoDescargas(medio.dir / "estado.json") as estado:
            for grupo, filas in grupos.items():
                try:
                    medio.procesar(_muestra(filas, MUESTRA_HISTORICA_POR_MES, nombre, grupo), "historica", estado)
                except DETENER as e:
                    alertas.append(f"{nombre}: {describir(e)}")
        notas = notas_de(nombre)
        vistas = [n for n in notas.values() if n["muestra"] == "candidata" and _si(n["nino_en_inicio"])]
        estratos.append(Estrato(nombre, "descargadas", len(vistas), [True] * len(vistas), True))
        for grupo, filas in grupos.items():
            leidas = [notas[f["id"]] for f in filas if f["id"] in notas]
            estratos.append(Estrato(nombre, grupo, len(filas), [_si(n["nino_en_inicio"]) for n in leidas], False))
            perdidos[nombre].add(grupo)
    valor = perdida(estratos, perdidos)
    return [
        criterio(
            "Filtro por título (histórico)",
            "pérdida estimada de enero a octubre con las candidatas del histórico",
            round(valor, 3),
            f"≤ {PERDIDA_MAXIMA}",
            valor <= PERDIDA_MAXIMA,
            _texto_perdida(estratos, perdidos),
        )
    ], alertas


def control_negativo(notas):
    """Notas de otros temas de los mismos medios: ni mencionan El Niño ni tienen términos del filtro; aparte, un
    estrato 'cercano' (lluvias, calor… sin El Niño), que se reporta solo como informativo."""
    salida = []
    for nombre in MEDIOS:
        propias = [n for n in notas if n["medio"] == nombre and _en_historico(n) and not _si(n["sin_texto"])]
        propias = [n for n in propias if not _si(n["menciona_nino"])]
        for estrato, elegibles in (
            ("otros_temas", [n for n in propias if not n["terminos_cuerpo"]]),
            ("cercano", [n for n in propias if n["terminos_cuerpo"]]),
        ):
            por_mes = collections.defaultdict(list)
            for n in elegibles:
                por_mes[n["fecha_publicacion"][:7]].append(n)
            cupo = max(1, NEGATIVO_POR_MEDIO // max(1, len(por_mes)))
            elegidas = [
                m for mes, grupo in sorted(por_mes.items()) for m in _muestra(grupo, cupo, nombre, estrato, mes)
            ]
            salida += [
                {"medio": nombre, "id": n["id"], "url": n["url"], "mes": n["fecha_publicacion"][:7], "estrato": estrato}
                for n in elegidas[:NEGATIVO_POR_MEDIO]
            ]
    escribir_csv(config.DIR_NOTICIAS / "control_negativo.csv", esquemas.CONTROL_NEGATIVO, salida)
    conteo = collections.Counter((f["medio"], f["estrato"]) for f in salida)
    return [
        criterio(
            "Control negativo (informativo)",
            "notas de otros temas por medio",
            sum(v for (m, e), v in conteo.items() if e == "otros_temas"),
            "",
            True,
            "; ".join(f"{m}/{e} {v}" for (m, e), v in sorted(conteo.items())),
        )
    ]


# ---------------------------------------------------------------- principal


def guardar(filas):
    """Reemplaza en validacion.csv solo las pruebas que se volvieron a correr."""
    ruta = config.DIR_NOTICIAS / "validacion.csv"
    corridas = {f["prueba"] for f in filas}
    previas = [f for f in leer_csv(ruta) if f["prueba"] not in corridas]
    escribir_csv(ruta, esquemas.ARCHIVOS["validacion.csv"], previas + filas)


def reporte(filas, alertas, inicio):
    for prueba in dict.fromkeys(f["prueba"] for f in filas):
        grupo = [f for f in filas if f["prueba"] == prueba]
        informativo = "informativo" in prueba or "respaldos" in prueba
        log.info(f"\n{prueba} {'' if informativo else ('PASA' if all(f['pasa'] for f in grupo) else 'NO PASA')}")
        for f in grupo:
            marca = "·" if informativo else ("ok" if f["pasa"] else "NO")
            log.info(f"  [{marca:2}] {f['criterio']}: {f['valor']} (umbral {f['umbral']})")
            if f["detalle"]:
                log.info(f"       {f['detalle'][:400]}")
    log.info("\n" + ("\n".join("- " + a for a in alertas) if alertas else "Sin alertas."))
    log.info(f"Duración: {(ahora() - inicio).total_seconds() / 60:.1f} min")


def main(argv=None):
    ap = argparse.ArgumentParser(description="Pruebas de viabilidad de noticias.")
    ap.add_argument("prueba", choices=("filtro", "rpp", "resultados"))
    args = ap.parse_args(argv)
    registro = configurar(f"noticias-viabilidad-{args.prueba}")
    inicio, parar = ahora(), threading.Event()
    if args.prueba == "filtro":
        filas, alertas = prueba_filtro(parar)
    elif args.prueba == "rpp":
        filas, alertas = prueba_rpp(parar)
    else:
        filas, alertas = prueba_perdida_historica(parar)
        notas = consolidar()
        filas = prueba_volumen(notas) + prueba_control_positivo(notas) + prueba_calidad(notas) + filas
        filas += control_negativo(notas)
    guardar(filas)
    reporte(filas, alertas, inicio)
    escrito = (config.DIR_NOTICIAS / "validacion.csv").relative_to(config.RAIZ)
    log.info(f"Escrito: {escrito} · registro: {registro.relative_to(config.RAIZ)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
