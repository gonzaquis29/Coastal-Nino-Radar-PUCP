"""Centro de Monitoreo de Desastres — Perú.   Ejecutar desde la raíz:  streamlit run src/centro.py

Streamlit sirve los datos y la búsqueda; la interfaz (mapa) es el componente propio de web/.
No reemplaza a los canales oficiales de alerta.
"""
import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

os.environ.setdefault("HF_HUB_DISABLE_IMPLICIT_TOKEN", "1")  # modelos públicos: no usar tokens guardados
sys.path.insert(0, str(Path(__file__).parent))
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

import consolidar

PROC = Path("data/processed")
MODELO = "paraphrase-multilingual-MiniLM-L12-v2"
UMBRAL = 0.35  # similitud mínima; provisional, falta calibrarla

st.set_page_config(page_title="Centro de Monitoreo", page_icon="🛰️", layout="wide")
st.html("""<style>
header[data-testid="stHeader"],footer{display:none!important}
.block-container,[data-testid="stMainBlockContainer"]{padding:0!important;max-width:none!important}
.stApp{overflow:hidden}
iframe{position:fixed;inset:0;width:100vw!important;height:100vh!important;border:0}
</style>""")
mapa = components.declare_component("centro_mapa", path=str(Path(__file__).resolve().parent.parent / "web"))


def _txt(x):
    return "" if pd.isna(x) else str(x)


def _ref(titulo):
    """'9 km N of Carhuamayo, Peru' -> '9 km al N de Carhuamayo'."""
    s = re.sub(r", Peru$", "", titulo.split(" · ", 1)[-1])
    return re.sub(r"(\d+ km) ([NSEW]+) of ", lambda m: f"{m[1]} al {m[2].replace('W', 'O')} de ", s)


@st.cache_data
def datos(firma):
    out = []
    for r in pd.read_csv(PROC / "eventos.csv").itertuples():
        e = {"id": r.id, "fuente": r.fuente, "peligro": r.peligro, "titulo": _txt(r.titulo), "url": _txt(r.url),
             "texto": _txt(r.texto) if r.fuente in ("SENAMHI", "USGS") else "",
             "publicado": _txt(r.publicado)[:19], "inicio": _txt(r.inicio)[:19], "fin": _txt(r.fin)[:19],
             "nivel": _txt(r.nivel), "deps": [d for d in _txt(r.departamentos).split("|") if d],
             "recs": [x for x in _txt(r.recomendaciones).split("||") if x]}
        if r.fuente == "USGS":
            e |= {"lat": r.lat, "lon": r.lon, "ref": _ref(r.titulo), "mag": float(re.search(r"M(\d+\.\d)", r.titulo)[1])}
        out.append(e)
    parrafos = []
    if (PROC / "comunicados.csv").exists():
        c = pd.read_csv(PROC / "comunicados.csv")
        parrafos = c[c.comunicado == c.comunicado.max()].texto.tolist()
    return out, parrafos


@st.cache_resource
def embebedor():
    from sentence_transformers import SentenceTransformer
    return SentenceTransformer(MODELO)


@st.cache_data
def vectores(textos):
    return embebedor().encode(list(textos), normalize_embeddings=True, show_progress_bar=False)


def responder(q, dep, eventos):
    """Solo medidas oficiales textuales, del peligro preguntado y de la zona. Si no hay, lo dice."""
    pel = "lluvias e inundaciones" if re.search(r"llue?v|huayco|inund", q, re.I) else consolidar.peligro(q)
    cand, vistos = [], set()
    for e in eventos:
        if (e["deps"] and dep not in e["deps"]) or e["peligro"] == "otro" or (pel != "otro" and e["peligro"] != pel):
            continue
        for t in e["recs"]:
            if t[:60] not in vistos:
                vistos.add(t[:60])
                cand.append((t, e))
    if not cand:
        que = f"sobre «{pel}» " if pel != "otro" else ""
        return [], f"No hay medidas oficiales {que}para tu zona en las fuentes consultadas. Consulta directamente a INDECI."
    sc = vectores(tuple(t for t, _ in cand)) @ vectores((q,))[0]
    orden = [i for i in sc.argsort()[::-1] if pel != "otro" or sc[i] >= UMBRAL][:3]
    return ([{"texto": cand[i][0], "fuente": cand[i][1]["fuente"], "url": cand[i][1]["url"]} for i in orden],
            "No encontramos una respuesta oficial. Prueba nombrando el peligro: lluvias, calor, viento o sismo.")


def leer(nombre):
    f = PROC / nombre
    return json.loads(f.read_text(encoding="utf8")) if f.exists() else {}


def marca():
    f = PROC / "ultima_actualizacion.txt"
    return f.read_text().strip() if f.exists() else ""


if not (PROC / "eventos.csv").exists():
    import actualizar
    with st.spinner("Descargando datos de fuentes oficiales (cerca de 1 min)"):
        actualizar.actualizar()

eventos, parrafos = datos((marca(), (PROC / "eventos.csv").stat().st_mtime))
ahora = datetime.now(timezone(timedelta(hours=-5))).strftime("%Y-%m-%d %H:%M:%S")
valor = mapa(datos={"eventos": eventos, "enfen": parrafos, "act": marca() or ahora, "ahora": ahora,
                    "zonas": leer("zonas.json"), "estado": leer("estado_fuentes.json")},
             resp=st.session_state.get("resp"), key="mapa", default=None)

if valor and valor.get("n") != st.session_state.get("n"):
    st.session_state.n = valor["n"]
    resp = {"accion": valor["accion"], "n": valor["n"]}
    if valor["accion"] == "actualizar":
        import actualizar
        actualizar.actualizar()
    elif valor["accion"] == "pregunta":
        items, motivo = responder(str(valor["q"])[:300], valor["dep"], eventos)
        resp |= {"dep": valor["dep"], "items": items, "motivo": motivo}
    st.session_state.resp = resp
    st.rerun()
