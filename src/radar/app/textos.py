"""Lo que lee el ciudadano: veredictos, cercanía y ayudas en palabras simples (docs/app/definicion.md, D1).

Es la única fuente de estos textos: la interfaz los muestra tal cual y las pruebas U2, U3 y U6 los revisan.
"""

# Veredicto por dato (capa 5): categoría -> (nivel, ícono, frase corta)
COINCIDE, REVISAR, NO_COINCIDE = "coincide", "revisar", "no_coincide"
VEREDICTO_DATO = {
    "respaldada": (COINCIDE, "✓", "Coincide con el ENFEN"),
    "desactualizada": (REVISAR, "!", "Usa un dato anterior del ENFEN"),
    "sin_respaldo": (REVISAR, "!", "El ENFEN no dice eso"),
    "mas_certeza": (REVISAR, "!", "Lo afirma con más seguridad que el ENFEN"),
    "otra_escala": (REVISAR, "!", "Usa otra escala que la del ENFEN para la costa"),
    "contradice": (NO_COINCIDE, "✕", "No coincide con el ENFEN"),
    "otra_fuente": (None, "·", "Lo dice otra fuente, no el ENFEN"),
}
# Del más grave al menos grave: la frase del resultado general sale de la categoría más grave presente
GRAVEDAD = ("contradice", "desactualizada", "sin_respaldo", "mas_certeza", "otra_escala", "respaldada")

RESUMEN_DATOS = {
    COINCIDE: "Los datos que da este texto coinciden con el comunicado vigente del ENFEN.",
    REVISAR: "Algunos datos de este texto no son los del comunicado vigente del ENFEN. Revisa por qué.",
    NO_COINCIDE: "Al menos un dato de este texto no coincide con el comunicado vigente del ENFEN.",
}
AVISO_NO_COINCIDE = "Una máquina leyó la frase y puede fallar. Antes de concluir, mira la comparación."

DATO = {"magnitud": "Magnitud", "estado": "Estado", "fecha": "Fechas", "certeza": "Seguridad"}
ESTADO = {"no_activo": "No activo", "vigilancia": "Vigilancia", "alerta": "Alerta"}

# Sin datos comparables: cercanía, nunca un veredicto (D1)
CERCANIA = {"cercano": "Alta", "intermedio": "Media", "lejano": "Baja"}
SIN_DATOS = (
    "Este texto no trae datos que podamos comparar, como magnitud, estado o fechas. Solo medimos si habla de lo"
    " mismo que el comunicado vigente. No medimos si es cierto."
)
CERCANIA_FRASE = {
    "cercano": "Habla de lo mismo que el comunicado vigente del ENFEN.",
    "intermedio": "Se parece en parte a lo que dice el comunicado vigente del ENFEN.",
    "lejano": "Habla de otra cosa que el comunicado vigente del ENFEN.",
}
INSUFICIENTE = "El texto es muy corto para compararlo. Pega el titular completo o el mensaje."

INTERESES = {
    "pesca": "Pesca y mar",
    "lluvias": "Lluvias, ríos y huaicos",
    "calor": "Calor",
    "prevencion": "Prevención y emergencias",
}
MACROREGIONES = {"costa_norte": "Costa norte", "costa_centro": "Costa centro", "lima": "Lima y Callao"}

# U2: no aparecen en Verificar ni en Preguntar
JERGA = ("capa", "distancia", "coseno", "umbral", "auc", "nli", "embedding", "origen", "percentil")
# U6: nunca en un resultado sin datos
PROMESAS = ("correcto", "verdadero", "falso", "verdad")


def textos_del_ciudadano():
    """Todos los textos de Verificar y Preguntar que vienen de la API (para U2, U3 y U6)."""
    salida = [v[2] for v in VEREDICTO_DATO.values()] + list(RESUMEN_DATOS.values()) + [AVISO_NO_COINCIDE]
    salida += list(CERCANIA_FRASE.values()) + [SIN_DATOS, INSUFICIENTE]
    return salida
