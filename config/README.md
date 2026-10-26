# Configuración editable

Listas de referencia que se pueden cambiar sin tocar código. Los valores del proyecto (fechas, user-agent, ritmo, hosts, rutas) están en `src/radar/config.py`.

| Archivo | Qué es | Lo usan |
|---------|--------|---------|
| `regiones.csv` | departamento → macro-región del README (`costa_norte`, `costa_centro`, `lima`, `otras`); `macroregion_avisos` es la macro-región cuyos avisos del Senamhi aplican (Lima y Callao usan los de costa centro); `litoral` marca los 11 departamentos con costa | asignación de región, corpus oficial |
| `lugares.csv` | los 2.111 lugares del INEI (WFS de su IDE, 25-oct-2026) con ubigeo y, por cada nombre, si se usa para asignar región (`usar`) y la medición que lo decidió (`motivo`, `ref_n`, `precision`…). Se genera con `python -m radar.region.lugares`; no se edita a mano | asignación de región (`region/`) |
| `terminos_titulo.csv` | términos del filtro por título (`termino`, `grupo`), cada forma escrita tal cual, sin tildes y en minúsculas; no se quitan plurales para que "niños" no cuente como "niño" | histórico de noticias (`noticias/filtro.py`) |
| `secciones_excluidas.csv` | secciones de RPP y Exitosa que no se descargan salvo que pasen el filtro por título (deportes, espectáculos, publirreportajes…) | histórico de noticias |
| `actores.csv` | actores del ENFEN y de la gestión del riesgo (README, "Actores") con la expresión regular que reconoce sus menciones | rasgos de las notas (`noticias/rasgos.py`) |
| `estaciones_costa.csv` | estaciones del Senamhi (listado de `?p=estaciones`, 24-oct-2026) usadas como puntos de referencia de la costa para los polígonos de los avisos. Elegirlas como "costa" es un supuesto declarado | corpus oficial (`senamhi.py`) |

UTF-8, saltos LF, una fila por elemento.
