# Red social de audiencias en YouTube: definición (aprobada el 22-nov-2026) y resultados

Base: README (fila 7, pregunta 6, "Evaluación sin etiquetado manual") y Y3 ([../youtube/definicion.md](../youtube/definicion.md)). Los criterios se fijan aquí antes de calcular comunidades ni nulos y no se cambian con los resultados. Construida y medida el 22-nov (sección 6).

- **Lo que se miró antes:** solo conteos y tamaños, además de una modularidad de Louvain con el peso crudo (Q 0,114), que se calculó en la primera exploración. No se calculó ningún nulo ni la modularidad con el peso de la definición. Se declara.
- **Corrección de pendientes:** allí dice "co-mención en los comentarios", pero el README define una red por **comentaristas compartidos**. La co-mención tampoco se puede hacer: las `@menciones` se reemplazan por marcadores al guardar.

## 1. Lo que muestran los datos del corte (22-nov)

| Dato | Valor |
|---|---|
| Comentarios con autor de videos que pasan el filtro | 23.813 (17.394 principales y 6.419 respuestas) en 903 videos |
| Autores seudonimizados | 16.298; **1.468 (9 %) comentan en 2 canales o más** |
| Red canal–canal, sin filtros | 153 canales y 1.171 aristas; el componente mayor tiene **151** (Y3) |
| Aristas de un solo autor compartido | 622 de 1.171 (53 %) |
| Autores por canal en el componente | p10: 2; p25: 5; mediana: 19; máximo: 2.712 (un medio) |
| **El dueño comenta en su canal** | 96 canales comentan en sus propios videos (397 comentarios) y 6 veces en otros canales. Se reconocen porque su seudónimo coincide con el del id del canal |
| Medios en la red | 10, con 2.712, 592, 531, 464, 183, 104, 32, 10, 6 y 5 autores |
| Cruce con medios en los "otros" | Mediana 0,08 y p90 0,36; 42 de 139 en 0. **El 74 % del cruce es con el medio más grande** |
| País de los "otros" | PE 74, sin país 26, ES 11, US 7, BR 7, CL 5 |
| Backbone hipergeométrico (FDR 5 %) | 40 aristas y un componente de 18 |
| Con **≥ 5 autores por canal** | Componente de 117 (106 otros, 10 medios, 1 oficial) |
| "Otros" con ≥ 10 autores y cercanía medida | 82 (29 con ≥ 3 videos) |

Consecuencias:
1. **Los comentarios del dueño no son audiencia.** Se quitan los comentarios cuyo autor es un canal de la muestra.
2. **Un canal con 2 autores entra a la red por un solo comentarista,** y su cruce con medios solo puede valer 0, 0,5 o 1. Un canal es nodo si tiene **≥ 5 autores**, y entra a la pregunta 6 si tiene **≥ 10**. Con esos cortes, el componente queda en 117 canales y R1 sigue pasando.
3. **El peso crudo mide el tamaño.** Se normaliza (coseno de Salton), y todo se compara con un **nulo que conserva la actividad** de autores y canales.
4. **El backbone estricto deja 18 canales:** la significancia se prueba sobre la estructura completa, no arista por arista.
5. **El "cruce con medios" es casi el cruce con un solo medio** (74 %), y depende del tamaño del canal. Por eso la pregunta 6 usa el **cruce excedente**, el observado menos el esperado en el nulo, y se repite sin el medio más grande.
6. **Hay canales de varios países.** Una comunidad puede ser solo "los canales de España". Por eso las comunidades se describen también por país.
7. **La pregunta 6 tiene poca muestra:** 82 canales dan un IC de ±0,2 para un Spearman. Si el IC incluye el 0, se dice "sin asociación medible", no "sin asociación".

## 2. Mapa de enfoques

| Enfoque | Problema | Decisión |
|---|---|---|
| A. Proyección canal–canal con el peso crudo (README) | Dominada por el tamaño de los canales | Se reporta, pero no decide |
| B. **Proyección con el peso normalizado** (coseno de Salton: compartidos / √(autores_a · autores_b)) | Una arista entre canales chicos pesa mucho: se compensa con el mínimo de 5 autores | **Base** |
| C. Backbone por significancia de cada arista (hipergeométrica o filtro de disparidad) | Deja 18 canales | Robustez informativa (R8) |
| D. Análisis bipartito directo (modularidad de Barber) | Sin implementación estándar en `networkx`; caro de validar en 5 días | Descartado |
| E. Red video–video | 903 videos, más dispersa | Descartado |
| F. Red autor–autor o de respuestas | Trata de personas, no de audiencias; roza la privacidad | Descartado |
| G. Co-mención en los comentarios | Las menciones no se guardan | Imposible |
| H. Co-mención de actores en noticias (respaldo del README) | Solo hacía falta si Y3 no pasaba | No se usa |

**Comunidades:** Louvain (`networkx`, con semilla) sobre B. Rival: propagación de etiquetas, como control de estabilidad.

**Modelo nulo (README: "red aleatoria con los mismos grados"):** se **baraja la red bipartita autor–canal conservando los grados de ambos lados** (curveball), y se proyecta igual: sin los dueños, con el mismo mínimo de autores (curveball conserva los grados, así que son los mismos canales), el mismo peso y el componente mayor. El nulo de configuración sobre la proyección no sirve: la proyección ya hereda los grados de la bipartita y saldría estructura falsa. Como Louvain maximiza Q también en una red al azar, se compara el **Q máximo observado con el Q máximo de cada nulo**.

## 3. Definición

1. **Comentarios:** principales y respuestas de los videos que pasan el filtro, **sin los del dueño de algún canal de la muestra**.
2. **Nodos:** canales con **≥ 5 autores distintos**. **Aristas:** al menos un autor compartido. **Peso:** coseno de Salton (el conteo crudo se guarda también). Se usa el componente mayor.
3. **Comunidades:** Louvain con resolución 1 y semilla fija; modularidad ponderada Q sobre el componente mayor. El rival de R3 es la propagación de etiquetas asíncrona y ponderada (`asyn_lpa_communities`), con semilla.
4. **Centralidad por tipo** (nunca por canal): fuerza, PageRank y betweenness ponderados (con distancia = 1 / peso), como mediana de medios y de otros. Los oficiales (1 en la red) no se resumen.
5. **Cruce excedente con medios** (pregunta 6). Los medios son los nodos de tipo medio. Para cada canal "otros" del componente mayor con ≥ 10 autores y al menos un video con cercanía, es la proporción de sus autores que también comentan en algún medio, menos la media de esa proporción en los 500 nulos. Se cruza con la **cercanía media del canal** a lo oficial: la media del coseno de sus videos con cercanía, de `engagement-variables`, que cubre los 1.609 videos del modelo (no entran los publicados después del 8-nov). El signo no se fija antes: el valor p es de dos colas. Un Spearman negativo quiere decir que los canales más alejados de lo oficial comparten más audiencia con los medios.
6. **Asortatividad de la cercanía:** si los canales que comparten audiencia tienen una cercanía parecida. Es la correlación de Pearson, ponderada por el peso de Salton, entre la cercanía de los dos extremos de cada arista (contada en ambos sentidos), solo con las aristas cuyos dos extremos tienen cercanía. Se compara con 1.000 permutaciones de la cercanía entre esos nodos.

## 4. Criterios fijados antes

| Id | Criterio | Umbral | Si no pasa |
|---|---|---|---|
| R1 | Componente mayor con la definición (≥ 5 autores, sin los dueños) | ≥ 30 canales | Se vuelve al respaldo de co-mención (README) |
| R2 | **Comunidades reales:** Q de Louvain observado frente al Q de Louvain de 500 redes nulas (curveball) | Q observado > p95 del nulo | Se informa que no hay comunidades más allá de la actividad de autores y canales; no se dibujan |
| R3 | **Estabilidad:** NMI de Louvain frente a la propagación de etiquetas, y mediana del NMI entre 10 semillas de Louvain | ≥ 0,50 en ambos | Las comunidades se reportan como inestables; solo cuenta Q |
| R4 | **Robustez sin autores muy activos** (más de 10 canales): R1 y R2 repetidos | Ambos pasan | Se declara que la estructura depende de pocos autores |
| R5 | **Pregunta 6:** Spearman entre la cercanía media y el cruce excedente con medios (otros con ≥ 10 autores) | Informativo; se afirma una asociación solo si el IC 95 % (bootstrap por canal) no incluye el 0 | Se dice "sin asociación medible" |
| R6 | R5 sin el medio más grande, y R5 solo con los canales de ≥ 3 videos con cercanía | Informativo | Si cambia el signo, R5 no se interpreta |
| R7 | Asortatividad de la cercanía frente a 1.000 permutaciones | Informativo; valor p de dos colas | — |
| R8 | Composición de cada comunidad por tipo y por país, y cuántas aristas del backbone (FDR 5 %) quedan dentro de una misma comunidad | Informativo | — |

- **Comunicación:** solo agregados por tipo y por comunidad. Ningún canal "otros" se nombra; se seudonimizan. Los medios y el oficial tampoco se señalan uno por uno (CLAUDE.md).
- **Límites declarados:**
  - Es una red de **audiencias que comentan**; quien solo mira no aparece.
  - Los comentarios llegan hasta 10 páginas por video, así que los videos con muchos comentarios están truncados.
  - La cercanía de un canal es la de sus videos sobre El Niño, no la de todo el canal.

## 5. Cómo se correría (cuando se apruebe)
- **Comando:** `python -m radar.redes.youtube`, sin red. Solo lee con `radar.youtube.almacen`, toma la cercanía de las variables del modelo de engagement y necesita la sal (`RADAR_YOUTUBE_SAL`) para reconocer a los dueños.
- **Salidas:** por canal, `data/processed/youtube/AAAA-MM-DD_red-canales.csv`, con seudónimos, que vence con los datos de YouTube. Los agregados, `red/youtube-validacion.csv` y `red/youtube-comunidades.csv`, sin ids.
- **Ejecución:** los 500 nulos corren en paralelo (núcleos − 1), con avance, tiempo estimado y semillas fijas.

## 6. Resultados (22-nov-2026)

`python -m radar.redes.youtube`: 1.000 nulos en 0,9 min con 19 procesos. Se quitaron 403 comentarios de dueños; quedaron 139 canales con ≥ 5 autores y 15.998 autores.

| Id | Resultado | Umbral | |
|---|---|---|---|
| R1 | Componente de **117 canales** y 1.097 aristas (106 otros, 10 medios, 1 oficial) | ≥ 30 | **Pasa** |
| R2 | Q = **0,241**, frente a un nulo con media 0,205, p95 0,230 y máximo 0,254; 8 comunidades | > p95 | **Pasa, por poco** |
| R3 | NMI con la propagación de etiquetas: **0,185**; mediana entre 10 semillas de Louvain: 0,766 | ≥ 0,50 en ambos | **No pasa** |
| R4 | Sin los 7 autores de más de 10 canales: componente de 117 y Q de 0,274 frente a un p95 de 0,249 | Ambos pasan | **Pasa** |
| R5 | Spearman de la cercanía con el cruce excedente con medios: −0,059 (IC −0,291 a 0,176; n = 82) | IC sin el 0 | Sin asociación medible |
| R6 | Sin el medio más grande: −0,123 (IC −0,353 a 0,106). Con ≥ 3 videos: **+0,536** (IC 0,227 a 0,731; n = 29) | Mismo signo | **Cambia el signo: R5 no se interpreta** |
| R7 | Asortatividad de la cercanía: **0,076** (valor p de dos colas 0,007; 113 canales) | Informativo | Débil pero distinta del azar |
| R8 | 27 de las 37 aristas del backbone quedan dentro de una comunidad (23 canales) | Informativo | — |

**Por tipo (medianas):** los medios tienen 143,5 autores, fuerza 0,367 y PageRank 0,0085; los otros, 37 autores, fuerza 0,201 y PageRank 0,0063. La intermediación es parecida (0,005 y 0,006). El único oficial no se resume.

**Comunidades por país:** de las 8, la tercera (21 canales) tiene 17 de otros países, con España como principal, y otra (9 canales) tiene a Argentina como principal. Las de Perú concentran a los medios (5, 2, 1 y 2).

**Lectura:**
- **Hay estructura de audiencias más allá del azar** (R2 y R4), pero es débil (Q 0,24 frente a 0,21) y **la partición no es estable** entre métodos (R3). Por eso no se dibujan comunidades como grupos firmes: se informa la modularidad y que una parte de la estructura es **por país** (R8).
- **La pregunta 6 no tiene respuesta firme.** Con todos los canales no hay asociación; el signo cambia al restringir a los canales con ≥ 3 videos (+0,54, n = 29). Se declara como resultado no concluyente.
- **Los canales que comparten comentaristas tienen una cercanía con lo oficial apenas más parecida** (R7, 0,076). Es una asociación débil.

