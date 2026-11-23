# Pendientes, por prioridad (actualizado el 23-nov-2026)

Orden según dependencias reales y fechas, revisado con lo aprendido en los pilotos; el calendario del README es orientativo. Cada tarea se define, se aprueba, se construye y se valida con muestras nuevas, una a la vez. Estado del índice de discrepancia y del flujo de NLP: [nlp/discrepancia.md](nlp/discrepancia.md).

## Por dónde seguir (actualizado el 23-nov)
**La recolección está cerrada** (corte del 20-nov): ya no hay rutina diaria. Quedan 4 días para el congelamiento (vie 27-nov). Alcance (decisión del 19-nov): solo el producto; no se planifican informe, declaración, avances semanales, presentación ni grabación. Cada tarea sigue el flujo de siempre: mapa de enfoques, definición con criterios fijados antes, aprobación del usuario, construcción (solo con su orden explícita) y validación con muestras nuevas.

1. **Modelo de engagement** (README, punto 11; insumo de ML del sílabo). **Hecho el 22-nov** (`python -m radar.modelos.engagement`; [modelos/engagement.md](modelos/engagement.md)): pasan M0 a M3. El boosting ordena por tipo con Spearman 0,43, mejora el MAE un 12,6 % frente a la persistencia, y el contenido agrega +0,063 (por poco); solo la cercanía es estable (M5).
   - **Datos:** YouTube del corte del 22-nov, con 1.007 videos para entrenar y 622 para probar (Y5; [youtube/definicion.md](youtube/definicion.md#13-resultados-del-corte-22-nov-2026)).
   - **Antes de definirlo:** el README fija la partición (entrenar con enero a agosto, probar con septiembre al corte) y excluye los videos con menos de 14 días. Como la descarga fue el 22-nov y no el 20-nov, el último video que entra es del 8-nov, no del 6-nov. Revisarlo al definir.
   - **Variables previstas:** el semáforo del título y la descripción del video, los tópicos y los rasgos del título, con los suscriptores y los días desde la publicación como controles. Las emociones **no** entran: la decisión del 17-nov las dejó solo descriptivas, aunque el README las lista.
2. **Red social con YouTube** (README, red; Y3 pasa con 151 canales). **Hecha el 22-nov** (`python -m radar.redes.youtube`; [redes/youtube.md](redes/youtube.md)): pasan R1, R2 (Q 0,241 frente a un p95 de 0,230) y R4; no pasa R3 (comunidades inestables); la pregunta 6 no es concluyente (R6 cambia el signo): red canal–canal por comentaristas compartidos (no co-mención: las @menciones no se guardan), con un nulo bipartito.
3. **Analítica web** (README, punto 10). **Hecha el 22-nov** (`python -m radar.analitica.web todo`; [analitica/web.md](analitica/web.md)): pasan W1, W6 y W9 a W11. La pregunta 5 da **sí**: dentro del canal, lo más alejado de lo oficial tiene algo más de engagement (ρ −0,17; IC −0,26 a −0,10), sin que lo que contradice tenga más. Trends no muestra relación medible con la cobertura (W8). Plan original: KPIs de engagement frente a la cercanía con lo oficial (Spearman, descriptivo), Trends por departamento alrededor de cada comunicado ([youtube/definicion.md](youtube/definicion.md#14-resultados-de-trends-segunda-exportación-22-nov-2026); Tumbes usa el promedio de dos exportaciones) e indicadores de los medios. Depende de 1 y 2 para lo de YouTube.
4. **Actualizar con las notas del corte** (corridas cortas, sin definición nueva). **Hecho el 22-nov:** discrepancia con 2.785 notas (74 % sin datos), eventos con 20 comunicados (14 de 20, mediana +51 %; V1 pasa y V2 no, sigue descriptivo), emociones del corte (solo descriptivas, M2 κ 0,232) y la app medida de nuevo (P1 a P12 y U1 a U6 pasan).
   - `python -m radar.nlp.discrepancia calcular`: es reanudable y solo agrega las notas que faltan. Quedó en 2.727 notas sobre El Niño y ahora hay 2.785.
   - `python -m radar.analitica.eventos validar --ronda c`, con los comunicados N.° 19 y 20 (sigue descriptivo).
   - Emociones de los comentarios del corte (`python -m radar.youtube.emociones`, unos 40 min), solo descriptivas.
5. **App** ([app/definicion.md](app/definicion.md), aprobada el 19-nov). **Hecha el 22-nov:** la API y la interfaz (`web/`: Verificar, Preguntar, Panorama A a F y Metodología) pasan P1 a P12 y U1 a U6 ([app/definicion.md](app/definicion.md#interfaz-pasos-2-a-4-22-nov)). Si cambian los datos (punto 4), se vuelven a correr `radar.app.validar`, `npm run medir` y `radar.app.validar_interfaz`. El 23-nov se agregó el filtro de tema en Verificar (sección 9): los textos de otros temas con «Alta» bajan de 5,8 % a 0,72 % en corto y de 6 % a 3 % en cuerpo (F1 en cuerpo no pasa y se declara). El clasificador de tema (sección 10) se construyó y no pasa C3 ni C5: rechaza textos de clima que no nombran a El Niño, así que sigue el filtro de palabras. Pendiente sin definir: etiquetas de clima y mar que no dependan de El Niño (avisos del Senamhi como positivos), con una prueba nueva. El 23-nov, Preguntar dejó de mostrar el texto interno del agente (fechas AAAA-MM-DD, ids como `enfen-2026-20` o `costa_norte` y "Semáforo: rojo (reglas)"): la respuesta se arma en `radar.app.textos` (`PREGUNTAR`, con U2 y U3), y el agente no cambia.
   - **23-nov, arranque:** los vectores de los párrafos oficiales se guardan en disco (`embeddings.con_cache`); el arranque bajó de 63,2 s a 15,6 s. Lo que queda (~14 s) es importar torch y transformers.
   - **23-nov, rediseño** ([app/definicion.md](app/definicion.md), sección 11): inicio «Hoy» con la zona y el mensaje en dos columnas, escalera de estados, regla de magnitud, avisos del Senamhi a la vista y glosario (ENFEN, Senamhi, El Niño costero, magnitud). Pasan I1 a I5, P1 a P12 y U1 a U6.
   - **23-nov, negación:** «no hay que…» y «no hay por qué…» ya no niegan el dato ([nlp/discrepancia.md](nlp/discrepancia.md)). Se recalcularon las 2.785 notas y no cambió ningún resultado.

**Antes del congelamiento (vie 27-nov):** nada obligatorio; los commits se subieron al repositorio del grupo el 23-nov. Opcionales, solo si sobra tiempo: etiquetas de clima y mar para el filtro de tema (sin definir), bajar el arranque que queda y la versión pública.

**Después del congelamiento:** volver a correr `python -m radar.analitica.web uso` tras la presentación.

**Borrado de YouTube:** los datos crudos vencen a los 30 días de la descarga (el día 1 fue el 16-nov, así que vence el 16-dic). Se borran con `python -m radar.youtube.borrar`.

## Estado al 23-nov
- **Noticias:** 81.879 notas de los 4 medios (1-ene al corte) y 2.785 sobre El Niño, con la macro-región asignada (`region.notas` pasa). La última recolección (22-nov) recuperó sus huecos ([recoleccion/diaria.md](recoleccion/diaria.md#recuperación-de-huecos-22-nov)).
- **Corpus oficial:** ENFEN hasta el comunicado N.° 20 (21 documentos) y avisos del Senamhi hasta el 477. Siguen dos fallas conocidas y declaradas: el control con `pypdf` del N.° 19 (0,974) y el acuerdo polígono/regla del Senamhi.
- **YouTube:** corte del 22-nov, en el que pasan Y1 a Y5 (1.762 videos, 154 con ≥ 30 comentarios, 151 canales conectados). Las emociones son solo descriptivas.
- **Trends:** dos exportaciones (17 y 22-nov) y la consulta nacional por región. G1 pasa y G2 no pasa por Tumbes (0,790), que usa el promedio.
- **Hecho y validado:**
  - histórico y viabilidad;
  - recálculo final (17-nov);
  - TF-IDF (no pasa T4) y embeddings (e5);
  - tópicos (polaridad descriptiva);
  - capas 3 y 5 del índice, con T5 informativo;
  - semáforo;
  - estudio de eventos (descriptivo);
  - recomendador (ronda b: R1 no pasa, así que se usa la cascada de 3 días);
  - agente (ronda c pasa);
  - red de enlaces (R2 no pasa para INDECI y PCM por enlaces SEO);
  - app: API e interfaz (P1 a P12 y U1 a U6), con el rediseño del 23-nov (I1 a I5).
  
  El NLI se cerró sin medir.
- **Sin empezar:** nada del alcance; el punto 4 se hizo el 22-nov.

## Rutina diaria (cerrada el 22-nov)
La recolección diaria terminó con el corte. Se registró en [recoleccion/diaria.md](recoleccion/diaria.md): ejecuciones, huecos del 16 y del 22-nov y cómo se recuperaron. Si hubiera que leer algo más: `python -m radar.noticias.historico` y `python -m radar.region.notas`. Un solo proceso a la vez pide páginas (`data/red.lock`).

## 1. Desbloquear YouTube y Trends (urgente: núcleo que no se recorta)
Desbloqueado: la clave existe desde el 16-nov y Trends se exportó el 17-nov. Lo que queda (corte del 21-nov, segunda exportación) está en "Por dónde seguir". La tabla se deja como registro de lo que se decidía.

| Prueba | Qué falta | Decide |
|--------|-----------|--------|
| **YouTube** (≥ 300 videos del período; ≥ 100 videos con ≥ 30 comentarios) | Crear la clave de YouTube Data API v3 en Google Cloud (la crea el usuario y la guarda en una variable de entorno, nunca en el repo ni en el chat) | Si la red social usa YouTube o la co-mención; si hay modelo de engagement. Toma 1-2 días de cupo |
| **Google Trends** por departamento (Tumbes, Piura, Lambayeque, La Libertad) | Exportar el CSV desde la web, una consulta por departamento para todo el período (pytrends está archivado) | Si el interés de búsqueda entra en la analítica y en el estudio de eventos |
| **Emociones de comentarios** (pysentimiento) | **Decidida el 17-nov** con los días 1 y 2 ([youtube/emociones.md](youtube/emociones.md#6-decisión-con-los-días-1-y-2-17-nov-2026)): pasan M0 y M1 (43,4 %), no pasan M2 (κ 0,16) ni M3 (κ 0,13) | **Solo descriptivas** (no entran al modelo ni al estudio de eventos) |
| **Versión pública (opcional)** | Decisión del 2-nov: la app principal corre en local. La versión pública solo se hace si hay tiempo, con e5-small cuantizado (0,78 GB) y sin NLI | Si hay demo pública |

**Decisión que depende de estas pruebas:** el insumo de ML depende del modelo de engagement (YouTube), porque el NLI ya quedó fuera de la app. Si YouTube no alcanza, la alternativa es un modelo que prediga el interés de Trends por semana y departamento a partir del volumen y el tono de las noticias y los comunicados.

## 2. Recálculo final, uno solo, antes del corte del 20-nov
Decisión del 1-nov: no se corren más recálculos completos (~10 h) después de cada corrección; ya fueron cuatro. Las correcciones se acumulan en el código y se recalcula **una sola vez**, con todo junto, antes del corte. Las notas nuevas de cada día ya se leen con el código vigente.

**Ya en el código, esperando ese recálculo:**
- Regla de menciones del 1-nov (FEN, "Fenómeno el Niño", "Código del Niño", "La Niña" como lugar) y su paso de causa "menciones" ([noticias/recalculo.md](noticias/recalculo.md#tercera-pasada-regla-de-menciones-1-nov)). Cambia menos del 1 % de las notas sobre El Niño.
- Fecha suelta de Andina (`Publicado: dd/mm/aaaa`) quitada del cuerpo el 1-nov, con su generación "fecha" en `recalculo.py`. La capa 1 se validó con dos semillas nuevas ([noticias/texto.md](noticias/texto.md#fecha-suelta-de-andina-1-nov-2026), [noticias/recalculo.md](noticias/recalculo.md#cuarta-corrección-fecha-de-andina-1-nov)). Cambia el sha1 de todas las notas de Andina, pero no sus rasgos.
- Notas de Andina en inglés reconocidas por el texto (1-nov; [noticias/definicion.md](noticias/definicion.md)). Ya no entran al consolidado ni a `region.notas` (quedan 76.646 notas y 2.378 sobre El Niño). En el recálculo, `Andina.leer` las rechaza como "en inglés" y quedan sin releer en `data/raw/`; el consolidado las vuelve a excluir. No hay que hacer nada más.

**Revisar o corregir antes de lanzarlo** (se agrega aquí lo que aparezca, sin recalcular):
- ~~Las 13 notas de RPP con menos de 0,9 del articleBody~~: declaradas el 17-nov (punto 6.1).
- ~~Confirmar que no hay `recalculo/` aplicados ni `*.anterior.csv`~~: confirmado el 17-nov; todos los anteriores ya tienen nombre propio.
- **Citas por número solo del ENFEN** (8-nov; [noticias/definicion.md](noticias/definicion.md#citas-por-número-sin-el-enfen-arreglo-del-8-nov-2026)). Pasa R1 a R3, y saldrán 34 citas de otras entidades (Ceplan, COEP, FAP…). `comunicados` no entra en las causas de M2: antes de `--aplicar`, comprobar que solo cambian esas notas. Después del recálculo, el control positivo de E3 queda limpio solo y `semaforo.positivo_limpio` da lo mismo; repetir `semaforo calibrar` y `validar`.
- Si alguna corrección nueva cambia el cuerpo o las menciones, agregar su generación y su paso de causa en `recalculo.py`, como "rescate" y "menciones".
- Confirmar que no hay directorios `recalculo/` ya aplicados ni `*.anterior.csv` en ningún medio (si los hay, renombrarlos; ver CLAUDE.md).

**Cómo lanzarlo:**
1. Ensayo corto, de unos 5 minutos: `python -m radar.noticias.historico --recalcular --todo --limite 200`, más `--informe`. Si algo falla, se corrige antes de gastar las 10 horas. Ese ensayo escribe en `recalculo/`; se borra o se renombra antes de la corrida completa.
2. Corrida completa de noche: `python -m radar.noticias.historico --recalcular --todo --horas 12`, después de una rutina diaria.
3. Revisar M1b a M5 y V1 a V3, y aplicar con aprobación: `--recalcular --aplicar`. Después, `region.notas`, `viabilidad resultados`, `redes.enlaces`, `nlp.tfidf vectores` y `nlp.embeddings criterios` (sus T1 y E1 comparan el sha1 con `notas.csv`).

## 3. Antes del NLP
1. ~~**Crear `src/radar/nlp/`** y pasar ahí las pruebas de viabilidad de modelos~~ Hecho el 1-nov: `python -m radar.nlp.viabilidad`, con pruebas sintéticas. D2 y memoria se reprodujeron ([nlp/viabilidad-modelos.md](nlp/viabilidad-modelos.md#cómo-se-corre)).

## 4. Semana 2 (2 a 8-nov), en orden de dependencias
1. ~~**Red de enlaces y citas**~~ Hecha el 1-nov: `python -m radar.redes.enlaces` ([redes/enlaces.md](redes/enlaces.md)). R1 pasa; R2 no pasa para Indeci, Cenepred y PCM, porque Exitosa enlaza palabras genéricas a esos sitios (SEO), no porque falten patrones. Repetida el 17-nov tras el recálculo: igual, con Cenepred ya en el umbral (18/20).
2. ~~**Preprocesamiento y TF-IDF**~~ Hecho el 1-nov: `python -m radar.nlp.tfidf` ([nlp/tfidf.md](nlp/tfidf.md)). **No pasa T4:** el AUC frente al control negativo es 0,80 (umbral 0,90). Las notas que hablan poco de El Niño, como las de medidas del Gobierno, no se parecen léxicamente a los párrafos del ENFEN. La lectura del corpus toma 23 min, así que no hace falta atar las etapas a una sola lectura.
3. ~~**Embeddings**~~ Hechos el 1-nov: `python -m radar.nlp.embeddings` ([nlp/embeddings.md](nlp/embeddings.md)). **Pasa con e5-small**, que empata con MiniLM en E4 (0,912 frente a 0,799 del TF-IDF); el semáforo del README se puede calibrar (E3: 0,951 en cuerpos y 0,901 en titulares, sin cruce), y e5 cuantizado da lo mismo. **Para el semáforo (semana 3):** un párrafo de definiciones del ENFEN es el más parecido para el 11,5 % de las notas (hubness), así que hay que decidir si los párrafos de `definicion` entran en la comparación. Repetidos el 17-nov tras el recálculo: pasan E1 a E5 y sigue e5 (E4 0,911).
3b. **Comparación de candidatos de embedding ([nlp/embeddings.md](nlp/embeddings.md)).** A y B cerradas el 5-nov: qwen3 se descarta con la muestra y el modelo elegido es **minilm**. **Sigue:**
   1. E cerrada el 7-nov: `buscar_oficial` usa minilm; las consultas por día del Senamhi van mejor con metadatos (`aviso_dias`). F (LLM como juez) solo si el equipo lo decide. C y D se cerraron el 6-nov sin cambios: el semáforo sigue solo con minilm. Su E4 en texto corto (0,860) no llega a 0,90, y hay que considerarlo al calibrar el semáforo. La rutina atrasada ya corrió el 6-nov.
4. **Hecho el 7-nov ([nlp/topicos.md](nlp/topicos.md)):** BERTopic k=12 (LDA inestable); P2 no pasa (κ 0,12), así que la polaridad es solo descriptiva. Antes: la polaridad se valida con el kappa frente a un zero-shot independiente (README). El cuerpo se parte en tramos de 128 tokens para robertuito.
5. ~~**Capas 3 y 5 del índice**~~ Hechas el 7-nov (`radar.nlp.afirmaciones`, `radar.nlp.temporalidad`, `radar.nlp.discrepancia`; [nlp/discrepancia.md](nlp/discrepancia.md)). La capa 3 pasa en estado y magnitud; la temporalidad (plazo v2) pasa de T1 a T4. La capa 5 pasa C1 a C6 en la ronda c y, con el código final, en las tres rondas; C3 se apoya en pocos casos.
6. **Red social:** YouTube o co-mención, según la prueba del punto 1.

## 5. Semana 3 (9 a 15-nov)
Índice de discrepancia, por orden:
1. ~~**Distancia dentro del semáforo**~~ Hecha el 7-nov: `radar.nlp.semaforo.medir_discrepancia(texto, fecha)` ([nlp/discrepancia.md](nlp/discrepancia.md#distancia-en-el-semáforo-punto-51-definición-aprobada-el-7-nov)). Usa los párrafos vigentes sin `definicion`, umbrales propios para corto (100 palabras o menos) y cuerpo, el verde desde el p95 del negativo y lo lejano en gris, nunca rojo. Si hay afirmaciones evaluables, manda la capa 5. Pasan S1 a S6. Se encontró que el control positivo de E3 tenía citas falsas (punto 2). Antes de usar los umbrales tras el recálculo final, hay que repetir `python -m radar.nlp.semaforo calibrar` y `validar`.
2. ~~**El único intento con NLI**~~ **Cerrado el 8-nov** sin cargar el modelo: con los pares naturales hay 0 casos que cambian en julio a octubre (mínimo 20), y 6 si la región es opcional. La app se queda con las reglas y la distancia ([nlp/discrepancia.md](nlp/discrepancia.md#resultado-8-nov-el-nli-se-cierra-sin-medir)).
3. ~~**Comunicado N.° 20**~~ Procesado el 16-nov: el corpus se reconstruyó (21 documentos del ENFEN), y temporalidad (T1 a T4) y capa 5 (`--solo-oficial`) pasan. Siguen sin pasar el control con `pypdf` del N.° 19 y el acuerdo polígono/regla del Senamhi, que ya fallaban antes.
4. **Después de T5 y del recálculo final:** `python -m radar.nlp.discrepancia calcular` (escrito el 8-nov; sin correr, porque leería las notas reservadas para T5). Deja `discrepancia-todas.csv` (una fila por dato, sin texto) y `discrepancia-todas-notas.csv` (color por nota); se puede cortar y relanzar.
5. **T5 (informativo, hasta el 18-nov):** las 242 notas sobre El Niño sin ver, más las que vayan llegando y las nuevas que citan al ENFEN. Con ellas se confirma de forma independiente la temporalidad y la capa 5, y se cuentan las rojas en notas que citan al ENFEN. No se usan para ajustar nada.

**Límites que quedan declarados, sin perseguirlos:**
- Las fechas del Pacífico central y la probabilidad no se comparan.
- Los avisos del Senamhi quedan fuera.
- El detector de certeza solo se midió en un sentido.
- La capa 3 no da a las frases de las notas la región que heredan del párrafo; solo lo hacen las frases oficiales.

Además, en la semana 3:
- Semáforo calibrado (punto 1).
- Estudio de eventos: `radar.analitica.eventos` ([analitica/eventos.md](analitica/eventos.md)). **Cerrado el 8-nov como descriptivo:** ninguna de las tres rondas controla el tamaño y la potencia con 18 eventos (la ronda c da V1 0,087 y V2 0,561, aunque V3 y V4 pasan). Se describe por comunicado: la proporción sobre El Niño sube en 14 de 18, con mediana +63 % frente a la semana anterior. Repetida el 22-nov con los N.° 19 y 20: 14 de 20, mediana +51 % (V1 ya pasa; V2 no).
- Modelo de engagement o su alternativa.
- Recomendador híbrido: `radar.analitica.recomendador` ([analitica/recomendador.md](analitica/recomendador.md)). La ronda a (8-nov) pasa la puerta, R2 a R4 y K2, pero no R1: lo más reciente le gana (MRR 0,387 frente a 0,196). Ronda b aprobada: la cascada fresca de 3 días, calibrada con A (MRR 0,425 frente a 0,387), se decide el **18-nov** con la muestra B (`validar --ronda b`, junto con T5). Requiere la recolección diaria hasta entonces.
- Agente con herramientas, sin LLM: `radar.agente` ([agente/definicion.md](agente/definicion.md)). La ronda a (9-nov) pasa A2 a A5 pero no A1 (0,83): las preguntas de recomendación se van a búsqueda. La ronda b (9-nov) tampoco: 0,874. La ronda c (desarrollo y prueba separados, clasificador de intención con TF-IDF y e5) **pasa**: A1 0,944 (IC 95 % de 0,904 a 0,984) y A2 a A6. Siguiente: la app (FastAPI + React). ChromaDB sigue sin instalar: el índice va en memoria detrás de la misma interfaz.

## 6. Menores, sin urgencia
1. ~~**13 notas de RPP con menos de 0,9 del articleBody**~~ Declaradas el 17-nov, sin corregir. Hoy son 17, incluidas 6 transmisiones en vivo, y ninguna es sobre El Niño ni lo menciona ([noticias/texto.md](noticias/texto.md#limitaciones-declaradas)).
2. ~~**Bug de `corpus --solo`**~~ Corregido el 8-nov: `validacion.csv` conserva las filas de la fuente que no corrió (`corpus.validacion_completa`).

## README
Al día al 19-nov: índice por capas sin NLI, polaridad descriptiva en las notas, la app en FastAPI + React y la sección "Producto" según [app/definicion.md](app/definicion.md).

El insumo de ML espera a la prueba de YouTube. Mientras tanto mandan [nlp/discrepancia.md](nlp/discrepancia.md), [nlp/viabilidad-modelos.md](nlp/viabilidad-modelos.md) y este archivo.

## Hecho (resumen; el detalle está en cada documento)
- **Recálculo de las notas con el texto limpio**, aplicado el 31-oct en dos pasadas: la general y la de RPP con el rescate de recomendados sin cerrar ([noticias/recalculo.md](noticias/recalculo.md)).
- **Capa 1 (texto limpio):** titulares ajenos y recomendados sin cerrar de RPP ([noticias/texto.md](noticias/texto.md)).
- **Capa 2 (corpus oficial limpio)** y regla de magnitud única para el ENFEN y las notas ([oficial/definicion.md](oficial/definicion.md), [nlp/magnitud.md](nlp/magnitud.md)).
- **Capas 3 y 5 del índice y temporalidad** (7-nov; [nlp/discrepancia.md](nlp/discrepancia.md)).
- **Pruebas de viabilidad de noticias** ([noticias/validacion-2026-10-24.md](noticias/validacion-2026-10-24.md)) y de modelos ([nlp/viabilidad-modelos.md](nlp/viabilidad-modelos.md)).
