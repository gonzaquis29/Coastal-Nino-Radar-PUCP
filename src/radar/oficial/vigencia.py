"""Qué rige en una fecha y macro-región: comunicado del ENFEN vigente y avisos del Senamhi aplicables.

Lo usan el agente (estado_vigente, buscar_oficial), el recomendador y el índice de discrepancia.
Reglas en docs/oficial/definicion.md ("Vigencia").
"""

from radar import config
from radar.comun.archivos import leer_csv
from radar.comun.regiones import macroregion_de_avisos
from radar.oficial.vocabulario import CANCELADO, EMITIDO, VIGENTE, mayor_nivel, orden_nivel


class Corpus:
    def __init__(self, directorio=config.DIR_OFICIAL):
        self.comunicados = sorted(leer_csv(directorio / "comunicados.csv"), key=lambda c: (c["fecha_emision"], c["id"]))
        self.avisos = {a["id"]: a for a in leer_csv(directorio / "avisos.csv")}
        self.dias_por_aviso = {}
        for d in leer_csv(directorio / "aviso_dias.csv"):
            self.dias_por_aviso.setdefault(d["aviso_id"], []).append(d)
        self.parrafos = leer_csv(directorio / "parrafos.csv")

    # ------------------------------------------------------------ ENFEN

    def comunicado_vigente(self, fecha):
        """Último comunicado emitido hasta la fecha (incluida); None antes del primero del corpus."""
        previos = [c for c in self.comunicados if c["fecha_emision"] <= fecha]
        return previos[-1] if previos else None

    def comunicados_a_comparar(self, fecha):
        """El vigente y, si la fecha es día de emisión, también el anterior (no se sabe la hora de publicación)."""
        vigente = self.comunicado_vigente(fecha)
        if vigente is None:
            return []
        if vigente["fecha_emision"] != fecha:
            return [vigente]
        i = self.comunicados.index(vigente)
        return [vigente] + ([self.comunicados[i - 1]] if i > 0 else [])

    # ------------------------------------------------------------ Senamhi

    def avisos_aplicables(self, fecha, macroregion):
        """Avisos no cancelados, emitidos hasta la fecha y no vencidos, de esa macro-región.

        estado_en_fecha: 'vigente' si la fecha es un día del evento allí; 'emitido' si el evento aún no empieza.
        """
        macro = macroregion_de_avisos(macroregion)
        if not macro:
            return []
        aplicables = []
        for aviso in self.avisos.values():
            if aviso["estado"] == CANCELADO or not (aviso["emision"] <= fecha <= aviso["fin"][:10]):
                continue
            if macro not in aviso["macroregiones"].split("|"):
                continue
            dias = [d for d in self.dias_por_aviso.get(aviso["id"], []) if d["macroregion"] == macro]
            hoy = [d for d in dias if d["fecha"] == fecha]
            if hoy:
                estado, nivel = VIGENTE, mayor_nivel(d["nivel_macroregion"] for d in hoy)
            elif dias and fecha < min(d["fecha"] for d in dias):
                estado, nivel = EMITIDO, mayor_nivel(d["nivel_macroregion"] for d in dias)
            else:
                continue  # el evento ya pasó en esa macro-región, aunque el aviso siga en otras
            aplicables.append(
                {
                    "id": aviso["id"],
                    "numero": aviso["numero"],
                    "titulo": aviso["titulo"],
                    "tipo": aviso["tipo"],
                    "nivel": nivel,
                    "estado_en_fecha": estado,
                    "inicio": aviso["inicio"],
                    "fin": aviso["fin"],
                    "url": aviso["url"],
                }
            )
        return sorted(aplicables, key=lambda a: (a["tipo"], -orden_nivel(a["nivel"]), a["id"]))

    # ------------------------------------------------------------ agente

    def estado_vigente(self, fecha, macroregion):
        """Resumen para la herramienta estado_vigente(fecha, región) del agente."""
        comunicado = self.comunicado_vigente(fecha)
        avisos = self.avisos_aplicables(fecha, macroregion)
        nivel_por_tipo = {}
        for a in avisos:
            if a["estado_en_fecha"] == VIGENTE:
                nivel_por_tipo[a["tipo"]] = mayor_nivel([nivel_por_tipo.get(a["tipo"], ""), a["nivel"]])
        campos = ("id", "fecha_emision", "estado", "magnitud_max_prevista", "magnitudes_mencionadas", "url")
        return {
            "fecha": fecha,
            "macroregion": macroregion,
            "comunicado": {k: comunicado[k] for k in campos} if comunicado else None,
            "dia_de_cambio": bool(comunicado and comunicado["fecha_emision"] == fecha),
            "avisos": avisos,
            "nivel_maximo_por_tipo": nivel_por_tipo,
        }

    def parrafos_vigentes(self, fecha, macroregion=None, sin_duplicados=True):
        """Párrafos que rigen en la fecha: comunicado vigente (y el anterior el día de cambio) y avisos aplicables."""
        documentos = {c["id"] for c in self.comunicados_a_comparar(fecha)}
        if macroregion:
            documentos |= {a["id"] for a in self.avisos_aplicables(fecha, macroregion)}
        return [p for p in self.parrafos if p["doc_id"] in documentos and not (sin_duplicados and p["duplicado_de"])]
