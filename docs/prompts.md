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
