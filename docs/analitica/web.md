# Analítica web (README, punto 10; pregunta 5)

**Estado:** propuesta del 22-nov, con dos revisiones (la segunda, un análisis crítico con datos en la sección 8), pendiente de aprobación. Nada se construye sin la orden del usuario. Los criterios se fijan aquí, antes de ver los resultados. Los tamaños de muestra de la sección 2 se contaron sin mirar ninguna relación.

## 1. Qué responde
La pregunta 5 del README tiene dos partes, y el punto 10 le suma dos piezas de apoyo:

| Parte | Pregunta | Datos |
|---|---|---|
| A | ¿El contenido más alejado de lo oficial tiene más engagement? | YouTube, corte del 22-nov |
| B | ¿Cómo varía el interés del público por departamento alrededor de cada comunicado? | Trends, exportaciones del 17 y 22-nov |
| C | Indicadores de los medios: volumen, secciones y tiempo de reacción tras un comunicado | `notas.csv` |
| D | Registro de uso de la app (web usage mining): sesiones, embudo y tiempo por pantalla | `POST /api/eventos` |

**Cómo se lee la pregunta A.** La validación de la cercanía mostró que separa por tema, no por acuerdo ([modelos/engagement.md](../modelos/engagement.md), sección 8, V3 y V5). Por eso "más alejado de lo oficial" se lee como "habla menos de lo que trata el ENFEN". No significa "lo contradice". Las contradicciones con datos (`color_reglas` rojo) son solo 20 videos.

## 2. Datos disponibles (contados el 22-nov)
- **YouTube:** 1.609 videos en `2026-11-22_engagement-variables.csv`.
  - Por tipo de canal: 1.168 de otros, 390 de medios y 51 oficiales.
  - 1.604 tienen cercanía (`coseno`).
  - Canales con 3 videos o más: **84, con 1.018 videos**. Son 71 de otros, 8 medios y 5 oficiales. Por partición son 51 canales (635 videos) en el entrenamiento y 40 (318) en la prueba.
  - Por `color_reglas`: 1.330 sin afirmaciones, 225 verdes, 34 amarillos y 20 rojos.
  - Sin los oficiales, los canales con ≥ 3 videos con cercanía son **79, con 968 videos**: 48 canales (602 videos) en el entrenamiento y 38 (308) en la prueba.
  - Por la búsqueda que los trajo: 686 videos solo por fecha, 504 por fecha y por relevancia, y **419 solo por relevancia** (26 %).
- **Trends:** 46 semanas completas por departamento.
  - Con dato en al menos la mitad de las semanas: Piura (80 %), Lambayeque (78 %) y La Libertad (85 %).
  - Tumbes solo tiene dato en el 15 % de las semanas y usa el promedio de las dos exportaciones (G2).
  - La consulta nacional por región está en `data/raw/trends/nacional/`.
- **Medios:**
  - 2.785 notas sobre El Niño de 4 medios, repartidas en 23 secciones; 11 tienen la fecha dudosa.
  - Solo **71** citan un comunicado (columna `comunicados`). Son pocas, y se declara.
- **Uso de la app:** todavía no hay. El uso real llega con la presentación (1-dic), después del congelamiento.

## 3. Mapa de enfoques

### A. Engagement frente a la cercanía
| Enfoque | Qué controla | Decisión |
|---|---|---|
| Spearman con todos los videos juntos | Nada: mezcla tipos y canales; los oficiales están cerca y tienen otra audiencia | Descartado como respuesta; se muestra en la dispersión |
| Spearman dentro de cada tipo, ponderado (como M1) | El tipo de canal | Informativo (W3) |
| Spearman parcial con los suscriptores y la edad | Lo que entra como control, con forma lineal | Descartado: lo absorbe el siguiente |
| **Dentro del canal:** ¿los videos más alejados de un mismo canal tienen más engagement que sus videos cercanos? | Todo lo fijo del canal: audiencia, suscriptores, país, estilo | **Elegido** (W2) |
| Dependencia parcial del boosting (M5) | Las demás variables del modelo | Descartado: M5 midió estabilidad y no el signo, y la prueba ya se usó |
| Terciles de cercanía con la mediana de la tasa | Nada; es para leer | Informativo (W4), para la pantalla F |
| Semáforo de reglas (rojo y amarillo frente a verde) | Nada | Informativo (W5): 54 videos |
| Causal (emparejamiento, variables instrumentales) | — | Descartado: no hay instrumento ni diseño |
| Repetir solo con los videos que salieron en búsquedas por fecha | El sesgo de selección: el orden por relevancia favorece a los videos populares | **Elegido como condición de W2** |

**Variable del engagement:** el objetivo del modelo, es decir, el logit de la tasa suavizada con la beta-binomial. Dentro del canal da casi el mismo orden que la tasa cruda y no exagera los videos con pocas vistas. La edad del video no se controla, porque en el entrenamiento la tasa no depende de ella (ρ −0,01; modelo, sección 2).

### B. Trends por departamento
| Enfoque | Decisión |
|---|---|
| Semana del comunicado frente al promedio de las 3 semanas anteriores, contando cuántos suben (como el estudio de eventos) | **Elegido, descriptivo** (W7) |
| Estudio de eventos con regresión o series interrumpidas | Descartado: con 18 eventos no pasó tamaño ni potencia en las notas ([eventos.md](eventos.md)) |
| Correlación cruzada con el volumen semanal de notas sobre El Niño (¿el interés sigue a la cobertura?) | **Elegido** (W8), con diferencias semanales y un nulo que conserva la autocorrelación |
| Comparar niveles entre departamentos con la consulta nacional por región | **Elegido, descriptivo** (sin criterio; ya medido: Piura 100, Tumbes 65, La Libertad 56, Lambayeque 45) |
| Parecido entre las formas de las series de los departamentos | Informativo dentro de W8 |
| Modelo que prediga Trends con las noticias | Descartado: era la alternativa si YouTube no alcanzaba (pendientes, punto 1) |

**Con qué notas se compara.** La serie principal es la de todas las notas sobre El Niño (2.785), porque la cobertura nacional también llega a cada departamento y 1.707 notas son nacionales. Las notas que nombran al propio departamento (`departamentos` de `regiones.csv`) son pocas: Piura 386, Tumbes 135, Lambayeque 78 y La Libertad 71, menos de 2 por semana en los dos últimos. Por eso van como informativas.

### C. Indicadores de los medios
| Indicador | Decisión |
|---|---|
| Volumen mensual de notas sobre El Niño por medio | Elegido |
| Mezcla de secciones por medio (las 5 primeras y "otras") | Elegido |
| Tiempo de reacción: días desde el comunicado hasta la primera nota del medio que lo cita | Elegido, con control de calidad (W9) y declarando que son 71 notas |
| Tiempo hasta la primera nota sobre El Niño tras el comunicado | Descartado: desde mitad de año hay notas sobre El Niño todos los días, así que mediría la frecuencia y no la reacción |
| Proporción que cita a lo oficial | Ya está en la pantalla E (red de enlaces); no se repite |

Los medios van en orden alfabético y nunca se ordenan por cercanía (P12 de la app).

### D. Registro de uso
| Enfoque | Decisión |
|---|---|
| Sesiones, embudo (vista → verificar → ver por qué o qué hacer → compartir) y tiempo por pantalla, con la definición de la app | **Elegido** |
| Secuencias frecuentes o cadenas de Markov entre pantallas | Descartado: no habrá sesiones suficientes |
| Analítica de terceros (Google Analytics y similares) | Descartado: la app no usa cookies ni manda datos fuera (sección 5 de la app) |

## 4. Definición

### A. Engagement frente a la cercanía
1. **Muestra:** los videos de medios y de otros en `engagement-variables.csv`, con cercanía, en los canales que tienen 3 videos o más. Los oficiales quedan fuera, como en M1: son 5 canales, su audiencia es otra, y en 8 de sus meses hay menos de 5 videos, así que no se les puede quitar el mes.
2. **Quitar el tiempo antes de comparar:** desde septiembre la tasa de los medios cae a la mitad, y la cobertura de El Niño cambia de tema a lo largo del año. Si un canal publica más lejos de lo oficial al final del año, la caída de la tasa daría una correlación falsa. Por eso, al objetivo y a la cercanía se les resta la mediana de su tipo de canal y mes, y la correlación se calcula con esos residuos. Como informativo se da también sin quitar el mes.
   - **Formato y largo del texto:** la cercanía sube con el largo del texto (ρ 0,16, medido sin el engagement), y los Shorts (hasta 180 s, 46 % de los videos) suelen tener descripciones cortas. Si los Shorts tienen otra tasa, la relación saldría del formato y no del contenido. Por eso, dentro del canal se descuentan también si el video es Short y el logaritmo de las palabras del texto.
3. **Correlación dentro del canal:**
   - En cada canal, los dos residuos se pasan a rangos, que se centran y se dividen por el número de videos del canal.
   - El Short y el logaritmo de las palabras se pasan a rangos centrados de la misma forma, y se quitan de los dos residuos con una regresión lineal.
   - Con lo que queda de todos los canales juntos se calcula Pearson. Es un Spearman parcial estratificado por canal, y cada video pesa lo mismo.
   - El signo se lee al revés: ρ < 0 quiere decir que **lo más alejado tiene más engagement**.
4. **Incertidumbre:** IC 95 % con un bootstrap por canal de 1.000 réplicas (semilla del proyecto). Se sortean canales y entran todos sus videos.
5. **Por período:** lo mismo, por separado en el entrenamiento (enero a agosto) y en la prueba (septiembre al corte), porque desde septiembre cambia el régimen de la tasa de los medios.
6. **Respuesta a la pregunta A, con la regla fijada aquí:**
   - **"Sí" o "no"** (según el signo) solo si se cumplen las tres condiciones: el IC excluye 0, el signo es el mismo en los dos períodos y se repite con los videos que salieron en búsquedas por fecha.
   - En cualquier otro caso, **"no concluyente"**. Esa es la frase que va en la app.
   - Exigir el mismo signo en la prueba (38 canales, 308 videos) es conservador: con poca muestra es más fácil quedar en "no concluyente" que afirmar algo falso. Se prefiere así.
7. **KPIs:** por tipo de canal y mes, el número de videos y las medianas de vistas, likes, comentarios y tasa. Son descriptivos.
8. **Uso de la prueba:** la partición de prueba del modelo se usa aquí solo para describir; no se elige ni se ajusta ningún modelo con ella.

### B. Trends por departamento
1. **Series:** `radar.trends.cargar.serie_final`, que ya promedia Tumbes.
2. **Por comunicado:**
   - De los 20 comunicados de 2026, 14 salen un viernes. En las semanas de domingo a sábado, la semana del comunicado solo tiene 2 días después de él. Por eso se compara el promedio de **la semana del comunicado y la siguiente** con el promedio de las 3 semanas anteriores a la del comunicado.
   - Entran los comunicados cuya semana siguiente está completa (el N.° 20 queda fuera) y que tienen sus 3 semanas anteriores dentro del período.
   - Se cuenta en cuántos comunicados sube, por departamento.
   - Es descriptivo y no lleva valor p. Se declara que las 3 semanas anteriores pueden incluir otro comunicado, porque salen cada 2 a 4 semanas. Eso sube la base y hace más difícil que "suba": el conteo es conservador.
3. **Correlación cruzada:**
   - Se compara la diferencia semanal de Trends de cada departamento con la diferencia semanal de todas las notas sobre El Niño, en las mismas semanas de domingo a sábado en hora de Lima. Como informativo se repite con las notas que nombran a ese departamento.
   - Se usan las diferencias porque las dos series crecen todo el año, y sin quitar la tendencia cualquier par sale correlacionado (eventos, medición previa).
   - Las diferencias son de log(1 + x). Las notas pasan de 20 en enero a 652 en octubre, así que con diferencias crudas las últimas semanas dominarían la correlación.
   - Se prueban los desfases de −2 a +2 semanas. Un desfase positivo quiere decir que Trends va detrás de las notas.
   - **Nulo:** 1.000 series sustitutas de Trends con las fases al azar y la distribución original (IAAFT; Schreiber y Schmitz, 1996), que conservan su autocorrelación y sus muchos ceros. En cada una se toma el máximo de |r| en los 5 desfases, así el nulo ya cuenta que se probaron 5. Un desplazamiento circular solo daría unos 40 valores con 46 semanas, y no alcanza la resolución que pide la corrección del punto siguiente.
   - **Tres departamentos:** el umbral se corrige por Bonferroni, así que se exige superar el p98,3 del nulo (0,05 / 3).
   - Solo entran los departamentos que pasan G1. Tumbes se muestra sin criterio.

### C. Indicadores de los medios
- **Volumen:** notas sobre El Niño por medio y mes, sin las de fecha dudosa.
- **Secciones:** proporción de las 5 secciones con más notas de cada medio, más "otras".
- **Tiempo de reacción:**
  - Para cada comunicado y medio: días (en hora de Lima) entre la emisión del comunicado (`fecha_emision` de `comunicados.csv`) y la primera nota del medio que lo cita como `informe`, `enlace` o `numero`, dentro de los 14 días siguientes. Una cita posterior ya no es reacción, sino referencia; se cuenta aparte.
  - No cuenta `proximo`, que es anunciar el siguiente comunicado.
  - Por medio se reporta la mediana y el número de comunicados. Solo si el medio citó al menos 5: contadas sin mirar los días, son Andina 17, Exitosa 17 y El Tiempo 9; RPP (4) queda fuera.

### D. Registro de uso
- Se lee con `radar.app.eventos.leer`.
- **Sesión:** id de sesión.
- **Embudo:** proporción de sesiones que llegan a cada paso, en el orden de la app.
- **Tiempo por pantalla:** en cada evento `vista`, `segundos` es el tiempo pasado en la pantalla `anterior`. Por eso se agrupa por `anterior` y se da la mediana.
- Se valida con registros sintéticos de resultado conocido. El uso real se calcula el 1-dic con la misma orden.

## 5. Criterios (fijados antes de ver resultados)

| # | Criterio | Umbral | Si no pasa |
|---|---|---|---|
| W1 | Canales de medios y otros con ≥ 3 videos con cercanía, y sus videos | ≥ 30 y ≥ 300 (contado: 79 y 968) | La parte A queda solo con W3 y W4 |
| W2 | Correlación parcial dentro del canal: IC 95 % por canal que excluye 0, el mismo signo en los dos períodos y en los videos de búsquedas por fecha | Las tres cosas | "No concluyente" |
| W3 | Spearman dentro de medios y dentro de otros, ponderado, con su IC por canal | Informativo | — |
| W4 | Mediana del objetivo (y de la tasa) por tercil de cercanía, con IC por canal | Informativo: mezcla canales y tipos, solo sirve para leer la dispersión | — |
| W5 | Mediana de la tasa por color de reglas (rojo y amarillo frente a verde), con su número de videos | Informativo (n pequeño) | — |
| W6 | Departamentos que entran a B (G1) | ≥ 3 (G1 ya pasó: 3) | B solo descriptiva |
| W7 | Comunicados en que sube el interés, por departamento | Descriptivo | — |
| W8 | Máximo de \|r\| en los desfases de −2 a +2 frente al nulo de fases al azar, por departamento | > p98,3 (Bonferroni por 3) para afirmar relación | "Sin relación medible" en ese departamento |
| W9 | Calidad del tiempo de reacción: citas con fecha anterior a la publicación de su comunicado | ≤ 2 % de las citas | El tiempo de reacción no se reporta |
| W10 | Registro de uso: con 3 registros sintéticos (embudo completo, abandono y sesiones mezcladas), sesiones, embudo y tiempos coinciden con lo esperado | 100 % | Se corrige antes de la presentación |
| W11 | Privacidad de las salidas: columnas con id de video o canal, título o seudónimo en los archivos para la app | 0 | Se quitan |

- **Sin etiquetado manual:** W10 usa registros sintéticos. Los demás criterios se calculan con código.
- **Una sola vez:** W2 y W8 se calculan una vez. Si se repiten, se declara.

## 6. Salidas y cómo se corre
- **Orden:** `python -m radar.analitica.web engagement|trends|medios|uso|todo`.
- **Código:** las funciones puras en `radar.analitica.indicadores` (sin archivos) y la línea de comandos en `radar.analitica.web`. Las pruebas sintéticas van en `tests/analitica/test_web.py`.
- **Archivos:**
  - `data/processed/youtube/<corte>_analitica-puntos.csv`: cercanía, objetivo, tasa, tipo y mes, sin ids. Vence con YouTube, porque sale de datos de YouTube.
  - `data/processed/analitica/web-engagement.csv`, `web-trends.csv`, `web-medios.csv` y `web-uso.csv`.
  - `web-validacion.csv`, con W1 a W11.
- **Pantalla F de la app:**
  - la dispersión de esos puntos, coloreada por tipo de canal y sin nombres;
  - **indicador 1:** la mediana de la tasa por tipo de canal;
  - **indicador 2:** la respuesta de W2 en palabras ("sí", "no" o "no concluyente"), con su IC.

## 7. Límites que se declaran
- La cercanía mide el tema, no el acuerdo (V3). El V2 de los videos es frágil, así que no hay lectura video por video.
- La parte A describe a los canales que publican varios videos sobre El Niño (79 de los canales). No dice nada de los que publicaron uno o dos.
- El 26 % de los videos entró solo por relevancia. W2 exige que el signo se repita sin ellos, pero el sesgo de búsqueda no se elimina del todo.
- La correlación dentro del canal no es causal. Quitar el mes por tipo absorbe la tendencia común, pero no un cambio de estilo propio de un canal.
- Trends es relativo y se muestrea, y Tumbes casi no tiene datos. Pocas notas nombran a cada departamento, así que la comparación principal usa todas.
- Son 71 citas de comunicados en 4 medios, así que el tiempo de reacción es solo indicativo.
- Los tres departamentos de W8 comparten la misma serie de notas, así que sus resultados no son independientes.
- W8 no distingue entre "la cobertura mueve el interés" y "los dos responden al mismo comunicado": dice si van juntos, no quién mueve a quién.
- No habrá uso real antes del congelamiento. El embudo de la presentación es la única evidencia de uso.

## 8. Análisis crítico (22-nov)
Se revisó cada supuesto con los datos, sin mirar la relación con el engagement ni con Trends.

| Riesgo | Comprobación | Cambio |
|---|---|---|
| La caída de la tasa desde septiembre fabrica una relación | Régimen ya medido en el modelo | Se quita la mediana por tipo y mes (A.2) |
| Los oficiales no permiten quitar el mes | 8 de sus meses tienen menos de 5 videos | Quedan fuera de W2, como en M1 |
| El largo del texto y el formato confunden | ρ 0,16 entre la cercanía y las palabras; el 46 % son Shorts | Se descuentan dentro del canal (A.3) |
| Selección por popularidad en la búsqueda | 419 videos (26 %) solo por relevancia | W2 exige el mismo signo sin ellos |
| Poca variación de la cercanía dentro del canal | El 77 % de su varianza está dentro del canal | Ninguno: el diseño tiene con qué medir |
| Las últimas semanas dominan la correlación de Trends | Las notas crecen 30 veces | Diferencias de log(1 + x) |
| Los muchos ceros de Trends rompen el nulo | Piura, Lambayeque y La Libertad tienen entre 15 y 22 % de semanas en 0 | Sustitutas IAAFT |
| Causa común en W8 | Los comunicados mueven las notas y las búsquedas | Se declara (sección 7) |
| Tiempo: quedan 5 días y la interfaz de la app no está empezada | Las cuatro partes son lecturas de archivos ya calculados; se estiman en 3 a 4 h | Se construye en una sola orden, `todo`, y deja tiempo a la interfaz |

**Qué no cambia:** el diseño dentro del canal, la regla de "no concluyente" y que B y C sean descriptivos.
