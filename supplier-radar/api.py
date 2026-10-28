"""Backend API del Supplier Radar."""

from __future__ import annotations

import io
from collections import Counter
from typing import Any

import pandas as pd
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from radar import config, data as radar_data, impact, pipeline

app = FastAPI(title="Supplier Radar API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_last_results: pd.DataFrame | None = None


def _df_to_records(df: pd.DataFrame) -> list[dict]:
    return df.where(pd.notnull(df), None).to_dict(orient="records")


class AnalyzeRequest(BaseModel):
    source: str
    mode: str


@app.get("/api/suppliers")
def get_suppliers() -> list[dict]:
    return _df_to_records(radar_data.load_suppliers())


@app.get("/api/materials")
def get_materials() -> list[dict]:
    return _df_to_records(radar_data.load_materials())


@app.post("/api/analyze")
def analyze(req: AnalyzeRequest) -> list[dict]:
    global _last_results

    source_map = {"test": config.TEST, "validation": config.VALID}
    if req.source not in source_map:
        raise HTTPException(400, f"Source desconocido: {req.source}")
    if req.mode not in ("rules", "models"):
        raise HTTPException(400, f"Mode desconocido: {req.mode}")

    news_df = radar_data.load_news(source_map[req.source])
    pool_df = pipeline.load_pool(include_valid=True)
    _last_results = pipeline.analyze_news(news_df, pool_df, mode=req.mode)
    return _df_to_records(_last_results)


@app.get("/api/results")
def get_results() -> list[dict]:
    if _last_results is None:
        raise HTTPException(404, "Ejecuta un analisis primero.")
    return _df_to_records(_last_results)


@app.get("/api/kpis")
def get_kpis() -> dict[str, Any]:
    if _last_results is None:
        raise HTTPException(404, "Ejecuta un analisis primero.")

    df = _last_results.copy()
    df["_is_risk"] = df["Is_Risk"].astype(str).str.upper().str.strip()
    risk_df = df[df["_is_risk"] == "Y"]

    total_alerts = int(risk_df["News_ID"].nunique())
    critical_alerts = int(
        risk_df[risk_df["Priority"].astype(str).str.upper() == "CRITICAL"]["News_ID"].nunique()
    )

    all_affected: list[str] = []
    for cell in risk_df["Affected_Supplier_IDs"]:
        all_affected.extend(impact.ids_of(cell))

    suppliers_at_risk = len(set(all_affected))
    suppliers_df = radar_data.load_suppliers()
    affected_set = set(all_affected)
    affected_suppliers = suppliers_df[suppliers_df["Supplier_ID"].astype(str).isin(affected_set)]
    countries_affected = int(affected_suppliers["Country"].nunique())

    most_exposed: dict[str, Any] = {}
    if all_affected:
        top_id, top_count = Counter(all_affected).most_common(1)[0]
        row = suppliers_df[suppliers_df["Supplier_ID"].astype(str) == top_id]
        if not row.empty:
            r = row.iloc[0]
            most_exposed = {"id": top_id, "name": r.get("Supplier_Name", ""),
                            "country": r.get("Country", ""), "alert_count": top_count}
        else:
            most_exposed = {"id": top_id, "name": "", "country": "", "alert_count": top_count}

    spend_at_risk = float(risk_df["Spend_At_Risk_EUR"].sum()) if "Spend_At_Risk_EUR" in df.columns else 0
    total_spend = float(suppliers_df["Annual_Spend_EUR"].sum())

    ss = suppliers_df[suppliers_df["Single_Source"] == "Yes"]
    ss_pct = round(float(ss["Annual_Spend_EUR"].sum()) / total_spend * 100, 1) if total_spend > 0 else 0

    has_alt = suppliers_df["Approved_Alternate_ID"].notna() & (suppliers_df["Approved_Alternate_ID"] != "")
    alt_pct = round(has_alt.sum() / len(suppliers_df) * 100, 1) if len(suppliers_df) > 0 else 0

    ar = suppliers_df[suppliers_df["Supplier_ID"].astype(str).isin(affected_set)]
    stockout = None
    if not ar.empty and "Inventory_Cover_Days" in ar.columns:
        inv = ar["Inventory_Cover_Days"].dropna()
        if len(inv):
            stockout = int(inv.min())

    cat_risk: dict[str, float] = {}
    for sid in affected_set:
        row = suppliers_df[suppliers_df["Supplier_ID"].astype(str) == sid]
        if not row.empty:
            cat = row.iloc[0].get("Category", "Other")
            cat_risk[cat] = cat_risk.get(cat, 0) + float(row.iloc[0].get("Annual_Spend_EUR", 0))

    ev_counts: dict[str, int] = {}
    for ev in risk_df.get("Event_Type", []):
        if ev:
            ev_counts[ev] = ev_counts.get(ev, 0) + 1

    urg = int(risk_df[risk_df["Urgent"].astype(str).str.upper() == "Y"]["News_ID"].nunique()) if "Urgent" in risk_df.columns else 0

    return {
        "total_alerts": total_alerts, "critical_alerts": critical_alerts,
        "suppliers_at_risk": suppliers_at_risk, "countries_affected": countries_affected,
        "most_exposed_supplier": most_exposed,
        "spend_at_risk": spend_at_risk, "total_spend": total_spend,
        "single_source_pct": ss_pct, "alt_coverage_pct": alt_pct,
        "stockout_countdown": stockout, "category_risk": cat_risk,
        "event_counts": ev_counts, "urgent_count": urg,
    }


@app.get("/api/alternatives/{supplier_id}")
def get_alternatives(supplier_id: str) -> list[dict]:
    suppliers_df = radar_data.load_suppliers()
    materials_df = radar_data.load_materials()

    primary = materials_df[materials_df["Primary_Supplier_ID"].astype(str) == supplier_id]
    results = []
    for _, m in primary.iterrows():
        alt_id = str(m.get("Alternate_Supplier_ID", "")) if pd.notna(m.get("Alternate_Supplier_ID")) else None
        alt_details: dict[str, Any] = {}
        if alt_id:
            alt_sup = suppliers_df[suppliers_df["Supplier_ID"].astype(str) == alt_id]
            if not alt_sup.empty:
                alt_details = alt_sup.iloc[0].where(pd.notnull(alt_sup.iloc[0]), None).to_dict()
        results.append({
            "material_id": m.get("Material_ID"), "material": m.get("Material"),
            "alternate_supplier_id": alt_id,
            "alternate_supplier_name": m.get("Alternate_Supplier_Name", ""),
            "alternate_supplier_details": alt_details,
        })
    return results


@app.get("/api/export")
def export_results() -> StreamingResponse:
    if _last_results is None:
        raise HTTPException(404, "Ejecuta un analisis primero.")
    buf = io.BytesIO()
    pipeline.save_excel(_last_results, buf)
    buf.seek(0)
    return StreamingResponse(
        buf, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=supplier_radar_results.xlsx"},
    )
