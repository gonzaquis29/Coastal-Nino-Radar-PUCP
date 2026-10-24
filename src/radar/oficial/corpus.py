"""Construye el corpus oficial (definición en docs/oficial/definicion.md).

Uso: python -m radar.oficial.corpus [--solo enfen|senamhi] [--sin-descarga] [--prueba]
"""

import argparse
import logging
import sys

from radar import config
from radar.comun.archivos import EstadoDescargas, escribir_csv, guardar_gz, leer_csv, leer_gz
from radar.comun.http import Cliente
from radar.comun.registro import configurar, describir
from radar.comun.texto import ahora
from radar.oficial import enfen, esquemas, senamhi, validar
from radar.oficial.senamhi_paginas import leer_tabla
from radar.recoleccion.urls import filas_de_notas

log = logging.getLogger(__name__)

HOSTS = {config.HOST_ENFEN, config.HOST_SENAMHI, config.HOST_SENAMHI_GIS}
FUENTES = ("enfen", "senamhi")


def conservar(nuevas, anteriores, ids_fallidos, clave="id"):
    """No empeorar el corpus: si un documento que ya estaba falla ahora, se conservan sus filas anteriores."""
    presentes = {f[clave] for f in nuevas}
    return nuevas + [f for f in anteriores if f[clave] in ids_fallidos and f[clave] not in presentes]


def leer_anteriores():
    """El corpus que ya está en data/oficial/ (para conservar lo que falle ahora)."""
    return {nombre: leer_csv(config.DIR_OFICIAL / nombre) for nombre in esquemas.ARCHIVOS}


def _parrafos_anteriores(anteriores, fuente):
    return [p for p in anteriores["parrafos.csv"] if p["fuente"] == fuente]


# ---------------------------------------------------------------- ENFEN


def _descargar_enfen(cliente, estado, alertas):
    slugs, lastmod, avisos = enfen.documentos(cliente)
    alertas += [f"ENFEN · {a}" for a in avisos]
    for slug in slugs:
        try:
            if enfen.descargar(cliente, slug, lastmod.get(slug, ""), estado):
                alertas.append(f"ENFEN · PDF nuevo o cambiado: {slug}")
        except Exception as e:  # una descarga que falla no detiene las demás
            log.debug("descarga %s", slug, exc_info=True)
            alertas.append(f"FALLO ENFEN · {slug}: {describir(e)}")
    return slugs


def correr_enfen(cliente, descargar, anteriores, alertas):
    with EstadoDescargas(enfen.DIR / "estado.json") as estado:
        if descargar:
            slugs = _descargar_enfen(cliente, estado, alertas)
        else:
            slugs = list(dict.fromkeys(enfen.SEMILLAS + sorted(estado)))
        comunicados, probs, parrafos, control, errores = enfen.construir(slugs, estado)
    alertas += [f"FALLO ENFEN · {slug}: {error}" for slug, error in errores.items()]
    fallidos = {c["id"] for c in anteriores["comunicados.csv"] if c["slug"] in errores}
    salida = {
        "comunicados.csv": conservar(comunicados, anteriores["comunicados.csv"], fallidos),
        "probabilidades.csv": conservar(probs, anteriores["probabilidades.csv"], fallidos, "comunicado_id"),
        "parrafos.csv": conservar(parrafos, _parrafos_anteriores(anteriores, "enfen"), fallidos, "doc_id"),
    }
    return salida, validar.validar_enfen(comunicados, parrafos, control, errores)


# ---------------------------------------------------------------- Senamhi


def _tabla_senamhi(cliente, descargar, alertas):
    if descargar:
        try:
            contenido = cliente.get(config.URL_AVISOS_SENAMHI).content
            guardar_gz(senamhi.ARCHIVO_TABLA, contenido)
            return leer_tabla(contenido)
        except Exception as e:
            log.debug("tabla del Senamhi", exc_info=True)
            alertas.append(f"FALLO Senamhi · tabla de avisos: {describir(e)} (se usa la última copia)")
    if not senamhi.ARCHIVO_TABLA.exists():
        raise RuntimeError("no hay tabla de avisos del Senamhi descargada")
    return leer_tabla(leer_gz(senamhi.ARCHIVO_TABLA))


def _descargar_senamhi(cliente, tabla, estado, alertas):
    fallidos = set()
    for fila in tabla:
        clase = senamhi.candidato(fila)
        if not clase:
            continue
        try:
            senamhi.descargar(cliente, fila, clase, estado)
        except Exception as e:
            clave = senamhi.clave_aviso(fila)
            fallidos.add(f"senamhi-{clave}")
            log.debug("descarga %s", clave, exc_info=True)
            alertas.append(f"FALLO Senamhi · aviso {clave}: {describir(e)}")
    return fallidos


def correr_senamhi(cliente, descargar, anteriores, alertas):
    tabla = _tabla_senamhi(cliente, descargar, alertas)
    en_tabla = {f"{f['anio']}-{f['b']}" for f in tabla}
    faltan = sorted({f["id"] for f in filas_de_notas("senamhi")} - en_tabla)
    if faltan:
        alertas.append(f"Senamhi · {len(faltan)} avisos de data/urls ya no están en la tabla: {', '.join(faltan[:5])}")
    with EstadoDescargas(senamhi.DIR / "estado.json") as estado:
        fallidos = _descargar_senamhi(cliente, tabla, estado, alertas) if descargar else set()
    avisos, dias, parrafos, control, errores = senamhi.construir(tabla)
    alertas += [f"FALLO Senamhi · {aviso}: {error}" for aviso, error in errores.items()]
    fallidos |= set(errores)
    salida = {
        "avisos.csv": conservar(avisos, anteriores["avisos.csv"], fallidos),
        "aviso_dias.csv": conservar(dias, anteriores["aviso_dias.csv"], fallidos, "aviso_id"),
        "parrafos.csv": conservar(parrafos, _parrafos_anteriores(anteriores, "senamhi"), fallidos, "doc_id"),
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
    anteriores = leer_anteriores()
    alertas, validacion, salida, parrafos = [], [], {}, {}
    for fuente, correr in (("enfen", correr_enfen), ("senamhi", correr_senamhi)):
        if args.solo not in (None, fuente):
            continue
        try:
            filas, criterios = correr(cliente, not args.sin_descarga, anteriores, alertas)
        except Exception as e:
            log.debug("fuente %s", fuente, exc_info=True)
            alertas.append(f"FALLO {fuente} completo: {describir(e)}")
            continue
        parrafos[fuente] = filas.pop("parrafos.csv")
        salida.update(filas)
        validacion += criterios
    if parrafos:  # al menos una fuente se construyó: la otra conserva sus párrafos anteriores
        todos = [p for fuente in FUENTES for p in parrafos.get(fuente, _parrafos_anteriores(anteriores, fuente))]
        salida["parrafos.csv"] = sorted(todos, key=lambda p: (p["fuente"], p["doc_id"], int(p["orden"])))
        salida["validacion.csv"] = validacion
    _reporte(salida, validacion, alertas, inicio, args.prueba)
    if parrafos and not args.prueba:
        for nombre, filas in salida.items():
            escribir_csv(config.DIR_OFICIAL / nombre, esquemas.ARCHIVOS[nombre], filas)
        log.info("Escrito en data/oficial/")
    log.info(f"Registro: {registro.relative_to(config.RAIZ)}")
    return 0 if parrafos else 1


if __name__ == "__main__":
    sys.exit(main())
