# Recolección diaria

Script que descubre las notas nuevas de cada fuente y guarda solo sus direcciones en `data/urls/`. Las mediciones que respaldan estas decisiones están en [validacion-2026-10-24.md](validacion-2026-10-24.md).

## Uso
```bash
pip install -r requirements.txt
python src/recolector/diario.py --persona joseph
```
- `--persona gonzalo|joseph`: obligatorio; va en el nombre del archivo.
- `--prueba`: ejecuta todo y muestra el resumen sin escribir archivos ni tocar git.
- `--publicar`: `git pull --ff-only` (se detiene si falla) → recolecta → `git add` solo de sus archivos → commit "datos: recolección AAAA-MM-DD (persona)" → push; si el push se rechaza, `git pull --rebase` y otro intento (no hay conflicto: cada ejecución escribe sus propios archivos).
- **Margen: máximo 48 h entre ejecuciones.** Con más tiempo se pierden notas de RPP y Andina (ver "Ventanas").

## Qué hace
- Lee los sitemaps (y una API) de 6 fuentes, sin descargar ninguna nota.
- Guarda **todas** las notas, sin filtrar por sección: el control negativo y la medición del filtro por título las necesitan. Se descartan solo las de fecha conocida anterior al 1-ene-2026.
- Nunca guarda títulos, cuerpo ni palabras clave de los medios.
- Escribe `data/urls/AAAA-MM-DD_<persona>.csv` (notas) y `data/urls/AAAA-MM-DD_<persona>_sitemaps.csv` (registro de sitemaps). La fecha es la del día de la ejecución en Lima.

## Fuentes y vías

| Fuente | Lee | Descarta | Fecha | Sección |
|--------|-----|----------|-------|---------|
| Andina | `news-sitemap.xml`, `sitemap-ultimo.xml` y los `sitemap-seccion-*.xml` del índice `agencia/sitemap.xml` | galería, videos, podcast, fijas e inglés; solo `noticia-*-N.aspx` | news → publicación; los demás → modificación | nombre del sitemap de sección (unidas con `\|` si son varias); vacía si no está en ninguno |
| RPP | `/sitemap/news`, los sitemaps del índice `/sitemap/web` y los listados en `robots.txt` (incluye `actualidad`, que no está en el índice) | — | news → publicación; `/sitemap/web/*` → modificación | segmentos de la dirección antes del slug (`peru/actualidad`) |
| Exitosa | `sitemapNews.xml`, mensual del mes en curso y del anterior | `sitemapGeneral.xml` (portadas) | news → publicación; mensual → vacía | primer segmento de la dirección |
| El Tiempo | API REST `wp-json/wp/v2/posts?after=<hoy − 10 días>&_fields=id,link,date_gmt`; `news.xml` de respaldo | — | `date_gmt` → publicación | primer segmento de la dirección |
| ENFEN | `wpdmpro-sitemap.xml` y `post-sitemap.xml` | páginas que no son documentos ni entradas | `lastmod` (UTC) → modificación | tipo según la dirección: comunicado-oficial, informe-tecnico, nota-tecnica, nota-de-prensa, entrada, otro |
| Senamhi | `?p=aviso-meteorologico` (tabla de avisos) | anteriores a 2026 | columna "Emisión" → emisión (solo fecha) | `aviso` |

Se leen primero los sitemaps de noticias, para que una nota quede con su fecha de publicación antes de verla con `lastmod`. La fecha verdadera de las candidatas sale después del `datePublished` de su HTML.

## Esquema del CSV de notas
UTF-8 sin BOM, saltos de línea LF (también fijados en `.gitattributes`), encabezado en cada archivo.

| Columna | Ejemplo | Nota |
|---------|---------|------|
| `url` | `https://rpp.pe/peru/actualidad/…-noticia-1714224` | tal como viene; Senamhi siempre en forma `-detalle` |
| `medio` | `andina`, `rpp`, `exitosa`, `eltiempo`, `enfen`, `senamhi` | |
| `id` | `1097214`, `noticia-1714224`, `live-3673`, `n186749`, `2026-29301` | número del medio; en RPP con prefijo porque `live` tiene otra numeración; en Senamhi año + número |
| `fecha` | `2026-10-24T11:00:45-05:00` | ISO 8601 en −05:00 (desfase fijo: el Perú no tiene horario de verano); Senamhi solo fecha; puede ir vacía |
| `tipo_fecha` | `publicacion`, `modificacion`, `emision` o vacío | |
| `seccion` | `peru/actualidad` | |
| `origen` | `rpp:web/peru` | primer sitemap o endpoint donde se vio |
| `recolectado` | `2026-10-24T12:10:03-05:00` | |

## Registro de sitemaps
Una fila por sitemap leído: `sitemap`, `http`, `entradas`, `mas_antigua`, `mas_reciente`, `ventana_h` (horas desde la quinta entrada más antigua, para que una nota vieja suelta no la infle), `recolectado`. Mide las ventanas durante todo el período y sirve para el informe (protocolos web, dinámica de los procesos web, fase 6 de CRISP-ML(Q)).

## Duplicados
- Una fila es duplicada si ya existe su (`medio`, `id`) **o** su `url` en cualquier `data/urls/*.csv`. El número es la clave real: con otro slug y el mismo número, los medios redirigen a la nota correcta.
- Se lee la columna clave de todos los archivos (~20 mil filas al final, menos de 1 s). Leer solo los últimos días no sirve: las secciones de RPP traen notas viejas.
- Si el archivo del día ya existe, se le agregan filas; si no hay nada nuevo, no se crea.
- Si los dos ejecutan el mismo día sin `git pull`, los duplicados entre archivos se eliminan al unirlos.

## Ventanas
Cuánto hacia atrás llega cada sitemap (detalle en la validación):

| Sitemap | Corte | Ventana |
|---------|-------|---------|
| Andina `sitemap-ultimo` | desde las 00:00 de anteayer | 48-72 h |
| Andina secciones | 64 notas | 1,9 días a meses (la sección se recupera del HTML) |
| Exitosa `sitemapNews` | desde las 00:00 de anteayer | ~2 días (el mensual cubre todo, sin fecha) |
| RPP Perú | 100 notas | mínimo 3,4 días en 2026 |
| RPP fútbol | 100 notas | mínimo 1,4 días |
| RPP news | 200 notas | 0,9-3,6 días (si no se alcanza, la nota queda con fecha de modificación) |
| El Tiempo API | sin límite | — |

Con 48 h entre ejecuciones solo puede perderse, en días muy cargados, parte del fútbol de RPP (se recupera por el archivo por fecha).

## Errores
- Cada fuente corre por separado: si una falla, las demás siguen. Si falla un sitemap, siguen los demás de esa fuente.
- 5xx o tiempo agotado: hasta 2 reintentos con espera creciente; `Retry-After` se respeta hasta 120 s.
- 403: no se reintenta y se reporta (no se eluden bloqueos). 429: se espera una sola vez.
- XML mal formado: se descarta ese sitemap y se reporta.
- 404 del mensual del mes en curso de Exitosa (aún no creado): normal.
- Código de salida 1 solo si fallan todas las fuentes.

## Ética
- User-agent honesto: `CoastalNinoRadar-PUCP/0.1 (proyecto academico INF656 PUCP; +https://github.com/gonzaquis29/Coastal-Nino-Radar-PUCP)`.
- `robots.txt` se lee una vez por host con un verificador propio que entiende `*` y `$` (`urllib.robotparser` no los entiende y da por permitido lo que RPP prohíbe con `/tema*`). Si el `robots.txt` no se puede leer por un error del servidor, esa fuente no se recolecta.
- 1 petición por segundo por host; ~60 peticiones por ejecución.

## Resumen y alertas
- Por fuente: sitemaps leídos, filas vistas, nuevas, fallos y fecha más antigua.
- **Hueco:** la ventana de un sitemap de cobertura (Andina `sitemap-ultimo`, RPP `/sitemap/web/*`, `news.xml` de El Tiempo si se usó) empieza después de la última recolección registrada → dice por qué vía recuperar (número de nota de Andina, archivo por fecha de RPP).
- **Sin novedades:** 0 nuevas en un medio que publica a diario, si pasaron más de 12 h desde la última ejecución.
- **Más de 36 h** desde la última ejecución.
- **Nuevo documento del ENFEN.**

## Volumen
~380 filas nuevas por día (Andina ~130, RPP ~140, Exitosa ~90, El Tiempo ~15-20, ENFEN y Senamhi ~1-2), ~90 KB/día. La primera ejecución (24-oct) trajo 7.485 filas, 1,75 MB: incluye los mensuales de septiembre y octubre de Exitosa (3.762 sin fecha) y las secciones de RPP con notas de 2026. Total al 27-nov: ~5 MB.
