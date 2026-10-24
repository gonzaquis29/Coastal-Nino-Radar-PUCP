# Configuración editable

Listas de referencia que se pueden cambiar sin tocar código. Los valores del proyecto (fechas, user-agent, ritmo, hosts, rutas) están en `src/radar/config.py`.

| Archivo | Qué es | Lo usan |
|---------|--------|---------|
| `regiones.csv` | departamento → macro-región del README (`costa_norte`, `costa_centro`, `lima`, `otras`); `macroregion_avisos` es la macro-región cuyos avisos del Senamhi aplican (Lima y Callao usan los de costa centro) | asignación de región, corpus oficial |
| `estaciones_costa.csv` | estaciones del Senamhi (listado de `?p=estaciones`, 24-oct-2026) usadas como puntos de referencia de la costa para los polígonos de los avisos. Elegirlas como "costa" es un supuesto declarado | corpus oficial (`senamhi.py`) |

UTF-8, saltos LF, una fila por elemento.
