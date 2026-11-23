"""Clasificador de tema de Verificar (docs/app/definicion.md, sección 10): criterios C1 a C8.

python -m radar.app.tema entrenar   ->  data/processed/app/tema-modelo.joblib (solo enero a agosto)
python -m radar.app.tema muestra    ->  los cuerpos de la prueba (100 por medio y grupo)
python -m radar.app.tema cuerpos    ->  los lee en memoria (puede correr mientras se entrena)
python -m radar.app.tema validar    ->  prueba "App: clasificador de tema" en data/processed/app/validacion.csv

Etiquetas automáticas: tema = sobre_nino (radar.noticias.rasgos); otro tema = otros_temas (radar.nlp.semaforo); la
zona gris (sin El Niño, con términos de clima en el cuerpo) no entra al entrenamiento. Rasgos: el vector del texto con
el mismo minilm del semáforo, que la app ya carga. La prueba (septiembre al corte) se mira una sola vez.
"""

import argparse
import collections
import functools
import logging
import threading

import joblib
import numpy as np

from radar import config
from radar.app import validar_tema as vt
from radar.comun import dominio
from radar.comun.archivos import escribir_csv, leer_csv
from radar.comun.candado import exclusivo
from radar.comun.energia import sin_suspension
from radar.comun.registro import configurar
from radar.nlp import reranker, semaforo, tfidf
from radar.noticias.medios import MEDIOS
from radar.noticias.viabilidad import _muestra, criterio, guardar

log = logging.getLogger(__name__)
PRUEBA = "App: clasificador de tema"
ARCHIVO_MODELO = config.DIR_APP / "tema-modelo.joblib"
ULTIMO_MES_ENTRENA = "2026-08"  # entrenar con enero a agosto; probar con septiembre al corte
GRUPOS_CV = 5
VALORES_C = (0.1, 1.0, 10.0)
MAX_PASAN_NEGATIVOS_CV = 0.01  # el umbral τ: el menor que deja pasar a lo sumo el 1 % de otros temas en la CV
SEMILLA = 20261123
SEMILLA_CUERPOS = "clasificador-tema-cuerpos-20261123"
CUERPOS_POR_MEDIO = 100
TEMA, OTRO, GRIS = "tema", "otro", "gris"
COLUMNAS_MUESTRA = ("medio", "id", "grupo")
# Del cuerpo solo quedan datos derivados: el filtro de la sección 9, la banda del semáforo y el vector del inicio
COLUMNAS_LECTURA = ("medio", "id", "grupo", "error", "palabras", "fenomeno", "pasa_a", "origen", "banda", "vector")
HILOS_LECTURA = 4  # la lectura corre junto al entrenamiento: sin saturar los núcleos

# Umbrales fijados en la sección 10.4 antes de construir
MAX_ALTA_CORTO, MAX_ALTA_CUERPO = 0.01, 0.02
MAX_FUERA_CORTO, MAX_FUERA_CUERPO = 0.05, 0.05
MAX_SINTETICOS_DEL_TEMA_FUERA = 1

# Sintéticos nuevos, escritos el 23-nov antes de medir (distintos de los de las secciones 9.4 y 9.5). Inventados.
NINO_OTRO_SENTIDO = (
    "Niño de 9 años salva a su hermano de morir ahogado",
    "Bomberos rescatan a un niño atrapado en un ascensor",
    "El niño Dios de la parroquia fue restaurado para Navidad",
    "Colegio premia a la niña que creó un robot de reciclaje",
    "Ministerio de Salud vacuna a niños contra el sarampión",
    "Un niño de Ayacucho llega a la final de un concurso de canto",
    "Niña con discapacidad recibe una silla de ruedas nueva",
    "Juguetes para el niño: ofertas por el Día del Padre",
    "La historia del niño lustrabotas que se hizo doctor",
    "Policía encuentra a la niña reportada como desaparecida",
)
FENOMENO_BIEN_ESCRITO = (
    "El Niño costero podría intensificarse en febrero",
    "Fenómeno El Niño: el agro del norte se prepara",
    "Ministerio de la Producción evalúa el impacto de El Niño en la pesca",
    "La Niña costera ya no se presenta este año, dice el ENFEN",
    "Tumbes refuerza diques por el fenómeno del Niño",
    "Expertos explican cómo se forma El Niño costero",
    "El Niño y las lluvias: lo que se espera en Lambayeque",
    "Gobierno declara emergencia preventiva por El Niño",
    "Arequipa no sería afectada por El Niño costero",
    "El ENFEN descarta un Niño fuerte para este verano",
)
DEL_TEMA_SIN_NINO = (
    "Temperatura del agua en Talara supera los 26 grados",
    "Lluvias de verano dejan carreteras bloqueadas en Áncash",
    "Flota pesquera regresa al puerto sin captura de anchoveta",
    "Senamhi alerta de calor extremo en la costa sur",
    "Río Chira aumenta su caudal y preocupa a los agricultores",
    "Desembarco de pota cae por el mar más caliente",
    "Familias de Piura pierden sus casas por la inundación",
    "Indeci entrega kits de ayuda a damnificados por huaicos",
    "Oleaje anómalo cierra 20 puertos del litoral norte",
    "Friaje golpea a comunidades de la selva central",
)


def ruta(nombre):
    return config.DIR_APP / f"tema-c-{nombre}.csv"


@functools.cache
def modelo_de_texto():
    """El minilm del semáforo, que la app ya carga (no se agrega otro modelo)."""
    return semaforo._semaforo().modelo


def inicio(texto):
    """El texto si es corto; si es largo, sus primeras PALABRAS_CORTO palabras (el tema está al inicio)."""
    palabras = texto.split()
    return texto if len(palabras) <= semaforo.PALABRAS_CORTO else " ".join(palabras[: semaforo.PALABRAS_CORTO])


def vectores(textos, modelo=None, lote=256):
    """Un vector normalizado por texto: el promedio de sus tramos."""
    modelo = modelo or modelo_de_texto()
    tramos, de = [], []
    for i, t in enumerate(textos):
        ts = modelo.tramos(t) or [t]
        tramos += ts
        de += [i] * len(ts)
    v = np.vstack([modelo.embeber(tramos[i : i + lote]) for i in range(0, len(tramos), lote)]) if tramos else None
    de = np.array(de)
    salida = np.vstack([v[de == i].mean(0) for i in range(len(textos))]) if textos else np.zeros((0, 1))
    return salida / np.linalg.norm(salida, axis=1, keepdims=True).clip(1e-12)


def grupos(notas):
    """{(medio, id): tema | otro | gris} con las etiquetas automáticas."""
    otros = {(n["medio"], n["id"]) for n in semaforo.negativos_elegibles(notas, set(), [])}
    return {(n["medio"], n["id"]): TEMA if n["sobre_nino"] == "1" else (OTRO if (n["medio"], n["id"]) in otros
                                                                       else GRIS) for n in notas}  # fmt: skip


def en_entrenamiento(nota):
    return nota["fecha_publicacion"][:7] <= ULTIMO_MES_ENTRENA


def umbral_de(probabilidades_negativas):
    """El menor τ que deja pasar a lo sumo MAX_PASAN_NEGATIVOS_CV de los negativos."""
    return float(np.quantile(probabilidades_negativas, 1 - MAX_PASAN_NEGATIVOS_CV, method="higher"))


def elegir_modelo(x, y):
    """(C, τ, average precision por C) con validación cruzada estratificada solo sobre el entrenamiento."""
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import average_precision_score
    from sklearn.model_selection import StratifiedKFold

    cv = StratifiedKFold(n_splits=GRUPOS_CV, shuffle=True, random_state=SEMILLA)
    resultados = {}
    for c in VALORES_C:
        fuera = np.zeros(len(y))
        for a, b in cv.split(x, y):
            m = LogisticRegression(C=c, class_weight="balanced", max_iter=3000).fit(x[a], y[a])
            fuera[b] = m.predict_proba(x[b])[:, 1]
        resultados[c] = (average_precision_score(y, fuera), fuera)
    mejor = max(VALORES_C, key=lambda c: resultados[c][0])
    return mejor, umbral_de(resultados[mejor][1][y == 0]), {c: round(r[0], 4) for c, r in resultados.items()}


def entrenar():
    from sklearn.linear_model import LogisticRegression

    notas = leer_csv(config.DIR_NOTICIAS / "notas.csv")
    g = grupos(notas)
    entrena = [n for n in notas if en_entrenamiento(n) and g[(n["medio"], n["id"])] != GRIS]
    y = np.array([g[(n["medio"], n["id"])] == TEMA for n in entrena], dtype=int)
    log.info(f"Entrenamiento: {len(entrena)} notas ({y.sum()} del tema)")
    x = vectores([reranker.texto_corto(n) for n in entrena])
    c, tau, ap = elegir_modelo(x, y)
    m = LogisticRegression(C=c, class_weight="balanced", max_iter=3000).fit(x, y)
    joblib.dump({"coef": m.coef_[0], "intercepto": float(m.intercept_[0]), "C": c, "tau": tau, "ap_cv": ap,
                 "n": len(entrena), "n_tema": int(y.sum()), "hasta": ULTIMO_MES_ENTRENA}, ARCHIVO_MODELO)  # fmt: skip
    log.info(f"Modelo: C {c}, τ {tau:.4f}, average precision en CV {ap} -> {ARCHIVO_MODELO}")


class Clasificador:
    def __init__(self, ruta_modelo=ARCHIVO_MODELO, modelo=None):
        d = joblib.load(ruta_modelo)
        self.coef, self.intercepto, self.tau, self.modelo = d["coef"], d["intercepto"], d["tau"], modelo

    def probabilidades(self, textos):
        z = vectores([inicio(t) for t in textos], self.modelo) @ self.coef + self.intercepto
        return 1 / (1 + np.exp(-z))

    def en_tema(self, texto):
        """Nombra el fenómeno, o el clasificador lo pone en el tema."""
        return dominio.nombra_el_fenomeno(texto) or bool(self.probabilidades([texto])[0] >= self.tau)


@functools.cache
def clasificador():
    return Clasificador()


def muestra():
    if ruta("muestra").exists():
        log.info(f"La muestra ya existe en {ruta('muestra')}; no se elige otra.")
        return
    notas = leer_csv(config.DIR_NOTICIAS / "notas.csv")
    g = grupos(notas)
    prueba = [n for n in notas if not en_entrenamiento(n)]
    filas = []
    for grupo in (TEMA, OTRO):
        for m in MEDIOS:
            del_medio = [n for n in prueba if n["medio"] == m and g[(n["medio"], n["id"])] == grupo]
            filas += [{"medio": n["medio"], "id": n["id"], "grupo": grupo}
                      for n in _muestra(del_medio, CUERPOS_POR_MEDIO, SEMILLA_CUERPOS, grupo, m)]  # fmt: skip
    escribir_csv(ruta("muestra"), COLUMNAS_MUESTRA, filas)
    log.info(f"Muestra de cuerpos: {collections.Counter(f['grupo'] for f in filas)}")


def medir_textos(s, k, textos_fechas):
    """[(pasa_c, pasa_a, alta)] por texto: el semáforo solo se calcula si alguno de los dos filtros lo deja pasar."""
    textos = [t for t, _ in textos_fechas]
    prob = k.probabilidades(textos)
    salida = []
    for (t, fecha), p in zip(textos_fechas, prob, strict=True):
        pasa_c = dominio.nombra_el_fenomeno(t) or bool(p >= k.tau)
        pasa_a = dominio.en_texto(t, largo=len(t.split()) > semaforo.PALABRAS_CORTO)
        alta = False
        if pasa_c or pasa_a:
            r, _ = s.medir(t, fecha)
            alta = r["origen"] == "distancia" and r["banda"] == "cercano"
        salida.append((pasa_c, pasa_a, alta))
    return salida


@exclusivo("radar.app.tema")
def leer_cuerpos(s, lista, parar, destino=None):
    """Lee los cuerpos en memoria (sin guardarlos). No necesita el modelo: guarda el vector del inicio del texto, y
    el clasificador se aplica después; así la lectura puede correr mientras se entrena."""
    destino = destino or ruta("cuerpos")
    modelo = s.semaforo.modelo

    def fila_de(nota, grupo, campos):
        fila = {"medio": nota["medio"], "id": nota["id"], "grupo": grupo, "error": ""}
        if not isinstance(campos, dict):
            return {**fila, "error": str(campos)[:200]}
        if campos["sin_texto"]:
            return {**fila, "error": "sin texto"}
        t, _ = tfidf.texto_de(campos)
        r, _ = s.medir(t, nota["fecha_publicacion"][:10])
        v = vectores([inicio(t)], modelo)[0]
        return fila | {"palabras": len(t.split()), "fenomeno": int(dominio.nombra_el_fenomeno(t)),
                       "pasa_a": int(dominio.en_texto(t, largo=len(t.split()) > semaforo.PALABRAS_CORTO)),
                       "origen": r["origen"], "banda": r.get("banda") or "",
                       "vector": " ".join(f"{x:.6f}" for x in v)}  # fmt: skip

    with sin_suspension():
        tfidf.leer_cuerpos(lista, destino, COLUMNAS_LECTURA, fila_de, parar)
    return leer_csv(destino)


def lista_de_cuerpos(notas):
    por_clave = {(n["medio"], n["id"]): n for n in notas}
    return [(por_clave[(f["medio"], f["id"])], f["grupo"]) for f in leer_csv(ruta("muestra"))]


def cuerpos():
    """Solo la lectura de los cuerpos de la prueba (reanudable); se puede correr mientras se entrena."""
    import torch

    from radar.app import servicio

    torch.set_num_threads(HILOS_LECTURA)
    if not ruta("muestra").exists():
        raise SystemExit("Falta la muestra: python -m radar.app.tema muestra")
    r = leer_cuerpos(servicio.servicio(), lista_de_cuerpos(leer_csv(config.DIR_NOTICIAS / "notas.csv")),
                     threading.Event())  # fmt: skip
    if not isinstance(r, list):
        raise SystemExit(r)


def pasa_c_de(fila, k):
    if fila["fenomeno"] == "1":
        return True
    v = np.array([float(x) for x in fila["vector"].split()])
    return bool(1 / (1 + np.exp(-(v @ k.coef + k.intercepto))) >= k.tau)


def tasa(k_, n, nombre, umbral, maximo, detalle=""):
    p, ic = vt.proporcion(k_, n)
    return criterio(PRUEBA, nombre, vt.texto(p, ic), umbral, p <= maximo, f"{k_} de {n}{detalle}")


def validar():
    if not ARCHIVO_MODELO.exists():
        raise SystemExit("Falta el modelo: python -m radar.app.tema entrenar")
    if not ruta("muestra").exists():
        raise SystemExit("Falta la muestra: python -m radar.app.tema muestra")
    from radar.app import servicio

    s = servicio.servicio()
    k = Clasificador(modelo=modelo_de_texto())
    notas = leer_csv(config.DIR_NOTICIAS / "notas.csv")
    g = grupos(notas)
    prueba = [n for n in notas if not en_entrenamiento(n)]
    filas = []

    medidos = {}
    for grupo in (TEMA, OTRO, GRIS):
        lista = [n for n in prueba if g[(n["medio"], n["id"])] == grupo]
        medidos[grupo] = medir_textos(s, k, [(reranker.texto_corto(n), n["fecha_publicacion"][:10]) for n in lista])
        log.info(f"Corto {grupo}: {len(lista)} notas")

    otros = medidos[OTRO]
    alta_c, alta_a = sum(pc and al for pc, _, al in otros), sum(pa and al for _, pa, al in otros)
    nombre, umbral = "C1. Otros temas con «Alta», corto (prueba)", "≤ 1 % y no peor que la sección 9"
    fila = tasa(alta_c, len(otros), nombre, umbral, MAX_ALTA_CORTO, f"; sección 9 en las mismas notas: {alta_a}")
    fila["pasa"] = fila["pasa"] and alta_c <= alta_a
    filas.append(fila)

    leidas = leer_cuerpos(s, lista_de_cuerpos(notas), threading.Event())  # reanuda si falta alguno
    if not isinstance(leidas, list):
        raise SystemExit(leidas)
    ok = [f | {"pasa_c": str(int(pasa_c_de(f, k))), "alta": f["origen"] == "distancia" and f["banda"] == "cercano"}
          for f in leidas if not f["error"]]  # fmt: skip
    neg = [f for f in ok if f["grupo"] == OTRO]
    alta_cu = sum(f["pasa_c"] == "1" and f["alta"] for f in neg)
    alta_cu_a = sum(f["pasa_a"] == "1" and f["alta"] for f in neg)
    filas.append(tasa(alta_cu, len(neg), "C2. Otros temas con «Alta», cuerpo", "≤ 2 %", MAX_ALTA_CUERPO,
                      f"; sección 9 en los mismos: {alta_cu_a}; sin leer: {len(leidas) - len(ok)}"))  # fmt: skip

    tema = medidos[TEMA]
    fuera_c, fuera_a = sum(not pc for pc, _, _ in tema), sum(not pa for _, pa, _ in tema)
    nombre, umbral = "C3. Notas del tema que quedan fuera, corto (prueba)", "≤ 5 % y no peor que la sección 9"
    fila = tasa(fuera_c, len(tema), nombre, umbral, MAX_FUERA_CORTO, f"; sección 9 en las mismas notas: {fuera_a}")
    fila["pasa"] = fila["pasa"] and fuera_c <= fuera_a
    filas.append(fila)
    pos = [f for f in ok if f["grupo"] == TEMA]
    filas.append(tasa(sum(f["pasa_c"] == "0" for f in pos), len(pos), "C4. Notas del tema que quedan fuera, cuerpo",
                      "≤ 5 %", MAX_FUERA_CUERPO, f"; sección 9: {sum(f['pasa_a'] == '0' for f in pos)}"))  # fmt: skip

    otro = [t for t in NINO_OTRO_SENTIDO if k.en_tema(t)]
    perdidas = [t for t in FENOMENO_BIEN_ESCRITO if not k.en_tema(t)]
    sin_nino = [t for t in DEL_TEMA_SIN_NINO if not k.en_tema(t)]
    pasa5 = not otro and not perdidas and len(sin_nino) <= MAX_SINTETICOS_DEL_TEMA_FUERA
    filas.append(criterio(PRUEBA, "C5. Sintéticos: «niño» con otro sentido que pasa / el fenómeno que no pasa / del "
                          "tema sin «El Niño» que quedan fuera", f"{len(otro)} / {len(perdidas)} / {len(sin_nino)}",
                          "0 / 0 / ≤ 1", pasa5, "; ".join(otro + perdidas + sin_nino)))  # fmt: skip
    gris = medidos[GRIS]
    p_c, p_a = sum(pc for pc, _, _ in gris) / len(gris), sum(pa for _, pa, _ in gris) / len(gris)
    filas.append(criterio(f"{PRUEBA} (informativo)", "C6. Zona gris de la prueba que pasa",
                          f"{p_c * 100:.1f} %".replace(".", ","), "informativo", True,
                          f"{len(gris)} notas; sección 9: {p_a * 100:.1f} %".replace(".", ",")))  # fmt: skip
    f8 = vt.f6()
    filas.append(criterio(PRUEBA, "C8. Preguntar sin cambios (no usa el clasificador)", f8["valor"], "0 cambios",
                          f8["valor"] == "0 cambios", f8["detalle"]))  # fmt: skip
    guardar(filas, config.DIR_APP / "validacion.csv")
    for f in filas:
        log.info(f"[{'ok' if f['pasa'] else 'NO'}] {f['criterio']}: {f['valor']} (umbral {f['umbral']}) {f['detalle']}")


def main(argv=None):
    ap = argparse.ArgumentParser(description="Clasificador de tema de Verificar: C1 a C8 (sección 10).")
    ap.add_argument("accion", choices=("entrenar", "muestra", "cuerpos", "validar"))
    a = ap.parse_args(argv)
    configurar("app-tema-clasificador")
    {"entrenar": entrenar, "muestra": muestra, "cuerpos": cuerpos, "validar": validar}[a.accion]()


if __name__ == "__main__":
    main()
