"""Genera neg_news.csv con noticias genericas de Supabase que NO son riesgo.

Alternativa a fetch_negatives.py que no necesita datasets/pyarrow.
Usa las noticias de Supabase que fueron clasificadas como no-riesgo.

  python3 gen_negatives.py
"""
import os

import pandas as pd
import requests
from dotenv import load_dotenv

from radar.config import DATA
from radar.data import load_suppliers
from radar.matcher import Matcher

load_dotenv()

SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "")

BAD = ["fire", "flood", "earthquake", "storm", "hurricane", "strike", "recall",
       "ban ", "sanction", "explosion", "cyber", "hack", "bankrupt", "shutdown",
       "evacuat", "outage", "blast", "tariff", "plant closed", "factory",
       "drug shortage", "supplier", "shortage", "port closure"]


def main():
    h = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"}
    r = requests.get(
        f"{SUPABASE_URL}/rest/v1/scraped_news?select=title,summary&predicted_risk=lt.0.3&limit=1000",
        headers=h,
    )
    rows = r.json()
    print(f"Noticias candidatas de Supabase: {len(rows)}")

    m = Matcher(load_suppliers())
    neg = []
    for row in rows:
        title = row.get("title") or ""
        summary = row.get("summary") or ""
        text = f"{title}. {summary}"
        low = text.lower()
        if any(b in low for b in BAD):
            continue
        if m.hints(text):
            continue
        neg.append({
            "News_ID": f"NEG_{len(neg)}",
            "Headline": title,
            "Summary": summary[:500],
            "Is_Risk": "N",
            "Urgent": "N",
            "Event_Type": "Not relevant",
            "Affected_Supplier_IDs": "",
            "text": f"{title}. {summary}",
        })
        if len(neg) >= 800:
            break

    df = pd.DataFrame(neg)
    out = DATA / "neg_news.csv"
    df.to_csv(out, index=False)
    print(f"Guardadas {len(df)} noticias negativas en {out}")


if __name__ == "__main__":
    main()
