"""Lo que calcula la app (docs/app/definicion.md): Verificar, estado vigente, Preguntar, Panorama y Metodología.

No hace peticiones a ningún sitio: usa los modelos ya descargados y los CSV de data/. De las notas solo devuelve
medio, id, titular, fecha, enlace y macro-región (derecho de autor); los textos oficiales van literales.
"""

import collections
import datetime as dt
import functools
import math
import re
import statistics

from radar import config
from radar.agente import agente, herramientas
from radar.analitica import recomendador
from radar.app import textos as tx
from radar.comun import dominio
from radar.comun.archivos import leer_csv
from radar.nlp import afirmaciones as af
from radar.nlp import discrepancia, semaforo, temporalidad
from radar.oficial import enfen
from radar.youtube import almacen

TIPO_PUNTOS = "analitica-puntos"  # el mismo de radar.analitica.web (no se importa: arrastra los modelos)
COMUNICADOS_EN_LINEA = 6  # comunicados que muestra la mini línea de tiempo de Verificar
PARRAFOS_QUE_HACER = 2
DIAS_NOTA_RECIENTE = 3  # la cascada fresca de la ronda b del recomendador
INTERES_POR_DEFECTO = "prevencion"
# Filtro de tema de Verificar: "palabras" (sección 9) o "clasificador" (sección 10, solo si pasa C1 a C5)
FILTRO_DE_TEMA = "palabras"
MESES = ("enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre",
         "noviembre", "diciembre")  # fmt: skip
CAMPOS_NOTA = ("medio", "id", "titular", "fecha", "url", "macroregion")  # P3: lo único que sale de una nota
MEDIOS = {"andina": "Andina", "rpp": "RPP", "exitosa": "Exitosa", "eltiempo": "El Tiempo"}
NIVEL_DE_COLOR = {"verde": tx.COINCIDE, "amarillo": tx.REVISAR, "rojo": tx.NO_COINCIDE}
INICIO_PANORAMA = "2026-01-01"


# ---------------------------------------------------------------- utilidades


def numero_de(doc_id):
    """'enfen-2026-20' -> 20."""
    return int(doc_id.rsplit("-", 1)[1])


def mes_texto(aaaa_mm):
    anio, mes = aaaa_mm.split("-")[:2]
    return f"{MESES[int(mes) - 1]} de {anio}"


def fecha_texto(aaaa_mm_dd):
    anio, mes, dia = aaaa_mm_dd[:10].split("-")
    return f"{int(dia)} de {MESES[int(mes) - 1]} de {anio}"


def _extremo(x):
    if x == "?":
        return None
    inicio, _, fin = x.partition("..")
    return mes_texto(inicio) if not fin or fin == inicio else f"{mes_texto(inicio)} a {mes_texto(fin)}"


def fecha_legible(celda):
    """'fuerte:2026-04>2027-02' -> 'fuerte: de abril de 2026 a febrero de 2027'."""
    partes = []
    for seg in celda.split("|"):
        sujeto, _, rango = seg.partition(":")
        inicio, _, fin = rango.partition(">")
        a, b = _extremo(inicio), _extremo(fin)
        cuando = f"de {a} a {b}" if a and b else f"desde {a}" if a else f"hasta {b}" if b else ""
        nombre = "el evento" if sujeto == temporalidad.EVENTO else f"la magnitud {sujeto}"
        partes.append(f"{nombre}, {cuando}".strip(", "))
    return "; ".join(partes)


def valor_legible(dato, valor):
    if dato == "estado":
        return tx.ESTADO.get(valor, valor)
    if dato == "fecha":
        return fecha_legible(valor)
    if dato == "certeza":
        return "lo afirma sin condicional"
    return valor


def resaltar(frase, dato, valor):
    """(inicio, fin) del valor dentro de la frase, para marcarlo en pantalla; None si no aparece tal cual."""
    if dato not in ("magnitud", "estado"):
        return None
    palabra = {"no_activo": "no activo"}.get(valor, valor)
    m = re.search(rf"\b{re.escape(palabra)}\w*", frase, re.I)
    return [m.start(), m.end()] if m else None


def _semana(fecha):
    d = dt.date.fromisoformat(fecha[:10])
    return (d - dt.timedelta(days=d.weekday())).isoformat()


def _en_rango(fecha, desde, hasta):
    return (not desde or fecha >= desde) and (not hasta or fecha <= hasta)


@functools.cache
def notas():
    """Las notas con su macro-región y su color de la capa 5 (None si no se calculó). Sin el cuerpo."""
    regiones = {(r["medio"], r["id"]): r for r in leer_csv(config.DIR_NOTICIAS / "regiones.csv")}
    colores = {(r["medio"], r["id"]): r for r in leer_csv(config.DIR_NLP / "discrepancia-todas-notas.csv")}
    salida = {}
    for n in leer_csv(config.DIR_NOTICIAS / "notas.csv"):
        clave = (n["medio"], n["id"])
        r = regiones.get(clave, {})
        c = colores.get(clave)
        salida[clave] = {
            "medio": n["medio"], "id": n["id"], "titular": n["titular"], "fecha": n["fecha_publicacion"][:10],
            "url": n["url"], "macroregion": r.get("macroregion_principal", ""),
            "macroregiones": set(filter(None, r.get("macroregiones", "").split("|"))),
            "sobre_nino": n["sobre_nino"] == "1",
            "color": (c["color"] or "") if c and not c["error"] else None,
        }  # fmt: skip
    return salida


# ---------------------------------------------------------------- servicio


class Servicio:
    """Carga una vez el semáforo, el corpus oficial y los resultados precalculados."""

    def __init__(self, semaforo_=None):
        self.semaforo = semaforo_ or semaforo._semaforo()
        self._tema = None
        self.corpus = herramientas.corpus()
        self.historia = self.semaforo.historia
        self.comunicados = {c["id"]: c for c in self.corpus.comunicados}
        self.parrafos = {p["id"]: p for p in self.corpus.parrafos}

    @property
    def notas(self):
        return notas()

    # ------------------------------------------------ estado vigente

    def comunicado(self, doc_id):
        c = self.comunicados[doc_id]
        return {"id": doc_id, "numero": numero_de(doc_id), "fecha": c["fecha_emision"],
                "fecha_texto": fecha_texto(c["fecha_emision"]), "estado": c["estado"],
                "magnitud": c["magnitud_max_prevista"], "plazo": c["plazo"], "url": c["url"],
                "proximo": c["proximo_anunciado"]}  # fmt: skip

    def estado(self, fecha, macroregion):
        e = self.corpus.estado_vigente(fecha, macroregion)
        avisos = [
            {"numero": int(a["numero"]), "titulo": a["titulo"].capitalize(), "tipo": a["tipo"],
             "nivel": a["nivel"].lower(), "vigente": a["estado_en_fecha"] == "vigente",
             "inicio": a["inicio"][:16], "fin": a["fin"][:16], "url": a["url"]}
            for a in e["avisos"]
        ]  # fmt: skip
        return {"fecha": fecha, "macroregion": macroregion, "macroregion_texto": tx.MACROREGIONES[macroregion],
                "comunicado": self.comunicado(e["comunicado"]["id"]) if e["comunicado"] else None,
                "avisos": avisos}  # fmt: skip

    # ------------------------------------------------ Verificar

    def en_tema(self, texto, largo):
        """Sección 9 (palabras) o sección 10 (clasificador), según FILTRO_DE_TEMA."""
        if FILTRO_DE_TEMA == "clasificador":
            from radar.app import tema

            if self._tema is None:
                self._tema = tema.Clasificador(modelo=self.semaforo.modelo)
            return self._tema.en_tema(texto)
        return dominio.en_texto(texto, largo)

    def medir(self, texto, fecha):
        """El semáforo con el texto como titular (corto) o como cuerpo (largo), igual que el agente."""
        if len(texto.split()) <= semaforo.PALABRAS_CORTO:
            return self.semaforo.medir("", fecha, titular=texto), (texto, "", "")
        return self.semaforo.medir(texto, fecha), ("", "", texto)

    def _frase_oficial(self, doc_id, palabra):
        """Una oración literal del comunicado que contiene la palabra (primero en el resumen)."""
        orden = {"resumen": 0, "titular": 1, "cuerpo": 2}
        propios = [p for p in self.corpus.parrafos
                   if p["doc_id"] == doc_id and not p["duplicado_de"] and p["seccion"] in orden]  # fmt: skip
        parrafos = sorted(propios, key=lambda p: (orden[p["seccion"]], int(p["orden"])))
        for p in parrafos:
            for frase in enfen.FRASE.split(p["texto"]):
                if palabra and re.search(rf"\b{re.escape(palabra)}", frase, re.I):
                    return {"cita": frase.strip(), "parrafo": p["id"]}
        return None

    def _oficial_de_dato(self, fila, ref, respaldo):
        """Lo que dice el ENFEN sobre ese dato en el comunicado vigente (y en el anterior que lo respaldaba)."""
        c = self.comunicado(ref["id"])
        if fila["dato"] == "magnitud":
            dice = f"magnitud máxima prevista para la costa: {c['magnitud'] or 'sin magnitud'}"
            palabra = c["magnitud"]
        elif fila["dato"] == "estado":
            dice = f"estado: {c['estado']}"
            palabra = c["estado"].split()[0] if c["estado"] else ""
        elif fila["dato"] == "fecha":
            dice = f"plazo: {c['plazo']}" if c["plazo"] else "no da un plazo para ese dato"
            palabra = "hasta"
        else:
            dice = "da sus pronósticos con condicional (por ejemplo, «podría» o «se espera»)"
            palabra = ""
        salida = {"comunicado": c, "dice": dice, "cita": self._frase_oficial(ref["id"], palabra)}
        if respaldo:
            salida["anterior"] = self.comunicado(respaldo["id"])
        return salida

    def _afirmaciones(self, titular, resumen, cuerpo, fecha):
        i = discrepancia.indice_vigente(self.historia, fecha)
        salida = []
        for a in af.afirmaciones(titular, resumen, cuerpo, fecha):
            filas = discrepancia.clasificar(a, fecha, self.historia)
            if not filas:
                continue
            datos = []
            for f in filas:
                nivel, icono, veredicto = tx.VEREDICTO_DATO[f["categoria"]]
                respaldo = self.historia[i - f["atras"]] if f["atras"] else None
                datos.append({"dato": f["dato"], "dato_texto": tx.DATO[f["dato"]],
                              "valor": valor_legible(f["dato"], f["valor"]), "categoria": f["categoria"],
                              "nivel": nivel, "icono": icono, "veredicto": veredicto,
                              "resaltado": resaltar(a["_texto"], f["dato"], f["valor"]),
                              "oficial": self._oficial_de_dato(f, self.historia[i], respaldo)})  # fmt: skip
            salida.append({"frase": a["_texto"], "datos": datos})
        return salida

    def linea_tiempo(self, fecha, respaldos=()):
        i = discrepancia.indice_vigente(self.historia, fecha)
        if i is None:
            return []
        tramo = self.historia[max(0, i - COMUNICADOS_EN_LINEA + 1) : i + 1]
        return [{**self.comunicado(r["id"]), "vigente": r is self.historia[i], "respaldo": r["id"] in respaldos}
                for r in tramo]  # fmt: skip

    def parrafo(self, parrafo_id):
        p = self.parrafos[parrafo_id]
        doc = self.comunicado(p["doc_id"]) if p["doc_id"] in self.comunicados else None
        return {"texto": p["texto"], "parrafo": p["id"], "comunicado": doc}

    def verificar(self, texto, fecha, macroregion, interes=None):
        r, (titular, resumen, cuerpo) = self.medir(texto, fecha)
        # U6: el color y el método no salen de aquí; el nivel solo es un veredicto cuando hay datos
        salida = {"fecha": fecha, "palabras": r["palabras"], "estado": self.estado(fecha, macroregion)}
        if r["origen"] in ("reglas", "distancia") and not self.en_tema(texto, bool(cuerpo)):
            # Sección 9: un texto de otro tema no recibe cercanía ni veredicto
            r = {"origen": "fuera_de_tema", "parrafo": None}
        afirmaciones = self._afirmaciones(titular, resumen, cuerpo, fecha) if r["origen"] == "reglas" else []
        if r["origen"] == "reglas":
            categorias = {d["categoria"] for a in afirmaciones for d in a["datos"]}
            grave = next(c for c in tx.GRAVEDAD if c in categorias)
            nivel = NIVEL_DE_COLOR[r["color"]]
            respaldos = {d["oficial"]["anterior"]["id"] for a in afirmaciones for d in a["datos"]
                         if "anterior" in d["oficial"]}  # fmt: skip
            salida |= {"tipo": "datos", "nivel": nivel, "icono": tx.VEREDICTO_DATO[grave][1],
                       "titulo": tx.VEREDICTO_DATO[grave][2], "resumen": tx.RESUMEN_DATOS[nivel],
                       "aviso": tx.AVISO_NO_COINCIDE if nivel == tx.NO_COINCIDE else None,
                       "afirmaciones": afirmaciones,
                       "linea_tiempo": self.linea_tiempo(fecha, respaldos) if respaldos else []}  # fmt: skip
        elif r["origen"] == "distancia":
            u = r["umbrales"]
            salida |= {"tipo": "cercania", "nivel": r["banda"], "titulo": f"Cercanía: {tx.CERCANIA[r['banda']]}",
                       "resumen": tx.CERCANIA_FRASE[r["banda"]], "aviso": tx.SIN_DATOS,
                       "medidor": {"valor": r["coseno"], "media_desde": u["lejano"],
                                   "alta_desde": u["cercano"]}}  # fmt: skip
        elif r["origen"] == "fuera_de_tema":
            salida |= {"tipo": "fuera_de_tema", "nivel": None, "titulo": tx.FUERA_DE_TEMA,
                       "resumen": tx.FUERA_DE_TEMA_AYUDA, "aviso": None}  # fmt: skip
        else:
            salida |= {"tipo": "insuficiente", "nivel": None, "titulo": tx.INSUFICIENTE, "resumen": "",
                       "aviso": None}  # fmt: skip
        salida["oficial_cercano"] = self.parrafo(r["parrafo"]) if r["parrafo"] else None
        salida["que_hacer"] = self.que_hacer(texto, fecha, macroregion, interes or INTERES_POR_DEFECTO)
        return salida

    def que_hacer(self, texto, fecha, macroregion, interes):
        q = herramientas.oficial().embeber([texto])[0] if texto.strip() else None
        puntaje = (lambda ts: herramientas.oficial().embeber(ts) @ q) if q is not None else None
        r = recomendador.oficial(self.corpus, fecha, macroregion, interes, puntaje)
        parrafos = sorted(r["parrafos"], key=lambda p: p["tipo"] != "recomendacion")[:PARRAFOS_QUE_HACER]
        return {"interes": interes, "interes_texto": tx.INTERESES[interes],
                "intereses": [{"id": k, "texto": v} for k, v in tx.INTERESES.items()],
                "oficiales": [self.parrafo(p["id"]) for p in parrafos],
                "nota": self.nota_reciente(fecha, macroregion)}  # fmt: skip

    def nota_reciente(self, fecha, macroregion):
        """La nota sobre El Niño más reciente de los últimos días cuyos datos coinciden con el ENFEN."""
        desde = (dt.date.fromisoformat(fecha) - dt.timedelta(days=DIAS_NOTA_RECIENTE)).isoformat()
        candidatas = [n for n in self.notas.values() if n["sobre_nino"] and n["color"] == "verde"
                      and desde <= n["fecha"] <= fecha and (macroregion in n["macroregiones"]
                                                            or "nacional" in n["macroregiones"])]  # fmt: skip
        if not candidatas:
            return None
        n = max(candidatas, key=lambda n: (n["fecha"], n["id"]))
        return {k: n[k] for k in CAMPOS_NOTA} | {"medio_texto": MEDIOS[n["medio"]]}

    # ------------------------------------------------ Preguntar

    def preguntar(self, consulta, fecha, macroregion, interes=None):
        perfil = {"macroregion": macroregion, "interes": interes or INTERES_POR_DEFECTO}
        r = agente.responder(consulta, hoy=fecha, perfil=perfil)
        citas = []
        for c in r["citas"]:
            doc = self.comunicado(c["documento"]) if c["documento"] in self.comunicados else None
            citas.append({"cita": c["cita"], "parrafo": c["parrafo"], "fuente": c["fuente"], "comunicado": doc,
                          "url": doc["url"] if doc else self._url_aviso(c["documento"])})  # fmt: skip
        p = r["parametros"]
        return {"herramienta": r["herramienta"], "texto": r["texto"], "citas": citas,
                "entendido": {"fecha": p["fecha"], "fecha_texto": fecha_texto(p["fecha"]),
                              "macroregion": p["macroregion"],
                              "macroregion_texto": tx.MACROREGIONES.get(p["macroregion"], p["macroregion"]),
                              "interes": p["interes"],
                              "interes_texto": tx.INTERESES.get(p["interes"], "")}}  # fmt: skip

    def _url_aviso(self, doc_id):
        aviso = self.corpus.avisos.get(doc_id)
        return aviso["url"] if aviso else None


@functools.cache
def servicio():
    return Servicio()


# ---------------------------------------------------------------- Panorama (sin modelos)


class Panorama:
    """Las secciones del Panorama desde los CSV; los filtros se aplican al pedirlas."""

    GRUPOS_A = (("coinciden", "Sus datos coinciden con el ENFEN"),
                ("difieren", "Sus datos difieren del ENFEN (anteriores, no dichos o distintos)"),
                ("sin_datos", "Sin datos comparables"))  # fmt: skip
    GRUPOS_B = {"respaldada": "Coincide", "desactualizada": "Dato anterior", "contradice": "No coincide",
                "sin_respaldo": "El ENFEN no lo dice", "otra_escala": "Otra escala"}  # fmt: skip
    MAGNITUDES = ("débil", "moderada", "fuerte", "extraordinaria")

    def __init__(self, notas, historia, comunicados):
        self.notas = [n for n in notas.values() if n["sobre_nino"] and n["fecha"] >= INICIO_PANORAMA]
        self.historia = historia
        self.comunicados = comunicados
        self.datos = [f for f in leer_csv(config.DIR_NLP / "discrepancia-todas.csv")]
        self.region_de = {(n["medio"], n["id"]): n["macroregiones"] for n in self.notas}

    def _filtrar(self, filas, desde, hasta, macroregion, clave=lambda f: (f["medio"], f["id"])):
        return [f for f in filas if _en_rango(f["fecha"], desde, hasta)
                and (not macroregion or macroregion in self.region_de.get(clave(f), ()))]  # fmt: skip

    def _comunicados(self, desde=None, hasta=None):
        salida = []
        for r, siguiente in zip(self.historia, [*self.historia[1:], None], strict=True):
            c = self.comunicados[r["id"]]
            hasta_c = siguiente["desde"] if siguiente else None
            if (hasta and r["desde"] > hasta) or (desde and hasta_c and hasta_c < desde):
                continue
            salida.append({"id": r["id"], "numero": numero_de(r["id"]), "desde": r["desde"], "hasta": hasta_c,
                           "estado": c["estado"], "magnitud": c["magnitud_max_prevista"]})  # fmt: skip
        return salida

    def linea(self, desde=None, hasta=None, macroregion=None):
        """A: notas sobre El Niño por semana en tres grupos, con los comunicados como franjas."""
        cuenta = collections.defaultdict(collections.Counter)
        for n in self._filtrar([n for n in self.notas if n["color"] is not None], desde, hasta, macroregion):
            grupo = ("sin_datos" if n["color"] == "sin_afirmaciones" else
                     "coinciden" if n["color"] == "verde" else "difieren")  # fmt: skip
            cuenta[_semana(n["fecha"])][grupo] += 1
        semanas = [{"semana": s, **{g: cuenta[s][g] for g, _ in self.GRUPOS_A}} for s in sorted(cuenta)]
        return {"grupos": [{"id": g, "texto": t} for g, t in self.GRUPOS_A], "semanas": semanas,
                "comunicados": self._comunicados(desde, hasta)}  # fmt: skip

    def magnitudes(self, desde=None, hasta=None, macroregion=None):
        """B: la magnitud oficial como escalón y cada dato de magnitud de las notas (escala costera)."""
        puntos = []
        for f in self._filtrar(self.datos, desde, hasta, macroregion):
            if f["dato"] != "magnitud" or f["escala"] != "costa" or f["categoria"] not in self.GRUPOS_B:
                continue
            puntos.append({"fecha": f["fecha"], "magnitud": f["valor"], "grupo": f["categoria"]})
        escalon = [{"desde": c["desde"], "hasta": c["hasta"], "magnitud": c["magnitud"], "numero": c["numero"]}
                   for c in self._comunicados(desde, hasta)]  # fmt: skip
        grupos = [{"id": k, "texto": v} for k, v in self.GRUPOS_B.items()]
        return {"magnitudes": list(self.MAGNITUDES), "grupos": grupos, "escalon": escalon, "puntos": puntos}

    def reaccion(self):
        """C: cuántas veces cambió la proporción de notas sobre El Niño tras cada comunicado (ronda c, descriptivo)."""
        por_fecha = {c["fecha_emision"]: c["id"] for c in self.comunicados.values() if c["tipo"] == "oficial"}
        filas = []
        for f in leer_csv(config.DIR_ANALITICA / "eventos-por-comunicado.csv"):
            doc = por_fecha.get(f["fecha"])
            veces = math.exp(float(f["proporcion_nino"]))
            filas.append({"fecha": f["fecha"], "numero": numero_de(doc) if doc else None, "veces": round(veces, 3)})
        return {"comunicados": filas}

    def temas(self, desde=None, hasta=None, macroregion=None):
        """D: notas por mes y categoría de interés (los tópicos sin categoría van a "Otros temas")."""
        categoria = {
            f["topico"]: f["categoria"] or "Otros temas" for f in leer_csv(config.DIR_NLP / "topicos-nombres.csv")
        }
        fecha_de = {(n["medio"], n["id"]): n["fecha"] for n in self.notas}
        filas = [{"medio": t["medio"], "id": t["id"], "fecha": fecha_de[(t["medio"], t["id"])],
                  "categoria": categoria[t["topico"]]}
                 for t in leer_csv(config.DIR_NLP / "topicos-notas.csv")
                 if (t["medio"], t["id"]) in fecha_de]  # fmt: skip
        cuenta = collections.defaultdict(collections.Counter)
        for f in self._filtrar(filas, desde, hasta, macroregion):
            cuenta[f["fecha"][:7]][f["categoria"]] += 1
        nombres = [*tx.INTERESES.values(), "Otros temas"]
        return {"categorias": nombres, "hasta": max(f["fecha"] for f in filas),  # los tópicos son del 7-nov
                "meses": [{"mes": m, **{c: cuenta[m][c] for c in nombres}} for m in sorted(cuenta)]}  # fmt: skip

    def citas(self):
        """E: proporción de notas sobre El Niño de cada medio que enlazan o mencionan a cada actor (alfabético)."""
        filas = [f for f in leer_csv(config.DIR_RED / "citas.csv") if f["grupo"] == "medio"
                 and f["actor"] in ("ENFEN", "SENAMHI", "INDECI")]  # fmt: skip
        medios = sorted({f["valor"] for f in filas}, key=lambda m: MEDIOS.get(m, m))
        return {"actores": ["ENFEN", "SENAMHI", "INDECI"],
                "medios": [{"medio": m, "medio_texto": MEDIOS.get(m, m),
                            "notas": next(int(f["notas"]) for f in filas if f["valor"] == m),
                            **{f["actor"]: float(f["proporcion"]) for f in filas if f["valor"] == m}}
                           for m in medios]}  # fmt: skip

    def youtube(self, desde=None, hasta=None, macroregion=None):
        """F: tasa de engagement frente a la cercanía por video (sin ids), más los 2 indicadores.

        Los puntos vencen con YouTube: si el archivo más reciente tiene más de 30 días (o no hay), F queda sin datos.
        Los indicadores son los del análisis completo; el filtro de fechas solo recorta la dispersión, y no hay región.
        """
        tipos = [{"id": k, "texto": v} for k, v in tx.TIPOS_CANAL.items()]
        base = {"tipos": tipos, "por_region": False, "nota": tx.CERCANIA_ES_TEMA}
        archivos = almacen.archivos(TIPO_PUNTOS, bases=(config.DIR_YOUTUBE,))
        if not archivos or almacen.vence(almacen.fecha_de(archivos[-1])) <= almacen.hoy():
            return base | {"disponible": False, "puntos": [], "indicador_tasa": [], "indicador_respuesta": None}
        filas = leer_csv(archivos[-1])
        puntos = [{"tipo": f["tipo"], "mes": f["mes"], "cercania": round(float(f["coseno"]), 4),
                   "tasa": round(float(f["tasa"]), 6)}
                  for f in filas if f["tipo"] in tx.TIPOS_CANAL
                  and _en_rango(f["mes"], desde and desde[:7], hasta and hasta[:7])]  # fmt: skip
        indicador_tasa = []
        for t in tx.TIPOS_CANAL:  # orden fijo de los tipos, nunca por tasa ni por cercanía (P12)
            tasas = [float(f["tasa"]) for f in filas if f["tipo"] == t]
            if tasas:
                indicador_tasa.append({"tipo": t, "texto": tx.TIPOS_CANAL[t], "mediana": statistics.median(tasas),
                                       "n": len(tasas)})  # fmt: skip
        web = leer_csv(config.DIR_ANALITICA / "web-engagement.csv")
        respuesta = next((f for f in web if f["parte"] == "A" and f["indicador"] == "respuesta"), None)
        rho = next((f for f in web if f["parte"] == "A" and f["indicador"] == "rho_dentro_del_canal"
                    and not f["grupo"]), None)  # fmt: skip
        indicador_respuesta = None
        if respuesta and rho:
            indicador_respuesta = {"respuesta": respuesta["valor"], "texto": tx.RESPUESTA_YOUTUBE[respuesta["valor"]],
                                   "rho": float(rho["valor"]), "ic_inf": float(rho["ic_inf"]),
                                   "ic_sup": float(rho["ic_sup"]), "n": int(rho["n"])}  # fmt: skip
        return base | {"disponible": True, "corte": almacen.fecha_de(archivos[-1]).isoformat(), "puntos": puntos,
                       "total": len(filas), "indicador_tasa": indicador_tasa,
                       "indicador_respuesta": indicador_respuesta}  # fmt: skip

    def hallazgos(self):
        reaccion = self.reaccion()["comunicados"]
        suben = sum(f["veces"] > 1 for f in reaccion)
        mediana = statistics.median(f["veces"] for f in reaccion) - 1
        con_color = [n for n in self.notas if n["color"] is not None]
        con_datos = [n for n in con_color if n["color"] != "sin_afirmaciones"]
        coinciden = sum(n["color"] == "verde" for n in con_datos)
        anteriores = [int(f["atras"]) for f in self.datos if f["categoria"] == "desactualizada"]
        notas_anteriores = len({(f["medio"], f["id"]) for f in self.datos if f["categoria"] == "desactualizada"})
        atras = statistics.median(anteriores) if anteriores else 0
        atras_texto = f"{atras:.0f} comunicado atrás" if atras == 1 else f"{atras:.0f} comunicados atrás"
        # Mini series de las tarjetas: veces por comunicado, % que coincide por mes y notas con un dato anterior por mes
        por_mes = collections.defaultdict(lambda: [0, 0])
        for n in con_datos:
            por_mes[n["fecha"][:7]][0] += n["color"] == "verde"
            por_mes[n["fecha"][:7]][1] += 1
        anteriores_por_mes = collections.defaultdict(set)
        for f in self.datos:
            if f["categoria"] == "desactualizada":
                anteriores_por_mes[f["fecha"][:7]].add((f["medio"], f["id"]))
        meses = sorted(set(por_mes) | set(anteriores_por_mes))
        return [
            {"id": "reaccion", "valor": f"{suben} de {len(reaccion)}",
             "texto": f"comunicados del ENFEN fueron seguidos por más notas sobre El Niño (mediana: "
                      f"{'+' if mediana >= 0 else ''}{mediana * 100:.0f} %).", "descriptivo": True,
             "serie": [{"x": f["fecha"], "y": f["veces"]} for f in reaccion]},
            {"id": "coinciden", "valor": f"{coinciden / len(con_datos) * 100:.0f} %",
             "texto": f"de las notas con datos comparables coinciden con el ENFEN. Solo el "
                      f"{len(con_datos) / len(con_color) * 100:.0f} % de las {len(con_color)} notas trae esos datos.",
             "descriptivo": False,
             "serie": [{"x": m, "y": round(por_mes[m][0] / por_mes[m][1], 4)} for m in meses if por_mes[m][1]]},
            {"id": "anteriores", "valor": str(notas_anteriores),
             "texto": f"notas usaron un dato de un comunicado anterior (mediana: {atras_texto}).",
             "descriptivo": False, "serie": [{"x": m, "y": len(anteriores_por_mes[m])} for m in meses]},
        ]  # fmt: skip


@functools.cache
def panorama():
    corpus = herramientas.corpus()  # sin el semáforo: el Panorama no usa modelos
    return Panorama(notas(), discrepancia.referencia(corpus), {c["id"]: c for c in corpus.comunicados})
