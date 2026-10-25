# Validación del histórico de noticias (24 y 25-oct-2026)

Peticiones reales con el user-agent del proyecto (1 por segundo por host). Respalda [definicion.md](definicion.md) y corrige supuestos del README. Los resultados de cada prueba quedan también en `data/processed/noticias/validacion.csv`.

## Vías (24-oct)
- **Andina.** `noticia.aspx?id=N` responde 301 con el slug también para notas no publicadas (1060000, 1058500 `noticia-xxxxxxxxxx`); la segunda petición a esa dirección da 302 a `/agencia/inicio`. Por eso basta un 301 por número y la segunda petición solo para las notas que se leen. Primer número de 2026 ≈ 1.057.710 (1.057.702 es del 31-dic, 1.057.718 del 1-ene). Los números no son estrictamente crecientes en fecha (el 1093716 es del 1-oct y el 1093836 del 30-sep).
- **Andina en inglés.** La página dice `lang="es"` y no hay marca de idioma en el JSON-LD. La regla de palabras funcionales del slug reconoce 25 de 25 notas de `sitemap-en-ultimo.xml` y marca 2 de 759 notas en español (títulos en inglés: "the-legend-of-zelda…").
- **Andina re-fecha.** La 1056807 (dic-2025) tiene `datePublished` 2026-10-23 en la página y en el sitemap.
- **RPP.** El archivo `/archivo/<fecha>` muestra 30 notas y un botón que pide `/archivo/<fecha>/page-N` (JSON con `html` y `nextPage`), **empezando en `page-1`** (empezar en `page-2` se salta 10 notas: así salía el ~83 % anterior). `robots.txt` permite `/archivo/2026-…` y `page-N`; prohíbe `/tema*`. Un día de 2026 cuesta entre 4 y 15 peticiones (mediana 11).
- **Exitosa.** Los mensuales de dic-2025 a oct-2026 no tienen repetidos y se continúan; en 2026 faltan 141 números (71 sueltos, 6 grupos de 2-3 y el hueco del 31-may, 176791-176844). De 40 faltantes al azar, 18 dan 301 hacia una nota y 22 dan 404. Las páginas están en ISO-8859-1 (decodificarlas como UTF-8 rompe las tildes).
- **El Tiempo.** 4.568 notas del 1-ene al 24-oct (334-515 por mes), 46 páginas de la API. `date_gmt` coincide con el `datePublished` de la página. El `content` de la API trae el cuerpo y sus enlaces (gob.pe, senamhi.gob.pe).

## Lectura del cuerpo (24-oct)
- RPP pone el cuerpo dentro de un `<figure>`; `/capital/` usa otra plantilla (se toma el `articleBody`); videos y fotogalerías no tienen texto (15 de 300 notas de la muestra).
- El cuerpo extraído de RPP coincide con su `articleBody` (99,6 % de las palabras).
- El resumen de RPP y Exitosa es editorial: solo ~57 % de sus palabras están en el cuerpo. Por eso el criterio de calidad pide ≥ 40 %, no la coincidencia completa.
- Las etiquetas editoriales no sirven como referencia general: RPP las pone por entidad ("Senamhi", "Ayacucho") y solo marca El Niño cuando es central; las `keywords` de Exitosa en febrero son el titular reescrito; Andina mezcla etiquetas con palabras del título; El Tiempo casi no etiqueta.

## Control positivo: cómo enlaza Andina (24-oct)
Notas de Andina sobre 8 comunicados: enlaza el PDF del comunicado en mayo (N.° 09, `…/download/comunicado-oficial-enfen-n-09-2026/?wpdmdl=2053`); el informe técnico en enero (en `cdn.www.gob.pe`), febrero, marzo y junio; nada en julio, septiembre y octubre. Varias citan el número ("comunicado oficial Enfen 16-2026", "Comunicado Oficial N° 09-2026") o la fecha del próximo comunicado. De ahí los niveles `numero`, `proximo` e `informe` (definicion.md).

## Prueba: filtro por título (paso 1, 24-oct) — **NO PASA**; con las candidatas ampliadas, pasa
Recolección diaria (`data/urls/2026-10-24_joseph.csv`, temporada alta): se leyeron todas las notas que pasan el filtro y muestras del resto. Referencia: `nino_en_inicio` (El Niño en el resumen o en las primeras 60 palabras, sin mirar el titular).

| Medio | Pasan el filtro (con El Niño en su inicio) | Muestras del resto (con El Niño / leídas de total) | Pérdida con solo el título |
|-------|------------------|-------------------|-----------|
| Andina | 34 de 70 | 8/400 de 686 | 28,8 % (IC95 13-43 %) |
| RPP | 53 de 99 | secciones 3/300 de 1.073; excluidas 0/138 de 949 | 15,8 % (0-31 %) |
| Exitosa | 113 de 286 | secciones 3/300 de 2.520; excluidas 1/150 de 1.159 | 22,6 % (6-38 %) |
| El Tiempo | 17 de 31 | 8/106 de 106 | 32,0 % (16-48 %) |
| **Total** | | | **22,8 % (IC95 13-32 %) > 20 % → no pasa** |

- Lo que se pierde no es ruido: facultades del Congreso para El Niño, limpieza del río Piura, cuencas ciegas, suspensión perfecta de labores.
- **Remedio del README (más candidatas), decidido con la regla fijada antes:** RPP y Exitosa descargan todas las secciones de noticias; El Tiempo todo; Andina perdía 28,8 % > 20 %, así que también todo (`config.CANDIDATAS`). **Pérdida con esas candidatas: 2,7 % (IC95 0-9 %) → pasa.**
- **Sensibilidad a la referencia.** Con "alguna mención en cualquier parte" la pérdida con solo el título sube a 54,9 %, y con "titular o inicio" es 20,8 %; con las candidatas ampliadas, 1,1 % y 2,4 %. La conclusión no depende de la regla.
- **La referencia frente a las etiquetas de RPP: NO PASA (0,867 < 0,90).** Reconoce 39 de 45 notas que RPP etiqueta El Niño (se excluyó una etiqueta "Instituto Nacional de Salud del Niño"). Las 6 que no reconoce son notas de lluvias en Piura y Lima que RPP agrupa bajo "Fenómeno El Niño" aunque su inicio solo habla de lluvias: la referencia es más estrecha que el criterio editorial. No cambia la decisión: esas notas tienen "lluvias" en el título y entran por el filtro; con cualquier referencia las candidatas ampliadas pierden ≤ 3 %. Se declara como limitación.
- Sesgo declarado: es octubre, en plena alerta. La pérdida de enero a octubre se mide con la prueba "Filtro por título (histórico)" al terminar el histórico.

## Prueba: cobertura del archivo de RPP (25-oct) — **PASA**
`python -m radar.noticias.viabilidad rpp`, que vuelve a leer el archivo de los días de cada referencia (la lista guarda una fila por nota, así que una nota que llegó antes por la recolección diaria no queda marcada como vista en el archivo; la primera corrida dio 0 % por eso):

| Referencia | En el archivo (±1 día de su `datePublished`) | Páginas "live" (aparte) |
|------------|---------------------------------------------|-------------------------|
| 7 copias de 2026 de `/sitemap/news` en Wayback | **1.123 de 1.128 (99,56 %)** | 38, ninguna en el archivo |
| Sitemap de noticias de la recolección diaria (21-24 oct) | **192 de 193 (99,48 %)** | 4 |

Todas las secciones están por encima del 95 % salvo las de pocas notas (apuestas deportivas 3/5, campañas 5/6). Con la fecha del sitemap en vez del `datePublished` salía 93 %: RPP vuelve a publicar notas (la de déficit fiscal figura el 22 y el 24-ene; su `datePublished` es el 26-ene). Wayback responde a veces 503: una copia que falla se salta y se avisa.

## Histórico (en curso desde el 24-oct 23:16)
- El Tiempo: 4.568 de 4.568 notas leídas.
- Exitosa: 20.965 notas listadas; lectura en curso.
- RPP: archivo recorrido hasta fines de agosto en la primera noche (~30 mil notas listadas).
- Andina: el descubrimiento por número va por el 1.060.300 de 1.097.224; luego se leen ~37 mil notas (~10 h).
- Entre las 00:22 y las 04:33 del 25-oct el equipo perdió la conexión (DNS) y se suspendió; lo que falló se reintenta en la siguiente ejecución. Hay que impedir que el equipo se suspenda durante la corrida.

Pendiente al terminar el histórico: volumen, control positivo, calidad, pérdida histórica y control negativo (`python -m radar.noticias.viabilidad resultados`), y la prueba formal de RPP.
