# Pendientes, por prioridad (actualizado el 31-oct-2026)

Orden según dependencias reales y fechas, revisado con lo aprendido en los pilotos; el calendario del README es orientativo. Cada tarea se define, se aprueba, se construye y se valida con muestras nuevas, una a la vez. Estado del índice de discrepancia y del flujo de NLP: [nlp/discrepancia.md](nlp/discrepancia.md).

## Siempre (rutina hasta el corte del 20-nov)
- Recolección diaria (`python -m radar.recoleccion.diario --persona <nombre> --publicar`), con máximo 48 h entre ejecuciones. Un solo proceso a la vez pide páginas (`data/red.lock`): si el recálculo está corriendo, cortarlo con Ctrl+C, hacer la rutina y relanzarlo. Luego `python -m radar.noticias.historico` (solo notas nuevas) y `python -m radar.region.notas`.
- Si la recolección avisa "Nuevo documento del ENFEN", `python -m radar.oficial.corpus`. El 28-oct el aviso eran solo ediciones de las páginas web de los N.° 14 a 18; los PDF no cambiaron.
- El comunicado N.° 19 del ENFEN (30-oct) ya está en el corpus (31-oct).

## 1. ~~Recalcular las notas con el texto limpio~~ (aplicado el 31-oct, [noticias/recalculo.md](noticias/recalculo.md))
`notas.csv` y `enlaces.csv` se calculaban con la extracción anterior a la capa 1: los enlaces incluyen recomendados y los rasgos usan texto pegado. La red de enlaces y citas y la co-mención los necesitan limpios.

**Hecho el 28-oct:** el resumen de El Tiempo se corta donde empieza el enlace a otra nota ([noticias/texto.md](noticias/texto.md)). Antes, 39 notas eran "sobre El Niño" solo por el titular ajeno. Se corrige en el recálculo.

**Hecho el 28-oct (capa 2):** el resumen HTML del ENFEN traía 82 llamadas de nota pegadas a las palabras ("fuerte2"); ya se quitan ([oficial/definicion.md](oficial/definicion.md)). Se encontró además que `corpus --solo enfen` borra de `validacion.csv` las filas del Senamhi; está pendiente corregirlo. Mientras tanto, correr el corpus sin `--solo`.

**Hecho el 28-oct (regla de magnitud):** una sola regla por cercanía para el ENFEN y las notas ([nlp/magnitud.md](nlp/magnitud.md)). Con `comunicados.csv` sin cambios, pasa la 1.ª y la 3.ª muestra; la 2.ª no pasó y se corrigió en la regla y en el instrumento. Quedan sin ver solo 16 notas con magnitud, todas de Andina: la medición previa al recálculo mide "sobre El Niño" con muestra nueva, y el efecto completo en las magnitudes lo da el recálculo, nota por nota.
1. ~~**Unificar la regla de magnitud:**~~ (hecho) `noticias.rasgos.magnitudes` pasa a usar, frase por frase, las reglas de `oficial.enfen`; es la definición de la capa 3. Hay que validar antes cuántas notas cambian sus magnitudes y su "sobre El Niño".
2. ~~**Un modo de recálculo en `noticias.historico`**~~ (hecho el 28-oct, [noticias/recalculo.md](noticias/recalculo.md)) (hoy solo lee notas nuevas): volver a leer las notas ya leídas y reescribir `notas.csv` y `enlaces.csv` de cada medio de forma atómica y reanudable, sin perder lo existente si se corta.
3. ~~**Correrlo:**~~ (hecho) la primera corrida destapó la fuga de titulares ajenos, que se corrigió en la capa 1. La segunda pasó M1b a M5, se revisó caso por caso y se aplicó el 31-oct. Después corrieron `region.notas` (pasa) y el histórico de las notas nuevas.
4. ~~**Volver a correr `viabilidad resultados`**~~ (hecho): 2.230 notas sobre El Niño (antes 2.236); el control positivo no cambia.
5. ~~**Capa 1, bloque "Te recomendamos" sin cerrar en RPP**~~ (hecho y validado el 31-oct, [noticias/texto.md](noticias/texto.md#recomendados-sin-cerrar-en-rpp-31-oct-2026)), junto con el instrumento de `cuerpo_vs_ld` (ítems de lista pegados en el `articleBody`). No cambia "sobre El Niño", las magnitudes ni los comunicados.
6. ~~**Volver a recalcular RPP** con la regla nueva~~. Hecho y aplicado el 31-oct: solo cambian cuerpos y enlaces (recuadros, caja del Rotafono, barra lateral y 10 rescates), ninguna nota cambia magnitudes ni "sobre El Niño" ([noticias/recalculo.md](noticias/recalculo.md#resultado-y-aplicación-31-oct)).
7. **13 notas de RPP con menos de 0,9 del articleBody** (8 del Rotafono, como 1672096 y 1674393). El texto que falta no queda después de la lista de recomendados, así que el rescate no lo cubre. Es un análisis de capa 1 aparte: diagnosticar caso por caso con muestra nueva antes de proponer una regla.
8. **Regla de "sobre El Niño"** ([noticias/definicion.md](noticias/definicion.md#diagnóstico-de-falsos-positivos-31-oct-2026)): la precisión pasa (5/100 falsos positivos en el grupo de riesgo), pero hay fallas de regla: "La Niña" como nombre propio, "Código del Niño", "Fenómeno el Niño" con minúscula y "FEN". Para corregirlas hay que medir antes cuántas notas cambian.
9. **Pasar a `src/radar/nlp/` las pruebas de viabilidad de modelos** (pysentimiento y memoria), con pruebas sintéticas: se corrieron con scripts provisionales.

## 2. Pruebas de viabilidad pendientes (esta semana; son las que deciden el alcance)
| Prueba | Qué falta | Decide |
|--------|-----------|--------|
| **YouTube** (≥ 300 videos del período; comentarios de ~30 videos) | Crear la clave de YouTube Data API v3 en Google Cloud (la crea el usuario) | Si la red social usa YouTube o la co-mención; si hay modelo de engagement. Toma 1-2 días de cupo y no apura antes del corte |
| **Google Trends** por departamento (sobre todo Tumbes) | Exportar el CSV desde la web (pytrends está archivado) | Si el interés de búsqueda entra en la analítica y en el estudio de eventos |
| ~~**pysentimiento**~~ (31-oct: no pasa; en las notas, solo polaridad) | Las emociones de los comentarios de YouTube, cuando haya datos | Si los comentarios tienen emociones |
| **Streamlit Cloud** con el modelo de embeddings | Una app mínima desplegada desde GitHub (cuenta del usuario). La memoria en local ya se midió (31-oct): el NLI queda offline, y caben e5-small cuantizado o MiniLM en ONNX float32 | Confirmar en el servidor |

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
