# Registro de prompts

Registro de la colaboración con IA generativa. Anotar fecha, propósito y prompt.

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
1. Hacer commit y push; listar todo lo que aún falta definir en el README.
2. Empezar a definir de una vez, analizando, siendo crítico y reevaluando.
3. Revisar de nuevo: Wikipedia no es una fuente confiable para extraer información.
4. Aprobar las definiciones y escribirlas sin hacer push.

**Resultado:** se definieron el modelo de engagement (se descarta el clasificador del estado oficial), el agente con herramientas, el estudio de eventos, la estructura del informe por CRISP-ML(Q) con sección de protocolos web, el tipo de canal por enlaces verificables desde sitios oficiales (sin Wikipedia) y los criterios de pasa / no pasa. La IA verificó los enlaces sitio–canal de 8 organizaciones, la cuota oficial de la API de YouTube y el estado archivado de `pytrends`.

## 2026-10-23 · Definiciones de producto, datos y uso de LLM (Claude Code, Claude Opus 5.5)
**Propósito:** definir usuario, semáforo, categorías, despliegue, período, medios, videos, regiones, avisos, actores y uso de LLM.

**Prompts (resumen fiel, en orden):**
1. Continuar con las definiciones de producto y datos, con análisis crítico.
2. Hacer commit local mientras tanto y continuar.

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
4. ¿Estás seguro? Validar e indicar hasta qué fecha considerar; la presentación es el martes 1-dic y ese día no se desarrolla.
5. ¿No íbamos a mirar también hacia atrás con un margen acotado?
6. ¿Considerar La República y Exitosa, o sería ruido? Elegir el más adecuado.

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
3. ¿Estás seguro? ¿No hay algo más que innovar o mejorar?
4. ¿No puedes validar ahora mismo de alguna manera lo pendiente?
5. Resumir si todo está conforme; asegurarse de que el resto esté validado (sin GitHub Actions ni turnos, que maneja el equipo).
6. Eliminar los archivos de prueba y crear un `.md` con las definiciones.
7. Aprobar; escribir el script, probarlo, actualizar README/CLAUDE.md sin mezclar todo en el README (solo resumen) y organizar los `.md` nuevos; commit local.
8. Subirlo; aclarar qué es una ejecución real frente al modo `--prueba` y si el script recupera días anteriores (sí: lee la ventana completa de cada sitemap).
9. ¿Todo está subido y bien documentado?

**Resultado:** la IA hizo ~600 peticiones a las fuentes (1 por segundo) y leyó copias de sitemaps en Wayback Machine. Encontró que `lastmod` es fecha de modificación, que los sitemaps de El Tiempo están congelados (se usa su API REST), que Andina sí tiene `robots.txt`, que el margen de 3 días perdía notas (pasó a 48 h, validado con el día más cargado de 2026), un hueco del 31-may en los mensuales de Exitosa y que el 301 de Andina no confirma que una nota exista. Se escribió `src/recolector/diario.py` (requests + lxml, verificador propio de `robots.txt`, registro de sitemaps y alertas de hueco), se documentó en `docs/recoleccion/` y la primera ejecución guardó 7.485 direcciones.

## 2026-10-24 · Corpus oficial ENFEN y Senamhi (Claude Code, Claude Opus 5.5)
**Propósito:** definir, validar con peticiones reales y construir el corpus oficial (comunicados del ENFEN y avisos del Senamhi en párrafos, con vigencia por fecha y macro-región).

**Prompts (resumen fiel, en orden):**
1. Leer README, CLAUDE.md, docs de recolección y `diario.py`; definir alcance, fuente del texto, campos, párrafos, vigencia, esquema, actualización, errores, criterios de las dos pruebas de viabilidad y ubicación del código, validando con todos los documentos reales; escribir solo tras aprobar.
2. ¿Está todo validado y conforme? Para dejarlo definido de una vez.
3. ¿Seguro que no hay forma de validar lo pendiente? Debe haberla.
4. En resumen, ¿está todo conforme o falta algo?
5. ¿Se aplicaron medidas de seguridad, respaldos y buenas prácticas? Evaluar las decisiones abiertas e indicar cuáles quedan.
6. Aprobar la definición (incluida la excepción para versionar `data/oficial/`).
7. ¿Cómo va?
8. ¿El análisis del "no pasa" es conforme o falta algo? ¿Cuáles son las opciones? ¿Estás conforme con la evaluación?
9. Verificar los 2 desacuerdos sin explicar; aprobar la opción A (polígono como método principal, prueba declarada como no pasa).

**Resultado:** la IA descargó los 20 comunicados (más 3 de 2025 con slug de extraordinario) y 198 avisos, y validó contra referencias externas: página de descarga, cadena de "próximo comunicado", tablas de probabilidad, segundo extractor de PDF, tabla de avisos, polígonos oficiales del WFS del Senamhi, párrafos diarios, copias de Wayback y el texto consolidado del D. Leg. 822 en WIPO Lex. Encontró que la fecha real es la del PDF (no el `lastmod`), que del 1 al 14-ene rige el N.° 13-2025, que dos slugs de "extraordinario" son comunicados oficiales y que el título del aviso no basta para la macro-región; corrigió sus propias reglas varias veces (notas al pie, magnitud, "costa norte y centro"). Se escribió `src/oficial/` con pruebas en `tests/`, el corpus en `data/oficial/` (19 comunicados, 125 avisos, 834 párrafos) y la documentación en `docs/oficial/`. Prueba del ENFEN: pasa. Prueba del Senamhi: no pasa en 2 de 8 criterios (acuerdo polígono/regla 94,8 % y 94,5 %, umbral 95 %); con árbitros independientes (texto diario y nivel 1 del polígono) se explicaron los 35 desacuerdos y se decidió mantener el polígono, declarándolo.

## 2026-10-24 · Reestructuración del código y buenas prácticas (Claude Code, Claude Opus 5.5)
**Propósito:** ordenar el código antes de que crezca: paquete único, configuración centralizada, sin valores repetidos, manejo de errores, reintentos y respaldos, y cómo montar el proyecto en el README.

**Prompts (resumen fiel, en orden):**
1. ¿Se aplican buenas prácticas (nombres, sintaxis limpia y eficiente, sin comentarios innecesarios, ortografía)? ¿Cómo se estructuran las carpetas? No debe quedar todo suelto ni con valores repetidos: ante un cambio no se deben tocar varias partes.
2. Reestructurar de una vez aplicando todas las observaciones, con buen manejo de errores, respaldos y reintentos; si hay más observaciones, decirlas primero.
3. Cómo montar todo el proyecto debe estar en el README.
4. Aprobar, siempre aplicando las buenas prácticas indicadas.
5. Verificar que no quede nada huérfano, con buenas prácticas y código legible.

**Resultado:** la IA revisó el código y encontró 18 observaciones más (un host caído podía costar horas de reintentos, errores de red no reintentados, `Retry-After` con fecha ignorado, descargas incompletas no detectadas, un aviso mal formado tumbaba toda la fuente, avance perdido si se cortaba, efecto al importar `diario.py`, valores repetidos en varios archivos, números mágicos, entre otras). Se creó el paquete `radar` (`pyproject.toml`, `src/radar/config.py` como único lugar de valores, `config/*.csv` para regiones y estaciones, `radar.comun` con HTTP, archivos, texto, regiones, geometría y registro), se movieron el recolector y el corpus oficial con `git mv`, se reorganizaron las pruebas por paquete (45, incluidas las de reintentos y fallos simulados sin red) y se adoptaron `ruff format` y `ruff check`. Verificación: el corpus reconstruido es idéntico byte a byte (solo cambia el formato del detalle de `validacion.csv`), y `diario --prueba` y el corpus incremental funcionan con red real. El comando diario pasa a `python -m radar.recoleccion.diario`. En la revisión final (`vulture` y lectura completa) se quitaron valores sin uso (`CORTE`, `CONGELAMIENTO`, `NACIONAL`, `src/.gitkeep`), se unificaron la lectura de `data/urls/` (3 copias), el XML de sitemaps, las URL oficiales, los meses abreviados y los mensajes de error, se renombraron variables cortas y se rehízo el bucle de reintentos sin código inalcanzable; el corpus volvió a salir idéntico.

## 2026-10-24/25 · Pruebas de viabilidad de noticias e histórico de los 4 medios (Claude Code, Claude Opus 5.5)
**Propósito:** definir, validar con peticiones reales y construir las pruebas de viabilidad de noticias (cobertura de RPP, pérdida del filtro por título, volumen, control positivo) y la recuperación del histórico de Andina, RPP, Exitosa y El Tiempo del 1-ene al 24-oct.

**Prompts (resumen fiel, en orden):**
1. Hacer git pull y leer README, CLAUDE.md y los docs de recolección y del corpus oficial; definir primero (vías revalidadas, términos del filtro y cómo medir su pérdida sin títulos guardados, qué se guarda, fechas, duplicados, control negativo, reanudación, errores, criterios, código) con opciones y una recomendación; escribir solo tras aprobar.
2. ¿Qué pasó? Te quedaste 30 min (si va a demorar no hay problema).
3. Verifica.
4. Aprobado.
5. Continúa; ¿en qué estado lo dejaste?

**Resultado:** la IA hizo unas 9 mil peticiones de validación y encontró que el archivo de RPP sí tiene paginación (`page-1`…; ~99,6 % frente a 7 copias de Wayback, no ~83 %), que el 301 de Andina trae el slug aun sin nota publicada (la segunda petición solo hace falta para las notas que se leen), que Exitosa tiene 141 números faltantes y está en ISO-8859-1, que El Tiempo entrega el cuerpo por su API, que las etiquetas editoriales no sirven como referencia general y que Andina casi nunca enlaza el PDF del comunicado (sí el informe técnico o cita el número). Al verificar, corrigió su propia definición: la regla "≥ 2 menciones" contaba menciones de pasada, y se cambió por "El Niño en el resumen o el primer párrafo". Se escribió `src/radar/noticias/` (vías por medio, lectura en memoria sin guardar el cuerpo, filtro, rasgos, comunicados citados en 4 niveles, reanudación por medio, pruebas de viabilidad con estimación por estratos y bootstrap), `config/terminos_titulo.csv`, `secciones_excluidas.csv` y `actores.csv`, pruebas con HTML sintético y `docs/noticias/`. Prueba del filtro: **no pasa** (pierde 22,8 %); con las candidatas ampliadas que prevé el README (secciones de noticias de RPP y Exitosa, todo Andina y El Tiempo) pierde 2,7 %. La referencia reconoce 0,867 de las notas que RPP etiqueta El Niño (umbral 0,90): no pasa y se declara. El histórico quedó corriendo (~21 h); volumen, control positivo y la prueba formal de RPP se miden al terminar.
