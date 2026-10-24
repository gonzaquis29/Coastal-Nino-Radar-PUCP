# Validación del corpus oficial (24-oct-2026)

Peticiones reales con el user-agent del proyecto (1 por segundo por host), copias de Wayback Machine y todos los documentos del período (no una muestra). Respalda las decisiones de [definicion.md](definicion.md). El reporte de cada ejecución queda en `data/oficial/validacion.csv`.

## Resultado de las pruebas de viabilidad
| Prueba | Resultado |
|--------|-----------|
| Descargar los comunicados ENFEN y probar la extracción de fecha, estado y magnitud con reglas | **Pasa** (11 de 11 criterios) |
| Extraer avisos del Senamhi (fecha, tipo, nivel, macro-región) y aplicar el filtro | **No pasa** en 2 de 8 criterios: el acuerdo entre polígono y regla queda en 94,8 % (costa norte) y 94,5 % (costa centro), bajo el 95 % fijado. Se mantiene el polígono como método principal (ver "Desacuerdos") |

Corpus resultante: 19 comunicados (N.° 13-2025 y N.° 01 a 18 de 2026), 44 filas de probabilidad, 125 avisos (79 de temperatura y 46 de precipitaciones; 2 cancelados), 538 aviso-días por macro-región y 834 párrafos (254 del ENFEN, 580 del Senamhi). `data/oficial/` pesa ~0,5 MB; `data/raw/oficial/`, ~100 MB comprimido. Primera ejecución: 1,6 min (ENFEN) y 17,9 min (Senamhi); reconstruir sin descargar, 1,7 min.

## ENFEN
| Criterio | Resultado | Referencia |
|----------|-----------|------------|
| Descargados y extraídos del PDF | 19/19 | — |
| Número y año del PDF = slug | 19/19 | slug de `wpdmpro-sitemap.xml` |
| Fecha de emisión a ±1 día de la página de descarga | 19/19 (N.° 01 y 07 difieren en 1 día) | fecha que publica la página |
| Emisión real a ±1 día de la anunciada en el comunicado anterior | 18/18 (solo 17→18 se corrió un día) | "el próximo Comunicado Oficial será el …"; además prueba que no falta ninguno |
| Estado = el de la página de descarga | 19/19 | HTML de la página |
| Magnitud extraída (vigilancia o alerta) | 18/18 | — |
| Magnitudes del resumen HTML ⊆ las del PDF | 16/16 (3 resúmenes no mencionan magnitud) | resumen HTML |
| Categoría más probable de la tabla ∈ magnitudes mencionadas | 4/4 (N.° 13-16) | tablas de probabilidad del propio comunicado |
| Acuerdo PyMuPDF / pypdf ≥ 0,98 | 19/19 (0,987-0,999) | segundo extractor |
| Frases del resumen HTML en los párrafos (similitud ≥ 0,9) | 265/265 | resumen HTML |
| Párrafos sin URL, encabezado, leyenda ni marca de nota | 240/240 | — |
| Temas (informativo) | 82/82 | frase de apertura de cada sección ("En relación con los recursos pesqueros…") |

Magnitud prevista para la costa (Niño 1+2) en 2026: débil (N.° 01-08), moderada (09-10), fuerte (11-13), extraordinaria (14-18). Estado: Vigilancia (01-02) y Alerta (03-18); "No Activo" en el N.° 13-2025, que rige del 1 al 14-ene.

### Hallazgos
- **El texto completo solo está en el PDF.** La página `/download/<slug>/` trae un resumen (~1.000 caracteres en los N.° 17 y 18). Las entradas del blog (`/AAAA/MM/DD/…`) solo llegan al N.° 13 y no se usan.
- **El `lastmod` no es la fecha de emisión ni del PDF.** El N.° 02 (30-ene) tiene `lastmod` del 5-feb; el N.° 14 (14-ago) tiene `lastmod` del 24-ago con un PDF creado el 14-ago. Se compara el hash del PDF.
- **Los slugs engañan.** `comunicado-extraordinario-enfen-n-02-2025` y `n-04-2025` contienen los Oficiales N.° 03 y 04 de 2025; solo `n-01-2025` es extraordinario (27-feb-2025). El slug de la entrada del blog del N.° 02 dice "alerta", pero era "vigilancia". La identidad sale del PDF.
- **El formato cambió en el N.° 17:** sin la línea "Estado del sistema de alerta:" ni resumen ejecutivo, con titular en mayúsculas y rótulos ("Lluvias:", "Pesquero:").
- Errores corregidos durante la validación: filtrar notas al pie por tamaño de letra (≤ 8) borraba el resumen del N.° 08, que está en letra 8 → se detectan por bloque y posición; las notas "1. https://…" de los N.° 14-15 y los enlaces partidos se colaban; una leyenda tras rótulos de panel ("a b Figura 2.") se colaba; la regla "primera magnitud principal" dependía del orden de las frases (10/20 con el HTML) → `magnitud_max_prevista` + `magnitudes_mencionadas`.
- Los informes técnicos pesan ~17 MB cada uno: fuera del alcance.

## Senamhi
| Criterio | Resultado | Referencia |
|----------|-----------|------------|
| Candidatos con panel de detalle | 127/127 | — |
| Número, nivel, título, emisión, inicio y fin = tabla | 127/127 | tabla `?p=aviso-meteorologico` |
| Nivel máximo de los mapas diarios = nivel de la tabla | 127/127 | tabla |
| Costa norte: polígono y regla coinciden | **312/329 (94,8 %)** | regla de título + departamentos |
| Costa centro: polígono y regla coinciden | **311/329 (94,5 %)** | regla de título + departamentos |
| Avisos sin costa en el título que no tocan estaciones de la costa | 153/153 aviso-días | polígonos oficiales |
| Días de cancelados cubiertos por otro aviso del mismo tipo | 2/2 (425 → 426, 430 → 432) | — |
| Avisos con macro-región por polígono (informativo) | 125/125 | — |

En 121 de 538 aviso-días el nivel en la costa (sobre las estaciones) es menor que el nivel del día: un aviso rojo en la sierra puede ser amarillo o naranja en la costa.

### Desacuerdos entre polígono y regla (35 aviso-días)
Árbitro independiente: el párrafo que el Senamhi escribe para cada día ("El viernes 23 … en la costa norte"). Donde polígono y regla coinciden, el texto también coincide en 304/309 (centro) y 308/310 (norte). Los casos que el texto no resolvía se revisaron con el polígono completo, incluido el nivel 1 (sin aviso).

| Grupo | Casos | Explicación | Acierta |
|-------|-------|-------------|---------|
| La regla nombra una costa que ese día está en nivel 1 en el mapa oficial | 9 (403, 383, 376, 233, 043, 040, 011, 092/3; 109 sus tres días en costa centro) | el título o los departamentos (que incluyen provincias de sierra) nombran la costa, pero el Senamhi no la puso en aviso; a veces el texto menciona lluvias ligeras o temperaturas allí | polígono |
| Ica en avisos titulados "costa sur" o con descripción de costa sur | 7 (368, 088, 061) | el polígono toca estaciones de Ica; el Senamhi la llama costa sur y el README la pone en costa centro | definición (supuesto declarado) |
| Mapa del día sin lista de departamentos | 1 (168/2) | omisión de la fuente; el texto confirma costa norte y centro | polígono |
| Resto | 18 | la regla no ve la costa (descripción con tramos de más o de menos en títulos genéricos, departamentos solo de sierra) y el texto del día da la razón al polígono | polígono |

En ninguno de los 35 falla el polígono. Por eso, frente al respaldo fijado ("macro-región solo por la regla"), se mantiene el polígono como método principal y la prueba se declara **no pasa** sin mover el umbral: el criterio medía acuerdo entre dos métodos, y el desglose muestra que el que falla es el de control. El aviso que se muestra como "vigente en tu zona" sigue el mapa oficial, no el título.

### Hallazgos
- La página de detalle (~1,4 MB) trae todos los avisos vigentes; el del aviso pedido está en `tabs-<número><año>` si está vigente y en `tabs-<b><año>` si no.
- Los mapas por día (`index.php?av=N&nl=nivel&mp=día&fc=año`) listan los departamentos de posible afectación; `nl` es el nivel del día.
- El polígono oficial se obtiene por WFS del GeoServer `idesep.senamhi.gob.pe` (sin `robots.txt`), filtrado a niveles 2-4 (~270 KB por día).
- La columna Nro. de la tabla lleva "(emitido)" antes del inicio y "(vigente)" durante el evento; la tabla del 20-sep (Wayback) frente a la de hoy solo cambió en esos sufijos.
- Avisos de 2025 vigentes el 1-ene: el N.° 469 (temperatura, costa norte) entra al corpus.
- Fuentes descartadas: la ficha de estación (`map_red_graf.php`) pide verificar que no se es un robot → no se usa; Nominatim y Wikidata prohíben esas rutas en su `robots.txt`; las provincias no separan costa de sierra (Huaral, Chincha o Lambayeque tienen distritos de sierra).
- Errores corregidos durante la validación: "COSTA NORTE Y CENTRO" se leía solo como norte (lo detectó una prueba unitaria); un título "COSTA" genérico se resolvía solo con la descripción y fallaba en el aviso 431 (la descripción nombra la costa norte por lluvias de paso) → descripción + párrafos diarios.

## Actualización (simulada con datos reales)
- Cinco copias del `wpdmpro-sitemap.xml` en Wayback (ene-may) y la de hoy: cada comunicado aparece una vez como nuevo; ninguno cambia de `lastmod` entre copias.
- Tabla del Senamhi del 20-sep frente a la de hoy: 60 avisos nuevos, ninguno desaparecido, y solo cambian los sufijos "(emitido)"/"(vigente)" → la comparación los ignora.
- Una segunda ejecución sin cambios en las fuentes no vuelve a descargar los avisos vencidos ni los comunicados con el mismo `lastmod`.

## Derecho de autor
Art. 9.b del D. Leg. 822 en el texto consolidado de WIPO Lex (modificaciones hasta el 7-feb-2026): no son objeto de protección los textos oficiales de carácter legislativo, administrativo o judicial, "sin perjuicio de la obligación de respetar los textos y citar la fuente". Un precedente del INDECOPI (documentos de la SUNAT) aplica el criterio a entidades del Ejecutivo.

## No verificable de antemano
Que el ENFEN o el Senamhi cambien su formato antes del corte. Lo detectan los criterios de cada ejecución (`validacion.csv`) y los respaldos.
