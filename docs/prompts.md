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

**Resultado:** la IA hizo ~600 peticiones a las fuentes (1 por segundo) y leyó copias de sitemaps en Wayback Machine. Encontró que `lastmod` es fecha de modificación, que los sitemaps de El Tiempo están congelados (se usa su API REST), que Andina sí tiene `robots.txt`, que el margen de 3 días perdía notas (pasó a 48 h, validado con el día más cargado de 2026), un hueco del 31-may en los mensuales de Exitosa y que el 301 de Andina no confirma que una nota exista. Se escribió `src/recolector/diario.py` (requests + lxml, verificador propio de `robots.txt`, registro de sitemaps y alertas de hueco), se documentó en `docs/recoleccion/` y la primera ejecución guardó 7.485 direcciones.
