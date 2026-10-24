# Radar Niño Costero

Lee `README.md` para el alcance, el pipeline y el plan. Este archivo recoge las reglas para trabajar en el repo.

## Restricciones duras
- **Cero etiquetado manual.** No pidas ni propongas etiquetar datos a mano. Valida con referencias externas (comunicados, controles automáticos, métricas estándar).
- **Tiempo:** del 24-oct al 27-nov-2026 (congelamiento) entre dos personas; corte de datos el 20-nov; presentación el 1-dic sin desarrollo. Las horas son orientativas. Si algo no cabe, recórtalo en el orden del README.
- **IA generativa:** registra los prompts de esta colaboración en `docs/prompts.md`. No presentes entregables como obra original sin que el equipo lo declare. Cualquier LLM (nombrar tópicos, redactar respuestas del agente) debe declararse.
- **Scraping ético:** respeta `robots.txt` y términos de uso, limita la tasa de peticiones y nunca eludas bloqueos. Usa `requests` + `BeautifulSoup`; Playwright solo si es imprescindible.
- **Privacidad:** no guardes nombres de usuario ni identificadores personales; solo texto, fecha e id anónimo.
- **Derecho de autor:** el cuerpo de las notas se procesa en memoria y nunca se guarda ni se publica; solo titular, enlace, datos derivados y métricas. Infobae y La República están excluidos.
- **YouTube:** solo la API oficial (nunca scraping de la web); borra o refresca los datos crudos a los 30 días. Sigue las "Reglas por sitio" del README para cada medio.

## Stack
`requests`, `BeautifulSoup`, spaCy/NLTK, `scikit-learn` (TF-IDF), `sentence-transformers` (con `normalize_embeddings=True`), ChromaDB (`PersistentClient`), `gensim`/LDA, BERTopic, pysentimiento, `transformers` (NLI con `MoritzLaurer/mDeBERTa-v3-base-xnli-multilingual-nli-2mil7`), `networkx`, `google-api-python-client` (YouTube Data API v3), Streamlit.

## Qué no hacer
- No presentar el índice de discrepancia como "detector de desinformación" ni señalar medios o canales individuales como engañosos.
- No prometer métrica de exactitud para "alarmismo": el producto mide cercanía a lo oficial.
- No versionar `data/` ni modelos pesados. Única excepción: `data/urls/`, con un archivo por ejecución diaria que solo tiene dirección, número de nota, medio, fechas y sección, más el registro de sitemaps de esa ejecución (nunca títulos, cuerpo de notas ni datos de YouTube).

## Estado
Nada de lo marcado "no verificado" en el README debe darse por cierto hasta probarlo (ver "Pruebas de viabilidad"). Los sitemaps de Andina y RPP solo cubren los últimos días: la recolección de notas nuevas (`src/recolector/diario.py`) debe correr con máximo 48 h entre ejecuciones, y el histórico se recupera por las vías de "Cobertura histórica". El README es un resumen: el detalle de cada parte va en `docs/` (la recolección en `docs/recoleccion/`).
