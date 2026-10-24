# Radar Niño Costero

Lee `README.md` para el alcance, el pipeline y el plan. Este archivo recoge las reglas para trabajar en el repo.

## Restricciones duras
- **Cero etiquetado manual.** No pidas ni propongas etiquetar datos a mano. Valida con referencias externas (comunicados, controles automáticos, métricas estándar).
- **Tiempo:** 4 semanas entre dos personas; las horas son orientativas. Si algo no cabe, recórtalo en el orden del README.
- **IA generativa:** registra los prompts de esta colaboración en `docs/prompts.md`. No presentes entregables como obra original sin que el equipo lo declare. Cualquier LLM (nombrar tópicos, redactar respuestas del agente) debe declararse.
- **Scraping ético:** respeta `robots.txt` y términos de uso, limita la tasa de peticiones y nunca eludas bloqueos. Usa `requests` + `BeautifulSoup`; Playwright solo si es imprescindible.
- **Privacidad:** no guardes nombres de usuario ni identificadores personales; solo texto, fecha e id anónimo.
- **Derecho de autor:** el cuerpo de las notas se procesa en memoria y nunca se guarda ni se publica; solo titular, enlace, datos derivados y métricas. Infobae está excluido.
- **YouTube:** solo la API oficial (nunca scraping de la web); borra o refresca los datos crudos a los 30 días. Sigue las "Reglas por sitio" del README para cada medio.

## Stack
`requests`, `BeautifulSoup`, spaCy/NLTK, `scikit-learn` (TF-IDF), `sentence-transformers` (con `normalize_embeddings=True`), ChromaDB (`PersistentClient`), `gensim`/LDA, BERTopic, pysentimiento, `networkx`, `google-api-python-client` (YouTube Data API v3), Streamlit.

## Qué no hacer
- No presentar el índice de discrepancia como "detector de desinformación" ni señalar medios o canales individuales como engañosos.
- No prometer métrica de exactitud para "alarmismo": el producto mide cercanía a lo oficial.
- No versionar `data/` ni modelos pesados.

## Estado
Nada de lo marcado "no verificado" en el README debe darse por cierto hasta probarlo (ver "Primera noche").
