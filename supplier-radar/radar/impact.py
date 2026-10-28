"""Capa de impacto de negocio: convierte 'S002; S006' en gasto en riesgo, stock frente a duracion,
alternativas y productos afectados. Todo sale de las tablas de proveedores y materiales."""
import re

import pandas as pd

WORDS = {"a": 1, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8,
         "nine": 9, "ten": 10, "twelve": 12}
UNIT_DAYS = {"hour": 1 / 24, "day": 1, "week": 7, "month": 30}
PAT = re.compile(r"\b(\d+|a|one|two|three|four|five|six|seven|eight|nine|ten|twelve)[\s-]+(hour|day|week|month)s?\b", re.I)


def extract_days(text: str) -> float | None:
    """Duracion mas larga que se menciona en el texto, en dias. 'weeks' a secas = 14, 'months' = 60."""
    best = None
    for n, unit in PAT.findall(text):
        v = (int(n) if n.isdigit() else WORDS[n.lower()]) * UNIT_DAYS[unit.lower()]
        best = v if best is None else max(best, v)
    if best is None:
        t = text.lower()
        if re.search(r"\bmonths\b", t):
            best = 60.0
        elif re.search(r"\bweeks\b", t):
            best = 14.0
    return best


def ids_of(cell) -> list[str]:
    if not isinstance(cell, str) or not cell.strip():
        return []
    return [i.strip() for i in cell.split(";") if i.strip()]


def eur(x: float) -> str:
    return f"{x / 1e6:.1f} M EUR" if x >= 1e6 else f"{x / 1e3:.0f} k EUR"


def impact(is_risk: bool, urgent: bool, ids: list[str], text: str, sup: pd.DataFrame, mat: pd.DataFrame) -> dict:
    s = sup.set_index("Supplier_ID")
    ids = [i for i in ids if i in s.index]
    days = extract_days(text)
    if not ids or not is_risk:
        return {"Spend_At_Risk_EUR": 0, "Duration_Days": days, "Min_Inventory_Days": None, "Stockout_Risk": "",
                "Single_Source_Affected": "", "Alternates": "", "Products_At_Risk": "", "Priority": "LOW" if not is_risk else "MEDIUM",
                "Action": "No action needed." if not is_risk else "Monitor."}
    spend = float(s.loc[ids, "Annual_Spend_EUR"].sum())
    cover = s.loc[ids, "Inventory_Cover_Days"].dropna()
    min_cover = float(cover.min()) if len(cover) else None
    single = [i for i in ids if s.loc[i, "Single_Source"] == "Y"]
    alts = []
    for i in ids:
        a = s.loc[i, "Approved_Alternate_ID"]
        if isinstance(a, str) and a in s.index:
            alts.append(f"{i}->{a} {s.loc[a, 'Supplier_Name']}" + (" (also affected)" if a in ids else ""))
    prods = sorted({p.strip() for i in ids for _, m in mat[mat.Primary_Supplier_ID == i].iterrows()
                    for p in str(m.Used_In_Products).split(";") if p.strip()})
    if days is None or min_cover is None:
        stock = "unknown"
    else:
        stock = "Y" if days > min_cover else "N"
    crit_high = any(s.loc[i, "Criticality"] == "High" for i in ids)

    if urgent and (single or stock == "Y"):
        prio = "CRITICAL"
    elif urgent:
        prio = "HIGH"
    elif crit_high or single:
        prio = "MEDIUM"
    else:
        prio = "LOW"

    acts = []
    if single:
        acts.append(f"Single source ({', '.join(single)}) with no approved alternate: secure stock and start qualifying a second source.")
    if alts:
        acts.append("Shift volume to the approved alternate where possible: " + "; ".join(alts) + ".")
    if stock == "Y":
        acts.append(f"Event (~{days:.0f} d) may outlast inventory ({min_cover:.0f} d): expedite orders now.")
    elif stock == "N":
        acts.append(f"Inventory ({min_cover:.0f} d) covers the expected ~{days:.0f} d: monitor and review weekly.")
    elif min_cover is not None:
        acts.append(f"Duration not stated; inventory covers {min_cover:.0f} d at the weakest supplier: ask the supplier for a restart date.")
    return {
        "Spend_At_Risk_EUR": spend, "Duration_Days": days, "Min_Inventory_Days": min_cover, "Stockout_Risk": stock,
        "Single_Source_Affected": ", ".join(single), "Alternates": "; ".join(alts), "Products_At_Risk": "; ".join(prods),
        "Priority": prio, "Action": " ".join(acts) or "Monitor.",
    }


def enrich(res: pd.DataFrame, news: pd.DataFrame, sup: pd.DataFrame, mat: pd.DataFrame) -> pd.DataFrame:
    """Anade columnas de impacto al DataFrame de resultados (mismo orden que news)."""
    texts = dict(zip(news["News_ID"], news["text"]))
    rows = [impact(r.Is_Risk == "Y", r.Urgent == "Y", ids_of(r.Affected_Supplier_IDs), texts.get(r.News_ID, ""), sup, mat)
            for r in res.itertuples()]
    return pd.concat([res.reset_index(drop=True), pd.DataFrame(rows)], axis=1)
