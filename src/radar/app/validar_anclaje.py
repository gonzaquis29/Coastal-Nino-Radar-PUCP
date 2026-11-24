"""«Alta» anclada al tema en Verificar (docs/app/definicion.md, sección 13): criterios V1 a V9.

python -m radar.app.validar_anclaje muestra   ->  los cuerpos de la prueba externa (50 por medio y grupo)
python -m radar.app.validar_anclaje cuerpos   ->  los lee en memoria, sin guardarlos (reanudable)
python -m radar.app.validar_anclaje validar   ->  prueba "App: Alta anclada" en data/processed/app/validacion.csv

La prueba externa son las notas de octubre a diciembre de 2025 de radar.noticias.externa, medidas con su mismo día en
2026 (el corpus oficial empieza el 18-dic-2025). La de 2026 (septiembre al corte) se repite solo como segunda vista.
No escribe en el registro de uso.
"""

import argparse
import collections
import datetime as dt
import logging
import threading

from radar import config
from radar.app import servicio as sv
from radar.app import tema_clima as tc
from radar.app import validar_tema as vt
from radar.comun import dominio
from radar.comun.archivos import escribir_csv, leer_csv
from radar.comun.candado import exclusivo
from radar.comun.energia import sin_suspension
from radar.comun.registro import configurar
from radar.nlp import reranker, semaforo, tfidf
from radar.nlp.viabilidad import registrada
from radar.noticias import externa
from radar.noticias.medios import MEDIOS
from radar.noticias.validar_texto import marcar_vistas, notas_vistas
from radar.noticias.viabilidad import _muestra, criterio, guardar

log = logging.getLogger(__name__)

PRUEBA = "App: Alta anclada"
MUESTRA = "externa-2025"
SEMILLA_CUERPOS = "anclaje-cuerpos-20261123"
CUERPOS_POR_MEDIO = 50
GRUPOS = (tc.TEMA, tc.CLIMA, tc.DURO, tc.OTRO)
MINIMO_GRUPO = 100  # con menos notas, el criterio del grupo es informativo (13.6)
COLUMNAS_MUESTRA = ("medio", "id", "grupo")
COLUMNAS_LECTURA = ("medio", "id", "grupo", "error", "pasa", "alta", "alta_anclada")

# Umbrales fijados en la sección 13.6 antes de construir
MAX_ALTA_DUROS, PROPORCION_DE_HOY = 0.02, 0.50  # V1 y V2
MAX_ALTA_OTROS_CORTO, MAX_ALTA_OTROS_CUERPO = 0.01, 0.02  # V3
MAX_ALTA_PERDIDA = 0.03  # V4 y V5: de las «Alta» de hoy, cuántas pasan a «Media»
MAX_SINTETICOS = 1  # V6, de 20

# Sintéticos nuevos, escritos el 23-nov antes de medir (distintos de los de las secciones 9, 10 y 12). Inventados.
OTRO_TEMA_GENERICO = (
    "Simulacro nacional de sismo: el Indeci pide preparar la mochila de emergencia",
    "Minsa declara alerta sanitaria por casos de tos ferina en Lima",
    "Bomberos atienden emergencia por incendio en un mercado de La Victoria",
    "Gobierno declara estado de emergencia en Trujillo por la inseguridad",
    "Evento cultural reúne a artesanos de la costa en Miraflores",
    "Alerta por estafas telefónicas: la Policía recomienda prevención",
    "Comunicado de la Federación: se suspende la fecha por falta de garantías",
    "Vigilancia epidemiológica del sarampión se refuerza en los colegios",
    "Aviso a los contribuyentes: la Sunat amplía el plazo de declaración",
    "Sismo de magnitud 4,8 se sintió en Arequipa sin causar daños",
)
OTRO_TEMA_ESPECIFICO_CON_OTRO_SENTIDO = (
    "Ola de robos de celulares preocupa a los vecinos de Comas",
    "Lluvia de goles en el clásico: Universitario gana 4 a 2",
    "El clima electoral se enrarece a una semana de la segunda vuelta",
    "Mar de fondo en el Congreso por la elección del Defensor del Pueblo",
    "Calor humano: miles acompañan la procesión del Señor de los Milagros",
    "Tormenta política tras la renuncia del ministro de Economía",
    "Temperatura de la campaña sube con el debate de candidatos",
    "Pesca milagrosa del delantero en el último minuto del partido",
    "Desborde de hinchas obliga a suspender el concierto en el estadio",
    "Sequía de goles del seleccionado preocupa al técnico",
)
DEL_TEMA_SIN_NINO = (
    "Senamhi pronostica lluvias de fuerte intensidad en la sierra norte desde el domingo",
    "Temperatura del mar frente a Piura sube dos grados sobre lo normal",
    "Huaicos interrumpen la Carretera Central a la altura de Matucana",
    "Desembarque de anchoveta cae en la primera temporada de pesca",
    "Río Piura alcanza el umbral rojo y preocupa a los vecinos de Castilla",
    "Calor intenso en Lima: el índice UV llegará a niveles extremos",
    "Inundaciones en Tumbes dejan 300 familias damnificadas",
    "Heladas en Puno: el Minsa reparte abrigo a los niños de las zonas altas",
    "Oleaje fuerte obliga a cerrar 15 puertos de la costa central",
    "Precipitaciones en Cajamarca superan el promedio del mes",
    "Imarpe detecta aguas cálidas en el litoral de Lambayeque",
    "Pescadores de Paita no pueden salir al mar por los fuertes vientos",
    "Friaje en Madre de Dios: la temperatura bajaría a 12 grados",
    "Lluvias intensas activan quebradas en el sur de Arequipa",
    "Sequía amenaza las siembras de arroz en el valle de Jequetepeque",
    "La temporada de lluvias empieza antes en la sierra sur, según el Senamhi",
    "Desborde del río Chancay inunda chacras en Lambayeque",
    "Varamiento de pelícanos en playas de Sechura por falta de alimento",
    "Temperaturas de hasta 34 grados se esperan en la costa norte este fin de semana",
    "Capturas de pota caen por el calentamiento del mar en Piura",
)


def ruta(nombre):
    return config.DIR_APP / f"anclaje-{nombre}.csv"


def fecha_2026(nota):
    """El mismo día un año después, como máximo el corte (13.4)."""
    d = dt.date.fromisoformat(nota["fecha_publicacion"][:10])
    if d.year == 2025:
        d = d.replace(year=2026)
    return min(d, config.FIN_CORTE).isoformat()


def clasificar(s, texto, fecha, largo):
    """(pasa el filtro de tema, «Alta» hoy, «Alta» con el anclaje)."""
    if not (dominio.nombra_el_fenomeno(texto) or dominio.en_texto(texto, largo)):
        return False, False, False
    r, _ = s.medir(texto, fecha)
    hoy = r["origen"] == "distancia" and r["banda"] == semaforo.CERCANO
    anclada = sv.anclar(r, texto, activo=True)
    return True, hoy, anclada["origen"] == "distancia" and anclada["banda"] == semaforo.CERCANO


def notas_externas():
    return leer_csv(externa.ARCHIVO)


def grupos_externos(notas):
    return tc.grupos(notas, set())


def muestra():
    if ruta("muestra").exists():
        log.info(f"La muestra ya existe en {ruta('muestra')}; no se elige otra.")
        return
    notas = notas_externas()
    g = grupos_externos(notas)
    filas = []
    for grupo in GRUPOS:
        for m in MEDIOS:
            del_medio = [n for n in notas if n["medio"] == m and g.get((n["medio"], n["id"])) == grupo]
            filas += [{"medio": n["medio"], "id": n["id"], "grupo": grupo}
                      for n in _muestra(del_medio, CUERPOS_POR_MEDIO, SEMILLA_CUERPOS, grupo, m)]  # fmt: skip
    escribir_csv(ruta("muestra"), COLUMNAS_MUESTRA, filas)
    log.info(f"Muestra de cuerpos: {collections.Counter(f['grupo'] for f in filas)}")


@exclusivo("radar.app.validar_anclaje")
def leer_cuerpos(s, lista, parar):
    """Lee los cuerpos en memoria y guarda solo tres datos derivados por nota."""

    def fila_de(nota, grupo, campos):
        fila = {"medio": nota["medio"], "id": nota["id"], "grupo": grupo, "error": ""}
        if not isinstance(campos, dict):
            return {**fila, "error": str(campos)[:200]}
        if campos["sin_texto"]:
            return {**fila, "error": "sin texto"}
        t, _ = tfidf.texto_de(campos)
        pasa, hoy, anclada = clasificar(s, t, fecha_2026(nota), len(t.split()) > semaforo.PALABRAS_CORTO)
        return fila | {"pasa": int(pasa), "alta": int(hoy), "alta_anclada": int(anclada)}

    with sin_suspension():
        tfidf.leer_cuerpos(lista, ruta("cuerpos"), COLUMNAS_LECTURA, fila_de, parar)
    return leer_csv(ruta("cuerpos"))


def lista_de_cuerpos():
    por_clave = {(n["medio"], n["id"]): n for n in notas_externas()}
    return [(por_clave[(f["medio"], f["id"])], f["grupo"]) for f in leer_csv(ruta("muestra"))]


def cuerpos():
    if not ruta("muestra").exists():
        raise SystemExit("Falta la muestra: python -m radar.app.validar_anclaje muestra")
    r = leer_cuerpos(sv.servicio(), lista_de_cuerpos(), threading.Event())
    if not isinstance(r, list):
        raise SystemExit(r)


def cortos(s, notas, grupo_de, fecha_de, por_plantilla=frozenset()):
    """{grupo: [(pasa, alta hoy, alta anclada)]} en corto; los grupos de por_plantilla, una nota por plantilla."""
    salida = {}
    for grupo in GRUPOS:
        lista = [n for n in notas if grupo_de.get((n["medio"], n["id"])) == grupo]
        if grupo in por_plantilla:
            lista = tc.una_por_plantilla(lista)
        salida[grupo] = [clasificar(s, reranker.texto_corto(n), fecha_de(n), False) for n in lista]
        log.info(f"Corto {grupo}: {len(lista)} notas")
    return salida


def alta(m, anclada):
    return sum(x[2] if anclada else x[1] for x in m)


def perdidas(m):
    """(de las «Alta» de hoy, cuántas pasan a «Media»; cuántas «Alta» había)."""
    return sum(x[1] and not x[2] for x in m), sum(x[1] for x in m)


def pct(k, n):
    return vt.texto(*vt.proporcion(k, n))


def criterios(c, cu, nombre_vista):
    """V1 a V5 con los resultados en corto (c) y en cuerpo (cu, puede faltar)."""
    filas = []

    def informativo(n):
        return n < MINIMO_GRUPO

    duros = c[tc.DURO]
    a_hoy, a_an = alta(duros, False), alta(duros, True)
    pasa = a_an / max(1, len(duros)) <= MAX_ALTA_DUROS and a_an <= PROPORCION_DE_HOY * a_hoy
    filas.append(
        (
            "V1. Negativos difíciles con «Alta», corto",
            pct(a_an, len(duros)),
            "≤ 2 % y ≤ 50 % de hoy",
            pasa,
            f"{a_an} de {len(duros)}; hoy {a_hoy}",
            informativo(len(duros)),
        )
    )
    if cu:
        d = cu[tc.DURO]
        a_hoy, a_an = alta(d, False), alta(d, True)
        filas.append(("V2. Negativos difíciles con «Alta», cuerpo", pct(a_an, len(d)), "≤ 2 % y no peor que hoy",
                      a_an / max(1, len(d)) <= MAX_ALTA_DUROS and a_an <= a_hoy, f"{a_an} de {len(d)}; hoy {a_hoy}",
                      informativo(len(d))))  # fmt: skip
    o = c[tc.OTRO]
    a_hoy, a_an = alta(o, False), alta(o, True)
    texto, pasa = pct(a_an, len(o)), a_an / max(1, len(o)) <= MAX_ALTA_OTROS_CORTO and a_an <= a_hoy
    detalle = f"corto {a_an} de {len(o)} (hoy {a_hoy})"
    if cu:
        oc = cu[tc.OTRO]
        b_hoy, b_an = alta(oc, False), alta(oc, True)
        texto += f" / {pct(b_an, len(oc))}"
        pasa = pasa and b_an / max(1, len(oc)) <= MAX_ALTA_OTROS_CUERPO and b_an <= b_hoy
        detalle += f"; cuerpo {b_an} de {len(oc)} (hoy {b_hoy})"
    filas.append(("V3. otros_temas con «Alta», corto / cuerpo", texto, "≤ 1 % / ≤ 2 % y no peor que hoy", pasa,
                  detalle, informativo(len(o))))  # fmt: skip
    for clave, grupo, nombre in (("V4", tc.CLIMA, "Clima y mar"), ("V5", tc.TEMA, "Sobre El Niño")):
        partes, pasa, valores = [(c[grupo], "corto")] + ([(cu[grupo], "cuerpo")] if cu else []), True, []
        for m, forma in partes:
            k, n = perdidas(m)
            pasa = pasa and k <= MAX_ALTA_PERDIDA * n
            valores.append(f"{forma} {k} de {n}")
        filas.append((f"{clave}. {nombre}: «Alta» que pasan a «Media»", "; ".join(valores), "≤ 3 % de sus «Alta»",
                      pasa, f"{len(c[grupo])} notas en corto", informativo(len(c[grupo]))))  # fmt: skip
    return [criterio(f"{PRUEBA}{nombre_vista}" + (" (informativo)" if inf else ""), n, v, u, True if inf else p, d)
            for n, v, u, p, d, inf in filas]  # fmt: skip


def validar(repetir=False):
    if not ruta("muestra").exists():
        raise SystemExit("Falta la muestra: python -m radar.app.validar_anclaje muestra")
    if registrada(MUESTRA) and not repetir:
        raise SystemExit(f"La prueba ya se miró ({MUESTRA} en notas_vistas.csv). Usa --repetir y decláralo.")
    s = sv.servicio()
    notas = notas_externas()
    g = grupos_externos(notas)
    log.info(f"Prueba externa: {collections.Counter(g.values())}")
    c = cortos(s, notas, g, fecha_2026, por_plantilla={tc.CLIMA})
    leidas = leer_cuerpos(s, lista_de_cuerpos(), threading.Event())  # reanuda si falta alguno
    if not isinstance(leidas, list):
        raise SystemExit(leidas)
    cu = {grupo: [(f["pasa"] == "1", f["alta"] == "1", f["alta_anclada"] == "1") for f in leidas
                  if f["grupo"] == grupo and not f["error"]] for grupo in GRUPOS}  # fmt: skip
    filas = criterios(c, cu, "")

    fecha = config.FIN_CORTE.isoformat()
    ajenos = [
        t for t in OTRO_TEMA_GENERICO + OTRO_TEMA_ESPECIFICO_CON_OTRO_SENTIDO if clasificar(s, t, fecha, False)[2]
    ]
    del_tema = [clasificar(s, t, fecha, False) for t in DEL_TEMA_SIN_NINO]
    bajan = [t for t, (_, hoy, an) in zip(DEL_TEMA_SIN_NINO, del_tema, strict=True) if hoy and not an]
    con_alta = sum(x[1] for x in del_tema)
    filas.append(criterio(PRUEBA, "V6. Sintéticos: de otros temas con «Alta» / del tema con «Alta» que pasa a «Media»",
                          f"{len(ajenos)} de 20 / {len(bajan)} de 20", "≤ 1 / ≤ 1",
                          len(ajenos) <= MAX_SINTETICOS and len(bajan) <= MAX_SINTETICOS,
                          "; ".join(ajenos + bajan) + f" (del tema con «Alta» hoy: {con_alta})"))  # fmt: skip

    # V7: 2026 de septiembre al corte, reutilizada (--repetir), solo en corto
    notas_2026 = leer_csv(config.DIR_NOTICIAS / "notas.csv")
    g26 = tc.grupos(notas_2026, set())
    prueba_2026 = [n for n in notas_2026 if not tc.en_entrenamiento(n)]
    c26 = cortos(s, prueba_2026, g26, lambda n: n["fecha_publicacion"][:10], por_plantilla={tc.CLIMA})
    filas += [f | {"prueba": f"{PRUEBA} (informativo)", "criterio": f"V7 (2026 reutilizada). {f['criterio']}",
                   "pasa": True} for f in criterios(c26, None, "")]  # fmt: skip
    f9 = vt.f6()
    filas.append(criterio(PRUEBA, "V9. Preguntar sin cambios (el anclaje solo está en Verificar)", f9["valor"],
                          "0 cambios", f9["valor"] == "0 cambios", f9["detalle"]))  # fmt: skip
    guardar(filas, config.DIR_APP / "validacion.csv")
    for f in filas:
        log.info(f"[{'ok' if f['pasa'] else 'NO'}] {f['criterio']}: {f['valor']} (umbral {f['umbral']}) {f['detalle']}")
    if not registrada(MUESTRA):
        vistas = notas_vistas()
        marcar_vistas([n for n in notas if (n["medio"], n["id"]) in g and (n["medio"], n["id"]) not in vistas], MUESTRA)


def main(argv=None):
    ap = argparse.ArgumentParser(description="«Alta» anclada al tema en Verificar: V1 a V9 (sección 13).")
    ap.add_argument("accion", choices=("muestra", "cuerpos", "validar"))
    ap.add_argument("--repetir", action="store_true", help="volver a medir una prueba ya mirada (se declara)")
    a = ap.parse_args(argv)
    configurar("app-anclaje")
    if a.accion == "validar":
        validar(a.repetir)
    else:
        {"muestra": muestra, "cuerpos": cuerpos}[a.accion]()


if __name__ == "__main__":
    main()
