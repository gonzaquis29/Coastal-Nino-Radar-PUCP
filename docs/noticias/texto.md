# Capa 1: texto limpio del cuerpo (28-oct-2026)

**Responsabilidad única:** entregar el cuerpo de cada nota con su estructura de líneas y sin lo que no es la nota. No parte en frases ni decide qué afirma la nota (eso es de las capas siguientes). Vive solo en `radar.noticias.nota`; el cuerpo sigue sin guardarse.

## Problemas medidos
Revisión de la estructura real en 40 notas nuevas (10 por medio), fuera del piloto del índice de discrepancia:

| Medio | Cómo viene el cuerpo | Lo que se colaba |
|-------|----------------------|------------------|
| Andina | Texto en `div` separados con `<br>` (no en `<p>`); el cuerpo real está en `div.linknotas` | Titular repetido, crédito de foto ("ANDINA/…", "AFP"), hora y lugar ("14:11 \| Loreto ene. 30."), "Más en Andina" y "[Lea también: …]", iniciales del editor ("JRA"), anuncios |
| RPP | `<p>` y subtítulos | "Te recomendamos", promociones ("¡Mira RPP en YouTube!", pódcast), reproductor ("Compartir … Share"), videos recomendados, "► otra nota" |
| Exitosa | `<p>` y subtítulos | "Lee también" (`div.rela`), anuncios, código incrustado |
| El Tiempo | `<p>` y subtítulos | "PUEDES LEER ►" en `<blockquote>`; y al revés, se borraban citas textuales |

Además `text_content()` pegaba los bloques ("…enero de 2027.La Comisión…"): 15 uniones por 1.000 palabras en Andina y 13 en RPP. Y los enlaces se tomaban de todo el contenedor, así que los recomendados entraban en `enlaces.csv`.

Los "??" de Andina vienen así en el propio HTML del sitio (pierde sus emojis); no es un error de decodificación.

## Qué hace
1. Quita los bloques que no son la nota con selectores por medio (`FUERA_POR_MEDIO`), los incrustados de redes (tuits, Instagram, TikTok) y los bloques cortos (≤ 80 palabras) que empiezan como enlace a otras notas ("Lea/Lee también", "Puedes leer", "Te recomendamos", "Más en Andina", "►"), o como hora y lugar ("HH:MM |", ≤ 15 palabras). Como se quitan como nodo, sus enlaces tampoco cuentan.
2. En El Tiempo, el `<blockquote>` se quita solo si es un enlace; las citas textuales se conservan. En los otros medios también, salvo los incrustados de redes.
3. Separa una línea en cada bloque y en cada `<br>`; el cuerpo se entrega con saltos de línea (`\n`).
4. Quita líneas de crédito ("ANDINA/Difusión") e iniciales del editor (en mayúsculas, sin confundir "Lima" o "Piura").
5. En Andina, la bajada (subtítulo `h2`, fuera de `linknotas`) va como primera línea del cuerpo: es texto de la nota. En RPP y Exitosa la bajada es la descripción de la página, que ya se lee como resumen.
6. Quita la primera línea solo si es igual al titular (antes se cortaba por prefijo y un titular corto podía comerse letras del cuerpo).

## Validación (`python -m radar.noticias.validar_texto [--semilla S]`)
Cada muestra: 25 notas por medio, nuevas, con su semilla. Compara con la extracción anterior sobre la misma página, pedida una sola vez. Criterios fijados antes de correr:

| Criterio | Pasa si |
|----------|---------|
| Las reglas de línea conservan el texto | ≥ 90 % de las palabras del contenedor sin bloques ajenos (aísla las reglas de línea de los selectores de bloques) |
| Uniones pegadas por la extracción | ≤ 0,5 por 1.000 palabras |
| RPP conserva el `articleBody` | ≥ 95 % de las notas con ≥ 90 % de sus palabras (como la prueba de calidad) |
| Restos de bloques ajenos | 0, con un detector independiente de las reglas de limpieza |

### Resultados, en orden
| Muestra | Resultado | Qué se encontró y qué se corrigió |
|---------|-----------|-----------------------------------|
| 1.ª | No pasa (8 restos) | 4 reales: "[Lea también" de Andina, entre corchetes → corregido. 4 del detector: "compartir" y "YouTube" en la redacción |
| 2.ª | No pasa (RPP 0,8 uniones; 3 restos) | Ninguno de la extracción: 6 uniones ya venían pegadas en el HTML de RPP ("contenido.En"), 2 eran comillas de cierre tomadas por inicio de frase, y los 3 restos, el verbo "compartir" → **se corrigió el instrumento** (cuenta solo las uniones que no están así en el original y que van seguidas de mayúscula; el detector busca frases de interfaz y botones con mayúscula), sin tocar umbrales |
| 3.ª | No pasa (1 resto) | Variante de hora y lugar con agencia ("… (EFE).-") → corregido. Una nota de RPP con 78 % del `articleBody`: los párrafos que faltan están solo en el JSON-LD, no en la página |
| 4.ª | No pasa (2 restos) | Otra variante ("14:11 \| Loreto ene. 30.") → se dejó de perseguir variantes: la hora y el lugar se quitan por su forma (bloque corto que empieza con "HH:MM \|"). Y "► otra nota" de RPP → agregado |
| 5.ª | No pasa (1 resto) | Del detector: "en el poema puede leerse" → el detector busca las frases de interfaz solo al inicio de una línea |
| **6.ª** | **Pasa** | Andina y RPP 0 uniones (antes 14,9 y 14,0 por 1.000 palabras), Exitosa 0 (antes 3,7); reglas de línea 100-102 %; RPP 25/25 con su `articleBody`; 0 restos. El arreglo del detector que admite "¡" (más estricto) se volvió a correr sobre la misma muestra: sigue en 0 |

| Notas sobre El Niño (25 por medio, semilla propia) | **Pasa** | El corpus que usará el NLP. Sin restos ni marcas de enlace en medio de una línea; ninguna nota usó las vías de respaldo. En Andina, 4 de 25 cambiaban su "El Niño en el inicio": 1 porque la bajada había quedado fuera (→ se incluye), 2 que ahora sí cuentan el primer párrafo (antes lo tapaban el titular repetido, el crédito y un anuncio) y 2 en que El Niño estaba solo en el titular o en el pie de foto, que ya no se filtran como inicio. Ninguna deja de ser "sobre El Niño" |
| 7.ª (tras incluir la bajada) | **Pasa** | Todos los criterios; 0 restos |

Con la 6.ª, la 7.ª y la de notas sobre El Niño son 300 notas sin restos: a lo más ≈ 1 % de las notas tendría alguno (regla del tres).

Los instrumentos tienen sus propias pruebas (`tests/noticias/test_validar_texto.py`).

### Efectos (informativos, en las 6 muestras)
- Ninguna nota cambia su "El Niño en el inicio"; "sin texto" no cambia.
- Los enlaces que dejan de contar son todos del propio medio (recomendados, "Lee también") o botones (WhatsApp, reproductor); no se perdió ningún enlace externo u oficial. En RPP bajan de ~230 a ~80 por 25 notas.
- Se recuperan citas textuales: en Exitosa, 32 citas de declaraciones en 25 notas (antes se borraban todos los `<blockquote>`); los tuits se siguen quitando.
- Ningún incrustado ni usuario de redes queda en el cuerpo.

## Resumen sin enlaces a otras notas (28-oct-2026)
Al probar la regla de magnitud con los titulares y resúmenes guardados apareció un error de esta capa en el **resumen** (la validación anterior solo miraba el cuerpo).

**Qué se encontró:**
- El resumen de El Tiempo es el *excerpt* que WordPress arma con las primeras palabras del contenido: el 98 % termina en "[…]".
- WordPress lo arma antes de que se quiten los bloques ajenos. Por eso 1.473 de 4.608 resúmenes (32 %) traían el enlace a otra nota: "PUEDES LEER ► titular ajeno", "Puedes Leer |", "►" y erratas del medio como "PUEDS LEER" o "PUEDES LEER4".
- **Efecto:** 39 de las 343 notas de El Tiempo marcadas "sobre El Niño" (11 %) lo eran solo por ese titular ajeno. Eran notas sobre un ahogado en el Chira, el papa o Jesse Jackson.
- Ningún resumen de Andina, RPP o Exitosa tenía el problema.

**Qué hace:** el resumen se corta donde empieza el enlace y se conserva lo que va antes (`nota.sin_enlace`, marcas en `ENLACE_EN_RESUMEN`). En 1.471 de los 1.473 casos quedan 15 palabras o más de la propia nota. Lo que venía después del titular ajeno también está al inicio del cuerpo, que es lo que mira "sobre El Niño". Se descartaron dos alternativas:
- regenerar el resumen desde el cuerpo, porque copiaría una regla interna de WordPress que no conocemos;
- borrar solo el titular ajeno, porque en un texto plano no se sabe dónde termina.

**Validación** (`python -m radar.noticias.validar_texto --resumen`). Criterios fijados antes de correr:

| Criterio | Pasa si | Resultado |
|----------|---------|-----------|
| Resúmenes guardados con un enlace tras el corte (4 medios, sin red; detector más amplio que el corte) | 0 | 0 |
| Resúmenes que cambian en Andina, RPP y Exitosa | 0 | 0 |
| Muestra nueva de El Tiempo por la API (semilla `resumen-eltiempo`; 40 notas con enlace y 20 sin enlace, sin las vistas ni las reservadas para la capa 3): notas con ≥ 90 % del resumen en el cuerpo limpio | ≥ 95 % | **60/60** |
| Restos de enlaces en el resumen leído | 0 | 0 |

**Pasa a la primera.** Control del instrumento: con el resumen sin cortar, solo 5 de las 40 notas con enlace llegan a ese 90 %; o sea, el criterio sí detecta el problema. Informativo: en la muestra, 1 nota deja de ser "sobre El Niño" ("Calor extremo golpea a viviendas rústicas…", que no nombra a El Niño ni en su titular ni al inicio del cuerpo).

## Titulares ajenos sin rótulo (29-oct-2026)
**Cómo se encontró:** al revisar el recálculo antes de aplicarlo. "Menciona El Niño" cambiaba en 1.220 notas y ningún criterio lo medía. De las 80 que ganaban la mención, 47 (44 de Andina, 3 de RPP) la ganaban por el titular de otra nota dentro del cuerpo: "Credicorp destaca anuncio del MEF… ante fenómeno El Niño" aparecía en 4 notas distintas.

**Qué es:** un bloque cuyo único texto es un enlace a otra nota del mismo medio:
- en Andina, un `a.ApplyClass` suelto bajo "Más en Andina", que sí se quitaba como rótulo, o un enlace que envuelve un `div`;
- en RPP, tarjetas `article.news` ("Lo último en…") dentro del cuerpo.

En una muestra de diseño (60 notas de Andina y 59 de RPP, semilla `fuga-enlaces-29oct`) lo tenían 4 notas de Andina (~7 %) y 1 de RPP, con una lista de 10. Entraban al cuerpo y a `enlaces.csv`. Los enlaces dentro de una frase ("…la cumbre organizada por la Contraloría…") no son fuga.

**Qué hace** (`nota._sin_titulares_ajenos`, después de los bloques ajenos): se quita el bloque más grande cuyo texto entero, sin signos de lista, es el de un enlace a otra nota del mismo medio que cumple:
- tiene 4 palabras o más (`MIN_PALABRAS_TITULAR_AJENO`);
- empieza como un titular: mayúscula, cifra o signo de apertura (`EMPIEZA_COMO_TITULAR`).

Se quita como nodo, así que su enlace tampoco cuenta. Se conservan los enlaces dentro de una frase, los enlaces a otros sitios (gob.pe), las anclas cortas ("Ver aquí") y los enlaces a la misma nota. En memoria, la lectura devuelve además `titulares_ajenos`, los textos quitados, y `cuerpo_con_ajenos`, el cuerpo como salía antes, que el recálculo usa para separar esta causa de una edición.

**Validación.** Criterios fijados antes de correr:

| | Criterio | Pasa si |
|---|---|---|
| V1 | Se quitan las 47 fugas conocidas y las 5 de la muestra de diseño | 100 % |
| V2 | Muestra nueva: de los bloques quitados, los que son el titular de la nota enlazada (≥ 80 % de sus palabras en ese titular, tomado de `notas.csv` o de su página) | ≥ 95 % |
| V3 | Líneas del cuerpo previo que faltan en el nuevo y no son un titular quitado | 0 |
| V4 | Notas de Exitosa y El Tiempo que cambian | 0; si no, caso por caso |
| V5 | `validar_texto` con semilla nueva | sus criterios pasan |

Resultados, en orden (cada muestra sin las notas vistas ni las reservadas para la capa 3, y registrada después):

| Muestra (semilla) | V1 | V2 | V3 | V4 | Diagnóstico |
|---|---|---|---|---|---|
| 1.ª `titulares-ajenos-v-29oct` (150 de Andina, 150 de RPP, 40 de Exitosa, 40 de El Tiempo) | 52/52 | **5/6, no pasa** | 27, mal medido | 0 | **Falla la regla:** un enlace que envolvía la continuación de una frase partida en dos bloques ("… la raza canina perro" / "pastor Chiribaya como patrimonio…"). Se agrega `EMPIEZA_COMO_TITULAR`. **Falla el instrumento en V3:** contaba enlaces que ya quitaban otras reglas; se mide como líneas del cuerpo previo que faltan en el nuevo |
| 2.ª `titulares-ajenos-v2-29oct` (300 de Andina) | 52/52 | **50/53 = 0,943, no pasa** | 0 de 7.380 | 0 | **Falla el instrumento:** los 3 son titulares ajenos de verdad, cuyo titular el medio editó después ("Confiep respalda…" → "Gremios empresariales respaldan…"); uno se contaba dos veces (tarjeta para móvil y para escritorio), y no se decodificaban entidades (`V&oacute;ley`). Se corrige: también vale el *slug* de la URL enlazada, que lleva el titular original; un bloque por nota; entidades decodificadas |
| 3.ª `titulares-ajenos-v3-29oct` (igual que la 2.ª) | 52/52 | **22/22** | 0 de 7.265 | 0 | Pasa |
| V5: `validar_texto --semilla texto-ajenos-29oct` | | | | | Pasa en los 4 medios; 0 restos de bloques ajenos |

Los umbrales no se movieron. La regla se corrigió una vez (después de la 1.ª) y el instrumento dos.

## Recomendados sin cerrar en RPP (31-oct-2026)
**Cómo se encontró:** después de aplicar el recálculo, la coincidencia de RPP con su `articleBody` bajó de 99,97 % a 99,77 %. Detrás había dos causas distintas.

**1. El instrumento.** El `articleBody` pega los ítems de lista sin espacio ("HBO Max**The** Office", "Perú**Partido**"). El cuerpo viejo venía pegado igual y coincidía por casualidad; el cuerpo limpio los separa. `proporcion_en_cuerpo(..., pegadas=True)`, que solo se usa para `cuerpo_vs_ld`, cuenta también la unión de dos palabras seguidas del cuerpo. **I1** (muestra nueva `instrumento-articlebody-i1-31oct`, 300 notas de RPP): cada nota que siga bajo 0,9 debe ser una pérdida real. Pasa: quedaron 0 bajo 0,9. Es un pase casi vacío, y se declara así.

**2. La regla.** En algunas notas el HTML de RPP no cierra `article__block-list` ni el bloque "Te recomendamos" después de la última tarjeta. El resto de la nota queda dentro del bloque (y a veces la caja del Rotafono, los tags y la barra lateral `column-fixed`), y al quitar el bloque se perdía la prosa. Prevalencia en una muestra de diseño (`recomendados-mal-cerrados-31oct`, 950 notas): 3 de 150 del Rotafono; 0 de 300 del resto de RPP; 0 de 300 de Andina y 0 de 200 de Exitosa. El detector de esa medición falló primero: descartaba los párrafos con un `<article>` como ancestro, y en RPP toda la página lo tiene. Se corrigió y se volvió a medir la misma muestra (es de diseño, sin umbral).

**Qué hace** (`nota._fuera_de_listas_sin_cerrar`, antes de quitar los bloques de RPP): lo que sigue a la última tarjeta (`article__block-item`) dentro de una lista se saca del bloque más externo y se deja justo después; luego pasan las reglas de siempre. A lo que se quita en RPP se suman la caja del Rotafono, `article__follow` y `column-fixed`. Para un bloque bien cerrado no cambia nada. No usa el `articleBody`, que es la referencia de la validación.

**Validación.** Criterios fijados antes de correr:

| | Criterio | Pasa si |
|---|---|---|
| C1 | En las notas donde rescata algo, `cuerpo_vs_ld` sube; y queda ≥ 0,9 | 100 %; ≥ 95 % |
| C2 | Líneas agregadas con < 50 % de sus palabras en el `articleBody` | 0 |
| C3 | Líneas quitadas que son texto de la nota (en el `articleBody`) | 0 |
| C4 | `validar_texto` con semilla nueva | sus criterios pasan |
| C5 | Andina, Exitosa y El Tiempo | sin cambios (pruebas con HTML sintético) |

| Muestra (semilla) | C1 | C2 | C3 | Diagnóstico |
|---|---|---|---|---|
| 1.ª `recomendados-sin-cerrar-c-31oct` (300 del Rotafono, 300 del resto) | 2/2 suben, 2/2 ≥ 0,9 | 0 | **280, no pasa** | **Falla el instrumento:** las 280 son rótulos ("Hablar con Rotafono" 263, "RPP TV", "Únete a nuestro canal en WhatsApp", "Cuéntanos qué está pasando", "Más sobre…"), que la regla quita bien. Contar palabras no sirve en líneas tan cortas. Se mide si la línea está entera y seguida en el `articleBody` |
| 2.ª `recomendados-sin-cerrar-c2-31oct` (las 449 del Rotafono que quedaban, 300 del resto) | 2/2, 2/2 | 0 | **1, no pasa** | **Falla el instrumento:** "Gobierno", la sección de una tarjeta de "Lo más leído" en la barra lateral; una sola palabra aparece en cualquier nota. Se exigen ≥ 4 palabras, como un titular ajeno |
| 3.ª `recomendados-sin-cerrar-c3-31oct` (400 del resto; el Rotafono ya estaba agotado) | sin casos | 0 | **0** | Pasa C2 y C3 |
| C4: `validar_texto --semilla texto-recomendados-31oct` | | | | Pasa en los 4 medios; 0 restos |

Los umbrales no se movieron. La regla no se corrigió; el instrumento de C3, dos veces. C1 pasa en las 4 notas con rescate de las dos primeras muestras: son pocas, porque el problema es raro (~2 % del Rotafono). De paso, la regla quita el botón "Hablar con Rotafono", que estaba en el cuerpo de casi todas las notas del Rotafono.

## Fecha suelta de Andina (1-nov-2026)
**Problema.** Todas las notas de Andina terminaban con la línea `Publicado: 21/10/2026`. Es un texto suelto tras un `<br />`, al final de `div.linknotas` y después de los créditos. El detector independiente no la buscaba, y apareció en el TF-IDF: `publicado` era el segundo término de Andina, presente en 1.192 de sus 1.192 notas sobre El Niño ([../nlp/tfidf.md](../nlp/tfidf.md)).

**Corrección.** Se quita toda línea que sea solo `Publicado: d/m/aaaa` (`nota.FECHA_DE_PUBLICACION`). El lector entrega también `cuerpo_con_fecha`, el cuerpo como lo sacaba el código anterior, para el recálculo; `cuerpo_con_ajenos` y `cuerpo_sin_rescate` también conservan la línea. El detector independiente (`RESTOS`) ahora busca `^Publicado:`.

**Validación** con dos semillas nuevas, de 100 notas cada una (`texto-limpio-fecha-1nov` y, después de ampliar el detector, `texto-limpio-fecha-1nov-b`): **pasa.** Las reglas de línea conservan del 100 al 101,9 % del texto, no hay uniones pegadas y quedan 0 restos.

**Efecto.** Cambia el cuerpo y el sha1 de todas las notas de Andina, pero no las menciones, las magnitudes, "sobre El Niño" ni los enlaces. Una línea con solo la fecha no tiene nada de eso, y además va al final, fuera de las 60 primeras palabras. Va al recálculo final ([recalculo.md](recalculo.md#cuarta-corrección-fecha-de-andina-1-nov)).

## Limitaciones declaradas
- Solo RPP publica `articleBody` en su JSON-LD; en Andina, Exitosa y El Tiempo no hay una referencia externa del cuerpo y la pérdida se mide contra el propio contenedor (reglas de línea) y la extracción anterior (bloques quitados, informativo).
- RPP publica a veces en el `articleBody` párrafos que no están en la página; se valida contra la página visible.
- Las uniones que el medio ya escribió pegadas ("contenido.En", "2.Sección") siguen en el texto; las resuelve el partidor de frases de la capa siguiente.
- Los selectores dependen de la plantilla de cada sitio (revisada el 28-oct-2026); si cambia, la validación lo detecta.

## Pendiente
`notas.csv` y `enlaces.csv` se recalcularon con el texto limpio el 31-oct ([recalculo.md](recalculo.md)), antes de la regla de recomendados sin cerrar. Las notas de RPP se vuelven a recalcular con ella ([pendientes.md](../pendientes.md)).
