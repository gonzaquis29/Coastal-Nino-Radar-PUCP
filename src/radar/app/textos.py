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
# La regla de magnitud de la interfaz (sección 11), de menor a mayor
MAGNITUDES = ("Débil", "Moderada", "Fuerte", "Extraordinaria")

# Sin datos comparables: cercanía, nunca un veredicto (D1). Sección 11: el título dice que no hay un dato que revisar
# y la cercanía queda como una línea chica, para que nadie la lea como «coincide».
CERCANIA = {"cercano": "Alta", "intermedio": "Media", "lejano": "Baja"}
SIN_DATO_TITULO = "No trae un dato que podamos comparar"
SIN_DATOS = "No dice qué tan fuerte será El Niño, ni su estado, ni sus fechas. Por eso no podemos decir si coincide."
CERCANIA_FRASE = {
    "cercano": "Habla del mismo tema que el comunicado del ENFEN. Eso no lo hace cierto.",
    "intermedio": "Habla en parte del mismo tema que el comunicado del ENFEN. Eso no lo hace cierto.",
    "lejano": "Habla de otro tema que el comunicado del ENFEN.",
}
INSUFICIENTE = "El texto es muy corto para compararlo. Pega el titular completo o el mensaje."
# Sección 9: el texto no trata del tema; sin medidor, sin color y sin ícono (U6)
FUERA_DE_TEMA = "Este texto no parece hablar de El Niño, del mar ni del clima."
FUERA_DE_TEMA_AYUDA = "Si sí habla de eso, pega la nota completa."

INTERESES = {
    "pesca": "Pesca y mar",
    "lluvias": "Lluvias, ríos y huaicos",
    "calor": "Calor",
    "prevencion": "Prevención y emergencias",
}
MACROREGIONES = {"costa_norte": "Costa norte", "costa_centro": "Costa centro", "lima": "Lima y Callao"}

# Preguntar: la respuesta en palabras simples. El texto del agente (radar.agente) es para su evaluación y no se
# muestra: trae fechas AAAA-MM-DD, ids y nombres internos. Las llaves se llenan en radar.app.servicio.
PREGUNTAR = {
    "estado": "Al {fecha}, el ENFEN dice: {estado}. Lo dijo en su comunicado N.° {numero}, del {emision}.",
    "estado_sin": "No hay un comunicado del ENFEN para el {fecha}.",
    "magnitud": "El ENFEN cree que su fuerza puede llegar a {magnitud}.",
    "avisos": "El Senamhi tiene estos avisos para tu zona ({region}): {avisos}.",
    "aviso": "el N.° {numero}, de {titulo}, con nivel {nivel}",
    "sin_avisos": "No hay avisos del Senamhi para tu zona ({region}) ese día.",
    "buscar": "Esto dicen los textos oficiales al {fecha}:",
    "buscar_sin": "No hay textos oficiales para el {fecha}.",
    "recomendar": "Para {interes} en tu zona ({region}), esto dice el ENFEN al {fecha}:",
    "medir_verde": "Los datos de ese texto coinciden con el comunicado del ENFEN.",
    "medir_amarillo": "Ese texto usa un dato anterior o que el ENFEN no dice. Mira el texto oficial.",
    "medir_rojo": "Ese texto tiene un dato distinto al del comunicado del ENFEN. Mira el texto oficial.",
    "medir_cercania": "Ese texto no trae datos para comparar. Su cercanía con lo que dice el ENFEN es {banda}.",
    "medir_corto": "Ese texto es muy corto para compararlo.",
    "mas_cercano": "El texto oficial más cercano:",
}

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

# Cifras de la prueba externa de 2025 (docs/app/definicion.md, 13.7): 21 de 333 en corto y 15 de 90 en cuerpo
LIMITACION_ALTA = (
    "Un texto de otro tema puede salir con «Alta». Pasa más si es largo o usa palabras de emergencias o del clima: en"
    " una prueba con textos así, fueron 6 de cada 100 cortos y 17 de cada 100 largos."
)
LIMITACIONES = (
    "La app mide cercanía con lo oficial; no dice si un texto es verdadero o falso.",
    "Solo se comparan las frases con datos (magnitud, estado o fechas); el 74 % de las notas no los trae.",
    "Una lectura automática puede equivocarse: por eso cada resultado muestra la frase y el dato comparados.",
    "Las macro-regiones son una agrupación supuesta; Google Trends da interés relativo y Tumbes tiene pocos datos.",
    "No hubo pruebas con usuarios: la única evidencia de uso es el registro anónimo de esta app.",
    LIMITACION_ALTA,
)


def textos_del_ciudadano():
    """Todos los textos de Verificar y Preguntar que vienen de la API (para U2, U3 y U6)."""
    salida = [v[2] for v in VEREDICTO_DATO.values()] + list(RESUMEN_DATOS.values()) + [AVISO_NO_COINCIDE]
    salida += list(CERCANIA_FRASE.values()) + [
        SIN_DATO_TITULO,
        SIN_DATOS,
        INSUFICIENTE,
        FUERA_DE_TEMA,
        FUERA_DE_TEMA_AYUDA,
    ]
    salida += list(PREGUNTAR.values())
    return salida


# ---------------------------------------------------------------- interfaz (web/)
# Etiquetas, ayudas y mensajes de las pantallas. `python -m radar.app.textos` los escribe en
# web/src/generado/textos.json, que la interfaz importa: así no hay textos del ciudadano fuera de este módulo.
# Las llaves {x} se rellenan en la interfaz con datos de la API.
INTERFAZ = {
    "comun": {
        "marca": "Radar Niño Costero",
        "lema": "Compara lo que circula sobre El Niño con lo que dice el ENFEN",
        "marca_corta": "Radar",
        "nav_verificar": "Hoy",
        "nav_preguntar": "Preguntar",
        "nav_panorama": "Cómo se habló",
        "nav_glosario": "¿Qué es el ENFEN?",
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
        "cerrar": "Cerrar",
    },
    # Sección 11: las palabras que no todos conocen; se abren al tocarlas y desde el menú
    "glosario": {
        "titulo": "Palabras que usamos",
        "abrir": "Qué quiere decir {termino}",
        "enfen_titulo": "¿Qué es el ENFEN?",
        "enfen": "Es la comisión del Estado peruano que estudia El Niño. Vigila el mar y el aire, y cada pocas semanas"
        " publica un comunicado oficial. Ahí dice si hay alerta, qué tan fuerte puede ser y hasta cuándo.",
        "enfen_miembros": "Lo forman el IMARPE, el Senamhi, la Marina, el IGP, la ANA y el Indeci, entre otros.",
        "enfen_corto": "el grupo del Estado que vigila el mar",
        "senamhi_titulo": "¿Qué es el Senamhi?",
        "senamhi": "Es el servicio de meteorología del Perú. Publica avisos de lluvia, calor o viento para cada zona."
        " El color del aviso dice qué tan grave es el peligro.",
        "nino_titulo": "¿Qué es El Niño costero?",
        "nino": "Es cuando el mar frente a Perú y Ecuador se calienta más de lo normal. Trae lluvias fuertes a la"
        " costa norte y cambia la pesca.",
        "magnitud_titulo": "¿Qué es la magnitud?",
        "magnitud": "Dice qué tan fuerte puede ser El Niño. El ENFEN usa cuatro niveles: débil, moderada, fuerte y"
        " extraordinaria.",
        "estados_titulo": "¿Qué quieren decir los estados?",
        "estados": "El ENFEN usa tres estados. No activo: no hay El Niño. Vigilancia: puede llegar en los próximos"
        " meses. Alerta: ya empezó o está por empezar.",
    },
    "verificar": {
        "titulo": "Hoy en tu zona",
        "hoy": "Hoy, {fecha}",
        "zona": "Tu zona",
        "tu_zona": "Tu zona: {zona}",
        "estado_titulo": "Estado de El Niño costero",
        "estado_de": "Estado de",
        "nino_costero": "El Niño costero",
        "magnitud_titulo": "Magnitud prevista",
        "lo_dice": "Lo dice el",
        "leer_comunicado": "Leer el comunicado",
        "marca_enfen": "Prevista por el ENFEN",
        "marca_texto": "Tu mensaje",
        "mensaje_titulo": "¿Te llegó un mensaje?",
        "mensaje_ayuda": "Pégalo y lo comparamos con lo último que dijo el ENFEN.",
        "tu_mensaje": "Tu mensaje",
        "elige_zona": "¿En qué zona estás?",
        "elige_zona_ayuda": "La guardamos en este equipo para la próxima vez.",
        "cambiar_zona": "Cambiar zona",
        "magnitud_prevista": "magnitud prevista: {magnitud}",
        "sin_comunicado": "No hay un comunicado del ENFEN para esa fecha.",
        "avisos": "{n} avisos del Senamhi",
        "aviso_uno": "1 aviso del Senamhi",
        "sin_avisos": "Sin avisos del Senamhi",
        "avisos_titulo": "Avisos del Senamhi para tu zona",
        "nivel_aviso": "Nivel {nivel}",
        # Sección 15: el nivel va en la escala de los 4 del Senamhi (verde, amarillo, naranja y rojo)
        "nivel_escala": "{nombre} · {posicion} de 4",
        "nivel_escala_lectores": "Nivel {nombre}: {posicion} de 4 en la escala del Senamhi",
        "nivel_amarillo": "Amarillo",
        "nivel_naranja": "Naranja",
        "nivel_rojo": "Rojo",
        "avisos_del": "Avisos del",
        "para_tu_zona": "para tu zona",
        "aviso_hasta": "hasta el {fin}",
        "cuadro": "Pega aquí el mensaje o titular",
        "cuadro_ayuda": "Puede ser un titular, un mensaje de WhatsApp o una nota completa.",
        "boton": "Comparar con el ENFEN",
        "verificando": "Comparando…",
        "otra_fecha": "¿El mensaje es antiguo?",
        "fecha": "¿Qué día llegó?",
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
        "cercania_medidor": "Qué tanto habla del mismo tema que el ENFEN",
        "baja": "Baja",
        "media": "Media",
        "alta": "Alta",
        "oficial_titulo": "Lo que sí dice el ENFEN",
        "oficial_ayuda": "Es la parte del comunicado más parecida a tu mensaje, copiada tal cual.",
        "que_hacer": "Qué hacer en tu zona",
        "que_te_interesa": "¿Qué te interesa?",
        "recomendacion": "Recomendación oficial",
        "nota_reciente": "Un medio que dice lo mismo que el ENFEN",
        "sin_que_hacer": "No hay consejos del ENFEN para este tema hoy.",
        "compartir": "Compartir",
        "copiado": "Copiamos el texto y el enlace. Pégalos donde quieras.",
        "compartir_texto": "Lo revisé en Radar Niño Costero: {titulo}. Según el Comunicado N.° {numero} del ENFEN"
        " ({fecha}).",
        "compartir_sin_comunicado": "Lo revisé en Radar Niño Costero: {titulo}.",
        "nueva": "Comparar otro mensaje",
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
        "titulo": "Cómo se habló de El Niño en 2026",
        "intro": "Lo que publicaron cuatro medios y YouTube, frente a lo que dijo el ENFEN.",
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
        "sesion": "sesión",
        "sesiones": "sesiones",
        "embudo": "Embudo",
        "segundos": "Segundos promedio por pantalla",
        "limitaciones": "Limitaciones",
        "sin_uso": "Todavía no hay uso registrado.",
    },
}

# Las pantallas del ciudadano: U2 y U6 se miden también sobre sus textos
PANTALLAS_DEL_CIUDADANO = ("comun", "glosario", "verificar", "preguntar")
# Las ayudas que se leen como frase (U3); las etiquetas cortas no tienen sentido para INFLESZ
AYUDAS = (("verificar", "elige_zona_ayuda"), ("verificar", "cuadro_ayuda"), ("verificar", "oficial_ayuda"),
          ("verificar", "sin_que_hacer"), ("verificar", "copiado"), ("preguntar", "entendido_ayuda"),
          ("comun", "sin_conexion"), ("comun", "arrancando"), ("verificar", "mensaje_ayuda"),
          ("glosario", "enfen"), ("glosario", "senamhi"), ("glosario", "nino"), ("glosario", "magnitud"),
          ("glosario", "estados"))  # fmt: skip


def textos_de_la_interfaz():
    return [t for p in PANTALLAS_DEL_CIUDADANO for t in INTERFAZ[p].values()]


def para_la_interfaz():
    """Lo que importa web/: la interfaz y las listas que muestra tal cual."""
    return {**INTERFAZ, "macroregiones": MACROREGIONES, "intereses": INTERESES, "cercania": CERCANIA,
            "estados": ESTADO, "magnitudes": list(MAGNITUDES)}  # fmt: skip


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
