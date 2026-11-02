# Preprocesamiento y TF-IDF (1-nov-2026)

Línea base de representación (README, pipeline 2 y 3). Los criterios se fijaron y aprobaron antes de correr.

```
python -m radar.nlp.tfidf leer       # pide páginas (@exclusivo); se puede cortar y relanzar
python -m radar.nlp.tfidf vectores   # sin red
```

## Definición
**Corpus:**
- las notas sobre El Niño de `notas.csv`, ya sin las de Andina en inglés;
- las 800 del control negativo (`control_negativo.csv`): 400 de otros temas, que deciden, y 400 "cercanas" (lluvias, calor sin El Niño), solo informativas;
- los 865 párrafos oficiales de `data/oficial/parrafos.csv`.

**Lectura.** Cada cuerpo se vuelve a leer en memoria con `Medio.descargar`, con los 4 medios en paralelo y el ritmo de siempre. De cada nota solo se guarda su bolsa de lemas en `data/processed/nlp/conteos.csv`: "lema veces", en orden alfabético. No se guarda la secuencia, que permitiría reconstruir el texto. También quedan los controles de la lectura: sha1 del cuerpo, menciones y errores.

**Texto de cada nota:** titular, resumen (solo si menos del 90 % de sus palabras está en el cuerpo) y cuerpo.

**Preprocesamiento** (`radar.nlp.preproceso`):
1. Cada mención de El Niño o La Niña según la regla de `noticias.rasgos` (`menciones_en`) se convierte en un solo término: `el_niño` o `la_niña`. Sin esto, `es_core_news_sm` juntaría "El Niño" con "niños". "ENFEN" no se cambia y queda como el lema `enfen`.
2. Lemas de spaCy (`es_core_news_sm`, sin parser ni NER), en minúsculas y con el clítico quitado ("adelantar él" → "adelantar").
3. Fuera: stopwords de spaCy, números, signos, lemas de una letra y los nombres de los medios (`andina`, `rpp`, `exitosa`, `eltiempo`, `rotafono`).

**Vectores** (`data/processed/nlp/`):
- `conteos.npz`: documentos × términos;
- `tfidf.npz`: `TfidfTransformer` con tf sublineal y norma L2, ajustado con las notas sobre El Niño y los párrafos oficiales; el control solo se transforma;
- `documentos.csv` (filas) y `vocabulario.csv` (columnas, con df ≥ 3 y como máximo en el 90 % de los documentos del ajuste).

## Criterios
| | Criterio | Umbral |
|---|---|---|
| T1 | notas del corpus leídas con texto | ≥ 98 % |
| T1 | cuerpo igual al de `notas.csv` (sha1) | ≥ 95 % |
| T2 | términos `el_niño` + `la_niña` de la bolsa = menciones de la regla en el mismo texto | ≥ 99 % |
| T3 | ningún archivo guarda el orden ni el texto | prueba sintética (`tests/nlp/test_tfidf.py`) |
| T4 | AUC del coseno máximo con los párrafos del ENFEN, notas sobre El Niño frente a otros temas, **sin** los términos del fenómeno (`el_niño`, `la_niña`, `enfen`, `fen`, `niño`, `niña`, `costero`) | ≥ 0,90 |
| T5 | ningún nombre de medio entre los 50 términos de más peso medio de cada medio | 0 |

T4 se calcula sin esos términos porque son los mismos que definen "sobre El Niño", y con ellos el AUC saldría inflado. El AUC con todo el vocabulario y frente a las notas "cercanas" se reporta como informativo. Ninguno de estos criterios usa muestras de notas.

## Resultado: NO PASA (por T4)
La lectura tomó 23 min: 3.177 notas con texto y 1 sin texto. Hay 4.042 documentos y 8.189 términos.

| | Valor | |
|---|---|---|
| T1 leídas con texto | 3.177/3.178 (99,97 %) | pasa |
| T1 sha1 igual | 99,91 % (3 de Andina distintas: ediciones del sitio) | pasa |
| T2 | 3.177/3.177 | pasa |
| T3 | prueba sintética en verde | pasa |
| **T4** | **0,799** | **no pasa** |
| T5 | ningún nombre de medio | pasa |

Informativos: AUC con todo el vocabulario 0,822; frente a las notas "cercanas", 0,651 sin los términos del fenómeno y 0,665 con ellos.

**Diagnóstico de T4** (sobre el mismo corpus, sin muestras nuevas; el criterio no se cambia):
- **No es el instrumento:** T1 y T2 pasan, y el AUC es parecido en los 4 medios (0,78-0,85).
- **Depende de cuánto habla la nota de El Niño:** 0,73 con 1-2 menciones, 0,80 con 3-5 y 0,93 con 6 o más. Muchas notas "sobre El Niño" tratan de medidas del Gobierno: emergencia, prevención, ministros, presupuesto. Léxicamente no se parecen a los párrafos técnicos del ENFEN, aunque sean del tema. La similitud mediana es baja en los dos grupos: 0,086 en las notas sobre El Niño frente a 0,053 en las de otros temas.
- **Otras agregaciones no lo arreglan:** media de los 5 más parecidos 0,806; centroide del ENFEN 0,827; con los avisos del Senamhi 0,770.

**Qué significa.** TF-IDF queda como línea base débil para la distancia a lo oficial. Si los embeddings (punto 4.3) tampoco separan, el umbral del semáforo (percentil 25 del control negativo) no se puede calibrar con este control. Eso hay que decidirlo en el punto 4.3, con los mismos controles.

**Hallazgo de capa 1.** Todas las notas de Andina terminan con la línea `Publicado: 21/10/2026` (comprobado en 2 notas nuevas, semilla `andina-publicado-1nov`). Es texto de la página, no de la nota, y por eso `publicado` salía como segundo término de Andina. T5 no lo detecta porque solo busca nombres de medios. Se quitó en `noticias/nota.py` (capa 1 validada con dos semillas nuevas) y Andina se volvió a leer: `publicado` ya no está entre sus términos y T4 pasa de 0,7997 a 0,7994; los demás criterios no cambian. En `notas.csv` el sha1 de Andina cambia con el recálculo final (`docs/pendientes.md`, punto 2); hasta entonces T1 acepta el sha1 con y sin la línea.
