# App: definición (borrador 3, aprobado el 19-nov-2026)

La app se compone de una API en FastAPI (`src/radar/app/`) y una interfaz en React con Vite y TypeScript (`web/`). Se decidió el 19-nov en lugar de Streamlit ([README](../README.md#despliegue)). Corre en local con un solo comando, en `http://localhost:8000`.

**Estado al 19-nov:** el paso 1 del orden de construcción (la API) está hecho y pasa P1 a P5, y la paleta pasa P9 (sección 8). La interfaz (`web/`) no está empezada: se construye cuando el equipo lo decida.

Este borrador parte de quién la usa y de lo que muestran nuestros datos. Cada decisión lleva su porqué, y lo que se puede comprobar tiene un criterio en la sección 6.

## 1. Quién la usa y qué necesita

| Persona | Situación | Qué necesita | Qué no necesita |
|---|---|---|---|
| **Ciudadano de la costa** (usuario principal): por ejemplo, un pescador de Paita o una madre de familia de Piura | Le llega un titular o un mensaje por WhatsApp o Facebook, y lo lee en el celular, a veces con datos móviles limitados | Saber en segundos si eso coincide con lo oficial, qué está vigente en su zona y qué hacer. Poder reenviar la respuesta | Términos técnicos, gráficos, cifras de validación |
| **Periodista o analista** (secundario) | Escribe sobre El Niño desde una computadora | El panorama de 2026 con cifras que pueda citar y descargar, y saber qué tan confiable es cada cifra | Que se le explique qué es El Niño |
| **Evaluador del curso** | Ve la app en la presentación | Ver los métodos del curso aplicados y cómo se validaron | Que la metodología invada las pantallas del ciudadano |

## 2. Lo que dicen los datos sobre cómo se usará

| Hecho medido | De dónde sale | Qué implica para el diseño |
|---|---|---|
| De los 2.727 titulares reales sobre El Niño, **el 94 % se decide por distancia y solo el 6 % trae datos comparables** (magnitud, estado o fechas) | Medido el 19-nov con `semaforo.medir_discrepancia` sobre los titulares de `notas.csv` | El caso principal es el texto **sin datos**, y ese es el que hay que diseñar primero |
| Por distancia, un verde solo dice que el texto **habla de lo mismo** que el comunicado vigente, no que sea cierto. De los titulares, el 66 % sale verde | Definición del semáforo; misma medición | Si se usa el semáforo, el ciudadano leería "verde = es verdad" en 2 de cada 3 consultas. Cuando no hay datos, **no se muestra un semáforo** |
| En T5, las 2 rojas eran errores de extracción | `discrepancia.md`, T5 | El rojo se presenta como "no coincide", con la comparación a la vista para que el usuario juzgue, y nunca como "falso" |
| El 74 % de las notas completas tampoco trae datos | Capa 5 sobre todas las notas | El Panorama también tiene que mostrar ese 74 %, no solo los colores |
| El titular mediano tiene 14 palabras | `notas.csv` | Un cuadro de 2 a 3 líneas que crece si se pega un texto largo |
| Una consulta tarda unos 0,02 s | S6 y la misma medición | El resultado aparece al instante: no hace falta pantalla de espera, salvo en el arranque |

## 3. Decisiones de diseño, con su porqué

**D1. Dos tipos de resultado, no uno.** El modelo no cambia; cambia cómo se presenta.
- **Con datos comparables (6 %):** el veredicto dice en palabras simples qué pasa con cada dato.

| Resultado del dato | Se muestra como |
|---|---|
| respaldada | ✓ **Coincide con el ENFEN** |
| desactualizada | ! **Usa un dato anterior del ENFEN** |
| sin respaldo | ! **El ENFEN no dice eso** |
| más certeza | ! **Lo afirma con más seguridad que el ENFEN** |
| otra escala | ! **Usa otra escala** (por ejemplo, la del Pacífico central) |
| contradice | ✕ **No coincide con el ENFEN** |

- **Sin datos (94 %):** no hay veredicto. Se muestra "**Cercanía con lo que dice hoy el ENFEN:** alta, media o baja" en un medidor de un solo tono, sin verde, amarillo ni rojo. Lo acompaña la frase: "Este texto no trae datos que podamos comparar (magnitud, estado o fechas). Solo medimos si habla de lo mismo que el comunicado vigente, no si es cierto".
- **Por qué:** cuando no hay datos, un color de semáforo promete un juicio que no hacemos.
- **Efecto en el README:** la clasificación interna (verde, amarillo y gris por distancia) sigue igual, y la sección "Producto" se actualiza con esta forma de presentarla.

**D2. El ciudadano tiene una sola pantalla para su tarea: Verificar.**
- La pantalla "Hoy" del borrador anterior se elimina. El estado vigente va en una línea arriba del cuadro.
- **Por qué:** su tarea empieza con un texto en la mano. Una portada previa agrega un paso sin resolver nada.

**D3. Lo mínimo se pide antes y el resto después.**
- **Antes:** solo el texto. La macro-región se pide una vez y se recuerda en el navegador; se puede cambiar en la línea de estado.
- **La fecha** es hoy por defecto, con un enlace "¿Es de otra fecha?".
- **El interés** se elige después del resultado, en "Qué hacer", con chips opcionales.
- **Por qué:** cada campo antes del botón es una razón para abandonar. El interés solo afecta a las recomendaciones.

**D4. El detalle se abre a pedido.**
- El resultado muestra el veredicto y una frase; "Ver por qué" despliega el resto:
  - la comparación lado a lado, con hasta 3 afirmaciones más "ver más";
  - la mini línea de tiempo, solo si el dato es anterior, que es cuando explica algo.
- **Por qué:** el que quiere la respuesta no carga con la evidencia, y el que duda la tiene a un toque.

**D5. "Qué hacer" en vez de solo "qué leer".**
- Hasta 3 elementos: los párrafos de recomendación del comunicado vigente para su interés y zona (texto oficial literal, con su fuente) y, si hay, 1 nota reciente que coincide con lo oficial.
- **Por qué:** el ciudadano pregunta "¿y qué hago?", y las recomendaciones oficiales responden eso.

**D6. Compartir es una acción principal.**
- El botón "Compartir" abre el menú del celular (por ejemplo, WhatsApp) con un texto corto: el veredicto, el comunicado y el enlace. El texto consultado va en el fragmento `#`, que no llega al servidor.
- **Por qué:** el contenido dudoso circula por mensajería, y la respuesta tiene que poder viajar por el mismo camino.

**D7. El agente tiene su propia pestaña: Preguntar.**
- **Por qué:** es otra tarea ("¿hay alerta en Lima?", "¿qué dice el ENFEN sobre la pesca?"). Pegado al final de Verificar alargaba la pantalla y mezclaba tareas.

**D8. El Panorama empieza con lo que se puede contar.**
- Arriba, 3 hallazgos en una frase con su número. Debajo, 4 gráficos y una lista.
- Fuera quedan el mapa, el grafo de fuerzas y el mapa de calor de 12 tópicos:
  - el mapa tiene 4 departamentos y Tumbes solo 13 % de semanas con dato;
  - el grafo de fuerzas suele quedar enredado y una lista lo responde mejor;
  - los 12 tópicos se nombran con listas de palabras que no le dicen nada al lector. Se reemplazan por las 4 categorías de interés que usa toda la app.

**D9. Etiquetas solo en la excepción.**
- Solo llevan la etiqueta discreta "Descriptivo" los gráficos cuyo componente no pasó su criterio (polaridad, emociones, efecto comunicado). El detalle va en un ícono de información.
- **Por qué:** poner insignia, n, intervalo y enlace en cada gráfico es ruido. La honestidad se mantiene, porque lo débil está marcado y todo se detalla en Metodología.

**D10. Los mismos filtros para todo el Panorama:** rango de fechas y macro-región.
- Un gráfico que no depende de la región (la reacción a cada comunicado es nacional) lo dice en su lugar, en vez de ignorar el filtro sin avisar.

**D11. Metodología va al pie de página, no como pestaña principal.**
- Ahí están "Cómo lo validamos", el modelo de engagement y el uso de la app.
- **Por qué:** es lo que necesita el evaluador; el ciudadano no la busca.

**D12. La app debe ser liviana.**
- La primera carga de Verificar pesa 300 KB comprimidos o menos, y los gráficos se cargan solo al abrir el Panorama.
- **Por qué:** el usuario principal está en un celular con datos móviles.

## 4. Pantallas

### 4.1 Verificar (celular primero)
1. **Línea de estado:** "Costa norte · Alerta de El Niño costero · magnitud prevista: fuerte · Comunicado N.° 20 (fecha)". A la derecha, cuántos avisos del Senamhi hay vigentes; al tocar, se abren.
2. **Cuadro** "Pega aquí el titular o mensaje" y botón **Verificar**.
3. **Resultado** (sección 3, D1): el veredicto o la cercanía, una frase y "Ver por qué".
4. **Lo oficial:** el párrafo del comunicado vigente más cercano al texto, literal, con su fuente.
5. **Qué hacer:** los chips de interés y hasta 3 elementos.
6. **Compartir.**

### 4.2 Preguntar
- Un cuadro de pregunta con 3 ejemplos que se pueden tocar.
- La respuesta del agente con sus citas literales.
- La zona y la fecha que el agente entendió, a la vista y editables, para que el usuario vea cómo leyó su pregunta.

### 4.3 Panorama (escritorio primero, y también se ve en el celular)

**Hallazgos** (3 tarjetas, cada una con su número y una mini serie):
- la cobertura de El Niño subió tras 14 de 18 comunicados (mediana +63 %), descriptivo;
- el porcentaje de notas cuyos datos coinciden con el ENFEN;
- cuántas notas usan un dato de un comunicado anterior, y de cuántos comunicados atrás (columna `atras`).

Las cifras salen de los CSV al arrancar; aquí no se fijan a mano.

| # | Pregunta | Forma | Por qué esa forma |
|---|---|---|---|
| A | ¿Cómo se habló de El Niño en 2026 frente a lo oficial? | Dos bandas sobre la misma fecha, cada una con su eje. Arriba, franjas del estado y la magnitud prevista del ENFEN, con una marca en cada comunicado. Abajo, notas por semana en tres grupos: datos que coinciden, datos que no coinciden o son anteriores, y sin datos | La pregunta central del proyecto en un solo vistazo. Muestra el 74 % sin datos, en vez de esconderlo |
| B | ¿Qué magnitud decían las notas frente al ENFEN? | La magnitud oficial como escalón y un punto por cada dato de magnitud de las notas, según coincida o no | Es la única vista que muestra el desfase, que solo este proyecto puede medir |
| C | ¿Reacciona la cobertura a cada comunicado? | Pesas por comunicado: semana anterior frente a los 3 días siguientes. Etiqueta *Descriptivo* | Compara el antes y el después de cada evento sin inventar significancia |
| D | ¿De qué se habló? | Área apilada por mes con las 4 categorías de interés, más la línea "otros" | 4 series se leen bien; 12 tópicos no |
| E | ¿Quién cita a lo oficial? | Lista de medidores, uno por medio en orden alfabético: proporción de sus notas que enlazan o mencionan al ENFEN, al Senamhi y al INDECI | Se lee y se compara mejor que un grafo, y el orden alfabético evita rankings |
| F | YouTube (después del 21-nov) | Dispersión de la tasa de engagement frente a la cercanía con lo oficial, más 2 indicadores | Responde la pregunta 5 sin abrir otra pantalla |

- **Datos:** A sale de `comunicados.csv` y `discrepancia-todas-notas.csv`; B de `discrepancia-todas.csv`; C de `eventos-por-comunicado.csv`; D de `topicos-notas.csv` y `topicos-nombres.csv`; E de `red/*.csv`; F de `processed/youtube/`.
- **Cada gráfico tiene:**
  - información emergente al pasar el cursor;
  - vista de tabla con descarga en CSV (para el periodista);
  - una línea de "Cómo leer".
- **En ningún gráfico:**
  - se ordena a los medios o canales por cercanía a lo oficial;
  - la información emergente de B muestra el medio de un dato.

### 4.4 Metodología (pie de página)
- "Cómo lo validamos": una tarjeta por componente, con el criterio, el resultado y si pasó.
- El modelo de engagement, después del 21-nov.
- El uso de la app: sesiones, embudo y tiempo por pantalla.
- Limitaciones declaradas.

## 5. API y registro de uso
- **Rutas:**

| Ruta | Qué hace |
|---|---|
| `POST /api/verificar` | Tipo de resultado, veredictos por dato, cercanía, comparación, línea de tiempo, párrafo oficial y "qué hacer" |
| `GET /api/estado` | Línea de estado y avisos de una zona |
| `POST /api/preguntar` | Respuesta del agente |
| `GET /api/panorama/{seccion}` | Datos de cada gráfico |
| `GET /api/metodologia` | Contenido de Metodología |
| `POST /api/eventos` | Registro de uso |
| `GET /api/opciones` | Listas de macro-regiones e intereses, con sus nombres |
| `GET /api/salud` | Estado de la API |

  - Todo lo que entra tiene un esquema fijo (Pydantic): listas cerradas, fechas con formato y textos con tope de largo. Las respuestas salen de `radar.app.servicio` con campos fijos, y P3 los revisa en respuestas reales.
  - Para las notas, solo se permiten los campos medio, id, titular, fecha, enlace y macro-región.
  - La API no hace peticiones a ningún sitio externo.
- **Eventos que se registran:**
  - `vista` (pantalla y tiempo en la anterior);
  - `verificar` (tipo de resultado, veredicto o cercanía, macro-región y largo del texto en palabras);
  - `ver_por_que`;
  - `interes` (chip elegido);
  - `clic_que_hacer` (tipo y posición);
  - `compartir`;
  - `preguntar` (herramienta elegida y si quedó fuera de alcance);
  - `filtro_panorama`;
  - `tabla_descargada`.
- **Cada evento lleva** un id de sesión al azar (en `sessionStorage`), la fecha y hora, y el tipo de pantalla.
- **No se guardan** el texto, la IP, cookies ni identificadores.
- **El embudo que se mide:** vista → verificar → ver por qué o qué hacer → compartir. Responde si la app se usa como se diseñó.

## 6. Criterios (fijados antes de construir)

| # | Criterio | Umbral |
|---|---|---|
| P1 | Contrato: con 20 textos sintéticos, la API da lo mismo que llamar a las funciones directamente | 100 % |
| P2 | Latencia: mediana de 20 consultas, y tiempo de arranque | ≤ 2 s; ≤ 90 s |
| P3 | Derecho de autor: campos fuera de la lista permitida, revisando el esquema y respuestas reales | 0 |
| P4 | Citas literales en Verificar y Preguntar | 100 % |
| P5 | Privacidad del registro: eventos con texto libre, IP o identificadores | 0 |
| P6 | Accesibilidad (axe) a 375 y 1.280 px | 0 violaciones graves o críticas |
| P7 | De punta a punta: 6 textos sintéticos (coincide, dato anterior y no coincide con datos; cercanía alta, media y baja sin datos) muestran el resultado esperado | 6/6 |
| P8 | Cifras del Panorama y de los hallazgos iguales a las de sus CSV | 100 % |
| P9 | Paleta: `validate_palette.js` sin fallas, en claro y en oscuro | 0 |
| P10 | Cada gráfico tiene información emergente, vista de tabla con descarga y "Cómo leer"; "Descriptivo" aparece justo donde corresponde | 100 % |
| P11 | Revisión con capturas a 375 y 1.280 px, en claro y oscuro, más la guía de errores de visualización | Sin problemas pendientes |
| P12 | Ningún gráfico ordena medios o canales por cercanía, y B no muestra el medio | 0 |
| U1 | **Pocos pasos:** de abrir la app al resultado hay 2 acciones (pegar y tocar Verificar), con la zona ya recordada | ≤ 2 |
| U2 | **Sin jerga:** ninguno de estos términos aparece en Verificar ni en Preguntar: capa, distancia, coseno, umbral, AUC, NLI, embedding, origen, percentil (prueba sobre los textos de la interfaz) | 0 |
| U3 | **Se lee fácil:** los textos de veredicto, cercanía y ayuda tienen un índice INFLESZ (legibilidad en español) "bastante fácil" o mejor | ≥ 65 |
| U4 | **Liviana:** primera carga de Verificar, comprimida | ≤ 300 KB |
| U5 | **Se puede tocar:** controles de 44 × 44 px o más | 100 % |
| U6 | **Sin promesas falsas:** ninguna respuesta sin datos muestra un color de semáforo ni las palabras "correcto", "verdadero" o "falso" | 0 |

- **Sin etiquetado manual:** P7 usa textos sintéticos y U2 a U6 se comprueban con código.
- **Limitación declarada:** ninguna prueba con usuarios reales mide si la app se entiende. Las decisiones se apoyan en los datos de la sección 2 y en buenas prácticas, y el embudo del registro de uso es la única evidencia de uso que habrá.

## 7. Tecnología y orden de construcción
- **Tecnología:**
  - FastAPI y Uvicorn, con pruebas en `tests/app/`;
  - React con Vite y TypeScript;
  - Visx para los gráficos A a D y F;
  - CSS propio con variables, en claro y oscuro;
  - Vitest;
  - `npm run build` deja la interfaz en `web/dist/`, que la API sirve.
- **Orden:**
  1. API y criterios P1 a P5.
  2. Sistema visual: paleta validada (P9), tipografía, tarjetas, veredicto, medidor e información emergente.
  3. Verificar y Preguntar, con P6, P7 y U1 a U6.
  4. Panorama A a E y Metodología, con P8 y P10 a P12.
  5. Registro de uso.
  6. Después del 21-nov, F y el modelo de engagement.

## 8. Resultados (19-nov)

### API (paso 1)
- **Código:** `src/radar/app/` (`api.py`, `servicio.py`, `esquemas.py`, `eventos.py`, `metodologia.py`, `textos.py`, `legibilidad.py`). Se arranca con `python -m radar.app`; necesita el extra `app` (`pip install -e ".[app]"`).
- **Textos del ciudadano:** solo en `radar.app.textos`. Las pruebas U2, U3 y U6 los revisan (`tests/app/`).
  - El aviso de "No coincide" se reescribió porque su INFLESZ daba 60 (U3 pide 65 o más). Ahora dice "Una máquina leyó la frase y puede fallar. Antes de concluir, mira la comparación." (80).
  - Verificar ya no devuelve el color interno ni el método: solo el nivel, que es un veredicto únicamente cuando hay datos (U6).
- **P1 a P5:** `python -m radar.app.validar`, con 20 textos y 5 preguntas sintéticos y los modelos reales. Deja `data/processed/app/validacion.csv`.

| Criterio | Valor | Umbral | Pasa |
|---|---|---|---|
| P1. La API da lo mismo que la llamada directa | 25/25 | 100 % | Sí |
| P2. Mediana de Verificar | 0,14 s (máximo 0,25 s) | ≤ 2 s | Sí |
| P2. Arranque | 40,9 s | ≤ 90 s | Sí |
| P3. Campos de notas fuera de la lista (20 notas revisadas) | 0 | 0 | Sí |
| P4. Citas literales | 84/84 | 100 % | Sí |
| P5. Campos de texto libre en el registro | 0 | 0 | Sí |

- **Primera consulta lenta:** en la primera corrida tardó 14,8 s porque un modelo se cargaba recién ahí. Ahora la API hace una consulta de prueba al arrancar, y el arranque sube de 27 a 41 s.

### Paleta (P9)
Se validó con `validate_palette.js` (método del skill de visualización), en claro y en oscuro: 0 fallas.

| Uso | Claro | Oscuro | Nota |
|---|---|---|---|
| Notas: coinciden y no coinciden o son anteriores (A y B) | `#1baf7a`, `#eb6834` | `#199e70`, `#d95926` | "Sin datos" en gris neutro |
| Magnitud oficial (A y B), ordinal | `#86b6ef` → `#0d366b` | `#184f95` → `#9ec5f4` | Débil, moderada, fuerte y extraordinaria |
| Categorías de interés (D) | `#eda100`, `#e87ba4`, `#008300`, `#6250d6` | `#c98500`, `#d55181`, `#0ca30c`, `#9085e9` | "Otros" en gris |
| Instituciones (E), todos los pares | `#2a78d6`, `#eb6834`, `#1baf7a` | `#3987e5`, `#d95926`, `#199e70` | ENFEN, Senamhi e INDECI |
| Veredicto | `#0ca30c`, `#fab219`, `#d03b3b` | los mismos | Paleta de estado de referencia, sin cambios; siempre con ícono y frase |

- **Aviso del validador:** el aqua, el amarillo y el magenta quedan por debajo de 3:1 sobre el fondo claro. Por eso esos gráficos llevan etiquetas visibles y vista de tabla, que ya estaban en la sección 4.3.
