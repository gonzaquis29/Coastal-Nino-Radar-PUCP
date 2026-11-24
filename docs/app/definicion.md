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
- la cobertura de El Niño subió tras 14 de 20 comunicados (mediana +51 %; era 14 de 18 y +63 % antes del corte), descriptivo;
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

## 8. Resultados (19 y 22-nov)

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

### Interfaz (pasos 2 a 4, 22-nov)
- **Código:** `web/` (React 19, Vite 8, TypeScript 5.9, Visx 4, Vitest 5). Se construye con `cd web && npm install && npm run build`, que deja `web/dist/`; la API la sirve en `http://localhost:8000`. `dist/` y `node_modules/` no se versionan.
- **Textos:** salen solo de `radar.app.textos` (`python -m radar.app.textos` escribe `web/src/generado/textos.json`). Una prueba en `tests/app` revisa que el archivo esté al día.
- **Pantallas:** Verificar y Preguntar cargan primero; Panorama (A a F) y Metodología se cargan aparte, solo al abrirlas (unos 32 KB comprimidos).
- **Pantalla F:** la API agrega `/api/panorama/youtube` desde `<corte>_analitica-puntos.csv` (leído con `radar.youtube.almacen`, que se niega a usarlo pasados los 30 días) y `analitica/web-engagement.csv`.
  - Indicador 1: mediana de la tasa por tipo de canal, en orden fijo (medios, instituciones oficiales y otros canales).
  - Indicador 2: la respuesta de W2 ("sí", ρ −0,168, IC −0,260 a −0,099).
  - Los puntos no traen ids ni nombres de canal. Los colores son los de las instituciones (E), ya validados en P9.
- **Seguridad:**
  - CSP `default-src 'self'` sin scripts en línea, `X-Frame-Options: DENY`, `Referrer-Policy: no-referrer` y `no-store` en `/api/`.
  - Los enlaces externos solo se abren si son `https`, y ningún texto se inserta como HTML.
  - El registro de uso tiene topes: 30 lotes por minuto por sesión, 600 en total y 50 MB. Si se pasa el tope responde 429, y con el registro lleno responde 204 sin guardar.
- **Registro de uso (paso 4):** una sesión al azar por pestaña (`sessionStorage`). Los eventos se mandan por lote y con `sendBeacon` al cerrar, y nunca llevan el texto consultado (prueba de Vitest).
- **Cómo se mide:** con la API corriendo, `cd web && npm run medir` (Edge y axe-core) deja `data/processed/app/interfaz.json`. Luego `python -m radar.app.validar_interfaz` recalcula P8 desde los CSV, sin pasar por `radar.app.servicio`, y guarda la prueba "App: interfaz" en `validacion.csv`, que Metodología muestra.
  - La medición intercepta `/api/eventos` y anula `sendBeacon`, para no escribir en el registro real. La primera vez sí escribió, y esas filas se sacaron.

| Criterio | Valor | Umbral | Pasa |
|---|---|---|---|
| P6. Violaciones graves o críticas de axe (24 pantallas: 375 y 1.280 px, claro y oscuro) | 0 | 0 | Sí |
| P7. De punta a punta, 6 textos sintéticos | 6/6 | 6/6 | Sí |
| P8. Cifras del Panorama iguales a sus CSV | 24/24 (y 27 en pantalla) | 100 % | Sí |
| P9. Paleta | 0 fallas | 0 | Sí (19-nov) |
| P10. Emergente, tabla con descarga y "Cómo leer"; "Descriptivo" solo en C | 6/6 | 100 % | Sí |
| P11. Problemas pendientes tras revisar las capturas | 0 | 0 | Sí |
| P12. Medios o canales ordenados por cercanía; B o F con el medio o ids | 0 | 0 | Sí |
| U1. Acciones hasta el resultado | 2 | ≤ 2 | Sí |
| U2. Jerga en Verificar y Preguntar (en pantalla) | 0 | 0 | Sí |
| U4. Primera carga de Verificar, comprimida | 73,9 KB | ≤ 300 KB | Sí |
| U5. Controles de 44 × 44 px o más (128) | 100 % | 100 % | Sí |
| U6. Respuestas sin datos con color de semáforo o promesas | 0 | 0 | Sí |

- **P11, lo que se corrigió al revisar las capturas:**
  - el detalle de "Ver por qué" se veía abierto porque el CSS pisaba el atributo `hidden`;
  - el encabezado del Panorama quedaba descentrado;
  - en F, la etiqueta del 0 se encimaba con la de 0,1 %;
  - las cifras salían con punto decimal y con decimales desiguales;
  - las viñetas de los PDF se veían como un cuadro al inicio de algunas citas (se ocultan solo en pantalla, sin cambiar el texto oficial).
- **P1 a P5 se repitieron** con la interfaz terminada, y P3 revisa ahora también la pantalla F: P1 25/25, P2 0,11 s (máximo 0,19 s) y arranque de 35,2 s, P3 0, P4 84/84, P5 0.
- **Repetición con las notas del corte (22-nov, noche):** con la discrepancia de las 2.785 notas, el estudio de eventos con 20 comunicados y las emociones del corte, se corrieron otra vez `radar.app.validar`, `npm run medir` y `radar.app.validar_interfaz`. Todo pasa y la tabla de arriba no cambia: P6 0, P7 6/6, P8 24/24 (27 en pantalla), P10 6/6, P12 0, U1 2, U2 0, U4 73,9 KB, U5 100 % (128 controles) y U6 0. P1 a P5: P1 25/25, P2 0,11 s (máximo 0,21 s) y arranque de 35,9 s, P3 0, P4 84/84, P5 0. El registro de uso no se creó.
  - Hallazgos del Panorama tras el corte: la primera tarjeta dice ahora "14 de 20" comunicados (mediana +52 %; con 20 comunicados la mediana promedia los dos centrales, y la app los promedia como cocientes mientras `eventos` lo hace en logaritmos y da +51 %), la segunda 75 % de coincidencia con el 26 % de las 2.781 notas con datos (el 74 % sigue sin datos) y la tercera 97 notas con un dato anterior.
- **Pruebas:** 27 en `tests/app` y 12 en Vitest (`npm test`), con datos sintéticos.
- **Hallazgos que quedan fuera de la app:**
  - "La selección peruana jugará el martes en Lima" sale con cercanía Alta, y una nota del precio del dólar con Media. Son los umbrales de la cercanía (NLP); la app solo los muestra.
  - La respuesta del agente escribía la fecha en formato ISO ("vigentes el 2026-11-22"). **Corregido el 23-nov:** Preguntar ya no muestra el texto del agente, que también traía ids (`enfen-2026-20`, `costa_norte`, `prevencion`) y jerga ("Semáforo: rojo (reglas)"). La respuesta se arma en `radar.app.servicio` con las plantillas `PREGUNTAR` de `radar.app.textos`, que pasan U2 y U3. El agente no cambia. Después, P1 a P12 y U1 a U6 volvieron a pasar (arranque de 63,2 s).
  - **Arranque lento (23-nov):** 63,2 s, de los que unos 40 s se iban en volver a calcular los vectores de los párrafos oficiales (semáforo y buscador del agente) en cada arranque. Ahora se guardan en `data/processed/cache/` (`embeddings.con_cache`): la clave lleva el modelo, su prefijo y todos los textos, así que si cambia el corpus oficial o el modelo se recalculan solos. Con la caché, el arranque baja a 15,6 s y P1 a P5 pasan igual. Lo que queda (unos 14 s) es importar `sentence-transformers` y `torch`.
- **Antes de la presentación:**
  - correr `npm run build`;
  - no usar la app para pruebas sueltas, para que el registro de uso solo tenga el uso real;
  - si cambian los datos (punto 4 de pendientes), volver a correr `python -m radar.app.validar`, `npm run medir` y `python -m radar.app.validar_interfaz`.

## 9. Textos de otros temas en Verificar (aprobada y construida el 23-nov)

### 9.1 Problema medido
- **Verificar da cercanía a cualquier texto, sea del tema o no.** "Alta" empieza en el p95 de las notas de otros temas (sección de umbrales en `docs/nlp/discrepancia.md`), así que, por construcción, cerca del 5 % de los textos ajenos salen "Alta" y cerca del 20 % "Media". S3 lo midió (5,8 %) y pasó, pero nadie tradujo esa tasa a lo que ve el ciudadano: la app muestra "Cercanía: Alta" para un texto de fútbol.
- **Diagnóstico** (23-nov, semilla 20261123; las 300 notas nuevas quedaron en `config/notas_vistas.csv` como `diagnostico-fuera-de-tema`):
  - en 286 titulares reales sin palabras del tema, 24 salen "Alta" (8,4 %) y 58 "Media" (20 %). Ejemplos: la visita del Papa, las elecciones, el retiro de AFP y el BCR;
  - con textos sintéticos, 1 de 20 titulares ajenos y los 2 textos largos ajenos salen "Alta". El texto de fútbol (0,46) supera al de huaicos (0,43), así que ningún umbral los separa;
  - Preguntar no tiene el problema: su regla de dominio (`DOMINIO` en `radar.agente.agente`) rechazó 5 de 5 preguntas ajenas.
- **Causa:** la cercanía mide cuánto se parece un texto a una noticia sobre el Perú y sus instituciones, no si trata del tema.

### 9.2 Alternativas
| Opción | Por qué no o por qué sí |
|---|---|
| A. **Filtro de tema compartido** antes de la cercanía | **Elegida.** Es simple y transparente, y hace que Verificar y Preguntar decidan igual. |
| B. Cercanía relativa (oficial frente a otros temas) | Obliga a recalibrar y a repetir S2 y S3; no cabe antes del 27-nov. |
| C. Clasificador de tema con etiquetas automáticas | Es un modelo nuevo y puede aprender solo a detectar la palabra "Niño". |
| D. Subir el umbral de "Alta" (p99) | No ordena bien: el texto de fútbol queda sobre el de huaicos. |
| E. Solo declararlo | Deja el error a la vista del ciudadano. |

### 9.3 Qué se construye
1. **Un solo vocabulario del tema:** `radar.comun.dominio`, con la expresión `DOMINIO` del agente. `radar.agente.agente` la importa de ahí y no la copia. Correcciones halladas en desarrollo, que se miden en 9.5:
   - `nino\b` sin `\b` inicial acepta "femenino";
   - `calid` acepta "calidad";
   - `costa` acepta "Costa Rica" y "Costa 21".
2. **«Niño» con otro sentido:** "niño" o "niña" cuentan solo si nombran el fenómeno. Vale la regla de `radar.noticias.rasgos.menciones` ("El Niño", "fenómeno El Niño"), o "niño costero" o "niño global" escritos en cualquier forma. Así, "Niño de 5 años rescatado" y "Día del Niño" no cuentan. Escrito en minúsculas y sin otra palabra del tema ("el niño será fuerte"), el texto queda fuera; se declara, porque Verificar recibe textos de notas, que traen las mayúsculas.
3. **El filtro en Verificar**, antes de los datos y de la cercanía (el caso de pocas palabras sigue primero):
   - texto corto (hasta `PALABRAS_CORTO`, 100 palabras): basta una palabra del tema;
   - texto largo: hacen falta dos palabras distintas del tema o una mención del fenómeno, porque en un texto largo aparecen sueltas "alerta", "evento" o "costa".
4. **Resultado nuevo `fuera_de_tema`:** sin medidor, sin color y sin ícono (U6). El texto va en `radar.app.textos` y debe pasar U2 y U3 (INFLESZ de 65 o más), por ejemplo: "Este texto no parece hablar de El Niño, del mar ni del clima. Pega un texto sobre esos temas." El registro de uso acepta `fuera_de_tema` en `tipo_resultado`, que es una lista cerrada (P5).
5. **Qué no cambia:** el Panorama (ya usa solo las notas sobre El Niño), los umbrales de la cercanía y el semáforo de `radar.nlp`.

### 9.4 Muestras (se usa toda la fuente; decisión del 23-nov)
- **Desarrollo** (se puede mirar y ajustar): los 400 negativos de S3, los 450 titulares del diagnóstico y los 33 textos sintéticos. En desarrollo, el filtro deja pasar 17 de los 400 negativos de S3 por el titular.
- **Validación** (se mira una vez):
  - *negativos:* **todas** las notas de otros temas (definición de `otros_temas` de `radar.nlp.semaforo`) que no están en `config/notas_vistas.csv`: 50.623 al 23-nov, en corto. Solo se calcula la cercanía de las que pasan el filtro. Para el cuerpo, 100 de ellas (25 por medio, semilla nueva), leídas en memoria con `Medio.leer` y sin guardarlas, como en S3, porque hay que volver a pedirlas a los medios;
  - *positivos:* **todas** las notas sobre El Niño (2.785) menos las 150 del diagnóstico, es decir 2.635, en corto, y 100 de ellas (25 por medio) en cuerpo. Se informan aparte las 58 del corte que nadie había usado;
  - *excepción a la regla de `notas_vistas.csv`, declarada:* 2.577 de los positivos están "vistos" porque se usaron en las capas del NLP, pero ninguno sirvió para elegir las palabras del filtro, que vienen de las preguntas del agente y de la muestra de desarrollo. La regla existe para no medir con lo que se ajustó, y eso aquí no ocurre. Con 2.635 notas, el intervalo de F2 es de unos ±1 punto; con 58 eran ±8;
  - después de medir, los negativos y positivos usados se agregan a `config/notas_vistas.csv` con la muestra `validacion-tema`. Si algún criterio no pasa y se ajusta el filtro, ya no queda una muestra limpia: la segunda medición se hace con `--repetir` y se declara;
  - *sintéticos nuevos*, escritos antes de medir: 10 usos de «niño» con otro sentido, 10 menciones del fenómeno bien escritas y 10 textos del tema que no nombran a El Niño (mar, lluvias, pesca, huaicos). Todos son inventados.

### 9.5 Criterios (fijados antes de construir)
| | Criterio | Umbral |
|---|---|---|
| F1 | Negativos con "Alta", en corto (50.623) y en cuerpo (100) por separado | ≤ 2 % |
| F2 | Positivos que el filtro deja fuera, en corto (2.635; se informan aparte las 58 del corte) | ≤ 10 % |
| F3 | Positivos que el filtro deja fuera, en cuerpo (100) | ≤ 5 % |
| F4 | Usos de «niño» con otro sentido que pasan solo por esa palabra / menciones del fenómeno que no pasan | 0 / 0 |
| F5 | Textos sintéticos del tema sin "El Niño" que quedan fuera | ≤ 1 de 10 |
| F6 | Preguntar: con las preguntas ya vistas del agente, toda decisión que cambie se explica por las correcciones de 9.3; A4 sigue en ≥ 0,90 y ≤ 0,05 | 100 % |
| F7 | La app sigue pasando P1 a P12 y U1 a U6. En P7, la receta de ceviche pasa de "Media" a `fuera_de_tema` | todos |

- Si F1 a F5 pasan, **P13** ("textos de otros temas con «Alta» en Verificar ≤ 2 %") entra a la sección 6 y se mide con cada cambio de la app.
- Si F2 no pasa, no se baja la exigencia: se declara cuánto deja fuera el filtro y se muestra el resultado `fuera_de_tema` con la frase "si sí trata del tema, pega la nota completa".
- **Comandos previstos:** `python -m radar.app.validar_tema muestra|validar`, que guarda la prueba "App: tema" en `data/processed/app/validacion.csv`. Después, `python -m radar.app.validar`, `npm run medir` y `python -m radar.app.validar_interfaz`.
- **Archivos:** `radar.comun.dominio` (nuevo), `radar.agente.agente` (solo la importación), `radar.app` (servicio, textos, eventos y `validar_tema`), `web/` (el resultado `fuera_de_tema` y P7) y sus pruebas.

### 9.6 Resultados (23-nov)
- **Código:**
  - `radar.comun.dominio` tiene el vocabulario único del tema; `radar.agente.agente` lo importa.
  - En `radar.app.servicio`, Verificar aplica el filtro y devuelve `fuera_de_tema` sin medidor, color ni ícono. Sus textos están en `radar.app.textos` (`FUERA_DE_TEMA` y `FUERA_DE_TEMA_AYUDA`) y pasan U2 y U3.
  - La interfaz muestra el nuevo resultado y el registro de uso lo acepta.
  - Pruebas: `tests/comun/test_dominio.py`, `tests/app` y Vitest (13).
- **Medición:** con `python -m radar.app.validar_tema muestra|validar`. El detalle queda en `data/processed/app/tema-*.csv` y la prueba "App: tema" en `validacion.csv`. Las 53.458 notas usadas pasaron a `config/notas_vistas.csv` (`validacion-tema`).

| Criterio | Valor | Umbral | Pasa |
|---|---|---|---|
| F1. Otros temas con «Alta», corto (50.623) | 0,72 % (IC 0,65 a 0,79); antes 5,8 % (S3) | ≤ 2 % | Sí |
| F1. Otros temas con «Alta», cuerpo (100) | 3 % (IC 1,0 a 8,5); antes 6 % (S3) | ≤ 2 % | **No** |
| F2. Sobre El Niño que el filtro deja fuera, corto (2.635) | 9,03 % (IC 8,0 a 10,2); de las 58 del corte, 2 | ≤ 10 % | Sí |
| F3. Sobre El Niño que el filtro deja fuera, cuerpo (100) | 0 % (IC 0 a 3,7) | ≤ 5 % | Sí |
| F4. «Niño» con otro sentido que pasa / el fenómeno que no pasa | 0 / 0 | 0 / 0 | Sí |
| F5. Del tema sin «El Niño» que quedan fuera | 0 de 10 | ≤ 1 | Sí |
| F6. Preguntar: decisiones que cambian; A4 | 0; A4 0,951 y abstención 0,007 | ≥ 0,90 y ≤ 0,05 | Sí |
| F7. La app: P1 a P12 y U1 a U6 | todos pasan; P7 7/7 con tres textos de otros temas, P4 83/83 | todos | Sí |

- **F1 en cuerpo no pasa, y se declara (decisión del 23-nov).**
  - En los textos largos, el error bajó a la mitad (de 6 % a 3 %), pero no llega a la meta. Con 100 cuerpos, el intervalo queda a ambos lados del 2 %.
  - No se ajustó el filtro: no quedan notas de otros temas sin usar, y repetir con los mismos 100 cuerpos sería una medición sesgada.
  - Como F1 no pasa completo, **P13 no entra** a la sección 6 tal como se definió. Se declara la tasa en corto (0,72 %) y en cuerpo (3 %).
- **F2 pasa cerca del límite:** de cada 11 titulares sobre El Niño, uno queda "fuera del tema" si se pega solo el titular. La frase de ayuda pide pegar la nota completa, y en cuerpo no se perdió ninguno.
- **Declaraciones:**
  - antes de medir, se comprobó que la lista de «niño» con otro sentido (F4) daba 0. Es una regla fija y no cambia el resultado;
  - las notas reservadas para la capa 3 entraron en los positivos; ninguna sirvió para elegir las palabras.
- **P7:** ahora tiene 7 textos. La receta, el teléfono y el fútbol esperan `fuera_de_tema`; ya no hay un caso de cercanía "Baja" dentro del tema.

## 10. Clasificador de tema en Verificar (definición aprobada el 23-nov)

### 10.1 Por qué
El filtro de la sección 9 tiene un techo que no depende de la cantidad de datos:
- **la presencia de una palabra no es el tema:** un texto largo de otro tema dice "alerta" o "costa" de pasada y pasa (F1 en cuerpo, 3 %), y un titular sobre El Niño sin palabras clave queda fuera (F2, 9 %);
- **la cercanía no tiene contraste:** compara solo con lo oficial, así que nunca aprendió qué *no* es el tema.

La salida es aprender el tema con toda la fuente, sin etiquetar a mano. Se descartan:
- NLI: se cerró sin medir y es lento;
- un LLM: la API no pide nada a internet;
- la cercanía relativa: obliga a recalibrar el semáforo, y el clasificador resuelve lo mismo y además el titular sin palabras.

### 10.2 Qué se construye
1. **Etiquetas automáticas**, las que el proyecto ya calcula:
   - tema: `sobre_nino` = 1, de `radar.noticias.rasgos` (2.785 notas);
   - otro tema: la definición `otros_temas` de `radar.nlp.semaforo`, sin El Niño y sin términos del filtro en el cuerpo (56.595);
   - **zona gris:** las 22.499 notas que no mencionan El Niño pero traen términos de clima en el cuerpo (lluvias, calor y también "emergencia" o "dengue"). No entran al entrenamiento, porque su etiqueta es dudosa; se informan aparte (C6).
2. **Rasgos:** el vector e5 de titular y resumen (`reranker.texto_corto`), con el mismo modelo que ya carga el semáforo, de modo que Verificar no calcula un vector más.
3. **Modelo:** regresión logística con pesos por clase balanceados.
   - Se elige con validación cruzada de 5 grupos *solo con el entrenamiento*: la regularización C y el umbral τ, el menor que deja pasar como máximo el 1 % de los textos de otros temas en la validación cruzada.
   - Semilla fija. Se guarda en `data/processed/app/tema-modelo.joblib`: son unos 770 números y no se versiona, como el resto de `data/`.
4. **Partición por tiempo:**
   - entrenamiento con enero a agosto: 1.167 notas del tema y 46.089 de otros temas;
   - **prueba con septiembre al corte:** 1.618 y 10.506, que no se miran hasta el final;
   - es la práctica estándar con datos que ya se usaron: no se ajusta nada con la prueba.
5. **En Verificar:**
   - si el texto nombra el fenómeno (`dominio.nombra_el_fenomeno`), está en el tema;
   - si no, decide el clasificador sobre el texto completo cuando es corto, o sobre sus primeras 100 palabras (`PALABRAS_CORTO`) cuando es largo, porque en una nota el tema está al inicio;
   - fuera del tema, el mismo resultado `fuera_de_tema` de la sección 9;
   - Preguntar no cambia: sigue con `dominio.en_pregunta`.
6. **Si no pasa,** queda el filtro de la sección 9 tal como está y se declara.

### 10.3 Muestras
- **Corto:** todas las notas de la prueba (septiembre al corte).
- **Cuerpo:** 100 notas por medio de cada grupo de la prueba (400 y 400, semilla nueva), leídas en memoria sin guardarlas, para que el intervalo sea de ±1,5 puntos y no de ±4.
- Las notas de la prueba ya se usaron el 23-nov para *medir* el filtro de la sección 9, pero no para entrenar ni para elegir nada del clasificador. Se declara.
- **Sintéticos nuevos**, escritos antes de medir y distintos de los de las secciones 9.4 y 9.5: 10 usos de «niño» con otro sentido, 10 menciones del fenómeno y 10 textos del tema sin «El Niño».

### 10.4 Criterios (fijados antes de construir)
| | Criterio | Umbral |
|---|---|---|
| C1 | Otros temas con «Alta», corto (prueba) | ≤ 1 % y no peor que la sección 9 en las mismas notas |
| C2 | Otros temas con «Alta», cuerpo (400) | ≤ 2 % |
| C3 | Notas del tema que quedan fuera, corto (prueba) | ≤ 5 % y no peor que la sección 9 en las mismas notas |
| C4 | Notas del tema que quedan fuera, cuerpo (400) | ≤ 5 % |
| C5 | Sintéticos: «niño» con otro sentido que pasa / el fenómeno que no pasa / del tema sin «El Niño» que quedan fuera | 0 / 0 / ≤ 1 de 10 |
| C6 | Zona gris de la prueba: proporción que pasa | informativo |
| C7 | La app: P1 a P12 y U1 a U6; P2 (mediana de Verificar ≤ 2 s) | todos |
| C8 | Preguntar sin cambios | 0 decisiones distintas |

- Si C1 a C5 pasan, **P13** (otros temas con «Alta» en Verificar ≤ 2 %, en corto y en cuerpo) entra a la sección 6.
- **Comandos previstos:** `python -m radar.app.tema entrenar|muestra|validar`. Archivos: `radar.app.tema` (nuevo), `radar.app.servicio` y sus pruebas.
- **Riesgo declarado:** la etiqueta dice "menciona El Niño". El modelo podría rechazar textos de lluvias o de mar que no lo nombran; C5 y C6 lo miden.

### 10.5 Resultados (23-nov): no pasa; la app sigue con el filtro de la sección 9
- **Código:**
  - `radar.app.tema`, con las órdenes `entrenar`, `muestra`, `cuerpos` y `validar`. `cuerpos` lee en memoria mientras se entrena y guarda solo datos derivados: el filtro de la sección 9, la banda del semáforo y el vector del inicio del texto.
  - En `radar.app.servicio`, el selector `FILTRO_DE_TEMA` queda en `"palabras"`.
  - Pruebas en `tests/app/test_tema.py`.
- **Entrenamiento** (enero a agosto, 47.256 notas, 1.167 del tema):
  - C = 10 y τ = 0,8285;
  - average precision en la validación cruzada: 0,872 con C = 0,1, 0,892 con C = 1 y 0,895 con C = 10;
  - C quedó en el borde de la grilla. La curva es plana, así que la ganancia de subirlo sería mínima; se declara.
- **Rasgos:** se usó el minilm del semáforo, no el e5. La sección 10.2 decía "e5", pero el semáforo usa minilm; se mantuvo lo que esa sección quería: el mismo modelo que la app ya carga.

| Criterio | Clasificador | Sección 9 en las mismas notas | Umbral | Pasa |
|---|---|---|---|---|
| C1. Otros temas con «Alta», corto (10.506) | 0,22 % (IC 0,15 a 0,33) | 0,97 % (102) | ≤ 1 % y no peor | Sí |
| C2. Otros temas con «Alta», cuerpo (400; 1 sin leer) | 0,50 % (IC 0,14 a 1,80) | 1,75 % (7) | ≤ 2 % | Sí |
| C3. Del tema que quedan fuera, corto (1.618) | 12,79 % (IC 11,3 a 14,5) | 10,9 % (176) | ≤ 5 % y no peor | **No** |
| C4. Del tema que quedan fuera, cuerpo (399) | 0 % | 0 % | ≤ 5 % | Sí |
| C5. Sintéticos: «niño» con otro sentido / el fenómeno / del tema sin «El Niño» | 0 / 0 / 6 de 10 | — | 0 / 0 / ≤ 1 | **No** |
| C6. Zona gris que pasa (9.503) | 10,0 % | 20,6 % | informativo | — |
| C8. Preguntar sin cambios | 0 cambios | — | 0 | Sí |

- **Lectura:** se cumplió el riesgo declarado en 10.4.
  - El clasificador es mucho mejor para rechazar otros temas: cuatro veces menos «Alta» en corto y tres veces menos en cuerpo.
  - Pero aprendió "menciona El Niño": rechaza textos de clima y mar que no lo nombran (6 de 10 sintéticos, como la pesca, los huaicos o el oleaje), y en corto pierde más notas del tema que el filtro de palabras.
  - Como la app debe aceptar El Niño, el mar y el clima, no se activa.
- **Lo que esto dice de la sección 9:** en esta muestra más grande (400 cuerpos de septiembre al corte), el filtro de palabras da 1,75 % de «Alta» en cuerpo, por debajo del 2 %. En la sección 9.6 había dado 3 de 100. Es otra muestra, medida después y como comparación, así que no cambia el "no pasa" de F1; se informa.
- **Por qué no se ajusta:** la prueba ya se miró. Combinar los dos filtros o cambiar τ ahora sería elegir con la prueba, y no queda otra muestra limpia.
- **Qué lo resolvería** (pendiente, sin definir): etiquetas de "clima y mar" que no dependan de nombrar a El Niño. Por ejemplo, los avisos del Senamhi y los párrafos de impactos del ENFEN como positivos. Pide otra definición y una prueba nueva, que no existe antes del congelamiento.

## 11. Rediseño de la interfaz (aprobado el 23-nov)

### 11.1 Por qué
Al recorrer la app en el celular, el 23-nov, aparecieron seis problemas para un ciudadano:
1. Un mensaje que contradice al ENFEN («será débil y ya se va», con la alerta vigente en extraordinaria) dio «Cercanía: Alta» bajo el título «¿Coincide con el ENFEN?». Cualquiera lo lee como «sí coincide».
2. La situación de la zona, que es lo primero que busca la gente, era una línea chica y densa.
3. El párrafo oficial y las recomendaciones salían tal cual, escritos para autoridades.
4. Había bloques que no se entendían («¿Es de otra fecha?»).
5. El aspecto era de herramienta técnica, con recuadros iguales como cualquier página hecha con IA.
6. Nadie explicaba qué es el ENFEN.

Se compararon tres opciones en maquetas: ordenar lo que ya existe, primero tu zona y un chat. El equipo eligió «primero tu zona», con una identidad propia del tema.

### 11.2 Qué se construye
- **Inicio «Hoy».** Primero va el estado de la zona: la escalera de estados del ENFEN (no activo, vigilancia, alerta) y una regla vertical de magnitud (débil, moderada, fuerte, extraordinaria), como la de un mareógrafo. Debajo, los avisos vigentes del Senamhi a la vista y el cuadro para pegar un mensaje.
  - En pantallas de 1.024 px o más: dos columnas, tu zona a la izquierda y tu mensaje a la derecha.
  - En el celular: una columna, con la navegación abajo.
  - Verificar sigue a 2 acciones (U1).
- **Resultado con datos.** Lleva un sello (✓, ! o ✕), el título y la comparación «Tu mensaje / El ENFEN». Si el dato es la magnitud, la regla marca las dos posiciones.
- **Resultado sin datos.** El título dice que no trae un dato que revisar. La cercanía queda como una línea chica, en un solo tono, que aclara que hablar del mismo tema no lo hace cierto (D1 y U6 se mantienen).
- **Glosario.** ENFEN, Senamhi, El Niño costero y magnitud van subrayados y abren una explicación corta. En el menú hay «¿Qué es el ENFEN?».
- **Identidad.** Fondo gris garúa, tinta azul de altamar y la corriente de Humboldt como acento. La regla usa la escala de magnitud ya validada en P9 (azul, de claro a oscuro), la misma del Panorama. La maqueta la mostraba cálida, pero el naranja ya significa «difieren» en los gráficos A y B. Los títulos van en Archivo condensada y los textos en Atkinson Hyperlegible.
  - Las fuentes se sirven desde la propia app, porque la CSP no admite nada de fuera.
  - El modo claro va por defecto; el oscuro tiene sus propios pasos.
- **Panorama** pasa a llamarse «Cómo se habló», con el mismo sistema visual. Sus textos no cambian de sentido: «Descriptivo» sigue donde lo pide P10.
- **Lo que no cambia:** la API, el registro de uso, los cálculos y el sentido de los veredictos. Todos los textos siguen en `radar.app.textos`.

### 11.3 Criterios (fijados antes de construir)
| # | Criterio | Umbral |
|---|---|---|
| I1 | Siguen pasando P1 a P12 y U1 a U6. En P7, la cercanía se espera con el título nuevo; en U4 cuentan las fuentes | todos |
| I2 | Sin desplazamiento horizontal a 360, 375 y 1.280 px | 0 pantallas |
| I3 | A 1.280 × 800, el estado de la zona y el botón para verificar se ven sin desplazarse | sí |
| I4 | Glosario: las cuatro palabras abren su explicación, y sus textos pasan U2 y U3 | 4/4 |
| I5 | La paleta de datos pasa `validate_palette.js` sobre las superficies nuevas, en claro y en oscuro (P9) | 0 fallas |

### 11.4 Resultados (23-nov)
Medido con `npm run medir`, `python -m radar.app.validar_interfaz` y `python -m radar.app.validar`, con la API recién arrancada.

| # | Resultado | Pasa |
|---|---|---|
| I1 | P1 a P12 y U1 a U6 pasan. P7 da 7/7 con el título nuevo; U4 da 228,9 KB con las fuentes (umbral 300 KB); U5 da 100 % en 146 controles | sí |
| I2 | 0 de 18 pantallas a 360, 375 y 1.280 px | sí |
| I3 | A 1.280 × 800, el estado termina a 182 px, la escalera a 354 px y el botón a 360 px | sí |
| I4 | 4/4 (ENFEN, Senamhi, El Niño costero y magnitud); los textos pasan U2 y U3 en `tests/app` | sí |
| I5 | P9 da 0 fallas. La magnitud en oscuro pasa con la superficie `#0f2029` (con `#11242e` no pasaba) | sí |

Lo que se corrigió durante la medición:
- El enlace al comunicado y la palabra «Senamhi» medían menos de 44 px de alto (U5): se agrandó su área de toque sin mover el texto.
- Los gráficos del Panorama se dibujaban con 640 px hasta que el navegador avisaba el ancho, y a 360 y 375 px la página se desplazaba a los lados (I2). Ahora miden su caja al aparecer.
- La primera medición de P7 usó una API arrancada antes del cambio de título; con la API recién arrancada da 7/7.

## 12. Etiquetas de clima y mar para el tema de Verificar (aprobada el 23-nov; construida, no pasa)

### 12.1 Por qué
El clasificador de la sección 10 aprendió "menciona El Niño" porque su única etiqueta positiva era `sobre_nino`: rechazó 6 de 10 textos sintéticos de clima y mar (C5) y perdió más titulares del tema que el filtro de palabras (C3). Hace falta una etiqueta positiva de clima y mar que no dependa de nombrar a El Niño y que no pongamos nosotros (cero etiquetado manual).

**Qué se quiere ganar, medido en desarrollo (enero a agosto, 23-nov):**
- el filtro de palabras **ya acepta** el 93,6 % de las notas de clima y mar en corto (titular y resumen), así que ahí el clasificador puede, como mucho, empatarlo;
- su falla está en los **otros temas con palabras de clima**: un sismo con "emergencia", el dengue o una nota política con "alerta". De las notas de la zona gris con etiquetas de otros temas, el filtro deja pasar el 19 % en corto;
- esa falla **nunca se midió**: F1 y C1 a C2 usaron `otros_temas`, que por definición no tiene términos de clima en el cuerpo. Son los negativos fáciles.

**Datos sin usar** (la zona gris, sin El Niño y con términos de clima en el cuerpo, tiene 20.286 notas fuera de `config/notas_vistas.csv`):
- **positivos:** 2.137 llevan una etiqueta editorial de clima o mar de la lista de 12.3, que puso el propio medio (`etiquetas` de `notas.csv`): 1.721 de enero a agosto y 416 de septiembre al corte. Con la lista amplia, el 52 % cita al Senamhi, IMARPE, DHN o ENFEN en `actores`, frente al 4,6 % de la zona gris sin esas etiquetas;
- **negativos difíciles:** 4.020 llevan solo etiquetas de otros temas (política, sismo, deportes, el Papa, Congreso, elecciones…): 1.639 de enero a agosto y 2.381 de septiembre al corte;
- **límites:** El Tiempo no tiene etiquetas (0 de 4.918) y Exitosa casi ninguna (26 positivos de prueba). Hay plantillas diarias («SENAMHI: Pronóstico del clima hoy…»): las 416 de prueba son 338 titulares distintos;
- **etiquetas con otro sentido**, vistas en desarrollo: «mar» (surf, una banda), «pesca» (un TLC, el PBI), «clima» (un volcán) y «cambio climático» (COP, plagas, reforestación). Por eso no entran (12.3).

### 12.2 Mapa de enfoques
| Tipo | Opción | Por qué sí o por qué no |
|---|---|---|
| Supervisión distante con metadatos | **A. Etiquetas editoriales del medio**: positivos de clima y mar y negativos difíciles | **Elegida.** Las pone el medio, no nosotros; no están en el texto que ve el modelo, así que no hay atajo léxico; dan positivos y, por primera vez, negativos con palabras de clima, todos sin usar. |
| Supervisión distante con fuentes | B. Notas que citan al Senamhi, IMARPE, DHN o ENFEN | El nombre está en el texto: el modelo aprendería «Senamhi» como antes aprendió «Niño», aunque se enmascare. **Solo como control** de las etiquetas (12.1). |
| Textos oficiales como positivos | C. Avisos del Senamhi y párrafos de impactos y pesca del ENFEN | Era la idea anotada. Son 143 avisos de solo dos fenómenos y en registro oficial («se prevén temperaturas máximas entre…»): el modelo aprendería el estilo, no el tema. **Entran solo si mejoran la validación cruzada del entrenamiento**; los de septiembre al corte se miden aparte. |
| Coincidencia temporal | D. Notas publicadas durante un aviso vigente en su macro-región | Etiqueta débil: en esas fechas se publica de todo. No entra. |
| Aprendizaje con no etiquetados | E. PU (positivos y no etiquetados) con la zona gris | Pide la proporción de positivos en la zona gris, que no se conoce sin etiquetar. |
| Sin entrenamiento | F. Prototipos del tema o NLI zero-shot | Los prototipos son la cercanía, que ya falló (9.1); el NLI se cerró y es lento. |
| Agrupamiento | G. Tópicos de BERTopic como etiqueta | Se calcularon solo con notas sobre El Niño. |
| Generativo | H. Un LLM que etiquete | La app no pide nada a internet, y sería un etiquetado sin referencia externa. |
| Reglas | I. Ampliar o endurecer el vocabulario de `radar.comun.dominio` | No resuelve el límite de 10.1: la palabra no es el tema. |
| Combinación | J. Filtro de palabras y clasificador juntos | Con muestras nuevas sí se puede medir, pero solo si queda fijada aquí (12.5). |
| No hacer nada | K. Dejar el filtro de la sección 9 y declararlo | Es lo que queda si 12.5 no pasa. |

### 12.3 Qué se construye
1. **Dos listas en `radar.comun.dominio`**, fijas antes de medir. Se compara la etiqueta completa, en minúsculas y sin tildes:
   - `ETIQUETAS_CLIMA_MAR`: senamhi, imarpe, dhn, lluvia(s), lluvias intensas o fuertes, precipitaciones, temporada de lluvias, temperatura(s), calor, ola de calor, friaje, helada(s), radiación UV, huaico(s) o huayco(s), inundación(es), desborde(s) (de río o ríos), sequía, oleaje(s), mar peruano, anchoveta, meteorología y fenómeno(s) climático(s). **No entran** «mar», «pesca», «clima» ni «cambio climático» (12.1);
   - `ETIQUETAS_OTRO_TEMA`: deportes, fútbol, Mundial 2026, elecciones (2026), ONPE, JNE, Congreso, Keiko Fujimori, Papa León XIV, sismo(s), terremoto, política, mundo, Estados Unidos, policía, delincuencia, extorsión, seguridad ciudadana, educación y cultura. **No entran** salud, Minsa, dengue ni economía, que pueden ser efectos del clima.
2. **Clases** (entrenamiento de enero a agosto):
   - *positiva:* `sobre_nino` = 1 (1.167) más la zona gris sin ver con alguna etiqueta de `ETIQUETAS_CLIMA_MAR` (1.721);
   - *negativa:* `otros_temas` sin ninguna etiqueta de clima o mar (se quitan 574, en entrenamiento y prueba), más los **negativos difíciles**: la zona gris sin ver con alguna etiqueta de `ETIQUETAS_OTRO_TEMA` y ninguna de clima o mar, ni siquiera de las cuatro excluidas (1.639);
   - el resto de la zona gris sigue fuera.
3. **Rasgos y modelo:** como en la sección 10 (vector minilm de titular y resumen, regresión logística balanceada, C por validación cruzada de 5 grupos solo con el entrenamiento). Cambian dos cosas:
   - **τ:** el menor que deja pasar, en la CV, ≤ 1 % de `otros_temas` **y** ≤ 5 % de los negativos difíciles;
   - **grilla de C** de 0,1 a 100, porque en la sección 10 quedó en el borde;
   - la única otra elección en la CV es con o sin los textos oficiales (opción C).
4. **En Verificar:** igual que en 10.2.5, detrás del selector `FILTRO_DE_TEMA`, que sigue en `"palabras"` hasta que pase 12.5.
5. **Comandos previstos:** `python -m radar.app.tema entrenar|muestra|cuerpos|validar --clima-mar`, con la prueba "App: clasificador de tema con clima y mar" en `validacion.csv`. No escribe en `eventos.csv`.

### 12.4 Muestras de prueba (septiembre al corte)
- **Nuevas, nunca usadas:**
  - *clima y mar, corto:* las de la zona gris con alguna etiqueta de `ETIQUETAS_CLIMA_MAR` (416, con 338 plantillas). Se cuenta **una por plantilla de titular** (sin números, días ni meses), para que los pronósticos diarios no pesen de más;
  - *negativos difíciles, corto:* los 2.381;
  - *cuerpo:* hasta 50 por medio de cada uno de los dos grupos (unas 126 y 150; El Tiempo no tiene, y Exitosa tiene 26 de clima y mar), con semilla nueva, leídas en memoria con `Medio.leer` y sin guardar el cuerpo;
  - *avisos del Senamhi* de septiembre al 19-nov, si la opción C entró (no se usan para entrenar);
  - *sintéticos nuevos*, escritos antes de medir y distintos de los de 9.4 y 10.3: 10 usos de «niño» con otro sentido, 10 menciones del fenómeno, 20 textos del tema sin «El Niño» (10 de clima y 10 de mar y pesca) y 10 de otros temas con palabras de clima (un sismo, el dengue, un «clima político», un «mar de gente»). Todos inventados.
- **Reutilizadas, y se declara:** las 10.506 de `otros_temas` y las 1.618 sobre El Niño de septiembre al corte ya se midieron en las secciones 9 y 10, sin entrenar ni elegir nada con ellas. No quedan otras, así que se usan con `--repetir`. En cuerpo se usan los vectores de inicio ya guardados en `tema-c-cuerpos.csv` (400 y 399), sin volver a leer las notas.
- Después de medir, las nuevas pasan a `config/notas_vistas.csv` con la muestra `validacion-clima-mar`.

### 12.5 Criterios (fijados antes de construir)
| | Criterio | Umbral |
|---|---|---|
| K1 | Negativos difíciles con «Alta», corto (2.381, nuevas) | ≤ 2 % y menos que la sección 9 en las mismas notas |
| K2 | Negativos difíciles con «Alta», cuerpo (~150, nuevas) | ≤ 2 % y no peor que la sección 9 |
| K3 | `otros_temas` con «Alta», corto (10.506) y cuerpo (400), reutilizadas | ≤ 1 % y ≤ 2 %, y no peor que la sección 9 (0,97 % y 1,75 %) |
| K4 | Clima y mar que quedan fuera, corto (338 plantillas, nuevas) | no peor que la sección 9 en las mismas notas más 2 puntos |
| K5 | Clima y mar que quedan fuera, cuerpo (~126, nuevas) | ≤ 5 % |
| K6 | Sobre El Niño que quedan fuera, corto (1.618, reutilizadas) | no peor que la sección 9 (10,9 %) |
| K7 | Sintéticos: «niño» con otro sentido que pasa / el fenómeno que no pasa / del tema sin «El Niño» fuera / de otros temas con palabras de clima que pasan | 0 / 0 / ≤ 2 de 20 / ≤ 2 de 10 |
| K8 | Avisos del Senamhi que quedan fuera; K4 y K5 por medio | informativo |
| K9 | La app: P1 a P12, U1 a U6 e I1 a I5; P2 (mediana de Verificar ≤ 2 s) | todos |
| K10 | Preguntar sin cambios | 0 decisiones distintas |

- **Lógica de la decisión:** el clasificador gana solo si **rechaza mejor los otros temas con palabras de clima** (K1, K2) **sin perder** clima, mar ni El Niño frente al filtro (K4 a K6). El margen de 2 puntos en K4 es el error que se acepta a cambio de K1.
- **Si K1 a K7 pasan,** `FILTRO_DE_TEMA` pasa a `"clasificador"` y P13 entra a la sección 6. Si no, sigue el filtro de palabras y se declaran los números de K1 y K2, que son nuevos.
- **Alternativa J, fijada ahora:** si fallan K4 o K6 pero pasan K1 a K3, K5 y K7, se mide una sola vez la combinación «nombra el fenómeno, o pasa el filtro de palabras y el clasificador», con los mismos criterios, y se declara como segunda medición.
- **Riesgos declarados:**
  - casi todas las etiquetas son de Andina y RPP: el modelo puede aprender su estilo. K8 lo informa por medio, y El Tiempo queda sin medir en clima y mar;
  - las etiquetas de otro tema pueden caer en notas que sí son del tema (un sismo con lluvias, una nota política sobre la emergencia). Si pasa, el error va en contra del clasificador en K1, no a su favor;
  - el mar queda con pocos positivos (oleaje, anchoveta, IMARPE, mar peruano): K7 lo mide con 10 sintéticos.
- **Archivos:** `radar.comun.dominio` (las dos listas), `radar.app.tema` (la opción `--clima-mar`), `radar.app.servicio` (solo el selector, si pasa) y sus pruebas, con notas sintéticas.

### 12.6 Resultados (23-nov): no pasa; la app sigue con el filtro de la sección 9
- **Código:**
  - las listas `ETIQUETAS_CLIMA_MAR`, `ETIQUETAS_CON_OTRO_SENTIDO` y `ETIQUETAS_OTRO_TEMA` están en `radar.comun.dominio`;
  - el clasificador está en un módulo propio, `radar.app.tema_clima` (`muestra`, `entrenar`, `cuerpos`, `validar [--repetir]`), no en una opción `--clima-mar` de `radar.app.tema`: así no se mezclan las dos pruebas;
  - `FILTRO_DE_TEMA` sigue en `"palabras"`;
  - pruebas en `tests/app/test_tema_clima.py`.
- **Orden:** la muestra se fijó antes de entrenar (`tema-clima-muestra.csv`). Se leyeron 272 de 276 cuerpos (4 sin texto, todos negativos difíciles). Las 2.797 notas nuevas pasaron a `config/notas_vistas.csv` (`validacion-clima-mar`).
- **Entrenamiento** (enero a agosto): 1.167 notas del tema, 1.721 de clima y mar, 45.613 de otros temas y 1.639 negativos difíciles.
  - Average precision en la CV: de 0,895 (C = 0,1) a 0,919 (C = 100). C volvió a quedar en el borde, con la curva plana.
  - **Los textos oficiales (opción C) no entraron:** con ellos la CV da un poco menos (0,918), como se esperaba por su registro.
  - τ = 0,903: el tope de los negativos difíciles (≤ 5 %) es el que manda.

| Criterio | Clasificador | Sección 9 en las mismas notas | Umbral | Pasa |
|---|---|---|---|---|
| K1. Negativos difíciles con «Alta», corto (2.381, nuevas) | 0,76 % (18; IC 0,48 a 1,19) | 2,35 % (56) | ≤ 2 % y menos | Sí |
| K2. Negativos difíciles con «Alta», cuerpo (146, nuevas) | 3,42 % (5; IC 1,5 a 7,8) | 5,5 % (8) | ≤ 2 % y no peor | **No** |
| K3. `otros_temas` con «Alta», corto (10.408) / cuerpo (400), reutilizadas | 0,27 % / 0 % | 0,88 % (92) / 1,75 % (7) | ≤ 1 % / ≤ 2 % y no peor | Sí |
| K4. Clima y mar que quedan fuera, corto (338 plantillas, nuevas) | 12,4 % (42) | 4,7 % (16) | ≤ sección 9 + 2 puntos | **No** |
| K5. Clima y mar que quedan fuera, cuerpo (126, nuevas) | 9,5 % (12; Andina 9 de 50) | 0 % | ≤ 5 % | **No** |
| K6. Sobre El Niño que quedan fuera, corto (1.618, reutilizadas) | 12,7 % (206) | 10,9 % (176) | no peor | **No** |
| K7. Sintéticos: «niño» con otro sentido / el fenómeno / del tema sin «El Niño» fuera / otros temas que pasan | 0 / 0 / 7 de 20 / 0 de 10 | — | 0 / 0 / ≤ 2 / ≤ 2 | **No** |
| K8. Textos oficiales de septiembre al corte que quedan fuera | 30 de 292 | — | informativo | — |
| K10. Preguntar sin cambios | 0 cambios (A4 0,951) | — | 0 | Sí |

- **K9 no se midió:** el selector no cambia, así que la app es la misma que pasó P1 a P12, U1 a U6 e I1 a I5.
- **La alternativa J no aplica:** pedía que pasaran K2, K5 y K7, y no pasan.
- **Lectura:**
  - las etiquetas de clima y mar sí cambiaron lo que aprende el modelo: rechaza mucho mejor los otros temas, también los que usan palabras de clima (K1: tres veces menos «Alta» que el filtro), y no deja pasar ninguno de los 10 sintéticos ajenos;
  - pero sigue perdiendo clima y mar: 7 de 20 sintéticos (ola de calor, déficit hídrico, granizada, oleaje, anchoveta, pesca), 12 % de los titulares de clima y mar y 10 % de sus cuerpos. El tope de los negativos difíciles sube τ, y lo que se gana en rechazo se pierde en el tema;
  - con 1.721 positivos de clima y mar, casi todos de Andina y RPP y del verano lluvioso, el modelo no generaliza al mar ni a la pesca.
- **Lo nuevo que deja medido:** el filtro de palabras tiene más «Alta» en los otros temas con palabras de clima de lo que decían F1 y C1: 2,35 % en corto y 5,5 % en cuerpo (8 de 146). Se declara como límite de Verificar.
- **Por qué no se ajusta:** la prueba ya se miró. Bajar τ o cambiar los topes ahora sería elegir con la prueba, y no quedan notas de la zona gris etiquetadas sin usar.

## 13. «Alta» anclada al tema en Verificar, con una prueba externa (aprobada el 23-nov con la prueba externa de 2025; construida, no pasa)

### 13.1 Qué falla, medido en desarrollo (enero a agosto, 23-nov)
- **El problema no es tanto quién pasa el filtro como quién recibe «Alta».** De 1.500 negativos difíciles (zona gris con etiquetas solo de otros temas), el 4,93 % recibe «Alta» con el filtro de palabras.
- **Causa:** 76 de las 90 «Alta» de los negativos difíciles de enero a agosto tienen como párrafo más cercano una **recomendación del ENFEN**, escrita en lenguaje general de gestión de riesgos («gobiernos regionales», «prevención», «emergencia»). Ya se había visto que esos párrafos atraen textos, y que quitarlos baja E4 de 0,873 a 0,800 ([nlp/discrepancia.md](../nlp/discrepancia.md)): por eso no se sacan, se anclan. Casi todos esos textos pasan el filtro solo por palabras **genéricas**: sismos con «emergencia», elecciones con «alerta», un balance de daños con «prevención».
- **Por qué fallaron los clasificadores:** también los veto. Un veto con el clasificador de la sección 12, fijado para conservar el 98 % de los positivos, deja pasar la mitad de negativos difíciles (19,4 % a 9,7 %), pero la «Alta» solo baja de 4,93 % a 3,87 %. Veta lo que ya era «Media» o «Baja», no lo que se parece a una recomendación.
- **Ruido de las etiquetas:** algunos negativos difíciles sí son del clima («Normas Legales: declaran emergencia en 134 distritos por intensas lluvias», con la etiqueta «política»). Esto castiga a cualquier regla que los deje pasar; se declara.

### 13.2 Mapa de enfoques
**Dónde actuar:**

| Opción | Lectura |
|---|---|
| En el filtro de tema (secciones 9, 10 y 12) | El reemplazo falló dos veces, y el veto apenas toca la «Alta». |
| **En la «Alta», que es lo que lee el ciudadano** | **Elegida.** El error está en una combinación concreta (párrafo de recomendación más palabras genéricas), y se puede corregir sin tocar el filtro ni el semáforo de `radar.nlp`. |
| En el corpus: sacar las recomendaciones de la comparación | Cambia el semáforo (S1 a S6), el agente y el Panorama. No cabe antes del 27-nov. |
| En la interfaz: «tema dudoso» con aviso | Cambia textos y repite U1 a U6. Queda como opción. |

**Qué regla** (desarrollo, 1.500 notas por grupo como máximo; «pasa» es el filtro de tema y «Alta» la cercanía mostrada):

| Regla | El Niño pasa / Alta | Clima y mar pasa / Alta | Negativos difíciles pasa / Alta | `otros_temas` pasa / Alta |
|---|---|---|---|---|
| Palabras (hoy) | 93,7 % / 57,75 % | 94,3 % / 55,87 % | 19,7 % / 4,93 % | 7,8 % / 0,73 % |
| Veto con el clasificador (98 %) | 93,1 % / 57,67 % | 92,1 % / 55,67 % | 9,7 % / 3,87 % | 1,2 % / 0,20 % |
| Palabras específicas en el filtro (las genéricas no cuentan solas) | 91,9 % / 57,07 % | 90,0 % / 53,87 % | 4,5 % / 1,20 % | 2,4 % / 0,13 % |
| **«Alta» anclada:** sin «Alta» si el párrafo es una recomendación y el texto no tiene palabras específicas | 93,7 % / 57,07 % | 94,3 % / 55,20 % | 19,7 % / **1,53 %** | 7,8 % / **0,33 %** |

- **Elegida: «Alta» anclada.** Baja la «Alta» de los negativos difíciles un 69 % sin perder ninguna nota del tema en el filtro. Su costo es que el 1,2 % de las «Alta» de clima y El Niño pasan a «Media».
- Las palabras específicas en el filtro bajan algo más la «Alta» (1,20 %), pero dejan fuera 4 puntos de clima y mar. Quedan como alternativa.
- Las palabras genéricas se eligieron mirando estos ejemplos de desarrollo. Por eso la prueba tiene que ser otra (13.5).

**Con qué se prueba:**

| Opción | Lectura |
|---|---|
| **Notas de octubre a diciembre de 2025 de Andina y RPP** | **Elegida, si la apruebas.** Mismos medios, mismas vías del histórico, mismas etiquetas, y nadie las vio. Ver los límites de 13.4. |
| Notas posteriores al corte (21 al 27-nov) | Pocas para criterios del 2 % y fuera del corte. |
| Reutilizar 2026 de septiembre al corte con `--repetir` | La regla no se eligió con esas notas, pero ya se miraron dos veces. Es lo que queda si no se aprueba 2025, y se declara. |

### 13.3 Qué se construye
1. **Palabras genéricas** en `radar.comun.dominio` (`PALABRAS_GENERICAS`), fijas antes de medir: emergencia, alerta, evento, prevención, comunicado, costa, vigilancia, aviso, fenómeno y anomalía. Son las de `PALABRAS` que también usan los textos de emergencias, política o sismos. `palabras_especificas(texto)` es el resto.
2. **En `radar.app.servicio.verificar`:** si la cercanía es «Alta», el párrafo más cercano es de tipo `recomendacion` y el texto no tiene palabras específicas ni nombra el fenómeno, la banda pasa a la de «Media» y el color se vuelve a combinar con la misma regla del semáforo. El resultado lleva `anclaje: "recomendacion_general"` para el registro de la medición, no para el ciudadano. El filtro de tema, el semáforo de `radar.nlp`, el Panorama y Preguntar no cambian.
3. **Prueba externa** (si se aprueba), con `python -m radar.noticias.externa leer`:
   - Andina con uno de cada dos números de nota de octubre a diciembre de 2025 (unos 6.000 números, cerca de 12.000 peticiones) y RPP completo por su archivo por día (unas 6.000 notas). A 1 s por host y en paralelo, unas **3,5 a 4 horas**;
   - **sin filtrar por palabras** antes de leer: así la prueba no favorece al filtro;
   - `radar.comun.http.Cliente`, `@exclusivo` y `energia.sin_suspension`; cuerpo solo en memoria; escribe en `data/processed/externa/notas-2025.csv` con el esquema de `notas.csv` (titular, resumen, etiquetas, rasgos), nunca en `notas.csv`;
   - **antes de leer todo**, una prueba de 20 notas por medio confirma que en 2025 las vías funcionan y que las notas traen etiquetas. Si no, se mide con 2026 reutilizada.

### 13.4 Límites de la prueba externa
- **Fecha de la medición:** el corpus oficial empieza el 18-dic-2025, así que en octubre y noviembre de 2025 no hay párrafos vigentes. Cada nota de 2025 se mide **con su mismo día en 2026** (un año después, como máximo el 20-nov). Es como pegar ese texto en Verificar en 2026, que es el uso real; se declara.
- **Volumen esperado**, con las tasas de 2026: unas 300 notas de clima y mar y unas 1.500 de negativos difíciles. Sobre El Niño habrá pocas en esos meses de 2025: si un grupo tiene menos de 100, su criterio pasa a informativo.

### 13.5 Muestras de prueba
- **Externa (2025, nueva):** todas las notas de los cuatro grupos de 12.3 en corto, y clima y mar contadas una por plantilla. En cuerpo, hasta 50 por medio y grupo, leídas en memoria.
- **2026 reutilizada** (septiembre al corte, `--repetir`): las mismas de 12.4 y los vectores y bandas de cuerpo ya guardados, como segunda vista.
- **Sintéticos nuevos**, escritos antes de medir y distintos de todos los anteriores: 10 de otros temas con solo palabras genéricas (un sismo con «emergencia», una alerta sanitaria), 10 de otros temas con palabras específicas de otro sentido («ola de robos», «lluvia de goles») y 20 del tema sin «El Niño» (clima y mar).

### 13.6 Criterios (fijados antes de construir; se miden en la prueba externa)
| | Criterio | Umbral |
|---|---|---|
| V1 | Negativos difíciles con «Alta», corto | ≤ 2 % y ≤ 50 % de los del filtro de palabras en las mismas notas |
| V2 | Negativos difíciles con «Alta», cuerpo | ≤ 2 % y no peor que hoy |
| V3 | `otros_temas` con «Alta», corto / cuerpo | ≤ 1 % / ≤ 2 % y no peor que hoy |
| V4 | Clima y mar: de sus «Alta» de hoy, cuántas pasan a «Media» (corto y cuerpo) | ≤ 3 % |
| V5 | Sobre El Niño: lo mismo | ≤ 3 % |
| V6 | Sintéticos: de otros temas con «Alta» / del tema con «Alta» que pasa a «Media» | ≤ 1 de 20 / ≤ 1 de 20 |
| V7 | Lo mismo en 2026 reutilizada (V1 a V5) | informativo |
| V8 | La app: P1 a P12, U1 a U6 e I1 a I5; P2 (mediana de Verificar ≤ 2 s) | todos |
| V9 | Preguntar, Panorama y semáforo de `radar.nlp` sin cambios | 0 diferencias |

- **Decisión:** si pasan V1 a V6 y V8, la regla queda activa en Verificar, y P13 («otros temas con «Alta» en Verificar ≤ 2 %, también con palabras de clima») entra a la sección 6. Si no, se retira y se declaran los números.
- **Riesgos declarados:**
  - el filtro de tema no cambia: el 19 % de los negativos difíciles sigue entrando, ahora casi siempre con «Media» o «Baja»;
  - los titulares sobre El Niño sin palabras del tema (F2, 9 %) siguen fuera;
  - 2025 es otro año: si ahí se habla distinto, se verá en V7 frente a V1 a V5.
- **Archivos:** `radar.comun.dominio` (`PALABRAS_GENERICAS`), `radar.app.servicio` (el anclaje), `radar.app.validar_anclaje` (nuevo: muestra, medición y la prueba "App: Alta anclada"), `radar.noticias.externa` (nuevo, solo si se aprueba 2025) y sus pruebas con HTML y notas sintéticas.

### 13.7 Resultados (23-nov, una sola medición)
**Prueba externa leída:**
- 14.701 notas de octubre a diciembre de 2025: 4.878 de Andina y 9.823 de RPP.
- Sin errores de red al final ni bloqueos; las notas fuera de fechas y los números sin nota quedan en `intentos-2025.csv`.
- La lectura tomó unas 5 horas, no 3,5 a 4. Desde las 20:43 se pide en paralelo: hasta `config.HILOS_POR_HOST` (4) peticiones en curso por host, con el mismo ritmo de 1 s entre el inicio de una y la siguiente. Si el servidor falla, baja a la mitad.

**Grupos:**
- En corto: 14 notas sobre El Niño, 206 de clima y mar (una por plantilla), 333 negativos difíciles y 12.210 de `otros_temas`.
- En cuerpo: 14, 99, 90 y 100 leídos; 11 no se pudieron leer.
- Hubo muchos menos negativos difíciles que los 1.500 esperados (13.4).

| | Resultado | Umbral | Pasa |
|---|---|---|---|
| V1 | Negativos difíciles con «Alta», corto: 1,20 % (IC 0,47 a 3,05), 4 de 333; hoy 21 | ≤ 2 % y ≤ 50 % de hoy | Sí |
| V2 | Negativos difíciles con «Alta», cuerpo: 7,78 % (IC 3,82 a 15,19), 7 de 90; hoy 15 | ≤ 2 % y no peor que hoy | Informativo (90 de 100 cuerpos); estaría lejos del umbral |
| V3 | `otros_temas` con «Alta»: corto 1,02 % (IC 0,85 a 1,21), 124 de 12.210 (hoy 145); cuerpo 4,00 % (IC 1,57 a 9,84), 4 de 100 (hoy 4) | ≤ 1 % / ≤ 2 % y no peor que hoy | **No** |
| V4 | Clima y mar: «Alta» que pasan a «Media», corto 0 de 169 y cuerpo 0 de 86 | ≤ 3 % | Sí |
| V5 | Sobre El Niño: corto 0 de 7 y cuerpo 0 de 5 | ≤ 3 % | Informativo (14 notas) |
| V6 | Sintéticos: 1 de 20 de otros temas con «Alta» («Alerta por estafas telefónicas…») / 0 de 20 del tema pasan a «Media» | ≤ 1 / ≤ 1 | Sí |
| V7 | 2026 reutilizada: V1 1,55 % (39 de 2.522; hoy 59), V3 corto 0,61 % (hoy 92 de 10.408), V4 4 de 310, V5 8 de 876 | informativo | Coincide en el sentido |
| V8 | No se midió: la regla no se activa | todos | — |
| V9 | Preguntar sin cambios: 0 diferencias | 0 | Sí |

**Decisión:**
- **No pasa V3,** así que la regla no se activa: `ANCLAR_ALTA = False` en `radar.app.servicio`.
- El anclaje baja la «Alta» de los textos cortos de otros temas con palabras de clima. Es mucho en los negativos difíciles (de 21 a 4) y poco en `otros_temas` (de 145 a 124, que queda sobre el 1 %).
- En el texto completo casi no ayuda: los cuerpos de otros temas siguen con 4 % a 8 % de «Alta». No se midió por qué; mirarlo aquí ya no sería una prueba nueva.
- Se declaran los números de hoy sin el anclaje: negativos difíciles 6,3 % en corto y 16,7 % en cuerpo; `otros_temas` 1,19 % en corto y 4 % en cuerpo.
- Queda pendiente, para después del congelamiento, la «Alta» del texto largo de otros temas, con muestras nuevas.

## 14. Arranque de la app sin torch (aprobada el 23-nov, sin calentar el agente; construida y activa)

### 14.1 Dónde se va el tiempo (medido el 23-nov)
**Arranque de hoy:** mediana de **17,7 s** en 3 arranques en frío (17,3, 17,7 y 17,7 s). Antes se habían medido 15,6 y 16,9 s, porque varía con lo que el disco tenga en memoria. P2 pide ≤ 90 s, así que pasa.

| Paso | Segundos | Qué es |
|---|---|---|
| Importar la API | 2,8 | sobre todo scikit-learn (1,4 s), que importa el agente |
| `servicio()` | 11,6 | importar `sentence-transformers`, `transformers` y `torch` (unos 10 s, con scikit-learn ya cargado) y cargar MiniLM (1,1 s) |
| `panorama()` | 1,1 | leer los resultados precalculados |
| Consulta de calentamiento de Verificar | 0,1 | — |

- **Del arranque, unos 10 s son importar librerías, no calcular.** Solo en `transformers.utils.import_utils` se van unos 4 s, porque al importarse recorre las 298 distribuciones instaladas.
- **Al arrancar se carga un solo modelo:** MiniLM, para el semáforo de Verificar. Los vectores oficiales ya están en disco.
- **El otro modelo, e5-small, se carga en la primera pregunta.** Lo usa el clasificador de intención de Preguntar (`agente.Enrutador`). Esa primera pregunta tarda **4,1 s** (cargar e5, 2,0 s; embeber las 171 preguntas de desarrollo, 0,6 s; entrenar la regresión), y la segunda 0,03 s.
- **Por eso no basta con pasar MiniLM a ONNX.** Si solo se cambia ese modelo, la primera pregunta tendría que importar `torch` y `transformers` (unos 10 s más) y empeoraría. Los dos modelos tienen que dejar `torch`.
- **Sin internet:** con el registro de `httpx`, `urllib3` y `huggingface_hub` activado, el arranque y la primera pregunta hacen **0 peticiones** a Hugging Face.
- `radar.nlp.viabilidad` ya tiene un motor ONNX (`Onnx`), pero usa el tokenizador de `transformers`.

**Prueba de viabilidad (23-nov), con MiniLM:**
- Se embebieron 304 textos: 300 párrafos oficiales y 4 sintéticos.
- Se usó su `onnx/model.onnx` en float32, que ya está en la caché local, con `onnxruntime` y la librería `tokenizers` sola.
- Frente a `sentence-transformers`, el coseno mínimo es **0,99999992** y la mayor diferencia es 2,5 × 10⁻⁷. Cargar el modelo toma **1,2 s**, y `onnxruntime` con `tokenizers` se importan en 0,2 s.
- **Con e5 no se probó:** en la caché solo está su versión cuantizada. El repositorio oficial `intfloat/multilingual-e5-small` sí trae `onnx/model.onnx` en float32 (470 MB, consultado el 23-nov) y su `tokenizer.json`.

### 14.2 Mapa de enfoques
| Enfoque | Ganancia esperada | ¿Cambia resultados? | Lectura |
|---|---|---|---|
| **ONNX en float32 con `tokenizers` para los dos modelos, sin `torch` ni `transformers` en la API** | arranque de 17,7 a unos 6 s; primera pregunta de 4,1 a unos 3 s | No: mismos vectores (14.1, MiniLM) | **Elegido** |
| Solo MiniLM en ONNX | el arranque igual | No | Empeora la primera pregunta (14.1). Descartado |
| ONNX cuantizado (ya en la caché para los dos) | algo más | Sí: otros vectores | Obliga a repetir S1 a S6 y la ronda c del agente. Descartado |
| Calentar también el agente al arrancar | primera pregunta en 0,03 s | No | Suma unos 3 s al arranque. Decisión aparte (14.4) |
| Cargar los modelos en segundo plano: la página y el Panorama en unos 3 s, y Verificar y Preguntar esperan | percibida, no total | No | Cambia la interfaz (un estado «preparando», textos, U1 a U6). Queda como complemento posible |
| Entorno mínimo (un `venv` con solo lo de la app) | unos 4 s | No | No quita `torch` y obliga a reinstalar todo. Descartado |
| Parchear la búsqueda de distribuciones de `transformers` | unos 4 s | No | Toca el interior de una librería; frágil. Descartado |
| Excluir la carpeta del antivirus | sin medir | No | Cambia la seguridad del sistema. Descartado |
| Dejar la API siempre encendida | no baja el arranque | No | Ya es así en uso; no resuelve el problema |
| Modelo más chico o destilado | algo | Sí | Repetir todo. Descartado |

### 14.3 Qué se construye
1. **Motor de la app** en `radar.nlp`:
   - ONNX en float32 con el tokenizador de `tokenizers` (`tokenizer.json` del mismo repositorio), el mismo promedio de tokens y la normalización;
   - contar tokens y partir en tramos con ese mismo tokenizador (`add_special_tokens=False`), como hoy;
   - `config.MOTOR_APP = "onnx32"`;
   - el semáforo (`candidatos.Candidato`, MiniLM) y el agente (`embeddings.Modelo("e5")`) lo usan dentro de la API. Los estudios de `radar.nlp` siguen con `torch`.
2. **Archivos del modelo** (no se versionan; quedan en la caché de Hugging Face):
   - MiniLM: `onnx/model.onnx`, que ya está;
   - e5-small: `onnx/model.onnx` (470 MB), que se baja una vez del repositorio oficial. **Aprobar esta definición es el permiso para bajarlo.**
3. **Si falta un archivo ONNX,** la API lo dice en el registro y usa `torch` para ese modelo: nunca deja de funcionar.
4. La API sigue sin pedir nada a internet (`HF_HUB_OFFLINE=1`).

### 14.4 Criterios (fijados antes de construir)
Los nombres H1 a H7 no chocan con los criterios A1 a A5 del agente.

| | Criterio | Umbral |
|---|---|---|
| H1 | Mismos vectores: coseno mínimo entre ONNX y `torch`, en todos los párrafos oficiales (MiniLM sin prefijo y e5 con el suyo), en las 171 preguntas de desarrollo del agente (e5) y en 40 sintéticos nuevos | ≥ 0,9999 (el umbral de E2) |
| H2 | Verificar igual: misma banda, color y párrafo más cercano en una muestra nueva de 300 notas no vistas (titular y resumen, repartidas entre los 4 medios) y en los 25 casos de P1 | 100 % |
| H3 | Preguntar igual: misma herramienta y mismo texto de respuesta en `config/agente_preguntas_c.csv` y en 20 sintéticos nuevos | 100 % |
| H4 | Arranque: mediana de 3 arranques en frío, medidos igual que en 14.1; y la API no carga `torch`, `transformers` ni `sentence_transformers` | ≤ 8 s (hoy 17,7) y 0 módulos |
| H5 | Primera pregunta después del arranque: mediana de 3 | no peor que hoy (4,1 s) |
| H6 | La app: P1 a P12, U1 a U6 e I1 a I5; P2 (mediana de Verificar ≤ 2 s) | todos |
| H7 | Sin red (`HF_HUB_OFFLINE=1`): 0 peticiones a Hugging Face. Sin un archivo ONNX, ese modelo vuelve a `torch` y H2 y H3 siguen iguales | sí / sí |

- **Decisión:**
  - si pasan H1 a H7, el motor ONNX queda por defecto en la API;
  - si falla H1, H2 o H3, se retira y sigue `torch`;
  - si solo falla H4 (más de 8 s), se declara el tiempo y el motor se queda si baja de 17,7 s.
- **El agente no se calienta al arrancar, como hoy.** Así H4 mide lo mismo que 14.1. Si lo prefieres calentado (unos 3 s más de arranque y primera pregunta al instante), dilo al aprobar y H4 pasa a ≤ 11 s.
- **Riesgos declarados:**
  - otra versión de `onnxruntime` podría dar diferencias mínimas; H1 lo controla;
  - quien instale la app necesita los dos archivos ONNX en su caché: el README dirá cómo traerlos, y sin ellos la app usa `torch`;
  - e5 aún no se probó en ONNX: si su `onnx/model.onnx` no reproduce a `torch` (H1), solo MiniLM no sirve (14.2), y se retira todo.
- **Archivos:** `radar.nlp.viabilidad` (o un módulo nuevo `radar.nlp.motor`), `radar.nlp.candidatos`, `radar.nlp.embeddings`, `radar.config` (`MOTOR_APP`), `radar.app.validar_arranque` (nuevo: H1 a H5 y H7) y sus pruebas con textos sintéticos.

### 14.5 Resultados (23-nov, una sola medición)
**Qué se construyó:**
- `radar.nlp.motor` (`Onnx32` y `Tokenizador`), `config.MOTOR_APP = "onnx32"` y `config.DIR_MOTOR_APP`.
- El semáforo de la app (`semaforo._semaforo`) y el enrutador del agente usan el motor. Los estudios que arman su propio `Semaforo()` siguen con `torch`.
- `radar.app.validar_arranque` mide H1 a H5 y H7.
- **Hallazgo antes de medir:** con e5, el `tokenizer.json` del repositorio no da los mismos tokens que `transformers` 5.21. Difiere en los espacios repetidos (11 de 391 textos de desarrollo, coseno 0,9899). Por eso `python -m radar.nlp.motor preparar` guarda una vez el tokenizador tal como lo arma `transformers`; con eso, los tokens coinciden en 1.153 de 1.153 textos en los dos modelos.

| | Resultado | Umbral | Pasa |
|---|---|---|---|
| H1 | Coseno mínimo 0,9999998: 954 párrafos oficiales, 191 preguntas de desarrollo (con las de fuera de dominio; la definición decía 171) y 40 sintéticos | ≥ 0,9999 | Sí |
| H2 | Verificar: 320 de 320 iguales (300 notas nuevas y 20 textos de P1); la salida completa también, y el coseno mostrado no cambia | 100 % | Sí |
| H3 | Preguntar: 175 de 175 iguales (150 de la ronda c, 20 sintéticas nuevas y 5 de P1) | 100 % | Sí |
| H4 | Arranque: mediana de 5,5 s (5,7, 5,4 y 5,5); sin `torch`, `transformers` ni `sentence_transformers` | ≤ 8 s y 0 | Sí |
| H5 | Primera pregunta: mediana de 1,88 s (2,00, 1,81 y 1,88) | ≤ 4,1 s | Sí |
| H6 | P1 a P5 (arranque 2,7 s dentro de `validar`), P6 a P12, U1 a U6 e I1 a I5 pasan | todos | Sí |
| H7 | 0 peticiones a Hugging Face en los 3 arranques; sin el tokenizador, `para_app` devuelve `None` y se usa `torch` | 0 / sí | Sí |

**Decisión:** el motor ONNX queda activo en la API. El arranque baja de 17,7 a 5,5 s, y la primera pregunta de 4,1 a 1,9 s, sin cambiar ningún resultado.

**Registro de uso:** al abrir la app en el panel de vista previa para medir, se crearon 2 visitas en `data/processed/app/eventos.csv`. No eran uso real, así que se borró el archivo; `npm run medir` ya bloquea sus eventos.
