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
| 5. Comparación | Reglas por dato + distancia (+ NLI acotado) → índice y semáforo | Por definir; evaluación descrita abajo |

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

## Capa 5: cómo se evalúa (para definir en detalle)
Cada método se evalúa con los mismos conjuntos, con criterios fijados antes y los umbrales calibrados con datos aparte:

1. **Contradicciones sintéticas.** Un piso mínimo; no basta.
2. **Pares naturales de la historia del ENFEN.** El estado pasó de Vigilancia a Alerta el 13-feb y la magnitud subió de débil a moderada (15-may), fuerte (15-jun) y extraordinaria (14-ago). Las frases de comunicados con datos distintos son contradicciones reales; las de comunicados con los mismos datos, paráfrasis reales. Se calibra con enero a junio y se evalúa con julio a octubre.
3. **Notas nuevas que citan un comunicado.** Mide falsas alarmas en noticias reales, reportadas por medio.
4. **Muestra al azar.** Solo descriptiva: cuántas alarmas da cada método y cuánto coinciden.

El índice separa **"contradice"** de **"desactualizada"**: una nota que reporta bien un comunicado anterior.

## Configuración del NLI (si se usa)
- Modelo `MoritzLaurer/mDeBERTa-v3-base-xnli-multilingual-nli-2mil7` (MIT; 83,2 % en XNLI en español).
- **Cargar con `dtype=torch.float32`.** `transformers` 5.x lo carga en float16, el formato en que está guardado, y en CPU eso es de 6 a 18 veces más lento con los mismos resultados.
- 12 hilos, sin lotes; 0,1-0,4 s por par.
- La versión cuantizada (ONNX) cambia las respuestas: descartada.
- En la laptop del equipo (i9-13900H) hace falta estar enchufada, con Windows en "Máximo rendimiento" y ASUS en "Rendimiento dinámico" (Fn + F). Si no, todo va de 3 a 8 veces más lento.
- `torch` no está en `pyproject.toml`: se instala para CPU con `pip install torch --index-url https://download.pytorch.org/whl/cpu`.
