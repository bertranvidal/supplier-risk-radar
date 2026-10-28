"""Pasos 4-6: prompt + LLM + reglas deterministas. Tambien un modo 'rules' sin LLM (linea base)."""
from dataclasses import dataclass

import pandas as pd

from . import llm
from .data import load_suppliers
from .examples import Retriever, format_example
from .matcher import Matcher, hints_text
from .pairs import pair_b
from .schema import EVENT_TYPES, Verdict

SYSTEM = """You are a supply-chain risk analyst for Helixa Pharmaceuticals. You read ONE news article and decide whether it is a supply risk for any of Helixa's 40 suppliers (list given below).

Rules:
1. is_risk = true only if the article describes an event that negatively affects (or threatens) a Helixa supplier: the supplier itself, its site, the city/region where it is located, the material it supplies, or the transport route its goods depend on.
2. NOT a risk: look-alike names (e.g. 'Orion Capital' is not 'Orion Synthesis AG', a football club called 'Celtic' is not 'Celtic BioLogics'), a place mentioned with nothing disrupted (conference, airport records, a weather forecast, investment news), macro or general business news, unrelated companies.
3. Positive news about a supplier (approval, capacity expansion, supply deal, financing, clean inspection): is_risk=false, event_type='Positive news', and list the supplier it is about.
4. Affected suppliers: every supplier located in the affected area (a disaster in a region affects ALL suppliers in its cities, e.g. Gujarat covers Ahmedabad and Vadodara), the supplier named, suppliers of a restricted material in the affected country, and suppliers whose goods travel through a disrupted route or port. Use the full supplier list and the detected hints. Only use IDs from the list. If is_risk is false and it is not positive news about a supplier, the list is empty.
5. supply_impact: 'stoppage' = production or deliveries are halted or can be halted (plant closed, evacuation, production licence suspended, recall, export ban, insolvency / going concern doubt, island-wide outage lasting weeks). 'delay' = slower, costlier or partial disruption (strikes, rerouting, low river levels, rationing, blocked road, warehouse stock loss with production intact, rating downgrade, leadership change). 'none' = no supply effect.
6. duration: 'short' = a few days or a temporary precaution (about 1 week or less, e.g. 48-hour closure, brief safety checks, 3-day strike); 'long' = weeks or months; 'unknown' = not stated.
7. Be conservative: do not invent suppliers that are not supported by the text or by a clear geographic / material link.

Answer ONLY with JSON in this shape:
{"event_type": "Natural disaster", "is_risk": true, "supply_impact": "stoppage", "duration": "long", "affected_supplier_ids": ["S002", "S006"], "confidence": "high", "reasoning": "one or two sentences"}
Allowed event_type values: """ + ", ".join(EVENT_TYPES)


def supplier_table(s: pd.DataFrame) -> str:
    return "\n".join(
        f"{r.Supplier_ID} | {r.Supplier_Name} | {r.City}, {r.Country} | {r.Material_Supplied} ({r.Category})"
        for r in s.itertuples()
    )


@dataclass
class Context:
    suppliers: pd.DataFrame
    matcher: Matcher
    retriever: Retriever
    table: str

    @classmethod
    def build(cls, pool: pd.DataFrame) -> "Context":
        s = load_suppliers()
        return cls(s, Matcher(s), Retriever(pool), supplier_table(s))


def build_prompt(row: pd.Series, ctx: Context, k: int = 6) -> str:
    hints = ctx.matcher.hints(row.text)
    ex = ctx.retriever.top(row.text, k=k, exclude_id=row.News_ID)
    shots = "\n\n".join(format_example(e) for e in ex)
    return (
        "HELIXA SUPPLIERS (ID | name | location | material):\n" + ctx.table
        + "\n\nDETECTED HINTS IN THE ARTICLE:\n" + hints_text(hints)
        + "\n\nSIMILAR ARTICLES ALREADY LABELLED BY EXPERTS (use them to calibrate):\n\n" + shots
        + "\n\nNEW ARTICLE TO ANALYSE:\n" + row.Headline + ". " + row.Summary
        + "\n\nAnswer with the JSON only."
    )


def finalize(v: Verdict, valid_ids: set[str]) -> dict:
    """Reglas deterministas encima de la respuesta del LLM."""
    ids = sorted({i for i in v.affected_supplier_ids if i in valid_ids})
    is_risk = v.is_risk
    note = ""
    if is_risk and not ids:
        is_risk = False  # un riesgo sin proveedor afectado no es un riesgo para Helixa
        note = "no supplier linked"
    if not is_risk and v.event_type != "Positive news":
        ids = []
    urgent = is_risk and v.supply_impact == "stoppage" and v.duration != "short"
    return {
        "Is_Risk": "Y" if is_risk else "N",
        "Urgent": "Y" if urgent else "N",
        "Affected_Supplier_IDs": "; ".join(ids),
        "Event_Type": v.event_type,
        "Supply_Impact": v.supply_impact,
        "Duration": v.duration,
        "Confidence": "low" if note else v.confidence,
        "Reasoning": (v.reasoning + (" [" + note + "]" if note else "")).strip(),
    }


# ----------------------------------------------------------------------------- modo 'rules' (sin LLM)
KW_EVENTS = [
    ("Fire / plant incident", ["fire", "explosion", "blaze"]),
    ("Natural disaster", ["flood", "earthquake", "hurricane", "typhoon", "cyclone", "storm", "wildfire", "landslide", "tsunami"]),
    ("Quality recall", ["recall", "contamination", "particles"]),
    ("Regulatory action", ["suspend", "licence", "license", "warning letter", "ban"]),
    ("Export restriction", ["export restriction", "export licensing", "export ban", "tariff"]),
    ("Labour strike", ["strike", "walkout"]),
    ("Financial distress", ["going concern", "bankruptcy", "insolvency", "downgrade", "missed"]),
    ("Utility outage", ["power cut", "power outage", "rationing", "blackout"]),
    ("Logistics disruption", ["blockade", "blocked", "barge", "reroute", "port congestion", "shipping lines", "protest"]),
    ("Cyber attack", ["cyberattack", "cyber attack", "ransomware"]),
    ("Leadership change", ["steps down", "resigns", "chief executive"]),
    ("Acquisition by competitor", ["acquire", "acquisition"]),
]
KW_POS = ["completes", "no observations", "approval", "doubles", "signs", "secures", "expand", "record", "wins"]
KW_STOP = ["evacuat", "halted", "suspend", "paused production", "closed", "recall", "going concern", "export", "ban", "outage"]
KW_SHORT = ["48 hours", "two days", "three-day", "3-day", "safety checks", "precaution", "overnight"]
KW_LONG = ["weeks", "months", "indefinite"]


NOT_SUPPLY_CHAIN = [
    "football", "soccer", "basketball", "tennis", "rugby", "cricket", "olympic",
    "election", "vote", "ballot", "political party", "campaign",
    "teacher", "profesor", "profesores", "student protest", "university protest",
    "education reform", "school", "classroom", "educacion", "educación",
    "colegio", "universidad", "docente",
    "cinema", "film festival", "concert", "album", "celebrity",
    "tourism", "hotel", "restaurant", "nightlife",
    "fashion week", "art exhibition", "museum", "art fair", "art basel", "gallery",
    "pension reform", "retirement age",
    "taxi driver", "taxista", "uber", "cabify", "vtc", "sector del taxi",
    "taxi protesta", "paros del taxi", "huelga del taxi",
    "disturbio", "revuelta", "saqueo", "enfrentamiento callejero",
    "chalecos amarillos",
]
NOT_SUPPLY_RE = "|".join(NOT_SUPPLY_CHAIN)


def rules_verdict(row: pd.Series, ctx: Context) -> Verdict:
    t = row.text.lower()
    hints = ctx.matcher.hints(row.text)
    # solo proveedores con match fuerte (nombre o ciudad, no solo pais)
    solid = [h["id"] for h in hints if h["score"] >= 2]
    event = next((e for e, kws in KW_EVENTS if any(k in t for k in kws)), None)
    # descartar noticias que no afectan a la cadena de suministro (educacion, deporte, politica, etc.)
    if event and any(k in t for k in NOT_SUPPLY_CHAIN):
        has_supply_kw = any(k in t for k in ["supplier", "factory", "plant", "pharma", "chemical",
                                              "drug", "medicine", "shipping", "port", "warehouse",
                                              "proveedor", "fabrica", "planta", "farmac", "quimic",
                                              "medicamento", "puerto", "almacen"])
        if not has_supply_kw:
            return Verdict(event_type="Not relevant", is_risk=False, confidence="medium",
                           reasoning="keyword rules: event detected but not supply-chain related")
    positive = any(k in t for k in KW_POS) and event in (None, "Acquisition by competitor")
    if positive and solid:
        return Verdict(event_type="Positive news", is_risk=False, affected_supplier_ids=solid[:1], confidence="low", reasoning="positive keywords")
    if event and solid:
        stop = any(k in t for k in KW_STOP)
        short = any(k in t for k in KW_SHORT)
        long_ = any(k in t for k in KW_LONG)
        return Verdict(
            event_type=event, is_risk=True,
            supply_impact="stoppage" if stop else "delay",
            duration="short" if short else ("long" if long_ else "unknown"),
            affected_supplier_ids=solid, confidence="low", reasoning="keyword rules",
        )
    return Verdict(event_type="Not relevant", is_risk=False, confidence="low", reasoning="keyword rules")


# ----------------------------------------------------------------------------- modo 'models' (nuestros modelos afinados)
def finalize_models(t: dict, probs: dict, hints: dict, thr=0.5) -> dict:
    """t = salida del modelo de texto; probs = prob. de vinculacion por proveedor.
    thr puede ser un float (mismo para todo) o un dict con claves risk/urgent/link."""
    if isinstance(thr, dict):
        thr_r, thr_u, thr_l = thr.get("risk", 0.5), thr.get("urgent", 0.5), thr.get("link", 0.5)
    else:
        thr_r = thr_u = thr_l = thr
    ev = t["event"]
    positive = ev == "Positive news"
    is_risk = t["p_risk"] >= thr_r and not positive
    ids = sorted(i for i, p in probs.items() if p >= thr_l)
    note = ""
    if is_risk and not ids:
        is_risk, note = False, "no supplier linked"
    if not is_risk and not positive:
        ids = []
    urgent = is_risk and t["p_urgent"] >= thr_u
    margin = min(abs(t["p_risk"] - 0.5), abs(t["p_urgent"] - 0.5) if is_risk else 0.5) * 2
    top = sorted(((p, i) for i, p in probs.items() if p >= thr_l), reverse=True)[:3]
    why = "; ".join(f"{i} {p:.2f}" + (f" ({'/'.join(hints[i])})" if i in hints else " (no direct hint)") for p, i in top)
    return {
        "Is_Risk": "Y" if is_risk else "N",
        "Urgent": "Y" if urgent else "N",
        "Affected_Supplier_IDs": "; ".join(ids),
        "Event_Type": ev,
        "Supply_Impact": "",
        "Duration": "",
        "Confidence": "low" if note else ("high" if margin > 0.6 else "medium" if margin > 0.3 else "low"),
        "Reasoning": f"p_risk={t['p_risk']:.2f}, p_urgent={t['p_urgent']:.2f}; links: {why or 'none'}" + (f" [{note}]" if note else ""),
    }


def models_result(row: pd.Series, ctx: Context) -> dict:
    from .models import get_models

    m = get_models()
    t = m.predict_text([row.text])[0]
    hmap = {h["id"]: h["reasons"] for h in ctx.matcher.hints(row.text)}
    sups = list(ctx.suppliers.itertuples())
    sc = m.score_links(row.text, [pair_b(x, hmap.get(x.Supplier_ID, [])) for x in sups])
    return finalize_models(t, {x.Supplier_ID: p for x, p in zip(sups, sc)}, hmap)


def analyze(row: pd.Series, ctx: Context, mode: str = "llm", k: int = 6) -> tuple[dict, str]:
    """Devuelve (resultado, prompt usado). El prompt sirve de clave de cache."""
    valid = set(ctx.suppliers.Supplier_ID)
    if mode == "models":
        return models_result(row, ctx), ""
    if mode == "rules":
        return finalize(rules_verdict(row, ctx), valid), ""
    prompt = build_prompt(row, ctx, k)
    v = llm.ask_structured(prompt, SYSTEM, Verdict)
    return finalize(v, valid), prompt
