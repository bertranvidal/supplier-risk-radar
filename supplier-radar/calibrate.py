"""Calibra los umbrales de decision (riesgo, urgencia, vinculacion) con noticias que los modelos NO han visto.

  python3 calibrate.py                  # usa el examen independiente data/Supplier_Risk_Holdout.xlsx
  python3 calibrate.py --data val       # solo si los modelos se entrenaron SIN validacion

Prueba una rejilla gruesa (0.30 ... 0.70) y solo se aparta de 0.5 si la mejora es clara (>= --min-gain),
porque con ~20 noticias un ajuste fino seria sobreajustar. Escribe models/thresholds.json.
"""
import argparse
import itertools
import json

from radar.analyze import Context, finalize_models
from radar.config import DATASETS, MODELS
from radar.data import is_labelled, load_news
from radar.models import get_models
from radar.pairs import pair_b
from radar.pipeline import load_pool


def ids(x) -> set:
    return {i.strip() for i in x.split(";") if i.strip()} if isinstance(x, str) else set()


def score(news, raw, thr) -> tuple[float, dict]:
    ok_r = ok_u = tp = fp = fn = 0
    for r, (t, probs, hmap) in zip(news.itertuples(), raw):
        res = finalize_models(t, probs, hmap, thr)
        ok_r += res["Is_Risk"] == r.Is_Risk
        ok_u += res["Urgent"] == r.Urgent
        g, p = ids(r.Affected_Supplier_IDs), ids(res["Affected_Supplier_IDs"])
        tp, fp, fn = tp + len(g & p), fp + len(p - g), fn + len(g - p)
    n = len(news)
    prec, rec = tp / (tp + fp) if tp + fp else 0, tp / (tp + fn) if tp + fn else 0
    f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0
    return ok_r / n + ok_u / n + f1, {"risk": ok_r / n, "urgent": ok_u / n, "f1": f1}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="holdout", choices=["val", "holdout"])
    ap.add_argument("--min-gain", type=float, default=0.05, help="mejora minima (suma de 3 metricas) para moverse de 0.5")
    a = ap.parse_args()

    news = load_news(DATASETS[a.data])
    assert is_labelled(news), "este fichero no tiene respuestas"
    ctx = Context.build(load_pool(include_valid=(a.data != "val")))
    m = get_models()
    print(f"ensemble: {m.n_text} modelos de texto + {m.n_link} de vinculacion; {len(news)} noticias")

    sups = list(ctx.suppliers.itertuples())
    raw = []
    for row in news.itertuples():
        t = m.predict_text([row.text])[0]
        hmap = {h["id"]: h["reasons"] for h in ctx.matcher.hints(row.text)}
        sc = m.score_links(row.text, [pair_b(x, hmap.get(x.Supplier_ID, [])) for x in sups])
        raw.append((t, {x.Supplier_ID: p for x, p in zip(sups, sc)}, hmap))

    base_thr = {"risk": 0.5, "urgent": 0.5, "link": 0.5}
    base_score, base_m = score(news, raw, base_thr)
    print(f"con 0.5/0.5/0.5 -> riesgo {base_m['risk']:.0%}  urgente {base_m['urgent']:.0%}  proveedores F1 {base_m['f1']:.0%}")

    grid = [0.30, 0.40, 0.50, 0.60, 0.70]
    best, best_thr, best_m = base_score, base_thr, base_m
    for r, u, l in itertools.product(grid, grid, grid):
        thr = {"risk": r, "urgent": u, "link": l}
        s, mm = score(news, raw, thr)
        dist = abs(r - .5) + abs(u - .5) + abs(l - .5)
        best_dist = sum(abs(v - .5) for v in best_thr.values())
        if s > best + 1e-9 or (abs(s - best) < 1e-9 and dist < best_dist):  # a igualdad, el mas cercano a 0.5
            best, best_thr, best_m = s, thr, mm
    if best - base_score < a.min_gain:
        best_thr, best_m = base_thr, base_m
        print(f"mejora {best - base_score:+.3f} < {a.min_gain}: se mantiene 0.5 (no merece la pena ajustar)")
    else:
        print(f"umbrales elegidos {best_thr} -> riesgo {best_m['risk']:.0%}  urgente {best_m['urgent']:.0%}  F1 {best_m['f1']:.0%}")
    (MODELS / "thresholds.json").write_text(json.dumps(best_thr, indent=2), encoding="utf-8")
    print("guardado en", MODELS / "thresholds.json")


if __name__ == "__main__":
    main()
