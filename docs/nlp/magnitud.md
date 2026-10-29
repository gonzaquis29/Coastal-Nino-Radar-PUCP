# Regla de magnitud por cercanía (28-oct-2026)

**Responsabilidad única:** decir qué magnitudes de El Niño (débil, moderada, fuerte, muy fuerte, extraordinaria) menciona una frase. No decide quién lo dice, de cuándo habla ni si coincide con lo oficial (capas 3 a 5). Es **una sola regla** para el ENFEN (`comunicados.csv`) y las notas (`notas.csv`): `oficial.enfen.magnitudes_de_frase`.

## Por qué cambió
Había dos reglas distintas y las dos decidían con la frase completa:
- `rasgos.magnitudes` contaba cualquier término en una frase con El Niño y con "magnitud", "intensidad" o "categoría". Tomaba "lluvias de fuerte intensidad" y perdía "El Niño fuerte".
- La del ENFEN descartaba la frase entera si decía "intensidad" o "lluvia". Aplicada a las notas, perdía la forma más común en que los medios escriben la magnitud ("Niño costero de intensidad fuerte"): 26 de 41 pérdidas en los resúmenes. El propio ENFEN escribe "alcance una intensidad moderada".

## Qué hace
1. **Cadena:** una o más magnitudes unidas por "a", "y", "o", ",", "hasta", "entre" o "e incluso", con porcentajes y comillas: "entre fuerte (48 %) y moderada", "de 'fuerte' o 'extraordinario'".
2. **Cuenta solo si está anclada:**
   - **antes**, a lo más `MAX_PUENTE` = 4 palabras de unión ("de", "una", "sería", "alcanzaría", años, adverbios en -mente, "ENOS"…), va El Niño (costero o global, "(FEN)"), evento, episodio o fenómeno, o un grado: magnitud, intensidad, categoría, nivel, fase o condición, en singular o plural;
   - **después** va el grado o el sujeto: "de fuerte intensidad", "un fuerte fenómeno El Niño";
   - o **continúa** una magnitud ya anclada en la frase: "…y entre fuerte y extraordinaria", "para luego disminuir a moderado", "primero débil, ahora moderado".
3. **Vetos:**
   - el grado o la cadena van pegados a lluvias, precipitaciones, caudales, crecidas, vientos, oleaje, temperaturas o calor;
   - **comparativos** ("el más fuerte en décadas", "tan fuerte como"), que no son una categoría del ICEN. Decisión del 28-oct; 14 frases en el diseño.
4. **Principal o posible:** como antes ("no se descarta", "podría alcanzar"…).
5. **Qué frases mira cada uno:**
   - **ENFEN:** las de la región Niño 1+2, como antes.
   - **Notas:** el texto se parte por línea y por frase. Cuenta la frase que nombra a El Niño o sigue a una que lo nombra en la misma línea, y se descartan las del Pacífico central.
   - **"El Niño global" es Pacífico central** (Niño 3.4), como en la capa 3. Decisión del 28-oct; 9 frases en el diseño. El ENFEN no usa "global": ningún párrafo oficial cambia.
   - `rasgos.magnitudes` devuelve todas las mencionadas, como `magnitudes_mencionadas`.

## Datos de diseño y de validación
- **Diseño:** el corpus oficial, más los titulares y resúmenes de todas las notas. Con ellos se escribió la regla.
- **Validación:** solo frases del **cuerpo** de notas nuevas. Se excluyen las que repiten una frase de un titular o resumen, porque el cuerpo suele repetir el resumen: en Andina lo contiene en el 100 % de las notas y en El Tiempo en el 72 %. También se excluyen las notas de `config/notas_vistas.csv` y las reservadas para la capa 3.

## Instrumento independiente
El análisis sintáctico de spaCy (`es_core_news_sm`; `pip install -e ".[nlp]"` y `python -m spacy download es_core_news_sm`) da el sustantivo del que depende cada término. Se salta las enumeraciones; si el término es el atributo de una copulativa, no da núcleo. Sus listas de lemas están escritas aparte de las expresiones de la regla.
- Se usa solo en los dos sentidos en que es confiable (C3a y C3b). El acuerdo global no sirve: el analizador se equivoca en ~10 % de los casos y mezclaría sus errores con los de la regla.
- Con el diseño, la primera versión del instrumento subía hasta 4 niveles en el árbol y "fuerte caída de la pesca" terminaba en El Niño. Se dejó en el núcleo directo antes de validar.

## Criterios (fijados antes de correr)
| | Criterio | Pasa si |
|---|---|---|
| C1 | Regresión oficial: `comunicados.csv` y `parrafos.csv` sin cambios; criterios del ENFEN en `validar.py` | sin diferencias; todos pasan |
| C2 | Frases sintéticas (`tests/noticias/test_magnitudes.py`). Es una regresión: salen de los patrones del diseño | 100 % |
| C3a | Términos aceptados cuyo núcleo es un sustantivo de clima | ≤ 2 % |
| C3a′ | Términos aceptados cuyo núcleo es otro sustantivo (no El Niño ni su grado); no depende de la lista de clima | ≤ 5 % |
| C3b | Términos que dependen de El Niño o de su grado (sin comparativos) y la regla rechaza | ≤ 10 % |
| C4 | Con la regla anterior, C3a y C3b salen peores (el instrumento distingue) | sí |

`python -m radar.noticias.validar_magnitud [--semilla S]`: 25 notas por medio con magnitud y 25 sobre El Niño sin magnitud, leídas una vez y en memoria. Los casos se muestran en pantalla para diagnosticarlos; las frases no se guardan.

## Resultados, en orden
| Muestra | C3a | C3a′ | C3b | Regla anterior (C3a / C3b) | Qué se encontró y qué se corrigió |
|---|---|---|---|---|---|
| Diseño (titulares y resúmenes) | 0/214 | 3/202 | 2/184 | 6/140 · 68/184 | Los 3 de C3a′ y los 2 de C3b son errores de spaCy |
| C1 antes de validar | — | — | — | — | El resumen HTML del ENFEN traía las llamadas de nota pegadas ("fuerte2") y la regla no las reconocía → corregido en la capa 2 ([../oficial/definicion.md](../oficial/definicion.md)). Con eso, C1 da 0 diferencias |
| 1.ª (`magnitud-cercania`, 188 notas) | 0/58 | 0/58 | 4/56 | 4/42 · 22/56 | **Pasa.** 1 omisión real ("de modo primero débil, ahora moderado"), 1 dudosa ("condiciones climáticas extraordinarias") y 2 del instrumento: un comparativo con "tan" y niveles de radiación UV |
| 2.ª (`…-confirmacion`, 175 notas) | 0/36 | 0/36 | **7/35** | 2/31 · 16/35 | **No pasa.** 6 omisiones reales en 2 frases: "eventos ENOS como débiles…" y "niveles" en plural. 1 del instrumento: el comparativo con "tan", que la definición excluye y el instrumento no → se corrigieron la regla (grados en plural; "ENOS", "modo", "primero" como puente; "ahora", "luego" como continuación) y el instrumento (comparativos con "tan" y "menos"), sin tocar umbrales. C1 y C2 se repitieron: sin cambios |
| **3.ª** (`…-tercera`, 147 notas) | **0/28** | **0/28** | **0/26** | 3/23 · 8/26 | **Pasa** |

**Límites declarados:**
- Las muestras son chicas, porque las notas con magnitud son pocas: 0/26 deja un intervalo de confianza del 95 % de hasta ~11 %. En las tres muestras juntas, la regla nueva no aceptó ningún término que dependiera de un sustantivo de clima ni de otro sustantivo (0/122). La anterior aceptó términos de clima en 9 de 96 casos.
- La 3.ª agotó las notas con magnitud sin ver (quedan 16 de Andina). La medición completa del efecto queda para el recálculo, que compara cada nota con su valor anterior.
- Lo que no se puede validar aquí: si la magnitud que afirma una nota es la del comunicado vigente. Eso es la capa 3, con su muestra reservada.
