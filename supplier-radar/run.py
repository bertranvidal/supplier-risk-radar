"""Procesa un Excel de noticias SIN tocar el fichero ni el codigo y exporta una fila por noticia.

  python3 run.py data/Supplier_Risk_3_Test.xlsx
  python3 run.py my_news.xlsx --out out/my_result.xlsx      # any Excel with the same columns as the Test file
"""
import argparse
from pathlib import Path

from radar.config import OUT
from radar.data import load_news
from radar.pipeline import analyze_news, load_pool, save_excel


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("file", help="Excel with the news to analyse")
    ap.add_argument("--out", default=None)
    ap.add_argument("--mode", default="models", choices=["models", "rules", "llm"])
    ap.add_argument("--workers", type=int, default=None)
    ap.add_argument("--no-cache", action="store_true")
    a = ap.parse_args()

    news = load_news(a.file)
    pool = load_pool(include_valid=True)  # train + validation como ejemplos; nunca test
    res = analyze_news(news, pool, a.mode, workers=a.workers, use_cache=not a.no_cache)

    OUT.mkdir(exist_ok=True)
    out = Path(a.out) if a.out else OUT / (Path(a.file).stem + "_result.xlsx")
    save_excel(res, out)
    print("Excel escrito en", out)
    print(res[["News_ID", "Is_Risk", "Urgent", "Affected_Supplier_IDs"]].to_string(index=False))


if __name__ == "__main__":
    main()
