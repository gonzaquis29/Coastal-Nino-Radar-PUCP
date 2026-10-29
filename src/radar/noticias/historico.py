"""Recupera el histórico de notas de los 4 medios (1-ene → 24-oct) y procesa las de la recolección diaria
(definición en docs/noticias/definicion.md).

Uso: python -m radar.noticias.historico [--medio andina rpp …] [--horas 7] [--solo-descubrir] [--limite N]
     python -m radar.noticias.historico --recalcular [--todo | --informe | --aplicar]  (docs/noticias/recalculo.md)
"""

import argparse
import concurrent.futures
import datetime as dt
import logging
import statistics
import sys
import threading

from radar import config
from radar.comun.archivos import EstadoDescargas, escribir_csv, leer_csv
from radar.comun.candado import exclusivo
from radar.comun.energia import sin_suspension
from radar.comun.http import Cliente
from radar.comun.registro import configurar, describir
from radar.comun.texto import ahora
from radar.noticias import esquemas
from radar.noticias.medios import DETENER, MEDIOS

log = logging.getLogger(__name__)

DIAS_FECHA_DUDOSA = 7  # más que esto entre la fecha y la de creación (o la de sus vecinas) = nota re-fechada
VECINAS_ANDINA = 20  # notas de número más cercano con que se compara la fecha de una nota de Andina
GUARDAR_ESTADO_CADA = 50


def correr_medio(nombre, parar, solo_descubrir=False, limite=None):
    """Descubre y descarga un medio. Un medio que falla o se bloquea no detiene a los demás."""
    medio = MEDIOS[nombre](Cliente(hosts_permitidos={config.HOSTS_MEDIOS[nombre]}), parar)
    resumen = {"medio": nombre, "detalle": ""}
    try:
        with EstadoDescargas(medio.dir / "estado.json", cada=GUARDAR_ESTADO_CADA) as estado:
            medio.agregar_diaria()
            medio.descubrir(estado)
            candidatas = medio.candidatas()
            resumen.update(listadas=len(medio.notas()), candidatas=len(candidatas))
            if not solo_descubrir:
                pendientes = [f for f in candidatas if f["id"] not in medio.hechas]
                leidas, sin_nota, errores = medio.procesar(pendientes[:limite], "candidata", estado)
                resumen.update(leidas=leidas, sin_nota=sin_nota, errores=errores)
    except DETENER as e:
        resumen["detalle"] = f"detenido: {describir(e)}"
    except Exception as e:
        log.debug("fallo en %s", nombre, exc_info=True)
        resumen["detalle"] = f"FALLO: {describir(e)}"
    resumen.update(listadas=len(medio.notas()), hechas=len(medio.hechas))
    return resumen


# ---------------------------------------------------------------- consolidación


def _dias_entre(posterior, anterior):
    return (dt.datetime.fromisoformat(posterior) - dt.datetime.fromisoformat(anterior)).total_seconds() / 86400


def marcar_fechas_dudosas(notas):
    """Andina vuelve a fechar notas antiguas y RPP las vuelve a publicar: se marcan, no se corrigen."""
    for n in notas:
        n["fecha_dudosa"] = bool(
            n["medio"] == "rpp"
            and n["fecha_creacion"]
            and _dias_entre(n["fecha_publicacion"], n["fecha_creacion"]) > DIAS_FECHA_DUDOSA
        )
    andina = sorted((n for n in notas if n["medio"] == "andina"), key=lambda n: int(n["id"]))
    mitad = VECINAS_ANDINA // 2
    for i, n in enumerate(andina):
        vecinas = andina[max(0, i - mitad) : i] + andina[i + 1 : i + 1 + mitad]
        if len(vecinas) >= mitad:
            mediana = statistics.median_low(dt.datetime.fromisoformat(v["fecha_publicacion"]) for v in vecinas)
            n["fecha_dudosa"] = _dias_entre(n["fecha_publicacion"], mediana.isoformat()) > DIAS_FECHA_DUDOSA
    return notas


def consolidar():
    """data/processed/noticias/notas.csv y enlaces.csv: las notas del período de los 4 medios, sin duplicados."""
    notas, claves = [], set()
    for nombre in MEDIOS:
        for n in leer_csv(config.DIR_RAW_NOTICIAS / nombre / "notas.csv"):
            clave = (n["medio"], n["id"])
            if clave not in claves and n["fecha_publicacion"][:10] >= config.INICIO.isoformat():
                claves.add(clave)
                notas.append(n)
    marcar_fechas_dudosas(notas)
    notas.sort(key=lambda n: (n["medio"], n["fecha_publicacion"], n["id"]))
    enlaces = [
        e
        for nombre in MEDIOS
        for e in leer_csv(config.DIR_RAW_NOTICIAS / nombre / "enlaces.csv")
        if (e["medio"], e["id"]) in claves
    ]
    escribir_csv(config.DIR_NOTICIAS / "notas.csv", esquemas.NOTAS, notas)
    escribir_csv(
        config.DIR_NOTICIAS / "enlaces.csv", esquemas.ENLACES, list({tuple(e.values()): e for e in enlaces}.values())
    )
    return notas


# ---------------------------------------------------------------- principal


def recalcular(args, parar, inicio, registro):
    from radar.noticias import recalculo  # recalculo usa viabilidad, que a su vez usa este módulo
    from radar.noticias.viabilidad import guardar, reporte

    if args.aplicar:
        filas, aplicado = recalculo.aplicar()
        guardar(filas)
        reporte(filas, [], inicio)
        if not aplicado:
            log.info("\nNo se aplicó: falta releer notas o algún criterio no pasa. Los archivos actuales no cambiaron.")
            return 1
        notas = consolidar()
        log.info(f"\nAplicado. Consolidado: {len(notas)} notas. Siguen region.notas y viabilidad resultados.")
        return 0
    if not args.informe:
        hechos = [m for m in args.medio if recalculo.leer_json(recalculo.Archivos(m).estado, {}).get("aplicado")]
        if hechos:
            log.info(f"El recálculo ya se aplicó o se está aplicando en: {', '.join(hechos)}. No se vuelve a leer.")
            return 1
        fase = recalculo.FASE_RESTO if args.todo else recalculo.FASE_NINO
        log.info(f"Recálculo {inicio.isoformat()} · fase {fase} · {', '.join(args.medio)} (Ctrl+C guarda y sale)")
        resumenes = recalculo.correr(args.medio, fase, args.limite, parar)
        log.info(f"\n{'medio':10}{'pendientes':>11}{'releídas':>10}{'sin releer':>11}{'errores':>9}{'de red':>8}")
        for m, r in resumenes.items():
            log.info(
                f"{m:10}{r['pendientes']:>11}{r['releidas']:>10}{r['sin_releer']:>11}{r['errores']:>9}"
                f"{r['errores_red']:>8}  {r.get('detalle', '')}"
            )
    filas, completo = recalculo.informe()
    guardar(filas)
    reporte(filas, [], inicio)
    if not completo:
        siguiente = "--recalcular --todo" if not args.todo else "--recalcular --todo (de nuevo)"
        log.info(f"\nPunto de control: revisar el informe antes de seguir con {siguiente}.")
    log.info(
        f"Duración: {(ahora() - inicio).total_seconds() / 60:.1f} min · registro: {registro.relative_to(config.RAIZ)}"
    )
    return 0


@exclusivo("radar.noticias.historico")
def main(argv=None):
    ap = argparse.ArgumentParser(description="Histórico de notas de los 4 medios.")
    ap.add_argument("--medio", nargs="+", choices=list(MEDIOS), default=list(MEDIOS))
    ap.add_argument("--horas", type=float, help="se detiene sola (y guarda) después de estas horas")
    ap.add_argument("--solo-descubrir", action="store_true", help="arma las listas sin descargar notas")
    ap.add_argument("--limite", type=int, help="descarga como máximo N notas por medio (para probar)")
    ap.add_argument("--recalcular", action="store_true", help="vuelve a leer las notas ya leídas (recalculo.py)")
    ap.add_argument("--todo", action="store_true", help="con --recalcular: sigue después del punto de control")
    ap.add_argument("--informe", action="store_true", help="con --recalcular: criterios sobre lo ya releído")
    ap.add_argument("--aplicar", action="store_true", help="con --recalcular: reemplaza los archivos si todo pasa")
    args = ap.parse_args(argv)
    registro = configurar("noticias-historico")
    inicio = ahora()
    parar = threading.Event()
    if args.horas:
        reloj = threading.Timer(args.horas * 3600, parar.set)
        reloj.daemon = True
        reloj.start()
    if args.recalcular:
        with sin_suspension():
            return recalcular(args, parar, inicio, registro)
    log.info(f"Histórico de noticias {inicio.isoformat()} · {', '.join(args.medio)} (Ctrl+C guarda y sale)")
    with concurrent.futures.ThreadPoolExecutor(max_workers=len(args.medio)) as hilos:
        tareas = [hilos.submit(correr_medio, m, parar, args.solo_descubrir, args.limite) for m in args.medio]
        try:
            resumenes = [t.result() for t in tareas]
        except KeyboardInterrupt:
            parar.set()
            resumenes = [t.result() for t in tareas]
    notas = consolidar()
    log.info(f"\n{'medio':10}{'listadas':>10}{'candidatas':>12}{'leídas':>8}{'sin nota':>10}{'errores':>9}{'total':>8}")
    for r in resumenes:
        log.info(
            f"{r['medio']:10}{r.get('listadas', 0):>10}{r.get('candidatas', '-'):>12}{r.get('leidas', '-'):>8}"
            f"{r.get('sin_nota', '-'):>10}{r.get('errores', '-'):>9}{r['hechas']:>8}  {r['detalle']}"
        )
    log.info(f"\nConsolidado: {len(notas)} notas en {config.DIR_NOTICIAS.relative_to(config.RAIZ)}")
    log.info(
        f"Duración: {(ahora() - inicio).total_seconds() / 60:.1f} min · registro: {registro.relative_to(config.RAIZ)}"
    )
    return 0 if any(r.get("hechas") or r.get("listadas") for r in resumenes) else 1


if __name__ == "__main__":
    sys.exit(main())
