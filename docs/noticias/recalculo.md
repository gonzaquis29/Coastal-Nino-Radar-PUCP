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
- regla: regla de magnitud única;
- actual: sin titulares ajenos en el cuerpo (29-oct a las 21:55);
- rescate: RPP, recomendados sin cerrar (31-oct a las 11:41).

Como `recolectado` se conserva al recalcular, después de aplicar ya no dice con qué código se calculó la fila. `PISO_DE_GENERACION` lo fija: los archivos aplicados el 31-oct se calcularon enteros con "actual", y ninguna fila es más vieja.

Pasos:
1. **Cuerpo:** antes frente a lo que da el código anterior sobre el texto nuevo. Se clasifica como:
   - "edicion", si cambió `fecha_modificacion`. En Andina esa fecha es la de la consulta, así que allí la edición solo se detecta por el `sha1` del cuerpo en las filas ya limpias;
   - "capa1";
   - "capa1_o_edicion", en Andina;
   - "sin_causa", si el cuerpo ya era el limpio y cambió sin edición.
2. **Titulares ajenos** ("ajenos"): el cuerpo como salía antes de quitarlos (`cuerpo_con_ajenos`, en memoria) frente al nuevo. El paso 1 usa ese cuerpo previo, así que una nota cuyo cuerpo solo cambió por esto no se toma por editada, y M1b mide lo mismo que antes ([texto.md](texto.md#titulares-ajenos-sin-rótulo-29-oct-2026)).
   En las filas "actual" este paso es **"rescate"**: el cuerpo como lo sacaba el código "actual" (`cuerpo_sin_rescate`, en memoria: sin el rescate ni los tres selectores nuevos de RPP) frente al nuevo ([texto.md](texto.md#recomendados-sin-cerrar-en-rpp-31-oct-2026)).
3. **Regla:** regla de magnitud anterior frente a la nueva.
4. **Resumen:** resumen viejo frente al nuevo.

## Criterios (fijados antes de correr)
| | Criterio | Pasa si | Resultado (28-oct) |
|---|---|---|---|
| B1 | Pruebas sintéticas: un corte en cada escritura posible, con la línea a medias, y un corte a mitad del reemplazo. Reanudado, el resultado es idéntico a una corrida sin cortes | 100 % | Pasa (18 cortes). Control: con la reparación desactivada, la prueba falla |
| B2 | Corrida real (`--limite 15`) cortada dos veces con `taskkill /F`: 0 ids repetidos, 0 filas mal formadas, todos los enlaces y cambios con nota | sí | Pasa (135 notas) |
| B3 | Un segundo proceso se niega a correr y un candado de un proceso muerto se toma | sí | Pasa (código 2; el candado se tomó tras cada corte) |
| B4 | El estado de ejecución de Windows pide no suspender mientras corre y lo libera al salir | sí | Pasa (0x1 mientras corre, 0x0 antes y después) |
| M1a | La regla de magnitud anterior reproducida da lo mismo que el código anterior (git 7fc3477) en todos los titulares y resúmenes | 100 % | Pasa (228.741/228.741) |
| M1b | Las 183 filas guardadas ya con el cuerpo limpio, sin edición, se reproducen con el resumen y la regla anteriores. Sin filas de control no pasa | ≥ 99 % | Pasa (24/24 en la fase 1) |
| M2 | Cambios con causa identificada | 100 % | Pasa (fase 1) |
| M3 | Cambio neto en "sobre El Niño", sin el resumen de El Tiempo. En el punto de control es parcial (la fase 1 se elige con el "menciona" guardado); antes de `--aplicar`, completo | ≤ 5 % | Pasa en la fase 1 (1,3 %) |
| M4 | Notas sin releer, por medio | ≤ 1 % | Pasa en la fase 1 (0) |
| M5 | Integridad: cada id del archivo actual una vez, enlaces con nota, columnas del esquema | 100 % | Al aplicar |

### Punto de control (29-oct, fase 1: 9.402 notas, 42,6 min)
Pasan M1b (24/24), M2 (0 sin causa), M3 (neto +30 de 2.326 = 1,3 %) y M4 (0 sin releer en los 4 medios). M5 queda pendiente de la fase 2. Además: 0 errores, 0 errores de red; ningún comunicado citado cambia; enlaces de 19.319 a 9.163, porque se quitan los recomendados.

| Cambio | Notas | Diagnóstico (muestra de 3 por grupo, releyendo la página y reproduciendo la extracción anterior) |
|---|---|---|
| "Sobre El Niño" 1→0 por el resumen (El Tiempo) | 34 | El titular ajeno del resumen; la estimación sin red daba como máximo 37 |
| "Sobre El Niño" 0→1, Andina | 42 | El titular repetido, el subtítulo, el crédito "ANDINA/Archivo" y la hora y lugar empujaban a El Niño fuera de las primeras 60 palabras |
| "Sobre El Niño" 1→0, Andina | 22 | El Niño estaba en el pie de foto o en un bloque que ya no es cuerpo; en Andina no se distingue de una edición |
| "Sobre El Niño" 0→1 y 1→0, RPP | 15 y 6 | "Compartir … Share" y el titular repetido empujaban a El Niño fuera del inicio; y al revés, El Niño estaba solo en títulos del reproductor de video o de recomendados ("Burneo advirtió que el Fenómeno del Niño…" en una nota del JNE) |
| Magnitudes que se pierden por el texto | 237 | Venían de titulares de otras notas ("Te recomendamos", "Lee también: ENFEN alerta que El Niño podría alcanzar una magnitud extraordinaria") o, en Andina, de "frases" de 64 a 250 palabras con párrafos pegados que mezclaban El Niño con vientos o temperatura |
| Magnitudes por la regla | 198 | 141 ganan (127 notas pasan de ninguna a alguna) y 53 pierden: el efecto validado en [../nlp/magnitud.md](../nlp/magnitud.md) |

Notas con magnitud: de 600 a 454.

La primera corrida real mostró que M1b pasaba sin datos (0/0): las filas de control están al final del archivo. Se corrigió antes de seguir. Sin filas de control, M1b no pasa, y la fase 1 las relee primero.

### Corrida completa sin aplicar (29-oct, 582 min) y segunda corrida
La fase 2 terminó con M1b a M5 en verde (M1b 178/178; M3 neto +31 de 2.334; 0 sin releer; integridad completa). Revisada antes de aplicar:
- **Bien:** `via`, `muestra`, `candidata_por` y `recolectado` idénticos; las 14 notas que pasan a `sin_texto` son notas reales de 40 a 50 palabras (o, en RPP, páginas cuyo "texto" anterior eran recomendados); las 1.135 que pierden "menciona El Niño" la tenían por "Lea/Lee también", listas de recomendados o el resumen de El Tiempo (muestra de 7, releídas); Exitosa gana 31 por citas textuales que antes se perdían.
- **Mal:** ningún criterio medía "menciona El Niño". De las 80 notas que la ganaban, 47 (Andina y RPP) la ganaban por un titular de otra nota sin rótulo dentro del cuerpo. Se corrigió en la capa 1 y se validó ([texto.md](texto.md#titulares-ajenos-sin-rótulo-29-oct-2026)).

No se aplicó. Lo recalculado quedó aparte en `recalculo.29oct-con-ajenos/`, y el recálculo se relanzó completo (los 4 medios) con el código corregido.

Antes de aplicar la segunda corrida se revisan también, caso por caso, los cambios de "menciona El Niño" y de `sin_texto`. Es una revisión informativa, sin umbral.

### Segunda corrida y aplicación (30 y 31-oct, 526 min)
Corrió del 29-oct en la noche al 30-oct, con un apagado de la laptop en medio (reanudó sin notas repetidas). Pasa M1b a M5 sin alertas: M1b 178/178; M2 0; M3 neto +30 de 2.334 (1,3 %); 0 notas sin releer; integridad completa en los 4 medios.

Revisión antes de aplicar, frente a la corrida 1:
- Exitosa, El Tiempo y `sin_texto` (14 notas) quedan idénticos.
- 82 notas de Andina y RPP dejan de mencionar El Niño. 47 son las de `gana.txt`, que vuelven a su valor anterior. Las otras 35 ya la tenían en la extracción anterior; releídas una por una, en las 35 la mención estaba solo en un titular ajeno quitado y en ninguna en el texto propio. El único cambio en "sobre El Niño" (Andina 1076761) tiene la misma causa. Las 35 quedaron en `notas_vistas.csv`.

Se aplicó el 31-oct. Los archivos aplicados son iguales, fila por fila, a los recalculados. Los enlaces bajan de 292.921 a 124.451 (ya no entran los recomendados).

Después del recálculo (`viabilidad resultados`, notas del 1-ene al 24-oct):

| Medida | Antes | Después |
|---|---|---|
| Notas sobre El Niño | 2.236 (Andina 1.119, RPP 452, Exitosa 336, El Tiempo 329) | 2.230 (Andina 1.135, RPP 461, Exitosa 337, El Tiempo 297) |
| Control positivo (enlace / número / extensiones) | 5 / 31 / 41 | 5 / 31 / 41 |
| Cuerpo con ≥ 40 % del resumen | 99,25 % | 99,33 % |
| RPP: cuerpo con ≥ 90 % del `articleBody` | 99,97 % (5 no) | 99,77 % (44 no) |

`region.notas` pasa sus 7 pruebas. De las 2.370 notas sobre El Niño (todo el período), 62 % quedan "nacional", 25 % costa norte, 11 % Lima y 4 % costa centro.

**La baja en RPP frente al `articleBody` se diagnosticó caso por caso (6 notas releídas).** Muestra un error de la capa 1, anterior a la regla de titulares ajenos:
- En ~25 notas de RPP (sobre todo de enero y febrero, de la serie del Rotafono), el HTML no cierra el bloque "Te recomendamos". El resto de la nota y la barra lateral quedan dentro de él, así que al quitarlo se pierde prosa real y entran rótulos como "Lo más leído" o "En Vivo".
- No toca "sobre El Niño", las magnitudes ni los comunicados. Pierden "menciona El Niño" 3 notas que no son sobre El Niño.
- En otras notas el cuerpo crece y no falta ninguna frase del `articleBody`. Ahí la baja es del instrumento y está por revisar.

Pendiente en [pendientes.md](../pendientes.md).

## Segunda pasada: RPP con el rescate (31-oct)
Adaptación aprobada antes de correr:
- `PISO_DE_GENERACION`: las filas aplicadas son de la generación "actual".
- La generación "rescate" y su paso de causa, con `cuerpo_sin_rescate`.
- M1b controla con las filas de `GENERACION_DE_CONTROL` ("actual") sin edición. Antes eran las de "capa1". En una segunda pasada son todas las filas, así que el control es el más amplio posible.
- `--informe` y `--aplicar` respetan `--medio`.

Los criterios M1b a M5 y sus umbrales no cambian. Antes de aplicar se revisan, caso por caso, los cambios de "menciona El Niño" y de `sin_texto`.

Control previo con 6 notas reales ya vistas: el cuerpo sin rescate reproduce el `sha1` guardado en 6/6, y solo cambia el de las 2 rescatadas.

Lo recalculado de la primera pasada, ya aplicado, queda en `recalculo.31oct-aplicado/`.
Los archivos de antes de la primera pasada se renombraron a `*.antes-del-recalculo.csv`: `--aplicar` solo crea `*.anterior.csv` si no existe, y sin el cambio el segundo reemplazo no habría guardado los archivos vigentes.

```bash
python -m radar.noticias.historico --recalcular --medio rpp --todo --horas 7
python -m radar.noticias.historico --recalcular --medio rpp --aplicar   # con aprobación
```

### Resultado y aplicación (31-oct)
La corrida terminó a las 17:44: 19.849 notas en 332 min, 0 errores de red. M1b 19.840/19.840, M2 0, M3 neto +0 de 492, M4 0/19.849, M5 sí.

Ninguna nota cambia magnitudes, "sobre El Niño", "menciona El Niño" ni comunicados. Cambia el cuerpo de 3.061 notas:

| Notas | Palabras | Enlaces | Qué es |
|---|---|---|---|
| 2.141 | −8 | −2 | recuadro "Síguenos en Google News / WhatsApp" (`article__follow`) |
| 838 | −40 | −3 | ese recuadro y la caja del Rotafono |
| ~60 | −18 a −27 | −8 a −13 | recuadro y etiquetas de la barra lateral (`column-fixed`) |
| 10 | +25 a +173 | — | texto rescatado de los recomendados sin cerrar; `cuerpo_vs_ld` de 0,49–0,88 a 1,0 |

`cuerpo_vs_ld` sube en 11.287 notas por la tolerancia de ítems pegados (instrumento) y baja apenas en 2 notas del Rotafono, 1672096 (0,647 → 0,640) y 1674393 (0,513 → 0,509), por la caja y la barra lateral que se quitan.
9 páginas fueron editadas por RPP desde la primera lectura (titulares y fechas). Una, `live-3679`, pasa a `sin_texto` porque el en vivo se volvió un historial de 7 palabras.

Aplicado con aprobación y verificado fila por fila: notas 19.849 y enlaces 49.639, iguales a lo recalculado.
`notas.anterior.csv` y `enlaces.anterior.csv` son los vigentes de antes, y lo recalculado queda en `recalculo.31oct-rescate-aplicado/`.
`region.notas` da los mismos resultados que antes.
En `viabilidad resultados`, RPP con ≥ 0,9 del articleBody pasa de 0,9977 a 0,9994 (18.735/18.747), y `sin texto` de 382 a 383. Las 2.230 notas sobre El Niño no cambian.

Quedan 13 notas de RPP con cobertura menor a 0,9 (8 del Rotafono). Su texto no queda después de la lista de recomendados, así que el rescate no las cubre: ver `docs/pendientes.md`.
