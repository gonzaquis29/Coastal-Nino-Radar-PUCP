# Tópicos y polaridad de las notas (punto 4)

Código: `radar.nlp.topicos`. Una sola lectura de los cuerpos en memoria; se guardan solo la bolsa de lemas (sin los términos del fenómeno), el vector promedio de minilm y la polaridad. Nada del cuerpo queda en disco.

```bash
python -m radar.nlp.topicos muestra   # 100 notas por medio para P2, agregadas a config/notas_vistas.csv
python -m radar.nlp.topicos leer      # pide páginas; se puede cortar y relanzar
python -m radar.nlp.topicos ajustar   # sin red
```

## Definición (aprobada el 7-nov)
- **Corpus:** las notas sobre El Niño. Vocabulario con el mismo corte que TF-IDF (`min_df` 3, `max_df` 0,9).
- **Modelos:** LDA (gensim) y BERTopic con KMeans en vez de HDBSCAN, para que tenga el mismo k que LDA. k ∈ {6, 8, 10, 12, 15}, con 3 semillas cada uno. Los dos se nombran con c-TF-IDF, sin LLM.
- **T1 (estabilidad):** Jaccard de las 10 palabras de cada tópico entre semillas, emparejando con el algoritmo húngaro. Debe ser ≥ 0,50. Si ninguno pasa, se toma el más estable y se declara inestable.
- **T2 (elección):** gana el mayor c_v, con la nota entera como ventana, porque solo se guardan bolsas. Con menos de 0,01 de diferencia gana el de menos tópicos.
- **P1:** 0 tramos truncados en robertuito (tramos de hasta 128 tokens; se promedian las probabilidades).
- **P2:** kappa de Cohen ≥ 0,40 entre pysentimiento y un zero-shot independiente (mDeBERTa NLI, hipótesis "El tono de este texto es {}."), en notas nuevas. Si no pasa, la polaridad queda solo descriptiva.
- **Informativos:** diversidad; presencia de las 4 categorías oficiales en las palabras (listas fijadas antes de ajustar); proporción de cada medio y polaridad por tópico; destilado TF-IDF + regresión logística.
- **Agregados:** por mes y, por separado, por macro-región principal. Las celdas mes × región se muestran solo con 20 notas o más.

## Resultado (7-nov)
Hubo 2.521 notas con texto, de 2.524. Las otras 3 son 2 sin texto y 1 que ya no existe. La lectura tomó 94 min y el ajuste, 12 min.

| Modelo | Jaccard entre semillas | c_v |
|---|---|---|
| LDA k = 6 a 15 | 0,35 a 0,44 (ninguno pasa T1) | 0,690 a 0,711 |
| BERTopic k=6 | 0,923 | 0,742 |
| BERTopic k=8 | 0,826 | 0,741 |
| BERTopic k=10 | 0,866 | 0,737 |
| **BERTopic k=12** | **0,866** | **0,758** |
| BERTopic k=15 | 0,782 | 0,765 |

**Elegido: BERTopic con k=12.** k=15 tiene un c_v 0,006 más alto, menos que el empate de 0,01, así que gana el de menos tópicos. LDA es inestable en todos los k. La diversidad es 0,83, y las 4 categorías oficiales aparecen en las palabras.

| Tópico | Notas | Palabras (c-TF-IDF) | Categoría |
|---|---|---|---|
| 0 | 345 | río, trabajo, agua, riesgo, lluvia, intervención, Piura, puente | Lluvias, ríos y huaicos |
| 1 | 322 | lluvia, temperatura, costa, Pacífico, normal, mar, calentamiento | Lluvias, ríos y huaicos |
| 2 | 310 | gobierno, ministro, Fujimori, presidenta, país | |
| 3 | 302 | emergencia, riesgo, respuesta, defensa, población | Prevención y emergencias |
| 4 | 216 | economía, precio, crecimiento, producción, sector | |
| 5 | 216 | millón, gobierno, medida, crédito, empresa, bono | |
| 6 | 215 | riesgo, lluvia, Piura, río, inundación, vivienda | Lluvias, ríos y huaicos |
| 7 | 178 | facultad, legislativo, cámara, ejecutivo, senado | |
| 8 | 128 | temperatura, Senamhi, costa, Lima, calor | Calor |
| 9 | 115 | pesca, especie, pesquero, anchoveta, Imarpe | Pesca y mar |
| 10 | 114 | salud, dengue, enfermedad, Minsa, hospital | |
| 11 | 60 | educativo, escolar, estudiante, Minedu, colegio | |

Por mes, el tópico más frecuente pasa del pronóstico (tópico 1, de enero a junio) a lluvias y obras (julio), política (agosto), prevención (septiembre) y economía y bonos (octubre). Hay 25 celdas mes × región con 20 notas o más.

**Polaridad:** P1 pasa, con 0 truncados en 17.623 tramos. **P2 no pasa:** κ = 0,12 en 385 notas, así que la polaridad queda **solo descriptiva**. pysentimiento casi nunca marca positivo (5 de 385) y el zero-shot sí (115). El destilado reproduce a pysentimiento (κ 0,53), pero no al zero-shot (0,03). En el corpus: neutral 2.016, negativo 424, positivo 81. El tópico más negativo es el 6 (inundaciones, 64 % negativo).

**Límites:**
- La muestra de P2 tiene 385 notas y no 400, porque El Tiempo solo tenía 85 sin ver.
- Los tópicos 2 y 7 (política) muestran que "sobre El Niño" incluye notas políticas que mencionan al fenómeno de pasada.
- c-TF-IDF nombra los tópicos, pero no garantiza que sean temas oficiales.
