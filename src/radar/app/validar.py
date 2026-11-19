"""Criterios P1 a P5 de la API (docs/app/definicion.md, sección 6) con textos sintéticos y los modelos reales.

python -m radar.app.validar  ->  data/processed/app/validacion.csv
"""

import logging
import statistics
import time
import typing

from fastapi.encoders import jsonable_encoder
from fastapi.testclient import TestClient

from radar import config
from radar.app import api, eventos, servicio
from radar.comun.avance import Avance
from radar.noticias.viabilidad import guardar

log = logging.getLogger(__name__)
PRUEBA = "App: API"
FECHA = "2026-11-15"  # fija, para que la API y la llamada directa vean el mismo comunicado vigente
LATENCIA_MAXIMA, ARRANQUE_MAXIMO = 2.0, 90.0
CAMPOS_PERMITIDOS = set(servicio.CAMPOS_NOTA) | {"medio_texto"}

# Textos inventados (el repo es público: nada de notas reales). Cubren datos, cercanía y textos muy cortos.
TEXTOS = (
    "El ENFEN declaró la alerta de El Niño costero y prevé una magnitud fuerte hasta marzo",
    "El Niño costero será moderado hasta el verano, según el último comunicado",
    "Estado de vigilancia de El Niño costero: se espera una magnitud débil",
    "El Niño costero no está activo y no se esperan cambios hasta enero",
    "Se viene un Niño extraordinario que arrasará la costa norte este verano",
    "El mar frente a Piura está más caliente de lo normal y los pescadores esperan más lluvias",
    "El calor en Lima seguirá en las próximas semanas por la temperatura del mar",
    "Recomiendan limpiar los canales y techos ante las lluvias en Tumbes",
    "La anchoveta se alejó de la costa por el agua cálida, dicen los gremios",
    "El fenómeno El Niño podría llegar con fuerza moderada en el verano de 2027",
    "Vigilancia de El Niño costero continúa y la magnitud prevista es débil hasta febrero",
    "Alerta: El Niño será fuerte en diciembre según expertos",
    "Senamhi anuncia lluvias de moderada a fuerte intensidad en la sierra norte",
    "El Gobierno declaró en emergencia a distritos de la costa por peligro de lluvias",
    "Hola",
    "Mañana juega la selección",
    "Precio del dólar hoy en Perú",
    "El Niño costero",
    ("El comité ENFEN informó que mantiene el estado de vigilancia de El Niño costero. " * 3
     + "Se prevé que las condiciones cálidas continúen hasta el verano, con una magnitud débil. "
     "Las autoridades recomiendan a la población de la costa norte prepararse ante posibles lluvias. ") * 3,
    ("Los pescadores artesanales de Paita y Sechura reportan menos pesca por el mar cálido. " * 4
     + "Piden apoyo al Estado mientras el comité multisectorial evalúa la situación. ") * 3,
)  # fmt: skip
CONSULTAS = (
    "¿Cuál es el estado del Niño costero hoy?",
    "¿Qué recomienda el ENFEN para la pesca?",
    "¿Hay alerta de lluvias en la costa norte?",
    "¿Qué dijo el último comunicado sobre la magnitud?",
    "¿Quién ganó el partido de ayer?",
)
MACROREGIONES = ("lima", "costa_norte", "costa_centro")


def criterio(nombre, valor, umbral, pasa, detalle=""):
    return {"prueba": PRUEBA, "criterio": nombre, "valor": valor, "umbral": umbral, "pasa": pasa,
            "detalle": detalle}  # fmt: skip


def notas_en(objeto):
    """Todo diccionario que parece una nota (tiene titular) dentro de una respuesta."""
    if isinstance(objeto, dict):
        if "titular" in objeto:
            yield objeto
        for v in objeto.values():
            yield from notas_en(v)
    elif isinstance(objeto, list):
        for v in objeto:
            yield from notas_en(v)


def citas_en(r, parrafos):
    """(literales, total) de las citas oficiales de una respuesta de Verificar o de Preguntar."""
    pares = []
    for a in r.get("afirmaciones", []):
        for d in a["datos"]:
            if d["oficial"]["cita"]:
                pares.append((d["oficial"]["cita"]["cita"], d["oficial"]["cita"]["parrafo"]))
    for p in ([r["oficial_cercano"]] if r.get("oficial_cercano") else []) + r.get("que_hacer", {}).get("oficiales", []):
        pares.append((p["texto"], p["parrafo"]))
    pares += [(c["cita"], c["parrafo"]) for c in r.get("citas", [])]
    return sum(cita in parrafos.get(pid, "") for cita, pid in pares), len(pares)


def campos_libres(modelo):
    """Campos de un esquema de eventos que aceptan texto libre (str sin lista cerrada)."""
    libres = []
    for nombre, campo in modelo.model_fields.items():
        tipos = typing.get_args(campo.annotation) or (campo.annotation,)
        if str in tipos and not campo.metadata:
            libres.append(nombre)
    return libres


def main():
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    inicio = time.perf_counter()
    with TestClient(api.crear()) as cliente:
        arranque = time.perf_counter() - inicio
        s = servicio.servicio()
        parrafos = {p["id"]: p["texto"] for p in s.corpus.parrafos}
        iguales, latencias, notas, literales, citas = 0, [], [], 0, 0
        avance = Avance("Verificar y Preguntar", len(TEXTOS) + len(CONSULTAS), cada=5)
        pedidos = [("verificar", t, MACROREGIONES[i % 3]) for i, t in enumerate(TEXTOS)]
        pedidos += [("preguntar", c, MACROREGIONES[i % 3]) for i, c in enumerate(CONSULTAS)]
        diferentes = []
        for ruta, texto, region in pedidos:
            campo = "texto" if ruta == "verificar" else "consulta"
            t0 = time.perf_counter()
            r = cliente.post(f"/api/{ruta}", json={campo: texto, "macroregion": region, "fecha": FECHA})
            if ruta == "verificar":
                latencias.append(time.perf_counter() - t0)
            r.raise_for_status()
            directo = jsonable_encoder(getattr(s, ruta)(texto, FECHA, region))
            if r.json() == directo:
                iguales += 1
            else:
                diferentes.append(texto[:40])
            notas += list(notas_en(r.json()))
            bien, total = citas_en(r.json(), parrafos)
            literales, citas = literales + bien, citas + total
            avance.paso()
        for seccion in ("hallazgos", "linea", "magnitudes", "reaccion", "temas", "citas"):
            notas += list(notas_en(cliente.get(f"/api/panorama/{seccion}").json()))
        notas += list(notas_en(cliente.get("/api/metodologia").json()))
    fuera = sorted({k for n in notas for k in n if k not in CAMPOS_PERMITIDOS})
    libres = campos_libres(eventos.Evento) + [c for c in campos_libres(eventos.Lote) if c != "sesion"]
    mediana = statistics.median(latencias)
    filas = [
        criterio("P1. API igual a la llamada directa", f"{iguales}/{len(pedidos)}", "100 %",
                 iguales == len(pedidos), "; ".join(diferentes)),
        criterio("P2. Mediana de Verificar (s)", f"{mediana:.2f}", f"≤ {LATENCIA_MAXIMA}", mediana <= LATENCIA_MAXIMA,
                 f"máximo {max(latencias):.2f} s"),
        criterio("P2. Arranque (s)", f"{arranque:.1f}", f"≤ {ARRANQUE_MAXIMO:.0f}", arranque <= ARRANQUE_MAXIMO),
        criterio("P3. Campos de notas fuera de la lista", len(fuera), "0", not fuera,
                 f"{len(notas)} notas revisadas; {', '.join(fuera)}"),
        criterio("P4. Citas literales", f"{literales}/{citas}", "100 %", citas > 0 and literales == citas),
        criterio("P5. Campos de texto libre en el registro", len(libres), "0", not libres, ", ".join(libres)),
    ]  # fmt: skip
    guardar(filas, config.DIR_APP / "validacion.csv")
    for f in filas:
        log.info(f"[{'ok' if f['pasa'] else 'NO'}] {f['criterio']}: {f['valor']} (umbral {f['umbral']}) {f['detalle']}")


if __name__ == "__main__":
    main()
