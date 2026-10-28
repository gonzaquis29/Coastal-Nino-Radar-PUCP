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
5. Quita la primera línea solo si es igual al titular (antes se cortaba por prefijo y un titular corto podía comerse letras del cuerpo).

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

Los instrumentos tienen sus propias pruebas (`tests/noticias/test_validar_texto.py`).

### Efectos (informativos, en las 6 muestras)
- Ninguna nota cambia su "El Niño en el inicio"; "sin texto" no cambia.
- Los enlaces que dejan de contar son todos del propio medio (recomendados, "Lee también") o botones (WhatsApp, reproductor); no se perdió ningún enlace externo u oficial. En RPP bajan de ~230 a ~80 por 25 notas.
- Se recuperan citas textuales: en Exitosa, 32 citas de declaraciones en 25 notas (antes se borraban todos los `<blockquote>`); los tuits se siguen quitando.
- Ningún incrustado ni usuario de redes queda en el cuerpo.

## Limitaciones declaradas
- RPP publica a veces en el `articleBody` párrafos que no están en la página; se valida contra la página visible.
- Las uniones que el medio ya escribió pegadas ("contenido.En", "2.Sección") siguen en el texto; las resuelve el partidor de frases de la capa siguiente.
- Los selectores dependen de la plantilla de cada sitio (revisada el 28-oct-2026); si cambia, la validación lo detecta.

## Pendiente
`data/processed/noticias/notas.csv` y `enlaces.csv` se calcularon con la extracción anterior. Se recalculan una sola vez al final, con el flujo completo ya validado, para que todo sea coherente con la metodología.
