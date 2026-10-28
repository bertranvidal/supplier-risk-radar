"""Panel de alertas del scraping de noticias.

Muestra las noticias recogidas por el scraper, clasificadas por riesgo,
con enlaces, resumenes y proveedores alternativos.

  streamlit run alerts_dashboard.py --server.port 8502
"""
import os

import pandas as pd
import requests
import streamlit as st
from dotenv import load_dotenv

from radar.data import load_suppliers, load_materials
from radar.impact import ids_of
from radar.schema import EVENT_TYPES

load_dotenv()

SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "")

st.set_page_config(page_title="Supplier Radar — Alertas en vivo", layout="wide", page_icon="🛡️")


def _h():
    return {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"}


@st.cache_data(ttl=60)
def fetch_all_news(limit: int = 500) -> pd.DataFrame:
    r = requests.get(
        f"{SUPABASE_URL}/rest/v1/scraped_news?select=*&order=scraped_at.desc&limit={limit}",
        headers=_h(),
    )
    if r.status_code != 200:
        return pd.DataFrame()
    return pd.DataFrame(r.json())


def priority_of(row) -> tuple[int, str, str]:
    """Calcula prioridad y color a partir de las predicciones."""
    risk = (row.get("predicted_risk") or 0) >= 0.5
    if not risk:
        return 4, "OK", "#2ecc71"

    event = row.get("predicted_event_type") or ""
    sup_ids = ids_of(row.get("predicted_supplier_ids") or "")

    sups = load_suppliers()
    s = sups.set_index("Supplier_ID")
    single = any(sid in s.index and s.loc[sid, "Single_Source"] == "Y" for sid in sup_ids)
    critical_sup = any(sid in s.index and s.loc[sid, "Criticality"] in ("Critical", "High") for sid in sup_ids)

    stoppage_kw = any(k in (row.get("title") or "").lower() + " " + (row.get("summary") or "").lower()
                      for k in ["halt", "suspend", "shut", "close", "evacuat", "recall", "ban", "insolvency"])

    if stoppage_kw and (single or critical_sup):
        return 0, "CRITICO", "#e74c3c"
    elif stoppage_kw:
        return 1, "ALTO", "#e67e22"
    elif critical_sup or single:
        return 2, "MEDIO", "#f39c12"
    else:
        return 3, "BAJO", "#3498db"


def get_alternatives(sup_ids: list[str]) -> list[dict]:
    """Busca proveedores alternativos para los afectados."""
    sups = load_suppliers()
    mats = load_materials()
    s = sups.set_index("Supplier_ID")
    alts = []
    for sid in sup_ids:
        if sid not in s.index:
            continue
        sup = s.loc[sid]
        alt_id = sup.get("Approved_Alternate_ID")
        if pd.notna(alt_id) and alt_id in s.index:
            alt = s.loc[alt_id]
            alts.append({
                "riesgo": f"{sid} — {sup['Supplier_Name']} ({sup['Country']})",
                "alternativa": f"{alt_id} — {alt['Supplier_Name']} ({alt['Country']})",
                "material": sup.get("Material_Supplied", ""),
                "quality_alt": alt.get("Quality_Score", "?"),
                "inventory_alt": alt.get("Inventory_Cover_Days", "?"),
            })
        else:
            alts.append({
                "riesgo": f"{sid} — {sup['Supplier_Name']} ({sup['Country']})",
                "alternativa": "Sin alternativa aprobada",
                "material": sup.get("Material_Supplied", ""),
                "quality_alt": "—",
                "inventory_alt": "—",
            })
    return alts


# Sidebar
with st.sidebar:
    st.markdown("### Supplier Radar")
    st.caption("Panel de alertas en vivo")
    st.divider()
    limit = st.slider("Noticias a cargar", 50, 1000, 300)
    show_all = st.checkbox("Mostrar tambien las no-riesgo", value=False)
    if st.button("Actualizar datos", type="primary"):
        st.cache_data.clear()

    st.divider()
    st.caption("Scraping")
    if st.button("Ejecutar scraper ahora"):
        with st.spinner("Scraping..."):
            import subprocess
            result = subprocess.run(["python3", "scraper.py", "--source", "all"],
                                    capture_output=True, text=True, cwd=os.path.dirname(__file__))
            st.code(result.stdout[-500:] if result.stdout else result.stderr[-300:])
            st.cache_data.clear()

    if st.button("Clasificar noticias nuevas"):
        with st.spinner("Clasificando..."):
            import subprocess
            result = subprocess.run(["python3", "classify_supabase.py", "--mode", "rules", "--unlabeled"],
                                    capture_output=True, text=True, cwd=os.path.dirname(__file__))
            st.code(result.stdout[-500:] if result.stdout else result.stderr[-300:])
            st.cache_data.clear()


# Datos
df = fetch_all_news(limit)
if df.empty:
    st.warning("No hay noticias en la base de datos. Ejecuta el scraper primero.")
    st.stop()

# Calcular prioridades
priorities = []
for _, row in df.iterrows():
    rank, label, color = priority_of(row.to_dict())
    priorities.append({"rank": rank, "label": label, "color": color})

df["_rank"] = [p["rank"] for p in priorities]
df["_label"] = [p["label"] for p in priorities]
df["_color"] = [p["color"] for p in priorities]

risk_df = df[df["_rank"] < 4].sort_values("_rank")
total_risk = len(risk_df)

# KPIs
st.markdown("## Panel de alertas")
k1, k2, k3, k4 = st.columns(4)
k1.metric("Noticias analizadas", len(df))
k2.metric("Alertas de riesgo", total_risk)
k3.metric("Criticas", len(risk_df[risk_df["_label"] == "CRITICO"]))
k4.metric("Fuentes activas", df["source"].nunique())

st.divider()

# Alertas ordenadas por prioridad
if total_risk == 0:
    st.success("No se han detectado riesgos en las ultimas noticias.")
else:
    st.markdown(f"### {total_risk} alertas detectadas")
    st.caption("Ordenadas de mayor a menor importancia")

    for _, row in risk_df.iterrows():
        color = row["_color"]
        label = row["_label"]
        event = row.get("predicted_event_type") or "?"
        title = row.get("title") or ""
        summary = row.get("summary") or ""
        url = row.get("url") or ""
        source = row.get("source") or ""
        pub = row.get("published_at") or ""
        sup_ids = ids_of(row.get("predicted_supplier_ids") or "")

        st.markdown(
            f"""<div style="border-left: 5px solid {color}; padding: 12px 16px; margin-bottom: 8px;
            background: {'#2c0b0b' if label == 'CRITICO' else '#1a1a2e' if label == 'ALTO' else '#16213e'};
            border-radius: 8px;">
            <span style="background: {color}; color: white; padding: 2px 10px; border-radius: 12px;
            font-size: 11px; font-weight: bold;">{label}</span>
            <span style="color: #888; font-size: 11px; margin-left: 8px;">{event}</span>
            <h4 style="margin: 6px 0 4px 0; color: #eee;">{title}</h4>
            </div>""",
            unsafe_allow_html=True,
        )

        with st.expander("Ver detalles", expanded=(label == "CRITICO")):
            st.write(summary)

            cols = st.columns([2, 1])
            with cols[0]:
                if url:
                    st.markdown(f"[Leer noticia completa]({url})")
                st.caption(f"Fuente: {source} · Publicado: {pub[:16] if pub else '?'}")

            with cols[1]:
                conf = row.get("confidence") or 0
                st.metric("Confianza", f"{conf:.0%}")

            if sup_ids:
                st.markdown("**Proveedores afectados:**")
                alts = get_alternatives(sup_ids)
                for alt in alts:
                    c1, c2 = st.columns(2)
                    with c1:
                        st.error(f"🔴 {alt['riesgo']}")
                        st.caption(f"Material: {alt['material']}")
                    with c2:
                        if alt["alternativa"] == "Sin alternativa aprobada":
                            st.warning(f"⚠️ {alt['alternativa']}")
                        else:
                            st.success(f"🟢 {alt['alternativa']}")
                            st.caption(f"Calidad: {alt['quality_alt']} · Inventario: {alt['inventory_alt']}d")

            st.divider()

# Mostrar no-riesgo si se pidio
if show_all:
    st.markdown("### Noticias sin riesgo detectado")
    ok_df = df[df["_rank"] == 4].head(50)
    for _, row in ok_df.iterrows():
        title = row.get("title") or ""
        source = row.get("source") or ""
        url = row.get("url") or ""
        link = f" — [enlace]({url})" if url else ""
        st.caption(f"**{source}**: {title}{link}")
