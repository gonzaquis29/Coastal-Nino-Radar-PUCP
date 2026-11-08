# Estudio de eventos: efecto de cada comunicado del ENFEN

Módulo: `python -m radar.analitica.eventos validar` (`src/radar/analitica/eventos.py`). Solo usa metadatos de `notas.csv` (fecha, "sobre El Niño", citas a comunicados): no pide páginas ni lee cuerpos. Escribe en `data/processed/analitica/` la serie diaria (solo conteos), el perfil por día relativo y la validación.

## Medición previa (8-nov, sin red)

- Los 19 comunicados de 2026 salen cada ~14 días. 209 de los 310 días caen dentro de alguna ventana de −3 a +7, así que la comparación del README contra "días sin evento" tiene pocos días de control.
- El volumen sobre El Niño se multiplicó por 30 entre enero (20 notas) y octubre (652). Sin quitar la tendencia, cualquier comparación da un efecto.
- En bruto, el día del comunicado casi no sobresale (media de 10,0 notas frente a 7,5 el día anterior). El pico más alto (19 al 23-oct) no coincide con un comunicado.

## Enfoques

| Enfoque | Decisión |
|---|---|
| Ventana frente a días sin evento (plan del README) | Descartado: pocos días de control y sesgo por la tendencia |
| Volumen anormal frente a una ventana previa | Descartado: con 14 días entre comunicados, la ventana previa cae en el efecto del anterior |
| Regresión de Poisson diaria con tendencia, día de la semana y una variable por día relativo | **Elegido** |
| Placebo por permutación de fechas | **Elegido para la inferencia** (ronda a) |
| Control sintético o diferencias en diferencias con otros temas | Usado como control negativo (V4) |
| Detección de cambios de nivel sin fechas; Granger | Informativo, o descartado (los comunicados tienen fecha fija) |

## Definición (aprobada el 8-nov)

- **Serie:** días desde el 1-ene hasta la última fecha de `notas.csv`, sin fechas dudosas. Entran los comunicados con la ventana completa (18 al 5-nov: N.° 1 a 18).
- **Modelo:** Poisson con tendencia lineal por tramos (un nodo cada 28 días), día de la semana y una variable por cada día de −3 a +7. La proporción usa el total de notas del día como exposición.
- **Efecto:** la media de los coeficientes de los días 0 a +2, frente a los días fuera de las ventanas.
- **Inferencia:** 999 conjuntos de fechas falsas, con los intervalos reales barajados y un inicio al azar. El valor p es bilateral.

**Criterios, fijados antes del código:**

| | Prueba | Umbral |
|---|---|---|
| V1 | Tamaño: 1.000 conjuntos de fechas falsas sobre la serie real, significativos al 5 % | ≤ 7 % |
| V2 | Potencia: +50 % en los días 0 a +2 de fechas falsas sobre la serie real, detectado | ≥ 80 % |
| V3 | Control positivo: las notas que citan un comunicado y mencionan El Niño suben en los días 0 a +2 | > 0 y p < 0,05 |
| V4 | Control negativo: las notas de otros temas no muestran efecto | p ≥ 0,05 |

## Ronda a (8-nov): no pasa

| | Resultado | Umbral | |
|---|---|---|---|
| V1 | 0,054 | ≤ 0,07 | pasa |
| V2 | 0,745 | ≥ 0,80 | **no pasa** |
| V3 | +770 % (p = 0,110) | p < 0,05 | **no pasa** |
| V4 | −2 % (p = 0,303) | p ≥ 0,05 | pasa |
| V1b (informativo): series simuladas sin efecto, con las fechas reales | 0,055 | ≈ 0,05 | |

**Diagnóstico:** como los comunicados salen cada ~14 días, cualquier conjunto de fechas falsas con esos intervalos queda cerca de las reales. El 65 % de los días 0 a +2 falsos cae dentro de una ventana real, y el 17 % justo en los días 0 a +2 reales. Por eso la nula contiene el efecto verdadero: V3 tiene un salto enorme (el día −1 da −100 % y el día 0 da +729 %) y aun así no llega a p < 0,05, y la potencia baja. V1 pasa casi por construcción (fechas falsas frente a fechas falsas). V1b sí es una prueba de tamaño real y da 0,055.

**Resultados (informativos, todavía sin validar):** la proporción sobre El Niño da +38 % (p = 0,009) y el conteo da +39 % (p = 0,013). Pero el perfil sube en casi toda la ventana (−2: +31 %, +5: +43 %), no solo en los días 0 a +2. Eso sugiere que la referencia (los días +8 a +10 y los huecos largos) es baja, más que un salto el día del comunicado. No se interpretan hasta que el método pase.

## Ronda b (8-nov): no pasa

Cambios aprobados tras el diagnóstico de la ronda a: el contraste pasa a ser los días 0 a +2 frente a los días −3 a −1 de la misma ventana, y la inferencia usa Poisson con errores de Newey-West (retardo de 7 días). V1 y V2 se miden con 1.000 series simuladas sin efecto, con la estructura real y las fechas reales. Es un cambio de método hecho después de ver los controles, no el resultado, y se declara así.

| | Resultado | Umbral | |
|---|---|---|---|
| V1 | 0,120 | ≤ 0,07 | **no pasa** |
| V2 | 0,700 | ≥ 0,80 | **no pasa** |
| V3 | p < 0,001 (el día −1 tiene 0 citas, así que la magnitud no se interpreta) | p < 0,05 | pasa |
| V4 | −6 % (p = 0,006) | p ≥ 0,05 | **no pasa** |

**Diagnóstico:**
- **Día de la semana:** 12 de los 18 comunicados salen un viernes. Así, los días 0 a +2 son casi siempre viernes a domingo, y los días −3 a −1, martes a jueves. El contraste mide sobre todo el fin de semana. Ese efecto cambia con el tiempo (en otros temas, el fin de semana pasa de 0,595 a 0,626 del volumen de entre semana), y las variables fijas de día de la semana no lo absorben. De ahí el −6 % de V4.
- **Pocos eventos:** con 18 comunicados, Newey-West rechaza de más. El tamaño baja de 0,10 a 0,08 con retardos de 14 o 28 días, y aun así queda por encima de 0,07 (diagnóstico con 300 series, no criterio).

**Resultados (informativos, sin validar):** la proporción sobre El Niño da +17 % (p = 0,066) y el conteo da +12 % (p = 0,18).
