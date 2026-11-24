"""Criterios de la interfaz (docs/app/definicion.md, secciones 6 y 11): P6 a P12, U1 a U6 y I2 a I4.

1. Con la API corriendo (python -m radar.app): cd web && npm run medir  ->  data/processed/app/interfaz.json
2. python -m radar.app.validar_interfaz  ->  agrega la prueba "App: interfaz" a data/processed/app/validacion.csv

Aquí se calcula P8 de la API contra sus CSV (recontando desde los archivos, sin pasar por radar.app.servicio), y se
juntan los criterios que mide el navegador (P6, P7, P8 en pantalla, P10, P12, U1, U2, U4, U5, U6 y I2 a I4 del
rediseño, sección 11), la paleta (P9, medida el 24-nov) y la revisión de capturas (P11). U3 y
los textos de U2 y U6 los revisa tests/app.
"""

import json
import logging
import math
import statistics

from radar import config
from radar.app import servicio
from radar.comun.archivos import leer_csv
from radar.noticias.viabilidad import guardar
from radar.youtube import almacen

log = logging.getLogger(__name__)
PRUEBA = "App: interfaz"
ARCHIVO_NAVEGADOR = "interfaz.json"
ACTORES = ("ENFEN", "SENAMHI", "INDECI")

# Lo que se encontró al revisar las capturas (375 y 1.280 px, claro y oscuro) con la guía de errores de
# visualización, y cómo quedó. Se actualiza en cada revisión; "pendientes" debe quedar en 0.
REVISION_P11 = {
    "corregidos": [
        "el detalle de «Ver por qué» se veía abierto porque el CSS pisaba el atributo hidden",
        "el encabezado del Panorama quedaba descentrado",
        "en F, la etiqueta del 0 se encimaba con la de 0,1 %",
        "las cifras usaban punto decimal y los porcentajes tenían decimales desiguales",
        "el cuadro fijo de Preguntar dejaba ver el texto por debajo en el celular (24-nov)",
        "las viñetas de los PDF se veían como un cuadro al inicio de algunas citas",
    ],
    "pendientes": [],
}

# P9 se mide aparte, con validate_palette.js; aquí se registra su última medición (24-nov, sección 15.5)
FALLAS_P9 = [
    "escala del Senamhi: amarillo y naranja a ΔE 14,7 (mínimo 15)",
    "escala del Senamhi: luminosidad del amarillo fuera de banda en claro y oscuro, y la del naranja en oscuro",
    "regla de magnitud de Hoy en claro: el tramo débil a 1,79:1 del fondo (mínimo 2:1)",
]


def criterio(nombre, valor, umbral, pasa, detalle=""):
    return {"prueba": PRUEBA, "criterio": nombre, "valor": valor, "umbral": umbral, "pasa": pasa,
            "detalle": detalle}  # fmt: skip


def p8_api_contra_csv():
    """(revisadas, diferencias) entre las cifras del Panorama y lo que se recuenta de sus CSV."""
    p = servicio.panorama()
    diferencias, revisadas = [], 0

    def comparar(nombre, api, csv):
        nonlocal revisadas
        revisadas += 1
        if api != csv:
            diferencias.append(f"{nombre}: API {api} / CSV {csv}")

    eventos = leer_csv(config.DIR_ANALITICA / "eventos-por-comunicado.csv")
    veces = [math.exp(float(f["proporcion_nino"])) for f in eventos]
    hallazgos = {h["id"]: h for h in p.hallazgos()}
    comparar("hallazgo reacción", hallazgos["reaccion"]["valor"], f"{sum(v > 1 for v in veces)} de {len(veces)}")
    mediana = statistics.median(veces) - 1
    comparar("mediana de la reacción", f"+{mediana * 100:.0f} %" in hallazgos["reaccion"]["texto"], True)
    comparar("C: comunicados", [f["veces"] for f in p.reaccion()["comunicados"]], [round(v, 3) for v in veces])

    datos = leer_csv(config.DIR_NLP / "discrepancia-todas.csv")
    anteriores = {(f["medio"], f["id"]) for f in datos if f["categoria"] == "desactualizada"}
    comparar("hallazgo anteriores", hallazgos["anteriores"]["valor"], str(len(anteriores)))

    notas = {(n["medio"], n["id"]): n for n in leer_csv(config.DIR_NOTICIAS / "notas.csv")}
    colores = leer_csv(config.DIR_NLP / "discrepancia-todas-notas.csv")
    con_color = [c for c in colores if not c["error"] and (c["medio"], c["id"]) in notas
                 and notas[(c["medio"], c["id"])]["sobre_nino"] == "1"
                 and notas[(c["medio"], c["id"])]["fecha_publicacion"][:10] >= servicio.INICIO_PANORAMA]  # fmt: skip
    con_datos = [c for c in con_color if c["color"] != "sin_afirmaciones"]
    verdes = sum(c["color"] == "verde" for c in con_datos)
    comparar("hallazgo coinciden", hallazgos["coinciden"]["valor"], f"{verdes / len(con_datos) * 100:.0f} %")
    linea = p.linea()["semanas"]
    comparar("A: notas", sum(s["coinciden"] + s["difieren"] + s["sin_datos"] for s in linea), len(con_color))
    comparar("A: coinciden", sum(s["coinciden"] for s in linea), verdes)

    citas = [f for f in leer_csv(config.DIR_RED / "citas.csv") if f["grupo"] == "medio" and f["actor"] in ACTORES]
    for m in p.citas()["medios"]:
        for a in ACTORES:
            csv = next(float(f["proporcion"]) for f in citas if f["valor"] == m["medio"] and f["actor"] == a)
            comparar(f"E: {m['medio']} {a}", m[a], csv)

    archivos = almacen.archivos(servicio.TIPO_PUNTOS, bases=(config.DIR_YOUTUBE,))
    f_api = p.youtube()
    if archivos and f_api["disponible"]:
        puntos = leer_csv(archivos[-1])
        comparar("F: puntos", len(f_api["puntos"]), len(puntos))
        for i in f_api["indicador_tasa"]:
            tasas = [float(x["tasa"]) for x in puntos if x["tipo"] == i["tipo"]]
            comparar(f"F: mediana {i['tipo']}", round(i["mediana"], 6), round(statistics.median(tasas), 6))
        web = leer_csv(config.DIR_ANALITICA / "web-engagement.csv")
        rho = next(f for f in web if f["indicador"] == "rho_dentro_del_canal" and not f["grupo"])
        r = f_api["indicador_respuesta"]
        comparar("F: ρ e IC", (r["rho"], r["ic_inf"], r["ic_sup"]),
                 (float(rho["valor"]), float(rho["ic_inf"]), float(rho["ic_sup"])))  # fmt: skip
    return revisadas, diferencias


def main():
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    ruta = config.DIR_APP / ARCHIVO_NAVEGADOR
    if not ruta.exists():
        raise SystemExit(f"Falta {ruta}: corre antes la API y luego 'cd web && npm run medir'")
    navegador = json.loads(ruta.read_text(encoding="utf-8"))["criterios"]
    revisadas, diferencias = p8_api_contra_csv()
    pendientes = REVISION_P11["pendientes"]

    def del_navegador(id_, nombre):
        c = navegador[id_]
        return criterio(nombre, c["valor"], c["umbral"], c["pasa"], c.get("detalle", ""))

    p8 = navegador["P8"]
    filas = [
        del_navegador("P6", "P6. Accesibilidad (axe): violaciones graves o críticas"),
        del_navegador("P7", "P7. De punta a punta: 6 textos sintéticos"),
        criterio("P8. Cifras del Panorama iguales a sus CSV", f"{revisadas - len(diferencias)}/{revisadas}", "100 %",
                 not diferencias and p8["pasa"],
                 f"API contra CSV: {'; '.join(diferencias) or 'sin diferencias'}. En pantalla: {p8['detalle']}"),
        criterio("P9. Paleta (validate_palette.js, claro y oscuro)", len(FALLAS_P9), "0", not FALLAS_P9,
                 "; ".join(FALLAS_P9)),
        del_navegador("P10", "P10. Emergente, tabla con descarga y Cómo leer; Descriptivo donde corresponde"),
        criterio("P11. Revisión de capturas (375 y 1.280 px, claro y oscuro)", len(pendientes), "0", not pendientes,
                 f"corregidos: {'; '.join(REVISION_P11['corregidos'])}"),
        del_navegador("P12", "P12. Sin ordenar medios o canales por cercanía; B sin el medio"),
        del_navegador("U1", "U1. Acciones hasta el resultado"),
        del_navegador("U2", "U2. Jerga en Verificar y Preguntar (en pantalla)"),
        del_navegador("U4", "U4. Primera carga de Verificar, comprimida"),
        del_navegador("U5", "U5. Controles de 44 × 44 px o más"),
        del_navegador("U6", "U6. Respuestas sin datos con color de semáforo o promesas"),
        del_navegador("I2", "I2. Sin desplazamiento horizontal (360, 375 y 1.280 px)"),
        del_navegador("I3", "I3. A 1.280 × 800, la zona y el botón sin desplazarse"),
        del_navegador("I4", "I4. Glosario: las cuatro palabras abren su explicación"),
    ]  # fmt: skip
    guardar(filas, config.DIR_APP / "validacion.csv")
    for f in filas:
        log.info(f"[{'ok' if f['pasa'] else 'NO'}] {f['criterio']}: {f['valor']} (umbral {f['umbral']})")


if __name__ == "__main__":
    main()
