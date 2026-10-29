# Recálculo de las notas ya leídas (28-oct-2026)

**Responsabilidad única:** volver a leer las ~76.000 notas de `data/raw/noticias/<medio>/notas.csv` con el código actual y reemplazar `notas.csv` y `enlaces.csv` sin perder nada si se corta. El código actual incluye el cuerpo limpio, el resumen sin enlaces y la regla de magnitud única. Antes del reemplazo se mide y se explica cada cambio. Código: `src/radar/noticias/recalculo.py`; se lanza desde `historico`.

## Uso
```bash
python -m radar.noticias.historico --recalcular                # fase 1 (~45 min): se detiene en el punto de control
python -m radar.noticias.historico --recalcular --todo --horas 11   # fase 2 (~10 h); se puede cortar y relanzar
python -m radar.noticias.historico --recalcular --informe      # criterios sobre lo ya releído
python -m radar.noticias.historico --recalcular --aplicar      # solo si todo está releído y pasan los criterios
python -m radar.region.notas
python -m radar.noticias.viabilidad resultados
```
- **Fase 1:** las notas que mencionaban a El Niño, más El Tiempo completo, que va por su API. Dentro de la fase, primero las filas de control (ver M1b).
- **Fase 2:** el resto.
- **Rutina diaria entre noches:** cortar con Ctrl+C, correr la rutina y relanzar. El candado impide que dos procesos pidan páginas a la vez, y las notas nuevas también se releen.
- **Laptop:** enchufada, con la tapa abierta, en "Máximo rendimiento" y con ASUS en "Rendimiento dinámico". El proceso pide a Windows que no se suspenda por inactividad, pero eso no evita la suspensión al cerrar la tapa.

## Cómo sobrevive a cortes y apagones
- **Todo va aparte,** en `data/raw/noticias/<medio>/recalculo/`: `notas.csv`, `enlaces.csv`, `cambios.csv` y `estado.json`. Los archivos actuales no se tocan hasta `--aplicar`.
- **Un compromiso por nota:** primero sus enlaces, luego su cambio y al final su fila, que la marca como hecha. Cada escritura se fuerza al disco (`fsync`, también en `escribir_atomico`). Al reanudar se corta una línea a medias (`archivos.reparar_csv`) y se descartan los enlaces y cambios sin fila.
- **Errores:**
  - de red: cuentan una vez por ejecución, hasta 3; una suspensión no descarta notas;
  - HTTP: hasta 3 intentos;
  - medio suspendido por fallos seguidos: espera 10 min y reintenta, hasta 3 veces;
  - bloqueo: ese medio se detiene, sin eludir nada.
- **Notas que ya no existen** o agotan sus intentos: se conserva su fila y sus enlaces anteriores, y quedan marcadas "sin releer" en `cambios.csv`.
- **Lo que se conserva de cada fila:** `via`, `muestra`, `candidata_por` y `recolectado`, que dicen cómo entró la nota.
- **`--aplicar`** reescribe los archivos nuevos en el orden de los actuales y renombra los actuales a `*.anterior.csv`, que se conservan hasta que se decida borrarlos. La fase del reemplazo queda en `estado.json`: un corte a mitad se termina al volver a correr.
- **Candado:** `radar.comun.candado`, en `data/red.lock`. Lo usan todos los procesos que piden páginas. Guarda el pid y la hora de inicio del proceso, para que un pid reusado tras un reinicio no lo bloquee. Si el proceso murió, el candado se toma igual.

## `cambios.csv` (sin texto)
Por nota: estado y motivo; antes y después de "sobre El Niño", "menciona", magnitudes, comunicados y número de enlaces; si cambió el resumen; si se editó la página; la causa de cada cambio.

La causa sale **paso a paso**, con el código que produjo la fila guardada. La generación de código se sabe por `recolectado`, cruzado con las fechas de los commits:
- anterior: hasta el 28-oct a las 12:45;
- capa1: cuerpo limpio;
- resumen: resumen sin enlaces;
- actual: regla de magnitud única.

Pasos:
1. **Cuerpo:** antes frente a lo que da el código anterior sobre el texto nuevo. Se clasifica como:
   - "edicion", si cambió `fecha_modificacion`. En Andina esa fecha es la de la consulta, así que allí la edición solo se detecta por el `sha1` del cuerpo en las filas ya limpias;
   - "capa1";
   - "capa1_o_edicion", en Andina;
   - "sin_causa", si el cuerpo ya era el limpio y cambió sin edición.
2. **Regla:** regla de magnitud anterior frente a la nueva.
3. **Resumen:** resumen viejo frente al nuevo.

## Criterios (fijados antes de correr)
| | Criterio | Pasa si | Resultado (28-oct) |
|---|---|---|---|
| B1 | Pruebas sintéticas: un corte en cada escritura posible, con la línea a medias, y un corte a mitad del reemplazo. Reanudado, el resultado es idéntico a una corrida sin cortes | 100 % | Pasa (18 cortes). Control: con la reparación desactivada, la prueba falla |
| B2 | Corrida real (`--limite 15`) cortada dos veces con `taskkill /F`: 0 ids repetidos, 0 filas mal formadas, todos los enlaces y cambios con nota | sí | Pasa (135 notas) |
| B3 | Un segundo proceso se niega a correr y un candado de un proceso muerto se toma | sí | Pasa (código 2; el candado se tomó tras cada corte) |
| B4 | El estado de ejecución de Windows pide no suspender mientras corre y lo libera al salir | sí | Pasa (0x1 mientras corre, 0x0 antes y después) |
| M1a | La regla de magnitud anterior reproducida da lo mismo que el código anterior (git 7fc3477) en todos los titulares y resúmenes | 100 % | Pasa (228.741/228.741) |
| M1b | Las 183 filas guardadas ya con el cuerpo limpio, sin edición, se reproducen con el resumen y la regla anteriores. Sin filas de control no pasa | ≥ 99 % | Punto de control |
| M2 | Cambios con causa identificada | 100 % | Punto de control |
| M3 | Cambio neto en "sobre El Niño", sin el resumen de El Tiempo. En el punto de control es parcial (la fase 1 se elige con el "menciona" guardado); antes de `--aplicar`, completo | ≤ 5 % | Punto de control |
| M4 | Notas sin releer, por medio | ≤ 1 % | Punto de control |
| M5 | Integridad: cada id del archivo actual una vez, enlaces con nota, columnas del esquema | 100 % | Al aplicar |

La primera corrida real mostró que M1b pasaba sin datos (0/0): las filas de control están al final del archivo. Se corrigió antes de seguir. Sin filas de control, M1b no pasa, y la fase 1 las relee primero.
