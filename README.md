# Radar Niño Costero

**¿Qué se dice frente a lo que dice el ENFEN?**

**Autores:** Gonzalo Sebastián Quispe Ordoñez y Joseph Celso Aparicio Bohorquez.

## Qué es
Una herramienta que compara la cobertura periodística del Fenómeno El Niño Costero con los comunicados oficiales del ENFEN vigentes en cada fecha. No decide qué es verdad: **mide cercanía a lo oficial** y la presenta como indicador, sin señalar medios individuales.

**Por qué este tema.** Hay una temporada de lluvias por delante y la información oficial es técnica y está dispersa. Además el corpus oficial es pequeño y ordenado, lo que lo hace factible en el tiempo disponible.

## Preguntas que responde
1. ¿Qué tan alineadas están las noticias con el comunicado vigente en su fecha?
2. ¿Qué fuentes enlazan o citan a ENFEN, Senamhi e Indeci, y cuáles no? (red de enlaces)
3. ¿Qué temas y emociones dominan por región (Piura, Tumbes, Lambayeque, Lima) y mes?
4. ¿Reacciona el discurso público a cada comunicado nuevo? (efecto comunicado)
5. ¿Puede un agente responder solo con texto oficial?

## Producto estrella: semáforo de alineación
En el dashboard se pega un titular y se muestra el párrafo oficial más cercano, la distancia semántica y el estado vigente del ENFEN en esa fecha.

## Pipeline
| # | Etapa | Detalle |
|---|-------|---------|
| 1 | Recolección | Comunicados ENFEN en PDF (2026) y noticias de 3-4 medios (Andina, RPP, Infobae Perú, La República) vía sitemaps/RSS y HTML. De los comunicados: fecha, estado de alerta, magnitud. De las notas: título, cuerpo, fecha, sección e hipervínculos. Respeta `robots.txt` y limita la tasa de peticiones. |
| 2 | Preprocesamiento | Limpieza, tokenización, stopwords, lematización en español (spaCy / NLTK). |
| 3 | Representación | TF-IDF (línea base) contra embeddings multilingües livianos (MiniLM / e5-small) con similitud coseno. |
| 4 | Tópicos | LDA contra BERTopic, por mes y región; sentimiento por tópico. |
| 5 | Sentimiento y emociones | Polaridad y emociones con modelos preentrenados en español (pysentimiento); acuerdo entre métodos con kappa. |
| 6 | Red de enlaces | Grafo noticias → fuentes oficiales con `networkx` (centralidad, PageRank), reportado por tipo de fuente. |
| 7 | Índice de discrepancia | Distancia semántica al comunicado vigente + regla que detecta magnitud distinta de la oficial (p. ej. "fuerte" vs. "moderada"). |
| 8 | Efecto comunicado | Series de tiempo del volumen de noticias y de las emociones alrededor de cada comunicado. |
| 9 | Agente extractivo | Consulta en lenguaje natural; recupera el párrafo oficial más relevante con ChromaDB (`PersistentClient`) y lo muestra textualmente con su fecha, filtrando por fecha vigente. |
| 10 | Dashboard | Streamlit: línea de tiempo del estado oficial vs. volumen de noticias, tópicos por región, emociones por mes, red de enlaces y semáforo. |

**Opcionales (primeros en recortarse):** comentarios de YouTube (solo si la prueba previa lo justifica; sin guardar nombres ni identificadores) y un clasificador del estado oficial a partir del texto de las noticias, con separación entrenamiento/prueba por fecha.

La red de enlaces es análisis de estructura web, no de redes sociales propiamente; así debe decirse en el informe.

## Evaluación sin etiquetado manual
| Componente | Cómo se valida |
|------------|----------------|
| Índice de discrepancia | Control positivo (notas de Andina que reproducen el comunicado → distancia baja) y negativo (otros temas → distancia alta); separación de ambas distribuciones. |
| Extractor de magnitud | Contraste contra los comunicados oficiales. |
| Recuperador / agente | Preguntas generadas desde secciones de los comunicados; recall@k, TF-IDF vs. embeddings. |
| Tópicos | Coherencia c_v y comparación del número de tópicos. |
| Sentimiento | Acuerdo (kappa de Cohen) entre pysentimiento, zero-shot y TF-IDF + regresión logística. |
| Emociones | Revisión cualitativa con ejemplos; sin cifra de exactitud. |

**Limitación declarada:** no hay métrica de exactitud para "detectar alarmismo"; el producto mide cercanía a lo oficial.

## Plan de 4 semanas (~12 h por persona)
| Semana | Persona A (datos) | Persona B (modelos) | Entregable |
|--------|-------------------|---------------------|------------|
| 1 | Scrapers de PDF ENFEN y HTML/sitemaps de 3-4 medios; extraer enlaces | Preprocesamiento y TF-IDF | Dataset limpio con fechas y enlaces |
| 2 | Grafo de enlaces | Embeddings, tópicos, emociones | Notebooks con resultados |
| 3 | Índice de discrepancia, efecto comunicado | Evaluación (recall@k, coherencia) | Métricas validadas |
| 4 | Dashboard | Agente extractivo | Producto, informe y presentación |

Los roles A/B no están asignados y pueden intercambiarse. El informe sigue **CRISP-ML(Q)**.

## Recortes, en orden
1. Clasificador opcional y YouTube.
2. Efecto comunicado simplificado.
3. Agente solo extractivo.
4. Bajar de 4 a 3 medios.

**Núcleo que no se recorta:** scraping, vectores (TF-IDF y embeddings), tópicos, emociones y dashboard.

## Primera noche: pruebas de viabilidad
- [ ] Verificar que las notas de 3-4 medios traigan enlaces a fuentes oficiales en el HTML.
- [ ] Revisar `robots.txt` y términos de uso de esos medios.
- [ ] Contar comentarios de ~30 videos de YouTube sobre El Niño.
- [ ] Descargar los comunicados ENFEN y probar la extracción de fecha, estado y magnitud con reglas.
- [ ] Probar pysentimiento (polaridad y emociones) sobre ~20 titulares.

Con eso se decide qué entra al alcance. Plan B si fallan datos o validez: reseñas de servicios digitales (Google Play, con estrellas como etiqueta externa).

## Datos y fuentes
- Comunicados oficiales: https://enfen.imarpe.gob.pe (ENFEN lo integran IMARPE, Senamhi, IGP y otras instituciones).
- Estado visto al 22-oct-2026: "Alerta de El Niño Costero", comunicados N.° 01-2026 a N.° 14-2026. Confirmar en la fuente antes de citar.
- **No verificado aún:** enlaces oficiales en el HTML de las notas, permisos de crawling, volumen de comentarios de YouTube y calidad de las emociones de pysentimiento en titulares.

## Reglas del proyecto
- **Cero etiquetado manual.** Toda validación usa una referencia externa.
- **Ética de scraping:** `robots.txt`, términos de uso, rate limiting, propósito declarado; sin eludir bloqueos. `requests` + `BeautifulSoup`; Playwright solo si es imprescindible.
- **Privacidad:** seudonimizar; no guardar nombres de usuario ni identificadores personales.
- **IA generativa:** se declara su uso y se conserva un registro de prompts en `docs/prompts.md`. Los modelos preentrenados de NLP (embeddings, emociones) se usan como herramientas de minería de texto.
- **Comunicación de resultados:** el índice de discrepancia no es un "detector de desinformación" y no se señalan medios individuales.

## Estructura del repo
```
data/raw/        comunicados (PDF) y HTML crawleado (no se versiona)
data/processed/  párrafos, enlaces y textos limpios (no se versiona)
notebooks/       exploración y análisis
src/             crawler, grafo, recuperación, sentimiento, tópicos, agente, dashboard
results/         figuras y métricas
docs/            bibliografía, notas y registro de prompts
```
