"""Distillation: Claude clasifica noticias de Supabase para generar etiquetas de alta calidad.

Toma noticias de Supabase, las envia a Claude con el mismo prompt del sistema que usa
el pipeline, y guarda las etiquetas en Supabase y en data/claude_labels.csv.

  python3 distill_claude.py                     # clasifica las sin etiquetar
  python3 distill_claude.py --limit 100         # solo 100
  python3 distill_claude.py --dry-run           # muestra sin guardar
"""
from __future__ import annotations

import argparse
import json
import os
import time

import pandas as pd
import requests
from dotenv import load_dotenv

from radar.analyze import SYSTEM, supplier_table
from radar.config import DATA
from radar.data import load_suppliers
from radar.impact import ids_of

load_dotenv()

SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "")
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")


def _sb_headers():
    return {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}", "Content-Type": "application/json"}


def fetch_unlabeled(limit: int) -> list[dict]:
    r = requests.get(
        f"{SUPABASE_URL}/rest/v1/scraped_news?select=*&is_labeled=eq.false&order=id.desc&limit={limit}",
        headers=_sb_headers(),
    )
    return r.json() if r.status_code == 200 else []


def classify_with_claude(title: str, summary: str, sup_table: str) -> dict | None:
    """Envia una noticia a Claude y devuelve la clasificacion estructurada."""
    if not ANTHROPIC_API_KEY:
        print("[!] ANTHROPIC_API_KEY no configurada")
        return None

    user_prompt = f"""Supplier list:
{sup_table}

News article:
Headline: {title}
Summary: {summary}"""

    try:
        r = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": ANTHROPIC_API_KEY,
                "anthropic-version": "2026-10-21",
                "content-type": "application/json",
            },
            json={
                "model": "claude-haiku-4-5-20251001",
                "max_tokens": 300,
                "system": SYSTEM,
                "messages": [{"role": "user", "content": user_prompt}],
            },
            timeout=30,
        )
        if r.status_code != 200:
            print(f"  [!] Claude API: {r.status_code} {r.text[:100]}")
            return None

        text = r.json()["content"][0]["text"]
        start = text.find("{")
        end = text.rfind("}") + 1
        if start >= 0 and end > start:
            return json.loads(text[start:end])
    except Exception as e:
        print(f"  [!] Claude: {type(e).__name__}")
    return None


def save_to_supabase(news_id: int, result: dict):
    valid_ids = {s.Supplier_ID for s in load_suppliers().itertuples()}
    sids = [s for s in result.get("affected_supplier_ids", []) if s in valid_ids]

    payload = {
        "is_labeled": True,
        "is_risk": result.get("is_risk", False),
        "urgent": result.get("is_risk", False) and result.get("supply_impact") == "stoppage" and result.get("duration") != "short",
        "event_type": result.get("event_type", "Not relevant"),
        "affected_supplier_ids": "; ".join(sids) if sids else None,
        "predicted_risk": 1.0 if result.get("is_risk") else 0.0,
        "predicted_urgent": 1.0 if result.get("is_risk") and result.get("supply_impact") == "stoppage" else 0.0,
        "predicted_event_type": result.get("event_type"),
        "predicted_supplier_ids": "; ".join(sids) if sids else None,
        "confidence": {"high": 0.9, "medium": 0.7, "low": 0.4}.get(result.get("confidence", "medium"), 0.7),
    }
    requests.patch(f"{SUPABASE_URL}/rest/v1/scraped_news?id=eq.{news_id}",
                   headers=_sb_headers(), json=payload)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=200)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if not ANTHROPIC_API_KEY:
        print("Necesitas configurar ANTHROPIC_API_KEY en .env")
        print("  echo 'ANTHROPIC_API_KEY=sk-ant-...' >> .env")
        return

    sups = load_suppliers()
    table = supplier_table(sups)

    print(f"Obteniendo noticias sin etiquetar (limit={args.limit})...")
    news = fetch_unlabeled(args.limit)
    print(f"  {len(news)} noticias")

    if not news:
        print("  Nada que clasificar.")
        return

    results = []
    risk_count = 0

    for i, row in enumerate(news):
        title = row.get("title", "")
        summary = row.get("summary", "")
        print(f"  [{i+1}/{len(news)}] {title[:60]}...", end=" ", flush=True)

        result = classify_with_claude(title, summary, table)
        if result is None:
            print("SKIP")
            continue

        is_risk = result.get("is_risk", False)
        if is_risk:
            risk_count += 1
        print(f"{'RISK' if is_risk else 'ok'} ({result.get('event_type', '?')})")

        results.append({
            "News_ID": f"CL_{row['id']}",
            "Headline": title,
            "Summary": summary,
            "Is_Risk": "Y" if is_risk else "N",
            "Urgent": "Y" if result.get("is_risk") and result.get("supply_impact") == "stoppage" and result.get("duration") != "short" else "N",
            "Event_Type": result.get("event_type", "Not relevant"),
            "Affected_Supplier_IDs": "; ".join(result.get("affected_supplier_ids", [])),
            "text": f"{title}. {summary}",
            "confidence": result.get("confidence", "medium"),
            "reasoning": result.get("reasoning", ""),
        })

        if not args.dry_run:
            save_to_supabase(row["id"], result)

        time.sleep(0.5)

    print(f"\n  Total: {len(results)} clasificadas, {risk_count} riesgos")

    if results:
        df = pd.DataFrame(results)
        out = DATA / "claude_labels.csv"
        df.to_csv(out, index=False)
        print(f"  Guardado en {out}")


if __name__ == "__main__":
    main()
