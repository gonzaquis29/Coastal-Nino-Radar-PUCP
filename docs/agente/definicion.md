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
2. **Preguntas del recuperador:**
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
