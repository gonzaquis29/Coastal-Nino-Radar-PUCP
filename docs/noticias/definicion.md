# Histórico de noticias y pruebas de viabilidad

Recupera las notas de Andina, RPP, Exitosa y El Tiempo del 1-ene al 24-oct-2026, procesa las de la recolección diaria y mide si los datos alcanzan, con criterios fijados antes de correr las pruebas. El cuerpo de cada nota se lee en memoria, se usa para calcular sus rasgos y se descarta: nunca se guarda. Las mediciones que respaldan estas decisiones están en [validacion-2026-10-24.md](validacion-2026-10-24.md).

## Uso
```bash
pip install -e ".[dev]"                               # una sola vez
python -m radar.noticias.viabilidad filtro            # paso 1: pérdida del filtro en la recolección diaria (~40 min)
python -m radar.noticias.historico --horas 7          # paso 2: una noche; se repite hasta terminar
python -m radar.noticias.viabilidad rpp               # cobertura del archivo de RPP (cuando RPP esté descubierto)
python -m radar.noticias.viabilidad resultados        # volumen, control positivo, calidad, pérdida histórica y control negativo
```
- `historico`: `--medio andina rpp …` (por defecto los 4, uno por hilo: son hosts distintos), `--horas N` (se detiene sola y guarda), `--solo-descubrir` (arma las listas sin descargar notas), `--limite N` (para probar). Ctrl+C también guarda.
- Se reanuda solo: cada ejecución sigue donde quedó la anterior, sin repetir peticiones ni duplicar filas. También procesa las notas nuevas de `data/urls/`, así que se vuelve a correr hasta el corte.
- Registro detallado en `data/registros/noticias-*.log`.
- Código: `src/radar/noticias/` (`medios.py` vías y descarga, `nota.py` lectura en memoria, `filtro.py`, `rasgos.py`, `esquemas.py`, `historico.py`, `viabilidad.py`). Listas en `config/terminos_titulo.csv`, `config/secciones_excluidas.csv` y `config/actores.csv`; fechas, hosts y modo de candidatas en `src/radar/config.py`.

## Vías por medio (validadas el 24-oct-2026)
| Medio | Descubrimiento | Lectura de la nota | Peticiones (1/s) |
|-------|----------------|--------------------|------------------|
| Andina | Números desde `ANDINA_PRIMER_ID` (1.057.700) hasta el mayor de `data/urls/`: `noticia.aspx?id=N` sin seguir la redirección. El 301 trae el slug **aunque la nota no esté publicada**, así que se filtra por el slug | Solo las candidatas: la segunda petición confirma (sin publicar → `/agencia/inicio`) | ~40 mil + candidatas |
| RPP | Archivo `/archivo/<fecha>` de todas las secciones: la primera página en HTML y luego `page-1`, `page-2`… en JSON hasta `nextPage: false`. Trae titular y hora | HTML de la nota | ~12 por día + candidatas |
| Exitosa | Sitemaps mensuales (solo dirección). Cada número que falta entre el menor y el mayor se prueba con `/actualidad/x-nN` (301 hacia la nota o 404); así entra el hueco del 31-may | HTML de la nota (ISO-8859-1) | ~10 + 141 + candidatas |
| El Tiempo | API REST (`after`/`before`, 100 por página) | La misma API con `include=` (100 por petición): el cuerpo viene en `content` | ~100 |

- **Notas en inglés de Andina:** comparten numeración y la página no las marca (`lang="es"`). Se reconocen por las palabras funcionales del slug (*the, of, to* frente a *de, la, el*) y no se descargan.
- **Páginas "live" de RPP:** no están en el archivo; entran solo si las trae la recolección diaria.
- **Videos y galerías:** sin texto (< 50 palabras); quedan con `sin_texto=1` (titular sí, cuerpo no).

## Candidatas
1. **Filtro por título.** Términos de `config/terminos_titulo.csv` (El Niño: nino, nina, meganino; oficiales: enfen, senamhi, indeci, cenepred, imarpe; peligros: lluvias, huaicos, inundaciones, calor, emergencia…; mar: anchoveta; salud: dengue). Se comparan como palabras completas tras quitar tildes y pasar a minúsculas, **sin quitar plurales** ("niños" no es "niño"). Se buscan en el slug y, si la vía lo trae, en el título (RPP, El Tiempo).
2. **Más candidatas (`config.CANDIDATAS`),** porque la prueba del filtro mostró que el título solo pierde demasiado (ver validación):
   - `secciones` (RPP, Exitosa): además, todas las notas de secciones de noticias; se excluyen deportes, espectáculos, música, cine, TV, videos y publirreportajes (`config/secciones_excluidas.csv`).
   - `todo` (El Tiempo): todas (la API lo hace barato).
   - `titulo` (Andina): sus direcciones no dicen la sección. Se queda en el título si su pérdida es ≤ 20 %; si no, `todo` (~37 mil páginas más).

## "Sobre El Niño"
Reglas automáticas sobre el texto de la nota (`rasgos.py`), sin etiquetado manual:
- **Mención:** "El/del Niño", "Fenómeno (del) Niño", "Niño Costero/Global", "Mega Niño", "La Niña", "ENFEN", respetando mayúsculas (un "niño" no es el fenómeno) y sin contar "Hospital/Instituto/Salud/Día del Niño".
- `nino_en_inicio`: hay mención en el resumen o en las primeras 60 palabras del cuerpo. **No mira el titular**: es la referencia con que se mide lo que pierde el filtro por título.
- `sobre_nino`: `nino_en_inicio` o mención en el titular. Es la que cuenta para el volumen y el análisis.
- `menciona_nino`: alguna mención en cualquier parte (red de citas, control negativo).

La referencia se contrasta con las etiquetas editoriales de RPP (`article:tag`). Las de Exitosa no sirven: en febrero sus `keywords` son el titular reescrito; Andina las mezcla con palabras del título y El Tiempo casi no etiqueta.

## Qué se guarda
| Dónde | Qué | Se versiona |
|-------|-----|-------------|
| `data/raw/noticias/<medio>/lista.csv` | lo descubierto: `medio, id, url, titulo, seccion, fecha_lista, via, http` (incluye números sin nota, para no volver a pedirlos) | no |
| `data/raw/noticias/<medio>/notas.csv`, `enlaces.csv` | lo leído, fila por fila (archivo de trabajo) | no |
| `data/raw/noticias/<medio>/estado.json` | días, meses y páginas ya recorridos; notas sin nota o con error y sus intentos | no |
| `data/processed/noticias/notas.csv` | consolidado del período, sin duplicados, con `fecha_dudosa` | no |
| `data/processed/noticias/enlaces.csv` | enlaces del cuerpo: `medio, id, url, dominio, oficial, comunicado` | no |
| `data/processed/noticias/control_negativo.csv`, `validacion.csv` | muestra del control negativo y resultado de las pruebas | no |
| `docs/noticias/validacion-AAAA-MM-DD.md` | resumen de las pruebas | sí |

Columnas de `notas.csv`: `medio, id, url, via, candidata_por, muestra, titular, resumen, fecha_publicacion, fecha_modificacion, fecha_creacion, fuente_fecha, fecha_dudosa, seccion, etiquetas, terminos_titulo, n_palabras, sin_texto, resumen_en_cuerpo, cuerpo_vs_ld, menciones_nino, menciona_nino, nino_en_inicio, sobre_nino, terminos_cuerpo, actores, comunicados, magnitudes, n_enlaces, n_enlaces_oficiales, sha1_cuerpo, recolectado`. Listas unidas con `|`, booleanos 1/0, fechas ISO en −05:00.

- **Nunca el cuerpo** ni el HTML crudo (contiene el cuerpo). Titular y resumen se guardan en local para el análisis y no se publican (README, "Despliegue").
- No se versiona nada nuevo en `data/`. Cuando la app necesite notas, se decidirá un subconjunto versionable (titular, medio, fecha, enlace y métricas).
- **La etapa de NLP (embeddings, NLI, tópicos, emociones) tendrá que volver a leer los cuerpos** del corpus final con `Medio.leer`, porque no se guardan. `sha1_cuerpo` dice si una nota cambió entre las dos lecturas.

## Rasgos
- `actores`: menciones de ENFEN, Senamhi, Indeci, IMARPE, DHN, IGP, ANA, Cenepred y PCM (`config/actores.csv`).
- `magnitudes`: débil, moderada, fuerte, muy fuerte o extraordinaria en frases que nombran El Niño y hablan de magnitud, intensidad o categoría (escala de `radar.oficial.vocabulario`).
- `comunicados`: `id:nivel` del comunicado del ENFEN que la nota enlaza o cita, cruzado con `data/oficial/comunicados.csv`:
  1. `enlace`: enlaza el PDF del comunicado (`enfen.imarpe.gob.pe/download/<slug>` o un PDF cuyo nombre lo identifica).
  2. `numero`: cita su número ("Comunicado Oficial N° 09-2026").
  3. `proximo`: dice "el próximo comunicado será el <fecha>", que se cruza con `proximo_anunciado` del comunicado anterior.
  4. `informe`: enlaza el informe técnico del ENFEN emitido entre 0 y 3 días antes de un comunicado.
- Enlaces del cuerpo sin botones de compartir; `oficial` = dominio `gob.pe`.

## Fechas y duplicados
- `fecha_publicacion` = `datePublished` del JSON-LD de la nota (en El Tiempo, `date_gmt` de la API, que coincide), en −05:00. Nunca `lastmod`. Sin `datePublished` la página no se toma como nota.
- `fecha_dudosa`: Andina vuelve a fechar notas antiguas (la 1056807, de dic-2025, aparece del 23-oct) y RPP vuelve a publicar. Se marca, sin corregir, si la fecha queda más de 7 días después de la mediana de las 20 notas de Andina de número más cercano, o de la `dateCreated` de RPP. Se usa para excluir esas notas del estudio de eventos.
- Clave (`medio`, `id`), la misma de `data/urls/`: cada nota se descarga una sola vez aunque venga del histórico y de la recolección diaria. El consolidado deja solo las de 2026.

## Pruebas de viabilidad (criterios fijados antes de correrlas)
| Prueba | Pasa si | Referencia | Si no pasa |
|--------|---------|------------|------------|
| Filtro por título | Con solo el título se pierde ≤ 20 % de las notas con El Niño en su inicio (recolección diaria); con las candidatas de `config.CANDIDATAS`, también ≤ 20 % en la recolección diaria **y** en el histórico | `nino_en_inicio` (independiente del título), contrastado con las etiquetas de RPP (≥ 0,90) | Ampliar candidatas (README) |
| Cobertura del archivo de RPP | ≥ 95 % de las notas de referencia están en el archivo de su `datePublished` (±1 día); "live" aparte | Copias de 2026 de `/sitemap/news` en Wayback y el sitemap de noticias de la recolección diaria | RPP parcial, declarado |
| Volumen | ≥ 400 notas `sobre_nino` del 1-ene al 24-oct entre los 4 medios | Reglas de arriba | Sumar secciones o términos; tópicos solo globales |
| Control positivo | ≥ 20 notas de Andina con nivel `enlace` | `comunicados.csv` | Sumar `numero` (README); `proximo` e `informe` son extensiones aprobadas |
| Calidad | 100 % de candidatas con titular y fecha; 0 duplicados; ≥ 95 % con ≥ 40 % de las palabras del resumen en el cuerpo; en RPP, ≥ 95 % con ≥ 90 % del `articleBody` | Metadatos del propio medio | Revisar el selector del cuerpo de ese medio |

**Cómo se mide la pérdida.** Las notas se separan en grupos como los ve el histórico: las que pasan el filtro por título, las de secciones de noticias, las de secciones excluidas y, en Andina y El Tiempo, el resto. Las del filtro se leen todas; de los demás grupos se lee una muestra al azar con semilla fija (`SEMILLA_MUESTRAS`): 300 de secciones de noticias, 150 de excluidas, 400 del resto en la recolección diaria, y 15 por mes y grupo en el histórico. La cantidad de notas con El Niño de cada grupo se estima con su proporción en la muestra; la pérdida es la parte que queda en los grupos que no se descargan. Intervalo de confianza bootstrap al 95 % (2.000 remuestreos dentro de cada grupo).

**Control negativo.** Del consolidado, por medio y repartidas por mes: hasta 100 notas que no mencionan El Niño ni tienen términos del filtro en el cuerpo (`otros_temas`) y, solo como informativo, hasta 100 que no mencionan El Niño pero sí lluvias, calor u otro término (`cercano`), porque los negativos de deportes o espectáculos son fáciles e inflan el AUC.

## Ética y errores
- `radar.comun.http.Cliente` restringido al host de cada medio: user-agent honesto, `robots.txt` con el verificador propio (RPP prohíbe `/tema*`, que nunca se pide), 1 petición por segundo por host, reintentos ante errores de red y 429/5xx.
- 403 o host suspendido: ese medio se detiene en esta ejecución (no se eluden bloqueos) y los demás siguen. 404: la nota queda como inexistente y no se vuelve a pedir. Otro error: se reintenta en las siguientes ejecuciones, hasta 3.
- Las redirecciones de Andina y Exitosa se piden sin seguirlas y se acepta el destino solo si es una nota del mismo host con el mismo número.

## Limitaciones declaradas
La referencia "El Niño en el inicio" es una regla, no una etiqueta: puede contar notas donde El Niño es secundario. La pérdida de la recolección diaria se mide en temporada alta (octubre), y por eso se mide también en el histórico. Las páginas "live" de RPP no tienen histórico. Las notas re-fechadas se marcan, no se corrigen. El cuerpo se vuelve a leer en la etapa de NLP y puede haber cambiado.
