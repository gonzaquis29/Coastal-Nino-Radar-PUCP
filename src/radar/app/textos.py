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

# Panorama F (YouTube): tipos de canal y la respuesta de W2 en palabras (docs/analitica/web.md, sección 6)
TIPOS_CANAL = {"medio": "Medios", "oficial": "Instituciones oficiales", "otros": "Otros canales"}
CERCANIA_ES_TEMA = "La cercanía mide si un video habla del mismo tema que el ENFEN, no si está de acuerdo con él."
RESPUESTA_YOUTUBE = {
    "sí": "Sí. Dentro de un mismo canal, los videos que hablan de otro tema que el ENFEN tienen algo más de"
    " interacción.",
    "no": "No. Dentro de un mismo canal, la interacción no cambia con la cercanía al ENFEN.",
    "no concluyente": "No se puede decir. Los datos no alcanzan para saber si la interacción cambia con la cercanía.",
}

# U2: no aparecen en Verificar ni en Preguntar
JERGA = ("capa", "distancia", "coseno", "umbral", "auc", "nli", "embedding", "origen", "percentil")
# U6: nunca en un resultado sin datos
PROMESAS = ("correcto", "verdadero", "falso", "verdad")


def textos_del_ciudadano():
    """Todos los textos de Verificar y Preguntar que vienen de la API (para U2, U3 y U6)."""
    salida = [v[2] for v in VEREDICTO_DATO.values()] + list(RESUMEN_DATOS.values()) + [AVISO_NO_COINCIDE]
    salida += list(CERCANIA_FRASE.values()) + [SIN_DATOS, INSUFICIENTE]
    return salida


# ---------------------------------------------------------------- interfaz (web/)
# Etiquetas, ayudas y mensajes de las pantallas. `python -m radar.app.textos` los escribe en
# web/src/generado/textos.json, que la interfaz importa: así no hay textos del ciudadano fuera de este módulo.
# Las llaves {x} se rellenan en la interfaz con datos de la API.
INTERFAZ = {
    "comun": {
        "marca": "Radar Niño Costero",
        "lema": "Compara lo que circula sobre El Niño con lo que dice el ENFEN",
        "nav_verificar": "Verificar",
        "nav_preguntar": "Preguntar",
        "nav_panorama": "Panorama",
        "nav_metodologia": "Cómo lo hicimos",
        "nav_principal": "Secciones",
        "tema": "Tema",
        "tema_sistema": "Como el sistema",
        "tema_claro": "Claro",
        "tema_oscuro": "Oscuro",
        "saltar": "Ir al contenido",
        "arrancando": "La app se está abriendo. Espera un poco.",
        "sin_conexion": "No hay conexión. Revisa tu internet y prueba otra vez.",
        "error": "Algo salió mal. Inténtalo otra vez.",
        "reintentar": "Reintentar",
        "cargando": "Cargando…",
        "fuente": "Fuente",
        "comunicado": "Comunicado N.° {numero} del ENFEN, {fecha}",
        "abrir_fuente": "Abrir la fuente oficial",
        "pie": "Hecho con datos públicos del ENFEN, el Senamhi y cuatro medios. No reemplaza los avisos oficiales.",
    },
    "verificar": {
        "titulo": "¿Coincide con el ENFEN?",
        "zona": "Tu zona",
        "elige_zona": "¿En qué zona estás?",
        "elige_zona_ayuda": "La guardamos en este equipo para la próxima vez.",
        "cambiar_zona": "Cambiar zona",
        "magnitud_prevista": "magnitud prevista: {magnitud}",
        "sin_comunicado": "No hay un comunicado del ENFEN para esa fecha.",
        "avisos": "{n} avisos del Senamhi",
        "aviso_uno": "1 aviso del Senamhi",
        "sin_avisos": "Sin avisos del Senamhi",
        "avisos_titulo": "Avisos del Senamhi para tu zona",
        "aviso_hasta": "hasta el {fin}",
        "cuadro": "Pega aquí el titular o mensaje",
        "cuadro_ayuda": "Puede ser un titular, un mensaje de WhatsApp o una nota completa.",
        "boton": "Verificar",
        "verificando": "Verificando…",
        "otra_fecha": "¿Es de otra fecha?",
        "fecha": "Fecha del texto",
        "fecha_hoy": "Usar la fecha de hoy",
        "vacio": "Pega un texto para verificarlo.",
        "ver_por_que": "Ver por qué",
        "ocultar": "Ocultar el detalle",
        "lo_que_dice_texto": "Lo que dice el texto",
        "lo_que_dice_enfen": "Lo que dice el ENFEN",
        "dato_anterior": "Ese dato es del Comunicado N.° {numero} ({fecha}).",
        "ver_mas": "Ver {n} frases más",
        "linea_titulo": "Últimos comunicados del ENFEN",
        "vigente": "vigente",
        "de_aqui": "el dato viene de aquí",
        "cercania_medidor": "Cercanía con lo que dice hoy el ENFEN",
        "baja": "Baja",
        "media": "Media",
        "alta": "Alta",
        "oficial_titulo": "Lo que dice el ENFEN",
        "oficial_ayuda": "El párrafo del comunicado que más se parece a tu texto, tal como lo escribió el ENFEN.",
        "que_hacer": "Qué hacer",
        "que_te_interesa": "¿Qué te interesa?",
        "recomendacion": "Recomendación oficial",
        "nota_reciente": "Una nota reciente que coincide con el ENFEN",
        "sin_que_hacer": "No hay consejos del ENFEN para este tema hoy.",
        "compartir": "Compartir",
        "copiado": "Copiamos el texto y el enlace. Pégalos donde quieras.",
        "compartir_texto": "Lo revisé en Radar Niño Costero: {titulo}. Según el Comunicado N.° {numero} del ENFEN"
        " ({fecha}).",
        "compartir_sin_comunicado": "Lo revisé en Radar Niño Costero: {titulo}.",
        "nueva": "Verificar otro texto",
    },
    "preguntar": {
        "titulo": "Pregunta sobre El Niño costero",
        "cuadro": "Escribe tu pregunta",
        "boton": "Preguntar",
        "pensando": "Buscando en los comunicados…",
        "ejemplos": "Puedes empezar por una de estas:",
        "ejemplo_1": "¿Hay alerta en Lima?",
        "ejemplo_2": "¿Qué dice el ENFEN sobre la pesca?",
        "ejemplo_3": "¿Qué magnitud se espera en la costa norte?",
        "entendido": "Así leímos tu pregunta",
        "entendido_ayuda": "Si algo no es lo que querías, cámbialo y vuelve a preguntar.",
        "zona": "Zona",
        "fecha": "Fecha",
        "tema": "Tema",
        "repetir": "Preguntar de nuevo",
        "citas": "Lo que dicen las fuentes",
        "tu_pregunta": "Tu pregunta",
        "respuesta": "Respuesta",
    },
    "panorama": {
        "titulo": "Panorama de 2026",
        "intro": "Cómo se habló de El Niño en cuatro medios y en YouTube, frente a lo que dijo el ENFEN.",
        "hallazgos": "Lo principal",
        "filtros": "Filtros",
        "desde": "Desde",
        "hasta": "Hasta",
        "region": "Macro-región",
        "todas": "Todas",
        "limpiar": "Quitar filtros",
        "sin_region": "No depende de la región: muestra todo el país.",
        "sin_filtros": "No depende de los filtros.",
        "descriptivo": "Descriptivo",
        "descriptivo_ayuda": "Este análisis no pasó su criterio de validación: describe lo que pasó, pero no prueba"
        " un efecto.",
        "como_leer": "Cómo leer",
        "ver_tabla": "Ver tabla",
        "ver_grafico": "Ver gráfico",
        "descargar": "Descargar CSV",
        "sin_datos": "No hay datos para estos filtros.",
        "sin_youtube": "Los datos de YouTube vencieron o todavía no están: se borran a los 30 días.",
        "a_titulo": "¿Cómo se habló de El Niño frente a lo oficial?",
        "a_leer": "Arriba, la magnitud que preveía el ENFEN en cada comunicado. Abajo, las notas por semana según"
        " sus datos coincidan, difieran o no traigan datos.",
        "a_oficial": "Magnitud prevista por el ENFEN",
        "a_notas": "Notas por semana",
        "b_titulo": "¿Qué magnitud decían las notas?",
        "b_leer": "La línea es la magnitud que preveía el ENFEN. Cada punto es una magnitud dicha en una nota.",
        "b_coincide": "Coincide con el ENFEN",
        "b_otros": "Difiere: dato anterior, no dicho, otra escala o distinto",
        "c_titulo": "¿Reacciona la cobertura a cada comunicado?",
        "c_eje": "Proporción de notas sobre El Niño, frente a la semana anterior (escala logarítmica)",
        "c_igual": "sin cambio",
        "d_hasta": "Los temas se calcularon con las notas hasta el {fecha}.",
        "f_eje_x": "Cercanía con lo que dice el ENFEN",
        "f_eje_y": "Interacción por vista (escala logarítmica)",
        "f_corte": "Datos de YouTube descargados el {fecha}; se borran a los 30 días.",
        "c_leer": "Cada punto compara la proporción de notas sobre El Niño en los 3 días después del comunicado con"
        " la semana anterior. A la derecha de la línea, subió.",
        "d_titulo": "¿De qué se habló?",
        "d_leer": "Notas por mes según su tema, con las cuatro categorías de interés de la app.",
        "e_titulo": "¿Quién cita a lo oficial?",
        "e_leer": "Proporción de las notas de cada medio que enlazan o mencionan a cada institución. Los medios van"
        " en orden alfabético.",
        "f_titulo": "YouTube: interacción y cercanía con lo oficial",
        "f_leer": "Cada punto es un video. A la derecha, habla más de lo mismo que el ENFEN; arriba, tuvo más"
        " interacción (me gusta y comentarios por vista).",
        "f_tasa": "Interacción mediana por tipo de canal",
        "f_tasa_ayuda": "Me gusta y comentarios por cada vista, con todos los videos.",
        "f_respuesta": "¿La interacción cambia con la cercanía?",
        "f_ic": "ρ parcial dentro del canal {rho} (IC 95 %: {inf} a {sup}), con {n} videos de canales con 3 o más.",
        "f_n": "{n} videos",
        "semana": "Semana",
        "mes": "Mes",
        "fecha": "Fecha",
        "magnitud": "Magnitud",
        "grupo": "Grupo",
        "notas": "Notas",
        "veces": "Cambio",
        "comunicado": "Comunicado",
        "medio": "Medio",
        "tipo": "Tipo de canal",
        "cercania": "Cercanía",
        "tasa": "Interacción",
        "estado": "Estado",
        "proporcion": "Proporción",
        "institucion": "Institución",
    },
    "metodologia": {
        "titulo": "Cómo lo hicimos",
        "intro": "Cada parte se validó con un criterio fijado antes de ver los resultados, sin etiquetar datos a mano.",
        "validacion": "Cómo lo validamos",
        "pasa": "Pasa",
        "no_pasa": "No pasa",
        "pasan": "{pasan} de {total} criterios",
        "ver_criterios": "Ver criterios",
        "criterio": "Criterio",
        "valor": "Valor",
        "umbral": "Umbral",
        "uso": "Uso de esta app",
        "uso_ayuda": "Registro anónimo: sin texto, IP, cookies ni identificadores.",
        "sesiones": "Sesiones",
        "embudo": "Embudo",
        "segundos": "Segundos promedio por pantalla",
        "limitaciones": "Limitaciones",
        "sin_uso": "Todavía no hay uso registrado.",
    },
}

# Las pantallas del ciudadano: U2 y U6 se miden también sobre sus textos
PANTALLAS_DEL_CIUDADANO = ("comun", "verificar", "preguntar")
# Las ayudas que se leen como frase (U3); las etiquetas cortas no tienen sentido para INFLESZ
AYUDAS = (("verificar", "elige_zona_ayuda"), ("verificar", "cuadro_ayuda"), ("verificar", "oficial_ayuda"),
          ("verificar", "sin_que_hacer"), ("verificar", "copiado"), ("preguntar", "entendido_ayuda"),
          ("comun", "sin_conexion"), ("comun", "arrancando"))  # fmt: skip


def textos_de_la_interfaz():
    return [t for p in PANTALLAS_DEL_CIUDADANO for t in INTERFAZ[p].values()]


def para_la_interfaz():
    """Lo que importa web/: la interfaz y las listas que muestra tal cual."""
    return {**INTERFAZ, "macroregiones": MACROREGIONES, "intereses": INTERESES, "cercania": CERCANIA}


def generar():
    import json

    from radar import config
    from radar.comun.archivos import escribir_atomico

    destino = config.DIR_WEB / "src" / "generado" / "textos.json"
    texto = json.dumps(para_la_interfaz(), ensure_ascii=False, indent=1) + "\n"
    escribir_atomico(destino, texto.encode("utf-8"))
    return destino


if __name__ == "__main__":
    print(f"Textos de la interfaz en {generar()}")
