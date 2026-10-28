"""Exporta noticias etiquetadas de Supabase para reentrenar los modelos.

Combina las noticias etiquetadas manualmente (is_labeled=true) de Supabase
con los datos de entrenamiento originales (Excel) y las sinteticas.

  python3 export_training.py                     # exporta a data/supabase_train.csv
  python3 export_training.py --include-predicted  # incluye tambien las clasificadas por rules
"""
from __future__ import annotations

import argparse
import os

import pandas as pd
import requests
from dotenv import load_dotenv

from radar.config import DATA

load_dotenv()

SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "")
OUT = DATA / "supabase_train.csv"


def fetch_labeled(include_predicted: bool = False) -> pd.DataFrame:
    """Trae noticias etiquetadas de Supabase."""
    h = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"}

    if include_predicted:
        url = f"{SUPABASE_URL}/rest/v1/scraped_news?select=*&predicted_risk=not.is.null&limit=2000"
    else:
        url = f"{SUPABASE_URL}/rest/v1/scraped_news?select=*&is_labeled=eq.true&limit=2000"

    r = requests.get(url, headers=h)
    r.raise_for_status()
    rows = r.json()

    if not rows:
        return pd.DataFrame()

    records = []
    for row in rows:
        is_risk = row.get("is_risk")
        if is_risk is None and include_predicted:
            is_risk = (row.get("predicted_risk") or 0) >= 0.5

        records.append({
            "News_ID": f"SB_{row['id']}",
            "Headline": row.get("title", ""),
            "Summary": row.get("summary", ""),
            "Is_Risk": "Y" if is_risk else "N",
            "Urgent": "Y" if row.get("urgent") or (row.get("predicted_urgent") or 0) >= 0.5 else "N",
            "Event_Type": row.get("event_type") or row.get("predicted_event_type") or "Not relevant",
            "Affected_Supplier_IDs": row.get("affected_supplier_ids") or row.get("predicted_supplier_ids") or "",
            "source": row.get("source", ""),
            "label_quality": "manual" if row.get("is_labeled") else "predicted",
        })

    return pd.DataFrame(records)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--include-predicted", action="store_true",
                        help="incluir noticias clasificadas automaticamente (no solo las manuales)")
    args = parser.parse_args()

    print("Exportando datos de Supabase...")
    df = fetch_labeled(args.include_predicted)
    print(f"  {len(df)} noticias de Supabase")

    if df.empty:
        print("  No hay noticias etiquetadas. Usa classify_supabase.py primero.")
        return

    risk_count = (df["Is_Risk"] == "Y").sum()
    print(f"  {risk_count} riesgos, {len(df) - risk_count} no-riesgos")

    df.to_csv(OUT, index=False)
    print(f"  Guardado en {OUT}")
    print(f"\n  Para reentrenar, estos datos se combinan automaticamente con los sinteticos")
    print(f"  y los datos de train.xlsx al ejecutar train_text.py / train_link.py")


if __name__ == "__main__":
    main()
