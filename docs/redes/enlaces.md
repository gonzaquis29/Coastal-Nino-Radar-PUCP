# Red de enlaces y citas (1-nov-2026)

Responde la pregunta 2 del README: qué fuentes enlazan o citan al ENFEN, al Senamhi y a Indeci, y cuáles no. Es análisis de estructura web. Los criterios se fijaron y aprobaron antes de correr.

```
python -m radar.redes.enlaces   # sin red: usa notas.csv, enlaces.csv y regiones.csv
```

## Definición
**Nodos:**
- `nota:<medio>:<id>`;
- `actor:<X>`, con los actores de `config/actores.csv`;
- `oficial:<entidad>`, para otra entidad del Estado (`gob.pe:mef`, `bcrp`);
- `dominio:<host>`, para sitios externos que no son medios del corpus (NOAA, x.com).

**Aristas,** desde las 2.378 notas sobre El Niño y sin repetir:

| Tipo | Origen |
|---|---|
| `enlace_actor` | hipervínculo a un sitio del actor (`config/instituciones_web.csv`). En `www.gob.pe` se lee la ruta (`/institucion/indeci`, `/pcm`) y en `cdn.www.gob.pe`, el nombre del PDF |
| `mencion` | el actor aparece en el texto (columna `actores`, `noticias.rasgos`) |
| `enlace_oficial` | hipervínculo a otra entidad del Estado |
| `enlace_nota` | hipervínculo a otra nota del consolidado, de cualquier tema |
| `enlace_externo` | hipervínculo a otro sitio |

Quedan fuera los enlaces internos que no llevan a una nota del consolidado (539: etiquetas como `rpp.pe/noticias/enfen`, secciones y notas de antes de 2026) y 14 enlaces oficiales sin entidad.

**Salidas** en `data/processed/red/`: `aristas.csv`, `nodos.csv` (grados y PageRank con α = 0,85; enlace y mención al mismo actor cuentan como una arista), `citas.csv` (por medio, mes y macro-región principal: cuántas notas enlazan, mencionan o hacen cualquiera de las dos cosas con cada actor) y `validacion.csv`.

**Mencionar no es citar.** "Indeci entregó ayuda" cuenta como mención. Se reporta como "enlaza o menciona", no como "cita".

## Criterios y resultado
| Criterio | Umbral | Resultado |
|---|---|---|
| **R1:** enlaces oficiales de notas sobre El Niño atribuidos a una entidad | ≥ 95 % | **pasa:** 305/319 (95,6 %). Sin entidad: la raíz de gob.pe (7), páginas de servicio ("que-es-la-leptospirosis") y una URL con errata |
| **R2:** notas de cualquier tema que enlazan a un actor y también lo mencionan (actores con ≥ 10 notas) | ≥ 90 % | **no pasa para todos:** ENFEN 34/35, Senamhi 96 %, DHN 20/20, IGP 95 %, ANA 13/14 pasan; Indeci 77 %, Cenepred 17/19 y PCM 58 % no |

R1 se midió sobre los mismos enlaces con los que se ajustaron los patrones de `instituciones_web.csv`. Es una medida de cobertura, no de una muestra.

**Diagnóstico de R2** (15 notas nuevas leídas en memoria, semilla `red-r2-diagnostico-1nov`): en 12 de las 15 el problema no son variantes que falten en los patrones. Exitosa enlaza palabras genéricas a `gob.pe/pcm` o `gob.pe/indeci`, como enlaces de SEO: "margen legal", "gestión", "constitucional", "Gobierno", "ministros de Estado". Solo faltaban "Defensa Civil" (1) y "Consejo de Ministros" (1). R2 falla porque supone que todo enlace es una cita, y para Exitosa no lo es; el detector de menciones funciona.

**Decisión:** no se amplían los patrones de `actores.csv`, porque dos casos en 15 no lo justifican y cambiar la columna `actores` exige el recálculo. La red guarda los enlaces y las menciones por separado. Al leer los resultados de Exitosa, un enlace a la PCM o a Indeci sin mención se trata como navegación, no como cita.

**Revisión cualitativa** (10 notas nuevas, semilla `red-revision-1nov`): todas las aristas eran correctas, y cada mención correspondía a una frase sobre el actor ("Senamhi recalca…", "INDECI recomienda…"). **Límite:** 5 de 10 notas no tienen ninguna arista a un actor, aunque citan a otras entidades del Estado (OECE, EsSalud, la Municipalidad de Lima, Sedapal). La red mide la cita a los actores del ENFEN y de la gestión del riesgo, no a cualquier fuente oficial. Las demás entidades solo aparecen cuando la nota las enlaza.

## Primeros resultados (informativos)
- 1.135 de las 2.378 notas sobre El Niño enlazan o mencionan algún actor o entidad oficial.
- **Enlazan o mencionan al ENFEN:** 16 % en total. Por medio: Andina 12 %, El Tiempo 21 %, Exitosa 21 % y RPP 20 %. Casi todo es por mención: solo 34 notas lo enlazan.
- **Al Senamhi:** 15 % en total; en Lima llega a 38 %, por los pronósticos del clima.
- **PageRank de los actores:** ENFEN 0,046, Senamhi 0,042, Indeci 0,030, ANA 0,021, PCM 0,016 y Cenepred 0,010.
- **Externos más enlazados:** x.com (76), El Peruano (55), Facebook (12), Wikipedia (9), NOAA (7) y la OMM (6).

No se señala a ningún medio por citar menos (CLAUDE.md): las proporciones describen la red, no califican a los medios.
