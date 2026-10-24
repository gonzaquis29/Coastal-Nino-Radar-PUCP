# Radar Niño Costero

**¿Qué se dice frente a lo que dice el ENFEN?**

**Autores:** Gonzalo Sebastián Quispe Ordoñez y Joseph Celso Aparicio Bohorquez.

## Qué es
Una herramienta que compara lo que circula sobre el Fenómeno El Niño Costero (noticias y videos de YouTube) con la información oficial vigente en cada fecha: comunicados del ENFEN y avisos del Senamhi, ambos expresados por macro-región (costa norte, costa centro, etc.). No decide qué es verdad: **mide cercanía a lo oficial**, la presenta como indicador y **recomienda la fuente oficial** que corresponde, sin señalar medios ni canales individuales.

**Por qué este tema.** Hay una temporada de lluvias por delante y la información oficial es técnica y está dispersa. El corpus oficial es pequeño y ordenado (~20 comunicados en 2026), lo que lo hace factible. Una muestra inicial indica que los medios tradicionales tienden a reproducir al ENFEN, mientras que en YouTube circulan títulos claramente exagerados: el contraste interesante está entre ambos.

## Preguntas que responde
1. ¿Qué tan alineadas están las noticias y los videos con la información oficial vigente en su fecha y macro-región?
2. ¿Qué fuentes enlazan o citan a ENFEN, Senamhi e Indeci, y cuáles no? (red de enlaces y citas)
3. ¿Qué temas y emociones dominan por macro-región (costa norte, costa centro, Lima) y mes?
4. ¿Reacciona el discurso público a cada comunicado nuevo? (efecto comunicado)
5. ¿El contenido más alejado de lo oficial tiene más engagement? ¿Cómo varía el interés del público por departamento? (analítica web)
6. ¿Las audiencias de los canales más alejados de lo oficial se cruzan con las de los medios? (red social)
7. Dado un contenido dudoso, ¿qué fuente oficial y qué notas alineadas le corresponden a una persona según su macro-región e interés? (recomendación)
8. ¿Puede un agente responder solo con texto oficial?

## Producto
**Usuario principal:** el ciudadano de la costa que quiere entender las alertas. **Usuario secundario:** el analista o periodista que quiere ver el panorama. El dashboard tiene dos pestañas:

- **Consulta (ciudadano):** se pega un titular o el título y descripción de un video (o se elige un video ya recolectado) y se elige macro-región e interés. Muestra el **semáforo de alineación** (producto estrella): el párrafo oficial más cercano, la distancia semántica, si el texto contradice a ese párrafo (NLI), el estado vigente del ENFEN y el aviso del Senamhi en esa fecha, más las fuentes oficiales y notas alineadas recomendadas. Incluye el agente.
- **Panorama (analista):** tópicos, emociones, redes, KPIs de engagement e interés, y estudio de eventos.

**Umbrales del semáforo**, calibrados con los controles de evaluación y **por separado para títulos cortos y cuerpos de nota** (sus distancias no son comparables):
- 🟢 Verde: distancia por debajo del percentil 75 del control positivo.
- 🔴 Rojo: distancia por encima del percentil 25 del control negativo, magnitud distinta de la oficial según la regla de magnitud, o contradicción con el párrafo oficial según el modelo NLI.
- 🟡 Amarillo: el resto.
- Si la separación entre controles es pobre (AUC < 0,8), se muestra solo la distancia, sin colores.

**Categorías de interés**, tomadas solo de temas presentes en los textos oficiales (los comunicados no tratan agricultura ni salud): Pesca y mar · Lluvias, ríos y huaicos · Calor · Prevención y emergencias. Los tópicos de las noticias se usan para confirmar que también aparecen en lo que circula.

**Validación con usuarios:** solo offline más el uso registrado durante la presentación; se declara como limitación.

## Cobertura del sílabo
| Tema del sílabo | Semana | Componente del proyecto |
|-----------------|--------|-------------------------|
| Internet y protocolos de intercambio | 1 | Sección de protocolos web del informe (HTTP, `robots.txt`, sitemaps, API REST) |
| Lenguajes de etiquetas; web scraping y crawling | 2-3 | Recolección de medios (HTML, sitemaps XML, RSS, JSON-LD) y del ENFEN y Senamhi |
| Redes sociales | 3 | Red social de audiencias de YouTube (respaldo: co-mención de actores) |
| Procesamiento de lenguaje natural y preprocesamiento | 4 | Limpieza, lematización y asignación de región |
| Representación vectorial | 6 | TF-IDF y embeddings |
| Búsqueda y recuperación | — | Recuperador del agente (ChromaDB, recall@k) |
| Sentimiento y minería de opinión | 7 | Polaridad y emociones de notas, videos y comentarios |
| Modelamiento de tópicos | 8 | LDA y BERTopic |
| Web analytics: conceptos, etapas, métricas | 10-11 | KPIs de engagement, interés en Trends, indicadores de los medios, registro de uso de la app |
| Herramientas y dashboards | 12 | Dashboard en Streamlit |
| CRISP-ML(Q) | 13 | Estructura del informe |
| Datos minados como insumo de ML | 14 | Modelo de engagement; índice de discrepancia con NLI |
| Sistemas de recomendación | — | Recomendador híbrido |
| Arquitecturas basadas en agentes | 15 | Agente con herramientas |
| Dinámica de los procesos web | — | Estudio de eventos |
| Estructura web | — | Red de enlaces y citas |

## Pipeline
| # | Etapa | Detalle |
|---|-------|---------|
| 1 | Recolección | **Oficial:** comunicados ENFEN 2026 (página HTML y PDF de cada uno) y avisos meteorológicos del Senamhi (tipo, nivel, macro-región, vigencia), filtrados según "Alcance de datos". **Noticias:** 4 medios (ver "Alcance de datos") vía sitemaps/RSS y HTML. El cuerpo se procesa en memoria y no se guarda: solo se conservan titular, resumen, `datePublished`, sección, hipervínculos, citas a fuentes oficiales, magnitudes, resultados de NLI y vectores. Se recolecta además una muestra de notas de otros temas de los mismos medios, solo para el control negativo. **YouTube (API oficial):** título, descripción (incluidos sus enlaces), canal, fecha, métricas (vistas, likes, n.° de comentarios) y comentarios seudonimizados. **Google Trends:** interés semanal por departamento, exportado manualmente en CSV en una sola consulta por departamento para que las semanas sean comparables. Respeta `robots.txt` y limita la tasa de peticiones. |
| 2 | Preprocesamiento | Limpieza, tokenización, stopwords, lematización en español (spaCy / NLTK). Asignación de macro-región (ver "Alcance de datos"). |
| 3 | Representación | TF-IDF (línea base) contra embeddings multilingües livianos (MiniLM / e5-small) con similitud coseno. |
| 4 | Tópicos | LDA contra BERTopic, ajustados sobre todo el corpus y luego agregados por mes y macro-región (ajustar por cada grupo dejaría grupos casi vacíos); sentimiento por tópico. Los tópicos se nombran con sus palabras clave (c-TF-IDF), sin LLM. |
| 5 | Sentimiento y emociones | Polaridad y emociones con modelos preentrenados en español (pysentimiento); acuerdo con un clasificador zero-shot independiente medido con kappa. |
| 6 | Red de enlaces y citas | Grafo de fuentes (notas y videos) → fuentes oficiales con `networkx` (centralidad, PageRank). Combina hipervínculos de las notas, **menciones en texto** ("según el ENFEN", porque no todos los medios enlazan) y enlaces a sitios oficiales en las descripciones de los videos (agranda la red y conecta ambas verticales). Es análisis de estructura web. |
| 7 | Red social (YouTube) | Red canal–canal por comentaristas compartidos (proyección de la red bipartita usuario–video, usuarios seudonimizados): centralidad y comunidades, reportadas por tipo de canal (oficial, medio, otros; ver "Tipo de canal"). **Respaldo** si no hay volumen de comentarios: red de co-mención de actores en noticias (lista de actores en "Alcance de datos"). |
| 8 | Índice de discrepancia | Tres señales frente al **párrafo** oficial más cercano del comunicado o aviso vigente: (a) distancia semántica, que mide si hablan de lo mismo; (b) **NLI** multilingüe (`mDeBERTa-v3-base-xnli-multilingual-nli-2mil7`), que mide si el texto contradice al párrafo, frase por frase; (c) regla de magnitud distinta de la oficial (p. ej. "extraordinaria" cuando el ENFEN dice "fuerte"). La similitud sola no basta: un texto exagerado sobre El Niño es temáticamente muy parecido al comunicado. Se aplica a notas y a título/descripción de videos. |
| 9 | Efecto comunicado | Estudio de eventos: cada comunicado del ENFEN es un evento; ventana corta de −3 a +7 días comparada contra días sin evento en volumen de notas y videos, emociones y engagement; Trends se compara por semana (semana del comunicado frente a las anteriores), porque sus datos son semanales. Ventanas cortas porque hay un comunicado cada ~2-4 semanas. Los avisos del Senamhi **no** son eventos (más de 400 en 2026): sirven como contexto regional. |
| 10 | Analítica web | KPIs de engagement en YouTube (vistas, likes, comentarios, tasa de engagement) frente al índice de discrepancia; interés de búsqueda por departamento (Trends) alrededor de cada comunicado; registro propio de eventos del dashboard (web usage mining); indicadores secundarios de los medios (volumen, sección, tiempo de reacción tras un comunicado). |
| 11 | Modelo de engagement | Modelo propio entrenado con los datos minados: predice la tasa de engagement de un video ((likes + comentarios) / vistas) a partir del índice de discrepancia, emociones, tópicos y rasgos del título (mayúsculas, exclamaciones, emojis), con los suscriptores del canal y los días desde la publicación como controles (las métricas se descargan en una sola fecha, así que los videos antiguos acumularon más tiempo). Regresión lineal y gradient boosting contra una línea base; importancia de variables. Muestra con varios términos de búsqueda, orden por fecha y tramos de tiempo para reducir el sesgo del ranking de YouTube; likes ocultos como dato faltante. |
| 12 | Recomendador híbrido | **Basado en conocimiento:** reglas con macro-región, aviso vigente del Senamhi y estado del ENFEN filtran qué información corresponde. **Basado en contenido:** similitud de embeddings ordena comunicados, avisos y notas alineadas. Entrada: un contenido (nota o video) y un perfil (macro-región, categoría de interés). |
| 13 | Agente con herramientas | Decide qué herramienta usar según la consulta: `buscar_oficial` (párrafos de comunicados y avisos con ChromaDB `PersistentClient`, filtrando por fecha vigente), `estado_vigente(fecha, región)`, `medir_discrepancia(texto)` y `recomendar(perfil)`. Un LLM por API solo elige la herramienta y extrae parámetros (uso declarado); la respuesta se arma con plantillas y citas textuales, y un control verifica que cada cita exista literalmente en la fuente. Respaldo sin LLM: enrutador por similitud de embeddings entre la consulta y la descripción de cada herramienta; entra automáticamente si falla la API del LLM o se alcanza el límite diario de consultas. |
| 14 | Dashboard | Streamlit con las pestañas Consulta y Panorama (ver "Producto" y "Despliegue"). |

**Opcional (primero en recortarse):** transcripciones de YouTube (la API oficial no las entrega para videos ajenos).

**Descartado:** clasificador del estado oficial a partir del texto. Su etiqueta sale de la fecha, así que aprendería la época y no el contenido, y con partición temporal faltarían clases en la prueba.

## Alcance de datos
**Período.** Análisis principal del 1-ene-2026 (comunicado N.° 01) al **20-nov-2026** (corte), para incluir el inicio de la intensificación esperada para fines de año. El modelo de engagement entrena con enero–agosto y prueba con septiembre–20 de noviembre. Del corte a la presentación se recolecta para el monitoreo (fase 6 de CRISP-ML(Q)). Los recolectores son incrementales: la descarga del corte refresca también los datos de YouTube dentro del plazo de 30 días.

**Medios.**
- **Andina** (agencia estatal): control positivo; se reporta aparte de los medios privados.
- **RPP, La República:** medios privados nacionales.
- **El Tiempo (Piura):** medio regional de la costa norte, la zona más afectada; los otros tres son de Lima.
- **Infobae Perú: excluido.** Sus términos prohíben expresamente "copiar … usar, tratar" sus contenidos (cláusula 3.4).

Todos los términos de uso prohíben reproducir el contenido sin autorización (La República permite la copia para uso personal y privado), y la ley peruana no tiene una excepción para minería de textos. Por eso el cuerpo de las notas solo se procesa en memoria, se guarda únicamente lo que el D. Leg. 822 no protege o permite citar (art. 9: noticias del día con fuente, simples hechos o datos; art. 44: citas breves) y nada se publica más allá de titular, enlace y métricas.

**Videos de YouTube.** `search.list` con 5 términos ("fenómeno El Niño", "Niño costero", "ENFEN", "El Niño Perú", "lluvias costa norte"), `regionCode=PE`, idioma español, mes a mes, orden por fecha y por relevancia: 5 × 10 × 2 = 100 búsquedas (el límite diario). Se conserva un video solo si su título o descripción menciona El Niño y además menciona Perú o una región peruana, o su canal es de Perú.

**Región.** Lista de lugares con los 25 departamentos y las provincias de los departamentos costeros (ubigeos del INEI), agrupados en macro-regiones según el uso del Senamhi:
- Costa norte: Tumbes, Piura, Lambayeque, La Libertad.
- Costa centro: Áncash, Ica.
- Lima: aparte en el análisis (los boletines la tratan de forma inconsistente y dominaría por volumen); para avisos y recomendaciones usa los de costa centro.
- Otros departamentos (costa sur, sierra, selva): "otras regiones".
- Sin mención de lugar: "nacional".

Se ignora el encabezado de lugar de las notas ("LIMA (ANDINA)") y se excluyen provincias con nombres ambiguos (p. ej. "Santa"). No hay una definición oficial publicada de estas macro-regiones: la agrupación es un supuesto declarado.

**Avisos del Senamhi.** Entran solo precipitaciones e incremento de temperatura en costa norte y costa centro; quedan fuera friaje, nevadas, selva y sierra sur. Se presentan como "aviso vigente en tu zona", **nunca como causados por El Niño**.

**Actores (red de co-mención).**
- ENFEN: IMARPE (preside), SENAMHI, DHN, IGP, ANA, INDECI y CENEPRED (según informe técnico del IMARPE).
- Gestión del riesgo: PCM.
- Gobiernos regionales de las macro-regiones analizadas, verificados en gob.pe.
- Personas: NER, solo las que aparecen con frecuencia.

## Tipo de canal
Sin listas editables por terceros (Wikipedia) ni etiquetado manual: cada canal se clasifica por enlaces verificables desde el sitio oficial de su organización. No existe un registro oficial y completo de medios en el Perú (las licencias del MTC salen en resoluciones sueltas y no cubren medios digitales).

1. **Oficial:** el canal está enlazado desde un sitio `.gob.pe` (dominio reservado al sector público; confirmar en la norma de NIC.pe).
2. **Medio:** el canal enlaza a un sitio web, ese sitio enlaza de vuelta al canal y publica notas con metadatos de noticia (`NewsArticle`/`datePublished`) o tiene sitemap de noticias.
3. **Otros:** todo lo demás.

Verificado el 23-oct-2026: Senamhi, Indeci, ENFEN, IGP, RPP, Andina, La República e Infobae enlazan su canal desde su sitio. Errores posibles (medio que no enlaza su canal → "otros"; blog con metadatos de noticia → se descarta exigiendo el enlace de vuelta) se revisan cualitativamente con ejemplos y se declaran.

## Evaluación sin etiquetado manual
| Componente | Cómo se valida |
|------------|----------------|
| Índice de discrepancia | Control positivo (notas de Andina que enlazan al PDF del comunicado → distancia baja, sin contradicción) y negativo (notas de otros temas de los mismos medios → distancia alta); separación de ambas distribuciones (AUC), por separado para titulares y cuerpos. |
| NLI y extractor de magnitud | **Contradicciones sintéticas** generadas automáticamente desde frases oficiales, con etiqueta conocida: cambio de magnitud ("fuerte" → "extraordinaria"), de alcance ("costa norte" → "todo el Perú") y de plazo ("en verano" → "desde mañana"); las frases oficiales sin cambios son el caso "no contradice". Se reporta precisión y exhaustividad. |
| Recuperador / agente | Preguntas generadas desde secciones de los comunicados; recall@k, TF-IDF vs. embeddings. Preguntas generadas por plantillas con herramienta correcta conocida: % de herramienta bien elegida; 100 % de citas literales. |
| Modelo de engagement | Partición temporal (entrenar con meses anteriores, probar con los últimos); MAE y R² contra línea base; importancia de variables. |
| Recomendador | Evaluación offline **de la parte basada en contenido, con el filtro de fecha apagado** (con el filtro, acertar el comunicado vigente sería automático): ¿la similitud sola pone primero el comunicado que la nota enlaza (notas de Andina) o el vigente en su fecha? MRR y precision@k, más cobertura y diversidad. Las reglas basadas en conocimiento se validan con pruebas unitarias. |
| Tópicos | Coherencia c_v y comparación del número de tópicos. |
| Sentimiento | Acuerdo (kappa de Cohen) solo entre métodos independientes: pysentimiento y zero-shot. TF-IDF + regresión logística entrenada con las etiquetas de pysentimiento se reporta como línea base "destilada", no como validación (su acuerdo con pysentimiento sería circular). |
| Emociones | Revisión cualitativa con ejemplos; sin cifra de exactitud. |
| Red social | Modularidad de las comunidades y comparación contra una red aleatoria con los mismos grados. |
| Analítica web | Correlación (Spearman) entre discrepancia y engagement; descriptivo, sin causalidad. |

**Limitaciones declaradas:** no hay métrica de exactitud para "detectar alarmismo"; el producto mide cercanía a lo oficial. El recomendador se evalúa solo offline (sin usuarios reales). El modelo de engagement muestra asociación, no causalidad. Google Trends da interés relativo (0-100, normalizado en cada consulta) con ruido de muestreo y puede no tener datos en departamentos pequeños. Las macro-regiones son una agrupación supuesta. El NLI se valida con contradicciones sintéticas, que no cubren todas las formas de exageración.

## Despliegue
- **Streamlit Community Cloud**, app pública sin datos personales.
- Offline: BERTopic, LDA, emociones, modelo de engagement, redes y el procesamiento de todo el corpus. La app carga esos resultados precalculados.
- En la app, solo lo necesario para textos nuevos (semáforo y agente): el modelo de embeddings (~470 MB) y el de NLI (~560 MB), más el índice de ChromaDB de los textos oficiales, que se reconstruye al iniciar.
- El registro de uso va a un almacenamiento externo: el sistema de archivos de Community Cloud se borra en cada reinicio.
- La app no usa la clave de YouTube: un video nuevo se analiza pegando su título y descripción. La clave del LLM va en los *secrets* de la plataforma, con un límite diario de consultas.
- **Derecho de autor:** de las notas solo se muestra titular, medio, fecha, enlace y nuestras métricas; ningún fragmento del cuerpo (ver "Alcance de datos"). Los comunicados y avisos son textos oficiales (D. Leg. 822, art. 9.b) y se pueden mostrar completos citando la fuente.
- Ritmo bajo de peticiones a los medios, para no caer en el "consumo masivo de recursos" que prohíben sus términos.

## Organización del trabajo
El trabajo se divide en **dos verticales de punta a punta** en lugar de "datos / modelos": así nadie espera al otro para empezar y cada integrante toca scraping, minería de texto, redes, ML y analítica (los exámenes son individuales).

| | Vertical Noticias | Vertical YouTube |
|---|---|---|
| Scraping | 4 medios (sitemaps, HTML, `robots.txt`) | API de YouTube y exportación de Google Trends |
| Minería de texto | Tópicos y emociones de las notas | Emociones de títulos y comentarios |
| Redes | Red de enlaces y citas; co-mención de actores | Red social de audiencias; tipo de canal |
| ML | Índice de discrepancia y calibración del semáforo | Modelo de engagement |
| Analítica | Indicadores de los medios; estudio de eventos | KPIs de engagement; interés en Trends |

**Trabajo conjunto:** corpus oficial (ENFEN y Senamhi), preprocesamiento y asignación de región en la semana 1; recomendador, agente y dashboard en las semanas 3-4; conclusiones del informe. Cada integrante escribe las partes de su vertical en cada fase de CRISP-ML(Q).

La asignación de verticales y del coordinador (vocero ante el profesor) está pendiente.

**Evidencia del aporte individual** (directiva de trabajo grupal del sílabo):
- `docs/declaracion-trabajo-grupal.md` con el formato del anexo del sílabo: planificación y funciones al inicio, labor realizada al final.
- `docs/avances/semana-N.md` cada semana, con lo que hizo cada integrante y enlaces a sus commits, más una etiqueta de git por semana.
- Cada integrante hace commits con su propia cuenta; los commits hechos con IA llevan la línea `Co-Authored-By`.

## Plan de 4 semanas
Las horas son una estimación orientativa, no un límite; el alcance agregado puede tomar más tiempo.

| Semana | Vertical Noticias | Vertical YouTube | Conjunto | Entregable |
|--------|-------------------|------------------|----------|------------|
| 1 | **Primero:** pruebas de viabilidad de noticias. Luego scrapers de los 4 medios; enlaces y citas | **Primero:** pruebas de viabilidad de YouTube y Trends. Luego recolector de YouTube por API; exportar Trends | Corpus oficial, preprocesamiento, asignación de región, TF-IDF | Resultado de las pruebas (pasa / no pasa) y dataset limpio con fechas, regiones, enlaces y videos |
| 2 | Red de enlaces y citas; tópicos y emociones de notas | Red social de audiencias; tipo de canal; emociones de videos | Embeddings | Notebooks con resultados |
| 3 | Índice de discrepancia, semáforo, estudio de eventos | Modelo de engagement, KPIs de analítica web | Recomendador híbrido; evaluación | Métricas validadas |
| 4 | Descarga del corte (20-nov); informe de su vertical | Descarga del corte (20-nov); informe de su vertical | Agente, dashboard con registro de eventos, despliegue, conclusiones | Producto, informe y presentación |

## Informe: CRISP-ML(Q)
El informe se organiza por las seis fases de Studer et al. (2021), cada una con su control de calidad:

| Fase | Contenido | Control de calidad |
|------|-----------|--------------------|
| 1. Comprensión del negocio y de los datos | Problema, preguntas, fuentes, pruebas de viabilidad | Criterios de pasa / no pasa |
| 2. Preparación de datos | Recolección, limpieza, seudonimización, reglas por sitio. Incluye una sección de **protocolos web** con casos propios: códigos HTTP (403 de Expreso, 404 del `robots.txt` de Andina), reglas por user-agent (RPP), sitemaps y RSS, JSON-LD, API REST con cuotas y verificación de identidad por enlace sitio–canal | Conteos, duplicados, fechas válidas |
| 3. Ingeniería del modelo | Vectores, tópicos, emociones, modelo de engagement, recomendador, agente | Líneas base y comparación de métodos |
| 4. Evaluación | Tabla de evaluación | Controles positivo y negativo, partición temporal |
| 5. Despliegue | Dashboard y agente | Registro de uso de la app |
| 6. Monitoreo y mantenimiento | Re-descarga cada 30 días (regla de YouTube); rendimiento en datos posteriores al corte (simulación, declarada) | Cambios en discrepancia y error en el tiempo |

## Recortes, en orden
1. Transcripciones de YouTube.
2. Efecto comunicado solo con volumen (sin emociones ni engagement).
3. Indicadores secundarios de los medios.
4. Agente sin LLM (enrutador por embeddings); en último caso, solo extractivo.
5. Bajar de 3 a 2 medios nacionales (Andina, como control, y El Tiempo se mantienen).

**Núcleo que no se recorta:** scraping (incluido YouTube), vectores (TF-IDF y embeddings), índice de discrepancia (con NLI si pasa su prueba), tópicos, emociones, modelo de engagement, recomendador, analítica web, red social (o su respaldo de co-mención), estudio de eventos, agente con herramientas (o su respaldo) y dashboard.

## Primera noche: pruebas de viabilidad
- [x] Verificar que las notas traigan enlaces a fuentes oficiales en el HTML. *Andina enlaza al PDF del comunicado; Infobae solo cita en texto → se agregan menciones en texto.*
- [x] Revisar `robots.txt` de esos medios. *Ver "Reglas por sitio".*
- [x] Verificar fechas de publicación. *Las notas traen `datePublished` separado de `dateModified`.*
- [x] Revisar estructura de comunicados y avisos. *Usan macro-regiones, no departamentos; más de 400 avisos en 2026.*
- [ ] Contar comentarios de ~30 videos de YouTube sobre El Niño **con la API oficial**. Decide si la red social usa YouTube o el respaldo de co-mención.
- [ ] Revisar en Google Trends si hay datos por departamento de la costa norte (en especial Tumbes) para "El Niño".
- [x] Revisar términos de uso de los medios. *Todos prohíben reproducir sin autorización; Infobae prohíbe "tratar" el contenido → excluido. Ver "Alcance de datos".*
- [ ] Descargar los comunicados ENFEN y probar la extracción de fecha, estado y magnitud con reglas.
- [ ] Extraer avisos del Senamhi (fecha, tipo, nivel, macro-región) y aplicar el filtro.
- [ ] Probar pysentimiento (polaridad y emociones) sobre ~20 titulares.
- [ ] Contar notas sobre El Niño por medio en el período (sitemaps).
- [ ] Probar el NLI con ~20 contradicciones sintéticas.

### Criterios de pasa / no pasa
Heurísticas fijadas antes de correr las pruebas, para no acomodarlas después.

| Prueba | Pasa si… | Si no pasa |
|--------|----------|------------|
| Volumen de noticias | ≥ 400 notas sobre El Niño en el período entre los 4 medios (heurística para tópicos estables) | Sumar secciones o ampliar términos; tópicos solo a nivel global |
| Videos de YouTube | ≥ 300 videos del período que mencionan El Niño | YouTube deja de ser central; evaluar plan B |
| Comentarios | ≥ 100 videos con ≥ 30 comentarios | Engagement sin comentarios; red social con respaldo de co-mención |
| Red de audiencias | La red canal–canal tiene un componente conectado de ≥ 30 canales | Respaldo de co-mención |
| Tipo de canal | ≥ 70 % de los canales de la muestra se clasifican sin ambigüedad | Revisar las reglas de "Tipo de canal" |
| Google Trends | ≥ 3 de los 4 departamentos de la costa norte con datos en ≥ 50 % de las semanas | Trends solo a nivel nacional |
| pysentimiento | Emociones coherentes en la revisión cualitativa de ~20 titulares | Solo polaridad, aplicada al cuerpo de la nota |
| NLI | Detecta ≥ 15 de ~20 contradicciones sintéticas sin marcar las frases oficiales sin cambios | Discrepancia solo con distancia y regla de magnitud; declararlo |

**Plan B** (reseñas de servicios digitales en Google Play, con estrellas como etiqueta externa): solo si fallan a la vez la prueba de videos y el contraste medios–YouTube.

## Datos y fuentes
- Comunicados oficiales: https://enfen.imarpe.gob.pe/comunicados/ (ENFEN: IMARPE, SENAMHI, DHN, IGP, ANA, INDECI y CENEPRED).
- Avisos meteorológicos: https://www.senamhi.gob.pe/?p=aviso-meteorologico
- Estado visto al 22-oct-2026: "Alerta de El Niño Costero", comunicados hasta N.° 18-2026. Confirmar en la fuente antes de citar.
- YouTube Data API v3 (página oficial de cuotas, 23-oct-2026): 10 000 unidades/día; `commentThreads.list`, `videos.list` y `channels.list` cuestan 1 unidad; `search.list` tiene un límite propio de 100 llamadas/día (hasta 50 resultados cada una).
- Google Trends: `pytrends` está archivado (confirmado en GitHub) y el API oficial está en alfa cerrado; se usa la exportación CSV de la web. Cada consulta se normaliza a 0-100 por separado, por eso cada departamento se descarga en una sola consulta que cubra todo el período (datos semanales).
- **No verificado aún:** volumen de comentarios de YouTube, datos de Trends por departamento, texto oficial del D. Leg. 822 (se leyó una transcripción de terceros), límites actuales de Streamlit Community Cloud, acceso al listado oficial de ubigeos del INEI y calidad de las emociones de pysentimiento en titulares.

## Reglas por sitio (revisado el 22 y 23-oct-2026)
| Sitio | Regla |
|-------|-------|
| Andina | Sin `robots.txt`; usar sitemap. |
| RPP | Bloquea por completo a Scrapy y bots de IA; usar `requests` con un user-agent honesto, nunca suplantando otro. Términos: prohíben la reproducción "en cualquier soporte" y el consumo masivo de recursos. |
| La República | Prohíbe `/archivo/`; recolectar solo desde sitemaps/RSS. Términos: permiten copiar y almacenar solo para uso personal y privado. |
| El Tiempo (Piura) | Permite el acceso salvo `/wp-admin/`; usar sus sitemaps. Términos: misma redacción que RPP. |
| Infobae | **Excluido**: sus términos prohíben "tratar" el contenido. |
| Expreso | Responde 403: **excluido**. |
| YouTube | Solo la API oficial; `robots.txt` prohíbe `/results`. Borrar o refrescar datos crudos a los 30 días (políticas de la API); guardar agregados y seudónimos. |

## Reglas del proyecto
- **Cero etiquetado manual.** Toda validación usa una referencia externa.
- **Ética de scraping:** `robots.txt`, términos de uso, rate limiting, propósito declarado; sin eludir bloqueos. `requests` + `BeautifulSoup`; Playwright solo si es imprescindible.
- **Privacidad:** seudonimizar; no guardar nombres de usuario ni identificadores personales.
- **Derecho de autor:** el cuerpo de las notas no se guarda, no se versiona ni se publica; solo titular, enlace, datos derivados y métricas.
- **IA generativa:** se declara su uso y se conserva un registro de prompts en `docs/prompts.md`. En el producto, un LLM solo se usa dentro del agente para elegir herramientas. Los modelos preentrenados de NLP (embeddings, emociones) se usan como herramientas de minería de texto.
- **Comunicación de resultados:** el índice de discrepancia no es un "detector de desinformación" y no se señalan medios ni canales individuales; se reporta por tipo de fuente.

## Decisiones abiertas
Las definiciones de este README son la mejor alternativa evaluada al 23-oct-2026 y pueden cambiar según las pruebas de viabilidad o la opinión del profesor.

## Estructura del repo
```
data/raw/        comunicados (PDF/HTML), avisos, respuestas de la API de YouTube, CSV de Trends (no se versiona; nunca el cuerpo de las notas)
data/processed/  párrafos oficiales, titulares y resúmenes, enlaces, citas, vectores, resultados de NLI y agregados (no se versiona)
notebooks/       exploración y análisis
src/             crawler, recolector YouTube, redes, recuperación, sentimiento, tópicos, modelo de engagement, recomendador, agente, dashboard
results/         figuras y métricas
docs/            bibliografía, notas y registro de prompts
```
