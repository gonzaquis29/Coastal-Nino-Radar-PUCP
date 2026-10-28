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
3. **Datos ya vistos no se reusan para evaluar:**
   - las 66 frases (39 notas) del control de Andina del piloto;
   - las 200 notas al azar del piloto (semilla 656);
   - las muestras de exploración de la capa 3 (semilla "capa3-exploracion").

## Flujo por capas
| Capa | Responsabilidad | Estado |
|------|-----------------|--------|
| 1. Texto limpio | Cuerpo en líneas y sin bloques ajenos (`noticias/nota.py`) | **Hecha** (28-oct): [../noticias/texto.md](../noticias/texto.md) |
| 2. Corpus oficial limpio | Sin encabezados de tabla; `tipo` y `region_enso` por párrafo (`oficial/`) | **Hecha** (28-oct): [../oficial/definicion.md](../oficial/definicion.md) |
| 3. Frases y afirmaciones | Qué dato afirma cada frase, quién lo dice, de cuándo, con qué seguridad | **Definida** (abajo), sin construir |
| 4. Referencia oficial | Comunicado vigente y anterior de cada nota, con datos comparables (plazos en mes y año) | Por definir; `radar.oficial.vigencia.Corpus` ya da el vigente |
| 5. Comparación | Reglas por dato + distancia (+ NLI acotado) → índice y semáforo | Por definir; evaluación descrita abajo |

## Capa 3: frases y afirmaciones (definición aprobada para construir)
**Responsabilidad única:** partir el texto limpio en frases y, de cada frase que afirma algo sobre El Niño, sacar qué dato afirma, quién lo dice, de qué momento habla y con qué seguridad. No compara con lo oficial. Va en `src/radar/nlp/`.

1. **Frases** de titular, resumen y cuerpo, marcadas con su origen. Se parte por línea y luego por fin de frase, también tras cifras y comillas. Las líneas de menos de 5 palabras son subtítulos y no cuentan como afirmación.
2. **Afirmación:** frase que nombra El Niño (o el Niño costero, o el ENFEN) y tiene al menos un dato:
   - **magnitud,** solo pegada a El Niño o a "magnitud" o "evento", con las reglas de `oficial/enfen.py`, que separan lo principal de lo posible. `rasgos.magnitudes`, la regla laxa, pasa a usar esa misma: una sola definición;
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
