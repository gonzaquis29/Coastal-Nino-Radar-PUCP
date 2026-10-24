"""Qué rige en una fecha y macro-región: comunicado del ENFEN vigente y avisos del Senamhi aplicables.

Lo usan el agente (estado_vigente, buscar_oficial), el recomendador y el índice de discrepancia.
Las reglas están en docs/oficial/definicion.md ("Vigencia").
"""
from oficial.comun import DIR_OFICIAL, leer_csv

ORDEN_NIVEL = ["", "VERDE", "AMARILLO", "NARANJA", "ROJO"]
MACRO_AVISOS = {"costa_norte": "costa_norte", "costa_centro": "costa_centro", "lima": "costa_centro"}  # Lima usa costa centro


class Corpus:
    def __init__(self, directorio=DIR_OFICIAL):
        self.comunicados = sorted(leer_csv(directorio / "comunicados.csv"), key=lambda c: (c["fecha_emision"], c["id"]))
        self.avisos = {a["id"]: a for a in leer_csv(directorio / "avisos.csv")}
        self.dias = leer_csv(directorio / "aviso_dias.csv")
        self.parrafos = leer_csv(directorio / "parrafos.csv")

    # ------------------------------------------------------------ ENFEN

    def comunicado_vigente(self, fecha):
        """Último comunicado emitido hasta la fecha (incluida). None antes del primero del corpus."""
        previos = [c for c in self.comunicados if c["fecha_emision"] <= fecha]
        return previos[-1] if previos else None

    def comunicados_a_comparar(self, fecha):
        """El vigente y, si la fecha es día de emisión, también el anterior (no se sabe la hora de publicación)."""
        vig = self.comunicado_vigente(fecha)
        if vig is None:
            return []
        if vig["fecha_emision"] == fecha:
            i = self.comunicados.index(vig)
            return [vig] + ([self.comunicados[i - 1]] if i > 0 else [])
        return [vig]

    # ------------------------------------------------------------ Senamhi

    def avisos_aplicables(self, fecha, macroregion):
        """Avisos no cancelados, emitidos hasta la fecha y no vencidos, de esa macro-región.

        estado_en_fecha: 'vigente' si la fecha es un día del evento en esa macro-región; 'emitido' si el evento aún no empieza.
        """
        m = MACRO_AVISOS.get(macroregion)
        if not m:
            return []
        out = []
        for a in self.avisos.values():
            if a["estado"] == "cancelado" or not (a["emision"] <= fecha <= a["fin"][:10]) or m not in a["macroregiones"].split("|"):
                continue
            dias = [d for d in self.dias if d["aviso_id"] == a["id"] and d["macroregion"] == m]
            hoy = [d for d in dias if d["fecha"] == fecha]
            if hoy:
                estado, nivel = "vigente", max((d["nivel_macroregion"] for d in hoy), key=ORDEN_NIVEL.index)
            elif dias and fecha < min(d["fecha"] for d in dias):
                estado, nivel = "emitido", max((d["nivel_macroregion"] for d in dias), key=ORDEN_NIVEL.index)
            else:
                continue  # el evento ya pasó en esa macro-región, aunque el aviso siga en otras
            out.append({"id": a["id"], "numero": a["numero"], "titulo": a["titulo"], "tipo": a["tipo"], "nivel": nivel,
                        "estado_en_fecha": estado, "inicio": a["inicio"], "fin": a["fin"], "url": a["url"]})
        return sorted(out, key=lambda x: (x["tipo"], -ORDEN_NIVEL.index(x["nivel"]), x["id"]))

    # ------------------------------------------------------------ agente

    def estado_vigente(self, fecha, macroregion):
        """Resumen para la herramienta estado_vigente(fecha, región) del agente."""
        com = self.comunicado_vigente(fecha)
        avisos = self.avisos_aplicables(fecha, macroregion)
        nivel = {}
        for a in avisos:
            if a["estado_en_fecha"] == "vigente":
                nivel[a["tipo"]] = max(nivel.get(a["tipo"], ""), a["nivel"], key=ORDEN_NIVEL.index)
        return {"fecha": fecha, "macroregion": macroregion,
                "comunicado": {k: com[k] for k in ["id", "fecha_emision", "estado", "magnitud_max_prevista", "magnitudes_mencionadas", "url"]} if com else None,
                "dia_de_cambio": bool(com and com["fecha_emision"] == fecha),
                "avisos": avisos, "nivel_maximo_por_tipo": nivel}

    def parrafos_vigentes(self, fecha, macroregion=None, sin_duplicados=True):
        """Párrafos oficiales que rigen en la fecha: los del comunicado vigente (y el anterior el día de cambio) y los de avisos aplicables."""
        docs = {c["id"] for c in self.comunicados_a_comparar(fecha)}
        if macroregion:
            docs |= {a["id"] for a in self.avisos_aplicables(fecha, macroregion)}
        return [p for p in self.parrafos if p["doc_id"] in docs and not (sin_duplicados and p["duplicado_de"])]
