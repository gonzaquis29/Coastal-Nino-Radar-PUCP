# Embeddings (1-nov-2026)

Representación de la distancia a lo oficial (README, pipeline 3): MiniLM (`paraphrase-multilingual-MiniLM-L12-v2`) frente a e5-small (`multilingual-e5-small`), comparados con la línea base TF-IDF ([tfidf.md](tfidf.md)). Los criterios se fijaron y aprobaron antes de correr, después de un piloto con los titulares.

```
python -m radar.nlp.embeddings leer        # pide páginas (@exclusivo); se puede cortar y relanzar
python -m radar.nlp.embeddings criterios   # sin red
python -m radar.nlp.embeddings revision    # sin red: 10 notas nuevas con su párrafo más cercano
```

## Piloto con los titulares (sin red, antes de definir)
Coseno máximo de cada titular con los 264 párrafos del ENFEN, en todo el corpus del TF-IDF:

| AUC | MiniLM | e5-small |
|---|---|---|
| sobre El Niño frente a otros temas, sin los términos del fenómeno | 0,764 | 0,840 |
| ídem, con todo | 0,876 | 0,889 |
| control positivo frente a otros temas, con todo | 0,995 | 0,991 |
| sobre El Niño frente a "cercano", sin términos | 0,632 | 0,695 |
| positivos cuyo párrafo más parecido es del comunicado que citan (al azar ~5 %) | 18 % | 39 % |

Lo que cambió la definición:
- **Largo.** MiniLM se entrenó con 128 tokens, y el 14 % de los párrafos del ENFEN pasa de ese largo; el cuerpo mediano tiene 423 palabras (p90: 785). Cada modelo usa su largo propio (MiniLM 128, e5 512) y el texto se parte en tramos que caben sin truncar.
- **Derecho de autor.** Los vectores de cada tramo permitirían reconstruir el texto de forma aproximada. Solo se guarda un vector por nota (el promedio) y sus puntajes.
- **Control positivo chico y solo de Andina** (41 notas, 13 que no son "sobre El Niño"): los AUC llevan un intervalo de 95 % por bootstrap, y se reporta además Andina frente a Andina.
- e5 da cosenos comprimidos (0,80-0,94): no afecta al AUC, pero deja los umbrales del semáforo muy juntos. Se declara.

## Definición
**Corpus:** el del TF-IDF (notas sobre El Niño y control negativo) más las 13 notas del control positivo que no son "sobre El Niño". El control positivo son las notas de Andina que citan un comunicado del ENFEN (`comunicados` de `notas.csv`, cualquier nivel). Se compara con los 264 párrafos del ENFEN.

**Texto:** titular, resumen (si no está en el cuerpo) y cuerpo, como en el TF-IDF. Los titulares se miden aparte, sin red, desde `notas.csv`. "Sin términos" quita las menciones de El Niño o La Niña (regla de `noticias.rasgos`) y las palabras ENFEN, FEN, costero, niño y niña, como T4.

**Tramos:** líneas completas juntas mientras quepan en el largo del modelo (con el prefijo `query: ` de e5 y los tokens especiales); una línea que no cabe se parte por oraciones y, si hace falta, por palabras. Los párrafos del ENFEN se parten igual.

**Puntaje:** coseno máximo entre los tramos de la nota y los tramos de los párrafos. Informativos: el vector promedio de la nota frente a cada párrafo, y frente al centroide del ENFEN.

**Modelos:** torch en float32 para los dos candidatos, y e5 cuantizado en ONNX, que es el que usaría la app.

**Salidas** (`data/processed/nlp/`): `embeddings.csv` (puntajes y controles por nota y modelo) y `vectores.csv` (el vector promedio de cada nota en base64, float32).

## Criterios
Sobre todo el corpus, sin muestras, por separado para titulares y cuerpos.

| | Criterio | Umbral |
|---|---|---|
| E1 | lectura de los cuerpos (como T1): notas leídas con texto; sha1 igual al de `notas.csv` | ≥ 98 %; ≥ 95 % |
| E2 | el promedio propio reproduce a `sentence-transformers` en los tramos del ENFEN; ningún tramo truncado | coseno ≥ 0,9999; 0 |
| E3 | **semáforo (README):** AUC del control positivo frente a otros temas, texto completo, sin que los umbrales se crucen (p25 del positivo > p75 del negativo) | ≥ 0,80 |
| E4 | **representación (como T4):** cuerpos sobre El Niño frente a otros temas, sin los términos del fenómeno | ≥ 0,90 |
| E5 | e5 cuantizado frente a float32, en E3 y E4 de cuerpos | \|ΔAUC\| ≤ 0,01 |

**Elección:** el de mayor E4 en cuerpos; si la diferencia es menor de 0,02, e5 (0,78 GB en la app frente a 1,31 GB). E3, E4 y E5 deciden con el modelo elegido; E5 solo decide si se elige e5.

**Informativos:** los dos modelos en E3 y E4; frente a "cercano"; por medio y por tramo de menciones; vector promedio y centroide; Andina frente a Andina; acierto del comunicado citado; revisión de 10 notas nuevas (semilla `embeddings-revision-1nov`).

Si E3 pasa y E4 no, el semáforo se calibra igual con E3, como pide el README, y se declara que la separación depende de cuánto habla la nota de El Niño.

## Resultado: PASA, con e5-small
La lectura tomó 64 min (los embeddings, no la red, marcan el ritmo) y los criterios, 30 min: 3.190 notas con texto y 1 sin texto, 0 tramos truncados.

| | e5 (elegido) | | MiniLM |
|---|---|---|---|
| E1 leídas con texto / sha1 igual | 99,97 % / 99,91 % (3 de Andina, ediciones del sitio) | pasa | |
| E2 coseno con sentence-transformers / truncados | 1,0000 / 0 | pasa | 1,0000 |
| E3 titulares (IC 95 %) | 0,901 (0,835-0,959); p25 positivo 0,851 > p75 negativo 0,825 | pasa | 0,880 |
| E3 cuerpos | 0,951 (0,902-0,989); 0,898 > 0,856 | pasa | 0,931 |
| **E4 cuerpos** | **0,912** (0,897-0,925) | pasa | 0,913 |
| E5 e5 cuantizado | \|ΔAUC\| 0,0063 en E3 y 0,0001 en E4 | pasa | — |

**Elección.** MiniLM y e5 empatan en E4 (0,913 frente a 0,912), así que manda la regla de empate: e5, que en la app cabe cuantizado (0,78 GB) y da lo mismo que en float32 (E5).

Informativos (e5; MiniLM entre paréntesis):
- Frente al TF-IDF: E4 sube de 0,799 a 0,912. En titulares, E4 es 0,840 (0,772).
- Frente a "cercano", sin términos: 0,737 (0,721). Las lluvias y el calor sin El Niño siguen siendo difíciles de separar.
- Por tramo de menciones: 0,866, 0,920 y 0,983 (igual en MiniLM). La dependencia que ya se vio en el TF-IDF sigue, aunque más atenuada.
- Por medio: entre 0,893 (Andina) y 0,934 (El Tiempo).
- Vector promedio 0,885 y centroide 0,875 (MiniLM: 0,930 y 0,917). Con e5 conviene el máximo por tramo.
- Andina frente a Andina, E3: 0,938 (0,920). El efecto del medio no explica el control positivo.
- Positivos cuyo párrafo más parecido es del comunicado que citan: 17/41 en cuerpos y 9/41 en titulares (MiniLM: 17 y 5).

**Límites que se declaran:**
- El límite inferior del IC de E4 (0,897) queda apenas bajo 0,90.
- En titulares, el margen entre los umbrales del semáforo es chico: 0,851 frente a 0,825, con cuantizado 0,853 frente a 0,832.

**Revisión de 10 notas nuevas** (semilla `embeddings-revision-1nov`, sin decidir nada):
- En 5 el párrafo más parecido es del tema: pérdidas por el FEN con la alerta, lluvias en China con las lluvias en la costa, quebradas con las lluvias en la costa norte, dengue con las temperaturas del aire, y descolmatación en Lambayeque con los embalses de Lambayeque.
- En las otras 5, notas de política (Senado, Midagri, MEF, Defensa, canales oficiales), el párrafo es genérico: la definición de "Alerta" o el de embalses.

**Hallazgo: párrafos "imán" (hubness).** Con e5, un solo párrafo de definiciones (`enfen-2026-11-p14`, la definición de "Alerta de El Niño Costero") es el más parecido para el 11,5 % de las notas sobre El Niño. Los 14 párrafos de tipo `definicion` (el 5 % del ENFEN) se llevan el 14,6 %. No cambia el AUC, pero sí lo que mostraría el semáforo como "párrafo oficial más cercano". Hay que decidirlo al construir el semáforo (por ejemplo, comparar sin los párrafos de `definicion` o elegir el párrafo por `tipo`), y no aquí, para no ajustar el criterio después de ver el resultado.
