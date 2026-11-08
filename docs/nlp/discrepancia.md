# Índice de discrepancia: pilotos, decisiones y flujo por capas (28-oct-2026)

Estado del diseño después de los pilotos del 27 y 28-oct. Reemplaza lo que el README dice del NLI ("párrafo oficial más cercano", prueba de ~20 contradicciones sintéticas) mientras no se actualice el README.

## Qué se aprendió de los pilotos
Pilotos fuera del repositorio, con notas reales leídas en memoria y sin guardar el cuerpo.

- **La prueba sintética del README es demasiado fácil.** Con cambios explícitos ("débil" → "fuerte") el NLI da contradicción ≈ 1,00, así que pasaría sin decir nada de las noticias reales.
- **Comparar contra "el párrafo más parecido" da falsas alarmas.** El modelo marca contradicción contra párrafos parecidos pero de otra región (costa frente a Pacífico central) o de otro tema (recomendaciones). La regla "algún párrafo del comunicado vigente la contradice y ninguno la respalda" (ambas con probabilidad > 0,5) bajó las falsas alarmas de 5/16 a 0/16 en frases oficiales.
- **Con notas reales, el NLI con umbral 0,5 no pasa.** En las notas de Andina que citan el comunicado marca el 25,8 % de las frases (resumen del comunicado) y el 22,7 % (comunicado completo); el umbral de descarte, fijado antes de ver los resultados, era 20 %. **Esa configuración se descarta.** Con umbral 0,9 serían 6 %, pero no se puede adoptar con esos mismos datos.
- **Las reglas por dato (magnitud frente a `comunicados.csv`) tampoco estaban listas.** Daban 0 falsas alarmas en el control, pero solo 1 de sus 8 discrepancias era real.
- **La mayoría de los errores de ambos métodos venían de etapas previas, no del método:**
  - texto sucio ("Lea también", créditos, párrafos pegados);
  - frases que no afirman nada del Niño actual (explicaciones, Niños pasados, otras agencias);
  - párrafos oficiales mal elegidos (encabezados de tabla, recomendaciones, Pacífico central).

  De ahí el flujo por capas.
- **Las afirmaciones verificables son pocas.** En 40 notas sobre El Niño (995 frases), solo ~0,7 por nota, contando titular, resumen y cuerpo. En muchas notas el índice dirá "sin afirmaciones verificables" y dependerá de la distancia semántica.

## Decisiones de estrategia
1. **El índice se apoya en las reglas por dato y la distancia semántica.** El NLI queda acotado a **un solo intento**: calibrar el umbral con los pares naturales de enero a junio y evaluarlo con los de julio a octubre y con notas nuevas. Si no mejora claramente a las reglas, se descarta y queda como análisis offline.
2. **Flujo por capas, una a la vez,** cada una definida, aprobada, construida y validada con muestras nuevas antes de la siguiente. Si una capa destapa un error de otra, se analiza y se corrige en su capa.
3. **Datos ya vistos no se reusan para evaluar.** La lista está en `config/notas_vistas.csv` (solo medio, id y muestra); cada validación nueva la excluye y agrega su propia muestra (`validar_texto.notas_vistas` y `marcar_vistas`). Se reconstruyó el 28-oct reproduciendo cada muestreo con su semilla y las notas que existían a la hora en que corrió. La del piloto coincide con sus 170 ids registrados. Son 2.127 notas:
   - las 66 frases (39 notas) del control de Andina del piloto;
   - las 200 notas con magnitud del piloto (semilla 656);
   - las muestras de exploración de la capa 3 (semilla "capa3-exploracion");
   - las de la capa 1 (estructura, las 7 semillas de `validar_texto` y "capa1-sobre-nino");
   - las de la prueba del filtro por título del 24-oct.

   Las notas sobre El Niño que citan un comunicado o nombran al ENFEN quedan **reservadas** para validar la capa 3 (`validar_texto.reservada_capa3`): ninguna otra muestra las toma.

## Flujo por capas
| Capa | Responsabilidad | Estado |
|------|-----------------|--------|
| 1. Texto limpio | Cuerpo en líneas y sin bloques ajenos (`noticias/nota.py`) | **Hecha** (28-oct): [../noticias/texto.md](../noticias/texto.md) |
| 2. Corpus oficial limpio | Sin encabezados de tabla; `tipo` y `region_enso` por párrafo (`oficial/`) | **Hecha** (28-oct): [../oficial/definicion.md](../oficial/definicion.md) |
| 3. Frases y afirmaciones | Qué dato afirma cada frase, quién lo dice, de cuándo, con qué seguridad | **Hecha** (7-nov): estado y magnitud pasan; plazo no pasa (0,882) |
| 4. Referencia oficial | Comunicado vigente y anterior de cada nota, con datos comparables (plazos en mes y año) | Por definir; `radar.oficial.vigencia.Corpus` ya da el vigente |
| 5. Comparación | Reglas por dato en cuatro dimensiones (dato, escala, tiempo, certeza) + distancia → semáforo | **Hecha** (7-nov): pasa en la ronda c; C3 con pocos casos |

## Capa 3: frases y afirmaciones (definición aprobada para construir)
**Responsabilidad única:** partir el texto limpio en frases y, de cada frase que afirma algo sobre El Niño, sacar qué dato afirma, quién lo dice, de qué momento habla y con qué seguridad. No compara con lo oficial. Va en `src/radar/nlp/`.

1. **Frases** de titular, resumen y cuerpo, marcadas con su origen. Se parte por línea y luego por fin de frase, también tras cifras y comillas. Las líneas de menos de 5 palabras son subtítulos y no cuentan como afirmación.
2. **Afirmación:** frase que nombra El Niño (o el Niño costero, o el ENFEN) y tiene al menos un dato:
   - **magnitud,** con la regla por cercanía `oficial.enfen.magnitudes_de_frase`, que separa lo principal de lo posible y es la misma de `rasgos.magnitudes` y de `comunicados.csv`. **Hecha y validada el 28-oct** ([magnitud.md](magnitud.md));
   - **estado** (No Activo, Vigilancia, Alerta);
   - **plazo,** convertido a mes y año con una función compartida, que también convierte el `plazo` de `comunicados.csv` ("hasta mediados de otoño de 2027" → mayo de 2027; "del presente año" → año de la nota);
   - **probabilidad,** solo junto a El Niño o a una condición (cálida, neutra, fría): un "%" económico no cuenta;
   - **región del océano:** "Niño costero" es costa; "Pacífico central" o "global" es Niño 3.4; "El Niño" solo queda ambigua.
3. **Marcas, sin borrar nada:**
   - atribución (ENFEN u otra fuente oficial, otra agencia, tercero, sin atribución);
   - cita textual entre comillas;
   - momento (actual o histórico);
   - modalidad (afirma, condicional, pregunta);
   - explicativa (definiciones, explicación de la escala).
4. **Salida** `data/processed/nlp/afirmaciones.csv`, sin el texto: nota, número de frase, origen, `sha1` de la frase, datos y marcas.

**Validación (criterios fijados el 28-oct):**

| Criterio | Pasa si |
|----------|---------|
| Frases de más de 60 palabras | ≤ 2 % |
| Estado en los textos oficiales (referencia independiente: el encabezado del comunicado) | ≥ 95 % |
| Estado, magnitud y plazo de las afirmaciones atribuidas al ENFEN en notas nuevas, frente al comunicado vigente o al anterior en la fecha de la nota | ≥ 90 % cada uno, con su intervalo; cada desacuerdo se diagnostica |
| Conversión de plazos (casos conocidos) | 100 % |
| Marcas (frases sintéticas) | 100 % |

Las notas nuevas para esa validación son ~170:
- las 52 notas de Exitosa, El Tiempo y RPP que citan un comunicado y no se vieron (de las 62, 9 estaban en el piloto y 1 en la exploración);
- 30 por medio de las 416 notas sobre El Niño que mencionan al ENFEN, sin las ya vistas.

**Lo que no se puede validar en esta capa:**
- La magnitud y el plazo de `comunicados.csv` salen de las mismas reglas aplicadas al texto oficial, así que compararlos sobre ese texto es solo un chequeo de regresión.
- Las marcas (histórico, otra agencia, explicativa) no tienen referencia externa: su efecto se mide en la capa 5, viendo si bajan las falsas alarmas (7 de las 8 de las reglas por dato venían de esas categorías) sin perder detección.

**Ajustes aprobados el 7-nov.** Salen de revisar la definición con 139 notas reservadas ya vistas, sin usar notas nuevas:
- **Afirmaciones:** en las notas que citan un comunicado o nombran al ENFEN hay ~3 por nota, y 1,6 atribuidas al ENFEN en la misma frase. Las frases de más de 60 palabras son el 1,6 %.
- **Estado:** solo cuenta como valor de El Niño ("estado de Alerta de El Niño Costero", "cambia el estado a Vigilancia"; en "de X a Y" vale Y). "Sistema de alerta", las alertas roja, naranja o amarilla y las de otros países no son el estado: en titulares y resúmenes, solo 43 de 245 frases con "alerta" o "vigilancia" lo eran.
- **Plazo en mes y año:** cada estación termina en un mes fijo (verano → marzo, otoño → junio, invierno → septiembre, primavera → diciembre). Con "inicios", "mediados" o "fines" va al primer, segundo o último mes. Sin año, vale la próxima estación o el próximo mes desde la fecha del texto.
- **Magnitud y plazo frente al comunicado:** aciertan si están entre los que menciona para la costa el comunicado vigente o el anterior. El N.° 19 dice "hasta fines de otoño de 2027" en el titular y "magnitud extraordinaria hasta febrero de 2027" en el cuerpo, y `comunicados.csv` guarda solo uno.
- **Probabilidad:** se extrae, pero no se valida. La tabla oficial está solo en 4 de los 20 comunicados (N.° 13 a 16).
- **Atribución:** pasa a la frase siguiente del mismo párrafo ("Según el ENFEN… Además, …"). Dentro de "tercero" se marca "otro país" (por ejemplo, Ecuador).
- **Muestra de validación:** son ~150 notas. Las 30 que citan un comunicado sin ver (el recálculo del 31-oct dejó 30, no 52), más 30 por medio de las que nombran al ENFEN. El 90 % se cumple con la estimación puntual, y el intervalo de Wilson se reporta.
- **Fuera de alcance:** el nivel de los avisos del Senamhi (rojo, naranja) que citan las notas. Queda para la capa 5, con la distancia.

**Resultado (7-nov).** Código: `radar.nlp.afirmaciones` (`muestra` y `validar`, con `--ronda a|b`). Salida: `data/processed/nlp/afirmaciones.csv`, sin el texto de las frases.

| Criterio | Ronda a (150 notas) | Ronda b (99 notas, tras los arreglos) |
|---|---|---|
| Conversión de plazos (15 casos) | 15/15 | 15/15 |
| Estado en los textos oficiales | 33/33 | 33/33 |
| Frases de más de 60 palabras | 1,3 % | 1,3 % |
| Estado atribuido al ENFEN | 63/64 (0,984) | 19/19 (1,000; IC 0,83–1,00) |
| Magnitud atribuida al ENFEN | 116/128 (0,906) | 62/63 (0,984; IC 0,92–1,00) |
| **Plazo atribuido al ENFEN** | 91/104 (0,875) **no pasa** | 30/34 (0,882; IC 0,73–0,95) **no pasa** |

- **Ronda a:** de 25 desacuerdos, 15 eran de extracción. Se corrigieron con 4 arreglos:
  1. marca `negada` ("descarta", "prematuro afirmar"), que no se evalúa;
  2. plazo de solo año ("hasta 2027"), que se compara por año;
  3. relato de un comunicado de dos o más meses atrás, que cuenta como histórico;
  4. plazo solo si va pegado a El Niño y no a lluvias o calor.

  Los otros 10 eran diferencias reales: un vocero que dice más que el comunicado, o notas que redondean.
- **Ronda b:** ninguno de los 4 desacuerdos de plazo es un error de extracción.
  - 2 son del vocero del ENFEN ("se expandiría hasta mayo de 2027", cuando el comunicado decía "hasta el verano").
  - 2 vienen de la referencia: el comunicado N.° 09 da el plazo como rango ("moderada entre mayo y agosto"), y la regla solo lee "hasta …".
- **Sin notas reservadas por ver:** las de la ronda b eran todas las que quedaban. Llegan ~1,5 por día.

### Temporalidad (plazo v2, aprobada el 7-nov)
El plazo v1 solo lee "hasta …" y compara un mes. La v2 (`radar.nlp.temporalidad`) parte cada frase en **segmentos**: un sujeto (el evento o una magnitud) con inicio y fin como intervalos de meses.
- **Normalización:** las estaciones son las del hemisferio sur (verano = dic. del año anterior a mar.). "Inicios", "mediados" y "fines" acotan el intervalo. Un año solo vale el año entero; "primer trimestre" vale de enero a marzo.
- **Relaciones:** rango ("de/entre X a/y Y", paréntesis, guion), "hasta" (fin), "a partir de/desde" (inicio) e "iniciado en" (inicio del evento). El punto ("en julio") solo cuenta junto a una magnitud.
- **Qué no es del evento:** las fechas de lluvias, temperatura del aire, condición neutra o publicación no son segmentos. Tras "luego disminuiría…", la fecha es de la fase que sigue.
- **Comparación:** el mismo extractor corre sobre las frases costeras de los comunicados (`data/processed/nlp/temporalidad-oficial.csv`). Un segmento queda *respaldado* (cruce con ±1 mes), *desactualizado* (cruza solo con un comunicado anterior) o *sin respaldo*.
- **Descartados:** HeidelTime (estaciones del hemisferio norte, sin "hasta"), dateparser y duckling (no hacen rangos de estación) y el NLI. Un LLM local queda solo como control informativo.

**Resultado (7-nov).** `python -m radar.nlp.temporalidad validar`:

| Criterio | Umbral | Resultado |
|---|---|---|
| T1. Normalización (casos conocidos) | 100 % | 32/32 |
| T2. Completitud en los comunicados | ≥ 95 % | 113/114 |
| T3. Paráfrasis oficiales (titular o resumen frente al cuerpo) | ≥ 90 % | 29/31 |
| T4. Fin del evento en cada comunicado | 100 % | 19/19 |

T2 a T4 se ajustaron mirando los mismos comunicados, así que son controles de desarrollo, no una validación independiente. En T4, el campo `plazo` de los N.° 17 a 19 es la duración de la magnitud, no la del evento; ahí se compara con el titular. La confirmación independiente es **T5** (informativo): las notas reservadas nuevas que lleguen hasta el 18-nov.

## Capa 5: comparación (definición aprobada el 7-nov)
**Qué hace:** mide qué tan lejos está cada afirmación de lo oficial y en qué dimensión. No dice si una nota es verdadera o falsa. Es la misma idea con la que se compara una nota de ciencia con su comunicado de prensa ([Sumner et al., 2014](https://www.bmj.com/content/349/bmj.g7465); [Wright y Augenstein, 2021](https://aclanthology.org/2021.emnlp-main.845); [Pei y Jurgens, 2021](https://arxiv.org/abs/2109.14776)). Código: `radar.nlp.discrepancia`, sobre lo que entrega la capa 3.

**Por qué cambió el plan** (exploración del 7-nov con los titulares y resúmenes de 1.683 notas ya vistas, sin validar):
- **La escala del Pacífico central.** "Muy fuerte" es la escala del Pacífico central y el ENFEN también la usa para Niño 3.4, desde el N.° 13. Comparar solo con la costa marcaba esos casos como contradicción.
- **Fuentes que se adelantan.** Casi todas las "contradicciones" restantes aparecieron más de 8 días después del último comunicado y venían de la NOAA o el Senamhi, o se adelantaron a lo que el ENFEN dijo después.
- **La certeza.** El ENFEN da todas sus magnitudes con cautela (89 de 89 frases). Algunos titulares las dan en futuro simple ("será moderado", "provocará").

**Referencia de cada comunicado:**
- **Costa:** el estado del encabezado, `magnitudes_mencionadas` de `comunicados.csv` y los segmentos de `temporalidad.oficial`.
- **Pacífico central:** las magnitudes de las frases que hablan de esa región, más las frases sin región de los párrafos `nino_3.4`.
- Las fechas se comparan solo en la costa.

**Afirmaciones evaluables:**
- Región costa, Pacífico central, ambas o ambigua.
- Momento actual.
- Ni negada, ni explicativa, ni pregunta.
- Las que se atribuyen a otra agencia (NOAA, OMM) o a otro país quedan como **de otra fuente** y no se comparan.

**Categorías de cada dato:**

| Dimensión | Categoría | Regla |
|---|---|---|
| Dato (magnitud, estado, fechas) | respaldada | Está en el comunicado vigente, en la escala de la afirmación. Si la región es ambigua, vale cualquiera de las dos escalas. |
| | desactualizada | Solo está en un comunicado anterior (se guarda cuántos atrás). |
| | sin respaldo | Una magnitud "posible" que no está en lo oficial, o una fecha de algo de lo que el ENFEN no da plazo. |
| | contradice | El resto. |
| Escala | otra escala | Dice "costero" con una magnitud que solo está en el Pacífico central, o al revés. |
| Tiempo (solo en el análisis retrospectivo) | adelantada | Lo que no tenía respaldo aparece en uno de los dos comunicados siguientes, dentro de 30 días. |
| Certeza | más certeza que lo oficial | Un pronóstico con magnitud en futuro simple y sin ninguna cautela ("podría", "se espera", "probable", condicional). |
| Dirección | mayor, igual o menor | Frente a la magnitud máxima de su escala. Solo descriptiva. |

**Nota y semáforo:**
- 🔴 si alguna afirmación evaluable contradice.
- 🟡 si hay alguna desactualizada, sin respaldo, de otra escala o con más certeza.
- 🟢 si todas están respaldadas.
- Sin afirmaciones: solo la distancia con minilm, con los umbrales del README y sin los párrafos de `definicion`.

El NLI queda fuera de esta capa. Su único intento se decide después, solo para frases sin datos.

**Muestra:** 200 de las notas sobre El Niño que nadie ha visto, en proporción por medio, con la semilla `capa5-validacion-7nov`. Se agregan a `notas_vistas.csv`.

**Criterios (fijados el 7-nov, antes del código):**

| | Prueba | Umbral |
|---|---|---|
| C1 | Lógica: casos sintéticos, al menos uno por categoría | 100 % |
| C2 | Pares naturales: cada frase oficial frente a su propio comunicado, y la magnitud costera y el estado frente a los demás (lo esperado sale de `comunicados.csv`) | ≥ 98 % respaldada con el suyo; ≥ 95 % de la categoría esperada con los demás |
| C3 | Desplazamiento: en los datos que distinguen al vigente del comunicado más cercano con otros datos, el vigente es el que respalda | ≥ 80 % |
| C4 | Perturbaciones de frases respaldadas de la muestra. Cambiar la magnitud o el estado deja de respaldar y da la categoría que le toca por la historia (contradice, o desactualizada si ese valor ya se dijo antes). Cambiar el año de la fecha deja de respaldar. Cambiar el condicional por el futuro da "más certeza" | 100 % |
| C5 | Frases oficiales marcadas "más certeza" | ≤ 2 % |
| C6 | Dinámica: las desactualizadas se juntan en los 7 días después de cada comunicado y las adelantadas en los 14 días antes del siguiente | Dirección esperada; informativo si hay menos de 20 casos |

**Solo descriptivos:**
- Reparto de categorías por atribución y por origen (titular o cuerpo de la misma nota), nunca por medio.
- Rojas en las notas nuevas que citan al ENFEN hasta el 18-nov.

**Límites:**
- C2 y C3 prueban que el método es coherente y responde a los datos, no su exactitud: no hay etiquetas.
- La certeza solo se mide en un sentido: lo oficial siempre sale condicional. El otro sentido solo tiene casos sintéticos (C4).
- Antes del cálculo final hay que correr `corpus` con el comunicado N.° 20 (~13-nov).

**Precisiones al construir (7-nov), dentro de lo definido:**
- *Desactualizada* va antes que *otra escala*. Un "costero débil" cuando la costa ya es moderada está desactualizado, aunque el Pacífico central siga en débil. Sin este orden, C2 daba 13 desacuerdos frente al N.° 10.
- En C2, la frase oficial sin región hereda la de la frase anterior del párrafo ("en esta región…"), con la misma regla que construye la referencia.
- El día de emisión de un comunicado, también respalda el anterior: no se sabe la hora de la nota (regla de `radar.oficial.vigencia`).

**Ronda a (7-nov):** `python -m radar.nlp.discrepancia validar`, con 199 notas leídas de 200.

| Criterio | Resultado |
|---|---|
| C1. Lógica | 28/28 |
| C2. Frases oficiales frente a su comunicado | 138/138 |
| C2. Magnitud costera y estado frente a los demás | 1.273/1.273 |
| C3. Desplazamiento | 24/27 (0,889; IC 0,72–0,96) |
| **C4. Perturbaciones** | **42/45: no pasa** |
| C5. Certeza oficial | 0/40 |
| C6. Dinámica | 3 desactualizadas y 0 adelantadas: informativo |

- **Cobertura:** 167 de 199 notas no tienen afirmaciones evaluables, así que su color lo da la distancia. De las otras 32, 27 salen en verde, 5 en amarillo y ninguna en rojo.
- **Diagnóstico de los 3 fallos de C4 (perturbaciones de fechas) y de las 3 desactualizadas:**
  - **Rango con un solo año.** En "entre enero y marzo del 2030", el primer mes no hereda el año del segundo: es un error de la temporalidad (capa 3).
  - **La prueba cambiaba años fuera del segmento.** El año que se reemplazaba no era el del segmento respaldado: es un error de diseño de C4.
  - **Fechas económicas.** "Los próximos dos trimestres… el PBI" sale como fecha de El Niño (capa 3).
  - **Hechos pasados.** "Inició en marzo de este año" queda *desactualizada* porque el vigente ya no repite el inicio. Un hecho pasado no caduca: es un error de la regla.

**Arreglos en la capa 3 (7-nov, aprobados):**
1. En un rango, el primer mes sin año hereda el del segundo.
2. Las fechas de la economía (PBI, "trimestres", inflación, exportaciones) no son segmentos de El Niño.
3. "Agencias (especializadas) internacionales" cuenta como otra agencia.

Con los tres, los controles oficiales dan lo mismo que antes:
- T1 a T4: 32/32, 113/114, 29/31 y 19/19.
- Plazos y estado oficial de la capa 3: 15/15 y 33/33.
- C1, C2 y C5: 28/28, 138/138, 1.273/1.273 y 0/40.

**Arreglos en la capa 5 (7-nov, aprobados):**
- **A.** Un hecho ya ocurrido (un segmento que terminó, o que solo tiene inicio y ya empezó) se respalda con cualquier comunicado hasta el vigente.
- **D.** C4 cambia el año solo dentro del segmento respaldado.

**Ronda b (7-nov):** 199 notas nuevas, semilla `capa5-validacion-7nov-b`. **No pasa.**

| Criterio | Resultado |
|---|---|
| C1 · C2 · C5 | 30/30 · 138/138 y 1.273/1.273 · 0/40 |
| **C3. Desplazamiento** | **17/22 (0,773; IC 0,57–0,90): no pasa** |
| **C4. Perturbaciones** | **27/29: no pasa** |
| C6 | 3 desactualizadas, 0 adelantadas: informativo |

- **Semáforo:** 177 notas sin afirmaciones, 19 verdes, 2 amarillas y 1 roja.
- **Diagnóstico de C3:** de los 5 casos en que el vigente no respalda, 4 son discrepancias reales de terceros u otras entidades, no fallos del método:
  - Minedu, el 16-jun, dice "extraordinaria" un mes antes que el ENFEN;
  - un ingeniero da un plazo antiguo;
  - Indeci, el 11-feb, da "desde marzo".

  El quinto es un error de la capa 3: "dedicada a la vigilancia del fenómeno" sale como estado *vigilancia*. La premisa de C3 (el vigente respalda casi siempre) mezcla la validez del método con cuánto se alejan de verdad las fuentes.
- **Diagnóstico de C4:** los 2 fallos vienen del diseño de la prueba.
  - En un rango ("a finales de este año y principios de 2030"), cambiar solo el año del final deja el periodo cruzado con el oficial, y la regla aprobada lo respalda.
  - Un año como 2030 hace que la capa 3 tome la frase como histórica: `ANIO_ACTUAL` solo acepta 2025 a 2027, así que "hasta 2028" también saldría histórica (error de la capa 3).

**Cambios aprobados tras la ronda b (7-nov):**
1. *Capa 3:* "la vigilancia del fenómeno" es la actividad de monitoreo, no el estado.
2. *Capa 3:* los años de 2028 en adelante son del evento actual, no históricos.
3. *C4:* solo se perturban segmentos con todos sus años explícitos.
4. *C3:* se mide sobre lo atribuido al ENFEN y lo que no tiene atribución, que es lo que debería seguir al vigente. Lo de otras entidades y terceros se reporta aparte, como informativo. Es un cambio del criterio hecho después de ver la ronda b: se declara así.

Con estos cambios, los controles oficiales no cambian (T1 a T4, plazos, estado oficial, C1, C2, C5).

**Ronda c (7-nov):** 200 notas nuevas, semilla `capa5-validacion-7nov-c`. **Pasa.**

| Criterio | Resultado |
|---|---|
| C1 · C2 · C5 | 30/30 · 138/138 y 1.273/1.273 · 0/40 |
| C3. Desplazamiento (ENFEN y sin atribución) | 4/4 (IC 0,51–1,00) |
| C3. Otras entidades y terceros (informativo) | 4/7 |
| C4. Perturbaciones | 35/35 |
| C6 | 3 desactualizadas, 0 adelantadas: informativo |

- **Semáforo:** 173 notas sin afirmaciones, 24 verdes, 3 amarillas, 0 rojas.
- **C3 pasa con muy pocos casos (4).** El intervalo de confianza no excluye un acierto bajo, así que la evidencia de C3 es débil. Las tres rondas juntas (a, b y c) suman unos 50 casos.
- **Casos reales que el índice muestra bien:**
  - El BCR, el 3-ago, da para "fuerte" el plazo del N.° 12 ("hasta el verano de 2027"). Con la regla de lo último dicho, ese plazo sigue vigente, porque el N.° 13 no dio otro para "fuerte": queda *respaldado*.
  - Una funcionaria del Senamhi, el 27-ago, dice "muy fuerte".
- **Silencio del vigente: resuelto después** (ver abajo).
- **No hubo ninguna roja** en las 3 rondas (598 notas), salvo una de un tercero en la ronda b. Con lo oficial, las notas casi siempre coinciden o no afirman datos. Lo que más aparece es *desactualizada* y *más certeza*.

**Lo último dicho de cada escala (aprobado el 7-nov).**
- **Pacífico central:** si un comunicado no da su magnitud, vale la del último que la dio. El N.° 14 hereda "muy fuerte" del N.° 13.
- **Plazo de cada magnitud costera:** si el comunicado no lo repite y la sigue mencionando, vale el último plazo dado para ella. Cuando una magnitud se deja de mencionar, su plazo se va.
- **El evento no se hereda.** Su fin viene en cada comunicado, y su inicio ya ocurrido lo cubre la regla de los hechos pasados.
- **Casos sintéticos:** 3 nuevos en C1, que queda en 33/33. C2 y C5 no cambian.

**Ajuste de la regla de "vigilancia" (7-nov).** Al repetir las rondas, la regla nueva también descartaba "la vigilancia de Niño Costero que mantiene vigente el Perú", que sí es el estado. Ahora "la vigilancia" es actividad solo si sigue "del fenómeno", "permanente", "del mar" o algo parecido. El estado oficial sigue en 33/33.

**Diagnóstico con el código final** (las rondas a y b sirvieron para corregir, así que no son independientes):

| Ronda | C3 (ENFEN y sin atribución) | C3 terceros (informativo) | C4 | Semáforo |
|---|---|---|---|---|
| a | 15/15 | 6/6 | 40/40 | 168 sin afirmaciones · 29 🟢 · 2 🟡 |
| b | 4/4 | 13/17 | 28/28 | 177 · 19 🟢 · 2 🟡 · 1 🔴 |
| c | 4/4 | 7/7 | 38/38 | 173 · 24 🟢 · 3 🟡 |

- Juntas, las tres rondas dan **C3 = 23/23** y **26/30 en terceros**. No son 23 casos independientes: la evidencia de C3 sigue siendo débil, y se declara así.
- Con la herencia, el único cambio en la ronda c es el "muy fuerte" del Senamhi del 27-ago, que pasa a *respaldada*. Su fecha ("muy fuerte en enero de 2027") sigue *sin respaldo*, porque las fechas del Pacífico central no se comparan.
- Las 242 notas sobre El Niño que quedan sin ver se reservan para T5. No hay una ronda d.

## Distancia en el semáforo (punto 5.1; definición aprobada el 7-nov)
**Qué hace:** una función única, `radar.nlp.semaforo.medir_discrepancia(texto, fecha)`, para la app, el agente y los videos. Une la capa 5 con la distancia de minilm a los párrafos oficiales. Entre el 84 y el 89 % de las notas no tiene afirmaciones evaluables, así que su color lo da la distancia.

**Exploración previa** (texto corto, sin red, con los controles de E3 ya vistos; no es validación):

| Variante (minilm, texto corto) | E3 | E4 | Definición elegida | Recomendación elegida |
|---|---|---|---|---|
| Todo el ENFEN | 0,877 | 0,832 | 4 % | 29 % |
| Vigentes | 0,864 | 0,859 | 3 % | 43 % |
| Vigentes sin `definicion` | 0,865 | 0,862 | 0 % | 44 % |
| Vigentes sin `definicion` ni `recomendacion` | 0,873 | 0,800 | 0 % | 0 % |
| Vigentes con corrección de hubness (CSLS) | 0,877 | 0,850 | 5 % | 33 % |

- **El 11,5 % de embeddings.md es de e5 frente a todo el ENFEN.** Con minilm y los vigentes, la definición es el párrafo elegido solo en el 3 %. El "imán" es el párrafo genérico de recomendación ("Se recomienda a los tomadores de decisiones…"), pero ese párrafo sí aporta tema: quitarlo baja E4 a 0,800.
- **El control positivo de E3 tenía citas falsas.** El nivel `numero` de `rasgos.comunicados_citados` toma cualquier "Comunicado N.°" (FAP, PNP, Minedu): 11 de los 41 positivos no mencionan El Niño. Con los 41, el p25 del positivo tiene un IC del 95 % de 0,20 a 0,53 y el 17 % de los positivos caería en "lejano". Con el **positivo limpio** (los 30 que mencionan El Niño), E3 en corto es 0,993, el IC del p25 va de 0,48 a 0,67 y ningún positivo queda lejano. El arreglo de `rasgos` queda para el recálculo final ([../pendientes.md](../pendientes.md)), y los E3 del 1-nov se declaran como medidos con ese control.
- **Corto y cuerpo se separan solos:** el titular con el resumen llega a 74 palabras en el p99; el cuerpo, a 117 en el p1.

**Decisiones:**
1. **Párrafos:** los del ENFEN vigentes en la fecha (`candidatos.vigentes`, la misma regla de `vigente_desde` y `vigente_hasta`), sin los de `definicion`. Los de `recomendacion` se quedan.
2. **Puntaje:** el coseno máximo de minilm entre los tramos del texto y los de cada párrafo, como en B.
3. **Tipo de texto:** corto si tiene 100 palabras o menos; si no, cuerpo. Cada tipo tiene sus umbrales. Con menos de 5 palabras, "texto insuficiente".
4. **Umbrales (README, ajustado):** *cercano* si el coseno llega al p95 del control negativo (`otros_temas`, 400 notas); *lejano* si no pasa del p75 del negativo; *intermedio* entre ambos. El verde sale del negativo porque el p25 de un positivo chico es inestable. Si un tipo no pasa E3 (AUC < 0,80 con el positivo limpio, o p25 del positivo ≤ p75 del negativo), ese tipo muestra la distancia sin color.
5. **Combinación, por orden:** si hay afirmaciones evaluables, el color es el de la capa 5 (rojo, amarillo o verde). Si no, lo da la distancia: verde (cercano), amarillo (intermedio) o **gris (lejano)**. **Lejos no es contradecir:** el rojo queda solo para "contradice". Es un cambio frente al README ("distancia por encima del p25 del negativo → rojo") que se declara.
6. **Salida:** el color, su origen (reglas o distancia), el tipo de texto, el coseno, la banda, el párrafo más parecido (id y tipo), los umbrales y las filas de la capa 5. Las dos señales se entregan aunque mande una.

**Criterios (fijados el 7-nov, antes del código):**

| | Prueba | Umbral |
|---|---|---|
| S1 | Lógica de la combinación y de las bandas (casos sintéticos) | 100 % |
| S2 | E3 con la configuración final y el positivo limpio, en corto y cuerpo por separado | AUC ≥ 0,80 y p25 del positivo > p75 del negativo |
| S3 | **Negativos nuevos:** 400 notas de otros temas no vistas (100 por medio, con la definición de `otros_temas`) en corto, sin red, y 100 de ellas (25 por medio) en cuerpo | Cercano ≤ 10 %; lejano ≥ 60 %, en cada tipo |
| S4 | **Positivos nuevos:** los párrafos de `resumen` de cada comunicado (sin duplicados), frente a los párrafos vigentes el día anterior a su emisión, en corto | Lejano ≤ 25 % |
| S5 | Las notas de las muestras con afirmaciones evaluables conservan el color de la capa 5 | 100 % |
| S6 | Tiempo por consulta (mediana de 20 textos cortos) | ≤ 2 s |

**Cambio aprobado al construir (7-nov):** S4 iba a usar las 23 notas no vistas que citan un comunicado, pero todas son citas falsas de otras entidades, y las demás notas sobre El Niño están vistas o reservadas para T5. Se reemplazó por texto oficial. Como el comunicado repite mucho del anterior, S4 es una prueba fácil: solo descarta un fallo grueso. En cuerpo no hay positivo nuevo, y se declara. Los comunicados casi no traen titular (3 de 20), así que se usan sus párrafos de resumen.

**Muestras:** semilla `semaforo-negativos-7nov`, que se agrega a `notas_vistas.csv`. La calibración de cuerpos lee los 430 controles (no es un recálculo).

```bash
python -m radar.nlp.semaforo muestra     # elige los negativos nuevos y los agrega a notas_vistas
python -m radar.nlp.semaforo calibrar    # umbrales de corto (sin red) y de cuerpo (pide páginas)
python -m radar.nlp.semaforo validar     # S1 a S6 (pide páginas para los 100 cuerpos nuevos)
```

**Resultado (7-nov): pasa.** La calibración leyó 430 cuerpos en 2,8 min y la validación, 100 en 1,1 min, sin errores. Los umbrales quedan en `config/semaforo_umbrales.csv` (solo cosenos y AUC), que la app necesita.

| Criterio | Resultado |
|---|---|
| S1. Lógica | 21/21 |
| S2. E3 en corto | 0,993 (IC 0,985–0,999); p25 del positivo 0,552 > p75 del negativo 0,302 |
| S2. E3 en cuerpo | 1,000 (IC 1,000–1,000); 0,808 > 0,448 |
| S3. Negativos nuevos en corto (400): cercano / lejano | 0,058 / 0,730 |
| S3. Negativos nuevos en cuerpo (100): cercano / lejano | 0,060 / 0,760 |
| S4. Resúmenes del ENFEN frente al comunicado anterior (93): lejano | 0,000 (todos cercanos) |
| S5. Con afirmaciones, manda la capa 5 | 29/29 |
| S6. Tiempo por consulta | 0,023 s |

**Umbrales:** corto cercano ≥ 0,411 y lejano ≤ 0,302; cuerpo cercano ≥ 0,545 y lejano ≤ 0,448.

**Lecturas críticas:**
- **S2 en cuerpo (1,000) y S4 son fáciles.** Las notas de Andina que citan un comunicado lo resumen casi al pie de la letra, y cada comunicado repite mucho del anterior. Solo descartan un fallo grueso. El lado positivo no tiene una muestra nueva independiente: el control limpio son 30 notas ya vistas.
- **S5 se apoya solo en los positivos de la calibración.** Ninguno de los 100 negativos nuevos tenía afirmaciones evaluables. Es un control de integración: el color de la capa 5 llega intacto.
- **La separación es de tema, no de alineación** (como E3 y E4): una nota sobre El Niño que habla de otro aspecto puede salir intermedia o lejana. Por eso lo lejano es gris, no rojo. El E4 de minilm en texto corto (0,860) sigue debajo de 0,90 y se declara.
- **Informativo:** en los 30 positivos, la capa 5 da 24 verdes, 3 amarillas, 2 rojas y 1 sin afirmaciones.

**Diagnóstico de las 5 notas no verdes del control positivo (8-nov).** Se releyeron en memoria; ya estaban vistas.
- **3 amarillas, bien:** dos dan la magnitud en futuro simple ("ratifica que evento será moderado", "pasará a magnitud moderada") y una da fechas de un comunicado anterior.
- **Roja real (Andina 1079643, 1-jul):** atribuye al ENFEN "moderado hasta diciembre de 2027", cuando el comunicado decía diciembre de 2026. El método mide bien la distancia; no dice si es una errata.
- **Roja por error de la capa 3 (Andina 1085001, 25-jul):** el subtítulo "Estudio sobre el Fenómeno de El Niño hacia 2030" salía como fin del evento. Además, esa nota solo era positiva por el "Comunicado 004-2026/Ceplan" ([../noticias/definicion.md](../noticias/definicion.md#citas-por-número-sin-el-enfen-arreglo-del-8-nov-2026)).

**Arreglo en la capa 3 (8-nov):** "hacia" seguido solo de un año ("hacia 2030") es un horizonte, no el fin del evento. "Hacia el otoño de 2027" sigue contando, y "hasta 2027" también. Los controles oficiales no cambian: T1 a T4 dan 32/32, 113/114, 29/31 y 19/19; C1, C2 y C5, 33/33, 138/138 y 1.273/1.273, y 0/40. En los 100 cuerpos nuevos, 76 grises, 18 amarillos y 6 verdes, y el párrafo más parecido es de `recomendacion` en 51.

## Configuración del NLI (si se usa)
- Modelo `MoritzLaurer/mDeBERTa-v3-base-xnli-multilingual-nli-2mil7` (MIT; 83,2 % en XNLI en español).
- **Cargar con `dtype=torch.float32`.** `transformers` 5.x lo carga en float16, el formato en que está guardado, y en CPU eso es de 6 a 18 veces más lento con los mismos resultados.
- 12 hilos, sin lotes; 0,1-0,4 s por par.
- La versión cuantizada (ONNX) cambia las respuestas: descartada.
- En la laptop del equipo (i9-13900H) hace falta estar enchufada, con Windows en "Máximo rendimiento" y ASUS en "Rendimiento dinámico" (Fn + F). Si no, todo va de 3 a 8 veces más lento.
- `torch` no está en `pyproject.toml`: se instala para CPU con `pip install torch --index-url https://download.pytorch.org/whl/cpu`.
