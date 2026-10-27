# Validación del histórico de noticias (24 al 27-oct-2026)

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

## Histórico (24 al 27-oct) — completo
Corrió del 24-oct 23:16 al 27-oct 09:28 en varias ejecuciones (se reanuda sola). Las pausas fueron por el equipo: una caída de conexión (25-oct, 00:22-04:33), suspensiones y un apagado (25-oct 23:37); el 26-oct Andina respondió 502 entre las 15:52 y las 16:00, y esas notas se leyeron en la ejecución siguiente.

| Medio | Listadas | Candidatas | Leídas | Sin nota | Errores que quedan |
|-------|---------:|-----------:|-------:|---------:|-------------------:|
| Andina | 39.647 | 37.396 | 36.194 | 1.202 (1.064 no publicadas, 138 sin JSON-LD de noticia) | 0 |
| RPP | 35.835 | 19.289 | 19.349 | 70 (videos y galerías) | 20 (8 agotaron los 3 intentos) |
| Exitosa | 20.990 | 14.973 | 15.123 | 0 | 0 |
| El Tiempo | 4.580 | 4.580 | 4.580 | 0 | 0 |

Consolidado: **75.169 notas de 2026** en `data/processed/noticias/notas.csv`. "Leídas" incluye las notas de muestra de las pruebas, por eso supera a las candidatas en RPP y Exitosa.

## Pruebas al terminar el histórico (27-oct)
`python -m radar.noticias.viabilidad resultados` (5,2 min, sin alertas). Umbrales fijados en [definicion.md](definicion.md) antes de correrlas.

### Volumen — **PASA**
**2.236 notas `sobre_nino`** del 1-ene al 24-oct (umbral 400): Andina 1.119, RPP 452, Exitosa 336, El Tiempo 329.

| Mes | ene | feb | mar | abr | may | jun | jul | ago | sep | oct (al 24) |
|-----|----:|----:|----:|----:|----:|----:|----:|----:|----:|----:|
| Notas | 21 | 78 | 79 | 31 | 53 | 180 | 325 | 423 | 556 | 490 |

La cobertura sigue al estado oficial: poca en el verano y crece de junio en adelante, con la alerta. Andina aporta la mitad: los tópicos y comparaciones por medio deben ponderar o separar por medio.

### Control positivo — **NO PASA**; con el respaldo del README, pasa
| Nivel (acumulado) | Notas de Andina | Comunicados distintos |
|-------------------|----------------:|----------------------:|
| `enlace` (PDF del comunicado, criterio del README) | **5** (umbral 20) | 5 |
| + `numero` (cita el número; respaldo del README) | **31** | 14 |
| + `proximo` (anuncia la fecha del próximo; extensión aprobada) | 40 | 17 |
| + `informe` (enlaza el informe técnico de su fecha; extensión aprobada) | 41 | 17 |

Como se anticipó el 24-oct, Andina casi nunca enlaza el PDF. Se aplica el remedio previsto: el control positivo usa `numero`, que pasa (31 notas sobre 14 comunicados distintos; el ENFEN emitió 18 en 2026). `proximo` e `informe` se reportan aparte, como extensiones.

### Calidad — **PASA**
- Candidatas con titular y `datePublished`: 100 %. Duplicados (medio, id): 0.
- Cuerpo con ≥ 40 % de las palabras del resumen: 99,25 % (umbral 95 %); sin texto (galerías, videos): 355 de 73.307.
- RPP, cuerpo con ≥ 90 % del `articleBody`: 18.397 de 18.402 (99,97 %).

### Filtro por título (histórico) — **PASA**
Pérdida estimada de enero a octubre con las candidatas de `config.CANDIDATAS`: **0 %** (umbral 20 %). Andina y El Tiempo se descargan completos. De lo que no se descarga se leyeron 15 notas por mes: RPP 0 de 138 (15.568 no descargadas), Exitosa 0 de 120 (4.812) y 0 de 15 en los números probados (25).

- **El IC95 bootstrap sale 0-0 porque no hubo ningún positivo, no porque la pérdida sea nula.** Cota conservadora (regla del tres: con 0 de 273 notas leídas, a lo más 1,1 % de las 20.405 no descargadas hablan de El Niño, ≈ 224 notas; ya se tienen 1.739 con El Niño en su inicio): **pérdida ≤ ≈ 11 %**, también por debajo del 20 %.
- Exitosa de septiembre y octubre no entra en esta muestra: esos meses llegaron por la recolección diaria, que lee sus sitemaps mensuales 202609 y 202610. Su pérdida se midió en el paso 1 (2,7 % con las candidatas).

### Control negativo (informativo)
`data/processed/noticias/control_negativo.csv`: 100 notas por medio que no mencionan El Niño ni tienen términos del filtro (`otros_temas`), y 100 por medio que no lo mencionan pero hablan de lluvias, calor u otros términos (`cercano`). Repartidas por mes, 800 en total.

### Cobertura del archivo de RPP
Ya pasó como prueba formal el 25-oct (99,56 % y 99,48 %); con el histórico completo no hay nada nuevo que medir.
