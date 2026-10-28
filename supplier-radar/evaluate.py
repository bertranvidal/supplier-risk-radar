"""Mide el sistema contra noticias con respuesta (validation por defecto).

  python3 evaluate.py --data val
  python3 evaluate.py --data val --mode rules      # linea base sin LLM
  python3 evaluate.py --data train --no-cache
"""
import argparse

import pandas as pd

from radar.config import DATASETS, OUT
from radar.data import is_labelled, load_news
from radar.pipeline import load_pool, process


def ids(x) -> set:
    if not isinstance(x, str) or not x.strip():
        return set()
    return {i.strip() for i in x.split(";") if i.strip()}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="val", choices=["train", "val", "holdout"])
    ap.add_argument("--mode", default="models", choices=["models", "rules", "llm"])
    ap.add_argument("--workers", type=int, default=None)
    ap.add_argument("--no-cache", action="store_true")
    a = ap.parse_args()

    if a.data == "train" and a.mode == "models":
        print("AVISO: los modelos se entrenan con train; medir en train es en la muestra, no vale como acierto real.")
    news = load_news(DATASETS[a.data])
    assert is_labelled(news), "este fichero no tiene respuestas"
    # val: ejemplos solo de train. train/holdout: train+val (a cada noticia se le excluye ella misma en el retriever)
    pool = load_pool(include_valid=(a.data != "val"))
    pred = process(news, pool, a.mode, a.workers, use_cache=not a.no_cache)

    df = news[["News_ID", "Headline", "Is_Risk", "Urgent", "Affected_Supplier_IDs"]].merge(
        pred.drop(columns=["Headline"]), on="News_ID", suffixes=("_gold", "_pred"))
    ok_risk = df.Is_Risk_gold == df.Is_Risk_pred
    ok_urg = df.Urgent_gold == df.Urgent_pred
    tp = fp = fn = 0
    exact = []
    for _, r in df.iterrows():
        g, p = ids(r.Affected_Supplier_IDs_gold), ids(r.Affected_Supplier_IDs_pred)
        tp += len(g & p)
        fp += len(p - g)
        fn += len(g - p)
        exact.append(g == p)
    prec = tp / (tp + fp) if tp + fp else 0
    rec = tp / (tp + fn) if tp + fn else 0
    f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0

    print("\n===== RESULTADOS (" + a.data + ", modo " + a.mode + ") =====")
    print(f"Is_Risk  accuracy: {ok_risk.mean():.0%}  ({ok_risk.sum()}/{len(df)})")
    print(f"Urgent   accuracy: {ok_urg.mean():.0%}  ({ok_urg.sum()}/{len(df)})")
    print(f"Proveedores  precision {prec:.0%}  recall {rec:.0%}  F1 {f1:.0%}  | listas exactas: {sum(exact)}/{len(df)}")
    print(f"Tiempo: {pred.attrs['seconds']:.1f} s")

    bad = df[~(ok_risk & ok_urg & pd.Series(exact, index=df.index))]
    if len(bad):
        print("\n----- ERRORES -----")
    for _, r in bad.iterrows():
        print(f"\n{r.News_ID}  {r.Headline}")
        print(f"   esperado: Is_Risk={r.Is_Risk_gold} Urgent={r.Urgent_gold} Prov={r.Affected_Supplier_IDs_gold if isinstance(r.Affected_Supplier_IDs_gold, str) else '-'}")
        print(f"   obtenido: Is_Risk={r.Is_Risk_pred} Urgent={r.Urgent_pred} Prov={r.Affected_Supplier_IDs_pred or '-'}  [{r.Event_Type}, {r.Supply_Impact}, {r.Duration}]")
        print(f"   motivo del modelo: {r.Reasoning}")

    OUT.mkdir(exist_ok=True)
    path = OUT / f"eval_{a.data}_{a.mode}.xlsx"
    df.to_excel(path, index=False)
    print("\nDetalle guardado en", path)


if __name__ == "__main__":
    main()
