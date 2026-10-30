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

## Limitaciones declaradas
- Solo RPP publica `articleBody` en su JSON-LD; en Andina, Exitosa y El Tiempo no hay una referencia externa del cuerpo y la pérdida se mide contra el propio contenedor (reglas de línea) y la extracción anterior (bloques quitados, informativo).
- RPP publica a veces en el `articleBody` párrafos que no están en la página; se valida contra la página visible.
- Las uniones que el medio ya escribió pegadas ("contenido.En", "2.Sección") siguen en el texto; las resuelve el partidor de frases de la capa siguiente.
- Los selectores dependen de la plantilla de cada sitio (revisada el 28-oct-2026); si cambia, la validación lo detecta.

## Pendiente
`data/processed/noticias/notas.csv` y `enlaces.csv` se calcularon con la extracción anterior. Se recalculan una sola vez al final, con el flujo completo ya validado, para que todo sea coherente con la metodología.
