# Pendientes, por prioridad (actualizado el 29-oct-2026)

Orden según dependencias reales y fechas, revisado con lo aprendido en los pilotos; el calendario del README es orientativo. Cada tarea se define, se aprueba, se construye y se valida con muestras nuevas, una a la vez. Estado del índice de discrepancia y del flujo de NLP: [nlp/discrepancia.md](nlp/discrepancia.md).

## Siempre (rutina hasta el corte del 20-nov)
- Recolección diaria (`python -m radar.recoleccion.diario --persona <nombre> --publicar`), con máximo 48 h entre ejecuciones. Un solo proceso a la vez pide páginas (`data/red.lock`): si el recálculo está corriendo, cortarlo con Ctrl+C, hacer la rutina y relanzarlo. Luego `python -m radar.noticias.historico` (solo notas nuevas) y `python -m radar.region.notas`.
- Si la recolección avisa "Nuevo documento del ENFEN", `python -m radar.oficial.corpus`. El 28-oct el aviso eran solo ediciones de las páginas web de los N.° 14 a 18; los PDF no cambiaron.
- Próximo comunicado del ENFEN anunciado: jueves 30-oct.

## 1. Recalcular las notas con el texto limpio (antes de la red de enlaces)
`notas.csv` y `enlaces.csv` se calcularon con la extracción anterior a la capa 1: los enlaces incluyen recomendados y los rasgos usan texto pegado. La red de enlaces y citas y la co-mención los necesitan limpios.

**Hecho el 28-oct:** el resumen de El Tiempo se corta donde empieza el enlace a otra nota ([noticias/texto.md](noticias/texto.md)). Antes, 39 notas eran "sobre El Niño" solo por el titular ajeno. Se corrige en el recálculo.

**Hecho el 28-oct (capa 2):** el resumen HTML del ENFEN traía 82 llamadas de nota pegadas a las palabras ("fuerte2"); ya se quitan ([oficial/definicion.md](oficial/definicion.md)). Se encontró además que `corpus --solo enfen` borra de `validacion.csv` las filas del Senamhi; está pendiente corregirlo. Mientras tanto, correr el corpus sin `--solo`.

**Hecho el 28-oct (regla de magnitud):** una sola regla por cercanía para el ENFEN y las notas ([nlp/magnitud.md](nlp/magnitud.md)). Con `comunicados.csv` sin cambios, pasa la 1.ª y la 3.ª muestra; la 2.ª no pasó y se corrigió en la regla y en el instrumento. Quedan sin ver solo 16 notas con magnitud, todas de Andina: la medición previa al recálculo mide "sobre El Niño" con muestra nueva, y el efecto completo en las magnitudes lo da el recálculo, nota por nota.
1. ~~**Unificar la regla de magnitud:**~~ (hecho) `noticias.rasgos.magnitudes` pasa a usar, frase por frase, las reglas de `oficial.enfen`; es la definición de la capa 3. Hay que validar antes cuántas notas cambian sus magnitudes y su "sobre El Niño".
2. ~~**Un modo de recálculo en `noticias.historico`**~~ (hecho el 28-oct, [noticias/recalculo.md](noticias/recalculo.md)) (hoy solo lee notas nuevas): volver a leer las notas ya leídas y reescribir `notas.csv` y `enlaces.csv` de cada medio de forma atómica y reanudable, sin perder lo existente si se corta.
3. **Correrlo:** la fase 1 y la fase 2 corrieron el 29-oct y pasaron los criterios, pero al revisarlas antes de aplicar apareció una fuga de titulares ajenos en el cuerpo (Andina y RPP), que ya se corrigió en la capa 1 ([noticias/recalculo.md](noticias/recalculo.md)). Se relanzó completo esa noche (~10 h). Falta revisar su informe, `--aplicar` (con aprobación) y luego `region.notas`.
4. **Volver a correr `viabilidad resultados`** y actualizar las cifras del README si cambian (volumen, control positivo, calidad).

## 2. Pruebas de viabilidad pendientes (esta semana; son las que deciden el alcance)
| Prueba | Qué falta | Decide |
|--------|-----------|--------|
| **YouTube** (≥ 300 videos del período; comentarios de ~30 videos) | Crear la clave de YouTube Data API v3 en Google Cloud (la crea el usuario) | Si la red social usa YouTube o la co-mención; si hay modelo de engagement. Toma 1-2 días de cupo y no apura antes del corte |
| **Google Trends** por departamento (sobre todo Tumbes) | Exportar el CSV desde la web (pytrends está archivado) | Si el interés de búsqueda entra en la analítica y en el estudio de eventos |
| **pysentimiento** sobre ~20 titulares | Descargar el modelo | Si las emociones usan pysentimiento o un respaldo |
| **Streamlit Cloud** con el modelo de embeddings (y el NLI, si sigue) | Una app mínima desplegada desde GitHub (cuenta del usuario) | Qué modelos caben en la app. Medir antes la memoria en local |

**Decisión que depende de estas pruebas:** el tema "datos minados como insumo de ML" depende hoy del modelo de engagement (YouTube) o del índice con NLI. Si caen los dos, la alternativa es un modelo que prediga el interés de Trends por semana y departamento con el volumen y el tono de las noticias y los comunicados.

## 3. Preprocesamiento y TF-IDF (semana 1-2)
- Una sola lectura por nota que produzca todo lo que se deriva del cuerpo, sin volver a leer en cada etapa. Corpus: las ~2.300 notas sobre El Niño más las del control negativo.
- **Cuidado con el derecho de autor:** se pueden guardar vectores y conteos, no la secuencia de lemas, porque reconstruiría el texto.

## 4. Semana 2
- Red de enlaces y citas (necesita el punto 1).
- Embeddings: elegir el modelo (MiniLM o e5-small) con los controles positivo y negativo.
- Tópicos (LDA y BERTopic) y emociones.
- Red social: YouTube o co-mención, según la prueba.

## 5. Semana 3
- Índice de discrepancia, capas 3 a 5: la capa 3 ya está definida ([nlp/discrepancia.md](nlp/discrepancia.md)), con un solo intento acotado para el NLI.
- Semáforo calibrado.
- Estudio de eventos.
- Modelo de engagement o su alternativa.

## README
Está desactualizado en el índice de discrepancia (NLI, "párrafo más parecido", prueba sintética) y en el insumo de ML. Se actualiza cuando esas decisiones queden firmes; mientras tanto mandan [nlp/discrepancia.md](nlp/discrepancia.md) y este archivo.
