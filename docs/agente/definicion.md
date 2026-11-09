# Agente con herramientas

Módulo: `python -m radar.agente.agente validar` (`src/radar/agente/`). El agente recibe una pregunta o un texto, elige una herramienta, extrae sus parámetros y arma la respuesta con una plantilla y citas literales de los textos oficiales. No usa ningún LLM: el enrutador combina reglas y embeddings (decisión del 9-nov).

## Medición previa (9-nov)

- No hay clave de ninguna API de LLM ni Ollama instalado. ChromaDB tampoco está instalado.
- `buscar_oficial` solo existía como evaluación (`radar.nlp.recuperador`), no como función. Por eso se escribe ahora con minilm, el modelo elegido en E, sobre los párrafos vigentes. El índice va en memoria con numpy: con 865 párrafos da el mismo orden que ChromaDB. Si se quiere usar ChromaDB, queda detrás de la misma interfaz.
- Las 1.827 preguntas del recuperador (6-nov) salen de solo 21 redacciones distintas. Por eso, además, se congelan 46 redacciones nuevas en `config/agente_preguntas.csv` y A1 se promedia por redacción.

## Enfoques

| Enfoque | Decisión |
|---|---|
| LLM por API que elige la herramienta | Descartado por ahora: no hay clave, tiene costo y límite, y hay que declararlo |
| LLM local pequeño en CPU | Descartado: varios segundos por consulta |
| **Reglas para lo inequívoco y embeddings para el resto** | **Elegido** |
| Clasificador zero-shot con mDeBERTa | Descartado: lento y débil en frases sin datos (punto 5.2) |
| Clasificador entrenado con plantillas | Descartado: circular |
| Sin enrutador (el usuario elige la pestaña) | Ya lo cubre la pestaña Consulta |

## Herramientas (qué responde cada una)

| Herramienta | Para qué | Parámetros |
|---|---|---|
| `estado_vigente` | Estado y nivel que rigen: alerta del ENFEN, magnitud prevista, avisos vigentes | fecha, macro-región |
| `buscar_oficial` | Contenido de los textos oficiales: pronóstico, impactos, pesca, recomendaciones, avisos del día | consulta, fecha |
| `medir_discrepancia` | Un texto o una afirmación que se quiere contrastar ("¿es cierto que…?", un titular) | texto, fecha |
| `recomendar` | Qué leer o revisar según el perfil | fecha, macro-región, interés |
| (ninguna) | Fuera de alcance: no trata de El Niño, el clima ni las fuentes oficiales | — |

- **Fecha:** la del texto ("15 de marzo", "hoy", "mañana"); si no hay, la de la consulta. Sin año, se toma el que deja la fecha entre 300 días antes y 60 después de la consulta.
- **Macro-región:** la de `radar.comun.regiones` (expresiones como "costa norte" y departamentos); si no hay, la del perfil.
- **Interés:** pesca, lluvias, calor o prevención, como en el recomendador.

## Evaluación (congelada el 9-nov, antes de escribir el enrutador)

1. **Redacciones nuevas** (`config/agente_preguntas.csv`): 10 de estado, 10 de búsqueda, 8 de recomendación, 8 de contraste y 10 fuera de alcance.
   - `{region}` toma 4 valores: "la costa norte", "la costa centro", "Lima" y "Piura".
   - `{dia}` toma 2: "15 de marzo" y "2 de octubre", con la consulta el 9-nov-2026.
2. **Preguntas del recuperador** (cada una se hace en su propia fecha: con la consulta el 9-nov, "1 de enero" sería el próximo año; ajuste del 9-nov, antes de medir):
   - El grupo A (contenido del ENFEN) y el C (pronóstico del Senamhi por día) van a `buscar_oficial`.
   - El grupo B se reparte por redacción. "¿Qué aviso hay…?" y "¿Hay alerta…?" van a `estado_vigente`, y también se acepta `buscar_oficial`. "¿Qué advierte…?" va a `buscar_oficial`, y también se acepta `estado_vigente`.
3. **Titulares de notas (informativo):**
   - Titulares sin ver que mencionan El Niño, fuera de la muestra A del recomendador, van a `medir_discrepancia`.
   - Titulares sin ver de otros temas (la definición del control negativo) van a fuera de alcance.
   - Es informativo porque la etiqueta sale de `rasgos`, que el enrutador también puede usar. Se agregan a `notas_vistas`.

El enrutador no usa como ejemplos ninguna de estas redacciones: solo la descripción de cada herramienta y reglas por palabras.

**Criterios:**

| | Prueba | Umbral |
|---|---|---|
| A1 | Herramienta correcta (o aceptable), promediada por redacción, en 1 y 2 | ≥ 90 % |
| A2 | Fecha, macro-región e interés extraídos bien, donde la pregunta los da | ≥ 95 % |
| A3 | Citas de la respuesta que existen literalmente en el párrafo fuente | 100 % |
| A4 | Fuera de alcance: las redacciones F terminan sin herramienta, y las válidas casi nunca | ≥ 90 % y ≤ 5 % |
| A5 | Tiempo por consulta (mediana) | ≤ 2 s |

## Resultado (ronda a, 9-nov)

**No pasa.** Duración: 5,2 min (`data/processed/agente/validacion.csv`).

| | Resultado | ¿Pasa? |
|---|---|---|
| A1 | 0,83 por redacción (45) | No |
| A2 | 2.279/2.279 | Sí |
| A3 | 3.979/3.979 | Sí |
| A4 | F: 10/10 sin herramienta; válidas: 0/1.905 abstenciones | Sí |
| A5 | mediana 0,10 s (máximo 132 s: la primera consulta carga los modelos) | Sí |

Informativo: 13 de 100 titulares sin ver que mencionan El Niño van a contrastar (85 se quedan fuera del dominio: el titular no trae las palabras que `rasgos` encuentra en el cuerpo); 100/100 de otros temas quedan fuera de alcance.

**Diagnóstico.** Casi todo el fallo está en `recomendar` (R02, R03, R04, R06 y R08 en 0; R07 en 0,5) y en dos búsquedas que caen en estado (B01, B03). La descripción de `recomendar` compite mal por embeddings con las de contenido: "me preocupan las lluvias" se parece más a buscar. R03, una orden sin "?", la toma la regla de afirmación sin pregunta. Cualquier regla escrita ahora para esto se ajustaría a las redacciones congeladas, así que la ronda a queda como resultado y un cambio necesita una ronda b con redacciones nuevas congeladas antes.

## Ronda b (aprobada el 9-nov; congelada antes de cambiar el enrutador)

**Cambio previsto** (genérico, no copiado de las redacciones):
- Una regla de pedido de recomendación ("recomiéndame", "qué me sugieres", "qué debería leer o revisar", "qué fuentes", "dónde me informo") va a `recomendar`, salvo que el sujeto sea una fuente oficial ("qué recomienda el ENFEN" es búsqueda).
- La regla de afirmación sin "?" no toma las órdenes (frases que empiezan con un imperativo como "dime", "explícame" o "resume").

**Evaluación:** 38 redacciones nuevas en `config/agente_preguntas_b.csv` (6 de estado, 8 de búsqueda, 12 de recomendación, 6 de contraste y 6 fuera de alcance), con los mismos valores de `{region}` y `{dia}`. Incluyen trampas a propósito: "¿Qué recomienda el ENFEN…?" (búsqueda), "Recomiéndame una película" (fuera de alcance), "¿Es real que…?" (contraste sin las palabras de la regla) y pedidos sin "?".

**Criterios:** los mismos A1 a A5 y umbrales, sobre las redacciones b y las preguntas del recuperador. Las redacciones de la ronda a se reportan solo como informativas, porque el cambio se decidió mirándolas. No se usan titulares: el cambio no los toca y no gasta notas sin ver.

### Resultado de la ronda b (9-nov)

**No pasa A1: 0,874** (umbral 0,90; 41 redacciones). A2 (2.265/2.269), A3 (4.006/4.006), A4 (6/6 y 0 abstenciones) y A5 (mediana 0,12 s) pasan. Detalle: `data/processed/agente/agente-b.csv`.

- **Recomendación:** pasa de casi 0 a 10 de 12 redacciones. Fallan "Necesito información para…" (sin "?" y sin imperativo: la toma la regla de afirmación) y "¿Qué comunicados y notas me sirven…?" (no trae ninguna palabra de la regla).
- **Contraste sin las palabras de la regla:** "¿Es real que…?" y "Vi en redes que… ¿Es así?" caen en estado. Las trampas que sí resolvió: "¿Qué recomienda el ENFEN…?" va a búsqueda y "Recomiéndame una película" queda fuera de alcance.
- **Búsqueda:** "¿Cómo afectaría El Niño a la agricultura del norte?" cae en estado.
- El recuperador no cambia (recuperador-A0 sigue en 0,84). Las redacciones de la ronda a, ya vistas, suben de 0,83 a 0,94.

Ajustar ahora las reglas a estos 5 casos sería repetir el ajuste a lo visto. Cada ronda con reglas cubre las frases que se previeron y falla en las que no: es el límite del enfoque sin LLM.

## Ronda c (aprobada el 9-nov): desarrollo y prueba separados

**Por qué:** con 41 redacciones, el intervalo de confianza del 95 % de A1 en la ronda b va de 0,77 a 0,97, y cada redacción mueve 2,4 puntos. Además, cada ronda gastó su conjunto de prueba al mirar los fallos. El error más frecuente es búsqueda → estado (16 casos).

**Conjunto de prueba** (`config/agente_preguntas_c.csv`, congelado antes de escribir el de desarrollo y de afinar nada): 150 redacciones (30 de estado, 35 de búsqueda, 30 de recomendación, 30 de contraste y 25 fuera de alcance). La columna `tipo` las reparte en P (pregunta directa), S (sin "?"), O (orden), C (coloquial o sin tildes) y T (trampa con palabras de otra herramienta). Se corre **una sola vez**, con el enrutador ya elegido.

**Conjunto de desarrollo** (`config/agente_preguntas_dev.csv`): redacciones distintas, sobre las que se puede afinar libremente: ejemplos por herramienta en vez de descripciones, minilm frente a e5, una regla de margen entre estado y búsqueda, y reglas.

**Criterios en la prueba c:**

| | Prueba | Umbral |
|---|---|---|
| A1 | Herramienta correcta, promedio por redacción, con IC 95 % por bootstrap de redacciones | ≥ 0,90 (valor puntual; el límite inferior se declara) |
| A2 a A5 | Igual que en la ronda a | Iguales |
| A6 | Preguntas del recuperador (ya vistas): sin retroceso | ≥ 0,95 por redacción |

Informativo: A1 por tipo, y las redacciones de las rondas a y b. **Límite declarado:** la IA escribe los dos conjuntos, así que no son del todo independientes. Para mitigarlo, la prueba se escribió primero y por tipos fijados de antemano.

### Desarrollo (9-nov)

Se midió con validación cruzada dejando fuera cada redacción del conjunto de desarrollo (120 redacciones), solo el enrutamiento:

| Enrutador | A1 en desarrollo |
|---|---|
| Ronda b (reglas + descripciones con minilm) | 0,662 |
| Reglas + kNN sobre los ejemplos (e5, k = 5) | 0,750 |
| **Reglas + regresión logística sobre TF-IDF de palabras y caracteres + e5 (peso 3, C = 100)** | **0,910** |

- Los embeddings solos captan el tema y no la intención: "¿Hay aviso en la costa norte?" se acercaba a los pedidos de recomendación que nombran una región. Por eso las regiones y fechas se reemplazan por `LUGAR` y `FECHA` antes de clasificar.
- La regla de afirmación sin "?" se quitó, porque tomaba pedidos como "Necesito…" o "Quiero…". El filtro de dominio se amplió (vigilancia, cálidas, Pacífico, inundará, etc.).
- Varias configuraciones quedan entre 0,89 y 0,91, así que elegir la mejor tiene algo de optimismo. El enrutador quedó en el commit 30a4996 antes de correr la prueba.

### Resultado de la ronda c (9-nov, una sola corrida)

**Pasa.** Detalle: `data/processed/agente/agente-c.csv`.

| | Resultado | Umbral |
|---|---|---|
| A1 | **0,944** (125 redacciones válidas); IC 95 % de 0,904 a 0,984 | ≥ 0,90 |
| A2 | 260/269 (0,967) | ≥ 0,95 |
| A3 | 375/375 | 100 % |
| A4 | F: 0,96 (24 de 25); válidas: 0,004 | ≥ 0,90 y ≤ 0,05 |
| A5 | mediana 0,04 s | ≤ 2 s |
| A6 | recuperador 1,00 | ≥ 0,95 |

- Por tipo: coloquial 1,00, pregunta directa 0,96, sin "?" 0,91, orden 0,90 y trampa 0,86.
- Fallan 7 redacciones, entre ellas "Cuéntame qué pronostica…", "¿Qué recomienda el Senamhi…?" y "Pronostican lluvias torrenciales…".
- A2 pierde 9 casos de interés: "pesquero", "Pesco" y "río" con tilde no los reconoce la regla. No se corrige, porque se vio en la prueba.
- Informativo: las redacciones de las rondas a y b dan 1,00. Confirma el límite declarado: todos los conjuntos los escribió la IA, con un estilo parecido. En el uso real, con redacciones de otras personas, el acierto puede ser menor. El agente queda validado frente a estas redacciones, no frente a usuarios reales.
