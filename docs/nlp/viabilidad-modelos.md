# Viabilidad de los modelos: emociones y despliegue (31-oct-2026)

Dos pruebas del README ("Pruebas de viabilidad"), con los criterios fijados y aprobados antes de correr. El README los dejaba cualitativos ("emociones coherentes", "la app arranca"), así que se concretaron sin cambiar su intención. Ninguna usa notas ya vistas: las muestras quedan en `config/notas_vistas.csv`.

## A. pysentimiento sobre titulares
**Instrumento.** pysentimiento 0.7.3 (última versión, marzo de 2024) funciona con transformers 5.21 y Python 3.13. Sus modelos (`robertuito-emotion-analysis`, `robertuito-sentiment-analysis`) están entrenados con tuits y sus fichas no declaran licencia: sirven para uso académico offline, que es lo que prevé el README.

**Diseño.** Con 20 titulares al azar, casi todos serían "others" y la revisión no vería ninguna emoción. Por eso:
- **E2** (automático): proporción de "others" en 100 titulares sobre El Niño no vistos, 25 por medio (semilla `pysentimiento-e2-31oct`).
- **Revisión cualitativa del README**, sin cifra de exactitud: 20 titulares nuevos, 10 a los que el modelo asigna una emoción y 10 "others" (semilla `pysentimiento-e1-31oct`).

**Corrección de diseño.** La propuesta aprobada convertía esa revisión en un criterio numérico: coincidencia con etiquetas puestas a ciegas por la IA, que pasaba con ≥ 7 de 10. Eso es etiquetado manual usado como referencia, y CLAUDE.md lo prohíbe ("cero etiquetado manual"). No se reporta como métrica. La decisión se apoya en E2 y en la revisión cualitativa, que es lo que pide el README ("revisión cualitativa con ejemplos; sin cifra de exactitud").

**Resultado: NO PASA.**

| Medida | Valor |
|---|---|
| E2: "others" en 100 titulares | 97 (Andina 25/25, RPP 23/25, Exitosa 24/25, El Tiempo 25/25) |
| Titulares con emoción en todo lo no visto | 21 de 1.133 (1,9 %) |
| Probabilidad máxima de los 10 con emoción | 0,38-0,63 en 8 de 10 |
| Polaridad en los 100 de E2 | NEU 67, NEG 31, POS 2 |

Revisión cualitativa:
- **El modelo casi no ve emociones en titulares informativos.** "886 mil personas están en riesgo muy alto", "Unicef: cerca de 3 millones de menores estarían expuestos" o "Crecida de ríos pone en riesgo puentes" salen "others" con probabilidad 0,79-0,97. Es un cambio de dominio, de tuits a titulares formales.
- **Cuando asigna una emoción, casi siempre duda,** y elige entre miedo y tristeza para titulares casi iguales (dos inundaciones en Tumbes y en Ayabaca).
- **Hay errores claros:** "Indeci moviliza más de 200 toneladas de ayuda humanitaria" sale alegría (0,49).
- Aunque las emociones que asigna fueran correctas, cubren ~2 % de los titulares. No sirven para describir temas y emociones por macro-región y mes (pregunta 3 del README).

**Decisión (la que prevé el README).** Para las notas solo se usa la polaridad, que sí discrimina (31 % NEG). Al aplicarla al cuerpo hay que partirlo, porque robertuito lee como máximo 128 tokens: se define cuando se construya. Las emociones de los comentarios de YouTube, más parecidos a los tuits del entrenamiento, se prueban aparte cuando haya datos de YouTube. Esta prueba no las descarta.

## B. Memoria para Streamlit Community Cloud
**Límite** (documentación oficial, valores de febrero de 2024 que "pueden cambiar sin aviso"): de 690 MB a 2,7 GB de memoria. El máximo no está garantizado.

**Criterios fijados antes:**
- **D1:** el pico de memoria de un proceso que importa streamlit, carga el embedding y el NLI, carga los 865 párrafos oficiales y hace una inferencia de cada uno es **≤ 2,0 GB** (25 % de margen).
- **D2**, para ONNX cuantizado:
  - en 300 pares de párrafos del ENFEN de comunicados distintos (semilla `b-d2-31oct`; no usa notas), la etiqueta del NLI es igual a la de float32 en **≥ 99 %** y |Δp| ≤ 0,05 en **≥ 99 %**;
  - el coseno de los embeddings frente a float32 es **≥ 0,99** en los 264 párrafos del ENFEN.

**Resultado** (peak working set en Windows; el contenedor Linux puede diferir):

| Configuración | Pico | Estable | D1 | D2 |
|---|---|---|---|---|
| MiniLM + NLI, torch float32 | 2,37 GB | 2,35 GB | no | — |
| e5-small + NLI, torch float32 | 2,43 GB | 2,41 GB | no | — |
| MiniLM + NLI, ONNX cuantizado | 1,42 GB | 1,21 GB | sí | **no**: NLI 75 % de etiquetas iguales, |Δp| mediana 0,14; MiniLM coseno mín. 0,974 |
| e5-small + NLI, ONNX cuantizado | 1,48 GB | 1,27 GB | sí | **no** por el NLI; e5 coseno mín. 0,9946 (pasa) |
| MiniLM ONNX float32 + NLI ONNX float32 (adicional) | 2,99 GB | 2,30 GB | no | (es float32) |
| e5 cuantizado + NLI ONNX float32 (adicional) | 2,73 GB | 2,04 GB | no | — |
| Solo MiniLM, ONNX float32 (adicional) | 1,31 GB | 0,96 GB | sí | (es float32) |
| Solo e5-small, ONNX cuantizado (adicional) | 0,78 GB | 0,70 GB | sí | pasa |

**Instrumento comprobado.** El ONNX en float32 del NLI reproduce a torch (60 pares: etiqueta igual 1,000, |Δp| máx. 0,0000), y el de MiniLM también (coseno 1,0000). La pérdida de D2 viene de la cuantización, no del script. La primera corrida de ONNX falló porque el script no pasaba `token_type_ids`: era el instrumento, se corrigió y se volvió a medir todo.

Las filas "adicional" salieron del diagnóstico, no de la definición previa. Usan el mismo umbral y no cambian ningún criterio.

**Decisión (la que prevé el README).** El NLI no cabe en la app sin cambiar sus resultados: en float32 pasa de 2,7 GB, y cuantizado da otra respuesta en 1 de cada 4 pares. Queda **solo offline**, y para textos nuevos la app usa la distancia y la regla de magnitud. Esto coincide con [discrepancia.md](discrepancia.md), que ya acotaba el NLI a un solo intento. El embedding sí cabe, con cualquiera de los dos candidatos: e5-small cuantizado (0,78 GB, equivalente a float32) o MiniLM en ONNX float32 (1,31 GB). MiniLM cuantizado no sirve.

**Falta.** La prueba que decide en el README es el despliegue real en Streamlit Cloud. Necesita la cuenta del usuario y el repositorio en GitHub.

## Cómo se corre
```
python -m radar.nlp.viabilidad emociones   # A (pip install -e ".[nlp]")
python -m radar.nlp.viabilidad memoria     # B, D1: un proceso por configuración
python -m radar.nlp.viabilidad d2          # B, D2 y el control del instrumento
```
Los resultados van a `data/processed/nlp/validacion.csv`. Los modelos se leen solo de la caché de Hugging Face (`HF_HUB_OFFLINE`), y sus nombres están en `config.py`. Pruebas sintéticas: `tests/nlp/test_viabilidad.py`.

**Reproducibilidad de A.** El 31-oct se corrió con scripts provisionales, que sorteaban entre las notas no vistas. Con la misma semilla, hoy elegirían otras notas, porque las del 31-oct ya están vistas y "sobre El Niño" cambió con el recálculo. El módulo usa las notas que la semilla ya guardó en `config/notas_vistas.csv` y solo sortea si la semilla es nueva. A no se volvió a correr: repetirlo sería reusar notas vistas, y una semilla nueva gastaría 100 de las notas sin ver. La revisión cualitativa muestra el titular con la emoción del modelo, sin el archivo oculto de la propuesta original, porque la comparación a ciegas se descartó.

**Comprobación del paso a `src/` (1-nov).** Criterio fijado antes: D2 igual con 4 decimales y memoria a ±5 % de lo medido el 31-oct. **Pasa.**
- D2: NLI 0,7500 de etiquetas iguales, |Δp| mediana 0,1373; coseno mínimo de MiniLM 0,9738 y de e5 0,9946; control del instrumento 1,0000. El |Δp| ≤ 0,05 se da en 10,3 % de los pares.
- Memoria: las 8 configuraciones quedan entre +1,1 % y +4,6 % del 31-oct (la mayor diferencia es e5 cuantizado solo: 0,816 frente a 0,78 GB), con las mismas decisiones.
