# YouTube y Google Trends: definición (aprobada el 16-nov-2026)

Los criterios se fijaron aquí antes de ver un solo dato y no se cambian con los resultados. El código está en `radar.youtube` y `radar.trends` (sección 9). Base: README (filas 1, 7, 10 y 11, "Reglas por sitio", "Pruebas de viabilidad"), y la página oficial de cuotas de la API, revisada el 16-nov: `search.list` tiene su propio límite de 100 llamadas por día; `videos.list`, `channels.list`, `commentThreads.list` y `playlistItems.list` cuestan 1 unidad del cupo de 10 000 por día. El cupo se reinicia a medianoche del Pacífico, que son las 03:00 en Lima.

## 1. Mapa de enfoques

**Descubrir videos de YouTube**

| Enfoque | Qué da | Problema | Decisión |
|---------|--------|----------|----------|
| A. `search.list` por término × tramo × orden (README) | Videos de cualquier canal, con fechas acotadas | 100 búsquedas por día; con 50 resultados por búsqueda, un tramo con mucho volumen se satura (en el orden por fecha, solo salen los últimos días del tramo) | **Base** |
| B. Subidas de canales semilla (`playlistItems.list`, 1 unidad) | Todo lo que subieron los canales de los 4 medios y los oficiales, barato y sin el límite de búsquedas | Sesgado a canales conocidos; no encuentra a "otros" | **Solo como respaldo**, si V1 no pasa |
| C. Bola de nieve por videos relacionados | — | La API quitó `relatedToVideoId` en 2023 | Descartado |
| D. Scraping de la web o de `/results` | — | Prohibido por la regla del sitio y por `robots.txt` | Descartado |
| E. Datasets de terceros o API de pago | — | No cubren 2026 ni Perú; cuesta dinero | Descartado |

**Interés de búsqueda (Trends)**

| Enfoque | Problema | Decisión |
|---------|----------|----------|
| Exportar el CSV desde la web, a mano (README) | No es automático; hay ruido de muestreo entre exportaciones | **Base** |
| `pytrends` | Archivado; además, es scraping no oficial | Descartado |
| API oficial de Trends | En alfa cerrado | Descartado |
| Servicios de pago (SerpAPI, etc.) | Cuestan dinero y son scraping de terceros | Descartado |

**Cliente HTTP.** CLAUDE.md pide `radar.comun.http.Cliente` para toda petición web. Para la API se propone `google-api-python-client`, que figura en el stack, envuelto en `radar.youtube.api`. Ese envoltorio aplica el ritmo, los reintentos y el registro, lleva la cuenta del cupo y **borra la clave de todo mensaje de error y de todo registro**, porque `HttpError` incluye la dirección con `key=`. Esto se declara en CLAUDE.md como una excepción. `robots.txt` no aplica a la API: lo que manda son los términos y las políticas para desarrolladores.

## 2. Búsquedas

- **Términos (5, del README):** "fenómeno El Niño", "Niño costero", "ENFEN", "El Niño Perú", "lluvias costa norte".
- **Parámetros:** `type=video`, `regionCode=PE`, `relevanceLanguage=es`, `publishedAfter` y `publishedBefore` con hora de Lima, `maxResults=50`, una sola página.
- **Tramos y orden:**
  - **Día 1:** meses de enero a octubre × 5 términos × 2 órdenes (`date` y `relevance`) = **100 búsquedas**.
  - **Día 2:** se parte en dos quincenas cada búsqueda por fecha que haya devuelto 50 (saturada), solo en orden por fecha, hasta 100 búsquedas. Si siguen saturadas, se declaran. La regla queda fijada desde ahora; no se elige a ojo.
  - **Corte:** noviembre (del 1 al 20) × 5 × 2 = 10 búsquedas. Cada día se cuenta según el cupo (sección 6).
- **Filtro (README, en código y sin etiquetar):**
  - El título o la descripción mencionan El Niño según `radar.noticias.rasgos.menciones`. Es la misma regla de las notas, que ya descarta "Hospital del Niño" o "Día del Niño", y no se escribe otra.
  - **Y además** mencionan Perú o una región peruana (`radar.region.asignacion`: cualquier macro-región salvo "nacional", o la palabra Perú), o el canal tiene `country=PE`.
- **Se guarda** por qué búsquedas apareció cada video (término, tramo y orden), para medir el sesgo y la saturación.

## 3. Campos

| Tabla | Campos | Dónde |
|-------|--------|-------|
| Videos | id, título, descripción, enlaces de la descripción, id del canal, `publishedAt`, duración, categoría, vistas, likes (vacío si están ocultos), n.° de comentarios, estado de los comentarios (abiertos o desactivados), fecha de descarga | `data/raw/youtube/` |
| Canales | id, título, `country`, suscriptores (vacío si están ocultos), `customUrl`, enlaces del canal (para verificar la identidad sitio–canal del "Tipo de canal") | `data/raw/youtube/` |
| Comentarios | id del hilo, id del video, texto del comentario principal, `publishedAt`, likes, n.° de respuestas, **autor seudonimizado** | `data/raw/youtube/` |
| Derivados por video | rasgos del título, discrepancia, emociones agregadas, tipo de canal, canal seudonimizado si es de tipo "otros" | `data/processed/youtube/` |

- Las respuestas a los comentarios no se descargan, solo se cuentan.
- Nunca se guardan el nombre ni la foto del autor, ni la dirección de su canal.

## 4. Seudonimización

- El seudónimo es `HMAC-SHA256(sal, authorChannelId)`, truncado a 16 caracteres hexadecimales. La sal va en una variable de entorno (`RADAR_YOUTUBE_SAL`), nunca en el repo, y se borra con los datos. Así nadie puede revertir el seudónimo ni cruzarlo con otro proyecto.
- En el texto de los comentarios se reemplazan las `@menciones`, los correos y los teléfonos por marcadores antes de escribir el archivo.
- **Canales:** el nombre se conserva solo si el canal es "oficial" o "medio", porque son instituciones. Los de tipo "otros" se seudonimizan con la misma sal en `processed/`. La app nunca señala canales individuales ni muestra comentarios.

## 5. Borrado a los 30 días

- Cada archivo crudo lleva su fecha de descarga en el nombre (`AAAA-MM-DD_*.jsonl`).
- `python -m radar.youtube.borrar` elimina lo que tenga más de 30 días, crudo y por video, incluida la sal. Todos los módulos de YouTube **se niegan a leer** un archivo vencido.
- Después del **20-dic-2026** solo quedan agregados sin ids: KPIs, métricas del modelo y estadísticas de la red.
- La presentación del 1-dic cae dentro de la ventana de 30 días.
- Ningún dato de YouTube se versiona, tampoco en `data/urls/`.

## 6. Cupo y calendario (la clave la crea el usuario: `YOUTUBE_API_KEY`)

Las fechas dependen del día en que exista la clave. Por eso se fijan en **días de cupo** (un día va de las 03:00 de Lima a las 03:00 del día siguiente), no en fechas. Lo único fijo es el corte.

| Día de cupo | Búsquedas | Unidades (aprox.) | Qué |
|-------------|-----------|-------------------|-----|
| Día 1 (el primero con clave) | 100 | ~300 | Enero a octubre + `videos.list` y `channels.list` + 1 página de comentarios en los candidatos → **prueba de viabilidad** (Y1, Y2 y Y4) |
| Día 2 (cualquier día siguiente, antes del corte) | ≤ 100 | ~200 | Quincenas saturadas |
| Corte (el primer cupo después del 20-nov a las 23:59, o sea el 21-nov desde las 03:00) | 10 | ≤ 9 000 | Noviembre; métricas de todos los videos en **una sola fecha**; comentarios: 1 página (100) para todos y luego más páginas, hasta 10 por video, mientras quede cupo, dejando 1 000 de margen → Y3 y Y5 |

**Si la clave llega tarde:**
- **Si llega el 20-nov:** el día 1 se corre ese día, el día 2 no se hace (las búsquedas saturadas se declaran) y el corte va el 21-nov.
- **Si llega después del 20-nov:** el día 1 y el corte se juntan en dos días seguidos, y todo se mide con la misma descarga.
- **Fecha del corte (por decidir):** el 21-nov a primera hora, para cubrir hasta las 23:59 del 20-nov con un cupo nuevo. La alternativa es el 20-nov por la noche, que deja fuera las últimas horas.
- **Límite:** el congelamiento es el 27-nov, así que el último día útil para el día 1 es el 24-nov. Después no queda tiempo para el modelo ni para la red.

## 7. Prueba de viabilidad: criterios fijados antes

| Id | Criterio | Umbral | Si no pasa |
|----|----------|--------|------------|
| Y1 | Videos que pasan el filtro, publicados en el período | ≥ 300 | Respaldo B (canales semilla); si sigue sin pasar, YouTube deja de ser central (README) |
| Y2 | Videos con ≥ 30 comentarios **descargables** (no solo `commentCount`) | ≥ 100 | Engagement sin comentarios; la red pasa a la co-mención |
| Y3 | Red canal–canal: componente conectado | ≥ 30 canales | Co-mención (se mide con los comentarios del corte) |
| Y4 | Canales clasificados sin ambigüedad en "Tipo de canal" | ≥ 70 % | Revisar las reglas del tipo |
| Y5 | Videos para el modelo: ≥ 14 días al descargar; entrenamiento de enero a agosto; prueba de septiembre al 6-nov. El umbral es propuesto: el README no fija número; con menos de 50 en la prueba, el error medido sería poco estable | ≥ 150 y ≥ 50 | Alternativa con Trends (pendientes, punto 1) |

- Y1, Y2 y Y4 se miden el 17-nov; Y3 y Y5, con la descarga del corte.
- Se reporta, sin umbral, el porcentaje de búsquedas saturadas.

## 8. Google Trends

- **Consulta principal:** **una sola serie por departamento**, el **tema** "El Niño" de Trends. El tema agrupa las variantes ("fenómeno del niño", "niño costero"…). Si el tema no aparece en la web, se usa el término "fenómeno del niño".
  - No se mezcla con "lluvias" ni "huaico" en la misma comparación: como cada consulta se escala a 0-100 con su máximo, un término de mucho volumen aplastaría a El Niño hasta "<1" y haría fallar G1 por una mala consulta, no por falta de datos.
- **Contexto (opcional):** "lluvias" y "huaico", en otra consulta por departamento. No entran en G1.
- **Período:** del 1-ene al 20-nov-2026. Son más de 9 meses, así que Trends lo entrega por semana. La última semana, incompleta, se descarta.
- **Categoría:** todas; búsqueda web.
- **Fecha:** la exportación de viabilidad se hace cualquier día antes del corte, y la final, después del corte. Las dos sirven para G2.
- **Departamentos:** Tumbes, Piura, Lambayeque y La Libertad, más una consulta nacional con desglose por región para comparar niveles.
- **Archivos:** el usuario los exporta a `data/raw/trends/<departamento>.csv`. `python -m radar.trends.cargar` comprueba el encabezado (región, fechas y términos) y se niega a cargar una exportación que no coincida.
- **Criterios:**
  - **G1 (README):** ≥ 3 de los 4 departamentos con datos en ≥ 50 % de las semanas. "Con dato" significa un valor ≥ 1: "<1" y 0 no cuentan.
  - **G2 (estabilidad):** la misma consulta, exportada otro día (en el corte), tiene ρ de Spearman ≥ 0,8 por departamento. Si no pasa, se promedian las dos exportaciones y se declara.
  - Si G1 no pasa, Trends queda solo a nivel nacional.

## 9. Cómo se corre

**Antes de empezar (lo hace el usuario):**
- Crear dos variables de entorno: `YOUTUBE_API_KEY`, con la clave de la API, y `RADAR_YOUTUBE_SAL`, con al menos 16 caracteres al azar. Ninguna va en el repo ni en el chat.
- Instalar la biblioteca: `pip install -e ".[youtube]"`. Con logfire instalado, conviene fijar `google-api-core<2.26` y `protobuf<7`: las versiones nuevas suben `opentelemetry-api` y rompen pytest.

**YouTube:**
```
python -m radar.youtube.descarga dia1     # 100 búsquedas, metadatos y la 1.ª página de comentarios
python -m radar.youtube.canales           # tipo de canal (lee una portada por sitio, respeta robots.txt)
python -m radar.youtube.viabilidad        # Y1, Y2, Y4 (y Y3, Y5 después del corte)
python -m radar.youtube.descarga dia2     # otro día de cupo: quincenas saturadas
python -m radar.youtube.descarga corte    # el 21-nov desde las 03:00 de Lima
python -m radar.youtube.borrar            # a los 30 días (--simular para ver qué borra)
```
- Cada etapa se puede cortar y volver a correr: no repite búsquedas, metadatos ni páginas ya descargadas. Si se acaba el cupo, sale con el código 3 y se vuelve a correr el día de cupo siguiente.
- La etapa comprueba la clave, la sal y la vigencia de los datos antes de gastar cupo.
- Un candado propio (`data/raw/youtube/api.lock`) evita dos descargas a la vez. `canales` usa el candado de red común, porque pide páginas.

**Trends:** exportar a mano el CSV "Interés a lo largo del tiempo" a `data/raw/trends/<departamento>_<AAAA-MM-DD>.csv` (tumbes, piura, lambayeque, la-libertad; la fecha es la del día de la exportación). Después:
```
python -m radar.trends.cargar             # G1 (y G2 con la segunda exportación)
```

**Archivos:**
- `data/raw/youtube/AAAA-MM-DD_{busquedas,videos,canales,comentarios}.jsonl` y `AAAA-MM-DD_tipos.csv` en `data/processed/youtube/`. Todos vencen a los 30 días.
- `data/processed/youtube/validacion.csv` y `data/processed/trends/{interes,validacion}.csv`. Son agregados sin ids, así que no vencen.

**Pruebas:** `tests/youtube/` y `tests/trends/` usan un servicio falso de la API, HTML inventado y CSV inventados. No usan red, clave ni datos reales.

## 10. Resultados del día 1 (16-nov-2026)

**Descarga:** 99 de 100 búsquedas. La número 100 recibió un 429 y su reintento ya no tuvo cupo; la retoma `descarga dia1` en el próximo día de cupo. Quedaron 2.966 videos, 1.368 canales y la página 1 de comentarios, con sus respuestas, de 114 videos. En total se gastaron 388 unidades de 10.000.

| Id | Resultado | Umbral | |
|----|-----------|--------|---|
| Y1 | 1.225 videos pasan el filtro | ≥ 300 | **Pasa** |
| Y2 | 114 videos con ≥ 30 comentarios descargados, con respuestas | ≥ 100 | **Pasa** (tras corregir la medición) |
| Y4 | 0,953 de los 443 canales de la muestra sin ambigüedad | ≥ 0,70 | **Pasa** (tras corregir la regla) |

- **Descartes del filtro:** 1.323 videos no mencionan El Niño y 418 no son de Perú.
- **Saturación:** 28 de 50 búsquedas por fecha llegaron a 50 resultados; el día 2 las parte en quincenas.

**Correcciones hechas después de ver el dato (declaradas; los umbrales no cambiaron):**
1. **Y2 medía menos de lo definido.** La definición dice "comentarios descargables", pero el código solo contaba los comentarios principales y daba 84. Ahora también baja las respuestas: las incluidas en `commentThreads` (`part=snippet,replies`) y las demás con `comments.list`. Como los ids de los hilos solo se guardaron seudonimizados, se volvió a pedir la página 1 de los 114 videos (186 unidades; `completar_respuestas`). Contadas así son 114, el mismo número del conteo de la API.
2. **El tipo de canal estaba al revés del README.** Exigía que el canal enlazara a su sitio, pero la API no entrega la sección de enlaces del canal. También aceptaba `datePublished` como metadato de noticia. Con eso, SENAMHI, RPP y Latina salían como "otros", y una academia o un estudio legal como "medio". Ahora:
   - **Oficial:** el canal está enlazado desde los sitios `.gob.pe` de `config/instituciones_web.csv` o desde las páginas `.gob.pe` que enlazan sus videos.
   - **Medio:** los sitios candidatos salen también de las descripciones de sus videos, y se exige `NewsArticle` o un sitemap de noticias.
   - Se reconoce además la forma `youtube.com/<nombre>`, que es la que usa el SENAMHI.

**Clasificación resultante:**
- **Por videos:** de los 1.225 que pasan el filtro, 320 son de medios, 47 de oficiales y 858 de otros.
- **Oficiales:** SENAMHI, INDECI, IGP, IMARPE, la Marina y el Mininter.
- **Medios:** Exitosa, RPP, Latina, El Comercio, Correo, entre otros.

**Límites declarados del tipo de canal:**
- **Andina queda como "otros":** su sitio enlaza una dirección antigua del canal (`/c/andinacanalonline`), y la API no permite saber a qué canal corresponde.
- **TVPerú queda ambiguo:** su sitio responde 403, y no se eluden bloqueos.
- **Canales nacionales que no enlazan su sitio en ninguna descripción** (24 Horas, ATV, La República) quedan como "otros".
- **El estado de un canal puede quedar como "otros"**, porque solo cuenta como oficial si el sitio enlaza a ese canal en particular.

`canales` leyó 381 sitios en unos 3,5 min (8 a la vez y de a uno por sitio).

## 11. Resultados del día 2 (17-nov-2026)

**Descarga:** el día 1 terminó con la búsqueda que faltaba. El día 2 hizo 56 búsquedas por quincena; en total quedan 3.819 videos (818 nuevos) y 1.798 canales. Bajó la página 1 de comentarios, con sus respuestas, de 136 videos. `canales` leyó 123 sitios nuevos en 1 min 14 s.

| Id | Resultado | Umbral | |
|----|-----------|--------|---|
| Y1 | 1.564 videos pasan el filtro | ≥ 300 | **Pasa** |
| Y2 | 136 videos con ≥ 30 comentarios descargados (igual al conteo de la API) | ≥ 100 | **Pasa** |
| Y4 | 0,949 de los 568 canales de la muestra (6 oficiales, 22 medios, 540 otros) | ≥ 0,70 | **Pasa** |

**Saturación declarada (regla de la sección 3):** 41 de las 56 quincenas siguen llegando a 50 resultados; sumando el día 1, son 69 de las 106 búsquedas por fecha. No se parten más, porque la regla no lo prevé. La muestra de videos es, entonces, un piso: en las quincenas saturadas hay videos que la API no devuelve. Y1 pasa con holgura igual.

**Descartes del filtro:** 1.590 videos no mencionan El Niño y 665 no son de Perú.

## 12. Resultados de Trends: primera exportación (17-nov-2026)

**Exportación:** la hizo la IA con Claude in Chrome, en el navegador del usuario y a pedido suyo. El navegador integrado de la app recibió un 429 y no se insistió. Son 4 CSV de "Interés a lo largo del tiempo" del 1-ene al 17-nov, guardados en `data/raw/trends/<departamento>_2026-11-17.csv`.
- **Tema elegido:** "El Niño · Fenómeno" (`/g/120ldl7m`), la entidad del fenómeno, que agrupa sus variantes. No se usó "El Niño-Oscilación del Sur · Tema", que es la oscilación completa e incluye a La Niña.
- **Período:** 46 semanas completas; la semana en curso se descarta.

| Departamento | Semanas con dato (≥ 1) |
|---|---|
| Tumbes | 13 % |
| Piura | 80 % |
| Lambayeque | 72 % |
| La Libertad | 85 % |

**G1 pasa: 3 de 4 departamentos** (umbral ≥ 3). Trends entra por departamento. Tumbes, con 13 %, queda declarado como serie con pocos datos: su volumen de búsqueda es bajo y casi todas sus semanas valen 0.

**Pendiente:**
- **G2:** se mide con la segunda exportación, después del corte, y la misma consulta.
- **Consulta nacional con desglose por región:** sirve para comparar niveles, no entra en G1 y sigue sin hacer.

## 13. Resultados del corte (22-nov-2026)

**Fecha:** el corte corrió el 22-nov a las 10:05, no el 21-nov como estaba previsto, porque la rutina se atrasó. Las búsquedas siguen cubriendo hasta el 20-nov (`FIN_CORTE`). Los conteos y los comentarios, en cambio, se leen el 22-nov e incluyen las respuestas de esos dos días; se declara.

**Descarga:** 4.147 videos encontrados (todos descargados) y 1.944 canales. Se bajaron los comentarios, con sus respuestas, de 905 videos, hasta 10 páginas por video. Tomó unos 9 min y quedaron 7.703 unidades libres del cupo. `canales` clasificó los 1.944 canales (6 oficiales, 69 medios, 1.869 otros) y dejó 93 ambiguos.

| Id | Resultado | Umbral | |
|----|-----------|--------|---|
| Y1 | 1.762 videos pasan el filtro | ≥ 300 | **Pasa** |
| Y2 | 154 videos con ≥ 30 comentarios descargados (igual al conteo de la API) | ≥ 100 | **Pasa** |
| Y3 | Componente conectado de la red canal–canal: 151 canales | ≥ 30 | **Pasa** |
| Y4 | 0,945 de los 656 canales de la muestra (6 oficiales, 24 medios, 626 otros) | ≥ 0,70 | **Pasa** |
| Y5 | 1.007 videos para entrenar y 622 para probar | ≥ 150 / ≥ 50 | **Pasa** |

- **Saturación declarada:** 73 de 111 búsquedas por fecha y 53 de 55 por relevancia llegan al tope de resultados. La muestra sigue siendo un piso.
- **Descartes del filtro:** 1.675 videos no mencionan El Niño y 710 no son de Perú.
- **Qué decide:** la red social se hace con YouTube (Y3) y hay datos para el modelo de engagement (Y5).

## 14. Resultados de Trends: segunda exportación (22-nov-2026)

**Exportación:** la hizo la IA con Claude in Chrome, a pedido del usuario. Usó la misma consulta que el 17-nov (tema "El Niño · Fenómeno", todas las categorías, búsqueda web), ahora del 1-ene al 20-nov. Los archivos son `data/raw/trends/<departamento>_2026-11-22.csv`. Las dos exportaciones dan 46 semanas completas.

| Departamento | Semanas con dato (≥ 1) | ρ de Spearman con la del 17-nov |
|---|---|---|
| Tumbes | 15 % | 0,790 |
| Piura | 80 % | 0,971 |
| Lambayeque | 78 % | 0,980 |
| La Libertad | 85 % | 0,983 |

- **G1 pasa (3 de 4).**
- **G2 no pasa:** el mínimo es 0,790 en Tumbes (umbral 0,80). Los otros tres superan 0,97. Se aplica la regla fijada antes: la serie de Tumbes es el promedio de las dos exportaciones en sus semanas comunes, y la de los demás es la del 22-nov. El criterio es por departamento, así que el promedio solo se aplica donde no llega. `radar.trends.cargar` lo hace solo (`serie_final`) y marca la columna `exportacion`. Se declara: con casi todas sus semanas en 0, Tumbes es la serie con más ruido de muestreo de Trends.
- **Consulta nacional (hecha):** la serie de Perú y el desglose por región, en `data/raw/trends/nacional/`. El desglose sirve para comparar niveles entre regiones y no entra en G1 ni en G2. En el período, Piura tiene el mayor interés relativo (100), seguida de Tumbes (65), La Libertad (56) y Lambayeque (45). El índice es relativo a las búsquedas de cada región, así que Tumbes tiene interés alto aunque su volumen sea bajo.
