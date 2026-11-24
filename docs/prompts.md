# Registro de prompts

Registro de la colaboración con IA generativa. Anotar fecha, propósito y prompt. Solo se registran los esenciales: los que definen, construyen o cambian algo. El registro completo hasta el 24-nov está en el historial de git (commit 60d0534).

## 2026-10-22 · Análisis de cobertura del sílabo (Claude Code, Claude Opus 5.5)
**Propósito:** contrastar el plan del README con el sílabo de INF656, identificar huecos y elegir opciones para cubrirlos.

**Prompts (resumen fiel, en orden):**
1. Analizar el repositorio de la idea 1 y decir qué está implementado y qué es solo plan.
2. ¿El sílabo pide entrenar un modelo propio?
3. Análisis exhaustivo y general de qué falta para cubrir todo el sílabo.
4. Definir primero los huecos claros y los más graves.
5. Cuáles son las mejores opciones para cada hueco, investigando y justificando de manera sencilla.
6. Volver a analizar de forma crítica (dos veces), investigando las fuentes reales; el tiempo estimado no es rígido.
7. Aprobar YouTube como fuente central y registrar en el README las opciones elegidas, que pueden cambiar.

**Resultado:** huecos claros identificados: recomendación, analítica web y redes sociales. La IA revisó `robots.txt` de los medios, notas de muestra, el sitio del ENFEN, los avisos del Senamhi y una búsqueda en YouTube. Se actualizaron `README.md` y `CLAUDE.md` con YouTube como fuente central, avisos del Senamhi, recomendador híbrido, analítica web, red social y reglas por sitio. Las decisiones son del equipo y quedan abiertas.

## 2026-10-23 · Definición de pendientes urgentes (Claude Code, Claude Opus 5.5)
**Propósito:** definir los pendientes más urgentes del README con análisis crítico.

**Prompts (resumen fiel, en orden):**
1. Empezar a definir de una vez, analizando, siendo crítico y reevaluando.
2. Revisar de nuevo: Wikipedia no es una fuente confiable para extraer información.

**Resultado:** se definieron el modelo de engagement (se descarta el clasificador del estado oficial), el agente con herramientas, el estudio de eventos, la estructura del informe por CRISP-ML(Q) con sección de protocolos web, el tipo de canal por enlaces verificables desde sitios oficiales (sin Wikipedia) y los criterios de pasa / no pasa. La IA verificó los enlaces sitio–canal de 8 organizaciones, la cuota oficial de la API de YouTube y el estado archivado de `pytrends`.

## 2026-10-23 · Definiciones de producto, datos y uso de LLM (Claude Code, Claude Opus 5.5)
**Propósito:** definir usuario, semáforo, categorías, despliegue, período, medios, videos, regiones, avisos, actores y uso de LLM.

**Prompts (resumen fiel, en orden):**
1. Continuar con las definiciones de producto y datos, con análisis crítico.

**Resultado:** la IA revisó un comunicado del ENFEN, la lista de avisos del Senamhi, los términos de RPP, el D. Leg. 822 (versión de terceros), la documentación de Streamlit y el `robots.txt` de El Tiempo. Se cambió la unidad regional a macro-región, los avisos del Senamhi pasaron de eventos a contexto, se agregaron reglas de derecho de autor y despliegue, y El Tiempo (Piura) entró como medio regional.

## 2026-10-23 · Términos de uso de medios y organización (Claude Code, Claude Opus 5.5)
**Propósito:** revisar los términos de uso de los medios y definir la organización del grupo.

**Prompts (resumen fiel, en orden):**
1. Continuar con análisis crítico; commit local.
2. "¿Estás totalmente seguro? Analiza de nuevo."
3. ¿Por qué hay preguntas para el profesor?
4. El uso de IA no es problema, no hay anexo ni rúbrica: elegir la opción más adecuada.

**Resultado:** la IA leyó las cláusulas literales de los términos de uso y del D. Leg. 822 y corrigió tres errores de su revisión anterior. Se excluyó Infobae, el cuerpo de las notas solo se procesa en memoria, el dashboard no muestra fragmentos del cuerpo y el trabajo se dividió en dos verticales (Noticias y YouTube) con evidencia de aporte individual.

## 2026-10-23 · Revisión completa del README (Claude Code, Claude Opus 5.5)
**Propósito:** revisar el README completo y corregir las observaciones.

**Prompts (resumen fiel, en orden):**
1. No importa definir quién hace cada cosa; dejar la planificación general clara y analizar todo por si queda alguna observación.
2. Corregir esas observaciones validando, analizando y evaluando como antes.

**Resultado:** se corrigieron 14 observaciones, entre ellas: NLI y contradicciones sintéticas para el índice de discrepancia, evaluación no circular del recomendador y del sentimiento, contradicciones internas (estructura de datos, despliegue, enlace de video), corte el 20-nov, prueba de volumen de noticias, edad del video como control, Trends semanal, enlaces de descripciones de videos y tabla de cobertura del sílabo. La IA verificó el tamaño de los modelos en Hugging Face y la normalización de Google Trends.

## 2026-10-23 · Segunda revisión completa (Claude Code, Claude Opus 5.5)
**Propósito:** volver a revisar el README, solo documentación, dejando escritas las pruebas necesarias.

**Prompt (resumen fiel):** volver a analizar; por ahora solo documentar, y si hacen falta pruebas o validaciones, colocarlas.

**Resultado:** la IA revisó los sitemaps de los 4 medios y encontró que Andina, RPP y La República solo listan los últimos días, así que se documentó cómo recuperar el histórico por medio y la recolección diaria. También se corrigieron el conteo de búsquedas de YouTube (110 en 2 días), la precedencia del semáforo, la regla de agregación del NLI, la exclusión de videos recientes, la comparación de series de Trends y la privacidad de comentarios. Se agregaron pruebas de histórico, control positivo y despliegue.

## 2026-10-24 · Histórico validado, ventana de datos y calendario (Claude Code, Claude Opus 5.5)
**Propósito:** validar si se puede recolectar hacia atrás, definir hasta qué fecha recolectar y elegir entre La República y Exitosa.

**Prompts (resumen fiel, en orden):**
1. Hacer git pull y commit; subir los commits.
2. ¿Con qué continuamos?
3. ¿Solo podemos buscar del presente al futuro?
4. ¿No íbamos a mirar también hacia atrás con un margen acotado?
5. ¿Considerar La República y Exitosa, o sería ruido? Elegir el más adecuado.

**Resultado:** la IA validó el histórico por fuente (Andina completo por número de nota, RPP ~83 % por archivo, La República sin vía, Exitosa completo por sitemaps mensuales). Se excluyó La República, entró Exitosa, se fijó la ventana 1-ene → 20-nov con monitoreo hasta el 27-nov, el congelamiento el 27-nov y un calendario de 5 semanas.

## 2026-10-24 · Recolección diaria (Claude Code, Claude Opus 5.5)
**Propósito:** decidir cómo y dónde correr la recolección diaria de notas nuevas.

**Prompts (resumen fiel, en orden):**
1. ¿Cuál sería el siguiente paso?
2. ¿Hay problema con GitHub Actions? Tengo créditos de estudiante.
3. ¿Cada cuánto correría? ¿Varias veces al día o una al final del día?
4. ¿Podríamos dejar un script y que cualquiera lo ejecute a mano al final del día?
5. ¿Esos archivos se guardarían en GitHub? Así nos daríamos cuenta rápido.
6. Anotar eso primero.

**Resultado:** la IA verificó en la documentación de GitHub que Actions es gratis en repositorios públicos y se cobra al dueño del repositorio. Se decidió un script manual diario (margen máximo de 3 días sin ejecutarlo), que guarda solo direcciones y fechas en `data/urls/` con un archivo por ejecución; GitHub Actions queda como opción posterior.

## 2026-10-24 · Script de recolección diaria (Claude Code, Claude Opus 5.5)
**Propósito:** definir, validar y construir el script de recolección diaria de direcciones de notas.

**Prompts (resumen fiel, en orden):**
1. Definir el script (qué notas, esquema del CSV, fecha y sección por fuente, duplicados, errores, dependencias, resumen, paso a GitHub Actions) validando con peticiones reales; escribirlo solo tras aprobar.
2. Volver a realizar el análisis y validar primero que no haya huecos u observaciones.
3. ¿No puedes validar ahora mismo de alguna manera lo pendiente?
4. Resumir si todo está conforme; asegurarse de que el resto esté validado (sin GitHub Actions ni turnos, que maneja el equipo).
5. Eliminar los archivos de prueba y crear un `.md` con las definiciones.
6. Aprobar; escribir el script, probarlo, actualizar README/CLAUDE.md sin mezclar todo en el README (solo resumen) y organizar los `.md` nuevos; commit local.
7. Subirlo; aclarar qué es una ejecución real frente al modo `--prueba` y si el script recupera días anteriores (sí: lee la ventana completa de cada sitemap).

**Resultado:** la IA hizo ~600 peticiones a las fuentes (1 por segundo) y leyó copias de sitemaps en Wayback Machine. Encontró que `lastmod` es fecha de modificación, que los sitemaps de El Tiempo están congelados (se usa su API REST), que Andina sí tiene `robots.txt`, que el margen de 3 días perdía notas (pasó a 48 h, validado con el día más cargado de 2026), un hueco del 31-may en los mensuales de Exitosa y que el 301 de Andina no confirma que una nota exista. Se escribió `src/recolector/diario.py` (requests + lxml, verificador propio de `robots.txt`, registro de sitemaps y alertas de hueco), se documentó en `docs/recoleccion/` y la primera ejecución guardó 7.485 direcciones.

## 2026-10-24 · Corpus oficial ENFEN y Senamhi (Claude Code, Claude Opus 5.5)
**Propósito:** definir, validar con peticiones reales y construir el corpus oficial (comunicados del ENFEN y avisos del Senamhi en párrafos, con vigencia por fecha y macro-región).

**Prompts (resumen fiel, en orden):**
1. Leer README, CLAUDE.md, docs de recolección y `diario.py`; definir alcance, fuente del texto, campos, párrafos, vigencia, esquema, actualización, errores, criterios de las dos pruebas de viabilidad y ubicación del código, validando con todos los documentos reales; escribir solo tras aprobar.
2. ¿Está todo validado y conforme? Para dejarlo definido de una vez.
3. ¿Seguro que no hay forma de validar lo pendiente? Debe haberla.
4. ¿Se aplicaron medidas de seguridad, respaldos y buenas prácticas? Evaluar las decisiones abiertas e indicar cuáles quedan.
5. Aprobar la definición (incluida la excepción para versionar `data/oficial/`).
6. ¿El análisis del "no pasa" es conforme o falta algo? ¿Cuáles son las opciones? ¿Estás conforme con la evaluación?
7. Verificar los 2 desacuerdos sin explicar; aprobar la opción A (polígono como método principal, prueba declarada como no pasa).

**Resultado:** la IA descargó los 20 comunicados (más 3 de 2025 con slug de extraordinario) y 198 avisos, y validó contra referencias externas: página de descarga, cadena de "próximo comunicado", tablas de probabilidad, segundo extractor de PDF, tabla de avisos, polígonos oficiales del WFS del Senamhi, párrafos diarios, copias de Wayback y el texto consolidado del D. Leg. 822 en WIPO Lex. Encontró que la fecha real es la del PDF (no el `lastmod`), que del 1 al 14-ene rige el N.° 13-2025, que dos slugs de "extraordinario" son comunicados oficiales y que el título del aviso no basta para la macro-región; corrigió sus propias reglas varias veces (notas al pie, magnitud, "costa norte y centro"). Se escribió `src/oficial/` con pruebas en `tests/`, el corpus en `data/oficial/` (19 comunicados, 125 avisos, 834 párrafos) y la documentación en `docs/oficial/`. Prueba del ENFEN: pasa. Prueba del Senamhi: no pasa en 2 de 8 criterios (acuerdo polígono/regla 94,8 % y 94,5 %, umbral 95 %); con árbitros independientes (texto diario y nivel 1 del polígono) se explicaron los 35 desacuerdos y se decidió mantener el polígono, declarándolo.

## 2026-10-24 · Reestructuración del código y buenas prácticas (Claude Code, Claude Opus 5.5)
**Propósito:** ordenar el código antes de que crezca: paquete único, configuración centralizada, sin valores repetidos, manejo de errores, reintentos y respaldos, y cómo montar el proyecto en el README.

**Prompts (resumen fiel, en orden):**
1. ¿Se aplican buenas prácticas (nombres, sintaxis limpia y eficiente, sin comentarios innecesarios, ortografía)? ¿Cómo se estructuran las carpetas? No debe quedar todo suelto ni con valores repetidos: ante un cambio no se deben tocar varias partes.
2. Reestructurar de una vez aplicando todas las observaciones, con buen manejo de errores, respaldos y reintentos; si hay más observaciones, decirlas primero.
3. Cómo montar todo el proyecto debe estar en el README.
4. Verificar que no quede nada huérfano, con buenas prácticas y código legible.

**Resultado:** la IA revisó el código y encontró 18 observaciones más (un host caído podía costar horas de reintentos, errores de red no reintentados, `Retry-After` con fecha ignorado, descargas incompletas no detectadas, un aviso mal formado tumbaba toda la fuente, avance perdido si se cortaba, efecto al importar `diario.py`, valores repetidos en varios archivos, números mágicos, entre otras). Se creó el paquete `radar` (`pyproject.toml`, `src/radar/config.py` como único lugar de valores, `config/*.csv` para regiones y estaciones, `radar.comun` con HTTP, archivos, texto, regiones, geometría y registro), se movieron el recolector y el corpus oficial con `git mv`, se reorganizaron las pruebas por paquete (45, incluidas las de reintentos y fallos simulados sin red) y se adoptaron `ruff format` y `ruff check`. Verificación: el corpus reconstruido es idéntico byte a byte (solo cambia el formato del detalle de `validacion.csv`), y `diario --prueba` y el corpus incremental funcionan con red real. El comando diario pasa a `python -m radar.recoleccion.diario`. En la revisión final (`vulture` y lectura completa) se quitaron valores sin uso (`CORTE`, `CONGELAMIENTO`, `NACIONAL`, `src/.gitkeep`), se unificaron la lectura de `data/urls/` (3 copias), el XML de sitemaps, las URL oficiales, los meses abreviados y los mensajes de error, se renombraron variables cortas y se rehízo el bucle de reintentos sin código inalcanzable; el corpus volvió a salir idéntico.

## 2026-10-24/25 · Pruebas de viabilidad de noticias e histórico de los 4 medios (Claude Code, Claude Opus 5.5)
**Propósito:** definir, validar con peticiones reales y construir las pruebas de viabilidad de noticias (cobertura de RPP, pérdida del filtro por título, volumen, control positivo) y la recuperación del histórico de Andina, RPP, Exitosa y El Tiempo del 1-ene al 24-oct.

**Prompts (resumen fiel, en orden):**
1. Hacer git pull y leer README, CLAUDE.md y los docs de recolección y del corpus oficial; definir primero (vías revalidadas, términos del filtro y cómo medir su pérdida sin títulos guardados, qué se guarda, fechas, duplicados, control negativo, reanudación, errores, criterios, código) con opciones y una recomendación; escribir solo tras aprobar.

**Resultado:** la IA hizo unas 9 mil peticiones de validación y encontró que el archivo de RPP sí tiene paginación (`page-1`…; ~99,6 % frente a 7 copias de Wayback, no ~83 %), que el 301 de Andina trae el slug aun sin nota publicada (la segunda petición solo hace falta para las notas que se leen), que Exitosa tiene 141 números faltantes y está en ISO-8859-1, que El Tiempo entrega el cuerpo por su API, que las etiquetas editoriales no sirven como referencia general y que Andina casi nunca enlaza el PDF del comunicado (sí el informe técnico o cita el número). Al verificar, corrigió su propia definición: la regla "≥ 2 menciones" contaba menciones de pasada, y se cambió por "El Niño en el resumen o el primer párrafo". Se escribió `src/radar/noticias/` (vías por medio, lectura en memoria sin guardar el cuerpo, filtro, rasgos, comunicados citados en 4 niveles, reanudación por medio, pruebas de viabilidad con estimación por estratos y bootstrap), `config/terminos_titulo.csv`, `secciones_excluidas.csv` y `actores.csv`, pruebas con HTML sintético y `docs/noticias/`. Prueba del filtro: **no pasa** (pierde 22,8 %); con las candidatas ampliadas que prevé el README (secciones de noticias de RPP y Exitosa, todo Andina y El Tiempo) pierde 2,7 %. La referencia reconoce 0,867 de las notas que RPP etiqueta El Niño (umbral 0,90): no pasa y se declara. El histórico quedó corriendo (~21 h); volumen, control positivo y la prueba formal de RPP se miden al terminar.

## 2026-10-25 · Asignación de macro-región de notas y videos (Claude Code, Claude Opus 5.5)
**Propósito:** definir, validar con fuentes primarias y peticiones reales, y construir la asignación de macro-región (costa norte, costa centro, Lima, otras, nacional) de las notas y del título y descripción de los videos, sin chocar con el histórico en curso.

**Prompts (resumen fiel, en orden):**
1. Hacer git pull y leer README, CLAUDE.md y las definiciones de noticias y del corpus oficial; definir primero (lista de lugares con ubigeo del INEI y su acceso, nombres ambiguos medidos con datos, normalización, regla de asignación, de dónde sale el texto sin guardar el cuerpo, validación con referencias externas, criterios de pasa / no pasa y ubicación del código) con opciones y una recomendación; no lanzar el histórico ni leer muchas notas; escribir solo tras aprobar.
2. En resumen, ¿lo validaste y verificaste correctamente? ¿Falta validar algo?
3. ¿Qué deberíamos hacer ahora?
4. Si estás totalmente seguro, construirlo, siempre que esté validado.

**Resultado:** la IA encontró que el WFS de la IDE del INEI entrega los ubigeos en CSV sin geometría (25 departamentos, 196 provincias, 1.890 distritos), idénticos a los GeoPackage en RAR del mismo instituto; que el portal de datos abiertos pide iniciar sesión; que las notas de Andina y El Tiempo de 2026 no traen el encabezado "LIMA (ANDINA)"; que la sección de la dirección de RPP, la sección local de El Tiempo y los sitemaps por sección de Andina sirven de referencia sin etiquetado; y que agregar columnas a `notas.csv` con el histórico corriendo desalinearía filas. Con un prototipo sobre las notas ya leídas midió qué nombres excluir ("Santa", "La Unión", "Castilla"), que los distritos medidos duplican el acierto en Lima y que los gentilicios no aportan; al revisar su propia evaluación corrigió que El Tiempo se usaba a la vez para decidir y evaluar, y lo partió en mitades. Se escribió `src/radar/region/` (lugares, asignación, referencias, pasada sobre notas con validación), la columna `litoral` de `config/regiones.csv`, `config/lugares.csv`, la función compartida de expresiones de macro-región en `radar.comun.regiones` (el corpus oficial no cambia: 834 de 834 párrafos iguales), pruebas con textos sintéticos y `docs/region/`. Las 7 pruebas pasan con titular y resumen (costa norte 96 %, costa centro 90 %, sección Lima 65 %, notas nacionales 87 % "nacional"); la pasada con cuerpo y los videos quedan para el preprocesamiento y la vertical de YouTube.

## 2026-10-27/28 · Índice de discrepancia (pilotos) y capa 1 del flujo de NLP: texto limpio (Claude Code, Claude Opus 5.5)
**Propósito:** definir cómo probar el índice de discrepancia (NLI y comparación por datos) sin guiarse solo por el README y, al encontrar que los errores venían de capas previas, ordenar el trabajo en un flujo por capas y construir la primera: el texto limpio del cuerpo.

**Prompts (resumen fiel, en orden):**
1. Analizar qué está hecho y qué falta; seguir con las pruebas pendientes, empezando por la más simple (NLI).
2. Volver a validar y ser crítico con la propuesta para no rehacer luego; ¿hay problemas serios?; evaluar alternativas mejores, no lo simple solo por cumplir.
3. Analizar, descartar y probar empezando por lo más adecuado; ¿esa prueba basta para concluir?; dejar de guiarse por el README si no está bien y definir cómo probar de forma eficiente y segura.
4. Investigar por qué el proceso es lento: detenerlo, medir tiempos, encontrar patrones y concluir; verificar que la corrección funciona.
5. ¿Cómo avanzar: limpieza, ETL o pipeline? No mezclar responsabilidades, para tener trazabilidad de qué parte falla o dónde está el cuello de botella; mejorar velocidad o efectividad sin degradar la calidad.
6. Definir primero, analizar, ser crítico; aprobado, siempre volviendo a revisar; recalcular `notas.csv` más adelante si hace falta para que todo sea coherente con la metodología.
7. Si aparecen errores de otras capas, analizarlos, probarlos y testearlos para elegir la mejor opción.

**Resultado:** la IA validó en su fuente el modelo NLI del README y encontró, con pilotos fuera de la prueba, lo siguiente:
- La prueba sintética del README es demasiado fácil.
- Comparar con "el párrafo más parecido" da falsas alarmas.
- La versión cuantizada cambia las respuestas.
- Con notas reales, el NLI con umbral 0,5 marca el 23-26 % de las frases de Andina que citan el comunicado (umbral de descarte 20 %), así que esa configuración se descarta.

Al revisar sus propias conclusiones, encontró que la mayoría de esos errores, y también los de la comparación por datos, venían de etapas previas:
- texto sucio;
- frases que no afirman nada del Niño actual;
- párrafos oficiales mal elegidos.

Midió además que la lentitud se debía a que `transformers` cargaba el modelo en float16 (de 6 a 18 veces más lento en CPU, con los mismos resultados) y a los modos de ahorro de energía del equipo.

Se acordó un flujo por capas, cada una con su validación, y se construyó la capa 1 en `noticias/nota.py`. Al revisar la estructura real de cada medio evitó un error de su propia propuesta: en Andina el texto viene con `<br>` y quedarse con los `<p>` perdía hasta el 96 %. La validación (`python -m radar.noticias.validar_texto`) se corrió con seis muestras nuevas de 100 notas. En las cinco primeras corrigió dos tipos de errores, sin mover umbrales:
- de la limpieza: "[Lea también", variantes de hora y lugar (que pasó a quitar por su forma y no por patrón), "►";
- del propio instrumento de medición: la palabra "compartir" de la redacción, uniones que ya vienen pegadas desde el medio, comillas de cierre.

La sexta pasa todos los criterios:
- 0 uniones pegadas (antes de 14 a 15 por cada 1.000 palabras);
- 0 restos;
- RPP con su `articleBody` en 25 de 25 notas.

También comprobó que los enlaces quitados son todos recomendados del propio medio y que se recuperan las citas textuales que antes se borraban. Detalle en `docs/noticias/texto.md`.

## 2026-10-28 · Capa 2 del flujo de NLP: corpus oficial limpio (Claude Code, Claude Opus 5.5)
**Propósito:** que cada párrafo oficial sea texto real y diga de qué trata, para las capas que comparan notas con lo oficial.

**Prompts (resumen fiel, en orden):**
1. Si el enfoque está bien, continuar; si no, seguir probando.
2. Sí, continuamos (aprobación de la definición de la capa 2).

**Resultado:** al verificar la capa 1 sobre notas sobre El Niño, la IA encontró que había dejado fuera la bajada de Andina. La corrigió y revisó caso por caso los cambios de "El Niño en el inicio": ninguna nota deja de ser sobre El Niño. Para la capa 2 midió el corpus:
- 4 encabezados de tabla que salían como párrafo;
- 41 párrafos de recomendaciones y seguimiento;
- párrafos de la costa y del Pacífico central sin nada que los distinguiera.

Usó como referencia externa la estructura fija del resumen ejecutivo: 17 comunicados con 6 párrafos en el mismo orden. Con eso, el extractor del PDF reconoce los encabezados de tabla ya unidos y cada párrafo lleva `tipo` y `region_enso`, calculados con reglas sobre el texto. Pasan todos los criterios: 102/102, 34/34, 30/30 y 250/250. La comparación con el corpus anterior destapó que la definición del N.° 13 cambiaba de id; se corrigió, y ahora solo salen los 4 encabezados.

## 2026-10-28 · Revisión de la estrategia y pendientes (Claude Code, Claude Opus 5.5)
**Propósito:** revisar si la estrategia sigue siendo la correcta con lo encontrado, sin guiarse a ciegas por el README, y dejar el repositorio al día para seguir en otro chat.

**Prompts (resumen fiel, en orden):**
1. Sí, procedemos con la capa 3; verifica de nuevo por si acaso; ¿podemos continuar con mayor seguridad?
2. ¿Cómo debemos continuar? ¿Otro enfoque o cambio de estrategia? ¿Seguir validando algún punto? Vamos a buen tiempo: este es el momento.
3. ¿Necesitamos sí o sí la API de YouTube para continuar? El README puede no estar al día con lo que vamos encontrando: no te guíes a ciegas y valida.
4. Sí seguimos con YouTube; la pregunta era si podemos avanzar con otras partes.
5. Actualiza en el código o en algún .md lo que haga falta, súbelo al repositorio y ordena por prioridad lo que sigue, para continuar en otro chat; primero defínelo.

**Resultado:** al volver a verificar la definición de la capa 3, la IA encontró cuatro problemas:
- validaba magnitud y plazo contra datos oficiales sacados con las mismas reglas, lo que es circular;
- la muestra era chica;
- 10 notas ya estaban vistas;
- faltaban el titular y el resumen.

Midió además que las afirmaciones verificables son ~0,7 por nota.

En la estrategia propuso:
- apoyar el índice en reglas por dato y distancia, con el NLI acotado a un solo intento;
- recalcular `notas.csv` y `enlaces.csv` antes de la red de enlaces, en vez de al final.

Al validar qué depende de YouTube según la tabla del sílabo, concluyó que nada de lo que sigue lo necesita para avanzar. Solo depende de él el insumo de ML, si además falla el NLI, y para ese caso propuso una alternativa con Trends. También corrigió su propia afirmación sobre el cupo de la API: son 1-2 días, no semanas.

Se escribieron `docs/nlp/discrepancia.md` (pilotos, decisiones, flujo por capas, capa 3) y `docs/pendientes.md` (prioridades), con avisos en el README y en CLAUDE.md.

## 2026-10-28 · Recálculo de las notas: definición y resumen de El Tiempo (Claude Code, Claude Opus 5.5)
**Propósito:** el punto 1 de `docs/pendientes.md` (regla de magnitud unificada, recálculo reanudable de `notas.csv` y `enlaces.csv`, corrida nocturna), definiendo y validando antes de escribir código.

**Prompts (resumen fiel, en orden):**
1. Haz git pull y lee la documentación. Tarea: el punto 1 de los pendientes, en tres partes. Primero define y analiza con datos reales, con criterios fijados antes y muestras nuevas; los procesos largos deben poder reanudarse si la laptop se suspende o se apaga. No escribas código hasta que se apruebe.
2. ¿Cómo procedemos, luego de haber analizado con criterio?
3. Ejecuta la rutina diaria en segundo plano y sigue con la regla de magnitud, siendo críticos, analizando y validando.
4. Sí, procedemos (corregir primero el resumen en la capa 1).

**Resultado:**
- Copiar la regla del ENFEN a las noticias perdía "intensidad fuerte" (26 de 41 pérdidas en los resúmenes). Se propuso una regla por cercanía; el prototipo da 19/19 en la regresión oficial.
- Al probarla apareció un error de la capa 1: el resumen de El Tiempo traía el titular de otra nota y volvía "sobre El Niño" a 39 notas. Se corrigió en su capa y su validación pasó a la primera (60/60), con un control que muestra que el criterio sí detecta el problema.
- La lista de notas ya vistas se reconstruyó y quedó en `config/notas_vistas.csv`.
- La rutina diaria corrió sin `--publicar`, porque el push solo se hace cuando el usuario lo pide.
5. Sigue (con las frases sintéticas y los criterios de la regla de magnitud).
6. ¿Cuál sería lo adecuado según tu análisis? Sí, realicemos eso y validemos.

**Resultado (continuación):**
- Al revisar su propio análisis, la IA encontró varios problemas:
  - las frases sintéticas salían del diseño;
  - el instrumento compartía listas con la regla;
  - la muestra de validación repetía frases del diseño (el cuerpo contiene el resumen);
  - "El Niño global" contradecía la definición aprobada de la capa 3;
  - el resumen HTML del ENFEN traía las llamadas de nota pegadas ("fuerte2").

  Esto último se corrigió en la capa 2.
- La regla por cercanía se construyó en `oficial.enfen` y la usa `rasgos`. La regresión oficial da 0 diferencias. De las tres muestras nuevas, la 2.ª no pasó (7/35): se diagnosticó caso por caso y se corrigieron la regla y el instrumento sin mover umbrales. La 3.ª pasa (0/28, 0/28, 0/26). Las notas con magnitud sin ver quedaron agotadas.
- También se encontró que `corpus --solo enfen` borra las filas del Senamhi de `validacion.csv` (pendiente).
7. Sí, sigue (con la medición previa al recálculo). ¿Estás seguro de que es la única manera? ¿Cuál es lo más adecuado? Hay que validar y analizar. Sí, apruebo (medir sobre el propio recálculo, con un punto de control).
8. Revísalo tú y me informas. Sí, apruebo (la definición corregida del recálculo).

**Resultado (recálculo):**
- La IA midió sin red el efecto del resumen y de la regla, y propuso medir sobre el propio recálculo, antes de reemplazar los archivos, en lugar de una muestra. Así se mide todo y no se gastan notas sin ver.
- Al revisar su propia definición encontró supuestos falsos:
  - las filas guardadas vienen de dos generaciones de código;
  - la `fecha_modificacion` de Andina no sirve para detectar ediciones;
  - el punto de control no ve todos los cambios.

  También encontró huecos: errores de red sin tope, el candado sin `oficial.corpus`.
- Construyó el recálculo reanudable con `cambios.csv`, el candado entre procesos y la antisuspensión. Las pruebas B1 a B4 y M1a pasan.
- La primera corrida real destapó que M1b pasaba sin datos; se corrigió.
9. Procede a ejecutarlo, ya tengo la laptop cargando. ¿Cómo va el proceso? Se suspendió la laptop un rato, ¿cómo va? ¿Termino de ejecutarse?
10. Procede sin problemas. Revisa primero, analiza, y si está todo conforme procedes. Corregimos.

**Resultado (corrida y revisión antes de aplicar):**
- La fase 2 terminó con los criterios en verde, y sobrevivió a una suspensión de la laptop sin perder notas.
- Antes de aplicar, la IA revisó lo que ningún criterio medía. Encontró que 47 notas ganaban "menciona El Niño" por titulares de otras notas sin rótulo dentro del cuerpo, y midió en una muestra nueva que la fuga afectaba a ~7 % de las notas de Andina. No aplicó.
- Corrigió la capa 1 y validó con tres muestras nuevas. La 1.ª no pasó por la regla: quitaba la continuación de una frase partida en dos bloques. La 2.ª no pasó por el instrumento: titulares editados por el medio. La 3.ª pasa; `validar_texto` también. El recálculo se relanzó completo.
11. Continúa con el proceso, ya prendí la laptop. ¿Cómo va el proceso, cuánto falta? ¿Estás totalmente seguro, para proceder? Entonces procedemos.

**Resultado (aplicación):**
- La segunda corrida reanudó tras el apagado sin repetir notas y pasó los criterios.
- La IA revisó caso por caso los cambios frente a la corrida 1: las 35 notas que no estaban explicadas, releídas, perdían la mención solo por un titular ajeno.
- Ante la pregunta de si estaba seguro, separó lo comprobado de lo no comprobado (las ~1.175 pérdidas de mención revisadas por muestra, la corrección de cada magnitud) y señaló que `--aplicar` se puede deshacer. También ordenó la rutina para no perder notas nuevas: la recolección antes de aplicar y el histórico después.
- Después de aplicar, la baja en la coincidencia de RPP con su `articleBody` destapó un error de la capa 1 (bloque de recomendados sin cerrar). Quedó como pendiente, sin código hasta su aprobación.
12. Sí, defínelo. Apruebo (instrumento, regla y recálculo completo de RPP). Puedes validar.

**Resultado (recomendados sin cerrar en RPP):**
- La IA separó dos causas en la baja frente al `articleBody`: una del instrumento (ítems de lista pegados) y otra de la regla (HTML de RPP que no cierra el bloque "Te recomendamos").
- Midió la prevalencia en una muestra de diseño. Su propio detector falló primero; lo diagnosticó y lo corrigió antes de proponer nada.
- Construyó el instrumento y la regla y los validó con criterios fijados antes. C3 no pasó en dos muestras; en las dos, caso por caso, fallaba el instrumento (rótulos cortos, una sola palabra), nunca la regla. La 3.ª muestra pasa.
- Al preparar la segunda pasada del recálculo encontró que la generación de cada fila ya no es fiable; lo definió antes de tocar el código.
13. Apruebo (la adaptación del recálculo). ¿Me indicas cuánto demorará aprox.?

**Resultado:** la IA adaptó el recálculo (piso de generación, paso "rescate" y control M1b). Antes de lanzar 5,5 h comprobó con 6 notas reales que el cuerpo sin rescate reproduce el `sha1` guardado.

    Al terminar, también evitó que el segundo `--aplicar` se quedara sin respaldo: renombró los archivos de la primera pasada, que ocupaban `*.anterior.csv`.

**Resultado:**
- La IA revisó el informe: M1b a M5 pasan, y ninguna nota cambia magnitudes, "sobre El Niño", "menciona" ni comunicados.
- Explicó los 3.061 cambios de cuerpo por grupo: recuadros de seguir al medio, la caja del Rotafono, la barra lateral y 10 rescates. También separó 9 ediciones reales de RPP.
- Aplicó y verificó fila por fila. `region.notas` no cambia, y en `viabilidad` la cobertura de RPP sube de 99,77 % a 99,94 %.
- Dejó como pendiente aparte las 13 notas que el rescate no cubre.
14. Procede a avanzar: ¿qué debemos mejorar, validar o actualizar? Pruebas de viabilidad. Vuélvelo a evaluar. Apruebo.

**Resultado:**
- La IA corrió la rutina diaria y ordenó los pendientes por lo que decide el alcance.
- Definió las pruebas de pysentimiento y de memoria para Streamlit. Al volver a evaluarlas encontró fallas de diseño:
  - un acuerdo trivial con "others";
  - pares de NLI demasiado fáciles;
  - comparar solo etiquetas.

  También encontró que nunca se había medido la precisión de "sobre El Niño" (386 notas lo son solo por el cuerpo), y la puso primero.
- **Precisión de "sobre El Niño": pasa.** Hay 5 falsos positivos en 100, todos de la regla: "La Niña" como nombre propio, "Código del Niño" y un apodo.
- **pysentimiento: no pasa.** 97 % de los titulares salen sin emoción, así que se usa el respaldo: solo polaridad.
- **Memoria:**
  - torch no cabe;
  - el NLI cuantizado cambia la respuesta en 25 % de los pares; comprobó que el instrumento estaba bien comparando el ONNX en float32 con torch;
  - el NLI en float32 pasa de 2,7 GB, así que queda solo offline;
  - el embedding sí cabe.
- Al releer CLAUDE.md señaló dos choques con lo aprobado: el criterio de E1 usaba etiquetas puestas por la IA (prohibido: "cero etiquetado manual") y los scripts eran provisionales. Corrigió la documentación y dejó como pendiente pasar los scripts a `src/`.
15. Realiza la rutina diaria y súbela; actualiza los pendientes. Sí, defínela (la regla de "sobre El Niño"). Vuelve a evaluarlo. Apruebo.

**Resultado:**
- La IA midió los patrones en todas las notas y propuso cinco cambios.
- Al volver a evaluarlos descartó dos, porque el inicio del cuerpo une las líneas y habrían borrado menciones legítimas. También evitó que "(FEN)" contara dos veces.
- Reemplazó la muestra de 400 notas, que no tenía potencia, por el recálculo completo como medición.
- Construyó la regla, las pruebas sintéticas y el paso de causa "menciones" del recálculo. Lo comprobó con 7 notas reales ya vistas: 7 de 7.
- Antes de lanzar encontró que los directorios de la primera pasada habrían hecho que el recálculo no releyera nada, y que `--aplicar` se quedaría sin respaldo. Renombró ambos.
16. ¿Hay que volver a correr el proceso largo? Ya sería la 5.ª vez. Deja claro lo pendiente y qué corregir antes de ejecutarlo.

**Resultado:** se decidió no recalcular después de cada corrección. Las correcciones se acumulan en el código y se hace un solo recálculo final antes del corte, con un ensayo corto antes. La lista de lo que hay que revisar antes de lanzarlo quedó en `docs/pendientes.md`.

## 2026-11-01 · Viabilidad de modelos en `src/`, red de enlaces y TF-IDF (Claude Code, Claude Opus 5.5)
1. Avanza con lo que no depende de YouTube, Trends ni del recálculo final: `src/radar/nlp/` con las pruebas de viabilidad de modelos, la red de enlaces y citas, y el preprocesamiento y TF-IDF. Para cada tarea, defínela y analízala con datos reales, sé crítico y fija los criterios antes de escribir código. Valida con muestras nuevas, sin reusar notas vistas. No lances el recálculo; si algo lo requiere, corrígelo en el código y anótalo.

**Resultado:** la IA analizó los datos y propuso las tres definiciones. Al hacerlo encontró:
- 315 notas de Andina en inglés que el filtro por slug dejaba pasar (10 sobre El Niño);
- que el script provisional de pysentimiento no se podía reproducir;
- que el AUC del TF-IDF saldría inflado con los términos que definen "sobre El Niño";
- que el criterio de menciones fallaba para Indeci y PCM.
2. Preguntas sobre la elección de los modelos de embeddings, el universo de alternativas y las restricciones de la app; revisión del sílabo sobre el despliegue. "Si existe una opción gratuita que sea mejor, podríamos elegirla; si no, como no pide que sea publicada, que se pueda correr en local estaría genial."

**Resultado:** la IA reconoció que había tomado el README como el universo de opciones y que presentó como hechos supuestos sin respaldo, como el tiempo por consulta. Revisó el sílabo, que no exige publicar la app, y la documentación oficial de Hugging Face Spaces: CPU Basic tiene 16 GB, pero crear Spaces con cómputo requiere PRO en las cuentas personales. Se decidió que la app principal corre en local y que la versión pública es opcional, en Community Cloud y liviana. Se actualizaron el README y los pendientes.
3. Sí, haz el mapa / procede, primero definimos y dejamos el plan bien armado / Sí, apruebo (el plan corregido de A a F).

**Resultado:**
- La IA escribió el mapa de alternativas (papeles, restricciones y tipos de enfoque con su veredicto; candidatos de varias fuentes). Al revisarlo encontró que el filtro con titulares no predice el resultado en cuerpos, que la comparación con todo el ENFEN no es la que hará el semáforo (que usa lo vigente) y que la duración de B no estaba medida. Corrigió el plan.
- Con la prueba A (`radar.nlp.candidatos tiempo`) encontró que la lentitud de granite y Qwen3 venía de cargarlos en bfloat16. Pasan los 10 candidatos. Dejó escrito el código de B, que falta probar.
4. Procedemos a definir / vuelve a evaluarlo / sí, apruebo (C, reranker).

**Resultado:** la IA midió que con el filtro de fecha B4 deja de medir al modelo y que el semáforo casi no necesita filtrar párrafos. En la reevaluación corrigió dos errores suyos: e5-small no es mejor en texto corto y mDeBERTa no debía entrar. Quedó una definición nueva para texto corto, con pasos y criterios fijados antes de correr, y el módulo `radar.nlp.reranker`.
5. Sí, defínela / sí, apruebo (D, híbrido).

**Resultado:** la IA midió que la fusión de rangos del plan no sirve para comparar notas (26 valores distintos en 2.777) y propuso una regla única de fusión de puntajes, con criterios fijados antes de medirla. Escribió `radar.nlp.hibrido`. El híbrido no se adopta: E4 de 0,866 frente al mínimo de 0,880.
6. Sí, defínela / sí, apruebo (E, recall@k).

**Resultado:** la IA midió que el filtro de fecha deja pocos párrafos y que recall@5 discrimina poco, y propuso decidir con acierto@3 frente al azar, con preguntas por plantilla sacadas de los metadatos. Escribió `radar.nlp.recuperador`. Ningún candidato reemplaza a minilm: los que mejoran el promedio retroceden en las preguntas sobre el ENFEN.
7. Sí, defínelo / vuelve a evaluarlo / sí, apruebo (punto 4, tópicos y polaridad).

**Resultado:** la IA propuso y corrigió la definición: BERTopic con KMeans para tener el mismo k que LDA, c_v con la nota como ventana, estabilidad entre semillas y kappa frente a un zero-shot en notas nuevas. Escribió `radar.nlp.topicos`. Se elige BERTopic k=12; LDA es inestable; la polaridad no pasa P2 (κ 0,12) y queda descriptiva.
8. Sí, mejor de una vez, siempre validando y analizando… / sí, apruebo (x2) (capa 3).

**Resultado:** la IA revisó la definición con notas ya vistas, propuso 6 ajustes y escribió `radar.nlp.afirmaciones`. Validó con 150 notas nuevas, diagnosticó los desacuerdos, propuso 4 arreglos y los volvió a validar con otras 99. Estado y magnitud pasan; el plazo no (0,882).
9. Evaluemos de manera crítica… / sí, defínela / sí, apruebo (temporalidad, plazo v2).

**Resultado:** la IA revisó las alternativas (HeidelTime, dateparser, NLI, LLM local) y propuso reglas propias con segmentos de inicio y fin y estaciones del hemisferio sur. Fijó T1 a T5 antes de escribir `radar.nlp.temporalidad`. Pasan T1 a T4 (32/32, 113/114, 29/31, 19/19). Son controles de desarrollo sobre los comunicados; T5, con notas nuevas, queda para el 18-nov.
10. Hay que analizar e investigar mejor, desde otra perspectiva / sí, reescríbela / sí, apruebo (capa 5).

**Resultado:** la IA revisó estudios que comparan noticias de ciencia con su fuente (Sumner, Wright y Augenstein, Pei y Jurgens) y exploró titulares ya vistos. Encontró que "muy fuerte" es la escala del Pacífico central, que muchas supuestas contradicciones se adelantaban a lo oficial y que algunas notas afirman con más certeza que el ENFEN. Reescribió la capa 5 en cuatro dimensiones, con C1 a C6 fijados antes, y escribió `radar.nlp.discrepancia`. En la ronda a, con 200 notas nuevas, pasan C1, C2, C3 y C5; C4 no pasa (42/45) por tres fallos de fechas ya diagnosticados.
11. Procedemos a corregir los 3 / sí, sigue / sí, apruebo (capa 5, rondas b y c).

**Resultado:** la IA corrigió en la capa 3 el año de los rangos, las fechas económicas y las agencias internacionales, y en la capa 5 los hechos pasados y el diseño de C4. La ronda b no pasó (C3 17/22, C4 27/29): 4 de los 5 fallos de C3 eran discrepancias reales de terceros. Con 4 cambios más (estado como actividad, años futuros, C4 con años explícitos y C3 sin terceros), la ronda c pasa, aunque C3 solo tiene 4 casos.
12. Define el punto 5.1 de los pendientes (la distancia dentro del semáforo): mapea los enfoques, fija los criterios antes del código, valida con muestras nuevas sin T5 y sin etiquetado manual / sí, apruebo / positivo limpio por regla y resúmenes del ENFEN en S4.

**Resultado:** la IA midió, sin pedir páginas, que el imán de minilm es el párrafo genérico de recomendación y no la definición, y que el umbral verde era inestable. Encontró la causa: citas falsas de "Comunicado N.°" en el control positivo de E3. Propuso párrafos vigentes sin definiciones, umbrales por tipo de texto, el verde desde el negativo, lo lejano en gris y las reglas primero. Escribió `radar.nlp.semaforo` y pasan S1 a S6 (con 400 y 100 negativos nuevos y 93 resúmenes oficiales). S2 en cuerpo y S4 son pruebas fáciles, y se declara.
13. Sí, define el NLI / sí, apruebo (punto 5.2).

**Resultado:** la IA midió que el 87 % de las frases sobre El Niño no traen datos y que solo el 7 % pronostica un impacto. Propuso aplicar el NLI solo a esas frases y comparar con las de impactos y pronóstico del comunicado vigente. Fijó N1 a N5 y el cierre si N2 tiene menos de 20 casos que cambian en julio a octubre, y escribió `radar.nlp.nli`. Hubo 0 casos, y 6 con la región opcional, así que el NLI se cerró sin cargar el modelo ni pedir páginas.
14. Sí, apruebo (estudio de eventos).

**Resultado:** la IA midió, sin red, que los comunicados salen cada ~14 días y que el volumen se multiplicó por 30. Propuso una regresión de Poisson diaria con tendencia y placebo por permutación, con V1 a V4 fijados antes, y escribió `radar.analitica.eventos`. La ronda a no pasa V2 (0,745) ni V3 (p = 0,11): las fechas falsas caen cerca de las reales y la nula contiene el efecto.
15. ¿Con qué seguimos? / Analiza críticamente / ¿Es la única forma? / ¿Cuál es la más adecuada? / Procedemos (recomendador).

**Resultado:** la IA midió las etiquetas débiles: solo sirven los enlaces que cada medio pone entre sus notas, y casi todos tienen el origen ya visto. Encontró una muestra nueva (notas sin ver que mencionan El Niño) fuera de la reserva de T5. Propuso reglas para lo oficial y una cascada sin parámetros ajustados para las notas, con una puerta y R1 a R4 fijados antes, y escribió `radar.analitica.recomendador`. Pasan la puerta (AUC 0,745), R2 a R4 y K2. R1 no pasa: los editores enlazan sobre todo lo más reciente.
16. ¿Con qué podemos continuar, que solo dependa de nosotros? / Procede (agente) / Reglas + embeddings.

**Resultado:** la IA escribió el agente sin LLM (`radar.agente`): cuatro herramientas con respuestas por plantilla y citas literales, y un enrutador con reglas genéricas y similitud de minilm con la descripción de cada herramienta. Congeló 46 redacciones nuevas y los criterios A1 a A5 antes de escribirlo. Pasan A2 a A5, pero A1 no (0,83): las preguntas de recomendación se confunden con búsqueda. Propuso una ronda b con redacciones nuevas en lugar de ajustar las reglas a las congeladas.
17. ¿Cómo podemos llegar a 0,90? Evaluemos mejor / Sí, apruebo (agente, ronda c).

**Resultado:** la IA mostró que con 41 redacciones el IC 95 % de A1 iba de 0,77 a 0,97 y que cada ronda había gastado su prueba. Escribió y congeló primero una prueba de 150 redacciones por tipos y después un conjunto de desarrollo de 120. En desarrollo comparó descripciones, kNN y un clasificador de intención. Eligió regresión logística sobre TF-IDF y e5 (0,91 en validación cruzada) y la congeló antes de la prueba. La prueba pasa: A1 0,944 (IC 0,904 a 0,984) y A2 a A6 pasan. Declaró que la IA escribió todos los conjuntos.
18. Empezamos con el punto 1: YouTube y Trends. Mapea los enfoques y propón la definición del módulo (términos, tramos, campos, cupo, seudonimización, borrado a los 30 días y prueba de viabilidad), con criterios fijados antes de escribir código, y espera mi aprobación.

**Resultado:** la IA mapeó los enfoques (búsqueda por tramos como base; canales semilla como respaldo; descartó los videos relacionados, que la API quitó, el scraping, `pytrends` y los servicios de pago) y revisó la página oficial de cuotas. Propuso términos, tramos, campos, seudonimización con HMAC, borrado a los 30 días y los criterios Y1 a Y5 y G1 y G2, todo fijado antes de escribir código ([youtube/definicion.md](youtube/definicion.md)).
19. Cada programa debe ir rápido sin saturar, mostrar su avance y no perder lo hecho si se corta; si no, páralo y hazlo bien.

**Resultado:** la IA detuvo `radar.youtube.canales` y lo rehízo en paralelo por sitio (8 a la vez, de a uno por sitio), con avance y tiempo restante (`radar.comun.avance`) y guardado por sitio terminado. También hizo que `descarga` guarde por lote y por página, con avance. Y4 pasa (0,991), con la reserva de que casi ningún canal enlaza su sitio en la descripción.
20. Sí, defínela (las emociones de los comentarios) / Vuelve a revisar, no me parece tan simple: hay varios casos que considerar / Una nueva revisión, porque es una parte importante / Sí, apruebo.

**Resultado:** la IA escribió la definición en `docs/youtube/emociones.md`, con los criterios M0 a M3 fijados antes de correr ningún modelo sobre los comentarios. La revisó dos veces más. La 2.ª agregó los casos de datos: respuestas, idioma, spam, autores, largos, emojis y religiosos. La 3.ª agregó el orden de descarga, la fuga hacia el modelo de engagement, la paradoja de κ, el zero-shot en dos pasos y el dueño del canal. Con la aprobación escribió `radar.youtube.emociones`. La primera corrida truncó 27 tramos por un conteo de tokens que se quedaba corto; lo corrigió y volvió a medir. Resultado preliminar: pasan M0 y M1 (42,8 %), no pasan M2 (κ 0,16) ni M3 (κ 0,11), así que las emociones quedan solo descriptivas.
21. Sí, el recálculo / Sí, ambas cosas / ¿Estás seguro de que no debemos validar algo antes? Son 10 h y no podemos desperdiciarlas / Sí, ajusta y lanza.

**Resultado:** la IA declaró las 17 notas de RPP incompletas (ninguna es sobre El Niño) y confirmó que no quedaban archivos de recálculos anteriores. Corrió la fase 1 como ensayo; le agregó avance porque no lo mostraba. Pasan M1b, M2, M3, V1 (9/9) y V2 (8/8). Ante la pregunta del usuario revisó los riesgos y encontró que M4 contaba como fallas las notas de Andina en inglés, excluidas a propósito: la corrida de 10 h no se habría podido aplicar. Con aprobación, M4 las cuenta aparte, con el mismo umbral. Probó la fase 2 con 450 notas y la lanzó.
22. Dime qué faltaría hacer a día de hoy, ¿es buena calidad lo que vamos haciendo? / Empecemos entonces / (T5) Apruebo.

**Resultado:** la IA listó lo pendiente y dio una evaluación crítica: buen método, pero la app y el modelo de engagement sin empezar a 8 días del congelamiento. Reconoció dos pasos del recálculo que había saltado. Corrió la rutina diaria, `viabilidad resultados` y el TF-IDF, leyendo antes las 552 notas que le faltaban. Corrió la ronda b del recomendador: R1 no pasa. T5 no tenía definición: la IA la propuso, el usuario la aprobó y la IA la agregó como ronda `t5` de la capa 5, con pruebas. C3 pasa con 68 casos y las 2 rojas resultaron errores de extracción.
23. ¿Por qué esperar al 21-nov? ¿Qué es Streamlit, hay que usarlo? / ¿No deberíamos usar algo adecuado para el frontend? / Hay que analizar si corresponde, no por estar hecho en Python / Revisa nuevamente: lo visual es muy importante / ¿Aplicamos buenas prácticas de UX/UI sin saturar? / Analiza con cuidado, ponte en el lugar de quien lo usa / Apruebo.

**Resultado:** la IA revisó el sílabo, que no exige Streamlit, y recomendó FastAPI + React por lo que necesita el producto: el ciudadano en el celular, una explicación a medida del semáforo, el registro de uso desde el navegador y los enlaces para compartir. Escribió tres borradores de `docs/app/definicion.md`. En el tercero midió que el 94 % de los titulares reales no trae datos comparables y que el 66 % saldría verde solo por parecido. Por eso, cuando no hay datos, la app no muestra un semáforo sino la "cercanía". También definió las personas, 12 decisiones justificadas y los criterios P1 a P12 y U1 a U6.
24. Sí, expórtala (segunda exportación de Google Trends).

**Resultado:** la IA exportó con Claude in Chrome los 4 departamentos y la consulta nacional por región. G1 pasa y G2 no pasa por Tumbes (0,790). Aplicó la regla fijada antes, que promedia las dos exportaciones, solo en el departamento que no llega; lo agregó al cargador con una prueba.
25. Modelo de engagement: primero mapear, analizar y definir (mapa de enfoques, recomendación según los datos, definición con criterios fijados antes); esperar la aprobación antes de construir.

**Resultado:** la IA midió el corte sin entrenar nada: la tasa no depende de la antigüedad en el entrenamiento (ρ −0,01), los días de entrenamiento (83 a 323) y de prueba (14 a 82) no se solapan, 13 % de tasas en 0 y un canal con el 12 % de los videos. Propuso en `docs/modelos/engagement.md` el logit de la tasa suavizada (beta-binomial), Ridge y gradient boosting frente a la mediana y a un modelo solo con controles, y los criterios M1 a M5. Sin emociones y con el último video del 8-nov.
26. Sí, constrúyelo (modelo de engagement).

**Resultado:** la IA escribió `radar.modelos` (`rasgos` y `engagement`) con 12 pruebas sintéticas, y calculó las variables de 1.609 videos. Entrenó con validación cruzada por canal: eligió el boosting (MAE 0,495). Evaluó la prueba una vez: pasan M1 (0,43), M2 (+12,6 %) y M3 (+0,063, por poco), y solo la cercanía es estable (M5). Corrigió la escala del rival Poisson en el detalle y lo repitió con `--repetir`, sin cambios en M1 a M4.
27. Continuamos entonces (red social con YouTube).

**Resultado:** la IA midió los comentarios del corte. El 9 % de los autores comenta en 2 canales o más; el 53 % de las aristas son un solo autor; hay solo 10 medios en la red; el backbone estricto deja 18 canales. Propuso en `docs/redes/youtube.md` la proyección con el coseno de Salton, Louvain contra un nulo bipartito (curveball) y los criterios R1 a R7, con el cruce con medios para la pregunta 6.
28. Sí, procede (red social), con buenas prácticas, manejo de errores, optimización, calidad, buen rendimiento, sin comentarios innecesarios, estructura adecuada y nombres claros.

**Resultado:** la IA escribió `radar.redes.audiencias`, con funciones puras (bipartita dispersa, curveball, Salton, Louvain, backbone y asortatividad), y `radar.redes.youtube` (línea de comandos, 1.000 nulos en paralelo con avance), más 9 pruebas sintéticas. Pasan R1, R2 (por poco) y R4; no pasa R3. La pregunta 6 no es concluyente y R7 es débil (0,076; p 0,007).
29. ¿Te pareció adecuado lo realizado con el modelo? ¿Hay algo más que validar? / Sí, defínela.

**Resultado:** la IA señaló que la cercanía nunca se validó en videos. Propuso en `docs/modelos/engagement.md` (sección 8) un control positivo (51 videos de 6 canales oficiales) y uno negativo (407 descartados sin El Niño ni términos del filtro, la misma definición que en las notas), con los criterios V1 a V5 (AUC ≥ 0,80, sin cruce de percentiles). Sin código.
30. Sí, constrúyela (validación de la cercanía en videos).

**Resultado:** la IA escribió `radar.modelos.cercania` (etapa `cercania`), con el AUC por canal y 3 pruebas sintéticas. Pasan V1 (AUC 0,882; IC 0,782–0,932) y V2 (0,472 frente a 0,460, por poco). Frente al negativo difícil da 0,779. La separación es de tema, como en las notas.
31. Sí, defínela (analítica web).

**Resultado:** la IA escribió `docs/analitica/web.md` con el mapa de enfoques de las cuatro partes (engagement frente a la cercanía, Trends por departamento, indicadores de los medios y registro de uso) y los criterios W1 a W11, fijados antes de ver resultados. La respuesta a la pregunta 5 se apoya en la correlación dentro del canal, y solo es "sí" o "no" si el IC por canal excluye 0 y el signo se repite en los dos períodos. No construyó nada: espera la aprobación.
32. Sí, constrúyela (analítica web).

**Resultado:** la IA escribió `radar.analitica.indicadores` (funciones puras) y `radar.analitica.web` (línea de comandos), con 18 pruebas sintéticas. Corrió una vez y pasan W1, W6 y W9 a W11.
- La pregunta 5 da "sí": ρ parcial dentro del canal −0,168, con IC −0,260 a −0,099 y el mismo signo en los dos períodos y por fecha. Lo que contradice al ENFEN no tiene más engagement.
- En W8, ningún departamento muestra relación medible entre Trends y las notas.
   - Al correr solo `uso`, la IA encontró que guardar una etapa borraba las filas de validación de las otras. Lo corrigió (reemplazo por criterio, con su prueba) y repitió todo con `--repetir`: dio los mismos valores. Lo declaró en la sección 9.
33. (Sesión aparte, encargada por la anterior) Construye la interfaz de la app según `docs/app/definicion.md`: React con Vite y TypeScript, Visx, CSS propio en claro y oscuro y Vitest; primero el plan y luego construir solo con orden explícita.

**Resultado:** la IA propuso el plan por pasos (sistema visual, Verificar y Preguntar, Panorama A a F y Metodología, registro de uso) y la forma de medir P6 a P12 y U1 a U6. No construyó nada: esperó la orden.
34. Sí, construye

**Resultado:** la IA construyó `web/` (Verificar, Preguntar, Panorama A a F y Metodología) y agregó a la API la pantalla F (`/api/panorama/youtube`), las tarjetas de YouTube, engagement, red, analítica web e interfaz en Metodología, y las cabeceras y topes. Los textos salen de `radar.app.textos` a `web/src/generado/textos.json`. Midió con Edge y axe (`npm run medir`) y con `python -m radar.app.validar_interfaz`: pasan los 12 criterios (P6 0 violaciones, P7 6/6, P8 24/24 cifras contra los CSV, U4 73,9 KB, U5 100 %). En la revisión corrigió el detalle que se veía abierto, el encabezado descentrado, la etiqueta del 0 en F, la coma decimal y las viñetas de los PDF. Al medir, el registro de uso recibió eventos de prueba; los sacó del registro real, y la medición ahora los intercepta. Hallazgos que quedan fuera (no se tocaron): un titular de fútbol sale con cercanía Alta por los umbrales del NLP, y el agente muestra la fecha en formato ISO.
35. (Sesión aparte, encargada por la anterior) Haz el punto 4 de `docs/pendientes.md`: `radar.nlp.discrepancia calcular`, `radar.analitica.eventos validar --ronda c` con los comunicados N.° 19 y 20, `radar.youtube.emociones` con los comentarios del corte, y vuelve a medir la app (`radar.app.validar`, `npm run medir`, `radar.app.validar_interfaz`); actualiza las cifras que cambien y comprueba que no exista el registro de uso.

**Resultado:** la IA corrió los tres cálculos sin cambiar código.
- Discrepancia: 2.785 notas (58 nuevas; una ya no está publicada). Siguen 74 % sin datos y 43 rojas. La nota no publicada quedó repetida al reintentarse, y se quitó la fila.
- Eventos con 20 comunicados: V1 ya pasa (0,059), V2 no (0,584), así que sigue descriptivo. La proporción sobre El Niño sube en 14 de 20 (mediana +51 %).
- Emociones del corte: 15.204 comentarios. Pasan M0 y M1 (41,6 %), no M2 (κ 0,232) ni M3 (κ 0,099); siguen solo descriptivas.
- App: pasan P1 a P12 y U1 a U6, y no se creó `eventos.csv`. El Panorama muestra "14 de 20" (+52 %).

Se actualizaron `docs/analitica/eventos.md`, `docs/nlp/discrepancia.md`, `docs/youtube/emociones.md`, la sección 8 de `docs/app/definicion.md`, `docs/pendientes.md` y el README.
36. sí, arregla los dos bugs

**Resultado:** la IA corrigió dos detalles de `radar.nlp.discrepancia`. `calcular` deja una sola fila por nota en `discrepancia-todas-notas.csv`, porque la nota con error que se reintentaba quedaba repetida. Y `main` (también `validar`) sale con código 2 cuando otro proceso tiene el candado, en vez de caerse con un `TypeError`. Agregó dos pruebas sintéticas. Volvió a correr `calcular` con los datos reales y quedaron 2.785 filas.
37. Sí, define A

**Resultado:** la IA escribió la sección 9 de `docs/app/definicion.md`: el problema medido, las alternativas, qué se construye, las muestras y los criterios F1 a F7, más P13 como criterio permanente. En desarrollo encontró tres fallas de `DOMINIO` ("femenino", "calidad" y "Costa Rica"). Registró las 300 notas del diagnóstico en `config/notas_vistas.csv`. No construyó nada: espera la aprobación.
38. Sí, usa todas

**Resultado:** la IA cambió las muestras de la sección 9 de `docs/app/definicion.md`. F1 usa las 50.623 notas de otros temas y F2 usa 2.635 notas sobre El Niño (las 58 del corte se informan aparte). También declaró la excepción a la regla de `notas_vistas.csv`: esas notas no sirvieron para elegir las palabras del filtro. Sigue sin construir.
39. Sí, construye (filtro de tema)

**Resultado:** la IA creó `radar.comun.dominio` (el agente lo importa), el filtro de tema y el resultado `fuera_de_tema` en Verificar y en la interfaz, y `radar.app.validar_tema`, con sus pruebas. Midió una vez con toda la fuente:
- F1 en corto pasa: 0,72 %, antes 5,8 %;
- F1 en cuerpo no pasa: 3 %, antes 6 %;
- pasan F2 (9,03 %) a F6. Preguntar no cambia ninguna decisión.
40. Sí, defínela

**Resultado:** la IA escribió la sección 10 de `docs/app/definicion.md`:
- etiquetas automáticas (tema, otros temas y una zona gris que no entra al entrenamiento);
- vector e5 y regresión logística, con la partición por tiempo (enero a agosto para entrenar, septiembre al corte para probar);
- cuerpos de 400 y 400 notas, y los criterios C1 a C8.
No construyó nada: espera la aprobación.
41. Sí, construye (clasificador de tema)

**Resultado:** la IA escribió `radar.app.tema` y sus pruebas, y entrenó con enero a agosto (C = 10, τ 0,83).
42. si arreglala (la fecha ISO del agente)

**Resultado:** la IA encontró que Preguntar mostraba el texto interno del agente: fechas AAAA-MM-DD, ids (`enfen-2026-20`, `costa_norte`, `prevencion`) y jerga ("Semáforo: rojo (reglas)"). Ahora la respuesta se arma con las plantillas `PREGUNTAR` de `radar.app.textos` (U2 y U3), con fechas largas y nombres legibles, y el agente no cambia. Agregó una prueba, y P1 a P12 y U1 a U6 volvieron a pasar.
43. te refieres que tenemos un servicio muy lento? eso de que parte es / debemos mejroar con urgencia eso, debemos optimizarlo, es pesimo tanto tiempo, o sea yo levanto el proyecto y va a estar ahi demorando tanto?

**Resultado:** la IA midió el arranque por pasos: la mayor parte se iba en volver a calcular los vectores de los párrafos oficiales en cada arranque. Los guardó en disco (`embeddings.con_cache`, en `data/processed/cache/`), y se recalculan solos si cambian el corpus oficial o el modelo. El arranque bajó de 63,2 s a 15,6 s, y P1 a P5 y las pruebas siguen pasando. Lo que queda es importar las librerías.
44. hay que mejorar mucho, esta terrible para un usuario, muestrame los diseños para ver cual debemos utilizar. Tu mismo revisalo

**Resultado:** la IA listó seis problemas para un ciudadano y armó maquetas de tres opciones: ordenar lo que existe, primero tu zona y un chat. Las revisó en el navegador y recomendó «primero tu zona».
45. esta mucho mejor, procedemos con ello. Mantengamos las buenas practicas

**Resultado:** la IA escribió la sección 11 de `docs/app/definicion.md` (criterios I1 a I5) y construyó el rediseño:
- tokens nuevos y letras servidas desde la app;
- el inicio «Hoy», con la zona y el mensaje en dos columnas;
- la regla con las dos marcas, el glosario, el resultado sin datos con título nuevo, y la cercanía como una línea chica.
Todos los textos siguen en `radar.app.textos`. La escala de magnitud siguió en el azul ya validado, porque el naranja significa «difieren» en el Panorama. Midió los criterios: pasan I1 a I5, P1 a P12 y U1 a U6 (sección 11.4). En la medición corrigió el área de toque de dos enlaces y el ancho de los gráficos del Panorama en el celular.
46. Tarea: el pendiente «etiquetas de clima y mar que no dependan de El Niño» para el filtro de tema de Verificar (avisos del Senamhi como positivos, con una prueba nueva). Primero un mapa de todos los enfoques, luego la definición con criterios y umbrales fijados antes de medir, para aprobarla; no construir sin orden explícita. Validar con muestras nuevas.

**Resultado:** la IA midió qué datos quedan sin usar (20.286 notas de la zona gris; 2.402 con etiquetas editoriales de clima o mar del propio medio) y escribió la sección 12 de `docs/app/definicion.md`: mapa de 11 enfoques, elige las etiquetas editoriales como positivos (los avisos del Senamhi solo si mejoran la validación cruzada, por su registro oficial), muestras nuevas de clima y mar y criterios K1 a K9. Sin aprobar ni construir.
47. Construye

**Resultado:** la IA construyó `radar.app.tema_clima`, con las listas de etiquetas en `radar.comun.dominio` y sus pruebas. Fijó la muestra antes de entrenar, leyó 272 cuerpos en memoria, entrenó (los textos oficiales no entraron por la CV) y midió una sola vez. Pasan K1, K3 y K10, y no pasan K2 y K4 a K7: rechaza mejor los otros temas, pero pierde clima y mar. La app sigue con el filtro de palabras, y se declara su «Alta» nueva en otros temas con palabras de clima (2,35 % en corto y 5,5 % en cuerpo). Resultados en la sección 12.6.
48. veo que aun tenemos problemas, debemos resolverlo, hay que ver ideas innovadoras y creativas

**Resultado:** la IA mapeó enfoques en tres ejes (cómo se decide, con qué modelo y con qué se prueba) y midió en desarrollo, con validación cruzada de enero a agosto, el veto, el rescate, los vecinos más cercanos y el anclaje a la evidencia. Escribió la sección 13 de `docs/app/definicion.md`: el clasificador ya no reemplaza al filtro de palabras, solo veta lo claramente ajeno (en desarrollo, la mitad de negativos difíciles con 1 punto menos de positivos), y se prueba con notas de octubre a diciembre de 2025 de Andina y RPP, que nadie vio. Criterios V1 a V10. Sin aprobar ni construir.
49. Construye

**Resultado:** la IA construyó la sección 13: `PALABRAS_GENERICAS` en `radar.comun.dominio`, el anclaje en `radar.app.servicio` (apagado por defecto), `radar.noticias.externa` y `radar.app.validar_anclaje`, con sus pruebas. Probó 20 notas por medio, leyó la prueba externa de 2025 y la midió una sola vez. Pasan V1, V4, V6 y V9; V3 no pasa (1,02 % en corto y 4 % en cuerpo), y V2 y V5 quedan informativos por tener menos de 100 notas. La regla no se activa; resultados en la sección 13.7.
50. como va el proceso, si se ha parado vuelvelo a ejecutar desde donde se quedo / necesito que sea mas rapido / si empiezan a responder puros 500 reduces un poco las peticiones

**Resultado:** la IA vio que la lectura no se había parado y que la limitaba la espera de cada respuesta, no la pausa. Hizo seguro entre hilos a `radar.comun.http.Cliente` y pidió hasta `config.HILOS_POR_HOST` (4) a la vez por medio, con el mismo 1 s entre inicios; si el servidor falla, baja a la mitad y vuelve a subir tras 200 respuestas sin error. Relanzó la lectura desde donde quedó: Andina pasó de 15 a 30 números por minuto y terminó a las 22:18, sin errores.
51. lo de bajar el arranque de la app seria bueno que hagamos eso

**Resultado:** la IA midió el arranque (15,6 s, de los que unos 12 s son importar `sentence-transformers`, `transformers` y `torch`) y probó MiniLM en ONNX float32 con `tokenizers`: mismos vectores (coseno mínimo 0,99999992) y 1,2 s de carga. Escribió la sección 14 de `docs/app/definicion.md`: mapa de 8 enfoques, motor ONNX en la API, criterios con arranque ≤ 8 s y resultados idénticos. Sin aprobar ni construir.
52. apruebalo y dale

**Resultado:** la IA marcó la sección 14 como aprobada y la construyó: bajó el ONNX de e5 (470 MB), creó `radar.nlp.motor` y conectó el semáforo de la app y el agente. Antes de medir encontró que el `tokenizer.json` de e5 no da los mismos tokens que `transformers`, y guardó el tokenizador que arma `transformers` (`python -m radar.nlp.motor preparar`). Midió una sola vez con `radar.app.validar_arranque` y las pruebas de la app: pasan H1 a H7. El arranque baja de 17,7 a 5,5 s y la primera pregunta de 4,1 a 1,9 s, con los mismos resultados. Borró 2 visitas del registro de uso que dejó el panel de vista previa.
53. (captura de los avisos del Senamhi) esta parte deberia ser simetrica, me refiero a nivel naranja, nivel rojo, etc, deben tener todos tamaño fijo e igual. Ademas ese badge y todos los que tienen ese badge lateral de color es lo mas generico que realiza siempre la IA asi que quita eso y ponle algo adecuado e intuitivo. Tambien el cuadro para colocar el texto tiene en su esquina derecha abajo para agrandar o dismniuir, eso quitalo. Tambien no se porque toda esa parte tiene un fondo blanco, si el fondo general es de un color distinto, hay que mejorar muchas cosas del diseño

**Resultado:** la IA revisó todas las pantallas en 375 y 1.280 px y midió 11 problemas: etiquetas de 132 y 104 px, franjas laterales también en las citas, cuadro estirable, columna blanca (`#f8fafa`) sobre la página gris (`#e8edef`), interlineado estirado por los botones del glosario (55 px), títulos de avisos en 4 líneas en el celular, entre otros. Mostró tres opciones para el nivel y escribió la sección 15 de `docs/app/definicion.md`: escala de los 4 niveles del Senamhi, sin franjas laterales, un solo fondo y criterios D1 a D8. Sin aprobar ni construir.
54. procede

**Resultado:** la IA construyó la sección 15 con la opción A:
- la escala de 4 tramos del Senamhi, de 132 px, debajo del título en el celular;
- sin franjas laterales, con comillas en las citas y sin el chip oscuro;
- el cuadro sin manija;
- un solo fondo, sin sombras en las tarjetas;
- el enlace del comunicado sin estirar la línea;
- los filtros igualados.

Con el validador de la paleta encontró tres cosas, y las declaró:
- los gráficos del Panorama se quedan sobre el panel blanco, porque el tramo claro de la magnitud no llega a 2:1 sobre el fondo;
- el naranja del Senamhi pasa a `#ec7d22`, para separarse del amarillo;
- el tramo vacío lleva solo el contorno.

Pasan D1 a D7 (`web/medir/diseno.mjs`). La IA dijo que también pasaba D8, y era incorrecto: ver el punto siguiente y la sección 15.6.
55. Sí, corrige eso

**Resultado:** la IA corrigió esos errores y uno más que encontró en las 20 capturas (el cuadro de Preguntar, transparente en el celular). Devolvió el naranja a su valor, quitó 2 filas de la medición del registro de uso y registró P9 como no pasa (sección 15.6). D1 a D7 y el resto de las pruebas pasan sobre el código final.
