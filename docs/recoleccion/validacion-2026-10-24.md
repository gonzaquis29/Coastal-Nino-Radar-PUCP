# Validación de las fuentes de noticias (24-oct-2026)

Peticiones reales con el user-agent del proyecto (1 por segundo) y copias de sitemaps en Wayback Machine (abr-2025 → may-2026). Respalda las decisiones de [diaria.md](diaria.md) y corrige supuestos del README.

## Fechas
- `lastmod` no es fecha de publicación: en RPP, 86 de 190 notas tienen `lastmod` igual al `dateModified` de la página; en Andina difieren 3 de 169 (una por un día). Solo `news:publication_date` coincide con el `datePublished` de la página.
- Andina vuelve a fechar notas antiguas que siguen vigentes (la 1056807, de dic-2025, aparece con fecha 23-oct-2026 en el sitemap y en la página).
- El número de nota de RPP no sirve para estimar la fecha: se asigna al crear el borrador (72 inversiones de orden en 196 notas, algunas de más de 24 h).
- El ENFEN publica `lastmod` en UTC; el resto en −05:00. En 2025 RPP ponía saltos de línea dentro de las fechas.

## Completitud
- RPP: el archivo por fecha del 23-oct (Perú, Lima, actualidad, economía, mundo, deportes, fútbol; 174 notas) no tiene notas fuera de los sitemaps.
- Andina: de 300 números seguidos faltan 39 en los sitemaps en español: 25 son notas en inglés (`sitemap-en`) y 14 redirigen con 302 a `/agencia/inicio` (no publicadas).
- El Tiempo: todas las notas de `news.xml` están en la API REST.

## Clave
Con un slug alterado y el mismo número, Andina (`noticia.aspx?id=N`), RPP, Exitosa (`x-nN`) y El Tiempo (`?p=N`) redirigen con 301 a la nota correcta. Un aviso del Senamhi cambia de `-vigente` a `-detalle` al vencer; las dos formas cargan el mismo aviso.

## Ventanas
Dos lecturas del mismo sitemap separadas en el tiempo muestran si se corta por tiempo (la más antigua no cambia y el total crece) o por cantidad:
- Por tiempo: Andina `sitemap-ultimo` (desde las 00:00 de anteayer) y news (~48 h); Exitosa `sitemapNews` y El Tiempo `news.xml` (~2 días).
- Por cantidad: RPP (100 por sección, 200 en news) y secciones de Andina (64).

| Sitemap | Hoy | Histórico |
|---------|-----|-----------|
| RPP Perú | 4,1 días | 19 copias de Wayback: 4,3-8,1 días (mediana 6,2). Conteo diario de 2026 en el archivo por fecha: máximo 34 notas (21-may), ningún día en el tope de 40 de la página → ventana mínima 3,4 días (19-21 may) |
| RPP fútbol | 1,9 días | mínimo 1,4, mediana 2,5 |
| RPP news | ~1,3 días | 0,9-3,6 días (mediana 2,2) |
| RPP mundo / actualidad / lima | 4,9 / 6,7 / 7,1 días | — |
| Andina `sitemap-ultimo` | 2,5 días | sin copias en Wayback |
| Andina regionales | 1,9 días | — |
| Exitosa `sitemapNews` | 2,5 días | 6 copias: 38-55 h |

El supuesto de que el archivo de Perú cuenta lo mismo que el sitemap de Perú se comprobó el 23-oct (22 y 23 notas).

## Cambio de mes
Los mensuales de Exitosa de dic-2025 a oct-2026 se continúan (saltos de 1-4 números, sin repetidos), salvo ~54 notas del 31-may que no están ni en mayo ni en junio (responden 200 y tienen `datePublished`). El mensual se regenera a las 23:40 y el del mes siguiente da 404 hasta crearse.

## Estabilidad
El índice de RPP (33 sitemaps) y sus topes no cambian entre abr-2025 y may-2026; el de Andina (19 sitemaps) no cambia desde may-2025.

## Sitios
- Andina **sí** tiene `robots.txt` en `andina.pe/robots.txt` (`Allow: /`, modificado el 2-jul-2026); el 404 es de `/agencia/robots.txt`.
- El Tiempo: `post-sitemap1` termina el 9-oct y otros responden 503 con `Retry-After: 60` y `X-Sitemap-Cache: WARMING`. La API REST de WordPress responde (60.699 entradas) y su `robots.txt` solo bloquea `/wp-admin/`.
- ENFEN: `post-sitemap` llega al comunicado N.° 13 (julio); los recientes solo están en `wpdmpro-sitemap`.
- Senamhi: sin `robots.txt` (404); la página lista avisos desde 2021 (434 de 2026).
- `urllib.robotparser` da por permitido `/tema-el-nino`, que RPP prohíbe con `/tema*`.

## Consecuencias para el histórico
- Andina: el 301 de `noticia.aspx?id=N` también aparece en notas no publicadas, así que cada número necesita una segunda petición (~86 mil, no 43 mil); las notas en inglés comparten numeración.
- Exitosa: el hueco del 31-may se recupera por número.
- El Tiempo: usar la API REST en vez de los sitemaps.

## No verificable de antemano
Que un sitio cambie sus sitemaps durante el período. Lo detectan el registro de sitemaps y la alerta de hueco.
