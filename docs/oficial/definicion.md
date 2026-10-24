# Corpus oficial (ENFEN y Senamhi)

Comunicados del ENFEN y avisos meteorológicos del Senamhi, partidos en párrafos, con su vigencia por fecha y macro-región. Lo usan el índice de discrepancia (párrafo oficial más cercano), el estudio de eventos (cada comunicado es un evento), el agente (`estado_vigente`, `buscar_oficial`), el recomendador y las contradicciones sintéticas. Las mediciones que respaldan estas decisiones están en [validacion-2026-10-24.md](validacion-2026-10-24.md).

## Uso
```bash
pip install -r requirements.txt
python src/oficial/corpus.py
```
- `--solo enfen|senamhi`: una sola fuente; los párrafos de la otra se conservan.
- `--sin-descarga`: vuelve a extraer desde `data/raw/oficial/` sin pedir nada (unos segundos).
- `--prueba`: hace todo y muestra el reporte, sin escribir `data/oficial/`.
- Correrlo después de `diario.py` cuando este avise "Nuevo documento del ENFEN", y antes del corte (20-nov). La primera vez tarda ~30 min; las siguientes, pocos minutos.
- Pruebas de las reglas: `python -m pytest tests/`.
- En Python: `from oficial.vigencia import Corpus` → `Corpus().estado_vigente("2026-10-24", "costa_norte")`, `avisos_aplicables(...)`, `comunicados_a_comparar(...)`, `parrafos_vigentes(...)`.

## Alcance
- **ENFEN:** comunicados oficiales y extraordinarios de 2026, más el **N.° 13-2025** (18-dic-2025, "No Activo"), que rige del 1 al 14-ene. Fuera quedan los informes técnicos (~17 MB cada uno, análisis técnico que metería ruido en la búsqueda del párrafo más cercano) y las notas técnicas. El N.° 13-2025 no es evento: los eventos son los de 2026.
- **Senamhi:** avisos de **precipitaciones** (títulos con PRECIPITACIONES o LLUVIA) e **incremento de temperatura** emitidos en 2026 o que siguen vigentes el 1-ene, que caen en costa norte o costa centro (ver "Macro-región"). Fuera quedan la llovizna (6 avisos de llovizna invernal en la costa centro, sin relación con la temporada de lluvias), los vientos, friajes, nevadas y descensos de temperatura. Se presentan como "aviso vigente en tu zona", nunca como causados por El Niño.

## Fuentes
| Fuente | Qué se lee | Para qué |
|--------|------------|----------|
| `data/urls/*.csv` | filas del ENFEN con `/download/comunicado-(oficial\|extraordinario)-*` y filas del Senamhi | lista de documentos |
| `wpdmpro-sitemap.xml` | `lastmod` de cada comunicado | detectar re-subidas y comunicados que falten en `data/urls` |
| `/download/<slug>/` | página de descarga: fecha publicada, estado y resumen | enlace al PDF y referencia para validar |
| PDF del comunicado | texto completo | **manda** sobre el HTML |
| `?p=aviso-meteorologico` | tabla de avisos (Aviso, Nro., Emisión, Inicio, Fin, Duración, Nivel) | lista de avisos y referencia para validar |
| `?p=aviso-meteorologico-detalle&a=<año>&b=<b>` | panel del aviso: título, nivel, emisión, inicio y fin con hora, descripción, un párrafo por día | texto y fechas |
| `mapas/mapa-avisos-meteorologicos/index.php?av=N&mp=día&fc=año` | departamentos de posible afectación por día | regla de respaldo |
| WFS `idesep.senamhi.gob.pe/geoserver/g_aviso` (`view_aviso`, niveles 2-4) | polígono oficial de cada día | macro-región y nivel |

La identidad de un comunicado (tipo, número, año) sale del PDF, no del slug: `comunicado-extraordinario-enfen-n-02-2025` contiene el Oficial N.° 03-2025.

## Comunicados: campos
| Campo | Regla |
|-------|-------|
| `tipo`, `numero`, `anio` | `COMUNICADO (OFICIAL\|EXTRAORDINARIO) ENFEN N° x-AAAA` |
| `fecha_emision` | primera fecha después del número (es la real; el `lastmod` es de re-subidas, hasta 6 días después) |
| `estado` | en los 120 caracteres después del número, contra 5 estados: No Activo, Vigilancia/Alerta de El Niño Costero, Vigilancia/Alerta de La Niña Costera. Cubre el formato con "Estado del sistema de alerta:" (hasta el N.° 16) y el que pone solo el estado (desde el N.° 17) |
| `magnitud_max_prevista` | región Niño 1+2: se parte el texto en frases y cada una se asigna a Niño 1+2 o 3.4 por sus menciones (la que no menciona hereda la anterior); solo cuentan frases de 1+2 con "magnitud", "evento" o "cálidas débiles" y sin lluvias, caudales ni vientos. Es la mayor magnitud que **no** va tras "no se descarta", "podría alcanzar", "pudiendo", "sin embargo" |
| `magnitudes_mencionadas` | todas las de esas frases, incluidas las que "no se descartan". Es la que usa la regla de magnitud del semáforo |
| `plazo` | primer "hasta …" de una frase de Niño 1+2 (texto, no se evalúa) |
| `proximo_anunciado` | fecha de "el próximo Comunicado Oficial … será/se emitirá el …" |
| `titular` | línea en mayúsculas del formato nuevo ("EL NIÑO COSTERO SE EXTENDERÍA …") |
| `fecha_web` | fecha de la página de descarga (control) |

Escalas: Niño 1+2 (ICEN) débil, moderado, fuerte, extraordinario; Niño 3.4 usa "muy fuerte" (tablas de probabilidad de los N.° 13-16). En los "No Activo" la magnitud es la del pronóstico ("condiciones cálidas débiles a partir de abril").

**Tablas de probabilidad** (N.° 13-16): `page.find_tables()` de PyMuPDF; la región sale de las categorías (Extraordinario → Niño 1+2, Muy Fuerte → Niño 3.4).

**Temas** (categorías de interés del README): el rótulo del ENFEN si el párrafo lo trae ("Lluvias:", "Caudales:", "Embalses:" → lluvias; "Temperatura del Aire:" → calor; "Pesquero:" → pesca); si no, palabras clave (`enfen.TEMAS`). En los avisos, el tema es el tipo (precipitaciones → lluvias, temperatura → calor).

## Párrafos del ENFEN
1. Líneas de PyMuPDF (`get_text("dict")`) con su bloque. Se quitan las marcas de nota al pie pegadas ("Costero1", "20266": números con bandera de superíndice o letra < 80 % de la línea) y se repone el espacio entre dos fragmentos separados en la página.
2. Tipo de bloque: **nota** (desde el primer bloque de letra ≤ 9,5 que empieza con número en la parte baja de la página, y las líneas `1. https://…` o con `wpdmdl=`), **tabla** (dentro de una tabla detectada o encabezado de tabla), **leyenda** ("Figura/Tabla/Fuente N.", aunque vaya tras rótulos de panel "a b", y su continuación inmediata) o **texto**. Se descarta todo lo que no es texto, más el encabezado de página (Comisión, Decreto Supremo, "Año de…", URL), la firma y "Para más información".
3. Agrupación: párrafo nuevo si hay espacio vertical > 0,45 de la letra, cambia el tamaño, la línea anterior termina en punto y es corta, empieza una viñeta (•, −) o un rótulo. Entre páginas se une si el anterior no termina en puntuación. Guion al final + minúscula → se une sin espacio.
4. El bloque número/fecha/estado/"RESUMEN EJECUTIVO" pasa a campos. Secciones: `titular`, `resumen` (bajo "RESUMEN EJECUTIVO", con su tamaño de letra), `cuerpo`, `definicion` (la nota al pie que define el estado; está en 14 de 19).
5. `duplicado_de`: el resumen repite el cuerpo; si dos párrafos del mismo comunicado tienen similitud ≥ 0,9 se marca el segundo. ChromaDB indexa sin duplicados.

Los textos se muestran tal cual y citando la fuente: el art. 9.b del D. Leg. 822 (texto consolidado en WIPO Lex, a feb-2026) excluye los textos oficiales administrativos "sin perjuicio de la obligación de respetar los textos y citar la fuente". La limpieza solo quita marcas de nota, encabezados y pies; siempre se enlaza el PDF.

## Avisos: macro-región y nivel
- **Por polígono oficial (método principal).** Por cada día del aviso se pide el polígono por WFS (solo niveles 2-4) y se mira qué estaciones de referencia cubre: 12 de la costa norte (Puente Tumbes, Rica Playa, El Alto, La Esperanza, Mallares, Miraflores, Chulucanas, Morropón, Lambayeque, Reque, Tinajones, Trujillo) y 9 de la costa centro (Huarmey, Huacho, Campo de Marte, Von Humboldt, Cañete, Socsi Cañete, Fonagro Chincha, San Camilo, Palpa). Las coordenadas son del listado oficial de estaciones del Senamhi; **elegirlas como "costa" es un supuesto nuestro**. El nivel de la macro-región ese día es el máximo sobre sus estaciones (puede ser menor que el del aviso: un aviso rojo en la sierra puede ser amarillo en la costa).
- **Regla de respaldo y control** (`metodo=regla` si falta el polígono): los tramos de costa del título (si dice solo "COSTA", los de la descripción y los párrafos diarios) cruzados con los departamentos del mapa del día. Costa norte: Tumbes, Piura, Lambayeque, La Libertad. Costa centro: Áncash, Ica y, para avisos, Lima y Callao.
- **Candidatos:** títulos de precipitación o temperatura que nombran la costa (incluida la costa sur, porque el polígono puede tocar Ica) o un departamento de la costa norte. Los títulos solo de sierra se descargan únicamente como control (solo polígonos): ninguno toca estaciones de la costa.
- Ica queda en costa centro (supuesto del README); el Senamhi la cubre tanto en avisos de "costa centro" como de "costa sur".

## Vigencia
- **ENFEN:** un comunicado rige desde su `fecha_emision` (incluida) hasta el día anterior al siguiente (`vigente_desde`, `vigente_hasta`; el último queda abierto). **El día de emisión** el texto se compara con el nuevo y con el anterior y se queda el más cercano (`comunicados_a_comparar`), porque no se sabe la hora de publicación. Día 0 del estudio de eventos = `fecha_emision`.
- **Senamhi:** un aviso es **aplicable** en la fecha D y macro-región M si no está cancelado, emisión ≤ D ≤ fin y tiene algún día en M. Es `vigente` si D es un día del evento en M y `emitido` si el evento aún no empieza (términos de la propia tabla del Senamhi). Si se solapan varios, se devuelven todos más el nivel máximo por tipo. La vigencia se cuenta por día (los textos tienen fecha); las horas de inicio y fin se guardan.
- **Cancelados:** fuera de la vigencia. En 2026 hubo dos (425 y 430) y ambos tienen un aviso que cubre los mismos días (426 y 432). "EXTENSIÓN/ACTUALIZACIÓN DEL AVISO N" queda en `relacion` y `aviso_relacionado`.
- Macro-regiones de consulta: `costa_norte`, `costa_centro`, `lima` (usa los avisos de costa centro); `otras` y `nacional` no tienen avisos.

## Salida (`data/oficial/`, se versiona)
CSV UTF-8 con saltos LF (fijado en `.gitattributes`), filas ordenadas, listas unidas con `|`, fechas `AAAA-MM-DD` o ISO con −05:00. Se versiona porque la app de Streamlit Cloud se despliega desde GitHub y reconstruye ChromaDB con estos párrafos (descargarlos al arrancar golpearía los sitios del Estado en cada reinicio). Son textos oficiales y datos derivados; nunca el cuerpo de notas. Lo crudo (PDF, páginas, polígonos; ~300 MB) va en `data/raw/oficial/`, que no se versiona.

| Archivo | Columnas |
|---------|----------|
| `comunicados.csv` | `id` (`enfen-2026-18`, `enfen-ext-2025-01`), `tipo`, `numero`, `anio`, `fecha_emision`, `fecha_web`, `vigente_desde`, `vigente_hasta`, `estado`, `magnitud_max_prevista`, `magnitudes_mencionadas`, `plazo`, `proximo_anunciado`, `titular`, `slug`, `url`, `lastmod`, `sha256_pdf`, `fuente_texto` (`pdf`/`html`), `n_parrafos` |
| `probabilidades.csv` | `comunicado_id`, `region` (`nino_1+2`/`nino_3.4`), `periodo`, `categoria`, `probabilidad` |
| `avisos.csv` | `id` (`senamhi-2026-432`), `anio`, `numero`, `b`, `titulo`, `tipo`, `nivel`, `estado` (`emitido`/`vigente`/`vencido`/`cancelado`), `relacion`, `aviso_relacionado`, `emision`, `inicio`, `fin`, `duracion`, `macroregiones`, `metodo_macroregion`, `url` |
| `aviso_dias.csv` | `aviso_id`, `fecha`, `mapa`, `macroregion`, `nivel_dia`, `nivel_macroregion`, `estaciones`, `departamentos`, `metodo` |
| `parrafos.csv` | `id` (`<doc>-p03`), `doc_id`, `fuente`, `orden`, `seccion`, `texto`, `fecha_doc`, `vigente_desde`, `vigente_hasta`, `macroregiones`, `temas`, `duplicado_de`, `sha1` |
| `validacion.csv` | `prueba`, `criterio`, `valor`, `umbral`, `pasa`, `detalle` |

`macroregiones` de un párrafo del ENFEN son las que nombra (vacío = nacional); las de un aviso, las de su polígono. El id de párrafo es estable mientras no cambie el PDF; `sha1` cambia si cambia el texto.

## Actualización
- Se reescriben los CSV desde `data/raw/oficial/` en cada ejecución (determinista): no hay duplicados por construcción y sin cambios no hay diferencias.
- **ENFEN:** se vuelve a descargar si cambió el `lastmod`; solo cambia el corpus si cambió el hash del PDF (el N.° 14 tiene `lastmod` del 24-ago y el PDF es del 14-ago).
- **Senamhi:** se vuelve a descargar un aviso si cambió su fila de la tabla (sin el sufijo "(emitido)"/"(vigente)", que cambia solo), si seguía emitido o vigente, o si la descarga anterior quedó incompleta.
- Estado de descargas: `data/raw/oficial/{enfen,senamhi}/estado.json`.

## Seguridad y errores
- Mismo `Cliente` que `diario.py`: user-agent del proyecto, `robots.txt` con el verificador propio (también para `idesep.senamhi.gob.pe`, que no tiene), 1 petición por segundo por host, reintentos ante 5xx y `Retry-After`. Ante 403 o verificación de robot se detiene y lo reporta.
- Solo se piden direcciones de `enfen.imarpe.gob.pe`, `www.senamhi.gob.pe` e `idesep.senamhi.gob.pe`, sin seguir redirecciones a otros hosts ni enlaces de dentro de los documentos; tope de 30 MB por respuesta; un PDF debe empezar con `%PDF-` y venir como `application/pdf`.
- Nombres de archivo derivados de slugs o números validados (`[a-z0-9._-]`); XML sin entidades externas.
- Escritura atómica (temporal + renombrar). **No se empeora el corpus:** si un documento que ya estaba falla, se conservan sus filas anteriores y se avisa.
- Respaldos: PDF ilegible → resumen HTML (`fuente_texto=html`); sin polígono → regla (`metodo=regla`); sin tabla del Senamhi → última copia guardada; una fuente que falla no detiene la otra. Código de salida 1 solo si fallan las dos.

## Pruebas de viabilidad (criterios fijados antes de correrlas)
Se calculan en cada ejecución y quedan en `validacion.csv`.

**ENFEN — pasa si:** 100 % descargados y extraídos del PDF; número y año = slug; fecha de emisión a ±1 día de la página de descarga; emisión real a ±1 día de la anunciada en el comunicado anterior en ≥ 90 %; estado = el de la página de descarga; magnitud extraída en todos los de vigilancia o alerta; magnitudes del resumen HTML ⊆ las del PDF; categoría más probable de la tabla ∈ magnitudes mencionadas; acuerdo PyMuPDF/pypdf ≥ 0,98 por documento; ≥ 95 % de las frases del resumen HTML en los párrafos (similitud ≥ 0,9); 0 párrafos con URL, encabezado, leyenda o marca de nota. *Si no pasa:* fecha o estado del HTML; magnitud solo de la frase "más probable" y la tabla; otro extractor.

**Senamhi — pasa si:** 100 % de los candidatos con panel de detalle; número, nivel, título, emisión, inicio y fin = tabla; nivel máximo de los mapas = nivel de la tabla; polígono y regla coinciden en ≥ 95 % de los aviso-días por macro-región; ningún aviso sin costa en el título toca estaciones de la costa; los días de cada cancelado los cubre otro aviso del mismo tipo. *Si no pasa:* macro-región solo por la regla y se declara.

## Limitaciones declaradas
Las estaciones de referencia de la costa son una elección nuestra; Ica es ambigua; el nivel por macro-región se mide en esas estaciones, no en todo el territorio; los temas por palabras clave se validan con la frase de apertura de cada sección (una referencia estructural, no etiquetas); la hora de publicación de los comunicados no se conoce; un cambio de formato de las fuentes antes del corte se detecta pero no se puede prever.
