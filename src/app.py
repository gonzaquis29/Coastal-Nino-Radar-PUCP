"""Bloque 7: MVP Streamlit. Ejecutar desde la raíz:  streamlit run src/app.py"""
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import pandas as pd
import streamlit as st

import radar

st.set_page_config(page_title="Radar Niño Costero", page_icon="🌊", layout="wide")
COLORES = {"verde": "#2a9d8f", "amarillo": "#e9c46a", "rojo": "#e76f51", "sin dato": "#adb5bd"}
ETIQ = {"verde": "Cercano a lo oficial", "amarillo": "Parcialmente alineado", "rojo": "Lejano de lo oficial",
        "sin dato": "Sin comunicado vigente"}


@st.cache_resource
def cargar():
    df = radar.cargar_comunicados()
    return df, radar.construir_indice(df)


df, col = cargar()

st.title("🌊 Radar Niño Costero")
st.caption("¿Qué se dice frente a lo que dice el ENFEN? Este indicador mide **cercanía a lo oficial**; "
           "no decide qué es verdad ni es un detector de desinformación.")

izq, der = st.columns([3, 2])
with izq:
    titular = st.text_area("Pega un titular", height=90,
                           placeholder="Ej.: Niño costero extraordinario traería lluvias intensas en la costa norte")
    fecha = st.date_input("Fecha de la nota", value=date.today())
    if st.button("Evaluar", type="primary") and titular.strip():
        r = radar.evaluar(titular.strip(), fecha.isoformat(), col=col, df=df)
        c = COLORES[r["semaforo"]]
        st.markdown(f"<div style='background:{c};padding:14px;border-radius:10px;font-size:1.3rem;"
                    f"font-weight:600'>{ETIQ[r['semaforo']]}</div>", unsafe_allow_html=True)
        if r["semaforo"] == "sin dato":
            st.warning(r["motivo"])
        else:
            m1, m2, m3 = st.columns(3)
            m1.metric("Distancia coseno", r["distancia"])
            m2.metric("Comunicado vigente", f"N.° {r['comunicado']}")
            m3.metric("Fecha del comunicado", r["fecha_comunicado"])
            if r["magnitud_distinta"]:
                st.warning(f"El titular usa magnitud «{r['magnitud_titular']}»; "
                           f"el comunicado dice «{r['magnitud_oficial']}».")
            st.subheader("Párrafo oficial más cercano")
            st.info(r["parrafo_oficial"])
            st.caption(f"Umbrales: verde ≤ {r['umbrales']['verde']}, rojo ≥ {r['umbrales']['rojo']} "
                       f"({r['umbrales']['origen']}).")
with der:
    st.subheader("Línea de tiempo oficial")
    lt = df.groupby(["comunicado", "fecha", "magnitud"], dropna=False).size().reset_index(name="párrafos")
    st.dataframe(lt, hide_index=True, use_container_width=True)
    noticias = Path("data/processed/noticias.csv")
    if noticias.exists():
        n = pd.read_csv(noticias)
        st.subheader("Volumen de noticias (Andina, titulares recientes)")
        st.bar_chart(n.groupby("fecha").size())
    if Path("results/controles.png").exists():
        st.subheader("Validación con controles")
        st.image("results/controles.png")
st.divider()
st.caption("Fuente oficial: comunicados ENFEN (enfen.imarpe.gob.pe). Titulares: Agencia Andina. "
           "Embeddings: paraphrase-multilingual-MiniLM-L12-v2. Texto sin datos personales.")
