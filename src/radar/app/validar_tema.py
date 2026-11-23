"""Filtro de tema de Verificar (docs/app/definicion.md, sección 9): criterios F1 a F6.

python -m radar.app.validar_tema muestra   ->  elige las notas (todas las elegibles; los cuerpos, 25 por medio)
python -m radar.app.validar_tema validar   ->  guarda la prueba "App: tema" en data/processed/app/validacion.csv

Se mira una sola vez: al terminar, las notas usadas pasan a config/notas_vistas.csv (muestra "validacion-tema").
Si un criterio no pasa y se ajusta el filtro, la segunda medición se corre con --repetir y se declara.
"""

import argparse
import collections
import logging
import math
import re
import subprocess
import threading

from radar import config
from radar.agente import agente
from radar.app import servicio
from radar.comun import dominio
from radar.comun.archivos import escribir_csv, leer_csv
from radar.comun.candado import exclusivo
from radar.comun.energia import sin_suspension
from radar.comun.registro import configurar
from radar.comun.texto import sin_tildes
from radar.nlp import reranker, semaforo, tfidf
from radar.nlp.viabilidad import registrada
from radar.noticias.medios import MEDIOS
from radar.noticias.validar_texto import marcar_vistas, notas_vistas
from radar.noticias.viabilidad import _muestra, criterio, guardar

log = logging.getLogger(__name__)
PRUEBA = "App: tema"
MUESTRA = "validacion-tema"
DIAGNOSTICO = ("diagnostico-fuera-de-tema", "diagnostico-fuera-de-tema-positivos")
SEMILLA_CUERPOS = "tema-cuerpos-20261123"
CUERPOS_POR_MEDIO = 25
FECHA_SINTETICOS = "2026-11-22"
MACROREGION = "lima"
COLUMNAS_MUESTRA = ("medio", "id", "grupo", "forma")
COLUMNAS_LECTURA = ("medio", "id", "grupo", "error", "palabras", "en_tema", "tipo", "nivel")
NEGATIVO, POSITIVO = "negativo", "positivo"
CORTO, CUERPO = "corto", "cuerpo"

# Umbrales fijados en la sección 9.5 antes de construir
MAX_ALTA_NEGATIVOS = 0.02
MAX_FUERA_POSITIVOS_CORTO = 0.10
MAX_FUERA_POSITIVOS_CUERPO = 0.05
MAX_SINTETICOS_DEL_TEMA_FUERA = 1
A4_MIN_FUERA, A4_MAX_ABSTENCION = 0.90, 0.05

# Sintéticos nuevos, escritos el 23-nov antes de medir (distintos de los de desarrollo). Todos inventados.
NINO_OTRO_SENTIDO = (
    "Niño de 7 años gana concurso nacional de matemáticas",
    "Un niño fue hallado sano y salvo tras perderse en un parque",
    "El niño Jesús recorre las calles de Cusco en procesión",
    "Campaña de vacunación para niños menores de cinco años",
    "Hospital del Niño recibe nuevos equipos médicos",
    "Niña peruana destaca en torneo de ajedrez en Brasil",
    "El niño prodigio del violín ofrecerá un concierto en Lima",
    "Padres denuncian que un niño fue agredido en el colegio",
    "Día del Niño por Nacer: actividades en todo el país",
    "La niña que vende flores en el mercado conmovió a todos",
)
FENOMENO_BIEN_ESCRITO = (
    "El Niño costero se mantendría débil hasta marzo",
    "ENFEN: El Niño podría llegar a moderado en el verano",
    "Fenómeno El Niño: cómo prepararse en casa",
    "Agricultores de Piura temen los efectos del Niño costero",
    "El fenómeno del Niño afectaría la pesca en Paita",
    "La Niña en el Pacífico central y su efecto en Perú",
    "Comisión del ENFEN actualiza su pronóstico de El Niño",
    "Colegios de Tumbes se preparan ante El Niño",
    "¿Qué es el Niño costero y en qué se diferencia del global?",
    "El Niño global sigue neutro según la NOAA",
)
DEL_TEMA_SIN_NINO = (
    "Calor intenso en Chiclayo: temperatura llegó a 35 grados",
    "Lluvias torrenciales afectan caminos rurales en Cajamarca",
    "Pescadores artesanales de Sechura reportan poca pesca",
    "El mar de Máncora está más cálido que de costumbre",
    "Oleaje fuerte obliga a cerrar puertos en el litoral",
    "Senamhi prevé noches más cálidas en la costa central",
    "Desborde del río Tumbes afecta cultivos de arroz",
    "Indeci instala módulos de vivienda tras inundaciones",
    "Huayco arrasa con casas en una quebrada de Chosica",
    "La sequía golpea a los productores de mango en Piura",
)


def ruta(nombre):
    return config.DIR_APP / f"tema-{nombre}.csv"


def elegir(notas, vistas, control):
    """[(nota, grupo, forma)]: todas en corto y 25 por medio en cuerpo, para negativos y positivos."""
    diagnostico = {k for m in DIAGNOSTICO for k in registrada(m)}
    negativos = semaforo.negativos_elegibles(notas, vistas, control)
    positivos = [n for n in notas if n["sobre_nino"] == "1" and (n["medio"], n["id"]) not in diagnostico]
    salida = []
    for grupo, lista in ((NEGATIVO, negativos), (POSITIVO, positivos)):
        salida += [(n, grupo, CORTO) for n in lista]
        for m in MEDIOS:
            del_medio = [n for n in lista if n["medio"] == m]
            salida += [(n, grupo, CUERPO) for n in _muestra(del_medio, CUERPOS_POR_MEDIO, SEMILLA_CUERPOS, grupo, m)]
    return salida


def muestra():
    if ruta("muestra").exists():
        log.info(f"La muestra ya existe en {ruta('muestra')}; no se elige otra.")
        return
    notas = leer_csv(config.DIR_NOTICIAS / "notas.csv")
    elegidas = elegir(notas, notas_vistas(), leer_csv(config.DIR_NOTICIAS / "control_negativo.csv"))
    escribir_csv(ruta("muestra"), COLUMNAS_MUESTRA,
                 [{"medio": n["medio"], "id": n["id"], "grupo": g, "forma": f} for n, g, f in elegidas])  # fmt: skip
    log.info(f"Muestra: {collections.Counter((g, f) for _, g, f in elegidas)}")


def proporcion(k, n):
    """(proporción, IC de Wilson al 95 %)."""
    if not n:
        return 0.0, (0.0, 0.0)
    p, z = k / n, 1.96
    centro = (p + z * z / (2 * n)) / (1 + z * z / n)
    margen = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return p, (max(0.0, centro - margen), min(1.0, centro + margen))


def texto(p, ic):
    return f"{p * 100:.2f} % (IC {ic[0] * 100:.2f} a {ic[1] * 100:.2f})".replace(".", ",")


def cortos(s, lista):
    """{grupo: (n, fuera, alta)} en corto (titular con resumen, como S3). La cercanía solo se calcula si pasa."""
    n, fuera, alta = collections.Counter(), collections.Counter(), collections.Counter()
    for nota, grupo in lista:
        t = reranker.texto_corto(nota)
        n[grupo] += 1
        if not dominio.en_texto(t, largo=len(t.split()) > semaforo.PALABRAS_CORTO):
            fuera[grupo] += 1
            continue
        r = s.verificar(t, nota["fecha_publicacion"][:10], MACROREGION)
        fuera[grupo] += r["tipo"] == "fuera_de_tema"
        alta[grupo] += r["tipo"] == "cercania" and r["nivel"] == "cercano"
    return {g: (n[g], fuera[g], alta[g]) for g in n}


@exclusivo("radar.app.validar_tema")
def leer_cuerpos(s, lista, parar):
    """Lee en memoria los cuerpos (sin guardarlos) y anota solo el resultado de Verificar."""

    def fila_de(nota, grupo, campos):
        fila = {"medio": nota["medio"], "id": nota["id"], "grupo": grupo, "error": ""}
        if not isinstance(campos, dict):
            return {**fila, "error": str(campos)[:200]}
        if campos["sin_texto"]:
            return {**fila, "error": "sin texto"}
        t, _ = tfidf.texto_de(campos)
        r = s.verificar(t, nota["fecha_publicacion"][:10], MACROREGION)
        return fila | {"palabras": r["palabras"], "en_tema": int(r["tipo"] != "fuera_de_tema"), "tipo": r["tipo"],
                       "nivel": r["nivel"] or ""}  # fmt: skip

    with sin_suspension():
        tfidf.leer_cuerpos(lista, ruta("cuerpos"), COLUMNAS_LECTURA, fila_de, parar)
    return leer_csv(ruta("cuerpos"))


def dominio_anterior():
    """La expresión de dominio del agente antes del 23-nov (git), para comparar sus decisiones (F6)."""
    fuente = subprocess.run(["git", "show", "1789cf8:src/radar/agente/agente.py"], capture_output=True, text=True,
                            encoding="utf-8", cwd=config.RAIZ, check=True).stdout  # fmt: skip
    cuerpo = re.search(r"DOMINIO = re\.compile\(\n(.*?)\n    re\.I,\n\)", fuente, re.S).group(1)
    return re.compile("".join(re.findall(r'r"([^"]*)"', cuerpo)), re.I)


def f6():
    antes = dominio_anterior()
    preguntas = [f for a in ("", "_b", "_c", "_dev") for f in leer_csv(config.DIR_CONFIG / f"agente_preguntas{a}.csv")]
    cambios = [p for p in preguntas if bool(antes.search(sin_tildes(p["texto"]))) != dominio.en_pregunta(p["texto"])]
    fuera = [p for p in preguntas if p["herramienta"] == agente.FUERA]
    validas = [p for p in preguntas if p["herramienta"] != agente.FUERA]
    a4 = sum(not dominio.en_pregunta(p["texto"]) for p in fuera) / len(fuera)
    abstencion = sum(not dominio.en_pregunta(p["texto"]) for p in validas) / len(validas)
    a4_t, abst_t = f"{a4:.3f}".replace(".", ","), f"{abstencion:.3f}".replace(".", ",")
    detalle = f"A4 {a4_t} con {len(fuera)} fuera de alcance; abstención {abst_t} con {len(validas)} válidas"
    if cambios:
        detalle += "; cambian: " + "; ".join(f"{p['id']} ({p['texto'][:60]})" for p in cambios)
    pasa = a4 >= A4_MIN_FUERA and abstencion <= A4_MAX_ABSTENCION
    nombre = "F6. Preguntar: A4 con las preguntas ya vistas; los cambios se revisan uno a uno"
    umbral = "A4 ≥ 0,90 y abstención ≤ 0,05"
    return criterio(PRUEBA, nombre, f"{len(cambios)} cambios", umbral, pasa, detalle)


def validar(repetir=False):
    if not ruta("muestra").exists():
        raise SystemExit("Falta la muestra: python -m radar.app.validar_tema muestra")
    if registrada(MUESTRA) and not repetir:
        raise SystemExit("La muestra ya se usó; una segunda medición va con --repetir y se declara")
    por_clave = {(n["medio"], n["id"]): n for n in leer_csv(config.DIR_NOTICIAS / "notas.csv")}
    elegidas = [(por_clave[(f["medio"], f["id"])], f["grupo"], f["forma"]) for f in leer_csv(ruta("muestra"))]
    s = servicio.servicio()
    nota = " (segunda medición, --repetir)" if repetir else ""

    c = cortos(s, [(n, g) for n, g, f in elegidas if f == CORTO])
    leidas = leer_cuerpos(s, [(n, g) for n, g, f in elegidas if f == CUERPO], threading.Event())
    if not isinstance(leidas, list):
        raise SystemExit(leidas)
    ok = [f for f in leidas if not f["error"]]
    cu = {g: (sum(f["grupo"] == g for f in ok), sum(f["grupo"] == g and f["en_tema"] == "0" for f in ok),
              sum(f["grupo"] == g and f["tipo"] == "cercania" and f["nivel"] == "cercano" for f in ok))
          for g in (NEGATIVO, POSITIVO)}  # fmt: skip
    errores = len(leidas) - len(ok)

    filas = []
    for forma, datos in ((CORTO, c), (CUERPO, cu)):
        n, _, alta = datos[NEGATIVO]
        p, ic = proporcion(alta, n)
        filas.append(criterio(PRUEBA, f"F1. Negativos con «Alta», {forma}{nota}", texto(p, ic),
                              f"≤ {MAX_ALTA_NEGATIVOS:.0%}", p <= MAX_ALTA_NEGATIVOS, f"{alta} de {n}"))  # fmt: skip
    n, fuera, _ = c[POSITIVO]
    p, ic = proporcion(fuera, n)
    corte = [x for x, g, f in elegidas if g == POSITIVO and f == CORTO and (x["medio"], x["id"]) not in notas_vistas()]
    fuera_corte = sum(not dominio.en_texto(reranker.texto_corto(x), largo=False) for x in corte)
    filas.append(criterio(PRUEBA, f"F2. Positivos que el filtro deja fuera, corto{nota}", texto(p, ic),
                          f"≤ {MAX_FUERA_POSITIVOS_CORTO:.0%}", p <= MAX_FUERA_POSITIVOS_CORTO,
                          f"{fuera} de {n}; las del corte sin usar: {fuera_corte} de {len(corte)}"))  # fmt: skip
    n, fuera, _ = cu[POSITIVO]
    p, ic = proporcion(fuera, n)
    filas.append(criterio(PRUEBA, f"F3. Positivos que el filtro deja fuera, cuerpo{nota}", texto(p, ic),
                          f"≤ {MAX_FUERA_POSITIVOS_CUERPO:.0%}", p <= MAX_FUERA_POSITIVOS_CUERPO,
                          f"{fuera} de {n}; cuerpos que no se pudieron leer: {errores}"))  # fmt: skip

    otro = [t for t in NINO_OTRO_SENTIDO if dominio.en_texto(t, largo=False)]
    perdidas = [t for t in FENOMENO_BIEN_ESCRITO if not dominio.en_texto(t, largo=False)]
    filas.append(criterio(PRUEBA, "F4. «Niño» con otro sentido que pasa / el fenómeno que no pasa",
                          f"{len(otro)} / {len(perdidas)}", "0 / 0", not otro and not perdidas,
                          "; ".join(otro + perdidas)))  # fmt: skip
    sin_nino = [t for t in DEL_TEMA_SIN_NINO if not dominio.en_texto(t, largo=False)]
    filas.append(criterio(PRUEBA, "F5. Textos del tema sin «El Niño» que quedan fuera",
                          f"{len(sin_nino)} de {len(DEL_TEMA_SIN_NINO)}", f"≤ {MAX_SINTETICOS_DEL_TEMA_FUERA}",
                          len(sin_nino) <= MAX_SINTETICOS_DEL_TEMA_FUERA, "; ".join(sin_nino)))  # fmt: skip
    filas.append(f6())
    guardar(filas, config.DIR_APP / "validacion.csv")
    if not repetir:
        usadas = {(n["medio"], n["id"]): n for n, _, _ in elegidas}
        vistas = notas_vistas()
        marcar_vistas([n for k, n in usadas.items() if k not in vistas], MUESTRA)
    for f in filas:
        log.info(f"[{'ok' if f['pasa'] else 'NO'}] {f['criterio']}: {f['valor']} (umbral {f['umbral']}) {f['detalle']}")


def main(argv=None):
    ap = argparse.ArgumentParser(description="Filtro de tema de Verificar: F1 a F6 (sección 9).")
    ap.add_argument("accion", choices=("muestra", "validar"))
    ap.add_argument("--repetir", action="store_true", help="segunda medición, declarada")
    a = ap.parse_args(argv)
    configurar("app-tema")
    muestra() if a.accion == "muestra" else validar(a.repetir)


if __name__ == "__main__":
    main()
