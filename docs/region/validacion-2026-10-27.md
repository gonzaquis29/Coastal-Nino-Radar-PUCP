# Validación final de la asignación de macro-región (27-oct-2026)

Ejecución con el histórico completo (75.169 notas de 2026, titular y resumen), con los mismos criterios y umbrales de [definicion.md](definicion.md). Con esta ejecución **se congela `config/lugares.csv`**. La validación anterior, con 29.052 notas, está en [validacion-2026-10-25.md](validacion-2026-10-25.md).

## Lista de lugares congelada
`python -m radar.region.lugares` (3 peticiones al WFS del INEI, 200 s): **127 lugares en uso** (23 departamentos, 59 provincias, 45 distritos).

Cambios frente a la lista del 25-oct, por las notas de RPP leídas desde entonces (más notas de referencia con resumen):

| Nombre | Antes | Ahora | Por qué |
|--------|-------|-------|---------|
| San Martín (departamento) | se usa (87,5 %, n = 8) | no (53,8 %, n = 13) | plaza y calles San Martín de Lima |
| Apurímac (departamento) | se usa (87,5 %, n = 8) | no (77,8 %, n = 9) | por debajo del 80 % |
| Santa Rosa (distrito de Lima) | se usa (88,9 %, n = 9) | no (76,9 %, n = 13) | por debajo del 80 % |
| Camaná, Ilo (provincias) | sin medir | medidos (85,7 % y 100 %) | — |
| San Luis (distrito de Lima) | homónimo sin medir | medido (83,3 %) | — |
| Cura Mori (distrito de Piura) | sin medir | medido en El Tiempo (100 %, n = 5) | — |

San Martín y Apurímac son de "otras": sus notas pasan a "nacional", salvo que digan "región San Martín" o "región Apurímac". No afecta a costa norte, costa centro ni Lima.

## Resultado (`python -m radar.region.notas`, 236 s)
| Prueba | Criterio | 25-oct | 27-oct | Umbral | |
|--------|----------|-------:|-------:|-------:|---|
| RPP regional (sin Lima) | acierto (n = 887) | 0,902 | 0,913 | ≥ 0,85 | pasa |
| | error | 0,008 | 0,007 | ≤ 0,05 | pasa |
| | precisión de etiquetas | 0,963 | 0,944 | ≥ 0,90 | pasa |
| RPP por macro-región | costa norte (n = 318) | 0,959 | 0,965 | ≥ 0,85 | pasa |
| | costa centro (n = 126) | 0,897 | 0,929 | ≥ 0,80 | pasa |
| RPP sección Lima | acierto (n = 1.611) | 0,646 | 0,700 | ≥ 0,50 | pasa |
| | error | 0,016 | 0,018 | ≤ 0,05 | pasa |
| RPP nacionales | política y economía (n = 2.841), nacional | 0,871 | 0,830 | ≥ 0,80 | pasa (Lima: 0,109) |
| | mundo (n = 2.527), nacional | 0,994 | 0,988 | ≥ 0,95 | pasa |
| El Tiempo local | costa norte (n = 854) | 0,864 | 0,864 | ≥ 0,80 | pasa |
| Secciones regionales | Andina regionales (n = 86), fuera de Lima | 0,718 | 0,709 | ≥ 0,60 | pasa |
| | Exitosa regiones (n = 972), fuera de Lima | 0,702 | 0,695 | ≥ 0,60 | pasa |
| Corpus oficial | párrafos del ENFEN sin cambios (n = 254) | 1,0 | 1,0 | = 1,0 | pasa |

**Todas pasan.** Atención: "nacional" en política y economía bajó a 0,830, cerca del umbral, porque ahora más notas de RPP aportan su resumen y este nombra Lima (11 % de esas notas). En la pasada con cuerpo se vigila con su propio criterio (Lima solo si se nombra en titular, resumen o inicio, si no pasa).

Informativo: de las 2.251 notas sobre El Niño, 60 % quedan "nacional", 27 % costa norte, 11 % Lima, 4 % costa centro y 4 % otras (una nota puede tener varias). "Nacional" debería bajar con el cuerpo (en El Tiempo bajó de 30 % a 17 %).

## Pendiente
- Pasada con cuerpo, en el preprocesamiento (criterio ya fijado en definicion.md).
- Videos, en la vertical de YouTube (sin referencia externa de región).
