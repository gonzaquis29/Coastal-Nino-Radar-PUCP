# Asignación de macro-región

Asigna a cada nota (y, más adelante, al título y la descripción de cada video) las macro-regiones del README: costa norte, costa centro, Lima, otras regiones o nacional. Lo usan el análisis por macro-región, el recomendador y el semáforo. Las mediciones que respaldan estas decisiones están en [validacion-2026-10-25.md](validacion-2026-10-25.md) y, con el histórico completo y la lista congelada, en [validacion-2026-10-27.md](validacion-2026-10-27.md).

## Uso
```bash
python -m radar.region.lugares                # lista de lugares: descarga el INEI (3 peticiones), mide y escribe config/lugares.csv
python -m radar.region.lugares --sin-descarga # vuelve a medir con data/raw/inei/
python -m radar.region.notas                  # macro-región de las notas ya leídas y validación (sin peticiones)
```
- `notas` se vuelve a correr después de cada ejecución del histórico (unos 80 s). No pide nada a los medios: lee `data/raw/noticias/`, `data/urls/` y `config/lugares.csv`.
- `lugares` se corrió por última vez al terminar el histórico (27-oct-2026), con los mismos criterios: la lista quedó **congelada** y no se vuelve a correr.
- En Python: `from radar.region.asignacion import asignar_nota` → `asignar_nota(titular, resumen, cuerpo=None)`.
- Registro detallado en `data/registros/region-*.log`. Código: `src/radar/region/` (`lugares.py`, `asignacion.py`, `referencias.py`, `notas.py`, `esquemas.py`); las expresiones de macro-región, en `radar.comun.regiones`.

## Lista de lugares (`config/lugares.csv`)
- **Fuente:** WFS de la IDE del INEI (`geoespacial.inei.gob.pe/geoserver/Interoperabilidad/ows`, capas `ig_departamento`, `ig_provincia` e `ig_distrito`, `outputFormat=csv` con `propertyName`, sin geometría). 25 departamentos, 196 provincias y 1.890 distritos con ubigeo. Coincide fila por fila con los GeoPackage que el INEI publica en `ide.inei.gob.pe` ("actualizado al 2023", fuente: V Censo Nacional Económico), y los 25 departamentos coinciden con `config/regiones.csv`. El ubigeo es el del INEI, no el de RENIEC.
- **Una fila por lugar del INEI** (2.111): `ubigeo, nivel, nombre, clave, departamento, usar, motivo, ref_n, precision, eltiempo_n, eltiempo_local, mayusculas, minusculas`. Se guardan todos para que gane siempre el nombre más largo ("San Martín de Porres" no cuenta como "San Martín"); solo asignan región los que tienen `usar=1`. La macro-región sale de `config/regiones.csv` por el departamento.
- **Alcance:** los 25 departamentos, las provincias de los 11 departamentos con litoral (columna `litoral` de `regiones.csv`) y los distritos de costa norte, costa centro y Lima.
- **Sin gentilicios ni lista de ríos:** los gentilicios ("piuranos") suman 0,3 pp; "río Piura" ya cae por "Piura".

### Decisión por nombre (medida, no a ojo)
Con la mitad de calibración de las referencias (ver "Referencias"):
1. **Con al menos 5 notas de referencia** (`MIN_MENCIONES`): se usa si ≥ 80 % (`PRECISION_MINIMA`) son de su macro-región. Un homónimo se asigna a la macro-región de sus lugares que más acierta (Comas, La Victoria y Miraflores → Lima). Así salen "Santa" (29 %) y "La Unión" (25 %).
2. **Sin medir y homónimo de un lugar de otra macro-región**, en cualquier nivel: no se usa ("Castilla" es provincia de Arequipa y distrito de Piura; "Bolívar", "Barranca").
3. **Sin medir, de Piura:** se usa si la sección local de El Tiempo concentra ≥ 60 % de sus menciones (`ELTIEMPO_LOCAL_MINIMO`; el propio "Piura" está allí en ~78 %). Entran así Paita, Sechura, Catacaos, Máncora, Chulucanas; queda fuera "Vice" (40 %).
4. **Sin medir, departamento o provincia:** se usa salvo que aparezca tanto o más en minúsculas que con mayúscula (palabra común).
5. **Sin medir, distrito:** no se usa (sin medir aparecen "Tomás", "Copa", "Asia", que también son distritos).

`motivo` dice cuál regla decidió: `medido_rpp`, `precision_baja`, `homonimo_sin_medir`, `medido_eltiempo`, `eltiempo_bajo`, `sin_medir`, `palabra_comun`, `distrito_sin_medir`, `homonimo` (otro lugar con el mismo nombre ya decidido) o `fuera_de_alcance`.

## Emparejamiento
- Se compara sin tildes y sin distinguir mayúsculas, con límites de palabra (un guion separa: "Piura-Sullana"), y se exige mayúscula inicial en cada palabra significativa del nombre ("la libertad de prensa" no es La Libertad); los titulares en mayúsculas valen.
- **Contexto administrativo:** "región/departamento/Gobierno Regional de X", "provincia/Municipalidad Provincial de X" o "distrito/Municipalidad Distrital de X" resuelven el nombre en ese nivel, aunque esté excluido, si ese nivel cae en una sola macro-región ("provincia del Santa" → costa centro, "distrito de Castilla" → costa norte).
- **Expresiones de macro-región** (`radar.comun.regiones.macroregiones_explicitas`, la misma que usa `regiones_mencionadas` para los textos oficiales): "costa norte", "norte del país", "norte peruano" → costa norte; "costa centro/central" → costa centro; "costa sur", "sur del país" → otras; "toda la costa", "litoral peruano"… → costa norte, costa centro y Lima. Que "norte del país" sea la costa norte es un supuesto declarado. Los textos oficiales no usan "otras" y no cambian (254 de 254 párrafos del ENFEN iguales).
- **Encabezado de agencia:** no hay regla. "LIMA (ANDINA)" no aparece en 12 notas de Andina de 2026 (enero y octubre) ni en 300 cuerpos de El Tiempo; el `dateline` del JSON-LD de RPP ("Lima, Perú", también en notas de Piura) no se usa. En la pasada con cuerpo se cuenta cuántos empiezan con "CIUDAD (AGENCIA)".
- Ruido conocido, declarado: "Alianza Lima" (69 menciones en titulares y resúmenes).

## Regla de asignación
- **Puntaje por macro-región:** titular × 3, resumen × 2, primeras 60 palabras del cuerpo × 2 (`PALABRAS_PRIMER_PARRAFO`, la misma de "sobre El Niño"), resto del cuerpo × 1.
- **Se asigna** cada macro-región con puntaje ≥ 2 (`UMBRAL_MACROREGION`): una mención fuera del resto del cuerpo, o dos dentro de él. Puede haber varias; **nacional** si ninguna llega. Sin regla de dispersión: solo 11 notas tocan 4 macro-regiones.
- `macroregion_principal`: la de mayor puntaje; en empate, la nombrada primero. Para el recomendador y el semáforo.
- **Lima** (Lima y Callao) va aparte; para avisos se usa `regiones.macroregion_de_avisos` (costa centro), sin otra tabla.

## De dónde sale el texto
- El cuerpo no se guarda. **Ahora:** desde titular y resumen de `notas.csv` (`fuente_texto=titular_resumen`).
- **En el preprocesamiento:** la etapa de NLP relee cada cuerpo una sola vez con `Medio.leer` y llama a `asignar_nota(titular, resumen, cuerpo)` en el mismo recorrido (`fuente_texto=cuerpo`), reemplazando la fila.
- **No se agregan columnas a `notas.csv`:** `anexar_csv` no revisa el encabezado, así que cambiar las columnas mientras corre el histórico desalinearía las filas. La región va en `data/processed/noticias/regiones.csv` (no se versiona): `medio, id, macroregiones, macroregion_principal, departamentos, lugares, puntajes, fuente_texto, version_lugares` (huella de `lugares.csv`).
- **Videos (vertical YouTube):** la misma clase `Asignador`, con el título × 3 y la descripción como resumen (sus primeras 60 palabras × 2, el resto × 1), sin URL y sin las líneas que se repiten en ≥ 3 videos del mismo canal (plantillas del canal: "Suscríbete…", la dirección del canal). Se escribe cuando exista la vertical. No hay referencia externa de región para videos: solo se reporta la distribución.

## Referencias (sin etiquetado manual)
| Referencia | Qué mide |
|------------|----------|
| Sección de la dirección de RPP: `/peru/<departamento>/` y `/lima/` (la lista del archivo trae el título de todas) | departamento exacto |
| RPP `politica`, `economia`, `mundo` | ruido de lugar en notas nacionales |
| Sección `local` de El Tiempo (diario de Piura) | costa norte |
| Secciones `regionales` y `locales` de Andina, vistas por la recolección diaria (sitemaps por sección) | fuera de Lima frente a Lima |
| Sección `exitosa-peru` de Exitosa | fuera de Lima |
| Párrafos del ENFEN de `data/oficial/` | que la función compartida no cambie el corpus oficial |

Las notas se parten en dos mitades fijas por el hash de su id (`referencias.mitad`): con la de calibración se decide la lista y con la de evaluación se mide. Andina y Exitosa no intervienen en la decisión. La página de sección de Andina muestra solo ~10 notas, sin paginación: no sirve para el histórico.

## Criterios de pasa / no pasa (fijados antes de construir)
Con titular y resumen, sobre la mitad de evaluación. *Acierto:* la macro-región de referencia está entre las asignadas. *Error:* se asignó otra y no esa. *Precisión de etiquetas:* parte de las etiquetas asignadas (sin "nacional") que son la de referencia.

| Prueba | Pasa si | Si no pasa |
|--------|---------|------------|
| RPP regional (sin Lima) | acierto ≥ 85 %, error ≤ 5 %, precisión de etiquetas ≥ 90 % | Revisar en la mitad de calibración los nombres que causan los errores |
| RPP por macro-región | costa norte ≥ 85 %, costa centro ≥ 80 % | Lo mismo, en esa macro-región |
| RPP sección Lima | acierto ≥ 50 %, error ≤ 5 % | Lima se reporta con cobertura parcial, declarada |
| RPP nacionales | "nacional" ≥ 80 % en política y economía; ≥ 95 % en mundo | Exigir que Lima se nombre en titular, resumen o inicio |
| El Tiempo local | costa norte ≥ 80 % | Revisar los nombres de Piura |
| Secciones regionales | Andina regionales y Exitosa regiones: fuera de Lima ≥ 60 % | Declarar |
| Corpus oficial | 100 % de los párrafos del ENFEN con las mismas macro-regiones | Corregir la función compartida |
| Pasada con cuerpo (en el preprocesamiento) | acierto en El Tiempo local no baja más de 2 pp frente a titular y resumen; "Lima" en su sección nacional ≤ 35 % | Lima solo si se nombra en titular, resumen o inicio |

Se calculan en cada ejecución de `notas` y quedan en `data/processed/region/validacion.csv`.

## Limitaciones declaradas
Las macro-regiones son una agrupación supuesta (README). Los titulares de RPP suelen empezar con el lugar ("Piura: …"): la referencia mide bien la precisión de los nombres, pero no la cobertura de notas sin lugar explícito. Las provincias poco frecuentes se usan sin medir. El efecto del cuerpo solo se midió en El Tiempo. Los videos no tienen referencia de región. La lista del INEI es de 2023; no se verificó si se crearon distritos después.
