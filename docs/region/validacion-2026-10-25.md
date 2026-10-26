# Validación de la asignación de macro-región (25-oct-2026)

Criterios fijados antes de construir ([definicion.md](definicion.md)). Datos: las 29.052 notas de 2026 que el histórico ya había leído (titular y resumen; el cuerpo no se guarda) y la lista del archivo de RPP. Las mediciones se hicieron sin chocar con el histórico en curso.

## Peticiones hechas
| Sitio | Peticiones | Para qué |
|-------|-----------:|----------|
| `geoespacial.inei.gob.pe` (WFS) | 3 + 3 | ubigeos (prototipo y ejecución) |
| `ide.inei.gob.pe` | 3 archivos RAR | comparar con el WFS |
| Andina | 15 notas y 3 páginas de sección | encabezado de agencia y sección de la nota |
| RPP, Exitosa | 1 nota cada uno | metadatos de lugar |
| El Tiempo (API) | 3 lotes de 100 | efecto del cuerpo (en memoria; solo se guardaron conteos) |

## Lista de lugares
- El WFS y los GeoPackage del INEI coinciden fila por fila (25 departamentos, 196 provincias, 1.890 distritos, mismos ubigeos y nombres); los departamentos coinciden con `config/regiones.csv`. El portal de datos abiertos pide iniciar sesión y el sistema de consulta de ubigeos del INEI (puerto 8080) no respondió.
- Resultado: **128 lugares en uso** (25 departamentos, 59 provincias, 44 distritos). Excluidos por medición: Santa (29 % en su macro-región, n = 7), La Unión (25 %, n = 8), San Marcos, Chilca, Santa María. Excluidos por homónimos sin medir: Castilla, Bolívar, Barranca, Yauyos, Julcán, Ocros, Asunción, Huancabamba, entre otros. Los 25 departamentos se miden con ≥ 86,7 % (el menor, Huancavelica).

## Prototipo (antes de fijar la definición)
Mitad de evaluación de RPP, titular y resumen:

| Variante | Costa norte | Costa centro | Sección Lima | Nacional en política y economía |
|----------|------------:|-------------:|-------------:|-----:|
| Departamentos y provincias | 93,1 % | 88,1 % | 32,0 % | 89,9 % |
| + distritos medidos | 94,3 % | 89,7 % | 60,7 % | 88,9 % |
| + gentilicios | 94,3 % | 89,7 % | 61,0 % | 88,8 % |

Los gentilicios no aportan y se descartaron. Con el cuerpo (300 notas de El Tiempo, pesos 3-2-2-1):

| Grupo | Titular y resumen | Con cuerpo |
|-------|------------------:|-----------:|
| Sección local → costa norte | 82 % | 90 % |
| Notas sobre El Niño → nacional | 30 % | 17 % |
| Sección nacional → Lima | 18 % | 32 % |

Ningún cuerpo de esas 300 notas ni de 12 notas de Andina empieza con un encabezado "CIUDAD (AGENCIA)".

## Resultado (`python -m radar.region.notas`)
| Prueba | Criterio | Valor | Umbral | |
|--------|----------|------:|-------:|---|
| RPP regional (sin Lima), n = 886 | acierto | 0,902 | ≥ 0,85 | pasa |
| | error | 0,008 | ≤ 0,05 | pasa |
| | precisión de etiquetas | 0,963 | ≥ 0,90 | pasa |
| RPP por macro-región | costa norte (n = 317) | 0,959 | ≥ 0,85 | pasa |
| | costa centro (n = 126) | 0,897 | ≥ 0,80 | pasa |
| RPP sección Lima, n = 1.606 | acierto | 0,646 | ≥ 0,50 | pasa |
| | error | 0,016 | ≤ 0,05 | pasa |
| RPP nacionales | política y economía (n = 2.835), nacional | 0,871 | ≥ 0,80 | pasa (Lima: 0,081) |
| | mundo (n = 2.512), nacional | 0,994 | ≥ 0,95 | pasa |
| El Tiempo local, n = 853 | costa norte | 0,864 | ≥ 0,80 | pasa |
| Secciones regionales | Andina regionales (n = 39), fuera de Lima | 0,718 | ≥ 0,60 | pasa |
| | Exitosa regiones (n = 890), fuera de Lima | 0,702 | ≥ 0,60 | pasa |
| Corpus oficial | párrafos del ENFEN sin cambios (n = 254) | 1,0 | = 1,0 | pasa |

**Todas pasan.** Informativo: de las 797 notas sobre El Niño leídas hasta ahora, 55 % quedan "nacional", 36 % costa norte, 10 % Lima, 4 % costa centro y 3 % otras (una nota puede tener varias). La pasada con cuerpo debería bajar "nacional" (en El Tiempo bajó de 30 % a 17 %).

## Errores que quedan
En la mitad de evaluación, la mayoría de las etiquetas "erradas" son menciones legítimas de otra región: una nota de la sección Lima de RPP sobre un vuelo a Arequipa, o "Lima" dentro de una nota regional. Errores reales: "Sánchez Carrión" (hospital y persona, provincia sin medir) y "San Martín" en notas de Lima (plaza o calle).

## Pendiente
- Volver a medir la lista con los mismos criterios al terminar el histórico y congelarla; Andina regionales tiene hoy solo 39 notas.
- Prueba de la pasada con cuerpo, en el preprocesamiento.
- Videos: sin referencia externa de región.
