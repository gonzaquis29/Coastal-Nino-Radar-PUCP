"""Columnas de los CSV de la asignación de macro-región (definición en docs/region/definicion.md)."""

# data/raw/inei/<capa>.csv: lo que devuelve el WFS del INEI (solo atributos, sin geometría)
CAPAS_INEI = {
    "ig_departamento": ("ccdd", "nombdep"),
    "ig_provincia": ("ccdd", "ccpp", "nombprov"),
    "ig_distrito": ("ccdd", "ccpp", "ccdi", "ubigeo", "nombdist"),
}
# config/lugares.csv: un lugar del INEI por fila, con la decisión medida sobre su nombre
LUGARES = (
    "ubigeo",
    "nivel",
    "nombre",
    "clave",
    "departamento",
    "usar",
    "motivo",
    "ref_n",
    "precision",
    "eltiempo_n",
    "eltiempo_local",
    "mayusculas",
    "minusculas",
)
# data/processed/noticias/regiones.csv: macro-región de cada nota
REGIONES_NOTAS = (
    "medio",
    "id",
    "macroregiones",
    "macroregion_principal",
    "departamentos",
    "lugares",
    "puntajes",
    "fuente_texto",
    "version_lugares",
)
