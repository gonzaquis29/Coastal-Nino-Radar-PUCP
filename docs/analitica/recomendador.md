# Recomendador híbrido

Módulo: `python -m radar.analitica.recomendador validar` (`src/radar/analitica/recomendador.py`). Entrada: un texto (titular y resumen, o título y descripción de un video), una fecha y un perfil (macro-región e interés). Salida: lo oficial que corresponde y las notas relacionadas.

## Medición previa (8-nov, sin red)

| Etiqueta sin trabajo manual (enlaces de las notas) | Casos | Uso |
|---|---|---|
| Nota → comunicado enlazado | 18 notas | Con el filtro de fecha solo hay un comunicado vigente: acertar es automático. La prueba del README (filtro apagado) mide algo que el producto no hace |
| Nota → aviso del Senamhi enlazado | 65 notas (15 sobre El Niño) | Mediana de 2 avisos candidatos por fecha: al azar se acierta la mitad |
| Nota → nota enlazada por el propio medio | 1.003 pares entre notas sobre El Niño (37 con el origen sin ver); 351 desde notas sin ver que **mencionan** El Niño hacia notas sobre El Niño | **Única etiqueta útil** |

## Enfoques

| Enfoque | Decisión |
|---|---|
| Solo reglas (conocimiento) | **Para lo oficial**: no hay nada que aprender, la corrección depende de la vigencia y la región ya validadas |
| Solo contenido (minilm) | Rival (R2) |
| Híbrido en cascada: reglas que filtran, similitud que ordena, premio por región y diversidad (MMR) | **Para las notas** |
| Híbrido por suma ponderada; aprender a ordenar | Descartados: no hay etiquetas para ajustar pesos |
| Grafo de enlaces | Descartado: es la misma señal que la etiqueta (circular) |
| Filtrado colaborativo | Imposible: no hay usuarios |
| Lo más reciente; al azar | Rivales (puerta y R1) |

## Definición (aprobada el 8-nov)

**Parte oficial (reglas):**
- El comunicado vigente (`vigencia.Corpus`).
- Sus párrafos con un `tema` igual al interés del perfil, sin las definiciones y sin el Pacífico central. Se ordenan por similitud minilm con el texto, el modelo elegido en E.
- Los avisos del Senamhi vigentes en la fecha y la macro-región del perfil, del nivel más alto al más bajo.
- Intereses: pesca, lluvias, calor y prevención, tomados del campo `temas` que calcula `radar.oficial`.

**Notas relacionadas (híbrido en cascada, sin parámetros ajustados):**
1. **Filtro:** notas sobre El Niño publicadas antes del texto, en los 90 días previos. Cuando exista la capa 5 de todas las notas, también sin las rojas.
2. **Puntaje:** el coseno minilm entre el titular y el resumen, más 0,05 si la macro-región principal de la nota coincide con la del perfil.
3. **Diversidad:** MMR con λ = 0,7 sobre los 50 primeros, hasta 5 notas.

Los valores 90, 0,05, 0,7 y 5 se fijan antes de medir y no se ajustan. Por eso no hace falta separar calibración y prueba.

**Muestra (A):**
- Orígenes: notas sin ver que mencionan El Niño, no son sobre El Niño (así no tocan la reserva de T5) y enlazan a una nota anterior del mismo medio sobre El Niño.
- La nota enlazada es la relevante.
- Los candidatos son las notas sobre El Niño del mismo medio en los 90 días previos (la etiqueta es una elección del editor de ese medio). Las notas reservadas para T5 se quitan como candidatas y como enlazadas.
- Los orígenes se agregan a `notas_vistas`.

**Criterios, fijados antes del código:**

| | Prueba | Umbral |
|---|---|---|
| P | **Puerta:** AUC de la similitud entre la enlazada y las no enlazadas del mismo día (estratificado por fecha). ¿El enlace sigue al contenido más allá de la fecha? | ≥ 0,60; si no, R1 y R2 no se evalúan y se declara |
| R1 | MRR del híbrido menos el de "lo más reciente" | ≥ 0,05, con el intervalo bootstrap pareado al 95 % por encima de 0 |
| R2 | MRR del híbrido frente al del contenido solo | ≥ el del contenido − 0,02 |
| R3 | Medios distintos entre las 5 notas, con candidatos de todos los medios (como en el producto) | ≥ 2 de media |
| R4 | Tiempo por consulta (catálogo ya embebido) | ≤ 2 s |
| K1 | Reglas: pruebas unitarias | 100 % |
| K2 | Cada día de 2026 × macro-región recibe un comunicado vigente | 100 % |

**Informativos:**
- MRR y recall@5 de cada pieza: contenido, más región, más MMR.
- Cobertura: la parte del catálogo que aparece alguna vez entre las 5.
- Estabilidad: enero a junio frente a julio a octubre.
- La muestra B (notas nuevas del 9 al 18-nov, junto con T5) como confirmación.
- La parte de notas en verde, cuando corra la capa 5.

**Límites:**
- Los orígenes solo mencionan El Niño, así que son entradas algo distintas de un titular sobre El Niño. Eso hace la prueba más exigente.
- El enlace del editor es una relevancia parcial: otras notas pueden ser igual de buenas.
- Sin usuarios, no hay evaluación en línea.

## Ronda a (8-nov): no pasa R1

La muestra A tiene 276 orígenes, con 1.058 pares para la puerta, y quedó agregada a `notas_vistas` (`recomendador-a-8nov`). La mediana es de 180 candidatas por origen.

| | Resultado | Umbral | |
|---|---|---|---|
| P | AUC 0,745 | ≥ 0,60 | pasa: el contenido explica el enlace más allá del día |
| R1 | −0,191 (IC −0,244 a −0,138) | ≥ +0,05 | **no pasa** |
| R2 | 0,196 frente a 0,199 | ≥ contenido − 0,02 | pasa |
| R3 | 2,66 medios | ≥ 2 | pasa |
| R4 | 0,14 s | ≤ 2 s | pasa |
| K2 | 927/927 | 100 % | pasa |

| Método (informativo) | MRR | recall@5 | MRR ene-jun | MRR jul-oct |
|---|---|---|---|---|
| Al azar | 0,063 | 0,080 | 0,216 | 0,029 |
| Lo más reciente | **0,387** | **0,605** | 0,599 | 0,339 |
| Contenido | 0,199 | 0,293 | 0,225 | 0,193 |
| Más región | 0,200 | 0,290 | 0,223 | 0,194 |
| Híbrido (más MMR) | 0,196 | 0,272 | 0,232 | 0,188 |

**Diagnóstico:**
- **Los editores enlazan sobre todo lo último que publicaron**, y entre lo del mismo día eligen por contenido. El híbrido definido no usa la fecha dentro de la ventana de 90 días, así que pierde frente a lo más reciente.
- **La región y el MMR casi no cambian el orden:** el premio de 0,05 y λ = 0,7 mueven poco.
- **La cobertura es amplia:** 663 de 2.282 notas aparecen alguna vez entre las 5.

Hay que decidir en una ronda b si la frescura entra como regla del híbrido. Para el producto también tiene sentido: mostrar lo último que está alineado.

## Ronda b (aprobada el 8-nov): frescura como regla

- **Cascada:** primero las notas de los últimos N días, ordenadas por el híbrido (contenido, región y MMR); después el resto, de la más reciente a la más antigua.
- **Calibración de N:** con la muestra A, que ya está vista y solo sirve como desarrollo, en la grilla 3, 7, 14 y 30. En caso de empate gana el menor.
- **Decisión:** con la muestra B, que son las notas nuevas desde el 9-nov que mencionan El Niño (sobre El Niño o no) y enlazan una nota anterior del mismo medio. Se usa el 18-nov junto con T5, como primer uso. Para B, el catálogo incluye las notas nuevas, porque sin ellas no habría frescura.
- **Criterios:** R1 a R3 iguales que en la ronda a, sobre la cascada fresca. Con menos de 30 orígenes en B, la ronda es informativa.

**Calibración (8-nov, 276 orígenes de A): N = 3 días.**

| | 3 días | 7 días | 14 días | 30 días | Lo más reciente |
|---|---|---|---|---|---|
| MRR | **0,425** | 0,370 | 0,314 | 0,249 | 0,387 |

Por mitades, lo más reciente frente a la cascada de 3 días da 0,599 frente a 0,543 en enero a junio, y 0,339 frente a 0,399 en julio a octubre.

**Aviso antes de B:** en la calibración, la mejora sobre lo más reciente (+0,038) no llega al +0,05 de R1. En julio a octubre, el período más parecido a B por volumen, sí llega (+0,06). El MRR crece al acortar la ventana, y 3 es el borde de la grilla; no se agregan valores menores para no ajustar después de mirar. Si R1 no pasa en B, el producto usa la cascada de 3 días de todas formas (no empeora frente al contenido solo y da frescura), pero se declara que no le gana a "lo más reciente".

```bash
python -m radar.analitica.recomendador validar --ronda b   # 18-nov, después de la recolección de ese día
```
