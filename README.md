# Radar Niño Costero

**¿Qué se dice frente a lo que dice el ENFEN?**

**Autores:** Gonzalo Sebastián Quispe Ordoñez y Joseph Celso Aparicio Bohorquez.

## Qué es
Una herramienta que compara lo que circula sobre el Fenómeno El Niño Costero (noticias y videos de YouTube) con la información oficial vigente en cada fecha: comunicados del ENFEN (nivel nacional) y avisos del Senamhi (nivel departamental). No decide qué es verdad: **mide cercanía a lo oficial**, la presenta como indicador y **recomienda la fuente oficial** que corresponde, sin señalar medios ni canales individuales.

**Por qué este tema.** Hay una temporada de lluvias por delante y la información oficial es técnica y está dispersa. El corpus oficial es pequeño y ordenado (~20 comunicados en 2026), lo que lo hace factible. Una muestra inicial indica que los medios tradicionales tienden a reproducir al ENFEN, mientras que en YouTube circulan títulos claramente exagerados: el contraste interesante está entre ambos.

## Preguntas que responde
1. ¿Qué tan alineadas están las noticias y los videos con la información oficial vigente en su fecha y región?
2. ¿Qué fuentes enlazan o citan a ENFEN, Senamhi e Indeci, y cuáles no? (red de enlaces y citas)
3. ¿Qué temas y emociones dominan por región (Piura, Tumbes, Lambayeque, Lima) y mes?
4. ¿Reacciona el discurso público a cada comunicado nuevo? (efecto comunicado)
5. ¿El contenido más alejado de lo oficial tiene más engagement? ¿Cómo varía el interés del público por departamento? (analítica web)
6. ¿Las audiencias de los canales más alejados de lo oficial se cruzan con las de los medios? (red social)
7. Dado un contenido dudoso, ¿qué fuente oficial y qué notas alineadas le corresponden a una persona según su región? (recomendación)
8. ¿Puede un agente responder solo con texto oficial?

## Producto estrella: semáforo de alineación
En el dashboard se pega un titular o un enlace de video y se muestra el párrafo oficial más cercano, la distancia semántica, el estado vigente del ENFEN y el aviso del Senamhi en esa fecha, junto con las fuentes oficiales y notas alineadas recomendadas para la región elegida.

## Pipeline
| # | Etapa | Detalle |
|---|-------|---------|
| 1 | Recolección | **Oficial:** comunicados ENFEN 2026 (página HTML y PDF de cada uno) y avisos meteorológicos del Senamhi (nivel y departamento). **Noticias:** 3-4 medios (Andina, RPP, Infobae Perú, La República) vía sitemaps/RSS y HTML: título, cuerpo, `datePublished`, sección e hipervínculos. **YouTube (API oficial):** título, descripción, canal, fecha, métricas (vistas, likes, n.° de comentarios) y comentarios seudonimizados. **Google Trends:** interés por departamento y semana, exportado manualmente en CSV. Respeta `robots.txt` y limita la tasa de peticiones. |
| 2 | Preprocesamiento | Limpieza, tokenización, stopwords, lematización en español (spaCy / NLTK). |
| 3 | Representación | TF-IDF (línea base) contra embeddings multilingües livianos (MiniLM / e5-small) con similitud coseno. |
| 4 | Tópicos | LDA contra BERTopic, por mes y región; sentimiento por tópico. |
| 5 | Sentimiento y emociones | Polaridad y emociones con modelos preentrenados en español (pysentimiento); acuerdo entre métodos con kappa. |
| 6 | Red de enlaces y citas | Grafo noticias → fuentes oficiales con `networkx` (centralidad, PageRank). Combina hipervínculos y **menciones en texto** ("según el ENFEN"), porque no todos los medios enlazan. Es análisis de estructura web. |
| 7 | Red social (YouTube) | Red canal–canal por comentaristas compartidos (proyección de la red bipartita usuario–video, usuarios seudonimizados): centralidad y comunidades, reportadas por tipo de canal (medio, institución, creador independiente). **Respaldo** si no hay volumen de comentarios: red de co-mención de actores en noticias (lista fija de instituciones + NER solo para personas). |
| 8 | Índice de discrepancia | Distancia semántica al comunicado o aviso vigente + regla que detecta magnitud distinta de la oficial (p. ej. "fuerte" vs. "moderada"). Se aplica a notas y a título/descripción de videos. |
| 9 | Efecto comunicado | Series de tiempo del volumen de noticias y videos y de las emociones alrededor de cada comunicado. |
| 10 | Analítica web | KPIs de engagement en YouTube (vistas, likes, comentarios, tasa de engagement) frente al índice de discrepancia; interés de búsqueda por departamento (Trends) alrededor de cada comunicado; registro propio de eventos del dashboard (web usage mining); indicadores secundarios de los medios (volumen, sección, tiempo de reacción tras un comunicado). |
| 11 | Recomendador híbrido | **Basado en conocimiento:** reglas con región, aviso vigente del Senamhi y estado del ENFEN filtran qué información corresponde. **Basado en contenido:** similitud de embeddings ordena comunicados, avisos y notas alineadas. Entrada: un contenido (nota o video) y un perfil (región, interés). |
| 12 | Agente extractivo | Consulta en lenguaje natural; recupera el párrafo oficial más relevante con ChromaDB (`PersistentClient`) y lo muestra textualmente con su fecha, filtrando por fecha vigente. |
| 13 | Dashboard | Streamlit: línea de tiempo del estado oficial vs. volumen de noticias y videos, tópicos por región, emociones por mes, redes, KPIs de engagement e interés, semáforo y recomendaciones. |

**Opcionales (primeros en recortarse):** transcripciones de YouTube (la API oficial no las entrega para videos ajenos) y un clasificador del estado oficial a partir del texto, con separación entrenamiento/prueba por fecha.

## Evaluación sin etiquetado manual
| Componente | Cómo se valida |
|------------|----------------|
| Índice de discrepancia | Control positivo (notas de Andina que enlazan al PDF del comunicado → distancia baja) y negativo (otros temas → distancia alta); separación de ambas distribuciones. |
| Extractor de magnitud | Contraste contra los comunicados oficiales. |
| Recuperador / agente | Preguntas generadas desde secciones de los comunicados; recall@k, TF-IDF vs. embeddings. |
| Recomendador | Evaluación offline: la "respuesta correcta" es el comunicado/aviso vigente en la fecha y región del contenido; precision@k, cobertura y diversidad. Notas que enlazan a un comunicado como control positivo. |
| Tópicos | Coherencia c_v y comparación del número de tópicos. |
| Sentimiento | Acuerdo (kappa de Cohen) entre pysentimiento, zero-shot y TF-IDF + regresión logística. |
| Emociones | Revisión cualitativa con ejemplos; sin cifra de exactitud. |
| Red social | Modularidad de las comunidades y comparación contra una red aleatoria con los mismos grados. |
| Analítica web | Correlación (Spearman) entre discrepancia y engagement; descriptivo, sin causalidad. |

**Limitaciones declaradas:** no hay métrica de exactitud para "detectar alarmismo"; el producto mide cercanía a lo oficial. El recomendador se evalúa solo offline (sin usuarios reales). Google Trends da interés relativo (0-100) y puede no tener datos en departamentos pequeños.

## Plan de 4 semanas
Las horas son una estimación orientativa, no un límite; el alcance agregado (YouTube, recomendador, analítica web, red social) puede tomar más tiempo.

| Semana | Persona A (datos) | Persona B (modelos) | Entregable |
|--------|-------------------|---------------------|------------|
| 1 | Scrapers de ENFEN, Senamhi y 3-4 medios; extraer enlaces y citas; recolector de YouTube por API | Preprocesamiento y TF-IDF | Dataset limpio con fechas, enlaces y videos |
| 2 | Red de enlaces y citas; red social de YouTube; exportar Trends | Embeddings, tópicos, emociones | Notebooks con resultados |
| 3 | Índice de discrepancia, efecto comunicado, KPIs de analítica web | Recomendador híbrido; evaluación (recall@k, precision@k, coherencia) | Métricas validadas |
| 4 | Dashboard con registro de eventos | Agente extractivo | Producto, informe y presentación |

Los roles A/B no están asignados y pueden intercambiarse. El informe sigue **CRISP-ML(Q)**.

## Recortes, en orden
1. Clasificador opcional y transcripciones de YouTube.
2. Efecto comunicado simplificado.
3. Indicadores secundarios de los medios.
4. Agente solo extractivo.
5. Bajar de 4 a 3 medios.

**Núcleo que no se recorta:** scraping (incluido YouTube), vectores (TF-IDF y embeddings), tópicos, emociones, recomendador, analítica web, red social (o su respaldo de co-mención) y dashboard.

## Primera noche: pruebas de viabilidad
- [x] Verificar que las notas traigan enlaces a fuentes oficiales en el HTML. *Andina enlaza al PDF del comunicado; Infobae solo cita en texto → se agregan menciones en texto.*
- [x] Revisar `robots.txt` de esos medios. *Ver "Reglas por sitio".*
- [x] Verificar fechas de publicación. *Las notas traen `datePublished` separado de `dateModified`.*
- [ ] Contar comentarios de ~30 videos de YouTube sobre El Niño **con la API oficial**. Decide si la red social usa YouTube o el respaldo de co-mención.
- [ ] Revisar en Google Trends si hay datos por departamento (en especial Tumbes) para "El Niño".
- [ ] Revisar términos de uso de los medios.
- [ ] Descargar los comunicados ENFEN y probar la extracción de fecha, estado y magnitud con reglas.
- [ ] Extraer avisos del Senamhi (fecha, nivel, departamentos).
- [ ] Probar pysentimiento (polaridad y emociones) sobre ~20 titulares.

Con eso se decide qué entra al alcance. Plan B si fallan datos o validez: reseñas de servicios digitales (Google Play, con estrellas como etiqueta externa).

## Datos y fuentes
- Comunicados oficiales: https://enfen.imarpe.gob.pe/comunicados/ (ENFEN lo integran IMARPE, Senamhi, IGP y otras instituciones).
- Avisos meteorológicos por departamento: https://www.senamhi.gob.pe/?p=aviso-meteorologico
- Estado visto al 22-oct-2026: "Alerta de El Niño Costero", comunicados hasta N.° 18-2026. Confirmar en la fuente antes de citar.
- YouTube Data API v3: cuota por defecto de 10 000 unidades/día; leer comentarios cuesta 1 unidad por petición y buscar videos 100.
- Google Trends: `pytrends` está archivado y el API oficial está en alfa cerrado; se usa la exportación CSV de la web.
- **No verificado aún:** volumen de comentarios de YouTube, datos de Trends por departamento, términos de uso de los medios y calidad de las emociones de pysentimiento en titulares.

## Reglas por sitio (revisado el 22-oct-2026)
| Sitio | Regla |
|-------|-------|
| Andina | Sin `robots.txt`; usar sitemap. |
| RPP | Bloquea por completo a Scrapy y bots de IA; usar `requests` con un user-agent honesto, nunca suplantando otro. |
| La República | Prohíbe `/archivo/`; recolectar solo desde sitemaps/RSS. |
| Infobae Perú | Usar el sitemap de noticias de la categoría Perú. |
| Expreso | Responde 403: **excluido**. |
| YouTube | Solo la API oficial; `robots.txt` prohíbe `/results`. Borrar o refrescar datos crudos a los 30 días (políticas de la API); guardar agregados y seudónimos. |

## Reglas del proyecto
- **Cero etiquetado manual.** Toda validación usa una referencia externa.
- **Ética de scraping:** `robots.txt`, términos de uso, rate limiting, propósito declarado; sin eludir bloqueos. `requests` + `BeautifulSoup`; Playwright solo si es imprescindible.
- **Privacidad:** seudonimizar; no guardar nombres de usuario ni identificadores personales.
- **IA generativa:** se declara su uso y se conserva un registro de prompts en `docs/prompts.md`. Los modelos preentrenados de NLP (embeddings, emociones) se usan como herramientas de minería de texto.
- **Comunicación de resultados:** el índice de discrepancia no es un "detector de desinformación" y no se señalan medios ni canales individuales; se reporta por tipo de fuente.

## Decisiones abiertas
Las opciones para recomendación, analítica web y red social son la mejor alternativa evaluada al 22-oct-2026 y pueden cambiar según las pruebas de viabilidad o la opinión del profesor.

## Estructura del repo
```
data/raw/        comunicados (PDF/HTML), avisos, HTML crawleado, respuestas de la API (no se versiona)
data/processed/  párrafos, enlaces, citas, textos limpios y agregados (no se versiona)
notebooks/       exploración y análisis
src/             crawler, recolector YouTube, redes, recuperación, sentimiento, tópicos, recomendador, agente, dashboard
results/         figuras y métricas
docs/            bibliografía, notas y registro de prompts
```
