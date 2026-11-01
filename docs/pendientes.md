# Pendientes, por prioridad (actualizado el 1-nov-2026)

Orden según dependencias reales y fechas, revisado con lo aprendido en los pilotos; el calendario del README es orientativo. Cada tarea se define, se aprueba, se construye y se valida con muestras nuevas, una a la vez. Estado del índice de discrepancia y del flujo de NLP: [nlp/discrepancia.md](nlp/discrepancia.md).

## Estado al 1-nov
- **Noticias:** 76.961 notas de los 4 medios (1-ene a hoy), con el texto limpio, y 2.388 notas sobre El Niño. Enlaces limpios: 117.516, de los que 7.616 apuntan a fuentes oficiales. La macro-región está asignada y validada (`region.notas` pasa).
- **Corpus oficial:** ENFEN hasta el comunicado N.° 19 (30-oct) y avisos del Senamhi; 865 párrafos.
- **Viabilidad cerrada:** histórico, filtro, volumen, calidad, control positivo (con el respaldo), macro-región, precisión de "sobre El Niño", pysentimiento (no pasa: solo polaridad en las notas) y memoria para la app (el NLI queda offline; el embedding cabe). Detalle: [nlp/viabilidad-modelos.md](nlp/viabilidad-modelos.md) y [noticias/definicion.md](noticias/definicion.md#diagnóstico-de-falsos-positivos-31-oct-2026).
- **Sin empezar:** `src/radar/nlp/` (TF-IDF, embeddings, tópicos, capa 3), YouTube y Trends, y la app.

## Siempre (rutina hasta el corte del 20-nov)
- Recolección diaria (`python -m radar.recoleccion.diario --persona <nombre> --publicar`), con máximo 48 h entre ejecuciones. La última fue el 1-nov a las 08:41, así que la próxima vence el **3-nov a las 08:41**. Un solo proceso a la vez pide páginas (`data/red.lock`): si un proceso largo está corriendo, cortarlo con Ctrl+C, hacer la rutina y relanzarlo.
- Después: `python -m radar.noticias.historico` (solo notas nuevas) y `python -m radar.region.notas`.
- Si la recolección avisa "Nuevo documento del ENFEN", correr `python -m radar.oficial.corpus` sin `--solo` (ver el punto 7).

## 1. Desbloquear YouTube y Trends (urgente: núcleo que no se recorta)
| Prueba | Qué falta | Decide |
|--------|-----------|--------|
| **YouTube** (≥ 300 videos del período; ≥ 100 videos con ≥ 30 comentarios) | Crear la clave de YouTube Data API v3 en Google Cloud (la crea el usuario y la guarda en una variable de entorno, nunca en el repo ni en el chat) | Si la red social usa YouTube o la co-mención; si hay modelo de engagement. Toma 1-2 días de cupo |
| **Google Trends** por departamento (Tumbes, Piura, Lambayeque, La Libertad) | Exportar el CSV desde la web, una consulta por departamento para todo el período (pytrends está archivado) | Si el interés de búsqueda entra en la analítica y en el estudio de eventos |
| **Emociones de comentarios** (pysentimiento) | Datos de YouTube | Si los comentarios tienen emociones (en los titulares no: [nlp/viabilidad-modelos.md](nlp/viabilidad-modelos.md)) |
| **Streamlit Cloud** con el modelo de embeddings | Una app mínima desplegada desde GitHub (cuenta del usuario). En local caben e5-small cuantizado (0,78 GB) o MiniLM en ONNX float32 (1,31 GB) | Confirmar la memoria en el servidor |

**Decisión que depende de estas pruebas:** el insumo de ML depende del modelo de engagement (YouTube), porque el NLI ya quedó fuera de la app. Si YouTube no alcanza, la alternativa es un modelo que prediga el interés de Trends por semana y departamento a partir del volumen y el tono de las noticias y los comunicados.

## 2. Antes del NLP (calidad del corpus)
1. **Regla de "sobre El Niño"** ([noticias/definicion.md](noticias/definicion.md#regla-de-menciones-del-1-nov-2026)): construida y probada el 1-nov (FEN, "Fenómeno el Niño", "Código", "La Niña" como lugar). Falta el recálculo completo, que va después de la rutina del 3-nov y dura ~10 h de noche. Luego hay que revisar V1 a V3 y M1b a M5, y aplicar con aprobación ([noticias/recalculo.md](noticias/recalculo.md#tercera-pasada-regla-de-menciones-1-nov)).
2. **Crear `src/radar/nlp/`** y pasar ahí las pruebas de viabilidad de modelos (pysentimiento y memoria), con pruebas sintéticas: se corrieron con scripts provisionales, y CLAUDE.md no admite scripts sueltos.

## 3. Semana 2 (2 a 8-nov), en orden de dependencias
1. **Red de enlaces y citas:** los enlaces ya están limpios (`data/processed/noticias/enlaces.csv`).
2. **Preprocesamiento y TF-IDF:** una sola lectura por nota que produzca todo lo que se deriva del cuerpo. Corpus: las ~2.400 notas sobre El Niño más las 400 del control negativo. Se pueden guardar vectores y conteos, no la secuencia de lemas, porque reconstruiría el texto.
3. **Embeddings:** elegir entre MiniLM y e5-small con los controles positivo y negativo (AUC). Los dos caben en la app; MiniLM solo en ONNX float32, porque cuantizado cambia los vectores.
4. **Tópicos (LDA y BERTopic) y polaridad de las notas:** la polaridad se valida con el kappa frente a un zero-shot independiente (README). El cuerpo se parte en tramos de 128 tokens para robertuito.
5. **Capa 3 del índice (afirmaciones):** definida y aprobada ([nlp/discrepancia.md](nlp/discrepancia.md)). Conviene empezarla esta semana porque está en el camino crítico del índice.
6. **Red social:** YouTube o co-mención, según la prueba del punto 1.

## 4. Semana 3 (9 a 15-nov)
- Índice de discrepancia, capas 4 y 5. El NLI tiene un solo intento acotado y queda solo offline. En la app, distancia y regla de magnitud.
- Semáforo calibrado.
- Estudio de eventos.
- Modelo de engagement o su alternativa.
- Recomendador híbrido.

## 5. Menores, sin urgencia
1. **13 notas de RPP con menos de 0,9 del articleBody** (8 del Rotafono, como 1672096 y 1674393). El texto que falta no queda después de la lista de recomendados, así que el rescate no lo cubre. Es un análisis de capa 1 aparte, con muestra nueva.
2. **Bug de `corpus --solo`:** `validacion.csv` se reescribe solo con la fuente que corrió, y `--solo enfen` borra las filas del Senamhi (`src/radar/oficial/corpus.py`, donde arma `validacion.csv`). Se corrige conservando las filas de la otra fuente, como ya se hace con `parrafos.csv`. Mientras tanto, correr el corpus sin `--solo`.

## README
Hay que actualizar:
- el índice de discrepancia: NLI solo offline, sin "párrafo más parecido" ni prueba sintética;
- las emociones de las notas, que pasan a ser solo polaridad;
- el producto: la pestaña Consulta ya no muestra el NLI.

El insumo de ML espera a la prueba de YouTube. Mientras tanto mandan [nlp/discrepancia.md](nlp/discrepancia.md), [nlp/viabilidad-modelos.md](nlp/viabilidad-modelos.md) y este archivo.

## Hecho (resumen; el detalle está en cada documento)
- **Recálculo de las notas con el texto limpio**, aplicado el 31-oct en dos pasadas: la general y la de RPP con el rescate de recomendados sin cerrar ([noticias/recalculo.md](noticias/recalculo.md)).
- **Capa 1 (texto limpio):** titulares ajenos y recomendados sin cerrar de RPP ([noticias/texto.md](noticias/texto.md)).
- **Capa 2 (corpus oficial limpio)** y regla de magnitud única para el ENFEN y las notas ([oficial/definicion.md](oficial/definicion.md), [nlp/magnitud.md](nlp/magnitud.md)).
- **Pruebas de viabilidad de noticias** ([noticias/validacion-2026-10-24.md](noticias/validacion-2026-10-24.md)) y de modelos ([nlp/viabilidad-modelos.md](nlp/viabilidad-modelos.md)).
