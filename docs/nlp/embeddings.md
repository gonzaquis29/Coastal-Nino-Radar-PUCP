# Embeddings (1-nov-2026)

Representación de la distancia a lo oficial (README, pipeline 3): MiniLM (`paraphrase-multilingual-MiniLM-L12-v2`) frente a e5-small (`multilingual-e5-small`), comparados con la línea base TF-IDF ([tfidf.md](tfidf.md)). Los criterios se fijaron y aprobaron antes de correr, después de un piloto con los titulares.

```
python -m radar.nlp.embeddings leer        # pide páginas (@exclusivo); se puede cortar y relanzar
python -m radar.nlp.embeddings criterios   # sin red
python -m radar.nlp.embeddings revision    # sin red: 10 notas nuevas con su párrafo más cercano
```

## Piloto con los titulares (sin red, antes de definir)
Coseno máximo de cada titular con los 264 párrafos del ENFEN, en todo el corpus del TF-IDF:

| AUC | MiniLM | e5-small |
|---|---|---|
| sobre El Niño frente a otros temas, sin los términos del fenómeno | 0,764 | 0,840 |
| ídem, con todo | 0,876 | 0,889 |
| control positivo frente a otros temas, con todo | 0,995 | 0,991 |
| sobre El Niño frente a "cercano", sin términos | 0,632 | 0,695 |
| positivos cuyo párrafo más parecido es del comunicado que citan (al azar ~5 %) | 18 % | 39 % |

Lo que cambió la definición:
- **Largo.** MiniLM se entrenó con 128 tokens, y el 14 % de los párrafos del ENFEN pasa de ese largo; el cuerpo mediano tiene 423 palabras (p90: 785). Cada modelo usa su largo propio (MiniLM 128, e5 512) y el texto se parte en tramos que caben sin truncar.
- **Derecho de autor.** Los vectores de cada tramo permitirían reconstruir el texto de forma aproximada. Solo se guarda un vector por nota (el promedio) y sus puntajes.
- **Control positivo chico y solo de Andina** (41 notas, 13 que no son "sobre El Niño"): los AUC llevan un intervalo de 95 % por bootstrap, y se reporta además Andina frente a Andina.
- e5 da cosenos comprimidos (0,80-0,94): no afecta al AUC, pero deja los umbrales del semáforo muy juntos. Se declara.

## Definición
**Corpus:** el del TF-IDF (notas sobre El Niño y control negativo) más las 13 notas del control positivo que no son "sobre El Niño". El control positivo son las notas de Andina que citan un comunicado del ENFEN (`comunicados` de `notas.csv`, cualquier nivel). Se compara con los 264 párrafos del ENFEN.

**Texto:** titular, resumen (si no está en el cuerpo) y cuerpo, como en el TF-IDF. Los titulares se miden aparte, sin red, desde `notas.csv`. "Sin términos" quita las menciones de El Niño o La Niña (regla de `noticias.rasgos`) y las palabras ENFEN, FEN, costero, niño y niña, como T4.

**Tramos:** líneas completas juntas mientras quepan en el largo del modelo (con el prefijo `query: ` de e5 y los tokens especiales); una línea que no cabe se parte por oraciones y, si hace falta, por palabras. Los párrafos del ENFEN se parten igual.

**Puntaje:** coseno máximo entre los tramos de la nota y los tramos de los párrafos. Informativos: el vector promedio de la nota frente a cada párrafo, y frente al centroide del ENFEN.

**Modelos:** torch en float32 para los dos candidatos, y e5 cuantizado en ONNX, que es el que usaría la app.

**Salidas** (`data/processed/nlp/`): `embeddings.csv` (puntajes y controles por nota y modelo) y `vectores.csv` (el vector promedio de cada nota en base64, float32).

## Criterios
Sobre todo el corpus, sin muestras, por separado para titulares y cuerpos.

| | Criterio | Umbral |
|---|---|---|
| E1 | lectura de los cuerpos (como T1): notas leídas con texto; sha1 igual al de `notas.csv` | ≥ 98 %; ≥ 95 % |
| E2 | el promedio propio reproduce a `sentence-transformers` en los tramos del ENFEN; ningún tramo truncado | coseno ≥ 0,9999; 0 |
| E3 | **semáforo (README):** AUC del control positivo frente a otros temas, texto completo, sin que los umbrales se crucen (p25 del positivo > p75 del negativo) | ≥ 0,80 |
| E4 | **representación (como T4):** cuerpos sobre El Niño frente a otros temas, sin los términos del fenómeno | ≥ 0,90 |
| E5 | e5 cuantizado frente a float32, en E3 y E4 de cuerpos | \|ΔAUC\| ≤ 0,01 |

**Elección:** el de mayor E4 en cuerpos; si la diferencia es menor de 0,02, e5 (0,78 GB en la app frente a 1,31 GB). E3, E4 y E5 deciden con el modelo elegido; E5 solo decide si se elige e5.

**Informativos:** los dos modelos en E3 y E4; frente a "cercano"; por medio y por tramo de menciones; vector promedio y centroide; Andina frente a Andina; acierto del comunicado citado; revisión de 10 notas nuevas (semilla `embeddings-revision-1nov`).

Si E3 pasa y E4 no, el semáforo se calibra igual con E3, como pide el README, y se declara que la separación depende de cuánto habla la nota de El Niño.

## Resultado: PASA, con e5-small
La lectura tomó 64 min (los embeddings, no la red, marcan el ritmo) y los criterios, 30 min: 3.190 notas con texto y 1 sin texto, 0 tramos truncados.

| | e5 (elegido) | | MiniLM |
|---|---|---|---|
| E1 leídas con texto / sha1 igual | 99,97 % / 99,91 % (3 de Andina, ediciones del sitio) | pasa | |
| E2 coseno con sentence-transformers / truncados | 1,0000 / 0 | pasa | 1,0000 |
| E3 titulares (IC 95 %) | 0,901 (0,835-0,959); p25 positivo 0,851 > p75 negativo 0,825 | pasa | 0,880 |
| E3 cuerpos | 0,951 (0,902-0,989); 0,898 > 0,856 | pasa | 0,931 |
| **E4 cuerpos** | **0,912** (0,897-0,925) | pasa | 0,913 |
| E5 e5 cuantizado | \|ΔAUC\| 0,0063 en E3 y 0,0001 en E4 | pasa | — |

**Elección.** MiniLM y e5 empatan en E4 (0,913 frente a 0,912), así que manda la regla de empate: e5, que en la app cabe cuantizado (0,78 GB) y da lo mismo que en float32 (E5).

Informativos (e5; MiniLM entre paréntesis):
- Frente al TF-IDF: E4 sube de 0,799 a 0,912. En titulares, E4 es 0,840 (0,772).
- Frente a "cercano", sin términos: 0,737 (0,721). Las lluvias y el calor sin El Niño siguen siendo difíciles de separar.
- Por tramo de menciones: 0,866, 0,920 y 0,983 (igual en MiniLM). La dependencia que ya se vio en el TF-IDF sigue, aunque más atenuada.
- Por medio: entre 0,893 (Andina) y 0,934 (El Tiempo).
- Vector promedio 0,885 y centroide 0,875 (MiniLM: 0,930 y 0,917). Con e5 conviene el máximo por tramo.
- Andina frente a Andina, E3: 0,938 (0,920). El efecto del medio no explica el control positivo.
- Positivos cuyo párrafo más parecido es del comunicado que citan: 17/41 en cuerpos y 9/41 en titulares (MiniLM: 17 y 5).

**Límites que se declaran:**
- El límite inferior del IC de E4 (0,897) queda apenas bajo 0,90.
- En titulares, el margen entre los umbrales del semáforo es chico: 0,851 frente a 0,825, con cuantizado 0,853 frente a 0,832.

**Revisión de 10 notas nuevas** (semilla `embeddings-revision-1nov`, sin decidir nada):
- En 5 el párrafo más parecido es del tema: pérdidas por el FEN con la alerta, lluvias en China con las lluvias en la costa, quebradas con las lluvias en la costa norte, dengue con las temperaturas del aire, y descolmatación en Lambayeque con los embalses de Lambayeque.
- En las otras 5, notas de política (Senado, Midagri, MEF, Defensa, canales oficiales), el párrafo es genérico: la definición de "Alerta" o el de embalses.

**Hallazgo: párrafos "imán" (hubness).** Con e5, un solo párrafo de definiciones (`enfen-2026-11-p14`, la definición de "Alerta de El Niño Costero") es el más parecido para el 11,5 % de las notas sobre El Niño. Los 14 párrafos de tipo `definicion` (el 5 % del ENFEN) se llevan el 14,6 %. No cambia el AUC, pero sí lo que mostraría el semáforo como "párrafo oficial más cercano". Hay que decidirlo al construir el semáforo (por ejemplo, comparar sin los párrafos de `definicion` o elegir el párrafo por `tipo`), y no aquí, para no ajustar el criterio después de ver el resultado.

## Mapa de alternativas (2-nov-2026)
La comparación del 1-nov solo usó los dos modelos del README. Este mapa revisa el problema completo antes de elegir. Nada de lo que sigue cambia los criterios E1 a E5 ni el resultado de arriba.

**Papeles** (qué tiene que hacer el modelo):
- **P1, semáforo:** distancia de un texto nuevo a los párrafos oficiales, en la app local y una vez por consulta.
- **P2, recuperador:** párrafos para el agente y el recomendador (recall@k, README).
- **P3, corpus offline:** las 3.190 notas, sin apuro de tiempo.
- **P4, validación independiente:** una referencia que no sean nuestros controles indirectos.

**Restricciones:**

| | Restricción | Origen |
|---|---|---|
| Verificada | La app principal corre en local: 15,6 GB de RAM, 14 núcleos, sin GPU | Decisión del 2-nov; el sílabo no exige publicar la app |
| Verificada | El cuerpo de las notas no sale a servicios externos | CLAUDE.md, derecho de autor |
| Verificada | Licencia abierta y sin código propio del repositorio del modelo (`trust_remote_code`) | Uso académico; seguridad: no se ejecuta código de terceros sin revisarlo |
| Decisión revisable | Streamlit; LLM por API solo en el agente | README |
| Por medir | Tiempo por consulta en esta CPU | Supuesto sin medir hasta hoy |

**Tipos de enfoque:**

| Tipo | Ejemplos | P1 | P2 | P3 | P4 | Veredicto |
|---|---|---|---|---|---|---|
| Léxico | TF-IDF, BM25 | sí | sí | sí | — | TF-IDF ya probado (E4 0,80). BM25 entra en el híbrido |
| Vectores estáticos | fastText en español, model2vec | sí | sí | sí | — | Descartado: sin contexto, y el TF-IDF ya cubre la línea base barata |
| **Bi-encoder** | e5, granite, bge-m3, Qwen3-Embedding | sí | sí | sí | — | **Probar** (filtro y prueba completa) |
| Cross-encoder (reranker) | bge-reranker-v2-m3, mmarco-mMiniLM | 2.ª etapa | 2.ª etapa | sí | — | **Probar** como 2.ª etapa sobre los 10 mejores párrafos: puede resolver el párrafo "imán" |
| Híbrido | BM25 + bi-encoder (fusión de rangos) | sí | sí | sí | — | **Probar** después de elegir el bi-encoder |
| NLI (cross-encoder) | mDeBERTa | sí | — | sí | — | Ya definido en la capa 5. Con la app local, la memoria no lo excluye |
| Ajuste fino del bi-encoder | e5 con pares débiles | — | — | — | — | Descartado: los únicos pares sin etiquetado manual son el control positivo (41), así que se evaluaría con lo mismo que se entrenó |
| Embeddings por API | OpenAI, Cohere, Voyage | — | — | — | — | Descartado: el cuerpo no puede salir y la app dependería de un servicio de pago |
| LLM generativo | Sonnet por API; Qwen o Llama local | lento y de pago | — | — | sí | Solo como **juez offline** de titulares y párrafos oficiales (nunca cuerpos). Decisión del equipo; se declara en `prompts.md` |

**Candidatos bi-encoder.** Fuentes: los modelos de similitud en español de Hugging Face ordenados por descargas, la búsqueda del 1-nov (anuncios y blogs) y los del README. Se excluyen los que traen código propio (gte-multilingual-base, snowflake-arctic-embed-m-v2.0, nomic-embed-text-v2-moe), los de licencia no abierta o con aprobación manual (EmbeddingGemma, Nemotron, LFM2.5), y LaBSE (está hecho para alinear traducciones, no para similitud). El tamaño no es criterio de exclusión: se mide el tiempo.

| Candidato | Tamaño | Licencia | Titulares, informativo: E4 / E3 |
|---|---|---|---|
| paraphrase-multilingual-MiniLM-L12-v2 | 118M | Apache 2.0 | 0,772 / 0,880 (cuerpos, 1-nov) |
| multilingual-e5-small | 118M | MIT | 0,840 / 0,901 |
| multilingual-e5-base | 278M | MIT | 0,853 / 0,885 |
| granite-embedding-278m-multilingual | 278M | Apache 2.0 | 0,851 / 0,911 (7 veces más lento que e5-base, sin explicar) |
| Qwen3-Embedding-0.6B | 596M | Apache 2.0 | cortado (se mide en cuerpos) |
| granite-embedding-107m-multilingual | 107M | Apache 2.0 | por probar |
| paraphrase-multilingual-mpnet-base-v2 | 278M | Apache 2.0 | por probar |
| snowflake-arctic-embed-l-v2.0 | 568M | Apache 2.0 | por probar |
| bge-m3 | 568M | MIT | por probar |
| sentence_similarity_spanish_es (BETO) | 110M | Apache 2.0 | por probar (único entrenado solo en español) |

**Candidatos reranker (2.ª etapa):** mmarco-mMiniLMv2-L12 (118M), mxbai-rerank-base-v2 (494M) y bge-reranker-v2-m3 (568M), todos con licencia abierta y sin código propio.

**Límite de lo que se mide.** E3 y E4 miden si la nota habla del mismo tema que el ENFEN, no si dice lo mismo. La alineación de cifras la cubren la regla de magnitud y el NLI, y la utilidad del párrafo mostrado, la 2.ª etapa y P4.

**Revisión del mapa (2-nov):**
- El filtro con titulares se descarta. MiniLM salió peor que e5 en titulares (0,772 frente a 0,840) y empató con él en cuerpos (0,913 frente a 0,912): los titulares no predicen el orden en cuerpos.
- La consulta de la app (P1) es un texto corto, porque el README dice que se pega un titular o un título con su descripción. El tiempo que importa es el de esa consulta. Los cuerpos son P3, offline.
- **El semáforo compara con los párrafos vigentes en la fecha, no con todo el ENFEN** (CLAUDE.md: `radar.oficial.vigencia.Corpus`). E3 y E4 se midieron contra los 264 párrafos sin mirar la fecha, y con e5 solo el 8 % de las notas sobre El Niño tiene como párrafo más parecido uno vigente en su fecha (al azar, 5 %). E3 y E4 miden si la nota habla del tema, no a qué comunicado corresponde.

## Plan de pruebas (2-nov, por aprobar)
Todas usan el corpus completo (sin muestras de notas) y criterios fijados antes de correr. Las lecturas llevan `@exclusivo` y no pueden chocar con la recolección diaria (máximo 48 h entre corridas). La máquina de referencia es esta laptop (15,6 GB, 14 núcleos, sin GPU): la de la presentación será esta u otra mejor.

**A. Tiempo y memoria (sin red, ~1 h).** Con cada uno de los 10 candidatos cargado en esta laptop:
- A1, consulta: mediana de 20 consultas de un titular más su resumen (embeber y comparar con los 865 párrafos ya embebidos);
- A2, rendimiento offline: tramos de 512 tokens por segundo, para estimar cuánto tarda B;
- A3, memoria del proceso;
- antes de usar los tiempos, se busca la causa de la lentitud de granite y Qwen3 (configuración o script).

**Criterio A:** A1 ≤ 2 s. Memoria: el modelo más el NLI en float32 (2,7 GB), Streamlit y el sistema tienen que caber en la laptop; con 16 GB, el embedding debe quedar en ≤ 6 GB. Con A2 se arma el calendario de B: si no entra en una noche, se reparte en varias noches (la lectura se puede cortar y relanzar) y no se recorta el corpus.

**B. Bi-encoders en cuerpos (con red, en las noches que diga A2).**
- Los candidatos que pasen A, más MiniLM y e5-small del 1-nov, con el mismo código de tramos, cargados con `sentence-transformers` (cada modelo con su pooling).
- Varias pasadas según la memoria, porque el cuerpo no puede guardarse entre pasadas.
- **Largo:** el de cada modelo, con un tope de 512 tokens.
- **Prompts fijados ahora:** `query: ` en las dos partes para e5; `query: ` en la nota para arctic-l-v2; para Qwen3, en la nota, "Instruct: Given a news article, retrieve the official bulletin paragraph about the same topic
Query:" (en inglés, como recomienda su ficha; se declara); los demás, sin prompt.
- **No hay campeón de partida:** e5 ganó el empate del 1-nov por memoria en la app pública, y esa razón ya no aplica.

| | Métrica | Rol |
|---|---|---|
| B1 | E4 en cuerpos, frente a todo el ENFEN | **decide** |
| B2 | E4 en cuerpos, frente a los párrafos del ENFEN vigentes en la fecha de la nota (`vigente_desde` a `vigente_hasta`) | **decide** |
| B3 | E3 en cuerpos y titulares, sin cruce (con todo el ENFEN y con los vigentes) | **debe pasar** (≥ 0,80) |
| B4 | comunicado citado: el párrafo más parecido es del comunicado que cita la nota, en las 67 notas sobre El Niño que citan uno (e5 31/67, MiniLM 40/67) | informativo; McNemar exacto frente al elegido |
| B5 | vigencia: el párrafo más parecido es de un comunicado vigente en la fecha, exacto o ±1 comunicado (e5: 8 %; al azar, 5 %) | informativo |
| B6 | concentración: % de notas cuyo párrafo más parecido es el más repetido, y % de tipo `definicion` (e5: 11,5 % y 14,6 %) | informativo |
| B7 | B1 y B3 contra los 865 párrafos (ENFEN y Senamhi), que es lo que tendrá la app | informativo |

**Regla de elección:** se toma el de mayor B1 entre los que pasan B3. Otro lo reemplaza solo si lo supera en B1 y en B2 por ≥ 0,02 y sin que se solapen los IC del 95 %. Entre los que no se distinguen así, gana el más rápido en A1. Con 10 candidatos, elegir el máximo favorece al que tuvo suerte; el margen y los IC lo atenúan y se declara.

**C. Segunda etapa con reranker (con red, una lectura).** Sobre los 10 párrafos más parecidos según el bi-encoder elegido, se reordena con mmarco-mMiniLMv2, mxbai-rerank-base-v2 y bge-reranker-v2-m3.

**Criterio C:** se adopta si mejora B4 con McNemar exacto p < 0,05, baja B6 y la consulta queda en ≤ 2 s (10 pares por consulta). Si dos pasan, gana el más rápido. E3 y E4 con el puntaje del reranker, informativos.

**D. Híbrido BM25 + bi-encoder** (fusión de rangos, k = 60; sin red, reusa las bolsas del TF-IDF y los puntajes de B). Para E4, BM25 va sin los términos del fenómeno, igual que T4. **Criterio D:** se adopta si cumple la misma regla que B (≥ 0,02 en B1 y B2, sin solape de IC) o mejora B4 con McNemar p < 0,05, sin empeorar B3.

**E. Recall@k del recuperador (P2).** Tarea aparte, con las preguntas por plantillas del README. Se define cuando termine B.

**F. LLM como juez offline (P4).** Solo si el equipo lo decide; con titulares y párrafos oficiales, nunca con cuerpos.

**Límites que se declaran:** E3 y E4 miden el tema y no la alineación; la regla de vigencia del semáforo (fecha y macro-región) se decide en la semana 3, y B2 usa solo la fecha; el control positivo es chico (41) y las 67 notas que citan un comunicado también.

**Qué no cambia:** el resultado del 1-nov (pasa con e5) sigue vigente hasta que B diga otra cosa.

## Resultado de A (2-nov): pasan los 10
`python -m radar.nlp.candidatos tiempo`, un proceso por candidato, todos en float32. **Causa de la lentitud del 1-nov:** granite y Qwen3 vienen guardados en bfloat16, y transformers 5 los cargaba así. En CPU eso es mucho más lento, por eso CLAUDE.md exige float32. Corregido en `candidatos.cargar`.

| Candidato | Consulta | Memoria | Tramos de 500 tokens/s | B estimado |
|---|---|---|---|---|
| minilm | 0,024 s | 1,37 GB | 47,2 (largo 128) | ~0,4 h* |
| e5-small | 0,024 s | 1,54 GB | 8,6 | ~0,4 h |
| e5-base | 0,057 s | 2,27 GB | 2,8 | ~1,3 h |
| granite-107m | 0,012 s | 1,47 GB | 17,7 | ~0,2 h |
| granite-278m | 0,057 s | 2,28 GB | 2,8 | ~1,3 h |
| mpnet | 0,053 s | 2,04 GB | 13,1 (largo 128) | ~1,1 h* |
| beto-es | 0,057 s | 1,33 GB | 2,9 | ~1,2 h |
| arctic-l | 0,189 s | 3,46 GB | 0,87 | ~4,1 h |
| bge-m3 | 0,185 s | 3,27 GB | 0,87 | ~4,1 h |
| qwen3 | 0,333 s | 3,45 GB | 0,52 | ~6,8 h |

\* Con largo 128, la prueba de 500 tokens se trunca y el rendimiento sale inflado. En B usan unas 4 veces más tramos, y la estimación ya lo corrige.

**Calendario de B** (la lectura se puede cortar y relanzar; no puede coincidir con la recolección diaria):
- pasada 1: minilm, e5-small, e5-base, granite-107m, granite-278m, mpnet y beto-es, ~6 h;
- pasada 2: arctic-l y bge-m3, ~8 h;
- pasada 3: qwen3, ~7 h.

MiniLM y e5-small se recalculan en la pasada 1, porque B2, B5 y B7 necesitan puntajes que el 1-nov no guardó. Su B1 debe reproducir el E4 del 1-nov (control del instrumento, ± 0,005).

## Resultado de B, pasada 1 (3-nov, provisional)
Se leyeron 3.186 notas (1 con error de lectura) en 7,7 h; se había estimado ~6 h. Hubo 0 tramos truncados. **Control del instrumento: pasa.** MiniLM da 0,9129 y e5-small 0,9122, igual que el E4 del 1-nov.

| Modelo | B1 (todo ENFEN) | B2 (vigente) | B3 | B4 citado | B5 exacto / ±1 | B6 repetido |
|---|---|---|---|---|---|---|
| mpnet | **0,929** (0,916-0,940) | 0,922 | pasa | 36/67 | 0,09 / 0,24 | 0,25 |
| beto-es | 0,920 | **0,938** | pasa | 20/67 | 0,12 / 0,30 | 0,20 |
| minilm | 0,913 | 0,910 | pasa | **40/67** | ver CSV | ver CSV |
| e5-small | 0,912 | 0,874 | pasa | 31/67 | ver CSV | ver CSV |
| e5-base | 0,902 | 0,898 | pasa | 32/67 | ver CSV | ver CSV |
| granite-278m | 0,900 | 0,885 | pasa | 37/67 | 0,08 / 0,22 | 0,09 |
| granite-107m | 0,887 | 0,885 | pasa | 32/67 | 0,10 / 0,27 | 0,07 |

**Elección provisional según la regla: minilm.** El líder en B1, mpnet, no supera por 0,02 en B1 y en B2 a minilm, e5-small, e5-base ni beto-es. Entre esos cinco, el más rápido en A1 es minilm. Los dos granite quedan fuera.

Lecturas críticas (informativas):
- beto-es tiene el mejor B2, pero el peor B4 (McNemar frente a minilm, p = 0,0003). Reconoce el tema, pero no el comunicado.
- En todos los modelos, el comunicado vigente exacto acierta poco (8-12 %).
- mpnet concentra el 25 % de las notas en un solo párrafo.

## Resultado de B, pasada 2 (5-nov, provisional)
Se leyeron las 3.191 notas de arctic-l y bge-m3. Quedan 3.189 notas comunes a todos los modelos: una nota de RPP sin texto, y una de Andina (1090297) que se leyó en la pasada 1 pero ya no está publicada. Por eso MiniLM baja de 0,9129 a 0,9128; el control del instrumento sigue pasando. Hubo 0 tramos truncados.

| Modelo | B1 | B2 | B3 | B4 citado | B5 exacto / ±1 | B6 repetido |
|---|---|---|---|---|---|---|
| arctic-l | 0,916 (0,905-0,928) | 0,916 | pasa | 29/67 | 0,08 / 0,22 | 0,31 |
| bge-m3 | 0,890 (0,876-0,906) | 0,886 | pasa | 35/67 | 0,08 / 0,22 | 0,17 |

**La elección provisional sigue siendo minilm.** arctic-l empata con el líder, pero es 8 veces más lento en A1, acierta menos el comunicado citado (McNemar frente a minilm, p = 0,027) y tiene la mayor concentración en un solo párrafo (31 %). bge-m3 queda fuera por la regla de reemplazo. Falta la pasada 3 (qwen3).

La duración real dependió de la memoria y de la corriente: unas 6 notas por minuto enchufada y con RAM libre; unas 2 con Chrome pesado o a batería. El 3-nov la paginación a disco explicó la lentitud (el proceso necesitaba 7,4 GB y solo tenía 2,6 GB en RAM).

## Pasada 3 con muestra (criterio fijado el 5-nov, antes de correrla)
La pasada completa de qwen3 cuesta entre 9 y 18 h y mantiene detenidos `historico` y `corpus`. Por la regla de reemplazo, qwen3 solo cambia la decisión si supera a minilm por 0,02 en B1 y en B2. Se mide primero en una muestra:

```bash
python -m radar.nlp.candidatos leer --pasada 3 --muestra
python -m radar.nlp.candidatos criterios
```

- **Muestra:** 300 notas al azar sobre El Niño y 300 de otros temas (semilla del proyecto). Se leen además las 36 del control positivo que quedan fuera, solo para B3. En total son 636 notas: unas 2-4 h.
- **Criterio:** qwen3 se descarta si el límite superior de su IC del 95 % queda por debajo de B1 < 0,9328 o de B2 < 0,9294 (minilm + 0,02). Los umbrales se calculan con el modelo elegido.
- **Si no se descarta:** se termina la pasada completa (`leer --pasada 3`), que aprovecha lo ya leído.
- **Orden:** `criterios` debe correr antes de `historico`, porque la muestra depende de la lista de notas.

## Resultado de la pasada 3 (5-nov): qwen3 se descarta y B queda cerrada
La muestra tomó 167 min, sin errores y con 0 tramos truncados. No hace falta terminar la pasada completa.

| Modelo | B1 | B2 | B3 | B4 citado | B5 exacto / ±1 | B6 repetido |
|---|---|---|---|---|---|---|
| qwen3 (muestra) | 0,910 (0,886-0,931) | 0,901 (0,876-0,925) | pasa | 5/9 | 0,05 / 0,20 | 0,19 |

Los dos límites superiores quedan por debajo de sus umbrales: 0,9307 frente a 0,9328 en B1 y 0,9247 frente a 0,9294 en B2. Basta con uno para descartarlo.

- **Modelo elegido: minilm**, con B1 0,913 y B2 0,909. Según la regla, ningún otro candidato lo reemplaza y es de los más rápidos en A1.
- **Margen:** el de B1 es de solo 0,002. El descarte se apoya en el criterio fijado antes de correr la muestra y en que B2 también lo cumple.
- **Límite de la muestra:** B4 de qwen3 solo tiene 9 notas de las 67 con comunicado citado, así que no permite compararlo con los demás. El descarte no lo usa.

## Definición de C (aprobada el 6-nov): reemplaza a la del plan del 2-nov
**Por qué cambia.** Medido antes de escribir el código:
- Cada nota tiene un solo comunicado vigente, de 11 a 14 párrafos. "Los 10 mejores" casi no filtra.
- B4 deja de medir al modelo: con el filtro de fecha da 59/67 en cuerpos y en texto corto, porque el comunicado citado es el vigente en esas 59 notas.
- La app recibe texto corto, y ahí E4 no llega al mínimo de 0,90 con ningún modelo medido:

| Modelo | E4 corto, vigentes | E3 corto, vigentes |
|---|---|---|
| minilm | 0,865 (0,845-0,883) | 0,870 |
| mpnet | 0,873 (0,854-0,887) | 0,883 |
| beto-es | 0,879 (0,862-0,893) | 0,877 |
| e5-small | 0,795 (0,772-0,818) | 0,909 |

**Alternativas:** el filtro por fecha ya es parte del semáforo; el filtro por `tipo` y la diversidad de párrafos se deciden en el semáforo si hay referencia. ColBERT se descarta porque añade complejidad sin una ventaja clara para unos 14 párrafos, y un LLM porque es de pago y lento. mDeBERTa no entra: detecta contradicción, no tema, y tiene un solo intento reservado para el índice.

**Prueba.** Titular y resumen frente a los párrafos vigentes del ENFEN, sin leer cuerpos. Cada candidato puntúa todos los párrafos vigentes, así que en el semáforo reemplaza al bi-encoder. Candidatos: mmarco-mMiniLMv2, bge-reranker-v2-m3, mxbai-rerank-base-v2 y Qwen3-Reranker-0.6B, con la instrucción por defecto de cada uno.

```bash
python -m radar.nlp.reranker tiempo
python -m radar.nlp.reranker puntuar minilm mmarco
python -m radar.nlp.reranker criterios
```

| Paso | Qué se mide | Criterio |
|---|---|---|
| 1. Tiempo | 14 pares reales, en float32 | Hasta 2 s y 6 GB; si no cumple, no sigue |
| 2. Decide | E4 en texto corto, con la lista de notas de B | minilm + 0,02 o más, con el límite inferior del IC sobre el superior de minilm |
| 3. Debe pasar | E3 en texto corto | 0,80 o más |
| 4. Confirma | Notas sobre El Niño que no estaban en B, frente al mismo control negativo | Debe superar a minilm |

Si dos pasan, gana el más rápido. Si ninguno pasa, el semáforo sigue con minilm y se declara que su E4 en texto corto no llega a 0,90. El tipo de párrafo elegido es informativo (se toma de la variante sin términos en las notas sobre El Niño).

**Límites:** el paso 4 reutiliza el control negativo, porque no hay otro. Estas pruebas miden el tema, no si se eligió el párrafo correcto; eso queda para E.

## Resultado de C (6-nov): ningún reranker pasa y el semáforo sigue con minilm
| Candidato | Paso 1: consulta / memoria | E4 corto | E3 corto | Notas nuevas |
|---|---|---|---|---|
| mmarco-mMiniLMv2 | 0,44 s / 1,4 GB | 0,418 (0,388-0,448) | 0,678 | 0,483 |
| bge-reranker-v2-m3 | 6,19 s / 3,15 GB | no sigue | | |
| mxbai-rerank-base-v2 | 12,23 s / 2,79 GB | no sigue | | |
| Qwen3-Reranker-0.6B | 14,00 s / 3,23 GB | no sigue | | |
| **minilm (base)** | | **0,860 (0,841-0,878)** | **0,864** | **0,903** |

Se puntuaron 2.936 notas (146 nuevas), sin errores y sin pares truncados. El control del instrumento pasa por poco: 0,8602 frente a 0,8651 ± 0,005. La diferencia con la medición previa viene de unir titular y resumen con un salto de línea, como la consulta de la prueba A.

- **El AUC bajo no es un error de la prueba.** El signo es correcto (par relevante 9,1; irrelevante -7,2), un párrafo consigo mismo da 10,6 y una muestra de 100 + 100 notas reproduce el CSV exactamente. En esa muestra, con términos, el AUC es 0,53.
- **Lectura:** el máximo sobre los párrafos vigentes es alto también en notas de otros temas (mediana 3,25, frente a 1,38 en las de El Niño). No sirve como medida de cercanía al tema. La causa exacta no se investigó.
- **Límite:** los otros tres candidatos quedaron fuera por tiempo, así que no se sabe cómo separan los temas.
- **Declarado:** el E4 de minilm en texto corto (0,860) no llega a 0,90. Hay que considerarlo al calibrar el semáforo en la semana 3.
- **Informativo, tipo de párrafo elegido:** minilm elige `recomendacion` en el 48 % de las notas sobre El Niño; mmarco, `pronostico` en el 44 %. No hay referencia para saber cuál acierta.
- **Sigue abierto:** el reranker en la recuperación del agente (P2) se mide en E.

## Definición de D (aprobada el 6-nov): reemplaza a la del plan del 2-nov
**Por qué cambia.** Medido antes de escribir el código, en texto corto y con párrafos vigentes:

| Medición | E4 | E3 | Notas nuevas |
|---|---|---|---|
| minilm (base) | 0,860 (0,841-0,878) | 0,864 | 0,903 |
| BM25 | 0,732 (0,708-0,755) | 0,861 | 0,887 |
| BM25 dividido por largo de la consulta | 0,770 (0,747-0,789) | | 0,912 |
| Fusión de rangos del plan (k = 60) | 0,654 (0,625-0,678) | | 0,720 |

La fusión de rangos da solo 26 valores distintos en 2.777 notas: usa posiciones, no cuánto se parece el texto, y por eso no sirve para comparar notas entre sí. Se puede medir en E, donde solo hay que ordenar párrafos. El plan original tampoco aplica porque B no guardó los puntajes por párrafo y la app recibe texto corto. BM25 y minilm no dicen lo mismo (Spearman 0,54).

**Alternativas descartadas:** pesos aprendidos (se ajustarían con las etiquetas que los evalúan), SPLADE (otro modelo pesado) y TF-IDF en lugar de BM25 (ya probado: E4 de 0,80 en cuerpos).

**Regla única, sin ajustes después de medir:**
1. Para cada párrafo vigente, el coseno de minilm y BM25 dividido por el largo de la consulta (k1 = 1,5; b = 0,75; IDF de los 264 párrafos del ENFEN).
2. Cada puntaje se normaliza con la media y la desviación de sus máximos en el estrato `cercano`, que no entra en E4 ni en E3.
3. Se suman con el mismo peso; el puntaje de la nota es el máximo entre los párrafos.

```bash
python -m radar.nlp.hibrido puntuar
python -m radar.nlp.hibrido tiempo
python -m radar.nlp.hibrido criterios
```

| Paso | Qué se mide | Criterio |
|---|---|---|
| 1. Decide | E4 en texto corto | minilm + 0,02 o más, con límite inferior del IC sobre el superior de minilm (0,880 y 0,878) |
| 2. Debe pasar | E3 en texto corto | 0,80 o más |
| 3. Confirma | Las 146 notas nuevas | Debe superar a minilm (0,903) |
| 4. Debe pasar | Tiempo y memoria en la consulta | Hasta 2 s y 6 GB |

Si no pasa, el semáforo sigue solo con minilm y el híbrido queda para medirse en E.

**Límites:** BM25 solo ya se vio, y por eso se eligió dividirlo por largo; la combinación no se midió antes de fijar los criterios. La prueba mide el tema, no si se eligió el párrafo correcto. El corpus offline (P3) sigue con minilm sobre cuerpos.

