# Pendientes, por prioridad (actualizado el 1-nov-2026)

Orden según dependencias reales y fechas, revisado con lo aprendido en los pilotos; el calendario del README es orientativo. Cada tarea se define, se aprueba, se construye y se valida con muestras nuevas, una a la vez. Estado del índice de discrepancia y del flujo de NLP: [nlp/discrepancia.md](nlp/discrepancia.md).

## Estado al 1-nov
- **Noticias:** 76.961 notas de los 4 medios (1-ene a hoy), con el texto limpio, y 2.388 notas sobre El Niño. Enlaces limpios: 117.516, de los que 7.616 apuntan a fuentes oficiales. La macro-región está asignada y validada (`region.notas` pasa).
- **Corpus oficial:** ENFEN hasta el comunicado N.° 19 (30-oct) y avisos del Senamhi; 865 párrafos.
- **Viabilidad cerrada:** histórico, filtro, volumen, calidad, control positivo (con el respaldo), macro-región, precisión de "sobre El Niño", pysentimiento (no pasa: solo polaridad en las notas) y memoria para la app (el NLI queda offline; el embedding cabe). Detalle: [nlp/viabilidad-modelos.md](nlp/viabilidad-modelos.md) y [noticias/definicion.md](noticias/definicion.md#diagnóstico-de-falsos-positivos-31-oct-2026).
- **NLP:** TF-IDF (no pasa T4) y embeddings (pasan con e5-small) hechos el 1-nov. **Sin empezar:** tópicos, capa 3, YouTube y Trends, y la app.

## Siempre (rutina hasta el corte del 20-nov)
- Recolección diaria (`python -m radar.recoleccion.diario --persona <nombre> --publicar`), con máximo 48 h entre ejecuciones. La última fue el 5-nov a las 17:24, así que la próxima vence el **7-nov a las 17:24**. Un solo proceso a la vez pide páginas (`data/red.lock`): si un proceso largo está corriendo, cortarlo con Ctrl+C, hacer la rutina y relanzarlo.
- Después: `python -m radar.noticias.historico` (solo notas nuevas) y `python -m radar.region.notas`. Última rutina con `corpus`: 6-nov, con 77.839 notas. El PDF del comunicado N.° 19 del ENFEN cambió el 1-nov, pero sus datos y párrafos quedan iguales. Su control con `pypdf` baja a 0,974 (umbral 0,98) por ruido de ese extractor: repite el encabezado y separa palabras.
- Si la recolección avisa "Nuevo documento del ENFEN", correr `python -m radar.oficial.corpus` sin `--solo` (ver el punto 6.2).

## 1. Desbloquear YouTube y Trends (urgente: núcleo que no se recorta)
| Prueba | Qué falta | Decide |
|--------|-----------|--------|
| **YouTube** (≥ 300 videos del período; ≥ 100 videos con ≥ 30 comentarios) | Crear la clave de YouTube Data API v3 en Google Cloud (la crea el usuario y la guarda en una variable de entorno, nunca en el repo ni en el chat) | Si la red social usa YouTube o la co-mención; si hay modelo de engagement. Toma 1-2 días de cupo |
| **Google Trends** por departamento (Tumbes, Piura, Lambayeque, La Libertad) | Exportar el CSV desde la web, una consulta por departamento para todo el período (pytrends está archivado) | Si el interés de búsqueda entra en la analítica y en el estudio de eventos |
| **Emociones de comentarios** (pysentimiento) | Datos de YouTube | Si los comentarios tienen emociones (en los titulares no: [nlp/viabilidad-modelos.md](nlp/viabilidad-modelos.md)) |
| **Versión pública (opcional)** en Streamlit Community Cloud | Decisión del 2-nov: la app principal corre en local. La versión pública solo se hace si hay tiempo, con e5-small cuantizado (0,78 GB) y sin NLI | Si hay demo pública |

**Decisión que depende de estas pruebas:** el insumo de ML depende del modelo de engagement (YouTube), porque el NLI ya quedó fuera de la app. Si YouTube no alcanza, la alternativa es un modelo que prediga el interés de Trends por semana y departamento a partir del volumen y el tono de las noticias y los comunicados.

## 2. Recálculo final, uno solo, antes del corte del 20-nov
Decisión del 1-nov: no se corren más recálculos completos (~10 h) después de cada corrección; ya fueron cuatro. Las correcciones se acumulan en el código y se recalcula **una sola vez**, con todo junto, antes del corte. Las notas nuevas de cada día ya se leen con el código vigente.

**Ya en el código, esperando ese recálculo:**
- Regla de menciones del 1-nov (FEN, "Fenómeno el Niño", "Código del Niño", "La Niña" como lugar) y su paso de causa "menciones" ([noticias/recalculo.md](noticias/recalculo.md#tercera-pasada-regla-de-menciones-1-nov)). Cambia menos del 1 % de las notas sobre El Niño.
- Fecha suelta de Andina (`Publicado: dd/mm/aaaa`) quitada del cuerpo el 1-nov, con su generación "fecha" en `recalculo.py`. La capa 1 se validó con dos semillas nuevas ([noticias/texto.md](noticias/texto.md#fecha-suelta-de-andina-1-nov-2026), [noticias/recalculo.md](noticias/recalculo.md#cuarta-corrección-fecha-de-andina-1-nov)). Cambia el sha1 de todas las notas de Andina, pero no sus rasgos.
- Notas de Andina en inglés reconocidas por el texto (1-nov; [noticias/definicion.md](noticias/definicion.md)). Ya no entran al consolidado ni a `region.notas` (quedan 76.646 notas y 2.378 sobre El Niño). En el recálculo, `Andina.leer` las rechaza como "en inglés" y quedan sin releer en `data/raw/`; el consolidado las vuelve a excluir. No hay que hacer nada más.

**Revisar o corregir antes de lanzarlo** (se agrega aquí lo que aparezca, sin recalcular):
- Las 13 notas de RPP con menos de 0,9 del articleBody (punto 6.1): decidir si se corrigen en la capa 1 o se declaran.
- Si alguna corrección nueva cambia el cuerpo o las menciones, agregar su generación y su paso de causa en `recalculo.py`, como "rescate" y "menciones".
- Confirmar que no hay directorios `recalculo/` ya aplicados ni `*.anterior.csv` en ningún medio (si los hay, renombrarlos; ver CLAUDE.md).

**Cómo lanzarlo:**
1. Ensayo corto, de unos 5 minutos: `python -m radar.noticias.historico --recalcular --todo --limite 200`, más `--informe`. Si algo falla, se corrige antes de gastar las 10 horas. Ese ensayo escribe en `recalculo/`; se borra o se renombra antes de la corrida completa.
2. Corrida completa de noche: `python -m radar.noticias.historico --recalcular --todo --horas 12`, después de una rutina diaria.
3. Revisar M1b a M5 y V1 a V3, y aplicar con aprobación: `--recalcular --aplicar`. Después, `region.notas`, `viabilidad resultados`, `redes.enlaces`, `nlp.tfidf vectores` y `nlp.embeddings criterios` (sus T1 y E1 comparan el sha1 con `notas.csv`).

## 3. Antes del NLP
1. ~~**Crear `src/radar/nlp/`** y pasar ahí las pruebas de viabilidad de modelos~~ Hecho el 1-nov: `python -m radar.nlp.viabilidad`, con pruebas sintéticas. D2 y memoria se reprodujeron ([nlp/viabilidad-modelos.md](nlp/viabilidad-modelos.md#cómo-se-corre)).

## 4. Semana 2 (2 a 8-nov), en orden de dependencias
1. ~~**Red de enlaces y citas**~~ Hecha el 1-nov: `python -m radar.redes.enlaces` ([redes/enlaces.md](redes/enlaces.md)). R1 pasa; R2 no pasa para Indeci, Cenepred y PCM, porque Exitosa enlaza palabras genéricas a esos sitios (SEO), no porque falten patrones. Se vuelve a correr después del recálculo final.
2. ~~**Preprocesamiento y TF-IDF**~~ Hecho el 1-nov: `python -m radar.nlp.tfidf` ([nlp/tfidf.md](nlp/tfidf.md)). **No pasa T4:** el AUC frente al control negativo es 0,80 (umbral 0,90). Las notas que hablan poco de El Niño, como las de medidas del Gobierno, no se parecen léxicamente a los párrafos del ENFEN. La lectura del corpus toma 23 min, así que no hace falta atar las etapas a una sola lectura.
3. ~~**Embeddings**~~ Hechos el 1-nov: `python -m radar.nlp.embeddings` ([nlp/embeddings.md](nlp/embeddings.md)). **Pasa con e5-small**, que empata con MiniLM en E4 (0,912 frente a 0,799 del TF-IDF); el semáforo del README se puede calibrar (E3: 0,951 en cuerpos y 0,901 en titulares, sin cruce), y e5 cuantizado da lo mismo. **Para el semáforo (semana 3):** un párrafo de definiciones del ENFEN es el más parecido para el 11,5 % de las notas (hubness), así que hay que decidir si los párrafos de `definicion` entran en la comparación. Se vuelve a correr después del recálculo final.
3b. **Comparación de candidatos de embedding ([nlp/embeddings.md](nlp/embeddings.md)).** A y B cerradas el 5-nov: qwen3 se descarta con la muestra y el modelo elegido es **minilm**. **Sigue:**
   1. E (recall@k), por definir. C y D se cerraron el 6-nov sin cambios: el semáforo sigue solo con minilm. Su E4 en texto corto (0,860) no llega a 0,90, y hay que considerarlo al calibrar el semáforo. El reranker y el híbrido para el agente se miden en E. La rutina atrasada ya corrió el 6-nov.
4. **Tópicos (LDA y BERTopic) y polaridad de las notas:** la polaridad se valida con el kappa frente a un zero-shot independiente (README). El cuerpo se parte en tramos de 128 tokens para robertuito.
5. **Capa 3 del índice (afirmaciones):** definida y aprobada ([nlp/discrepancia.md](nlp/discrepancia.md)). Conviene empezarla esta semana porque está en el camino crítico del índice.
6. **Red social:** YouTube o co-mención, según la prueba del punto 1.

## 5. Semana 3 (9 a 15-nov)
- Índice de discrepancia, capas 4 y 5. El NLI tiene un solo intento acotado. Con la app local (decisión del 2-nov), la memoria ya no lo obliga a quedar offline: si pasa su prueba, puede ir en la app local; en la versión pública, distancia y regla de magnitud.
- Semáforo calibrado.
- Estudio de eventos.
- Modelo de engagement o su alternativa.
- Recomendador híbrido.

## 6. Menores, sin urgencia
1. **13 notas de RPP con menos de 0,9 del articleBody** (8 del Rotafono, como 1672096 y 1674393). El texto que falta no queda después de la lista de recomendados, así que el rescate no lo cubre. Es un análisis de capa 1 aparte, con muestra nueva.
2. **Bug de `corpus --solo`:** `validacion.csv` se reescribe solo con la fuente que corrió, y `--solo enfen` borra las filas del Senamhi (`src/radar/oficial/corpus.py`, donde arma `validacion.csv`). Se corrige conservando las filas de la otra fuente, como ya se hace con `parrafos.csv`. Mientras tanto, correr el corpus sin `--solo`.

## README
Hay que actualizar:
- el índice de discrepancia: NLI en la app local solo si pasa su prueba, sin "párrafo más parecido" ni prueba sintética;
- las emociones de las notas, que pasan a ser solo polaridad;
- el producto: la pestaña Consulta ya no muestra el NLI.

El insumo de ML espera a la prueba de YouTube. Mientras tanto mandan [nlp/discrepancia.md](nlp/discrepancia.md), [nlp/viabilidad-modelos.md](nlp/viabilidad-modelos.md) y este archivo.

## Hecho (resumen; el detalle está en cada documento)
- **Recálculo de las notas con el texto limpio**, aplicado el 31-oct en dos pasadas: la general y la de RPP con el rescate de recomendados sin cerrar ([noticias/recalculo.md](noticias/recalculo.md)).
- **Capa 1 (texto limpio):** titulares ajenos y recomendados sin cerrar de RPP ([noticias/texto.md](noticias/texto.md)).
- **Capa 2 (corpus oficial limpio)** y regla de magnitud única para el ENFEN y las notas ([oficial/definicion.md](oficial/definicion.md), [nlp/magnitud.md](nlp/magnitud.md)).
- **Pruebas de viabilidad de noticias** ([noticias/validacion-2026-10-24.md](noticias/validacion-2026-10-24.md)) y de modelos ([nlp/viabilidad-modelos.md](nlp/viabilidad-modelos.md)).
