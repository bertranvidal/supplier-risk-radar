
"""Ruido REAL para entrenar: noticias de negocio genericas (ag_news, categoria Business) como 'no relevante'.

Ensenan al modelo a no saltar con cualquier noticia economica. Se descartan las que contienen palabras de incidente
o cualquier pista de nuestros proveedores, para no etiquetar mal ninguna. Requiere internet.

  python3 fetch_negatives.py --n 800     # genera data/neg_news.csv
"""
import argparse

import pandas as pd

from radar.config import DATA
from radar.data import load_suppliers
from radar.matcher import Matcher

BAD = ["fire", "flood", "earthquake", "storm", "hurricane", "strike", "recall", "ban ", "sanction", "explosion", "cyber",
       "hack", "bankrupt", "shutdown", "shut down", "evacuat", "outage", "blast", "crash", "tariff", "plant", "factory",
       "drug", "pharma", "chemical", "supplier", "shortage", "port ", "shipping"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=800)
    ap.add_argument("--seed", type=int, default=7)
    a = ap.parse_args()
    from datasets import load_dataset

    ds = load_dataset("fancyzhx/ag_news", split="train")
    df = ds.to_pandas()
    df = df[df["label"] == 2]  # Business
    m = Matcher(load_suppliers())
    rows = []
    for t in df.sample(frac=1, random_state=a.seed)["text"]:
        low = t.lower()
        if any(b in low for b in BAD) or m.hints(t):
            continue
        rows.append(t.strip())
        if len(rows) >= a.n:
            break
    out = pd.DataFrame({
        "News_ID": [f"NEG{i:04d}" for i in range(len(rows))], "Headline": rows, "Summary": "",
        "Is_Risk": "N", "Urgent": "N", "Affected_Supplier_IDs": "", "Event_Type": "Not relevant",
        "Supply_Impact": "none", "Duration": "unknown", "Explanation": "generic business news"})
    out["text"] = out["Headline"]
    out.to_csv(DATA / "neg_news.csv", index=False)
    print(f"neg_news.csv: {len(out)} noticias genericas")


if __name__ == "__main__":
    main()
