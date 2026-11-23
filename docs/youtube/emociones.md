# Emociones de los comentarios de YouTube: definición (borrador 3, aprobada el 16-nov-2026)

Responde lo que dejó abierto [nlp/viabilidad-modelos.md](../nlp/viabilidad-modelos.md): pysentimiento casi no veía emociones en los titulares (97 de 100 salían "others"), por el cambio de dominio de tuits a titulares. Los comentarios se parecen más a los tuits del entrenamiento. Los criterios se fijan aquí antes de correr ningún modelo sobre los comentarios.

**Lo único que se miró antes de fijar los criterios** fueron conteos de los 9.032 comentarios del día 1, nunca la salida de un modelo (sección 2).

**Tres revisiones.**
- **La 1.ª** era un diseño simple.
- **La 2.ª** agregó los casos de datos: respuestas, idioma, spam, autores, largos, emojis y religiosos.
- **La 3.ª** revisó cómo se usarán las emociones y qué sesga las métricas:
  - el orden de descarga (caso 22);
  - la fuga hacia el modelo de engagement (caso 23);
  - la paradoja de κ (caso 24);
  - el alcance de M2 (caso 25);
  - el zero-shot en dos pasos;
  - el dueño del canal, el spam y los marcadores de la limpieza (casos 19 a 21).

## 1. Mapa de enfoques

| Enfoque | Qué aporta | Problema | Decisión |
|---------|-----------|----------|----------|
| A. pysentimiento (`robertuito-emotion-analysis`, tuits en español) | Seis emociones más "others", rápido en CPU | Hay que probar que sirve en este dominio | **Instrumento** |
| B. Zero-shot con NLI (mDeBERTa, ya en caché) | Clasificador independiente: el acuerdo que pide el README (fila 5) | No calibrado, y el zero-shot no entiende bien los emojis | **Referencia 1** (κ, como P2) |
| C. Emojis puestos por el autor | Una etiqueta externa, puesta por quien escribió, sin etiquetado nuestro (supervisión distante) | Solo cubre los comentarios con emojis; la risa (😂) puede ser burla | **Referencia 2** |
| D. Léxico de emociones (NRC traducido) | Independiente | Débil con negaciones e ironía, y hay que descargar otra fuente | Descartado |
| E. LLM como clasificador | Probablemente mejor | Habría que declararlo, cuesta y no está en el stack | Descartado |
| F. Ajustar un modelo propio | — | Requiere etiquetas: prohibido (cero etiquetado manual) | Descartado |

## 2. Casos que hay que tratar (con sus conteos del día 1)

| # | Caso | Tamaño | Cómo se trata |
|---|------|--------|---------------|
| 1 | **Respuestas.** Reaccionan a otro comentarista, no al video; 159 empiezan con una @mención | 2.281 (25 %) | La unidad principal es el **comentario principal**. Las respuestas se reportan aparte (informativo) y no entran en M1 a M3 |
| 2 | **Vacíos o solo emojis** | 187 | Fuera de M1 y M3; tampoco sirven para M2, porque al quitar el emoji no queda texto |
| 3 | **Muy cortos** (menos de 3 palabras: "gracias", "xd") | ~740 | Fuera de M1 y M3; se reportan aparte |
| 4 | **Otro idioma** (robertuito es solo para español) | ~47 en inglés y ~280 dudosos | Solo español, con una regla de palabras vacías (español frente a inglés), fijada como constante. Se reporta cuántos salen |
| 5 | **Repetidos y spam** ("gracias", "xd", el mismo texto pegado varias veces) | 451 textos repetidos | Se quita el mismo texto del mismo autor en el mismo video. Textos iguales de autores distintos se quedan: son reacciones reales |
| 6 | **Autores muy activos**, que pesan más que el resto | 32 autores con 10 o más | En las medidas, máximo 3 comentarios por autor y video; en la muestra de M3, 1 por autor |
| 7 | **Videos con muchos comentarios** | El mayor tiene el 2 % y los 10 primeros, el 17 % (crecerá en el corte, con hasta 1.000 por video) | La muestra de M3 toma máximo 5 por video. M1 se reporta por comentario y como mediana por video |
| 8 | **Comentarios largos** (robertuito lee hasta 128 tokens) | 191 con más de 100 palabras | Se parten en tramos de 128 tokens y se promedian las probabilidades, como en P1 de las notas. **M0:** 0 truncados |
| 9 | **Emojis dentro del texto.** pysentimiento los traduce a palabras; el zero-shot no los entiende | 1.646 con algún emoji | M3 compara los dos modelos **sin emojis** (se quitan en ambos), para comparar lo mismo. En el uso normal, pysentimiento lee el texto completo |
| 10 | **Emojis ambiguos** | 350 con risa (😂); el llanto (😭) aparece 19 veces, ninguna junto a "jaja" | 😂 va con alegría (límite declarado: si es burla, baja M2). Quedan fuera ❤️, 🙏, 👍 y 🔥. Solo cuentan los comentarios con emojis de un solo grupo |
| 11 | **M2 puede evaluarse con muy pocos casos** (solo cuenta cuando el modelo asigna una emoción) | — | M2 exige **al menos 100 comentarios evaluables** en los grupos con 30 o más. Con menos, M2 **no pasa** por falta de datos. Se reporta también cuántos comentarios con emoji salen "others" |
| 12 | **Religiosos** ("Dios nos proteja", oraciones) | 732 (8 %) | No se quitan: son una reacción real. Se reporta su distribución aparte para ver si caen en "others" o en miedo y tristeza |
| 13 | **Fuera de tema** (política, burlas a autoridades) | Sin conteo posible sin etiquetar | No se filtran: se mide la emoción del público, no solo sobre el fenómeno. Se declara. Informativo: la emoción de los comentarios que mencionan El Niño o las lluvias frente a los que no |
| 14 | **Ironía y sarcasmo** | — | Límite declarado de cualquier modelo; afecta a todos los criterios por igual |
| 15 | **Fecha del comentario y fecha del video.** Muchos comentarios se escriben días después | — | Para el estudio de eventos cuenta la fecha del comentario; para el modelo de engagement, el video. Se guardan ambas |
| 16 | **Videos con pocos comentarios** | — | La proporción de emociones por video solo se calcula con **20 o más** comentarios principales en español; si hay menos, queda como dato faltante |
| 17 | **Títulos de los videos** (el README también pide sus emociones) | 1.225 | M1 sobre títulos, solo informativo: se parecen a los titulares, donde no funcionó |
| 18 | **Cuándo se decide** | — | Con los comentarios disponibles antes del corte (días 1 y 2). En el corte se aplica sin volver a decidir; si hay muchos más comentarios, M1 se repite como informativo |
| 19 | **Comentarios del dueño del canal** (promoción, respuestas del medio) | 35 | Fuera de todo: no son público. Se reconocen comparando seudónimos, porque el del autor y el del canal usan la misma sal |
| 20 | **Promoción o datos de contacto** (comentarios con `[enlace]`, `[telefono]` o `[correo]`) | 12 | Fuera de M1 a M3: suelen ser spam o venta |
| 21 | **Marcadores de la limpieza** (`[mencion]`, `[enlace]`) que robertuito no conoce | — | Antes de pasar el texto al modelo se cambian por `@usuario` y `url`, las formas con que se entrenó el modelo |
| 22 | **Orden de descarga.** `order=time` trae primero los comentarios **más recientes** | En 30 de los 114 videos, la página 1 se llenó: se tienen sus últimos 100, no la primera reacción. La demora mediana es 1 día (38 % el mismo día; p90, 25 días) | En la viabilidad se declara. En el corte se bajan hasta 10 páginas; en los videos con más de 1.000 se pierden los más antiguos (se declaran cuántos). Para la "reacción al video" (estudio de eventos) cuentan solo los comentarios de los primeros 7 días, y se reporta en cuántos videos esa ventana está completa |
| 23 | **Uso en el modelo de engagement: fuga y sesgo de selección.** La tasa de engagement incluye los comentarios, y solo los videos con 20 o más comentarios tendrían emociones | — | Las emociones de los comentarios **no entran en el modelo principal** (que cubre todos los videos). Si pasan M0 a M3, entran solo en un modelo secundario restringido a los videos con 20 o más comentarios, como variables de la audiencia, y se declara que esa muestra está seleccionada por el propio engagement |
| 24 | **κ con "others" mayoritario** (paradoja de la prevalencia: κ baja aunque el acuerdo sea alto si una clase domina) | — | M3 se calcula con las 7 clases, como pide el README. Además se reporta, solo como informativo, el κ binario (emoción frente a "others") y el κ entre las 6 emociones cuando ambos modelos asignan una. Así se ve si la falla está en detectar si hay emoción o en cuál es |
| 25 | **M2 solo mira cuando el modelo asigna una emoción** (mide si acierta cuál, no si la detecta) | — | Es a propósito: sin el emoji, muchos textos quedan neutros de verdad ("Ya llegó el Niño 😱" → "Ya llegó el Niño"), y castigar el "others" ahí castigaría al modelo por algo que no puede ver. La detección la mide M1. Se reporta como informativo cuántos comentarios con emoji salen "others" frente a los que no tienen emoji |

## 3. Criterios (fijados antes de correr)

**Población de las medidas:**
- Comentarios principales en español, con 3 palabras o más.
- Sin repetidos del mismo autor, con máximo 3 por autor y video.
- Sin los del dueño del canal ni los que traen enlaces o datos de contacto.

| Id | Criterio | Umbral |
|----|----------|--------|
| M0 | Comentarios truncados por robertuito (tramos de 128 tokens) | 0 |
| M1 | Proporción con una emoción distinta de "others" (pysentimiento) | ≥ 30 % (en los titulares era el 3 %) |
| M2 | κ de Cohen entre pysentimiento (sobre el texto **sin emojis**) y el grupo del emoji, cuando el modelo asigna una emoción; solo grupos con ≥ 30 comentarios | ≥ 0,40, con ≥ 100 evaluables |
| M3 | κ de Cohen entre pysentimiento y el zero-shot, los dos sobre el texto sin emojis, en 400 comentarios al azar (semilla `emociones-yt-16nov`, máximo 5 por video y 1 por autor; 7 clases) | ≥ 0,40 |

**Zero-shot, en dos pasos.** Una etiqueta "ninguna emoción" compitiendo con las emociones en un solo paso no está calibrada en NLI, y decidiría casi sola el κ.
1. **¿Hay emoción?** Se pregunta "Este comentario expresa una emoción." Si la probabilidad de implicación es menor que 0,5, el comentario es "others". El 0,5 es el corte estándar de NLI y no se ajusta con los datos.
2. **¿Cuál?** Si hay emoción, se toma la de mayor probabilidad entre "Este comentario expresa {alegría | tristeza | enojo | miedo | sorpresa | asco}."

Con 400 comentarios, el IC del 95 % de κ es de unos ±0,07.

**Grupos de emojis** (constantes al inicio del módulo):

| Grupo | Emojis |
|---|---|
| alegría | 😂🤣😄😁😃😆😊🥰😍 |
| tristeza | 😢😭😞😔💔🥺 |
| enojo | 😡🤬😠👿 |
| miedo | 😱😨😰😧 |
| sorpresa | 😮😲🤯😯 |
| asco | 🤢🤮 |

**Informativos, sin umbral:**
- Las respuestas, los comentarios cortos y los títulos.
- La distribución por tipo de canal, por mes y por largo.
- La matriz de confusión con los emojis.
- El κ entre el zero-shot y los emojis, para saber cuál de las dos referencias es más confiable si M3 falla.
- La descomposición de M3: κ binario y κ entre las 6 emociones (caso 24).
- La proporción de "others" en los comentarios con emoji frente a los que no tienen (caso 25).
- La ventana de 7 días: en cuántos videos está completa (caso 22).
- Los comentarios religiosos y los que mencionan El Niño, cada uno por separado.
- La polaridad de los comentarios.

**Decisión:**
- **Si pasan M0 a M3:** las emociones entran en la analítica y en el estudio de eventos (casos 15 y 22), y en el modelo secundario de engagement (caso 23), nunca en el principal.
- **Si pasan M0 y M1, pero no M2 o M3:** las emociones quedan **solo descriptivas**, como la polaridad de las notas, y no entran al modelo.
- **Si M1 no pasa:** no se usan emociones; la polaridad se reporta como descriptiva.

## 4. Costo y forma
- pysentimiento sobre unos 7.000 comentarios útiles: unos minutos en CPU.
- Zero-shot sobre 400 × 7 hipótesis: unos 5 a 10 min.
- Modelos con `dtype=float32`, en memoria.
- Se guardan solo las probabilidades por comentario, con su seudónimo, en `data/processed/youtube/AAAA-MM-DD_emociones.csv`, que vence a los 30 días.
- `python -m radar.youtube.emociones`, con avance y guardado por lote, para retomar si se corta.
- Las pruebas son sintéticas.

## 5. Resultados preliminares (16-nov-2026, comentarios del día 1)

`python -m radar.youtube.emociones`: 9.339 textos, de los cuales 6.027 forman la población; 40 min en CPU.

| Id | Resultado | Umbral | |
|----|-----------|--------|---|
| M0 | 0 truncados (199 comentarios en más de un tramo) | 0 | **Pasa** (tras corregir el código) |
| M1 | 42,8 % con emoción; mediana por video 0,424 (102 videos con ≥ 20) | ≥ 30 % | **Pasa** |
| M2 | κ 0,161 con 169 evaluables (grupos alegría, tristeza y sorpresa) | ≥ 0,40 | **No pasa** |
| M3 | κ 0,108 en 400 comentarios | ≥ 0,40 | **No pasa** |

**Decisión (preliminar; caso 18): las emociones quedan solo descriptivas, como la polaridad de las notas. No entran en el estudio de eventos ni en el modelo de engagement.** Se repite con los comentarios del día 2 sin cambiar nada. Si el resultado se invirtiera, se reportaría.

**Corrección del código antes de medir (no cambia criterios):** la primera corrida truncó 27 tramos. El tokenizador de robertuito da menos tokens a las palabras sueltas que a la frase, sobre todo en los emojis traducidos a palabras. Por eso el conteo por palabras de `embeddings.tramos` se quedaba corto. Ahora cada tramo se mide entero y se parte por la mitad hasta que cabe (`partir_hasta_caber`). M1 a M3 casi no cambiaron (M1 pasó de 0,424 a 0,428).

**Por qué fallan M2 y M3 (informativos):**
- **😂 casi nunca es alegría:** de 86 comentarios con risa, pysentimiento ve enojo en 52 y alegría en 16. La risa acompaña burlas a las autoridades o a los medios, el límite declarado en el caso 10. Tristeza (😢😭) es el grupo que mejor coincide: 26 de 53.
- **El paso 1 del zero-shot ve emoción en casi todo:** solo el 2 % sale "others", frente al 57 % de pysentimiento. El κ binario es 0,005. Entre las 6 emociones, cuando ambos asignan una, el κ es 0,256: también bajo. Contra los emojis, el zero-shot tampoco va mejor (κ 0,10 con 39 casos). No hay una referencia que respalde a ninguno de los dos.
- **"Others" es casi igual con y sin emoji** (0,572 frente a 0,581): el modelo no detecta más emoción donde el autor sí la marcó.

**Lo descriptivo que queda:**
- El enojo domina (27 % de la población), seguido de tristeza (7 %) y alegría (6 %). El miedo es casi nulo (0,8 %).
- Los comentarios religiosos tienen más alegría y tristeza y menos enojo.
- Los que mencionan El Niño o las lluvias tienen más tristeza (9,9 % frente a 6,3 %).
- La proporción de comentarios con emoción sube con el largo: 30 % con 3 a 9 palabras y 64 % con 30 o más.
- En los títulos la proporción con emoción es 6,9 %, como en los titulares.
- Polaridad: 60 % negativa, 28 % neutral y 12 % positiva.

**Otros datos:**
- La ventana de 7 días está completa en 84 de los 114 videos.
- De la población se descartaron 918 comentarios, 567 de ellos por "idioma dudoso": sin palabras vacías ni tildes. Es la regla fijada y se declara.

## 6. Decisión con los días 1 y 2 (17-nov-2026)

Se repitió la prueba sin cambiar nada, con 11.347 textos (7.163 en la población); retomó lo ya hecho y tardó 17 min.

| Id | Resultado | Umbral | |
|----|-----------|--------|---|
| M0 | 0 truncados | 0 | **Pasa** |
| M1 | 43,4 % con emoción; mediana por video 0,437 (122 videos) | ≥ 30 % | **Pasa** |
| M2 | κ 0,161 con 195 evaluables | ≥ 0,40 | **No pasa** |
| M3 | κ 0,131 en 400 comentarios | ≥ 0,40 | **No pasa** |

**Decisión final (caso 18): las emociones de los comentarios quedan solo descriptivas.** No entran al estudio de eventos ni a ningún modelo de engagement. En el corte se aplican tal cual, y M1 a M3 se repiten solo como informativos.

Los informativos confirman lo de la sección 5:
- 😂 sale como enojo en 59 de 99 casos.
- El zero-shot ve emoción en el 98 % de los comentarios (κ binario 0,002). Entre las 6 emociones, el κ es 0,306.
- El enojo domina (27,6 %).
- Los comentarios religiosos tienen más alegría (15 %) y tristeza (12 %).
- La ventana de 7 días está completa en 103 de los 136 videos.


## 7. Corte del 22-nov (informativo)

Se aplicó tal cual a los comentarios del corte: 22.610 textos (15.204 en la población); retomó los 11.341 ya hechos y tardó 29,5 min. La decisión del 17-nov no cambia: M1 a M3 son solo informativos.

| Id | Resultado | Umbral | |
|----|-----------|--------|---|
| M0 | 0 truncados (449 comentarios en más de un tramo) | 0 | Pasa |
| M1 | 41,6 % con emoción; mediana por video 0,44 (146 videos) | ≥ 30 % | Pasa |
| M2 | κ 0,232 con 456 evaluables | ≥ 0,40 | No pasa |
| M3 | κ 0,099 en 400 comentarios | ≥ 0,40 | No pasa |

- El enojo sigue dominando (24,4 %), seguido de alegría (7,6 %) y tristeza (7,0 %); la polaridad es 58 % negativa.
- 😂 (grupo alegría) sale como enojo en 120 de 219 casos.
- El zero-shot ve emoción en el 99 % de los comentarios (κ binario 0,005); entre las 6 emociones, κ 0,274.
- Los comentarios religiosos tienen más alegría (15,5 %) y tristeza (13,1 %).
- La ventana de 7 días está completa en 821 de 903 videos (46 con menos de 7 días).
