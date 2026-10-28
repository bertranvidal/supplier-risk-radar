"""Clasifica las noticias de Supabase con el pipeline del radar y guarda las predicciones.

  python3 classify_supabase.py                    # clasifica con rules (no necesita GPU)
  python3 classify_supabase.py --mode models      # clasifica con los modelos entrenados
  python3 classify_supabase.py --limit 100        # solo las 100 mas recientes
  python3 classify_supabase.py --unlabeled        # solo las que no tienen prediccion
"""
from __future__ import annotations

import argparse
import os

import pandas as pd
import requests
from dotenv import load_dotenv

from radar.analyze import Context, rules_verdict
from radar.config import TRAIN, VALID
from radar.data import load_news
from radar.pipeline import load_pool

load_dotenv()

SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "")


def _headers():
    return {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}", "Content-Type": "application/json"}


def fetch_news(limit: int, unlabeled_only: bool) -> list[dict]:
    """Trae noticias de Supabase."""
    url = f"{SUPABASE_URL}/rest/v1/scraped_news?select=*&order=id.desc&limit={limit}"
    if unlabeled_only:
        url += "&predicted_risk=is.null"
    r = requests.get(url, headers=_headers())
    r.raise_for_status()
    return r.json()


def update_prediction(news_id: int, pred: dict):
    """Actualiza una fila con la prediccion del modelo."""
    payload = {
        "predicted_risk": pred.get("p_risk"),
        "predicted_urgent": pred.get("p_urgent"),
        "predicted_event_type": pred.get("event_type"),
        "predicted_supplier_ids": pred.get("supplier_ids"),
        "confidence": pred.get("confidence"),
    }
    r = requests.patch(
        f"{SUPABASE_URL}/rest/v1/scraped_news?id=eq.{news_id}",
        headers=_headers(), json=payload,
    )
    if r.status_code not in (200, 204):
        print(f"  [!] update id={news_id}: {r.status_code}")


def classify_rules(news_rows: list[dict]) -> list[dict]:
    """Clasifica con el modo rules (baseline sin modelos)."""
    pool = load_pool(include_valid=True)
    ctx = Context.build(pool)

    results = []
    for row in news_rows:
        text = f"{row.get('title', '')}. {row.get('summary', '')}"
        fake_row = pd.Series({"text": text, "News_ID": str(row["id"]), "Headline": row.get("title", "")})
        v = rules_verdict(fake_row, ctx)
        pred = {
            "p_risk": 1.0 if v.is_risk else 0.0,
            "p_urgent": 1.0 if (v.is_risk and v.supply_impact == "stoppage" and v.duration != "short") else 0.0,
            "event_type": v.event_type,
            "supplier_ids": "; ".join(v.affected_supplier_ids) if v.affected_supplier_ids else None,
            "confidence": 1.0 if v.confidence == "high" else 0.5 if v.confidence == "medium" else 0.2,
        }
        results.append({"id": row["id"], "title": row.get("title", ""), "pred": pred})
    return results


def classify_models(news_rows: list[dict]) -> list[dict]:
    """Clasifica con los modelos entrenados (text + link)."""
    from radar.models import get_models

    pool = load_pool(include_valid=True)
    ctx = Context.build(pool)
    m = get_models()

    texts = [f"{r.get('title', '')}. {r.get('summary', '')}" for r in news_rows]
    text_preds = m.predict_text(texts)

    results = []
    for row, tp in zip(news_rows, text_preds):
        text = f"{row.get('title', '')}. {row.get('summary', '')}"
        hints = ctx.matcher.hints(text)
        link_probs = m.predict_links(text, hints)

        ids = sorted(i for i, p in link_probs.items() if p >= 0.5)
        pred = {
            "p_risk": tp["p_risk"],
            "p_urgent": tp["p_urgent"],
            "event_type": tp["event"],
            "supplier_ids": "; ".join(ids) if ids else None,
            "confidence": tp["p_risk"],
        }
        results.append({"id": row["id"], "title": row.get("title", ""), "pred": pred})
    return results


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["rules", "models"], default="rules")
    parser.add_argument("--limit", type=int, default=500)
    parser.add_argument("--unlabeled", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    print(f"Obteniendo noticias de Supabase (limit={args.limit}, unlabeled={args.unlabeled})...")
    news = fetch_news(args.limit, args.unlabeled)
    print(f"  {len(news)} noticias")

    if not news:
        print("  Nada que clasificar.")
        return

    print(f"Clasificando con modo '{args.mode}'...")
    if args.mode == "rules":
        results = classify_rules(news)
    else:
        results = classify_models(news)

    risk_count = sum(1 for r in results if r["pred"]["p_risk"] >= 0.5)
    print(f"  {risk_count}/{len(results)} detectadas como riesgo")

    if args.dry_run:
        for r in results[:20]:
            risk = "RISK" if r["pred"]["p_risk"] >= 0.5 else "ok"
            print(f"  [{risk:4s}] {r['pred']['event_type']:25s} {r['title'][:70]}")
        return

    print("Guardando predicciones en Supabase...")
    for r in results:
        update_prediction(r["id"], r["pred"])
    print(f"  {len(results)} predicciones guardadas")


if __name__ == "__main__":
    main()
