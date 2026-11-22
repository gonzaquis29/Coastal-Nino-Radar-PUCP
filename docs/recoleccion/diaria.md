# Recolección diaria

Script que descubre las notas nuevas de cada fuente y guarda solo sus direcciones en `data/urls/`. Las mediciones que respaldan estas decisiones están en [validacion-2026-10-24.md](validacion-2026-10-24.md).

## Uso
```bash
pip install -e ".[dev]"          # una sola vez (ver "Cómo montar el proyecto" en el README)
python -m radar.recoleccion.diario --persona joseph
```
- `--persona gonzalo|joseph`: obligatorio; va en el nombre del archivo.
- `--prueba`: ejecuta todo y muestra el resumen sin escribir archivos ni tocar git.
- `--publicar`: `git pull --ff-only` (se detiene si falla) → recolecta → `git add` solo de sus archivos → commit "datos: recolección AAAA-MM-DD (persona)" → push; si el push se rechaza, `git pull --rebase` y otro intento (no hay conflicto: cada ejecución escribe sus propios archivos).
- **Margen: máximo 48 h entre ejecuciones.** Con más tiempo se pierden notas de RPP y Andina (ver "Ventanas").
- Cada ejecución lee la ventana completa de cada sitemap (varios días hacia atrás) y guarda solo lo que falta: las notas publicadas después de una ejecución entran en la siguiente. El nombre del archivo es la fecha de la ejecución, no la de las notas; para tener un día completo se unen todos los CSV y se agrupa por `fecha`.
- `--prueba` no cuenta para el margen, porque no guarda nada.

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
- Errores de red (conexión, tiempo agotado, respuesta cortada o incompleta frente a `Content-Length`) y respuestas 429, 500, 502, 503 o 504: hasta 2 reintentos con espera exponencial y algo de azar; `Retry-After` se respeta en segundos o como fecha, hasta 120 s.
- Un host que falla 5 veces seguidas se suspende en esa ejecución (no se le sigue pidiendo nada) y se reporta.
- 403: no se reintenta y se reporta (no se eluden bloqueos).
- El detalle técnico de cada fallo (con la traza) queda en `data/registros/diario-<fecha>.log`; en pantalla, solo el resumen.
- Estos valores están en `src/radar/config.py`.
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

## Recuperación de huecos (16-nov)
El 16-nov la recolección corrió después de 129 h y avisó huecos en Andina (`sitemap-ultimo` empezaba el 14-nov) y RPP (`web/peru` desde el 11-nov y `web/futbol` desde el 12-nov). Se recuperan con las vías del histórico, sin un módulo nuevo:
- **Andina:** no hace falta nada. `historico` prueba todos los números desde `ANDINA_PRIMER_ID` hasta el mayor visto en `data/urls/`, y salta los que ya conoce. Los 355 números del hueco (1.099.448 a 1.100.190) se resolvieron todos (301 a su nota).
- **RPP:** el archivo por fecha recorre, además del histórico, los días de `config.HUECOS_RPP` (10, 11 y 12-nov). Aportó 36 notas que la diaria no tenía (3, 26 y 7).
- **Validación:** se comparó con la diaria de esos días. Día por día cubre de 0,93 a 0,99, porque la diaria y el archivo a veces fechan la misma nota en días distintos. Con los días vecinos (9 al 13-nov) y sin las páginas "live" (5, que el archivo no lista, como en la validación del 24-oct), cubre 296 de 299 notas (**0,990**, umbral 0,99). Este ajuste de la comparación se decidió después de ver la primera cifra.
- Lo recuperado entra en la lista cruda del medio (`data/raw/noticias/<medio>/lista.csv`), no en `data/urls/`, y se lee con la rutina de `historico`.

## Recuperación de huecos (22-nov)
La recolección del 22-nov a las 10:00 corrió 73 h después de la anterior. Fue la última del período: el corte es el 20-nov a las 23:59. Avisó dos huecos: Andina (`sitemap-ultimo` empezaba el 19-nov a las 23:00) y RPP (`web/futbol` desde el 20-nov a las 13:55). Se recuperaron igual que el 16-nov:
- **Andina:** `historico` recorrió los números de nota sin hacer nada aparte.
- **RPP:** el 19 y el 20-nov se agregaron a `config.HUECOS_RPP`. El archivo de esos días listó 133 y 118 notas, y aportó 24 que la diaria no tenía (16 y 8).
- **Lectura:** `historico` leyó 699 notas sin errores y el consolidado quedó en 81.879. `region.notas` pasa (2.785 notas sobre El Niño).
- **Aviso del ENFEN:** la página del comunicado N.° 20 se modificó el 19-nov. `oficial.corpus` lo rehízo sin cambios en los comunicados; entraron 3 avisos nuevos del Senamhi (472, 476 y 477). Siguen las dos fallas de antes: el control con `pypdf` del N.° 19 y el acuerdo polígono/regla del Senamhi.
