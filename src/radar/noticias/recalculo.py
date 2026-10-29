"""Recálculo de las notas ya leídas con el código actual (texto limpio, resumen sin enlaces, regla de magnitud única),
de forma reanudable y sin tocar lo existente hasta aplicarlo (definición en docs/noticias/recalculo.md).

Cada medio escribe en data/raw/noticias/<medio>/recalculo/: notas.csv, enlaces.csv y cambios.csv (antes y después
de cada nota, sin texto) y estado.json. Por nota se escriben primero sus enlaces, luego su cambio y al final su fila,
que es la marca de hecha: al reanudar se corta una línea a medias y se descarta lo que no tenga fila.

Uso (desde radar.noticias.historico):
  --recalcular            fase 1: notas que mencionan El Niño (y El Tiempo completo); se detiene en el punto de control
  --recalcular --todo     fase 2: el resto (se puede cortar y volver a lanzar)
  --recalcular --informe  criterios sobre lo ya releído
  --recalcular --aplicar  si todo está releído y pasan los criterios, reemplaza notas.csv y enlaces.csv
"""

import collections
import logging
import os
import re
import threading

import requests

from radar import config
from radar.comun.archivos import (
    EstadoDescargas,
    anexar_csv,
    escribir_csv,
    guardar_json,
    leer_csv,
    leer_json,
    reparar_csv,
)
from radar.comun.http import Bloqueado, Cliente, HostSuspendido, Rechazado
from radar.comun.registro import describir
from radar.comun.texto import ahora, sha1_corto
from radar.noticias import esquemas, rasgos
from radar.noticias.medios import MEDIOS, NoExiste, filas_de_nota
from radar.noticias.nota import NotaInvalida
from radar.noticias.viabilidad import _si, criterio
from radar.oficial import enfen

log = logging.getLogger(__name__)

FASE_NINO, FASE_RESTO = "nino", "resto"
# Código con que se calculó cada fila guardada, según su "recolectado" (commits del 28-oct-2026, hora de Lima)
GENERACIONES = (
    ("anterior", ""),  # extracción, resumen y regla de magnitud anteriores
    ("capa1", "2026-10-28T12:45"),  # cuerpo limpio (91c1aa0); resumen y regla anteriores
    ("resumen", "2026-10-28T18:23"),  # resumen sin enlaces (7fc3477); regla anterior
    ("actual", "2026-10-28T22:40"),  # regla de magnitud única (333c413)
)
MAX_INTENTOS = 3  # respuestas con error (HTTP, contenido) antes de dejar la nota como estaba
MAX_EJECUCIONES_CON_ERROR_DE_RED = 3  # un error de red cuenta una vez por ejecución (una suspensión no la descarta)
PAUSA_TRAS_SUSPENSION = 600  # segundos que espera un medio suspendido por fallos seguidos antes de reintentar
REANUDACIONES = 3
GUARDAR_ESTADO_CADA = 50
MEDIOS_SIN_FECHA_DE_EDICION = {"andina"}  # su dateModified es la fecha en que se sirve la página, no una edición
# Criterios (fijados el 28-oct-2026 antes de correr)
REPRODUCCION_MINIMA = 0.99  # M1b
CAMBIO_SOBRE_MAXIMO = 0.05  # M3, sobre las notas "sobre El Niño" de antes
SIN_RELEER_MAXIMO = 0.01  # M4, por medio
CAUSA_DESCONOCIDA = "sin_causa"

# Regla de magnitud anterior (hasta el 28-oct-2026), reproducida para separar causas
_MAGNITUD_ANTERIOR = re.compile(r"\b(muy fuertes?|extraordinari[oa]s?|fuertes?|moderad[oa]s?|d[ée]bil(?:es)?)\b", re.I)
_CONTEXTO_ANTERIOR = re.compile(r"magnitud|intensidad|categor[íi]a", re.I)
_FRASE_ANTERIOR = re.compile(r"(?<=[.!?])\s+")


def magnitudes_regla_anterior(texto):
    encontradas = set()
    for frase in _FRASE_ANTERIOR.split(texto or ""):
        if rasgos.NINO.search(frase) and _CONTEXTO_ANTERIOR.search(frase):
            encontradas.update(enfen.magnitud_canonica(m.group(1)) for m in _MAGNITUD_ANTERIOR.finditer(frase))
    return [e for e in enfen.ESCALA_MAGNITUD if e in encontradas]


def generacion(recolectado):
    return next(g for g, desde in reversed(GENERACIONES) if recolectado[:16] >= desde)


def fase(nota):
    if nota["medio"] == "eltiempo" or _si(nota["menciona_nino"]) or _si(nota["sobre_nino"]):
        return FASE_NINO
    return FASE_RESTO


def _sobre(titular, resumen, cuerpo):
    return rasgos.nino_en_inicio(resumen, cuerpo) or rasgos.menciones(titular) > 0


def _lista(valor):
    return "|".join(valor) if isinstance(valor, list | tuple) else str(valor or "")


# ---------------------------------------------------------------- archivos de un medio


class Archivos:
    def __init__(self, medio):
        self.dir = config.DIR_RAW_NOTICIAS / medio / "recalculo"
        self.notas, self.enlaces, self.cambios = (self.dir / f for f in ("notas.csv", "enlaces.csv", "cambios.csv"))
        self.estado = self.dir / "estado.json"

    def reparar(self):
        """Corta líneas a medias y descarta enlaces y cambios de notas sin fila (cortes entre escrituras)."""
        for ruta, columnas in (
            (self.notas, esquemas.NOTAS),
            (self.enlaces, esquemas.ENLACES),
            (self.cambios, esquemas.CAMBIOS),
        ):
            if reparar_csv(ruta, columnas):
                log.info("%s: se quitó una línea a medias", ruta)
        hechas = {f["id"] for f in leer_csv(self.notas)}
        for ruta, columnas in ((self.enlaces, esquemas.ENLACES), (self.cambios, esquemas.CAMBIOS)):
            filas = leer_csv(ruta)
            buenas = [f for f in filas if f["id"] in hechas]
            if len(buenas) != len(filas):
                escribir_csv(ruta, columnas, buenas)
        return hechas

    def escribir(self, nota, enlaces, cambio):
        if enlaces:
            anexar_csv(self.enlaces, esquemas.ENLACES, enlaces)
        anexar_csv(self.cambios, esquemas.CAMBIOS, [cambio])
        anexar_csv(self.notas, esquemas.NOTAS, [nota])  # al final: marca la nota como hecha


# ---------------------------------------------------------------- una nota


def comparar(vieja, nueva, campos, enlaces_nuevos, medio, momento):
    """Fila de cambios.csv: antes, después y la causa, separando cuerpo, regla y resumen paso a paso."""
    gen = generacion(vieja["recolectado"])
    cuerpo, resumen_nuevo, resumen_viejo, titular = (
        campos["cuerpo"],
        campos["resumen"],
        vieja["resumen"],
        campos["titular"],
    )
    if medio in MEDIOS_SIN_FECHA_DE_EDICION:
        editada = sha1_corto(cuerpo) != vieja["sha1_cuerpo"] if gen != "anterior" else None
    else:
        editada = bool(vieja["fecha_modificacion"]) and campos["fecha_modificacion"] > vieja["fecha_modificacion"]
        if gen != "anterior":
            editada = editada or sha1_corto(cuerpo) != vieja["sha1_cuerpo"]

    def causa_del_cuerpo():
        if editada:
            return "edicion"
        if gen == "anterior":
            return "capa1_o_edicion" if editada is None else "capa1"
        return CAUSA_DESCONOCIDA  # con el cuerpo limpio ya guardado y sin edición, el cuerpo no debió cambiar

    def causas(pasos):
        return "+".join(c for c, cambia in pasos if cambia)

    # "sobre El Niño": antes → (cuerpo y titular nuevos, resumen viejo) → (resumen nuevo)
    s_antes = _si(vieja["sobre_nino"])
    s_medio = _sobre(titular, resumen_viejo if gen in ("anterior", "capa1") else resumen_nuevo, cuerpo)
    s_ahora = _si(nueva["sobre_nino"])
    causa_sobre = causas([(causa_del_cuerpo(), s_antes != s_medio), ("resumen", s_medio != s_ahora)])

    # magnitudes: antes → regla anterior sobre el texto nuevo (resumen viejo) → regla nueva → resumen nuevo
    m_antes = [m for m in vieja["magnitudes"].split("|") if m]
    resumen_de_antes = resumen_viejo if gen in ("anterior", "capa1") else resumen_nuevo
    regla_de_antes = gen in ("anterior", "capa1", "resumen")
    m_texto = magnitudes_regla_anterior(f"{resumen_de_antes} {cuerpo}") if regla_de_antes else m_antes
    m_regla = rasgos.magnitudes(f"{resumen_de_antes} {cuerpo}")
    m_ahora = nueva["magnitudes"]
    causa_magnitudes = causas(
        [(causa_del_cuerpo(), m_antes != m_texto), ("regla", m_texto != m_regla), ("resumen", m_regla != m_ahora)]
    )
    return {
        "medio": medio,
        "id": vieja["id"],
        "fase": fase(vieja),
        "generacion": gen,
        "estado": "releida",
        "motivo": "",
        "sobre_antes": s_antes,
        "sobre_ahora": s_ahora,
        "sobre_texto_nuevo": s_medio,
        "menciona_antes": _si(vieja["menciona_nino"]),
        "menciona_ahora": nueva["menciona_nino"],
        "magnitudes_antes": "|".join(m_antes),
        "magnitudes_ahora": _lista(m_ahora),
        "magnitudes_texto_nuevo": _lista(m_texto),
        "comunicados_antes": vieja["comunicados"],
        "comunicados_ahora": _lista(nueva["comunicados"]),
        "n_enlaces_antes": vieja["n_enlaces"],
        "n_enlaces_ahora": len(enlaces_nuevos),
        "resumen_cambia": resumen_nuevo != resumen_viejo,
        "pagina_editada": "" if editada is None else editada,
        "causa_sobre": causa_sobre if s_antes != s_ahora else "",
        "causa_magnitudes": causa_magnitudes if m_antes != list(m_ahora) else "",
        "recalculado": momento,
    }


def sin_releer(vieja, motivo, momento):
    return {
        **{c: "" for c in esquemas.CAMBIOS},
        "medio": vieja["medio"],
        "id": vieja["id"],
        "fase": fase(vieja),
        "generacion": generacion(vieja["recolectado"]),
        "estado": "sin_releer",
        "motivo": motivo[:200],
        "recalculado": momento,
    }


# ---------------------------------------------------------------- un medio


class Recalculo:
    def __init__(self, nombre, parar, ejecucion, fase_maxima=FASE_NINO, limite=None):
        self.nombre, self.parar, self.ejecucion, self.limite = nombre, parar, ejecucion, limite
        self.fases = (FASE_NINO,) if fase_maxima == FASE_NINO else (FASE_NINO, FASE_RESTO)
        self.archivos = Archivos(nombre)
        self.medio = self._medio()
        self.resumen = collections.Counter()

    def _medio(self):
        return MEDIOS[self.nombre](Cliente(hosts_permitidos={config.HOSTS_MEDIOS[self.nombre]}), self.parar)

    def pendientes(self, hechas):
        viejas = leer_csv(config.DIR_RAW_NOTICIAS / self.nombre / "notas.csv")
        orden = {f: i for i, f in enumerate(self.fases)}
        filas = [n for n in viejas if n["id"] not in hechas and fase(n) in orden]
        # estable: dentro de cada fase, primero las filas de control del instrumento (M1b) y luego el orden del archivo
        filas.sort(key=lambda n: (orden[fase(n)], generacion(n["recolectado"]) != "capa1"))
        return filas[: self.limite] if self.limite else filas, viejas

    def correr(self):
        hechas = self.archivos.reparar()
        pendientes, viejas = self.pendientes(hechas)
        enlaces_viejos = collections.defaultdict(list)
        for e in leer_csv(config.DIR_RAW_NOTICIAS / self.nombre / "enlaces.csv"):
            enlaces_viejos[e["id"]].append(e)
        self.resumen.update(pendientes=len(pendientes), ya_hechas=len(hechas))
        with EstadoDescargas(self.archivos.estado, cada=GUARDAR_ESTADO_CADA) as estado:
            reanudaciones = 0
            while pendientes and not self.parar.is_set():
                try:
                    self._procesar(pendientes, enlaces_viejos, estado)
                    break
                except HostSuspendido as e:
                    reanudaciones += 1
                    if reanudaciones > REANUDACIONES:
                        self.resumen["detalle"] = f"detenido tras {REANUDACIONES} reanudaciones: {describir(e)}"
                        break
                    log.info("%s: %s; se reintenta en %d s", self.nombre, describir(e), PAUSA_TRAS_SUSPENSION)
                    if self.parar.wait(PAUSA_TRAS_SUSPENSION):
                        break
                    self.medio = self._medio()  # cliente nuevo: los fallos seguidos vuelven a cero
                    hechas = {f["id"] for f in leer_csv(self.archivos.notas)}
                    pendientes = [n for n in pendientes if n["id"] not in hechas]
                except Bloqueado as e:  # no se eluden bloqueos: este medio se detiene
                    self.resumen["detalle"] = f"bloqueado: {describir(e)}"
                    break
        return self.resumen

    def _lotes(self, pendientes):
        """El Tiempo de a 100 por la API; los demás de a una, para que el error de una nota no afecte a otras."""
        paso = 100 if self.nombre == "eltiempo" else 1
        for i in range(0, len(pendientes), paso):
            yield pendientes[i : i + paso]

    def _procesar(self, pendientes, enlaces_viejos, estado):
        por_id = {n["id"]: n for n in pendientes}
        for lote in self._lotes(pendientes):
            if self.parar.is_set():
                return
            filas = [self.medio.lista.get(n["id"]) or {**n, "titulo": ""} for n in lote]
            try:
                resultados = list(self.medio.descargar(filas))
            except Rechazado as e:
                resultados = [(f, e) for f in filas]
            for fila, resultado in resultados:
                self._una(por_id[fila["id"]], fila, resultado, enlaces_viejos, estado)

    def _una(self, vieja, fila, resultado, enlaces_viejos, estado):
        momento = ahora().isoformat()
        clave = f"nota:{vieja['id']}"
        if isinstance(resultado, dict):
            nueva, enlaces = filas_de_nota(self.nombre, fila, resultado, vieja["muestra"])
            for campo in ("via", "muestra", "candidata_por", "recolectado"):  # cómo entró la nota: se conserva
                nueva[campo] = vieja[campo]
            cambio = comparar(vieja, nueva, resultado, enlaces, self.nombre, momento)
            self.archivos.escribir(nueva, enlaces, cambio)
            self.resumen["releidas"] += 1
            return
        previo = estado.get(clave)
        if isinstance(resultado, NoExiste | NotaInvalida):
            motivo = str(resultado)
        elif isinstance(
            resultado, requests.ConnectionError | requests.Timeout | requests.exceptions.ChunkedEncodingError
        ):
            ejecuciones = set(previo.get("ejecuciones_red", [])) | {self.ejecucion}
            estado.marcar(clave, {**previo, "ejecuciones_red": sorted(ejecuciones)})
            self.resumen["errores_red"] += 1
            if len(ejecuciones) < MAX_EJECUCIONES_CON_ERROR_DE_RED:
                return
            motivo = f"red en {len(ejecuciones)} ejecuciones: {describir(resultado)}"
        else:
            intentos = previo.get("intentos", 0) + 1
            estado.marcar(clave, {**previo, "intentos": intentos})
            self.resumen["errores"] += 1
            if intentos < MAX_INTENTOS:
                return
            motivo = f"{intentos} intentos: {describir(resultado)}"
        log.debug("%s %s sin releer: %s", self.nombre, vieja["id"], motivo)
        self.archivos.escribir(vieja, enlaces_viejos.get(vieja["id"], []), sin_releer(vieja, motivo, momento))
        self.resumen["sin_releer"] += 1


# ---------------------------------------------------------------- informe y criterios

PRUEBA = "Recálculo de las notas"


def informe():
    """Criterios M1b a M5 sobre lo ya releído (docs/noticias/recalculo.md). Devuelve (filas, completo)."""
    filas, completo, integridad, sin_releer_por_medio = [], True, [], {}
    todos = []
    for nombre in MEDIOS:
        a = Archivos(nombre)
        cambios = leer_csv(a.cambios)
        todos += cambios
        viejas = leer_csv(config.DIR_RAW_NOTICIAS / nombre / "notas.csv")
        nuevas = leer_csv(a.notas)
        ids_viejos, ids_nuevos = [n["id"] for n in viejas], [n["id"] for n in nuevas]
        completo = completo and set(ids_viejos) <= set(ids_nuevos)
        repetidos = len(ids_nuevos) - len(set(ids_nuevos))
        enlaces_huerfanos = sum(e["id"] not in set(ids_nuevos) for e in leer_csv(a.enlaces))
        integridad.append(f"{nombre}: {len(set(ids_nuevos))}/{len(ids_viejos)} releídas o conservadas, "
                          f"{repetidos} repetidas, {enlaces_huerfanos} enlaces sin nota")  # fmt: skip
        if repetidos or enlaces_huerfanos:
            completo = False
        sin = sum(c["estado"] == "sin_releer" for c in cambios)
        sin_releer_por_medio[nombre] = (sin, len(cambios))
    releidas = [c for c in todos if c["estado"] == "releida"]
    # control del instrumento: filas guardadas ya con el cuerpo limpio y sin edición; con el resumen y la regla de
    # antes sobre el texto nuevo deben dar lo guardado
    control = [c for c in releidas if c["generacion"] == "capa1" and c["pagina_editada"] == "0"]
    reproducidas = [
        c
        for c in control
        if c["sobre_antes"] == c["sobre_texto_nuevo"] and c["magnitudes_antes"] == c["magnitudes_texto_nuevo"]
    ]
    sin_causa = [c for c in releidas if CAUSA_DESCONOCIDA in c["causa_sobre"] + c["causa_magnitudes"]]
    cambian_sobre = [c for c in releidas if c["causa_sobre"]]
    por_resumen_eltiempo = [c for c in cambian_sobre if c["medio"] == "eltiempo" and c["causa_sobre"] == "resumen"]
    neto = sum((1 if _si(c["sobre_ahora"]) else -1) for c in cambian_sobre if c not in por_resumen_eltiempo)
    base = sum(_si(c["sobre_antes"]) for c in releidas) or 1
    causas = collections.Counter(f"sobre:{c['causa_sobre']}" for c in cambian_sobre)
    causas.update(f"magnitudes:{c['causa_magnitudes']}" for c in releidas if c["causa_magnitudes"])
    parte = round(len(reproducidas) / len(control), 3) if control else 0.0  # sin filas de control no pasa
    filas += [
        criterio(PRUEBA, "M1b: filas con el cuerpo limpio ya guardado, sin edición, que se reproducen", parte,
                 f"≥ {REPRODUCCION_MINIMA}", bool(control) and parte >= REPRODUCCION_MINIMA,
                 f"{len(reproducidas)}/{len(control)}"),
        criterio(PRUEBA, "M2: cambios con causa identificada", len(sin_causa), "= 0", not sin_causa,
                 "; ".join(f"{c['medio']} {c['id']}" for c in sin_causa[:20])),
        criterio(PRUEBA, "M3: cambio neto en 'sobre El Niño' (sin el resumen de El Tiempo)", round(abs(neto) / base, 4),
                 f"≤ {CAMBIO_SOBRE_MAXIMO}", abs(neto) / base <= CAMBIO_SOBRE_MAXIMO,
                 f"neto {neto:+d} de {base}; resumen de El Tiempo: {len(por_resumen_eltiempo)}; "
                 + ", ".join(f"{k} {v}" for k, v in causas.most_common())),
    ]  # fmt: skip
    for nombre, (sin, total) in sin_releer_por_medio.items():
        parte_sin = round(sin / total, 4) if total else 0.0
        filas.append(criterio(PRUEBA, f"M4: {nombre}: notas sin releer", parte_sin, f"≤ {SIN_RELEER_MAXIMO}",
                              parte_sin <= SIN_RELEER_MAXIMO, f"{sin}/{total}"))  # fmt: skip
    filas.append(criterio(PRUEBA, "M5: integridad (todas, una vez, enlaces con nota)", completo, "sí", completo,
                          "; ".join(integridad)))  # fmt: skip
    return filas, completo


# ---------------------------------------------------------------- aplicar


def _cambiar(nombre):
    """Reemplaza notas.csv y enlaces.csv por los recalculados, en el orden del archivo actual. Si se corta a mitad,
    la fase guardada en estado.json permite terminarlo al volver a correr."""
    a = Archivos(nombre)
    base = config.DIR_RAW_NOTICIAS / nombre
    estado = leer_json(a.estado, {})
    if estado.get("aplicado") == "hecho":
        return
    finales = {archivo: a.dir / f"{archivo}.final" for archivo in ("notas.csv", "enlaces.csv")}
    if estado.get("aplicado") != "cambiando":
        orden = [n["id"] for n in leer_csv(base / "notas.csv")]
        nuevas = {n["id"]: n for n in leer_csv(a.notas)}
        enlaces = collections.defaultdict(list)
        for e in leer_csv(a.enlaces):
            enlaces[e["id"]].append(e)
        escribir_csv(finales["notas.csv"], esquemas.NOTAS, [nuevas[i] for i in orden])
        escribir_csv(finales["enlaces.csv"], esquemas.ENLACES, [e for i in orden for e in enlaces[i]])
        _marcar(a, "cambiando")
    for archivo, final in finales.items():
        actual, anterior = base / archivo, base / archivo.replace(".csv", ".anterior.csv")
        if final.exists():
            if actual.exists() and not anterior.exists():
                os.replace(actual, anterior)
            os.replace(final, actual)
    _marcar(a, "hecho")


def _marcar(archivos, fase_aplicado):
    estado = leer_json(archivos.estado, {})
    estado["aplicado"] = fase_aplicado
    guardar_json(archivos.estado, estado)


def aplicar():
    """Solo si todo está releído y pasan los criterios. Devuelve (filas del informe, aplicado)."""
    filas, completo = informe()
    if not completo or not all(f["pasa"] for f in filas):
        return filas, False
    for nombre in MEDIOS:
        _cambiar(nombre)
    return filas, True


def nueva_ejecucion():
    return ahora().strftime("%Y%m%d-%H%M%S")


def correr(medios, fase_maxima, limite, parar=None):
    """Un hilo por medio (cada uno con su propio ritmo de 1 petición por segundo)."""
    import concurrent.futures

    parar = parar or threading.Event()
    ejecucion = nueva_ejecucion()
    with concurrent.futures.ThreadPoolExecutor(max_workers=len(medios)) as hilos:
        tareas = {m: hilos.submit(Recalculo(m, parar, ejecucion, fase_maxima, limite).correr) for m in medios}
        try:
            return {m: t.result() for m, t in tareas.items()}
        except KeyboardInterrupt:
            parar.set()
            return {m: t.result() for m, t in tareas.items()}
