# Radar Niño Costero

Lee `README.md` para el alcance, el pipeline y el plan. Este archivo recoge las reglas para trabajar en el repo.

## Restricciones duras
- **Cero etiquetado manual.** No pidas ni propongas etiquetar datos a mano. Valida con referencias externas (comunicados, controles automáticos, métricas estándar).
- **Tiempo:** del 24-oct al 27-nov-2026 (congelamiento) entre dos personas; corte de datos el 20-nov; presentación el 1-dic sin desarrollo. Las horas son orientativas. Si algo no cabe, recórtalo en el orden del README.
- **IA generativa:** registra los prompts de esta colaboración en `docs/prompts.md`. No presentes entregables como obra original sin que el equipo lo declare. Cualquier LLM (nombrar tópicos, redactar respuestas del agente) debe declararse.
- **Scraping ético:** respeta `robots.txt` y términos de uso, limita la tasa de peticiones y nunca eludas bloqueos. Usa `requests` + `BeautifulSoup` (`lxml` para sitemaps XML); Playwright solo si es imprescindible.
- **Privacidad:** no guardes nombres de usuario ni identificadores personales; solo texto, fecha e id anónimo.
- **Derecho de autor:** el cuerpo de las notas se procesa en memoria y nunca se guarda ni se publica; solo titular, enlace, datos derivados y métricas. Infobae y La República están excluidos.
- **YouTube:** solo la API oficial (nunca scraping de la web); borra o refresca los datos crudos a los 30 días. Sigue las "Reglas por sitio" del README para cada medio.

## Stack
`requests`, `BeautifulSoup`, PyMuPDF (PDF de comunicados; `pypdf` solo como control), spaCy/NLTK, `scikit-learn` (TF-IDF), `sentence-transformers` (con `normalize_embeddings=True`), ChromaDB (`PersistentClient`), `gensim`/LDA, BERTopic, pysentimiento, `transformers` (NLI con `MoritzLaurer/mDeBERTa-v3-base-xnli-multilingual-nli-2mil7`), `networkx`, `google-api-python-client` (YouTube Data API v3), Streamlit.

## Código
- Todo vive en el paquete `src/radar/` (`pip install -e ".[dev]"`; se ejecuta con `python -m radar.<paquete>.<módulo>`): nada de `sys.path.insert` ni scripts sueltos. Cada vertical nueva es un subpaquete (`noticias/`, `youtube/`, `nlp/`, `modelos/`, `app/`) con sus pruebas en `tests/<subpaquete>/`.
- Valores que pueden cambiar (fechas del proyecto, user-agent, ritmo, reintentos, hosts, rutas) solo en `src/radar/config.py`; listas de referencia (regiones, estaciones) en `config/*.csv`; vocabulario compartido (estados, niveles, temas) en un único módulo; umbrales de reglas como constantes con nombre al inicio del módulo.
- Peticiones web solo con `radar.comun.http.Cliente` (robots.txt, ritmo, reintentos, hosts caídos); archivos con `radar.comun.archivos` (escritura atómica, rutas seguras); columnas de cada CSV en un esquema único.
- Un documento o una fuente que falla no detiene a los demás; el detalle va al registro (`logging`, `data/registros/`) y el resumen a pantalla.
- Nombres descriptivos en español sin tildes; comentarios y textos con buena ortografía; comentarios solo donde aportan. `ruff format`, `ruff check` sin errores y `pytest` en verde antes de cada commit.

## Qué no hacer
- No presentar el índice de discrepancia como "detector de desinformación" ni señalar medios o canales individuales como engañosos.
- No prometer métrica de exactitud para "alarmismo": el producto mide cercanía a lo oficial.
- No versionar `data/` ni modelos pesados. Excepciones: `data/urls/`, con un archivo por ejecución diaria que solo tiene dirección, número de nota, medio, fechas y sección, más el registro de sitemaps de esa ejecución (nunca títulos, cuerpo de notas ni datos de YouTube); y `data/oficial/`, el corpus oficial derivado (comunicados del ENFEN y avisos del Senamhi en párrafos, textos oficiales del art. 9.b del D. Leg. 822), que la app necesita en el repo. Los PDF y páginas crudas van en `data/raw/oficial/` y no se versionan. Las notas leídas (`data/raw/noticias/`, `data/processed/noticias/`) tampoco: tienen titulares y resúmenes. Las pruebas no usan notas reales como fixtures (el repo es público): solo HTML sintético.

## Estado
Nada de lo marcado "no verificado" en el README debe darse por cierto hasta probarlo (ver "Pruebas de viabilidad"). Los sitemaps de Andina y RPP solo cubren los últimos días: la recolección de notas nuevas (`python -m radar.recoleccion.diario`) debe correr con máximo 48 h entre ejecuciones, y el histórico se recupera por las vías de "Cobertura histórica". El corpus oficial se construye con `python -m radar.oficial.corpus` (definición en `docs/oficial/definicion.md`); la vigencia por fecha y macro-región se consulta con `radar.oficial.vigencia.Corpus`, no recalculándola en cada componente. Las notas de los 4 medios (histórico y nuevas de `data/urls/`) se leen con `python -m radar.noticias.historico` y quedan en `data/processed/noticias/notas.csv` sin el cuerpo; las etapas que necesiten el cuerpo (NLP, NLI, embeddings) lo vuelven a leer en memoria con `Medio.leer` de `radar.noticias.medios`, sin guardarlo ni cachearlo. "Sobre El Niño" y los comunicados citados se calculan solo en `radar.noticias.rasgos`. La macro-región de un texto se calcula solo con `radar.region.asignacion` (lista de lugares en `config/lugares.csv`, decidida por medición con `python -m radar.region.lugares`; las expresiones como "costa norte" en `radar.comun.regiones`), y la de las notas queda en `data/processed/noticias/regiones.csv` (`python -m radar.region.notas`); no agregues columnas a `notas.csv` mientras el histórico escribe en él. El README es un resumen: el detalle de cada parte va en `docs/` (la recolección en `docs/recoleccion/`, el corpus oficial en `docs/oficial/`, las noticias en `docs/noticias/`, la macro-región en `docs/region/`).
