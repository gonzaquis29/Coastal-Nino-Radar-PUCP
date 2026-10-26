"""Lista de lugares (config/lugares.csv): los ubigeos del INEI y, por cada nombre, si se usa para asignar región.

Uso: python -m radar.region.lugares                # descarga el WFS del INEI (3 peticiones), mide y escribe
     python -m radar.region.lugares --sin-descarga  # vuelve a medir con data/raw/inei/

La decisión se mide con la mitad de calibración de las referencias (referencias.py), no a ojo:
1. Nombre con al menos MIN_MENCIONES notas de referencia: se usa si al menos PRECISION_MINIMA de ellas son de su
   macro-región. Un homónimo (Comas, La Victoria) se asigna a la macro-región de sus lugares que más acierta.
2. Sin medir y homónimo de un lugar de otra macro-región, en cualquier nivel: no se usa (Castilla, Bolívar).
3. Sin medir, de Piura: se usa si la sección local de El Tiempo concentra al menos ELTIEMPO_LOCAL_MINIMO de sus
   menciones.
4. Sin medir, departamento o provincia: se usa salvo que aparezca más en minúsculas que con mayúscula (palabra común).
5. Sin medir, distrito: no se usa.
"""

import argparse
import collections
import csv
import io
import logging
import sys

from radar import config
from radar.comun import regiones
from radar.comun.archivos import escribir_atomico, escribir_csv
from radar.comun.http import Cliente
from radar.comun.registro import configurar
from radar.comun.texto import ahora, sin_tildes
from radar.noticias.filtro import seccion_principal
from radar.region import esquemas, referencias
from radar.region.asignacion import Asignador, clave, macro_de_departamento

log = logging.getLogger(__name__)

MIN_MENCIONES = 5  # con 5 notas, 4 aciertos ya son el 80 %
PRECISION_MINIMA = 0.80
ELTIEMPO_LOCAL_MINIMO = 0.60  # el propio "Piura" está en la sección local en ~78 % de sus menciones
NIVELES = ("departamento", "provincia", "distrito")  # de mayor a menor
DEPARTAMENTOS_INEI = 25  # 24 departamentos y la Provincia Constitucional del Callao


class DatosInvalidos(ValueError):
    """Lo descargado del INEI no tiene la forma esperada."""


# ---------------------------------------------------------------- INEI


def descargar(cliente):
    """Atributos (sin geometría) de las capas de departamentos, provincias y distritos, en data/raw/inei/."""
    for capa, columnas in esquemas.CAPAS_INEI.items():
        r = cliente.get(
            config.URL_WFS_INEI,
            params={
                "service": "WFS",
                "version": "1.0.0",
                "request": "GetFeature",
                "typeName": f"Interoperabilidad:{capa}",
                "outputFormat": "csv",
                "propertyName": ",".join(columnas),
            },
        )
        _filas_capa(capa, r.text)  # valida antes de guardar
        escribir_atomico(config.DIR_RAW_INEI / f"{capa}.csv", r.content)
        log.info(f"INEI {capa}: {len(r.content) / 1000:.0f} kB")


def _filas_capa(capa, texto):
    filas = list(csv.DictReader(io.StringIO(texto)))
    faltan = set(esquemas.CAPAS_INEI[capa]) - set(filas[0] if filas else ())
    if faltan:
        raise DatosInvalidos(f"{capa}: faltan las columnas {sorted(faltan)}")
    return filas


def leer_inei(textos):
    """Lugares del INEI: {capa: texto CSV} → [{ubigeo, nivel, nombre, clave, departamento}]."""
    deps = {f["ccdd"]: f["nombdep"] for f in _filas_capa("ig_departamento", textos["ig_departamento"])}
    if set(deps.values()) != {d["departamento"] for d in regiones.departamentos()} or len(deps) != DEPARTAMENTOS_INEI:
        raise DatosInvalidos("los departamentos del INEI no coinciden con config/regiones.csv")
    lugares = [{"ubigeo": f"{c}0000", "nivel": "departamento", "nombre": n, "departamento": n} for c, n in deps.items()]
    lugares += [
        {
            "ubigeo": f"{f['ccdd']}{f['ccpp']}00",
            "nivel": "provincia",
            "nombre": f["nombprov"],
            "departamento": deps[f["ccdd"]],
        }
        for f in _filas_capa("ig_provincia", textos["ig_provincia"])
    ]
    lugares += [
        {"ubigeo": f["ubigeo"], "nivel": "distrito", "nombre": f["nombdist"], "departamento": deps[f["ccdd"]]}
        for f in _filas_capa("ig_distrito", textos["ig_distrito"])
    ]
    for lugar in lugares:
        lugar["clave"] = clave(lugar["nombre"])
    if len({lugar["ubigeo"] for lugar in lugares}) != len(lugares):
        raise DatosInvalidos("ubigeos repetidos")
    return sorted(lugares, key=lambda lugar: lugar["ubigeo"])


def en_alcance(lugar):
    """Los 25 departamentos, las provincias de los departamentos con litoral y los distritos de costa norte, costa
    centro y Lima (README, "Región")."""
    if lugar["nivel"] == "departamento":
        return True
    if lugar["nivel"] == "provincia":
        return lugar["departamento"] in regiones.departamentos_litoral()
    return macro_de_departamento()[lugar["departamento"]] != regiones.OTRAS


# ---------------------------------------------------------------- medición


def medir(lugares, notas, referencia_rpp):
    """Conteos por nombre en la mitad de calibración: macro-regiones de RPP, secciones de El Tiempo y apariciones
    con mayúscula o en minúsculas en titulares y resúmenes de todas las notas."""
    asignador = Asignador([dict(lugar, usar="0") for lugar in lugares])

    def nombres(texto):
        return {c for _, c, propio in asignador.ocurrencias(sin_tildes(texto)) if propio}

    rpp, eltiempo = collections.defaultdict(collections.Counter), collections.defaultdict(collections.Counter)
    for f in referencia_rpp:
        if f["macro"] and referencias.mitad(f["id"]) == referencias.CALIBRACION:
            for c in nombres(f"{f['titular']} . {f['resumen']}"):
                rpp[c][f["macro"]] += 1
    mayusculas, minusculas = collections.Counter(), collections.Counter()
    for n in notas:
        texto = f"{n['titular']} . {n['resumen']}"
        for _, c, propio in asignador.ocurrencias(sin_tildes(texto)):
            (mayusculas if propio else minusculas)[c] += 1
        if n["medio"] == "eltiempo" and referencias.mitad(n["id"]) == referencias.CALIBRACION:
            for c in nombres(texto):
                eltiempo[c][seccion_principal(n["url"])] += 1
    return {"rpp": rpp, "eltiempo": eltiempo, "mayusculas": mayusculas, "minusculas": minusculas}


def decidir(lugares, conteos):
    """Filas de config/lugares.csv: la regla del encabezado del módulo, por nombre."""
    por_clave = collections.defaultdict(list)
    for lugar in lugares:
        por_clave[lugar["clave"]].append(lugar)
    filas = []
    for c, todos in por_clave.items():
        alcance = sorted((x for x in todos if en_alcance(x)), key=lambda x: NIVELES.index(x["nivel"]))
        rpp, et = conteos["rpp"].get(c, collections.Counter()), conteos["eltiempo"].get(c, collections.Counter())
        n, n_et = sum(rpp.values()), sum(et.values())
        medida = {
            "ref_n": n,
            "precision": "",
            "eltiempo_n": n_et,
            "eltiempo_local": round(et[referencias.SECCION_LOCAL_ELTIEMPO] / n_et, 3) if n_et else "",
            "mayusculas": conteos["mayusculas"][c],
            "minusculas": conteos["minusculas"][c],
        }
        elegido, usar, motivo = (alcance[0] if alcance else None), False, "fuera_de_alcance"
        macros = {macro_de_departamento()[x["departamento"]] for x in todos}
        if alcance and n >= MIN_MENCIONES:
            mejor = max(sorted({macro_de_departamento()[x["departamento"]] for x in alcance}), key=lambda m: rpp[m])
            medida["precision"] = round(rpp[mejor] / n, 3)
            usar = medida["precision"] >= PRECISION_MINIMA
            motivo = "medido_rpp" if usar else "precision_baja"
            elegido = next(x for x in alcance if macro_de_departamento()[x["departamento"]] == mejor)
        elif alcance and len(macros) > 1:
            motivo = "homonimo_sin_medir"
        elif alcance and elegido["departamento"] == referencias.DEPARTAMENTO_ELTIEMPO and n_et >= MIN_MENCIONES:
            usar = medida["eltiempo_local"] >= ELTIEMPO_LOCAL_MINIMO
            motivo = "medido_eltiempo" if usar else "eltiempo_bajo"
        elif alcance and elegido["nivel"] != "distrito":
            usar = not (medida["minusculas"] and medida["minusculas"] >= medida["mayusculas"])
            motivo = "sin_medir" if usar else "palabra_comun"
        elif alcance:
            motivo = "distrito_sin_medir"
        for x in todos:
            es_elegido = x is elegido
            filas.append(
                {
                    **{k: x[k] for k in ("ubigeo", "nivel", "nombre", "clave", "departamento")},
                    "usar": usar and es_elegido,
                    "motivo": motivo if es_elegido or motivo == "fuera_de_alcance" else "homonimo",
                    **medida,
                }
            )
    return sorted(filas, key=lambda f: f["ubigeo"])


# ---------------------------------------------------------------- principal


def main(argv=None):
    ap = argparse.ArgumentParser(description="Lista de lugares del INEI y su decisión medida (config/lugares.csv).")
    ap.add_argument("--sin-descarga", action="store_true", help="usa lo ya descargado en data/raw/inei/")
    args = ap.parse_args(argv)
    registro = configurar("region-lugares")
    inicio = ahora()
    if not args.sin_descarga:
        descargar(Cliente(hosts_permitidos={config.HOST_INEI_GIS}))
    textos = {capa: (config.DIR_RAW_INEI / f"{capa}.csv").read_text(encoding="utf-8") for capa in esquemas.CAPAS_INEI}
    lugares = leer_inei(textos)
    notas = referencias.notas_leidas()
    filas = decidir(lugares, medir(lugares, notas, referencias.referencia_rpp(notas)))
    escribir_csv(config.ARCHIVO_LUGARES, esquemas.LUGARES, filas)
    resumen = collections.Counter((f["nivel"], f["motivo"]) for f in filas if f["motivo"] not in ("homonimo",))
    log.info(f"Lugares del INEI: {len(filas)} ({len(notas)} notas leídas como referencia)")
    for (nivel, motivo), n in sorted(resumen.items()):
        log.info(f"  {nivel:13}{motivo:20}{n:>6}")
    log.info(f"En uso: {sum(f['usar'] for f in filas)} · escrito {config.ARCHIVO_LUGARES.relative_to(config.RAIZ)}")
    log.info(f"Duración: {(ahora() - inicio).total_seconds():.0f} s · registro: {registro.relative_to(config.RAIZ)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
