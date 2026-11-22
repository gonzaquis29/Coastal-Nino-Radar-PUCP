# Analítica web (README, punto 10; pregunta 5)

**Estado:** propuesta del 22-nov, pendiente de aprobación. Nada se construye sin la orden del usuario. Los criterios se fijan aquí, antes de ver los resultados. Los tamaños de muestra de la sección 2 se contaron sin mirar ninguna relación.

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
1. **Muestra:** los videos de `engagement-variables.csv` con cercanía, en los canales que tienen 3 videos o más.
2. **Correlación dentro del canal:**
   - En cada canal, la cercanía y el objetivo se pasan a rangos, que se centran y se dividen por el número de videos del canal.
   - Con esos valores de todos los canales juntos se calcula Pearson. Es un Spearman estratificado por canal, y cada video pesa lo mismo.
   - El signo se lee al revés: ρ < 0 quiere decir que **lo más alejado tiene más engagement**.
3. **Incertidumbre:** IC 95 % con un bootstrap por canal de 1.000 réplicas (semilla del proyecto). Se sortean canales y entran todos sus videos.
4. **Por período:** lo mismo, por separado en el entrenamiento (enero a agosto) y en la prueba (septiembre al corte), porque desde septiembre cambia el régimen de la tasa de los medios.
5. **Respuesta a la pregunta A, con la regla fijada aquí:**
   - **"Sí" o "no"** (según el signo) solo si el IC excluye 0 y el signo es el mismo en los dos períodos.
   - En cualquier otro caso, **"no concluyente"**. Esa es la frase que va en la app.

### B. Trends por departamento
1. **Series:** `radar.trends.cargar.serie_final`, que ya promedia Tumbes.
2. **Por comunicado:**
   - Se compara la semana de Trends que contiene la fecha del comunicado (semanas de domingo a sábado) con el promedio de las 3 semanas anteriores.
   - Se cuenta en cuántos comunicados sube, por departamento. Entran los comunicados con 3 semanas anteriores dentro del período.
   - Es descriptivo y no lleva valor p. Se declara que las 3 semanas anteriores pueden incluir otro comunicado, porque salen cada 2 a 4 semanas.
3. **Correlación cruzada:**
   - Se compara la diferencia semanal de Trends de cada departamento con la diferencia semanal de todas las notas sobre El Niño, en las mismas semanas de domingo a sábado en hora de Lima. Como informativo se repite con las notas que nombran a ese departamento.
   - Se usan las diferencias porque las dos series crecen todo el año, y sin quitar la tendencia cualquier par sale correlacionado (eventos, medición previa).
   - Se prueban los desfases de −2 a +2 semanas. Un desfase positivo quiere decir que Trends va detrás de las notas.
   - **Nulo:** se desplaza en círculo una serie respecto de la otra, en todos los desplazamientos de más de 2 semanas. En cada uno se toma el máximo de |r| en los 5 desfases. Con 46 semanas, el nulo tiene unos 40 valores, y esa resolución se declara.
   - Solo entran los departamentos que pasan G1. Tumbes se muestra sin criterio.

### C. Indicadores de los medios
- **Volumen:** notas sobre El Niño por medio y mes, sin las de fecha dudosa.
- **Secciones:** proporción de las 5 secciones con más notas de cada medio, más "otras".
- **Tiempo de reacción:**
  - Para cada comunicado y medio: días (en hora de Lima) entre la publicación del comunicado (`comunicados.csv`) y la primera nota del medio que lo cita como `informe`, `enlace` o `numero`.
  - No cuenta `proximo`, que es anunciar el siguiente comunicado.
  - Por medio se reporta la mediana y el número de comunicados. Solo si el medio citó al menos 5.

### D. Registro de uso
- Se lee con `radar.app.eventos.leer`.
- **Sesión:** id de sesión.
- **Embudo:** proporción de sesiones que llegan a cada paso, en el orden de la app.
- **Tiempo por pantalla:** la mediana del campo de tiempo de los eventos `vista`.
- Se valida con registros sintéticos de resultado conocido. El uso real se calcula el 1-dic con la misma orden.

## 5. Criterios (fijados antes de ver resultados)

| # | Criterio | Umbral | Si no pasa |
|---|---|---|---|
| W1 | Canales con ≥ 3 videos con cercanía, y sus videos | ≥ 30 y ≥ 300 (contado: 84 y 1.018) | La parte A queda solo con W3 y W4 |
| W2 | Correlación dentro del canal: IC 95 % por canal que excluye 0 y el mismo signo en los dos períodos | Las dos cosas | "No concluyente" |
| W3 | Spearman dentro de medios y dentro de otros, ponderado, con su IC por canal | Informativo | — |
| W4 | Mediana del objetivo (y de la tasa) por tercil de cercanía, con IC por canal | Informativo | — |
| W5 | Mediana de la tasa por color de reglas (rojo y amarillo frente a verde), con su número de videos | Informativo (n pequeño) | — |
| W6 | Departamentos que entran a B (G1) | ≥ 3 (G1 ya pasó: 3) | B solo descriptiva |
| W7 | Comunicados en que sube el interés, por departamento | Descriptivo | — |
| W8 | Máximo de \|r\| en los desfases de −2 a +2 frente al p95 del nulo circular, por departamento | > p95 para afirmar relación | "Sin relación medible" en ese departamento |
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
- La correlación dentro del canal no es causal. Si el canal cambia de estilo con el tiempo, eso puede quedar mezclado.
- Trends es relativo y se muestrea, y Tumbes casi no tiene datos. Pocas notas nombran a cada departamento, así que la comparación principal usa todas.
- Son 71 citas de comunicados en 4 medios, así que el tiempo de reacción es solo indicativo.
- No habrá uso real antes del congelamiento. El embudo de la presentación es la única evidencia de uso.
