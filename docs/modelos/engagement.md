# Modelo de engagement: definición (aprobada el 22-nov-2026) y resultados

README, fila 11 y "Evaluación sin etiquetado manual"; pendientes, punto 1. Los criterios se fijan aquí antes de entrenar y no se cambian con los resultados. Construido y evaluado el 22-nov (sección 7).

**Qué se miró antes de definir (declarado):** solo distribuciones descriptivas de los datos, incluida la tasa observada en la prueba por mes y por tipo de canal (sección 1.3). En la prueba no se entrenó ni se evaluó ningún modelo. En el entrenamiento se corrió una validación cruzada por canal con los controles y los rasgos del título, para fijar umbrales realistas (sección 5); la cercanía y los tópicos todavía no se calcularon. Mirar la tasa de la prueba cambió el diseño (sección 1.3): se declara para que nadie lo lea como un criterio acomodado después.

## 1. Lo que muestran los datos del corte (22-nov)

### 1.1 Muestra
Son los videos que pasan el filtro y tienen ≥ 14 días entre la publicación y la descarga del 22-nov. **El último video que entra es del 8-nov**, no del 6-nov como dice el README, porque la regla usa la fecha real de descarga (igual que Y5).

| Dato | Entrenamiento (ene–ago) | Prueba (sep–8-nov) |
|---|---|---|
| Videos | 1.007 | 622 |
| Tasa (likes + comentarios) / vistas: mediana y p90 | 0,011 / 0,041 | 0,010 / 0,041 |
| Tasa 0 | 130 (13 %) | 55 (9 %) |
| < 30 vistas | 97 | 47 |
| Sin vistas, likes ocultos o comentarios desactivados | 8 | 9 |
| Última descarga anterior al corte | 0 | 3 |
| **Quedan para el modelo** | **999** | **610** |
| Días desde la publicación | 83 a 323 | 14 a 82 |
| Canales (con un solo video) | 365 (258) | 305 (230) |
| Los 10 canales con más videos | 41 % de los videos | 30 % |
| Mediana de suscriptores | 102.000 | 33.350 |
| Tipo: otros / medio / oficial | 699 / 270 / 38 | 485 / 120 / 17 |

### 1.2 Supuestos que se verificaron
| Supuesto | Medición | Resultado |
|---|---|---|
| La tasa sirve como objetivo, no las vistas | ρ de la tasa con los días en el entrenamiento: −0,01; ρ de las vistas con los suscriptores: 0,60 | Se sostiene |
| **La regla de los 14 días** | 1.551 videos con dos descargas (16 o 17-nov y 22-nov). Entre 14 y 30 días de edad, la tasa cambia una mediana de −0,3 % en 6 días (p10 −1,8 %); con más edad, 0 % | Se sostiene: a los 14 días la tasa ya es estable |
| Las tasas con pocas vistas son ruido | Con < 30 vistas, 67 de 91 videos tienen tasa 0 y el rango intercuartil es 0,039; con 1.000 a 10.000 vistas, 0 ceros y un rango de 0,010 | Hace falta suavizar |
| Los likes dominan la tasa | 245.000 likes frente a 15.400 comentarios (94 %) | Se declara: es casi la tasa de likes |
| El origen de la búsqueda no sesga la tasa | Los videos hallados solo por relevancia tienen más vistas (mediana 1.752 frente a 523), pero la misma tasa (0,011 frente a 0,012) | Se declara, sin control |
| Los días se solapan | No: la prueba tiene de 14 a 82 días y el entrenamiento, de 83 a 323 | Ningún modelo aprende la edad en la prueba. Como la tasa no varía con la edad (filas 1 y 2), **los días no entran como variable**; se declara |
| "Short" se reconoce por la duración | No: desde oct-2024 un Short dura hasta 3 min y la API no lo marca | Solo entra log(duración) |

### 1.3 Hallazgo crítico: cambio de régimen en los medios desde septiembre
Mediana de la tasa (‰, videos con ≥ 100 vistas) por mes de publicación:

| Tipo | feb | mar | may | jun | jul | ago | **sep** | **oct** | **nov** |
|---|---|---|---|---|---|---|---|---|---|
| Medio | 10,7 | 9,4 | 10,0 | 10,0 | 12,2 | 7,7 | **4,6** | **5,2** | **4,7** |
| Otros | 13,3 | 13,2 | 15,5 | 10,6 | 13,8 | 11,9 | 10,6 | 14,2 | 12,4 |

- **En los medios, la tasa cae a la mitad en la prueba** y lo mismo pasa dentro de cada uno de sus 4 canales más grandes, así que no es un cambio en la composición. A la vez, sus vistas se multiplican por 5 (mediana de 1.677 en agosto y de 8.934 en septiembre). Lectura probable: con la alerta, más gente que no sigue al canal ve sus videos y da menos likes. En los canales "otros", la tasa no cambia.
- **El entrenamiento no tiene cómo aprenderlo.** El interés nacional de Trends en la semana de publicación no explica la tasa dentro del entrenamiento (ρ −0,00 en medios, −0,02 en total), y 342 de los 622 videos de prueba están en semanas con más interés que cualquiera del entrenamiento (máximo 64, frente a hasta 100). Por eso Trends **no** entra como variable.
- **Consecuencias para el diseño:**
  1. Con la partición del README, el error medido mezcla dos cosas: el **nivel** (un cambio de régimen que nada en el entrenamiento anticipa) y el **orden** (qué video tiene más engagement que otro, que sí se puede aprender). Los criterios se separan en esas dos partes (sección 5).
  2. Se agrega la línea base de **persistencia**: la mediana del último mes de entrenamiento (agosto), que es la que se usaría en la práctica.
  3. Se agrega una evaluación con **origen móvil**, informativa: cada mes de prueba se predice con un modelo entrenado con todos los meses anteriores. Mide qué pasa si el modelo se reentrena cada mes (M6).
  4. Hay un riesgo de **asociación espuria:** los títulos con "extraordinario" se concentran después del comunicado N.° 18 (16-oct), justo en el régimen nuevo. Una variable de contenido puede parecer importante solo porque marca la época. Por eso M3 se mide **dentro de cada tipo de canal** y frente a un modelo con los controles.

## 2. Mapa de enfoques

**Qué se predice**

| Enfoque | Problema | Decisión |
|---|---|---|
| A. Tasa cruda (README) | Ruido con pocas vistas; 13 % de ceros; cola larga | Descartada como objetivo directo |
| B. **Logit de la tasa suavizada** (beta-binomial, con la tasa del entrenamiento como prior; con el método de momentos, α + β ≈ 100) | Un video con 100 vistas queda a mitad de camino hacia la media | **Base** |
| C. Conteo (likes + comentarios) con pérdida Poisson y las vistas como exposición | Los videos de millones de vistas dominan el ajuste | Rival (M4) |
| D. Vistas | Dependen de los suscriptores y de la edad: es alcance, no engagement | Descartado |
| E. Clase (tasa sobre la mediana) | Tira información y el umbral es arbitrario | Descartado |
| F. Tasa relativa a la de su canal | 258 de 365 canales tienen un solo video | Descartado |
| G. Tasa relativa a la del mes (quitar el régimen) | Usaría la tasa de otros videos de la prueba para normalizar | Descartado |
| H. Solo likes o solo comentarios | Los comentarios son el 6 %: casi lo mismo que la tasa o muy escaso | Descartado |

**Con qué modelo**

| Enfoque | Decisión |
|---|---|
| Mediana del entrenamiento y mediana de agosto (persistencia) | **Líneas base B0** (se toma la mejor de las dos en la prueba, la más exigente) |
| Solo controles, **con el mismo algoritmo y la misma búsqueda de hiperparámetros que el modelo elegido** | **Línea base B1**: decide si el contenido agrega algo. Si se comparara un boosting con un Ridge, la ventaja podría venir del algoritmo y no del contenido |
| Ridge con controles y contenido (README: regresión lineal) | **Modelo L** |
| Gradient boosting (`HistGradientBoostingRegressor`) | **Modelo G** |
| Efectos mixtos con intercepto por canal | Descartado: 258 canales con un video y no sirve para canales nuevos |
| Embeddings como variables | Descartado: 1.007 videos para 384 dimensiones |
| La tasa histórica del canal como variable | Descartado: aprendería al canal en lugar del contenido |

**Partición**

| Enfoque | Decisión |
|---|---|
| Temporal fija: ene–ago / sep–8-nov (README, Y5) | **Base**: está fijada desde el 16-nov y no se cambia tras ver el régimen |
| Origen móvil por mes (sep, oct, nov) | **Informativa** (M6) |
| GroupKFold por canal | Solo dentro del entrenamiento, para elegir los hiperparámetros |
| Aleatoria | Descartada: mezcla épocas |

## 3. Definición

**Objetivo:** `y = logit((likes + comentarios + α) / (vistas + α + β))`. α y β salen de una beta-binomial ajustada solo con el entrenamiento, por el método de momentos.

**Exclusiones:** videos sin vistas, con likes ocultos o con los comentarios desactivados (8 en el entrenamiento y 9 en la prueba), y los 3 de la prueba cuya última descarga no es la del corte. Quedan 999 y 610. Se declaran.

**Variables** (ninguna requiere etiquetar):
| Grupo | Variables | De dónde |
|---|---|---|
| Controles | log(suscriptores + 1), log(n.° de videos del canal + 1), canal de Perú (`country`), log(duración en s), tipo de canal (oficial, medio, otros), categoría (25, 22, 28, 24, 27; el resto se junta), publicado en fin de semana y en horario diurno (de 6 a 18 h, hora de Lima) | API y `canales` |
| Enlaces | La descripción enlaza a un sitio `.gob.pe` (55 videos del entrenamiento); conecta con la red de enlaces | `enlaces` del video |
| Cercanía con lo oficial | La similitud minilm continua (no el color) del título y la descripción con los párrafos del ENFEN vigentes en la fecha de publicación. El texto va **sin enlaces ni hashtags y cortado a 100 palabras**, el tipo "corto" calibrado del semáforo, porque la mediana de la descripción es de 107 palabras y suele traer texto de relleno ("suscríbete…"). Si hay afirmaciones con datos, se agrega una variable que dice si alguna no coincide | `semaforo.medir_discrepancia` |
| Tópicos | El más cercano de los 12 tópicos de las notas, por el centroide minilm de cada tópico | `topicos-notas.csv` y `topicos-lectura.csv` |
| Rasgos del título | Proporción de mayúsculas, n.° de signos ¡ y !, n.° de emojis, si es una pregunta, n.° de palabras, si menciona una magnitud (`magnitudes_de_frase`) | Código nuevo, con pruebas sintéticas |

- **No entran:** las emociones (decisión del 17-nov: son solo descriptivas, aunque el README las liste), los días (sección 1.2) y Trends (sección 1.3).
- La variable "alguna no coincide" entra solo si al menos 30 videos del entrenamiento tienen afirmaciones con datos; si no, se omite y se declara.
- Los suscriptores son los del 22-nov, no los del día de la publicación. Se declara.
- Los tópicos se ajustaron con notas de todo el año. No conocen el engagement, así que no filtran el objetivo; se declara.

**Hiperparámetros:** solo con el entrenamiento, con GroupKFold por canal (5 grupos).
- Ridge: α en {0,1; 1; 10; 100}.
- Boosting: profundidad máxima en {2, 3}, n.° de árboles en {100, 200, 300}, tasa de aprendizaje 0,05 y hoja mínima de 20, **sin parada temprana**: la de scikit-learn separa la validación al azar y mezclaría videos de un mismo canal.
- Entre L y G se elige por el MAE de la validación cruzada, no por la prueba. La prueba se usa **una sola vez**.

**Intervalos:** bootstrap de 1.000 réplicas, remuestreando canales de la prueba, con semilla fija.

## 4. Métricas
- **MAE** en la escala del objetivo (principal), también en ‰ de tasa para leerlo, y **R²** (README).
- **Sesgo medio** (predicción menos observado): mide el nivel.
- **Spearman** entre la predicción y el objetivo: mide el orden. Se calcula en total y **dentro de cada tipo de canal**.
- **Importancia por permutación** en la prueba, por grupo de variables, con su intervalo.
- Todo se reporta también por separado para canales nuevos y vistos, y para medios y otros (informativo).

## 5. Criterios fijados antes

| Id | Criterio | Umbral | Si no pasa |
|---|---|---|---|
| M0 | **Tópicos útiles en videos:** ningún tópico se lleva más del 50 % de los videos del entrenamiento (se mide antes de entrenar) | ≤ 50 % | Los tópicos salen del modelo y se declara |
| M1 | **Orden:** Spearman del modelo elegido en la prueba, calculado dentro de medios y dentro de otros y promediado según el n.° de videos de cada tipo (los 17 videos oficiales de la prueba no alcanzan para un Spearman propio y solo se informan) | ≥ 0,20, con el IC 95 % sin el 0 | El modelo no ordena los videos: se reporta solo la analítica descriptiva |
| M2 | **Error:** MAE del modelo elegido frente a la mejor B0 | IC 95 % de la diferencia sin el 0 (se informa el % de mejora) | Se declara que el cambio de régimen domina el error; si M1 pasa, el modelo sirve para ordenar, no para predecir el nivel |
| M3 | **El contenido agrega:** Spearman dentro de cada tipo, del modelo elegido frente a B1 (solo controles) | IC 95 % de la diferencia sin el 0 | Se informa que, con estos datos, el contenido no ordena el engagement más allá del canal. Es un hallazgo, no un error |
| M4 | Objetivo B frente al rival C (Poisson), con el mismo modelo, por Spearman | Informativo | — |
| M5 | Estabilidad: la importancia de cada grupo tiene el mismo signo en los 5 grupos de validación | Informativo | Ese grupo se declara inestable y no se interpreta |
| M6 | Origen móvil: MAE, sesgo y Spearman de sep, oct y nov, cada uno con todo lo anterior | Informativo | — |

- El R² y el sesgo se reportan siempre. Si el R² sale negativo por el nivel, se dice así.
- Los coeficientes y la importancia se leen como **asociación, no causalidad** (README), nunca por canal individual y nunca como prueba de que el contenido alejado de lo oficial "rinde más".
- **En la app:** el gráfico F usa la tasa observada y la cercanía (descriptivo). El modelo solo aparece en Metodología, con el cambio de régimen declarado.

**Rendimiento esperado, medido solo en el entrenamiento** (GroupKFold por canal, 22-nov). Se midió con las variables de API y los rasgos del título; la cercanía y los tópicos todavía no estaban calculados. La prueba no se tocó.

| Modelo | MAE (B0: 0,529) | Spearman en medios | Spearman en otros |
|---|---|---|---|
| Ridge, controles del README | 0,521 | 0,02 | 0,22 |
| Boosting, controles del README | 0,509 | 0,09 | 0,30 |
| Boosting, controles de esta definición | 0,501 | 0,09 | 0,36 |
| Boosting, controles + rasgos del título | 0,501 | −0,05 | 0,37 |

- **Se espera poco:** el mejor modelo mejora el MAE un 5 % en el entrenamiento, y en la prueba se suma el cambio de régimen. Por eso M2 pide solo que la mejora sea real (IC sin el 0) y no fija un 5 % que ni el entrenamiento alcanza.
- **Dentro de los medios casi no hay orden** que explicar con controles (todos son canales grandes de noticias). La señal está en "otros". Por eso M1 pondera por el número de videos y no promedia los dos tipos por igual. En el entrenamiento daría 0,28.
- **Los rasgos del título casi no agregan** (0,36 a 0,37 en otros, y empeoran en medios). Lo más probable es que M3 no pase. Eso responde la pregunta 5 del README con honestidad, y no se acomoda.
- **Por qué 0,20 en M1:** el entrenamiento llega a 0,28, y con unos 485 "otros" en la prueba, el IC es de cerca de ±0,09. Un umbral más alto pediría más de lo que se mide; uno más bajo aceptaría un orden casi nulo.

## 6. Cómo se correría (cuando se apruebe)
- `python -m radar.modelos.engagement variables`: sin red; carga minilm una vez.
- `python -m radar.modelos.engagement entrenar`.
- `python -m radar.modelos.engagement evaluar`.

Solo lee con `radar.youtube.almacen`. Las variables por video llevan ids, así que van a `data/processed/youtube/AAAA-MM-DD_engagement-variables.csv` con la fecha del corte y vencen con los datos de YouTube (`radar.youtube.borrar`). Los resultados son solo agregados, sin ids ni textos, y van a `data/processed/modelos/`: `engagement-eleccion.json`, `-validacion.csv`, `-detalle.csv`, `-importancia.csv` y `-meses.csv`. `evaluar` se niega a correr dos veces sobre la prueba si no se le pasa `--repetir`.

- `variables` es **reanudable**: guarda cada video al terminarlo y, si se corta, sigue desde el último. Muestra el avance con un tiempo estimado.
- La cercanía se calcula en lotes con minilm cargado una sola vez. Con 1.609 videos y la mediana de S6, se esperan minutos.
- La validación cruzada y el bootstrap corren en paralelo (`n_jobs` = núcleos − 1, para no saturar la máquina).
- Las semillas son fijas, así que dos corridas dan lo mismo.

## 7. Resultados (22-nov-2026)

**Variables:** 1.609 videos (999 para entrenar y 610 para probar), en unos 4 min.
- 5 videos tienen un texto insuficiente (menos de 5 palabras) y quedan sin cercanía. El boosting los trata como faltantes y el Ridge, con la mediana.
- 178 videos del entrenamiento tienen afirmaciones con datos (145 verdes, 17 amarillas y 16 rojas), así que **entra "alguna no coincide"**.

**Entrenamiento** (`entrenar`, GroupKFold por canal):

| | MAE de validación | Spearman por tipo |
|---|---|---|
| B0 (mediana) | 0,529 | — |
| L, Ridge (α = 100) | 0,516 | 0,213 |
| **G, boosting (profundidad 2, 100 árboles)** | **0,495** | **0,303** |
| B1, boosting solo con controles | 0,500 | 0,285 |

- **M0 pasa:** el tópico más grande se lleva el 36,9 % de los videos, así que entran los 12 tópicos.
- **Se elige G.** Los dos óptimos quedaron en el borde de su grilla (α = 100 en Ridge; profundidad 2 y 100 árboles en el boosting). La grilla estaba fijada antes y no se amplió: un modelo más simple sería un poco mejor. Se declara.

**Prueba** (`evaluar`, una vez; bootstrap de 1.000 réplicas por canal):

| Id | Resultado | Umbral | |
|---|---|---|---|
| M1 | Spearman por tipo **0,430** (IC 0,292–0,542) | ≥ 0,20 e IC sin el 0 | **Pasa** |
| M2 | MAE 0,578 frente a 0,662 de B0 agosto (**+12,6 %**; IC de la mejora 0,057–0,108) | IC sin el 0 | **Pasa** |
| M3 | El contenido agrega **+0,063** de Spearman sobre B1 (0,368; IC 0,005–0,111) | IC sin el 0 | **Pasa, por poco** |
| M4 | El objetivo B le gana al rival Poisson por +0,218 (C: 0,212; IC 0,113–0,325) | Informativo | El suavizado acierta |
| M5 | Solo la **cercanía** tiene el mismo signo en los 5 pliegues. Rasgos, enlaces y tópicos son inestables | Informativo | Solo se interpreta la cercanía |
| M6 | MAE / B0 / sesgo / Spearman: sep 0,604 / 0,690 / +0,18 / 0,47; oct 0,554 / 0,664 / +0,13 / 0,43; nov 0,422 / 0,591 / +0,24 / 0,50 | Informativo | Reentrenar cada mes mantiene el orden |

**Detalle:**
- **R² en total: 0,218.** En los medios es −1,55, con un sesgo de +0,63: el modelo sobreestima su tasa, que es el cambio de régimen de la sección 1.3. Aun así, ordena bien dentro de los medios (Spearman 0,32, frente a 0,15 de B1).
- **En los otros:** R² 0,21 y Spearman 0,46.
- **Canales nuevos** (296 videos): Spearman por tipo 0,25 y MAE 0,514. **Canales vistos** (314 videos): 0,41 y 0,639. Una parte del orden viene de conocer al canal.
- **Importancia en la prueba** (aumento del MAE al permutar):
  - rasgos: 0,0084 (IC 0,0055–0,0117), pero inestable en la validación cruzada;
  - cercanía: 0,0070 (IC 0,0043–0,0096), estable;
  - tópicos: 0,0002, con un IC que incluye el 0;
  - enlaces: 0.

**Lectura:**
- El modelo **ordena** el engagement de los videos nuevos mejor que el canal solo (M1 y M3) y **mejora el error** frente a la persistencia (M2).
- El aporte del contenido es pequeño, y la única parte estable es la **cercanía con lo oficial**. Esto es una asociación, no una causa. La importancia no da el sentido de la relación: si lo más cercano tiene más o menos engagement lo responde la analítica web (Spearman, punto 3 de los pendientes).
- El nivel de la tasa de los medios en la alerta no se puede predecir con el entrenamiento: queda declarado.

**Corrección declarada:** la primera corrida de `evaluar` comparaba el MAE del rival C (que predice la tasa) con el objetivo en logit. Se corrigió la escala y se repitió con `--repetir`. M1 a M4 dan lo mismo, porque las semillas son fijas y el Spearman no cambia con la escala; solo cambian el MAE, el R² y el sesgo de C en el detalle.
