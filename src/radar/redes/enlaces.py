"""Red de enlaces y citas de las notas sobre El Niño: quién enlaza o menciona a las fuentes oficiales y quién no
(pregunta 2 del README). Definición y criterios en docs/redes/enlaces.md. No pide páginas: usa notas.csv, enlaces.csv
y regiones.csv, y las menciones ya contadas en la columna actores.

Uso: python -m radar.redes.enlaces
"""

import argparse
import collections
import functools
import logging
import re
import sys
from urllib.parse import urlsplit

from radar import config
from radar.comun.archivos import escribir_csv, leer_csv
from radar.comun.registro import configurar
from radar.comun.texto import ahora
from radar.noticias.viabilidad import _si, criterio, guardar, reporte
from radar.redes import esquemas

log = logging.getLogger(__name__)

PRUEBA = "Red de enlaces y citas"
RESOLUCION_MINIMA = 0.95  # R1: enlaces oficiales de notas sobre El Niño atribuidos a una entidad
MENCION_MINIMA = 0.90  # R2: notas que enlazan a un actor y también lo mencionan
MIN_NOTAS_R2 = 10  # actores con menos notas que los enlacen no se evalúan
AMORTIGUAMIENTO = 0.85  # PageRank
# Tipos de arista
ENLACE_ACTOR, MENCION, ENLACE_OFICIAL, ENLACE_NOTA, ENLACE_EXTERNO = (
    "enlace_actor", "mencion", "enlace_oficial", "enlace_nota", "enlace_externo",
)  # fmt: skip
# Páginas de www.gob.pe sin institución: la raíz y las de servicio ("/113355-que-es-la-leptospirosis")
RUTA_GOB = re.compile(r"/(?:institucion/)?([a-z][a-z-]*)(?:/|$)")
ARCHIVO_CDN = re.compile(r"-([a-z]+)\.pdf$")  # ".../resolucion-ministerial-n-053-2026-minsa.pdf"


@functools.cache
def _patrones():
    return tuple((f["actor"], re.compile(f["patron"], re.I)) for f in leer_csv(config.ARCHIVO_INSTITUCIONES_WEB))


@functools.cache
def actores():
    """Actores en el orden de config/actores.csv."""
    return tuple(f["actor"] for f in leer_csv(config.ARCHIVO_ACTORES))


def entidad(url):
    """Actor de config/instituciones_web.csv, otra entidad oficial ('gob.pe:mef', 'bcrp'), '' si es oficial pero no se
    puede atribuir, o None si no es un sitio oficial."""
    partes = urlsplit(url)
    host, ruta = partes.netloc.lower(), partes.path.lower()
    for actor, patron in _patrones():
        if patron.search(host + ruta):
            return actor
    if not host.endswith("gob.pe"):
        return None
    if host in ("www.gob.pe", "gob.pe"):
        m = RUTA_GOB.match(ruta)
        return f"gob.pe:{m.group(1)}" if m else ""
    if host == "cdn.www.gob.pe":
        m = ARCHIVO_CDN.search(ruta)
        return f"gob.pe:{m.group(1)}" if m else ""
    return host.removesuffix(".gob.pe").split(".")[-1]


def _sin_www(host):
    return host.lower().removeprefix("www.")


@functools.cache
def _hosts_medios():
    return {_sin_www(h): medio for medio, h in config.HOSTS_MEDIOS.items()}


def medio_de_host(host):
    """Medio dueño del host, también en sus subdominios ('podcast.andina.pe')."""
    host = _sin_www(host)
    return next((m for h, m in _hosts_medios().items() if host == h or host.endswith("." + h)), None)


def clave_url(url):
    partes = urlsplit(url)
    return _sin_www(partes.netloc) + partes.path.rstrip("/")


def nodo_nota(medio, ident):
    return f"nota:{medio}:{ident}"


def mencionados(nota):
    """Actores de la columna actores ('ENFEN:3|SENAMHI:1')."""
    return {a.split(":")[0] for a in nota["actores"].split("|") if a}


# ---------------------------------------------------------------- red


def aristas(notas, enlaces, regiones):
    """Aristas desde las notas sobre El Niño, sin repetir (origen, destino, tipo), y conteos de lo que quedó fuera."""
    por_url = {clave_url(n["url"]): n for n in notas}
    sobre = {(n["medio"], n["id"]): n for n in notas if _si(n["sobre_nino"])}
    salida, vistas, fuera = [], set(), collections.Counter()

    def agregar(nota, destino, tipo):
        if (clave := (nodo_nota(nota["medio"], nota["id"]), destino, tipo)) not in vistas:
            vistas.add(clave)
            region = regiones.get((nota["medio"], nota["id"]), "")
            salida.append(
                dict(zip(esquemas.ARISTAS, (*clave, nota["medio"], nota["fecha_publicacion"][:7], region), strict=True))
            )

    for e in enlaces:
        if (nota := sobre.get((e["medio"], e["id"]))) is None:
            continue
        ent = entidad(e["url"])
        if ent in actores():
            agregar(nota, f"actor:{ent}", ENLACE_ACTOR)
        elif ent:
            agregar(nota, f"oficial:{ent}", ENLACE_OFICIAL)
        elif ent == "":
            fuera["oficial sin entidad"] += 1
        elif medio_de_host(urlsplit(e["url"]).netloc):
            destino = por_url.get(clave_url(e["url"]))
            if destino is None:
                fuera["interno sin nota (etiquetas, secciones, notas de antes de 2026)"] += 1
            elif (destino["medio"], destino["id"]) != (nota["medio"], nota["id"]):
                agregar(nota, nodo_nota(destino["medio"], destino["id"]), ENLACE_NOTA)
        else:
            agregar(nota, f"dominio:{_sin_www(urlsplit(e['url']).netloc)}", ENLACE_EXTERNO)
    for nota in sobre.values():
        for actor in sorted(mencionados(nota)):
            agregar(nota, f"actor:{actor}", MENCION)
    return salida, fuera


def clase(nodo):
    return nodo.split(":", 1)[0]


def nodos(filas_aristas):
    """Grados y PageRank en el grafo dirigido; enlace y mención al mismo actor cuentan como una sola arista."""
    import networkx as nx

    grafo = nx.DiGraph()
    medio = {}
    for a in filas_aristas:
        grafo.add_edge(a["origen"], a["destino"])
        medio[a["origen"]] = a["medio"]
    for n in grafo:
        if clase(n) == "nota":
            medio.setdefault(n, n.split(":")[1])
    rango = nx.pagerank(grafo, alpha=AMORTIGUAMIENTO)
    filas = [
        {
            "nodo": n,
            "clase": clase(n),
            "medio": medio.get(n, ""),
            "grado_entrada": grafo.in_degree(n),
            "grado_salida": grafo.out_degree(n),
            "pagerank": round(rango[n], 6),
        }  # fmt: skip
        for n in grafo
    ]
    return sorted(filas, key=lambda f: -f["pagerank"])


def citas(notas, filas_aristas, regiones):
    """Por grupo y actor: notas sobre El Niño que lo enlazan, lo mencionan o cualquiera de las dos."""
    tipos = collections.defaultdict(set)
    for a in filas_aristas:
        if a["tipo"] in (ENLACE_ACTOR, MENCION):
            tipos[(a["origen"], a["destino"].removeprefix("actor:"))].add(a["tipo"])
    grupos = collections.defaultdict(list)
    for n in notas:
        if _si(n["sobre_nino"]):
            nodo = nodo_nota(n["medio"], n["id"])
            region = regiones.get((n["medio"], n["id"]), "")
            for grupo in (("todos", "todos"), ("medio", n["medio"]), ("mes", n["fecha_publicacion"][:7])):
                grupos[grupo].append(nodo)
            if region:
                grupos[("macroregion", region)].append(nodo)
    filas = []
    for (grupo, valor), miembros in sorted(grupos.items()):
        for actor in actores():
            marcas = [tipos.get((m, actor), set()) for m in miembros]
            alguna = sum(bool(t) for t in marcas)
            filas.append(
                {
                    "grupo": grupo,
                    "valor": valor,
                    "actor": actor,
                    "notas": len(miembros),
                    "enlazan": sum(ENLACE_ACTOR in t for t in marcas),
                    "mencionan": sum(MENCION in t for t in marcas),
                    "enlazan_o_mencionan": alguna,
                    "proporcion": round(alguna / len(miembros), 4),
                }  # fmt: skip
            )
    return filas


# ---------------------------------------------------------------- criterios


def r1(notas, enlaces):
    """Enlaces oficiales de notas sobre El Niño atribuidos a una entidad."""
    sobre = {(n["medio"], n["id"]) for n in notas if _si(n["sobre_nino"])}
    oficiales = [e for e in enlaces if (e["medio"], e["id"]) in sobre and entidad(e["url"]) is not None]
    resueltos = sum(bool(entidad(e["url"])) for e in oficiales)
    valor = round(resueltos / len(oficiales), 4) if oficiales else 0.0
    sin = collections.Counter(clave_url(e["url"]) for e in oficiales if not entidad(e["url"]))
    detalle = f"{resueltos}/{len(oficiales)}; sin entidad: " + "; ".join(f"{u} ({n})" for u, n in sin.most_common(6))
    return [
        criterio(
            PRUEBA, "R1: enlaces oficiales con entidad", valor, RESOLUCION_MINIMA, valor >= RESOLUCION_MINIMA, detalle
        )
    ]


def r2(notas, enlaces):
    """Notas (de todos los temas) que enlazan a un actor y también lo mencionan: control de las menciones."""
    por_clave = {(n["medio"], n["id"]): n for n in notas}
    enlazan = collections.defaultdict(set)
    for e in enlaces:
        if (clave := (e["medio"], e["id"])) in por_clave and (ent := entidad(e["url"])) in actores():
            enlazan[ent].add(clave)
    filas = []
    for actor in actores():
        grupo = enlazan.get(actor, set())
        if len(grupo) < MIN_NOTAS_R2:
            continue
        con = [k for k in grupo if actor in mencionados(por_clave[k])]
        valor = round(len(con) / len(grupo), 4)
        sin = collections.Counter(k[0] for k in grupo if actor not in mencionados(por_clave[k]))
        detalle = f"{len(con)}/{len(grupo)}; sin mención por medio: {dict(sin)}"
        filas.append(
            criterio(
                PRUEBA, f"R2: {actor} enlazado y mencionado", valor, MENCION_MINIMA, valor >= MENCION_MINIMA, detalle
            )
        )
    return filas


def informativo(filas_aristas, filas_nodos, filas_citas, fuera):
    tipos = collections.Counter(a["tipo"] for a in filas_aristas)
    externos = collections.Counter(a["destino"] for a in filas_aristas if a["tipo"] == ENLACE_EXTERNO)
    actores_rango = [f"{f['nodo']} {f['pagerank']:.4f}" for f in filas_nodos if f["clase"] == "actor"][:6]
    notas_rango = [f"{f['nodo']} ({f['grado_entrada']})" for f in filas_nodos if f["clase"] == "nota"][:5]
    por_medio = [
        f"{f['valor']} {f['enlazan_o_mencionan']}/{f['notas']}"
        for f in filas_citas
        if f["grupo"] == "medio" and f["actor"] == "ENFEN"
    ]
    prueba = f"{PRUEBA} (informativo)"
    return [
        criterio(prueba, "aristas por tipo", dict(tipos), "", True),
        criterio(prueba, "enlaces fuera de la red", dict(fuera), "", True),
        criterio(prueba, "notas que enlazan o mencionan al ENFEN, por medio", "", "", True, "; ".join(por_medio)),
        criterio(prueba, "actores por PageRank", "", "", True, "; ".join(actores_rango)),
        criterio(prueba, "notas con más PageRank (grado de entrada)", "", "", True, "; ".join(notas_rango)),
        criterio(prueba, "dominios externos", "", "", True, "; ".join(f"{d} {n}" for d, n in externos.most_common(8))),
    ]


# ---------------------------------------------------------------- principal


def main(argv=None):
    argparse.ArgumentParser(description="Red de enlaces y citas de las notas sobre El Niño.").parse_args(argv)
    registro = configurar("redes-enlaces")
    inicio = ahora()
    notas = leer_csv(config.DIR_NOTICIAS / "notas.csv")
    enlaces = leer_csv(config.DIR_NOTICIAS / "enlaces.csv")
    regiones = {
        (f["medio"], f["id"]): f["macroregion_principal"] for f in leer_csv(config.DIR_NOTICIAS / "regiones.csv")
    }
    filas_aristas, fuera = aristas(notas, enlaces, regiones)
    filas_nodos = nodos(filas_aristas)
    filas_citas = citas(notas, filas_aristas, regiones)
    escribir_csv(config.DIR_RED / "aristas.csv", esquemas.ARISTAS, filas_aristas)
    escribir_csv(config.DIR_RED / "nodos.csv", esquemas.NODOS, filas_nodos)
    escribir_csv(config.DIR_RED / "citas.csv", esquemas.CITAS, filas_citas)
    filas = r1(notas, enlaces) + r2(notas, enlaces) + informativo(filas_aristas, filas_nodos, filas_citas, fuera)
    guardar(filas, config.DIR_RED / "validacion.csv")
    reporte(filas, [], inicio)
    log.info(f"Escrito: {config.DIR_RED.relative_to(config.RAIZ)} · registro: {registro.relative_to(config.RAIZ)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
