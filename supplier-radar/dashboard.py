"""Panel de alertas del Supplier Risk Radar.

  python3 -m streamlit run dashboard.py --server.port 8501 --server.headless true \
      --server.enableCORS false --server.enableXsrfProtection false
"""
import io
import os

import pandas as pd
import pydeck as pdk
import requests
import streamlit as st
from dotenv import load_dotenv

from radar.config import TEST, VALID
from radar.data import is_labelled, load_materials, load_news, load_suppliers
from radar.alerts import add_alerts
from radar.impact import eur, ids_of
from radar.pipeline import analyze_news, load_pool, save_excel

load_dotenv()

st.set_page_config(page_title="Supplier Risk Radar", layout="wide")

with st.sidebar:
    lang = st.radio(
        "Language" if st.session_state.get("dashboard_language", "en") == "en" else "Idioma",
        ["en", "es"],
        format_func={"en": "English", "es": "Español"}.get,
        horizontal=True,
        key="dashboard_language",
    )

TEXT = {
    "en": {
        "title_caption": "News risk monitor for Helixa Pharmaceuticals' 40 suppliers",
        "input": "Input",
        "source": "Source",
        "test": "Test",
        "validation": "Validation (labelled)",
        "upload": "Upload Excel",
        "news_excel": "News Excel file",
        "engine": "Engine",
        "engine_help": "models = our fine-tuned models; rules = baseline without models",
        "models": "Fine-tuned models",
        "rules": "Rules (baseline)",
        "gen_alerts": "Draft alerts with generative AI",
        "gen_help": "The models decide; generative AI only writes the alert. If no local LLM is available, a template is used.",
        "analyze": "Analyze",
        "upload_first": "Upload an Excel file first.",
        "analyzing": "Analyzing news...",
        "updating_alerts": "Updating alert language...",
        "analysis_error": "Could not analyze: ",
        "choose_source": "Choose a source and click **Analyze**.",
        "news": "News",
        "risks": "Risks",
        "urgent": "Urgent",
        "annual_spend": "Annual spend associated",
        "time": "Time",
        "labelled_accuracy": "Compared with file labels: Risk {risk:.0%} · Urgent {urgent:.0%}",
        "alerts": "Alerts",
        "alerts_tab": "Alerts",
        "actions_tab": "Recommended actions",
        "map_tab": "Map",
        "filter_by": "Filter alerts",
        "filter_priority": "Priority",
        "filter_urgency": "Urgency",
        "filter_event": "Event type",
        "filter_country": "Supplier country",
        "filter_supplier": "Supplier",
        "no_alerts_match": "No alerts match the selected filters.",
        "only_risks": "Show risks only",
        "priority": "Priority",
        "news_id": "News ID",
        "headline": "Headline",
        "is_risk": "Risk?",
        "is_urgent": "Urgent?",
        "affected_suppliers": "Affected supplier IDs",
        "event_type": "Event type",
        "confidence": "Confidence",
        "details": "Details",
        "why_matters": "Why it matters",
        "next_steps": "Next steps",
        "supplier_email": "Draft email to supplier",
        "alert_source": "Alert drafted by",
        "original_news": "Original news: ",
        "risk": "Risk",
        "yes": "yes",
        "no": "no",
        "urgent_label": "Urgent",
        "type": "Type",
        "suppliers": "Suppliers",
        "products_affected": "Affected products",
        "worst_inventory": "Worst-case inventory",
        "estimated_duration": "Estimated duration",
        "not_stated": "not stated",
        "recommended_action": "Recommended action",
        "model_reasoning": "Confidence {confidence} · {reasoning}",
        "map_title": "Exposure map by country",
        "map_hint": "Hover over a bubble to see its suppliers and materials. Size represents associated annual spend; color shows the highest priority. Points mark approximate country centers, not incident locations or transport routes.",
        "priority_legend": "Priority: CRITICAL (red) · HIGH (orange) · MEDIUM (yellow) · LOW (blue).",
        "country": "Country",
        "affected_supplier_count": "Affected suppliers",
        "risk_news_count": "Risk news",
        "urgent_count": "Urgent",
        "spend_eur": "Associated annual spend (EUR)",
        "top_priority": "Highest priority",
        "suppliers_column": "Suppliers",
        "unmapped": "No coordinates are configured for these countries; they appear in the table but not on the map: ",
        "no_suppliers": "No affected suppliers were detected in news classified as risk.",
        "actions_title": "Recommended actions",
        "actions_hint": "Prioritized by detected alerts and approved alternatives in the data. Confirm availability and capacity before reallocating orders.",
        "alert_count": "alert(s)",
        "map_alerts": "alerts",
        "map_urgent": "urgent",
        "map_supplier": "Suppliers",
        "map_priority": "Priority",
        "inventory": "Inventory",
        "no_data": "No data",
        "action": "Action",
        "contact_alt": "Contact **{alt_id} ({alt_name})** to confirm capacity and lead time; request **{materials}**{products}.",
        "confirm_supplier": "Confirm inventory and recovery with **{supplier}**. Approved alternative **{alternate}** is also affected; find another source.",
        "no_approved_alt": "Confirm inventory and recovery with **{supplier}**; no approved alternative is listed.",
        "material": "Material",
        "related_news": "Related news",
        "download": "Download Excel (Results + Details)",
        "translated_priority": {"CRITICAL": "CRITICAL", "HIGH": "HIGH", "MEDIUM": "MEDIUM", "LOW": "LOW"},
        "translated_confidence": {"high": "high", "medium": "medium", "low": "low"},
        "risk_values": {"Y": "Yes", "N": "No"},
        "urgent_values": {"Y": "Yes", "N": "No"},
        "events": {},
        "countries": {},
    },
    "es": {
        "title_caption": "Monitor de noticias de riesgo para los 40 proveedores de Helixa Pharmaceuticals",
        "input": "Entrada",
        "source": "Fuente",
        "test": "Prueba",
        "validation": "Validación (con respuestas)",
        "upload": "Subir Excel",
        "news_excel": "Excel de noticias",
        "engine": "Motor",
        "engine_help": "modelos = nuestros modelos afinados; reglas = línea base sin modelos",
        "models": "Modelos afinados",
        "rules": "Reglas (línea base)",
        "gen_alerts": "Redactar alertas con IA generativa",
        "gen_help": "Los modelos deciden; la IA generativa solo redacta la alerta. Si no hay un LLM local, se usa una plantilla.",
        "analyze": "Analizar",
        "upload_first": "Sube un Excel primero.",
        "analyzing": "Analizando noticias...",
        "updating_alerts": "Actualizando el idioma de las alertas...",
        "analysis_error": "No se pudo analizar: ",
        "choose_source": "Elige una fuente y pulsa **Analizar**.",
        "news": "Noticias",
        "risks": "Riesgos",
        "urgent": "Urgentes",
        "annual_spend": "Gasto anual asociado",
        "time": "Tiempo",
        "labelled_accuracy": "Contra las respuestas del fichero: Riesgo {risk:.0%} · Urgencia {urgent:.0%}",
        "alerts": "Alertas",
        "alerts_tab": "Alertas",
        "actions_tab": "Acciones recomendadas",
        "map_tab": "Mapa",
        "filter_by": "Filtrar alertas",
        "filter_priority": "Prioridad",
        "filter_urgency": "Urgencia",
        "filter_event": "Tipo de evento",
        "filter_country": "País del proveedor",
        "filter_supplier": "Proveedor",
        "no_alerts_match": "Ninguna alerta coincide con los filtros seleccionados.",
        "only_risks": "Mostrar solo riesgos",
        "priority": "Prioridad",
        "news_id": "ID noticia",
        "headline": "Titular",
        "is_risk": "¿Riesgo?",
        "is_urgent": "¿Urgente?",
        "affected_suppliers": "IDs de proveedores afectados",
        "event_type": "Tipo de evento",
        "confidence": "Confianza",
        "details": "Detalle",
        "why_matters": "Por qué importa",
        "next_steps": "Siguientes pasos",
        "supplier_email": "Borrador de email al proveedor",
        "alert_source": "Alerta redactada por",
        "original_news": "Noticia original: ",
        "risk": "Riesgo",
        "yes": "sí",
        "no": "no",
        "urgent_label": "Urgente",
        "type": "Tipo",
        "suppliers": "Proveedores",
        "products_affected": "Productos afectados",
        "worst_inventory": "Inventario (peor caso)",
        "estimated_duration": "Duración estimada",
        "not_stated": "no indicada",
        "recommended_action": "Acción recomendada",
        "model_reasoning": "Confianza {confidence} · {reasoning}",
        "map_title": "Mapa de exposición por país",
        "map_hint": "Pasa el cursor sobre una burbuja para ver sus proveedores y materiales. El tamaño representa el gasto anual asociado; el color, la prioridad máxima. Los puntos indican centros aproximados de países, no ubicaciones exactas de incidentes ni rutas de transporte.",
        "priority_legend": "Prioridad: CRÍTICA (rojo) · ALTA (naranja) · MEDIA (amarillo) · BAJA (azul).",
        "country": "País",
        "affected_supplier_count": "Proveedores afectados",
        "risk_news_count": "Noticias de riesgo",
        "urgent_count": "Urgentes",
        "spend_eur": "Gasto anual asociado (EUR)",
        "top_priority": "Prioridad máxima",
        "suppliers_column": "Proveedores",
        "unmapped": "No hay coordenadas configuradas para estos países; aparecen en la tabla, pero no en el mapa: ",
        "no_suppliers": "No se detectaron proveedores afectados en las noticias clasificadas como riesgo.",
        "actions_title": "Acciones recomendadas",
        "actions_hint": "Priorizadas por las alertas detectadas y las alternativas aprobadas en los datos. Confirma disponibilidad y capacidad antes de reasignar pedidos.",
        "alert_count": "alerta(s)",
        "map_alerts": "alertas",
        "map_urgent": "urgentes",
        "map_supplier": "Proveedores",
        "map_priority": "Prioridad",
        "inventory": "Inventario",
        "no_data": "Sin dato",
        "action": "Acción",
        "contact_alt": "Contactar a **{alt_id} ({alt_name})** para confirmar capacidad y plazo; solicitar **{materials}**{products}.",
        "confirm_supplier": "Confirmar inventario y recuperación con **{supplier}**. La alternativa aprobada **{alternate}** también está afectada: buscar otra fuente.",
        "no_approved_alt": "Confirmar inventario y recuperación con **{supplier}**; no consta una alternativa aprobada.",
        "material": "Material",
        "related_news": "Noticias relacionadas",
        "download": "Descargar Excel (Results + Details)",
        "translated_priority": {"CRITICAL": "CRÍTICA", "HIGH": "ALTA", "MEDIUM": "MEDIA", "LOW": "BAJA"},
        "translated_confidence": {"high": "alta", "medium": "media", "low": "baja"},
        "risk_values": {"Y": "Sí", "N": "No"},
        "urgent_values": {"Y": "Sí", "N": "No"},
        "events": {
            "Natural disaster": "Desastre natural",
            "Fire / plant incident": "Incendio / incidente en planta",
            "Labour strike": "Huelga laboral",
            "Logistics disruption": "Interrupción logística",
            "Quality recall": "Retirada por calidad",
            "Regulatory action": "Medida regulatoria",
            "Export restriction": "Restricción a la exportación",
            "Utility outage": "Corte de suministros",
            "Financial distress": "Dificultades financieras",
            "Leadership change": "Cambio de dirección",
            "Acquisition by competitor": "Adquisición por competidor",
            "Cyber attack": "Ciberataque",
            "Geopolitical / sanctions": "Riesgo geopolítico / sanciones",
            "Other risk": "Otro riesgo",
            "Positive news": "Noticia positiva",
            "Not relevant": "No relevante",
        },
        "countries": {
            "Belgium": "Bélgica", "Brazil": "Brasil", "China": "China", "Germany": "Alemania",
            "India": "India", "Ireland": "Irlanda", "Italy": "Italia", "Japan": "Japón",
            "Mexico": "México", "Morocco": "Marruecos", "Netherlands": "Países Bajos",
            "Norway": "Noruega", "Poland": "Polonia", "Puerto Rico (USA)": "Puerto Rico (EE. UU.)",
            "Singapore": "Singapur", "Spain": "España", "Switzerland": "Suiza", "Taiwan": "Taiwán",
            "USA": "EE. UU.", "Vietnam": "Vietnam",
        },
    },
}
T = TEXT[lang]
PRIORITY_LABELS = T["translated_priority"]
CONFIDENCE_LABELS = T["translated_confidence"]
EVENT_LABELS = T["events"]
COUNTRY_LABELS = T["countries"]

SUP = load_suppliers().set_index("Supplier_ID")
MATERIALS = load_materials()
COLORS = {"CRITICAL": "#f4a6a6", "HIGH": "#f8cbad", "MEDIUM": "#ffe699", "LOW": "#ffffff"}
ORDER = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}
MAP_COLORS = {
    "CRITICAL": [200, 62, 77, 210],
    "HIGH": [237, 139, 50, 210],
    "MEDIUM": [227, 183, 47, 210],
    "LOW": [57, 119, 183, 210],
}


def display_action(row) -> str:
    if row.Is_Risk != "Y":
        return "No action needed." if lang == "en" else "No se requiere ninguna acción."

    ids = ids_of(row.Affected_Supplier_IDs)
    single_source = {
        supplier_id.strip()
        for supplier_id in str(row.Single_Source_Affected or "").split(",")
        if supplier_id.strip()
    }
    actions = []
    for supplier_id in ids:
        if supplier_id not in SUP.index:
            continue
        alternate_id = SUP.loc[supplier_id, "Approved_Alternate_ID"]
        if not isinstance(alternate_id, str) or alternate_id not in SUP.index:
            continue
        if alternate_id in ids:
            text = (
                f"Approved alternate for {supplier_id} is also affected; identify another source."
                if lang == "en" else
                f"La alternativa aprobada de {supplier_id} también está afectada; buscar otra fuente."
            )
        else:
            text = (
                f"Contact approved alternate {alternate_id} for {SUP.loc[alternate_id, 'Supplier_Name']}."
                if lang == "en" else
                f"Contactar con la alternativa aprobada {alternate_id} "
                f"({SUP.loc[alternate_id, 'Supplier_Name']})."
            )
        actions.append(text)

    uncovered_single_sources = sorted(
        supplier_id for supplier_id in single_source
        if supplier_id in SUP.index
        and not (
            isinstance(SUP.loc[supplier_id, "Approved_Alternate_ID"], str)
            and SUP.loc[supplier_id, "Approved_Alternate_ID"] in SUP.index
        )
    )
    if uncovered_single_sources:
        ids_text = ", ".join(uncovered_single_sources)
        actions.append(
            f"Secure stock and qualify a second source for {ids_text}."
            if lang == "en" else
            f"Asegurar existencias y homologar una segunda fuente para {ids_text}."
        )

    days = row.Duration_Days
    cover = row.Min_Inventory_Days
    if row.Stockout_Risk == "Y" and pd.notna(days) and pd.notna(cover):
        actions.append(
            f"Expedite orders: the estimated event ({days:.0f} days) may outlast inventory ({cover:.0f} days)."
            if lang == "en" else
            f"Acelerar pedidos: el evento estimado ({days:.0f} días) puede durar más que el inventario ({cover:.0f} días)."
        )
    elif row.Stockout_Risk == "N" and pd.notna(days) and pd.notna(cover):
        actions.append(
            f"Inventory ({cover:.0f} days) covers the estimated event ({days:.0f} days); monitor weekly."
            if lang == "en" else
            f"El inventario ({cover:.0f} días) cubre el evento estimado ({days:.0f} días); revisar semanalmente."
        )
    elif pd.notna(cover):
        actions.append(
            f"Confirm the supplier's restart date; inventory covers {cover:.0f} days."
            if lang == "en" else
            f"Confirmar la fecha de reanudación con el proveedor; hay {cover:.0f} días de inventario."
        )
    return " ".join(dict.fromkeys(actions)) or ("Monitor." if lang == "en" else "Realizar seguimiento.")


with st.sidebar:
    st.header(T["input"])
    src_options = ["Test", "Validación (con respuestas)", "Subir Excel"]
    src_labels = {
        "Test": T["test"],
        "Validación (con respuestas)": T["validation"],
        "Subir Excel": T["upload"],
    }
    src = st.radio(T["source"], src_options, format_func=src_labels.get)
    up = st.file_uploader(T["news_excel"], type=["xlsx"]) if src == "Subir Excel" else None
    mode = st.selectbox(
        T["engine"],
        ["models", "rules"],
        format_func={"models": T["models"], "rules": T["rules"]}.get,
        help=T["engine_help"],
    )
    gen = st.checkbox(T["gen_alerts"], value=True, help=T["gen_help"])
    go = st.button(T["analyze"], type="primary", use_container_width=True)

st.title("Supplier Risk Radar")
st.caption(T["title_caption"])

if go:
    try:
        if src == "Subir Excel":
            if up is None:
                st.error(T["upload_first"])
                st.stop()
            news = load_news(up)
        else:
            news = load_news({"Test": TEST, "Validación (con respuestas)": VALID}[src])
        pool = load_pool(include_valid=(src != "Validación (con respuestas)"))
        with st.spinner(T["analyzing"]):
            res = analyze_news(news, pool, mode, alerts=gen, alert_lang=lang)
        st.session_state["res"], st.session_state["news"] = res, news
        st.session_state["analysis_language"] = lang
        st.session_state["analysis_alerts"] = gen
    except Exception as e:  # noqa: BLE001
        st.error(f"{T['analysis_error']}{e}")
        st.stop()

if "res" not in st.session_state:
    st.info(T["choose_source"])
    st.stop()

if st.session_state.get("analysis_language") != lang:
    res = st.session_state["res"]
    if st.session_state.get("analysis_alerts") and "Alert_Title" in res.columns:
        with st.spinner(T["updating_alerts"]):
            res = add_alerts(
                res,
                st.session_state["news"],
                SUP.reset_index(),
                lang=lang,
                use_llm=True,
            )
        st.session_state["res"] = res
    st.session_state["analysis_language"] = lang

res: pd.DataFrame = st.session_state["res"]
news: pd.DataFrame = st.session_state["news"]
res["_o"] = res["Priority"].map(ORDER)
res = res.sort_values(["_o", "News_ID"]).drop(columns="_o").reset_index(drop=True)

risk_res = res[res.Is_Risk == "Y"]
supplier_news = {}
for row in risk_res.itertuples():
    for supplier_id in set(ids_of(row.Affected_Supplier_IDs)):
        if supplier_id not in SUP.index:
            continue
        entry = supplier_news.setdefault(
            supplier_id, {"news_ids": set(), "urgent_news_ids": set(), "priority": "LOW"}
        )
        entry["news_ids"].add(row.News_ID)
        if row.Urgent == "Y":
            entry["urgent_news_ids"].add(row.News_ID)
        if ORDER.get(row.Priority, len(ORDER)) < ORDER.get(entry["priority"], len(ORDER)):
            entry["priority"] = row.Priority

k = st.columns(5)
k[0].metric(T["news"], len(res))
k[1].metric(T["risks"], int((res.Is_Risk == "Y").sum()))
k[2].metric(T["urgent"], int((res.Urgent == "Y").sum()))
k[3].metric(
    T["annual_spend"],
    eur(sum(float(SUP.loc[supplier_id, "Annual_Spend_EUR"]) for supplier_id in supplier_news)),
)
k[4].metric(T["time"], f"{res.attrs.get('seconds', 0):.1f} s")

if is_labelled(news):
    g = news.set_index("News_ID")
    m = res.set_index("News_ID")
    acc_r = (m.Is_Risk == g.loc[m.index, "Is_Risk"]).mean()
    acc_u = (m.Urgent == g.loc[m.index, "Urgent"]).mean()
    st.success(T["labelled_accuracy"].format(risk=acc_r, urgent=acc_u))

live_tab = "Live news alerts" if lang == "en" else "Alertas en vivo"
weather_tab = "Weather alerts" if lang == "en" else "Alertas climáticas"
review_tab = "Review & label" if lang == "en" else "Revisar y etiquetar"
kpi_tab = "KPI Dashboard" if lang == "en" else "Panel KPIs"
tabs = st.tabs([T["alerts_tab"], T["actions_tab"], T["map_tab"], kpi_tab, live_tab, weather_tab, review_tab])
with tabs[0]:
    st.subheader(T["alerts"])
    only_risk = st.checkbox(T["only_risks"], value=True, key="alert_filter_risks_only")
    st.caption(T["filter_by"])
    filter_columns = st.columns(5)
    priority_options = ["CRITICAL", "HIGH", "MEDIUM", "LOW"]
    selected_priorities = filter_columns[0].multiselect(
        T["filter_priority"],
        priority_options,
        format_func=PRIORITY_LABELS.get,
        key="alert_filter_priority",
    )
    selected_urgencies = filter_columns[1].multiselect(
        T["filter_urgency"],
        ["Y", "N"],
        format_func=T["urgent_values"].get,
        key="alert_filter_urgency",
    )
    event_options = sorted(res["Event_Type"].dropna().unique())
    selected_events = filter_columns[2].multiselect(
        T["filter_event"],
        event_options,
        format_func=lambda value: EVENT_LABELS.get(value, value),
        key="alert_filter_event",
    )
    supplier_ids = sorted({
        supplier_id
        for affected in res["Affected_Supplier_IDs"].dropna()
        for supplier_id in ids_of(affected)
        if supplier_id in SUP.index
    })
    supplier_labels = {
        f"{supplier_id} · {SUP.loc[supplier_id, 'Supplier_Name']}": supplier_id
        for supplier_id in supplier_ids
    }
    selected_supplier_labels = filter_columns[3].multiselect(
        T["filter_supplier"],
        list(supplier_labels),
        key="alert_filter_supplier",
    )
    countries = sorted({
        SUP.loc[supplier_id, "Country"]
        for supplier_id in supplier_ids
    })
    selected_countries = filter_columns[4].multiselect(
        T["filter_country"],
        countries,
        format_func=lambda value: COUNTRY_LABELS.get(value, value),
        key="alert_filter_country",
    )

    view = res[res.Is_Risk == "Y"].copy() if only_risk else res.copy()
    selected_supplier_ids = {
        supplier_labels[label] for label in selected_supplier_labels
    }
    selected_country_supplier_ids = {
        supplier_id for supplier_id in supplier_ids
        if not selected_countries or SUP.loc[supplier_id, "Country"] in selected_countries
    }
    if selected_priorities:
        view = view[view["Priority"].isin(selected_priorities)]
    if selected_urgencies:
        view = view[view["Urgent"].isin(selected_urgencies)]
    if selected_events:
        view = view[view["Event_Type"].isin(selected_events)]
    if selected_supplier_ids:
        view = view[view["Affected_Supplier_IDs"].map(
            lambda affected: bool(set(ids_of(affected)) & selected_supplier_ids)
        )]
    if selected_countries:
        view = view[view["Affected_Supplier_IDs"].map(
            lambda affected: bool(set(ids_of(affected)) & selected_country_supplier_ids)
        )]
    cols = ["Priority", "News_ID", "Headline", "Is_Risk", "Urgent", "Affected_Supplier_IDs", "Event_Type", "Spend_At_Risk_EUR", "Confidence"]
    table = view[cols].copy()
    table["Priority"] = table["Priority"].map(PRIORITY_LABELS)
    table["Is_Risk"] = table["Is_Risk"].map(T["risk_values"])
    table["Urgent"] = table["Urgent"].map(T["urgent_values"])
    table["Event_Type"] = table["Event_Type"].map(lambda value: EVENT_LABELS.get(value, value))
    table["Confidence"] = table["Confidence"].map(CONFIDENCE_LABELS).fillna(table["Confidence"])
    table = table.rename(columns={
        "Priority": T["priority"],
        "News_ID": T["news_id"],
        "Headline": T["headline"],
        "Is_Risk": T["is_risk"],
        "Urgent": T["is_urgent"],
        "Affected_Supplier_IDs": T["affected_suppliers"],
        "Event_Type": T["event_type"],
        "Spend_At_Risk_EUR": T["annual_spend"],
        "Confidence": T["confidence"],
    })
    priority_colors = {PRIORITY_LABELS[key]: value for key, value in COLORS.items()}
    priority_column = T["priority"]
    try:
        if not table.empty:
            st.dataframe(table.style.apply(
                lambda row: [f"background-color: {priority_colors[row[priority_column]]}"] * len(row),
                axis=1,
            ), use_container_width=True, hide_index=True)
    except Exception:  # noqa: BLE001
        if not table.empty:
            st.dataframe(table, use_container_width=True, hide_index=True)
    if table.empty:
        st.info(T["no_alerts_match"])

    st.subheader(T["details"])
    for r in view.itertuples():
        label = f"{PRIORITY_LABELS.get(r.Priority, r.Priority)} · {r.News_ID} · {r.Headline}"
        with st.expander(label, expanded=(r.Priority == "CRITICAL")):
            text = news.loc[news.News_ID == r.News_ID, "Summary"].iloc[0]
            if getattr(r, "Alert_Title", ""):
                st.markdown(f"#### {r.Alert_Title}")
                st.write(r.Alert_Summary)
                st.markdown(f"**{T['why_matters']}:** {r.Alert_Why}")
                st.markdown(f"**{T['next_steps']}:**\n{r.Alert_Steps}")
                with st.popover(T["supplier_email"]):
                    st.text(r.Alert_Email)
                st.caption(f"{T['alert_source']}: {r.Alert_Source}")
                st.divider()
                st.caption(T["original_news"] + text)
            else:
                st.write(text)
            c1, c2 = st.columns(2)
            with c1:
                is_risk_text = T["yes"] if r.Is_Risk == "Y" else T["no"]
                is_urgent_text = T["yes"] if r.Urgent == "Y" else T["no"]
                event_text = EVENT_LABELS.get(r.Event_Type, r.Event_Type)
                st.markdown(
                    f"**{T['risk']}:** {is_risk_text} · **{T['urgent_label']}:** {is_urgent_text} · "
                    f"**{T['type']}:** {event_text}"
                )
                ids = ids_of(r.Affected_Supplier_IDs)
                if ids:
                    st.markdown(
                        f"**{T['suppliers']}:** " + ", ".join(
                            f"{i} {SUP.loc[i, 'Supplier_Name']} ({SUP.loc[i, 'City']})"
                            for i in ids if i in SUP.index
                        )
                    )
                if r.Products_At_Risk:
                    st.markdown(f"**{T['products_affected']}:** {r.Products_At_Risk}")
            with c2:
                if r.Is_Risk == "Y":
                    st.markdown(f"**{T['annual_spend']}:** {eur(r.Spend_At_Risk_EUR)}")
                    if r.Min_Inventory_Days == r.Min_Inventory_Days and r.Min_Inventory_Days is not None:
                        duration_text = (
                            f"{r.Duration_Days:.0f} days" if lang == "en" else f"{r.Duration_Days:.0f} días"
                        ) if r.Duration_Days == r.Duration_Days and r.Duration_Days is not None else T["not_stated"]
                        day_unit = "days" if lang == "en" else "días"
                        st.markdown(
                            f"**{T['worst_inventory']}:** {r.Min_Inventory_Days:.0f} {day_unit} · "
                            f"**{T['estimated_duration']}:** {duration_text}"
                        )
                    st.markdown(f"**{T['recommended_action']}:** {display_action(r)}")
            confidence_text = CONFIDENCE_LABELS.get(str(r.Confidence).lower(), r.Confidence)
            reasoning = r.Reasoning
            if lang == "es":
                reasoning = (
                    str(reasoning)
                    .replace("p_risk=", "prob. riesgo=")
                    .replace("p_urgent=", "prob. urgencia=")
                    .replace("links:", "vínculos:")
                    .replace("no direct hint", "sin coincidencia directa")
                    .replace("no supplier linked", "sin proveedor vinculado")
                    .replace("positive keywords", "palabras clave positivas")
                    .replace("keyword rules", "reglas de palabras clave")
                    .replace("none", "ninguno")
                )
            st.caption(T["model_reasoning"].format(confidence=confidence_text, reasoning=reasoning))
with tabs[1]:
    if supplier_news:
        st.subheader(T["actions_title"])
        st.caption(T["actions_hint"])
        ordered_suppliers = sorted(
            supplier_news.items(),
            key=lambda item: (ORDER.get(item[1]["priority"], len(ORDER)), item[0]),
        )
        for start in range(0, len(ordered_suppliers), 3):
            columns = st.columns(3)
            for column, (supplier_id, entry) in zip(columns, ordered_suppliers[start:start + 3]):
                supplier = SUP.loc[supplier_id]
                alternate_id = supplier["Approved_Alternate_ID"]
                supplier_materials = MATERIALS[MATERIALS["Primary_Supplier_ID"] == supplier_id]
                inventory = supplier["Inventory_Cover_Days"]
                day_unit = "days" if lang == "en" else "días"
                inventory_text = f"{inventory:.0f} {day_unit}" if pd.notna(inventory) else T["no_data"]
                with column:
                    with st.container(border=True):
                        urgency_label = (
                            ("URGENT · " if lang == "en" else "URGENTE · ")
                            if entry["urgent_news_ids"] else ""
                        )
                        _bc = {"CRITICAL": "#ef4444", "HIGH": "#f97316", "MEDIUM": "#eab308", "LOW": "#3b82f6"}
                        _c = _bc.get(entry["priority"], "#6b7280")
                        st.markdown(f'<span style="background:{_c};color:white;padding:2px 10px;border-radius:10px;font-size:12px;font-weight:600">{urgency_label}{PRIORITY_LABELS[entry["priority"]]}</span>', unsafe_allow_html=True)
                        st.markdown(f"**{supplier_id} · {supplier['Supplier_Name']}**")
                        st.caption(
                            f"{COUNTRY_LABELS.get(supplier['Country'], supplier['Country'])} · "
                            f"{len(entry['news_ids'])} {T['alert_count']} · {T['inventory']}: {inventory_text}"
                        )

                        if isinstance(alternate_id, str) and alternate_id in SUP.index and alternate_id not in supplier_news:
                            matched_materials = supplier_materials[
                                supplier_materials["Alternate_Supplier_ID"] == alternate_id
                            ]
                            material_names = []
                            for material in matched_materials.itertuples():
                                name = str(material.Material)
                                if pd.notna(material.Monthly_Requirement):
                                    quantity = float(material.Monthly_Requirement)
                                    quantity_text = f"{quantity:.0f}" if quantity.is_integer() else f"{quantity:g}"
                                    month_unit = "month" if lang == "en" else "mes"
                                    name += f" ({quantity_text} {material.Unit}/{month_unit})"
                                material_names.append(name)
                            if not material_names:
                                material_names = [str(supplier["Material_Supplied"])]
                            product_names = sorted({
                                product.strip()
                                for products in matched_materials["Used_In_Products"].dropna().astype(str)
                                for product in products.split(";")
                                if product.strip()
                            })
                            material_text = ", ".join(material_names)
                            if product_names:
                                product_text = (
                                    f" for {', '.join(product_names)}" if lang == "en"
                                    else f" para {', '.join(product_names)}"
                                )
                            else:
                                product_text = ""
                            action = T["contact_alt"].format(
                                alt_id=alternate_id,
                                alt_name=SUP.loc[alternate_id, "Supplier_Name"],
                                materials=material_text,
                                products=product_text,
                            )
                        elif isinstance(alternate_id, str) and alternate_id in supplier_news:
                            action = T["confirm_supplier"].format(supplier=supplier_id, alternate=alternate_id)
                        else:
                            action = T["no_approved_alt"].format(supplier=supplier_id)
                        st.markdown(f"**{T['action']}:** {action}")
                        st.caption(f"{T['material']}: {supplier['Material_Supplied']}")
                        st.caption(f"{T['related_news']}: {', '.join(sorted(entry['news_ids']))}")
with tabs[2]:
    st.subheader(T["map_title"])
    if supplier_news:
        country_locations = {
            "Belgium": (50.5, 4.5),
            "Brazil": (-10.8, -52.9),
            "China": (35.9, 104.2),
            "Germany": (51.2, 10.5),
            "India": (22.6, 79.0),
            "Ireland": (53.1, -7.7),
            "Italy": (41.9, 12.6),
            "Japan": (36.2, 138.3),
            "Mexico": (23.6, -102.5),
            "Morocco": (31.8, -7.1),
            "Netherlands": (52.1, 5.3),
            "Norway": (61.0, 8.5),
            "Poland": (52.0, 19.1),
            "Puerto Rico (USA)": (18.2, -66.5),
            "Singapore": (1.35, 103.8),
            "Spain": (40.2, -3.7),
            "Switzerland": (46.8, 8.2),
            "Taiwan": (23.7, 121.0),
            "USA": (39.8, -98.6),
            "Vietnam": (16.2, 107.8),
        }
        country_exposure = {}
        for supplier_id, entry in supplier_news.items():
            supplier = SUP.loc[supplier_id]
            country = supplier["Country"]
            entry_country = country_exposure.setdefault(country, {
                "suppliers": [],
                "news_ids": set(),
                "urgent_news_ids": set(),
                "spend": 0.0,
                "priority": "LOW",
            })
            entry_country["suppliers"].append({
                "id": supplier_id,
                "name": supplier["Supplier_Name"],
                "material": supplier["Material_Supplied"],
                "priority": entry["priority"],
                "news_count": len(entry["news_ids"]),
                "urgent_count": len(entry["urgent_news_ids"]),
            })
            entry_country["news_ids"].update(entry["news_ids"])
            entry_country["urgent_news_ids"].update(entry["urgent_news_ids"])
            entry_country["spend"] += float(supplier["Annual_Spend_EUR"])
            if ORDER.get(entry["priority"], len(ORDER)) < ORDER.get(entry_country["priority"], len(ORDER)):
                entry_country["priority"] = entry["priority"]

        country_rows = []
        map_rows = []
        max_spend = max(item["spend"] for item in country_exposure.values())
        for country, entry in country_exposure.items():
            location = country_locations.get(country)
            suppliers_text = "\n".join(
                f"{item['id']} {item['name']} — {item['material']} | "
                f"{T['map_priority']}: {PRIORITY_LABELS[item['priority']]} | "
                f"{item['news_count']} {T['map_alerts']}, {item['urgent_count']} {T['map_urgent']}"
                for item in sorted(entry["suppliers"], key=lambda item: item["id"])
            )
            country_rows.append({
                T["country"]: COUNTRY_LABELS.get(country, country),
                T["affected_supplier_count"]: len(entry["suppliers"]),
                T["risk_news_count"]: len(entry["news_ids"]),
                T["urgent_count"]: len(entry["urgent_news_ids"]),
                T["spend_eur"]: entry["spend"],
                T["top_priority"]: PRIORITY_LABELS[entry["priority"]],
                T["suppliers_column"]: "; ".join(
                    f"{item['id']} {item['name']}" for item in sorted(entry["suppliers"], key=lambda item: item["id"])
                ),
            })
            if location:
                map_rows.append({
                    "latitude": location[0],
                    "longitude": location[1],
                    "radius": 90_000 + 260_000 * entry["spend"] / max_spend,
                    "fill_color": MAP_COLORS[entry["priority"]],
                    "tooltip": (
                        f"{COUNTRY_LABELS.get(country, country)}\n"
                        f"{T['affected_supplier_count']}: {len(entry['suppliers'])} | "
                        f"{T['risk_news_count']}: {len(entry['news_ids'])} | "
                        f"{T['urgent_count']}: {len(entry['urgent_news_ids'])}\n"
                        f"{T['annual_spend']}: {eur(entry['spend'])}\n"
                        f"{T['top_priority']}: {PRIORITY_LABELS[entry['priority']]}\n\n"
                        f"{suppliers_text}"
                    ),
                })

        country_table = pd.DataFrame(country_rows).sort_values(
            [T["spend_eur"], T["country"]], ascending=[False, True]
        )
        st.caption(T["map_hint"])
        st.caption(T["priority_legend"])
        if map_rows:
            layer = pdk.Layer(
                "ScatterplotLayer",
                data=pd.DataFrame(map_rows),
                get_position="[longitude, latitude]",
                get_radius="radius",
                get_fill_color="fill_color",
                get_line_color=[255, 255, 255, 220],
                line_width_min_pixels=1,
                stroked=True,
                filled=True,
                pickable=True,
                radius_min_pixels=8,
                radius_max_pixels=36,
            )
            deck = pdk.Deck(
                layers=[layer],
                initial_view_state=pdk.ViewState(latitude=25, longitude=0, zoom=1),
                map_provider="carto",
                tooltip={
                    "text": "{tooltip}",
                    "style": {
                        "backgroundColor": "#20242c",
                        "color": "white",
                        "fontSize": "13px",
                        "padding": "12px",
                        "maxWidth": "420px",
                        "whiteSpace": "pre-wrap",
                    },
                },
            )
            st.pydeck_chart(deck, use_container_width=True)
        unmapped = sorted(set(country_exposure) - set(country_locations))
        if unmapped:
            st.warning(T["unmapped"] + ", ".join(COUNTRY_LABELS.get(country, country) for country in unmapped))
        st.dataframe(country_table, use_container_width=True, hide_index=True)
    else:
        st.info(T["no_suppliers"])

with tabs[3]:
    _kpi_title = "Panel de indicadores clave" if lang == "es" else "Key Performance Indicators"
    st.subheader(_kpi_title)
    st.caption(
        "Metricas de riesgo de la cadena de suministro basadas en el analisis actual."
        if lang == "es" else
        "Supply chain risk metrics based on the current analysis."
    )

    _total_news = len(res)
    _total_risks = int((res.Is_Risk == "Y").sum())
    _total_urgent = int((res.Urgent == "Y").sum())
    _total_suppliers = len(SUP)
    _at_risk_ids = set()
    for _cell in res[res.Is_Risk == "Y"]["Affected_Supplier_IDs"]:
        _at_risk_ids.update(ids_of(_cell))
    _suppliers_at_risk = len(_at_risk_ids)
    _countries_at_risk = len({SUP.loc[s, "Country"] for s in _at_risk_ids if s in SUP.index})
    _spend_at_risk = sum(float(SUP.loc[s, "Annual_Spend_EUR"]) for s in _at_risk_ids if s in SUP.index)
    _total_spend = float(SUP["Annual_Spend_EUR"].sum())
    _single_source = SUP[SUP["Single_Source"] == "Y"]
    _ss_spend = float(_single_source["Annual_Spend_EUR"].sum())
    _ss_pct = round(_ss_spend / _total_spend * 100, 1) if _total_spend > 0 else 0
    _has_alt = SUP["Approved_Alternate_ID"].notna() & (SUP["Approved_Alternate_ID"] != "")
    _alt_pct = round(_has_alt.sum() / len(SUP) * 100, 1)
    _at_risk_sups = SUP.loc[[s for s in _at_risk_ids if s in SUP.index]]
    _min_inv = int(_at_risk_sups["Inventory_Cover_Days"].min()) if not _at_risk_sups.empty else None

    # Row 1: main KPIs
    _r1 = st.columns(4)
    _r1[0].metric(
        "Noticias analizadas" if lang == "es" else "News analyzed",
        _total_news,
    )
    _r1[1].metric(
        "Riesgos detectados" if lang == "es" else "Risks detected",
        _total_risks,
        delta=f"{_total_risks/_total_news*100:.0f}%" if _total_news else None,
    )
    _r1[2].metric(
        "Urgentes" if lang == "es" else "Urgent",
        _total_urgent,
    )
    _r1[3].metric(
        "Proveedores afectados" if lang == "es" else "Suppliers at risk",
        f"{_suppliers_at_risk} / {_total_suppliers}",
    )

    # Row 2: financial KPIs
    _r2 = st.columns(4)
    _r2[0].metric(
        "Gasto en riesgo" if lang == "es" else "Spend at risk",
        eur(_spend_at_risk),
        delta=f"{_spend_at_risk/_total_spend*100:.1f}% del total" if _total_spend else None,
        delta_color="inverse",
    )
    _r2[1].metric(
        "Paises afectados" if lang == "es" else "Countries affected",
        _countries_at_risk,
    )
    _r2[2].metric(
        "Proveedor unico" if lang == "es" else "Single source exposure",
        f"{_ss_pct}%",
        help="Porcentaje del gasto sin proveedor alternativo" if lang == "es" else "Spend percentage with no backup supplier",
    )
    _r2[3].metric(
        "Cobertura alternativa" if lang == "es" else "Alternative coverage",
        f"{_alt_pct}%",
        help="Proveedores con alternativa aprobada" if lang == "es" else "Suppliers with approved alternate",
    )

    st.divider()

    # Most Exposed Supplier (tarjeta destacada)
    if supplier_news:
        _top_all = sorted(supplier_news.items(), key=lambda x: (-len(x[1]["news_ids"]), x[0]))
        _top_sid, _top_entry = _top_all[0]
        _top_sup = SUP.loc[_top_sid]
        _top_prio = PRIORITY_LABELS.get(_top_entry["priority"], _top_entry["priority"])

        st.markdown(
            f"""<div style="border: 2px solid #3b82f6; border-radius: 12px; padding: 20px; margin: 10px 0;
            background: linear-gradient(135deg, #eff6ff 0%, #dbeafe 100%);">
            <p style="color: #6b7280; font-size: 13px; margin: 0;">{'Proveedor mas expuesto' if lang == 'es' else 'Most Exposed Supplier'}</p>
            <h2 style="margin: 4px 0; color: #1e293b;">{_top_sid} · {_top_sup['Supplier_Name']}</h2>
            <p style="color: #64748b; margin: 0;">
                {COUNTRY_LABELS.get(_top_sup['Country'], _top_sup['Country'])} ·
                {len(_top_entry['news_ids'])} {'alertas' if lang == 'es' else 'alerts'} ·
                {'Prioridad' if lang == 'es' else 'Priority'}: {_top_prio} ·
                {'Material' if lang == 'es' else 'Material'}: {_top_sup['Material_Supplied']}
            </p></div>""",
            unsafe_allow_html=True,
        )
    else:
        st.info("Sin proveedores afectados" if lang == "es" else "No affected suppliers")

    st.divider()

    # Graficos complementarios
    _g1, _g2 = st.columns(2)

    with _g1:
        st.markdown(f"**{'Alertas por prioridad' if lang == 'es' else 'Alerts by priority'}**")
        _prio_counts = {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0}
        for _p in res[res.Is_Risk == "Y"]["Priority"]:
            if _p in _prio_counts:
                _prio_counts[_p] += 1
        _prio_df = pd.DataFrame([
            {"priority": PRIORITY_LABELS.get(k, k), "count": v}
            for k, v in _prio_counts.items()
        ])
        st.bar_chart(_prio_df.set_index("priority"), height=250)

    with _g2:
        st.markdown(f"**{'Proveedores en riesgo por pais' if lang == 'es' else 'Suppliers at risk by country'}**")
        _country_counts = {}
        for _sid in _at_risk_ids:
            if _sid in SUP.index:
                _c = COUNTRY_LABELS.get(SUP.loc[_sid, "Country"], SUP.loc[_sid, "Country"])
                _country_counts[_c] = _country_counts.get(_c, 0) + 1
        if _country_counts:
            _cc_df = pd.DataFrame([{"country": k, "suppliers": v} for k, v in sorted(_country_counts.items(), key=lambda x: -x[1])])
            st.bar_chart(_cc_df.set_index("country"), height=250)

    # Top 5 proveedores
    if supplier_news:
        st.markdown(f"**{'Top 5 proveedores mas expuestos' if lang == 'es' else 'Top 5 most exposed suppliers'}**")
        _top5 = sorted(supplier_news.items(), key=lambda x: (-len(x[1]["news_ids"]), x[0]))[:5]
        _top_cols = st.columns(len(_top5))
        for _col, (_sid, _entry) in zip(_top_cols, _top5):
            with _col:
                _sup = SUP.loc[_sid]
                _prio_label = PRIORITY_LABELS.get(_entry["priority"], _entry["priority"])
                with st.container(border=True):
                    st.metric(_sup["Supplier_Name"], f"{len(_entry['news_ids'])} {'alertas' if lang == 'es' else 'alerts'}")
                    st.caption(f"{_prio_label} · {COUNTRY_LABELS.get(_sup['Country'], _sup['Country'])}")

with tabs[4]:
    st.subheader("Alertas en vivo — noticias scrapeadas" if lang == "es" else "Live news alerts — scraped articles")
    st.caption(
        "Noticias recogidas automáticamente de prensa internacional y nacional, clasificadas por riesgo."
        if lang == "es" else
        "News automatically collected from international and national press, classified by risk."
    )
    _sb_url = os.environ.get("SUPABASE_URL", "")
    _sb_key = os.environ.get("SUPABASE_KEY", "")
    if _sb_url and _sb_key:
        _sb_h = {"apikey": _sb_key, "Authorization": f"Bearer {_sb_key}"}
        _sb_risks = requests.get(
            f"{_sb_url}/rest/v1/scraped_news?select=*&predicted_risk=gte.0.5&order=confidence.desc&limit=50",
            headers=_sb_h,
        ).json() if _sb_url else []
        _sb_all = requests.get(
            f"{_sb_url}/rest/v1/scraped_news?select=id",
            headers={**_sb_h, "Prefer": "count=exact", "Range": "0-0"},
        )
        _total = _sb_all.headers.get("content-range", "0-0/0").split("/")[-1]

        lk1, lk2, lk3 = st.columns(3)
        lk1.metric("Total noticias" if lang == "es" else "Total articles", _total)
        lk2.metric("Alertas" if lang == "es" else "Alerts", len(_sb_risks))
        lk3.metric("Fuentes" if lang == "es" else "Sources",
                    len({r.get("source") for r in _sb_risks}) if _sb_risks else 0)

        if not _sb_risks:
            st.success("No se han detectado riesgos en las noticias recientes." if lang == "es" else "No risks detected in recent news.")
        else:
            _prio_order = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}
            _prio_colors = {"CRITICAL": "#f4a6a6", "HIGH": "#f8cbad", "MEDIUM": "#ffe699", "LOW": "#dbeafe"}

            def _live_priority(row):
                text = (row.get("title") or "").lower() + " " + (row.get("summary") or "").lower()
                sids = ids_of(row.get("predicted_supplier_ids") or "")
                stop = any(k in text for k in ["halt", "suspend", "shut", "close", "recall", "ban"])
                single = any(sid in SUP.index and SUP.loc[sid, "Single_Source"] == "Y" for sid in sids)
                crit = any(sid in SUP.index and SUP.loc[sid, "Criticality"] in ("Critical", "High") for sid in sids)
                if stop and (single or crit):
                    return "CRITICAL"
                if stop:
                    return "HIGH"
                if crit or single:
                    return "MEDIUM"
                return "LOW"

            for row in sorted(_sb_risks, key=lambda r: _prio_order.get(_live_priority(r), 4)):
                prio = _live_priority(row)
                bg = _prio_colors.get(prio, "#fff")
                prio_label = PRIORITY_LABELS.get(prio, prio)
                event = row.get("predicted_event_type") or "?"
                event_text = EVENT_LABELS.get(event, event)
                title = row.get("title") or ""
                summary = row.get("summary") or ""
                url = row.get("url") or ""
                source = row.get("source") or ""
                sids = ids_of(row.get("predicted_supplier_ids") or "")

                with st.container(border=True):
                    _bc2 = {"CRITICAL": "#ef4444", "HIGH": "#f97316", "MEDIUM": "#eab308", "LOW": "#3b82f6"}
                    _c2 = _bc2.get(prio, "#6b7280")
                    st.markdown(f'<span style="background:{_c2};color:white;padding:2px 10px;border-radius:10px;font-size:12px;font-weight:600">{prio_label}</span>', unsafe_allow_html=True)
                    st.markdown(f"**{title}**")
                    st.write(summary[:500])
                    c1, c2 = st.columns([2, 1])
                    with c1:
                        if url:
                            st.markdown(f"[{'Leer noticia completa' if lang == 'es' else 'Read full article'}]({url})")
                        st.caption(f"{'Fuente' if lang == 'es' else 'Source'}: {source} · {'Tipo' if lang == 'es' else 'Type'}: {event_text}")
                    with c2:
                        if sids:
                            for sid in sids:
                                if sid in SUP.index:
                                    sup = SUP.loc[sid]
                                    alt_id = sup.get("Approved_Alternate_ID")
                                    st.error(f"🔴 {sid} — {sup['Supplier_Name']} ({sup['Country']})")
                                    if isinstance(alt_id, str) and alt_id in SUP.index:
                                        alt = SUP.loc[alt_id]
                                        st.success(f"🟢 {alt_id} — {alt['Supplier_Name']} ({alt['Country']})")
                                    else:
                                        st.warning("⚠️ Sin alternativa aprobada" if lang == "es" else "⚠️ No approved alternate")
    else:
        st.warning("Configura SUPABASE_URL y SUPABASE_KEY en .env para ver las alertas en vivo." if lang == "es"
                   else "Set SUPABASE_URL and SUPABASE_KEY in .env to see live alerts.")

with tabs[5]:
    st.subheader("Alertas climáticas" if lang == "es" else "Weather alerts")
    st.caption(
        "Previsión meteorológica de Open-Meteo para las ciudades de los proveedores. Destaca condiciones adversas."
        if lang == "es" else
        "Open-Meteo weather forecast for supplier cities. Highlights adverse conditions."
    )
    _supplier_cities = {}
    for sid in SUP.index:
        s = SUP.loc[sid]
        city = s.get("City", "")
        country = s.get("Country", "")
        if city and country:
            key = f"{city}, {country}"
            _supplier_cities.setdefault(key, []).append({"id": sid, "name": s["Supplier_Name"], "material": s["Material_Supplied"]})

    _city_coords = {
        "Ahmedabad, India": (23.02, 72.57), "Vadodara, India": (22.31, 73.18),
        "Shanghai, China": (31.23, 121.47), "Mumbai, India": (19.08, 72.88),
        "Frankfurt, Germany": (50.11, 8.68), "Mainz, Germany": (50.0, 8.27),
        "Basel, Switzerland": (47.56, 7.59), "Milan, Italy": (45.46, 9.19),
        "Bergamo, Italy": (45.69, 9.67), "Barcelona, Spain": (41.39, 2.17),
        "Dublin, Ireland": (53.35, -6.26), "Brussels, Belgium": (50.85, 4.35),
        "Antwerp, Belgium": (51.22, 4.40), "Hsinchu, Taiwan": (24.80, 120.97),
        "Hanoi, Vietnam": (21.03, 105.85), "Ho Chi Minh City, Vietnam": (10.82, 106.63),
        "Monterrey, Mexico": (25.69, -100.32), "Sao Paulo, Brazil": (-23.55, -46.63),
        "Singapore, Singapore": (1.35, 103.82), "Tokyo, Japan": (35.68, 139.69),
        "Warsaw, Poland": (52.23, 21.01), "Casablanca, Morocco": (33.57, -7.59),
        "Oslo, Norway": (59.91, 10.75), "Amsterdam, Netherlands": (52.37, 4.90),
        "San Juan, Puerto Rico (USA)": (18.47, -66.11), "Cork, Ireland": (51.90, -8.47),
    }

    _weather_alerts = []
    for city_key, sups_list in _supplier_cities.items():
        coords = _city_coords.get(city_key)
        if not coords:
            continue
        try:
            wr = requests.get("https://api.open-meteo.com/v1/forecast", params={
                "latitude": coords[0], "longitude": coords[1],
                "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum,wind_speed_10m_max,weather_code",
                "timezone": "auto", "forecast_days": 3,
            }, timeout=5)
            if wr.status_code != 200:
                continue
            wd = wr.json().get("daily", {})
            dates = wd.get("time", [])
            temps_max = wd.get("temperature_2m_max", [])
            precip = wd.get("precipitation_sum", [])
            wind = wd.get("wind_speed_10m_max", [])
            codes = wd.get("weather_code", [])

            for i, date in enumerate(dates):
                alert_type = None
                if i < len(codes) and codes[i] in (95, 96, 99):
                    alert_type = "Tormenta severa" if lang == "es" else "Severe storm"
                elif i < len(precip) and precip[i] and precip[i] > 50:
                    alert_type = "Lluvia intensa" if lang == "es" else "Heavy rain"
                elif i < len(wind) and wind[i] and wind[i] > 80:
                    alert_type = "Viento fuerte" if lang == "es" else "Strong wind"
                elif i < len(temps_max) and temps_max[i] and temps_max[i] > 42:
                    alert_type = "Calor extremo" if lang == "es" else "Extreme heat"
                elif i < len(temps_max) and temps_max[i] is not None and temps_max[i] < -10:
                    alert_type = "Frío extremo" if lang == "es" else "Extreme cold"

                if alert_type:
                    _weather_alerts.append({
                        "city": city_key, "date": date, "type": alert_type,
                        "temp_max": temps_max[i] if i < len(temps_max) else None,
                        "precip": precip[i] if i < len(precip) else None,
                        "wind": wind[i] if i < len(wind) else None,
                        "suppliers": sups_list,
                    })
        except Exception:
            continue

    if _weather_alerts:
        st.warning(f"{'Se detectaron' if lang == 'es' else 'Detected'} {len(_weather_alerts)} {'alertas climáticas' if lang == 'es' else 'weather alerts'}")
        for wa in _weather_alerts:
            with st.container(border=True):
                _wc = "#ef4444" if "severa" in wa["type"].lower() or "severe" in wa["type"].lower() else "#f97316"
                st.markdown(f'<span style="background:{_wc};color:white;padding:2px 10px;border-radius:10px;font-size:12px;font-weight:600">{wa["type"]}</span>', unsafe_allow_html=True)
                st.markdown(f"**{wa['city']}** — {wa['date']}")
                mc1, mc2, mc3 = st.columns(3)
                if wa["temp_max"] is not None:
                    mc1.metric("Temp. max", f"{wa['temp_max']:.0f}°C")
                if wa["precip"] is not None:
                    mc2.metric("Precipitación" if lang == "es" else "Precipitation", f"{wa['precip']:.0f} mm")
                if wa["wind"] is not None:
                    mc3.metric("Viento" if lang == "es" else "Wind", f"{wa['wind']:.0f} km/h")
                st.caption(
                    f"{'Proveedores afectados' if lang == 'es' else 'Affected suppliers'}: " +
                    ", ".join(f"{s['id']} {s['name']}" for s in wa["suppliers"])
                )
    else:
        st.success(
            "No se prevén condiciones meteorológicas adversas en las próximas 72 h en las zonas de proveedores."
            if lang == "es" else
            "No adverse weather conditions forecast in the next 72h for supplier zones."
        )

    st.divider()
    st.caption(
        "Datos de [Open-Meteo](https://open-meteo.com/) (API gratuita, sin necesidad de API key)"
        if lang == "es" else
        "Data from [Open-Meteo](https://open-meteo.com/) (free API, no key required)"
    )

with tabs[6]:
    st.subheader("Revisar noticias — Active Learning" if lang == "es" else "Review articles — Active Learning")
    st.caption(
        "Noticias donde el modelo tiene menos confianza (0.3–0.7). Etiquetar estas primero mejora más el modelo."
        if lang == "es" else
        "Articles where the model has low confidence (0.3–0.7). Labeling these first maximizes model improvement."
    )
    if _sb_url and _sb_key:
        _al_h = {"apikey": _sb_key, "Authorization": f"Bearer {_sb_key}"}
        _al_news = requests.get(
            f"{_sb_url}/rest/v1/scraped_news?select=*&confidence=gte.0.15&confidence=lte.0.7&is_labeled=eq.false&order=confidence.asc&limit=30",
            headers=_al_h,
        ).json() if _sb_url else []

        if not _al_news:
            _al_news = requests.get(
                f"{_sb_url}/rest/v1/scraped_news?select=*&is_labeled=eq.false&order=id.desc&limit=30",
                headers=_al_h,
            ).json()

        al1, al2 = st.columns(2)
        al1.metric("Pendientes de revisar" if lang == "es" else "Pending review", len(_al_news))
        risk_pct = sum(1 for r in _al_news if (r.get("predicted_risk") or 0) >= 0.5) / max(len(_al_news), 1) * 100
        al2.metric("Prediccion riesgo" if lang == "es" else "Predicted risk", f"{risk_pct:.0f}%")

        for row in _al_news:
            conf = row.get("confidence") or 0
            p_risk = row.get("predicted_risk") or 0
            title = row.get("title") or ""
            summary = row.get("summary") or ""
            event = row.get("predicted_event_type") or "?"
            event_text = EVENT_LABELS.get(event, event)
            url = row.get("url") or ""
            source = row.get("source") or ""

            risk_icon = "🔴" if p_risk >= 0.5 else "⚪"
            conf_bar = "🟩" * int(conf * 10) + "⬜" * (10 - int(conf * 10))

            with st.container(border=True):
                rc1, rc2 = st.columns([3, 1])
                with rc1:
                    st.markdown(f"{risk_icon} **{title}**")
                    if summary:
                        st.write(summary[:300])
                    link_text = f"[{'Leer' if lang == 'es' else 'Read'}]({url})" if url else ""
                    st.caption(f"{source} · {event_text} {link_text}")
                with rc2:
                    st.caption(f"{'Confianza' if lang == 'es' else 'Confidence'}: {conf:.0%}")
                    st.caption(conf_bar)
                    is_risk_val = st.selectbox(
                        "Riesgo?" if lang == "es" else "Risk?",
                        ["—", "Sí" if lang == "es" else "Yes", "No"],
                        key=f"al_risk_{row['id']}",
                    )
                    if is_risk_val != "—":
                        is_r = is_risk_val in ("Sí", "Yes")
                        requests.patch(
                            f"{_sb_url}/rest/v1/scraped_news?id=eq.{row['id']}",
                            headers={**_al_h, "Content-Type": "application/json"},
                            json={"is_labeled": True, "is_risk": is_r},
                        )
                        st.success("✓" if lang == "en" else "✓ Guardado")
    else:
        st.warning("Configura SUPABASE_URL y SUPABASE_KEY en .env" if lang == "es" else "Set SUPABASE_URL and SUPABASE_KEY in .env")

buf = io.BytesIO()
save_excel(res, buf)
st.download_button(T["download"], buf.getvalue(), "supplier_risk_result.xlsx",
                   mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
