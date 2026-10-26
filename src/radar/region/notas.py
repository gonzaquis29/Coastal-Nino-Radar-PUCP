"""Macro-región de las notas ya leídas (titular y resumen) y su validación con criterios fijados antes de correrla.

Uso: python -m radar.region.notas  # escribe data/processed/noticias/regiones.csv y data/processed/region/validacion.csv

No pide nada a los medios: usa data/raw/noticias/ (lo que ya leyó el histórico), data/urls/ y config/lugares.csv.
El cuerpo no se guarda; la etapa de preprocesamiento llamará a asignacion.asignar_nota con el cuerpo al releerlo.
"""

import argparse
import collections
import logging
import sys

from radar import config
from radar.comun import regiones
from radar.comun.archivos import escribir_csv, leer_csv
from radar.comun.registro import configurar, describir
from radar.comun.texto import ahora
from radar.noticias.filtro import seccion_principal
from radar.oficial.esquemas import VALIDACION
from radar.region import asignacion, esquemas, referencias

log = logging.getLogger(__name__)

# ---------------------------------------------------------------- umbrales (docs/region/definicion.md, criterios)
ACIERTO_REGIONAL_MINIMO = 0.85
ERROR_MAXIMO = 0.05
PRECISION_ETIQUETAS_MINIMA = 0.90
ACIERTO_COSTA_NORTE_MINIMO = 0.85
ACIERTO_COSTA_CENTRO_MINIMO = 0.80
ACIERTO_LIMA_MINIMO = 0.50
NACIONAL_EN_NACIONALES_MINIMO = 0.80
NACIONAL_EN_MUNDO_MINIMO = 0.95
ELTIEMPO_LOCAL_MINIMO = 0.80
FUERA_DE_LIMA_MINIMO = 0.60
SECCIONES_NACIONALES_RPP = ("politica", "economia")
SECCION_MUNDO_RPP = "mundo"
FUENTE_TEXTO = "titular_resumen"
FUERA_DE_LIMA = {regiones.COSTA_NORTE, regiones.COSTA_CENTRO, regiones.OTRAS}


def criterio(prueba, nombre, valor, umbral, pasa, detalle=""):
    return {"prueba": prueba, "criterio": nombre, "valor": valor, "umbral": umbral, "pasa": pasa, "detalle": detalle}


def proporcion(filas, condicion):
    return round(sum(map(condicion, filas)) / len(filas), 3) if filas else 0.0


def asignar_notas(notas):
    """Filas de regiones.csv; una nota que falla no detiene a las demás."""
    version, filas, errores = asignacion.version_lugares(), [], 0
    for n in notas:
        try:
            r = asignacion.asignar_nota(n["titular"], n["resumen"])
        except Exception as e:  # error aislado por nota; el detalle va al registro
            log.debug("%s %s: %s", n["medio"], n["id"], describir(e))
            errores += 1
            continue
        filas.append(
            {"medio": n["medio"], "id": n["id"], **r, "fuente_texto": FUENTE_TEXTO, "version_lugares": version}
        )
    return filas, errores


# ---------------------------------------------------------------- validación


def _con_asignacion(filas):
    for f in filas:
        f["asignadas"] = asignacion.asignar_nota(f["titular"], f["resumen"])["macroregiones"]
    return filas


def _acierto(prueba, grupo, filas, minimo, con_error=True, con_precision=False):
    """Acierto (la macro-región de referencia está entre las asignadas), error (asignó otras y no esa) y precisión
    de las etiquetas asignadas (sin contar "nacional")."""
    acierto = proporcion(filas, lambda f: f["macro"] in f["asignadas"])
    out = [criterio(prueba, f"{grupo}: acierto (n={len(filas)})", acierto, minimo, acierto >= minimo)]
    if con_error:
        error = proporcion(
            filas, lambda f: f["macro"] not in f["asignadas"] and f["asignadas"] != [asignacion.NACIONAL]
        )
        out.append(criterio(prueba, f"{grupo}: error", error, ERROR_MAXIMO, error <= ERROR_MAXIMO))
    if con_precision:
        etiquetas = [(f["macro"], m) for f in filas for m in f["asignadas"] if m != asignacion.NACIONAL]
        precision = round(sum(r == m for r, m in etiquetas) / len(etiquetas), 3) if etiquetas else 0.0
        ok = precision >= PRECISION_ETIQUETAS_MINIMA
        out.append(criterio(prueba, f"{grupo}: precisión de etiquetas", precision, PRECISION_ETIQUETAS_MINIMA, ok))
    return out


def _nacional(prueba, grupo, filas, minimo):
    valor = proporcion(filas, lambda f: f["asignadas"] == [asignacion.NACIONAL])
    lima = proporcion(filas, lambda f: regiones.LIMA_Y_CALLAO in f["asignadas"])
    return [criterio(prueba, f"{grupo}: nacional (n={len(filas)})", valor, minimo, valor >= minimo, f"Lima: {lima}")]


def validar(notas, referencia_rpp):
    """Criterios de docs/region/definicion.md sobre la mitad de evaluación (titular y resumen)."""
    evaluacion = [f for f in referencia_rpp if referencias.mitad(f["id"]) == referencias.EVALUACION]
    rpp = _con_asignacion(evaluacion)
    regional = [f for f in rpp if f["macro"] in FUERA_DE_LIMA]
    filas = _acierto("RPP regional (sin Lima)", "regional", regional, ACIERTO_REGIONAL_MINIMO, con_precision=True)
    for macro, minimo in (
        (regiones.COSTA_NORTE, ACIERTO_COSTA_NORTE_MINIMO),
        (regiones.COSTA_CENTRO, ACIERTO_COSTA_CENTRO_MINIMO),
    ):
        grupo = [f for f in rpp if f["macro"] == macro]
        filas += _acierto("RPP por macro-región", macro, grupo, minimo, con_error=False)
    lima = [f for f in rpp if f["macro"] == regiones.LIMA_Y_CALLAO]
    filas += _acierto("RPP sección Lima", "lima", lima, ACIERTO_LIMA_MINIMO)
    nacionales = [f for f in rpp if f["seccion"] in SECCIONES_NACIONALES_RPP]
    filas += _nacional("RPP nacionales", "política y economía", nacionales, NACIONAL_EN_NACIONALES_MINIMO)
    mundo = [f for f in rpp if f["seccion"] == SECCION_MUNDO_RPP]
    filas += _nacional("RPP nacionales", "mundo", mundo, NACIONAL_EN_MUNDO_MINIMO)

    eltiempo = _con_asignacion(
        [
            {**n, "macro": regiones.COSTA_NORTE}
            for n in notas
            if n["medio"] == "eltiempo"
            and referencias.mitad(n["id"]) == referencias.EVALUACION
            and seccion_principal(n["url"]) == referencias.SECCION_LOCAL_ELTIEMPO
        ]
    )
    filas += _acierto("El Tiempo local", "costa_norte", eltiempo, ELTIEMPO_LOCAL_MINIMO, con_error=False)

    andina = referencias.secciones_andina()
    for nombre, es_regional in (
        ("Andina regionales", lambda n: n["medio"] == "andina" and andina.get(n["id"]) == "regional"),
        (
            "Exitosa regiones",
            lambda n: n["medio"] == "exitosa" and seccion_principal(n["url"]) == referencias.SECCION_REGIONES_EXITOSA,
        ),
    ):
        grupo = _con_asignacion([dict(n) for n in notas if es_regional(n)])
        valor = proporcion(grupo, lambda n: bool(FUERA_DE_LIMA & set(n["asignadas"])))
        ok = valor >= FUERA_DE_LIMA_MINIMO
        filas.append(
            criterio(
                "Secciones regionales", f"{nombre}: fuera de Lima (n={len(grupo)})", valor, FUERA_DE_LIMA_MINIMO, ok
            )
        )
    filas += _corpus_oficial()
    return filas


def _corpus_oficial():
    """regiones_mencionadas sigue dando lo mismo que guardó el corpus oficial en los párrafos del ENFEN."""
    parrafos = [p for p in leer_csv(config.DIR_OFICIAL / "parrafos.csv") if p["fuente"] == "enfen"]
    iguales = proporcion(
        parrafos, lambda p: "|".join(sorted(regiones.regiones_mencionadas(p["texto"]))) == p["macroregiones"]
    )
    return [
        criterio("Corpus oficial", f"párrafos del ENFEN sin cambios (n={len(parrafos)})", iguales, 1.0, iguales == 1.0)
    ]


def informativo(filas_regiones, notas):
    """Distribución de las notas sobre El Niño (sin umbral)."""
    sobre_nino = {(n["medio"], n["id"]) for n in notas if n["sobre_nino"] == "1"}
    conteo = collections.Counter(
        m for f in filas_regiones if (f["medio"], f["id"]) in sobre_nino for m in f["macroregiones"]
    )
    total = len(sobre_nino) or 1
    detalle = " · ".join(f"{m} {n / total:.0%}" for m, n in conteo.most_common())
    return [criterio("Distribución (informativo)", f"notas sobre El Niño (n={len(sobre_nino)})", "", "", True, detalle)]


# ---------------------------------------------------------------- principal


def reporte(filas):
    for prueba in dict.fromkeys(f["prueba"] for f in filas):
        grupo = [f for f in filas if f["prueba"] == prueba]
        informativa = "informativo" in prueba
        log.info(f"\n{prueba} {'' if informativa else ('PASA' if all(f['pasa'] for f in grupo) else 'NO PASA')}")
        for f in grupo:
            marca = "·" if informativa else ("ok" if f["pasa"] else "NO")
            umbral = f" (umbral {f['umbral']})" if f["umbral"] != "" else ""
            log.info(f"  [{marca:2}] {f['criterio']}: {f['valor']}{umbral}")
            if f["detalle"]:
                log.info(f"       {f['detalle']}")


def main(argv=None):
    argparse.ArgumentParser(description="Macro-región de las notas ya leídas y su validación.").parse_args(argv)
    registro = configurar("region-notas")
    inicio = ahora()
    notas = referencias.notas_leidas()
    filas_regiones, errores = asignar_notas(notas)
    escribir_csv(config.DIR_NOTICIAS / "regiones.csv", esquemas.REGIONES_NOTAS, filas_regiones)
    log.info(f"Macro-región de {len(filas_regiones)} notas ({errores} con error) desde titular y resumen")
    validacion = validar(notas, referencias.referencia_rpp(notas)) + informativo(filas_regiones, notas)
    escribir_csv(config.DIR_REGION / "validacion.csv", VALIDACION, validacion)
    reporte(validacion)
    log.info(f"\nDuración: {(ahora() - inicio).total_seconds():.0f} s · registro: {registro.relative_to(config.RAIZ)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
