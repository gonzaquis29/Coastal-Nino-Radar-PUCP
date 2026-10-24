"""Construye el corpus oficial (definición en docs/oficial/definicion.md).

Uso: python -m radar.oficial.corpus [--solo enfen|senamhi] [--sin-descarga] [--prueba]
"""

import argparse
import logging
import sys

from radar import config
from radar.comun.archivos import EstadoDescargas, escribir_csv, guardar_gz, leer_csv, leer_gz
from radar.comun.http import Cliente
from radar.comun.registro import configurar
from radar.comun.texto import ahora
from radar.oficial import enfen, esquemas, senamhi, validar
from radar.oficial.senamhi_paginas import leer_tabla

log = logging.getLogger(__name__)

HOSTS = {enfen.HOST, senamhi.HOST, senamhi.HOST_GIS}
FUENTES = ("enfen", "senamhi")


def conservar(nuevas, anteriores, ids_fallidos, clave="id"):
    """No empeorar el corpus: si un documento que ya estaba falla ahora, se conservan sus filas anteriores."""
    presentes = {f[clave] for f in nuevas}
    return nuevas + [f for f in anteriores if f[clave] in ids_fallidos and f[clave] not in presentes]


def _anteriores(nombre):
    return leer_csv(config.DIR_OFICIAL / nombre)


# ---------------------------------------------------------------- ENFEN


def correr_enfen(cliente, descargar, alertas):
    with EstadoDescargas(enfen.DIR / "estado.json") as estado:
        if descargar:
            slugs, lastmod, avisos = enfen.documentos(cliente)
            alertas += [f"ENFEN · {a}" for a in avisos]
            for slug in slugs:
                try:
                    if enfen.descargar(cliente, slug, lastmod.get(slug, ""), estado):
                        alertas.append(f"ENFEN · PDF nuevo o cambiado: {slug}")
                except Exception as e:  # una descarga que falla no detiene las demás
                    log.debug("descarga %s", slug, exc_info=True)
                    alertas.append(f"FALLO ENFEN · {slug}: {type(e).__name__} {e}"[:200])
        else:
            slugs = list(dict.fromkeys(enfen.SEMILLAS + sorted(estado)))
        comunicados, probs, parrafos, control, errores = enfen.construir(slugs, estado)
    alertas += [f"FALLO ENFEN · {k}: {v}" for k, v in errores.items()]
    fallidos = {c["id"] for c in _anteriores("comunicados.csv") if c["slug"] in errores}
    salida = {
        "comunicados.csv": conservar(comunicados, _anteriores("comunicados.csv"), fallidos),
        "probabilidades.csv": conservar(probs, _anteriores("probabilidades.csv"), fallidos, "comunicado_id"),
        "parrafos": conservar(
            parrafos, [p for p in _anteriores("parrafos.csv") if p["fuente"] == "enfen"], fallidos, "doc_id"
        ),
    }
    return salida, validar.validar_enfen(comunicados, parrafos, control, errores)


# ---------------------------------------------------------------- Senamhi


def _tabla_senamhi(cliente, descargar, alertas):
    if descargar:
        try:
            contenido = cliente.get(senamhi.URL_TABLA).content
            guardar_gz(senamhi.ARCHIVO_TABLA, contenido)
            return leer_tabla(contenido)
        except Exception as e:
            log.debug("tabla del Senamhi", exc_info=True)
            alertas.append(
                f"FALLO Senamhi · tabla de avisos: {type(e).__name__} {e}"[:180] + " (se usa la última copia)"
            )
    if not senamhi.ARCHIVO_TABLA.exists():
        raise RuntimeError("no hay tabla de avisos del Senamhi descargada")
    return leer_tabla(leer_gz(senamhi.ARCHIVO_TABLA))


def _avisos_de_urls():
    filas = []
    for ruta in sorted(config.DIR_URLS.glob("*.csv")):
        if ruta.stem.count("_") == 1:  # AAAA-MM-DD_persona.csv (no el registro de sitemaps)
            filas += [f["id"] for f in leer_csv(ruta) if f["medio"] == "senamhi"]
    return set(filas)


def correr_senamhi(cliente, descargar, alertas):
    tabla = _tabla_senamhi(cliente, descargar, alertas)
    faltan = sorted(_avisos_de_urls() - {f"{f['anio']}-{f['b']}" for f in tabla})
    if faltan:
        alertas.append(f"Senamhi · {len(faltan)} avisos de data/urls ya no están en la tabla: {', '.join(faltan[:5])}")
    fallidos = set()
    with EstadoDescargas(senamhi.DIR / "estado.json") as estado:
        if descargar:
            for fila in tabla:
                clase = senamhi.candidato(fila)
                if not clase:
                    continue
                try:
                    senamhi.descargar(cliente, fila, clase, estado)
                except Exception as e:
                    fallidos.add(f"senamhi-{senamhi.clave_aviso(fila)}")
                    log.debug("descarga %s", senamhi.clave_aviso(fila), exc_info=True)
                    alertas.append(f"FALLO Senamhi · aviso {senamhi.clave_aviso(fila)}: {type(e).__name__} {e}"[:200])
    avisos, dias, parrafos, control, errores = senamhi.construir(tabla)
    alertas += [f"FALLO Senamhi · {k}: {v}" for k, v in errores.items()]
    fallidos |= set(errores)
    salida = {
        "avisos.csv": conservar(avisos, _anteriores("avisos.csv"), fallidos),
        "aviso_dias.csv": conservar(dias, _anteriores("aviso_dias.csv"), fallidos, "aviso_id"),
        "parrafos": conservar(
            parrafos, [p for p in _anteriores("parrafos.csv") if p["fuente"] == "senamhi"], fallidos, "doc_id"
        ),
    }
    return salida, validar.validar_senamhi(avisos, dias, control, errores)


# ---------------------------------------------------------------- reporte y escritura


def _reporte(salida, filas_validacion, alertas, inicio, prueba):
    log.info(f"\nCorpus oficial {inicio.isoformat()}{' [PRUEBA]' if prueba else ''}")
    for nombre, filas in salida.items():
        log.info(f"  {nombre:20} {len(filas):5} filas")
    log.info("\nPruebas de viabilidad:")
    for nombre_prueba in dict.fromkeys(f["prueba"] for f in filas_validacion):
        grupo = [f for f in filas_validacion if f["prueba"] == nombre_prueba]
        informativo = "informativo" in nombre_prueba
        resultado = "" if informativo else ("PASA" if all(f["pasa"] for f in grupo) else "NO PASA")
        log.info(f"  {nombre_prueba} {resultado}")
        for f in grupo:
            marca = "·" if informativo else ("ok" if f["pasa"] else "NO")
            detalle = f" — {f['detalle'][:120]}" if f["detalle"] else ""
            log.info(f"    [{marca:2}] {f['criterio']}: {f['valor']} (umbral {f['umbral']}){detalle}")
    log.info("\n" + ("\n".join("- " + a for a in alertas) if alertas else "Sin alertas."))
    log.info(f"\nDuración: {(ahora() - inicio).total_seconds() / 60:.1f} min")


def main(argv=None):
    ap = argparse.ArgumentParser(description="Construye el corpus oficial (ENFEN y Senamhi).")
    ap.add_argument("--solo", choices=FUENTES)
    ap.add_argument("--sin-descarga", action="store_true", help="solo vuelve a extraer desde data/raw/oficial")
    ap.add_argument("--prueba", action="store_true", help="no escribe data/oficial")
    args = ap.parse_args(argv)
    registro = configurar("corpus")
    inicio = ahora()
    cliente = Cliente(hosts_permitidos=HOSTS)
    alertas, validacion, parrafos, salida, ok = [], [], {}, {}, 0
    for fuente, correr in (("enfen", correr_enfen), ("senamhi", correr_senamhi)):
        if args.solo not in (None, fuente):
            continue
        try:
            filas, criterios = correr(cliente, not args.sin_descarga, alertas)
        except Exception as e:
            log.debug("fuente %s", fuente, exc_info=True)
            alertas.append(f"FALLO {fuente} completo: {type(e).__name__} {e}"[:200])
            continue
        parrafos[fuente] = filas.pop("parrafos")
        salida.update(filas)
        validacion += criterios
        ok += 1
    anteriores = _anteriores("parrafos.csv")
    todos = [p for fuente in FUENTES for p in parrafos.get(fuente, [x for x in anteriores if x["fuente"] == fuente])]
    salida["parrafos.csv"] = sorted(todos, key=lambda p: (p["fuente"], p["doc_id"], int(p["orden"])))
    if validacion:
        salida["validacion.csv"] = validacion
    _reporte(salida, validacion, alertas, inicio, args.prueba)
    if not args.prueba and ok:
        for nombre, filas in salida.items():
            escribir_csv(config.DIR_OFICIAL / nombre, esquemas.ARCHIVOS[nombre], filas)
        log.info("Escrito en data/oficial/")
    log.info(f"Registro: {registro.relative_to(config.RAIZ)}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
