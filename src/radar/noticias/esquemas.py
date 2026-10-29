"""Columnas de cada CSV de noticias (definición en docs/noticias/definicion.md, "Salida")."""

from radar.oficial.esquemas import VALIDACION

# data/raw/noticias/<medio>/lista.csv: lo descubierto, con o sin nota detrás (http dice qué respondió)
LISTA = ("medio", "id", "url", "titulo", "seccion", "fecha_lista", "via", "http")
# data/raw/noticias/<medio>/notas.csv (de trabajo) y data/processed/noticias/notas.csv (consolidado)
NOTAS = (
    "medio",
    "id",
    "url",
    "via",
    "candidata_por",
    "muestra",
    "titular",
    "resumen",
    "fecha_publicacion",
    "fecha_modificacion",
    "fecha_creacion",
    "fuente_fecha",
    "fecha_dudosa",
    "seccion",
    "etiquetas",
    "terminos_titulo",
    "n_palabras",
    "sin_texto",
    "resumen_en_cuerpo",
    "cuerpo_vs_ld",
    "menciones_nino",
    "menciona_nino",
    "nino_en_inicio",
    "sobre_nino",
    "terminos_cuerpo",
    "actores",
    "comunicados",
    "magnitudes",
    "n_enlaces",
    "n_enlaces_oficiales",
    "sha1_cuerpo",
    "recolectado",
)
ENLACES = ("medio", "id", "url", "dominio", "oficial", "comunicado")
# data/raw/noticias/<medio>/recalculo/cambios.csv: antes y después de cada nota recalculada, sin texto
# (docs/noticias/recalculo.md)
CAMBIOS = (
    "medio",
    "id",
    "fase",
    "generacion",
    "estado",
    "motivo",
    "sobre_antes",
    "sobre_ahora",
    "sobre_texto_nuevo",
    "menciona_antes",
    "menciona_ahora",
    "magnitudes_antes",
    "magnitudes_ahora",
    "magnitudes_texto_nuevo",
    "comunicados_antes",
    "comunicados_ahora",
    "n_enlaces_antes",
    "n_enlaces_ahora",
    "resumen_cambia",
    "pagina_editada",
    "causa_sobre",
    "causa_magnitudes",
    "recalculado",
)
CONTROL_NEGATIVO = ("medio", "id", "url", "mes", "estrato")
ARCHIVOS = {
    "notas.csv": NOTAS,
    "enlaces.csv": ENLACES,
    "control_negativo.csv": CONTROL_NEGATIVO,
    "validacion.csv": VALIDACION,
}
