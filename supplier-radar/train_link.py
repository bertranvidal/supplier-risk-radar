"""Afina NUESTRO modelo de vinculacion noticia-proveedor (cross-encoder) desde un reranker preentrenado.

  python3 train_link.py                    # sinteticas + train real; mide en validacion
  python3 train_link.py --with-val         # version final
  python3 train_link.py --base BAAI/bge-reranker-base --epochs 3
"""
import argparse
import random

import numpy as np
import pandas as pd
import torch
import torch.nn.functional as F
from transformers import AutoModelForSequenceClassification, AutoTokenizer, get_linear_schedule_with_warmup

from radar.config import HOLDOUT, MODELS, TRAIN, VALID
from radar.data import load_extra, load_news, load_suppliers
from radar.matcher import Matcher
from radar.pairs import build_pairs, ids_of
from radar.synth import load_synth


def make_batches(pairs, tok, bs, dev, shuffle):
    idx = list(range(len(pairs)))
    if shuffle:
        random.shuffle(idx)
    for i in range(0, len(idx), bs):
        j = [pairs[k] for k in idx[i:i + bs]]
        enc = tok([p[0] for p in j], [p[1] for p in j], truncation="only_first", max_length=256,
                  padding=True, return_tensors="pt").to(dev)
        yield enc, torch.tensor([float(p[2]) for p in j], device=dev)


def scores(model, tok, pairs, dev):
    model.eval()
    out = []
    with torch.no_grad():
        for enc, _ in make_batches(pairs, tok, 64, dev, False):
            out += torch.sigmoid(model(**enc).logits.squeeze(-1).float()).cpu().tolist()
    return np.array(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="BAAI/bge-reranker-base")
    ap.add_argument("--epochs", type=int, default=3)
    ap.add_argument("--lr", type=float, default=2e-5)
    ap.add_argument("--bs", type=int, default=32)
    ap.add_argument("--neg", type=int, default=8, help="negativos aleatorios por noticia sintetica")
    ap.add_argument("--real-weight", type=int, default=4)
    ap.add_argument("--with-val", action="store_true")
    ap.add_argument("--with-holdout", action="store_true", help="version final: incluye tambien el examen independiente")
    ap.add_argument("--out", default=str(MODELS / "link"))
    ap.add_argument("--seed", type=int, default=7)
    a = ap.parse_args()

    random.seed(a.seed); np.random.seed(a.seed); torch.manual_seed(a.seed)
    dev = "cuda" if torch.cuda.is_available() else "cpu"
    sup = load_suppliers()
    matcher = Matcher(sup)

    real = load_news(TRAIN)
    val = load_news(VALID)
    if a.with_val:
        real = pd.concat([real, val], ignore_index=True)
    if a.with_holdout:
        real = pd.concat([real, load_news(HOLDOUT)], ignore_index=True)
    pairs = build_pairs(load_synth(), sup, matcher, n_neg=a.neg, seed=a.seed)
    for name, df in load_extra():  # parafrasis, reescrituras con LLM, ruido real (si se han generado)
        pairs += build_pairs(df, sup, matcher, n_neg=a.neg, seed=a.seed)
        print(f"  + {len(df)} noticias de {name}", flush=True)
    pairs += build_pairs(real, sup, matcher, n_neg=None) * a.real_weight  # reales: todos los pares
    random.shuffle(pairs)
    pos = sum(p[2] for p in pairs)
    print(f"pares: {len(pairs)} ({pos} positivos)", flush=True)

    tok = AutoTokenizer.from_pretrained(a.base)
    model = AutoModelForSequenceClassification.from_pretrained(a.base, num_labels=1, ignore_mismatched_sizes=True).to(dev)
    steps = a.epochs * ((len(pairs) + a.bs - 1) // a.bs)
    opt = torch.optim.AdamW(model.parameters(), lr=a.lr, weight_decay=0.01)
    sch = get_linear_schedule_with_warmup(opt, int(0.1 * steps), steps)
    pos_w = torch.tensor((len(pairs) - pos) / max(pos, 1), device=dev).clamp(max=8.0)
    use_bf16 = dev == "cuda"

    for ep in range(a.epochs):
        model.train()
        tot = n = 0
        for enc, y in make_batches(pairs, tok, a.bs, dev, True):
            with torch.autocast(device_type=dev, dtype=torch.bfloat16, enabled=use_bf16):
                logit = model(**enc).logits.squeeze(-1)
            loss = F.binary_cross_entropy_with_logits(logit.float(), y, pos_weight=pos_w)
            opt.zero_grad()
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            opt.step()
            sch.step()
            tot += float(loss) * len(y)
            n += len(y)
        print(f"epoca {ep + 1}/{a.epochs}  loss {tot / n:.4f}", flush=True)

    if not a.with_val:
        vp = build_pairs(val, sup, matcher, n_neg=None)
        sc = scores(model, tok, vp, dev)
        y = np.array([p[2] for p in vp])
        pred = sc >= 0.5
        tp = int((pred & (y == 1)).sum()); fp = int((pred & (y == 0)).sum()); fn = int((~pred & (y == 1)).sum())
        prec = tp / (tp + fp) if tp + fp else 0
        rec = tp / (tp + fn) if tp + fn else 0
        f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0
        print("\n== VALIDACION REAL (todos los pares de las 10 noticias) ==")
        print(f"precision {prec:.0%}  recall {rec:.0%}  F1 {f1:.0%}   (TP {tp}, FP {fp}, FN {fn})")
    model.save_pretrained(a.out)
    tok.save_pretrained(a.out)
    print("guardado en", a.out)


if __name__ == "__main__":
    main()
