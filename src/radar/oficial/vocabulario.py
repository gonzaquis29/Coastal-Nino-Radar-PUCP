"""Vocabulario oficial del corpus: estados, escalas, niveles y temas. Único lugar donde se definen."""

# ENFEN: estados del sistema de alerta (Nota Técnica ENFEN 02-2026)
NO_ACTIVO = "No Activo"
ESTADOS_ENFEN = (
    NO_ACTIVO,
    "Vigilancia de El Niño Costero",
    "Alerta de El Niño Costero",
    "Vigilancia de La Niña Costera",
    "Alerta de La Niña Costera",
)

# Magnitudes de El Niño, de menor a mayor. Niño 1+2 (ICEN) llega a "extraordinaria"; Niño 3.4 usa "muy fuerte".
ESCALA_MAGNITUD = ("débil", "moderada", "fuerte", "muy fuerte", "extraordinaria")
REGION_COSTERA, REGION_CENTRAL = "nino_1+2", "nino_3.4"

# Senamhi: niveles de aviso; el índice es el número de nivel del mapa (nl) y del polígono ("Nivel N")
NIVELES_AVISO = ("", "VERDE", "AMARILLO", "NARANJA", "ROJO")
NIVEL_MINIMO_AVISO = 2  # el nivel 1 (verde) es zona sin aviso

# Senamhi: tipos de aviso del alcance y estados
PRECIPITACIONES, TEMPERATURA = "precipitaciones", "temperatura"
EMITIDO, VIGENTE, VENCIDO, CANCELADO = "emitido", "vigente", "vencido", "cancelado"

# Categorías de interés del README
PESCA, LLUVIAS, CALOR, PREVENCION = "pesca", "lluvias", "calor", "prevencion"
TEMA_DE_TIPO_AVISO = {PRECIPITACIONES: LLUVIAS, TEMPERATURA: CALOR}


def orden_nivel(nivel):
    return NIVELES_AVISO.index(nivel) if nivel in NIVELES_AVISO else 0


def nivel_por_numero(numero):
    return NIVELES_AVISO[numero] if 0 <= numero < len(NIVELES_AVISO) else ""


def mayor_nivel(niveles):
    return max(niveles, key=orden_nivel, default="")
