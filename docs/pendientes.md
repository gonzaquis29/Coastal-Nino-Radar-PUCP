# Pendientes (actualizado el 24-nov-2026)

Lo hecho, con sus decisiones y resultados, está en [historial.md](historial.md). Cada tarea que cambia lo que ve o mide la app se define, se aprueba, se construye y se valida con muestras nuevas. Alcance: solo el producto (decisión del 19-nov).

## Antes del congelamiento (vie 27-nov)
Nada obligatorio.

## Opcional
- **Versión pública:** la API usa 776 MB (antes 2 GB; sección 16 de [app/definicion.md](app/definicion.md)), sin medir en Linux; faltaría atender más de una consulta con modelos a la vez.

## Después del congelamiento
- **Uso real:** `python -m radar.analitica.web uso`, tras la presentación.
- **YouTube:** los datos crudos vencen a los 30 días; los primeros, el 16-dic (`python -m radar.youtube.borrar`). Después del borrado, el gráfico F queda sin datos.
- **«Alta» en otros temas:** 2,35 % en textos cortos y 5,5 % en notas completas ([app/definicion.md](app/definicion.md), secciones 12 y 13).
- **Código:** dividir las funciones de más de 60 líneas (15 de 1.469).

## Cómo probar los cambios
- `python -m pytest` (30 s). La prueba de BERTopic tarda más de 2 minutos y va aparte: `python -m pytest -m lento`, con el extra `nlp`.
- GitHub corre ruff, pytest y las pruebas de la interfaz en cada subida (`.github/workflows/pruebas.yml`). Las de datos descargados y de spaCy, gensim y BERTopic solo corren en local.
- Las versiones con las que se midió están en `restricciones.txt`.
