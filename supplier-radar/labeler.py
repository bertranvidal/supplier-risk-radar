"""Interfaz de etiquetado manual para noticias de Supabase.

  streamlit run labeler.py --server.port 8502
"""
import os

import requests
import streamlit as st
from dotenv import load_dotenv

from radar.schema import EVENT_TYPES

load_dotenv()

SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "")

st.set_page_config(page_title="Etiquetado de noticias", layout="wide")


def _headers():
    return {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}", "Content-Type": "application/json"}


def fetch_news(filter_mode: str, limit: int) -> list[dict]:
    url = f"{SUPABASE_URL}/rest/v1/scraped_news?select=*&order=id.desc&limit={limit}"
    if filter_mode == "Sin etiquetar":
        url += "&is_labeled=eq.false"
    elif filter_mode == "Baja confianza":
        url += "&confidence=gte.0.2&confidence=lte.0.6"
    elif filter_mode == "Prediccion riesgo":
        url += "&predicted_risk=gte.0.5"
    r = requests.get(url, headers=_headers())
    return r.json() if r.status_code == 200 else []


def save_label(news_id: int, is_risk: bool, urgent: bool, event_type: str, supplier_ids: str):
    payload = {
        "is_labeled": True,
        "is_risk": is_risk,
        "urgent": urgent,
        "event_type": event_type,
        "affected_supplier_ids": supplier_ids if supplier_ids else None,
    }
    r = requests.patch(f"{SUPABASE_URL}/rest/v1/scraped_news?id=eq.{news_id}",
                       headers=_headers(), json=payload)
    return r.status_code in (200, 204)


def count_labeled() -> dict:
    h = {**_headers(), "Prefer": "count=exact"}
    total = requests.get(f"{SUPABASE_URL}/rest/v1/scraped_news?select=id", headers={**h, "Range": "0-0"})
    labeled = requests.get(f"{SUPABASE_URL}/rest/v1/scraped_news?select=id&is_labeled=eq.true", headers={**h, "Range": "0-0"})
    return {
        "total": total.headers.get("content-range", "0-0/0").split("/")[-1],
        "labeled": labeled.headers.get("content-range", "0-0/0").split("/")[-1],
    }


st.title("Etiquetado de noticias")
st.caption("Clasifica noticias para mejorar el entrenamiento de los modelos")

counts = count_labeled()
c1, c2, c3 = st.columns(3)
c1.metric("Total en BD", counts["total"])
c2.metric("Etiquetadas", counts["labeled"])
c3.metric("Pendientes", int(counts["total"]) - int(counts["labeled"]))

st.divider()

col_f, col_l = st.columns([1, 3])
with col_f:
    mode = st.selectbox("Filtro", ["Sin etiquetar", "Baja confianza", "Prediccion riesgo", "Todas"])
    limit = st.slider("Cantidad", 10, 100, 30)

news = fetch_news(mode, limit)

if not news:
    st.info("No hay noticias con ese filtro.")
    st.stop()

st.write(f"**{len(news)} noticias**")

for i, article in enumerate(news):
    pred_risk = article.get("predicted_risk") or 0
    pred_event = article.get("predicted_event_type") or "?"
    conf = article.get("confidence") or 0
    already = article.get("is_labeled", False)

    color = "red" if pred_risk >= 0.5 else "green"
    badge = f":{color}[{'RIESGO' if pred_risk >= 0.5 else 'OK'}]"
    label_badge = " :blue[ETIQUETADA]" if already else ""

    with st.expander(f"{badge} {article['title'][:100]}{label_badge}", expanded=False):
        st.write(article.get("summary", ""))
        st.caption(f"Fuente: {article.get('source', '?')} · Prediccion: {pred_event} (conf: {conf:.1%})")

        with st.form(key=f"form_{article['id']}"):
            fc1, fc2 = st.columns(2)
            is_risk = fc1.selectbox("Es riesgo?", ["No", "Si"],
                                     index=1 if (article.get("is_risk") or pred_risk >= 0.5) else 0,
                                     key=f"risk_{article['id']}")
            urgent = fc2.selectbox("Urgente?", ["No", "Si"],
                                    index=1 if article.get("urgent") else 0,
                                    key=f"urg_{article['id']}")
            event = st.selectbox("Tipo de evento", EVENT_TYPES,
                                  index=EVENT_TYPES.index(pred_event) if pred_event in EVENT_TYPES else len(EVENT_TYPES) - 1,
                                  key=f"ev_{article['id']}")
            sups = st.text_input("IDs proveedores afectados (ej: S002; S006)",
                                  value=article.get("affected_supplier_ids") or article.get("predicted_supplier_ids") or "",
                                  key=f"sup_{article['id']}")

            if st.form_submit_button("Guardar etiqueta"):
                ok = save_label(article["id"], is_risk == "Si", urgent == "Si", event, sups)
                if ok:
                    st.success("Guardada")
                else:
                    st.error("Error al guardar")
