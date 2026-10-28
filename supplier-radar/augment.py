"""Aumento de datos por parafrasis (retrotraduccion con modelos de traduccion abiertos, sin LLM).

Traduce cada titular y resumen a otro idioma (es, fr, de) y de vuelta al ingles. Se descarta cualquier parafrasis que
cambie un nombre propio (proveedor, ciudad, region), una cifra o la duracion, para que la etiqueta siga siendo valida.

  python3 augment.py                 # genera data/aug_synth.csv, aug_real_train.csv y aug_real_trainval.csv
  python3 augment.py --synth 1500 --variants 2
"""
import argparse
import random
import re

import pandas as pd

from radar.config import DATA, TRAIN, VALID
from radar.data import load_news, load_suppliers
from radar.impact import extract_days
from radar.knowledge import city_aliases
from radar.matcher import norm
from radar.synth import load_synth

PIVOTS = ["es", "fr", "de"]
NUM = re.compile(r"\d+(?:[.,]\d+)?")


def protected_terms(suppliers: pd.DataFrame) -> list[str]:
    terms = set()
    for s in suppliers.itertuples():
        terms.update(w for w in norm(s.Supplier_Name).split()[:2] if len(w) >= 4)  # las 2 primeras palabras: lo distintivo
        terms.add(norm(s.City).strip())
    for city, al in city_aliases().items():
        terms.update(norm(a).strip() for a in al)
    return sorted(t for t in terms if len(t) >= 4)


def safe(orig: str, para: str, protect: list[str]) -> bool:
    """La parafrasis solo vale si conserva nombres, numeros y duracion del original."""
    if not para or norm(orig) == norm(para):
        return False
    o, p = norm(orig), norm(para)
    if not 0.5 <= len(p) / max(len(o), 1) <= 1.8:
        return False
    for t in protect:
        if (" " + t + " ") in o and (" " + t + " ") not in p:
            return False
    if sorted(NUM.findall(orig)) != sorted(NUM.findall(para)) and extract_days(orig) != extract_days(para):
        return False
    return extract_days(orig) == extract_days(para)


def translate(texts, tok, model, dev, sample: bool, bs: int = 48):
    import torch

    out = []
    for i in range(0, len(texts), bs):
        enc = tok(texts[i:i + bs], return_tensors="pt", padding=True, truncation=True, max_length=256).to(dev)
        with torch.no_grad():
            kw = dict(do_sample=True, top_p=0.9, temperature=0.9) if sample else dict(num_beams=4)
            gen = model.generate(**enc, max_new_tokens=200, **kw)
        out += tok.batch_decode(gen, skip_special_tokens=True)
    return out


def paraphrase(df: pd.DataFrame, variants: int, protect: list[str], seed: int) -> pd.DataFrame:
    import torch
    from transformers import MarianMTModel, MarianTokenizer

    random.seed(seed)
    torch.manual_seed(seed)
    dev = "cuda" if torch.cuda.is_available() else "cpu"
    heads, sums = df["Headline"].tolist(), df["Summary"].tolist()
    rows = []
    for lang in PIVOTS:
        fw_tok = MarianTokenizer.from_pretrained(f"Helsinki-NLP/opus-mt-en-{lang}")
        fw = MarianMTModel.from_pretrained(f"Helsinki-NLP/opus-mt-en-{lang}").to(dev).eval()
        bw_tok = MarianTokenizer.from_pretrained(f"Helsinki-NLP/opus-mt-{lang}-en")
        bw = MarianMTModel.from_pretrained(f"Helsinki-NLP/opus-mt-{lang}-en").to(dev).eval()
        mid_h = translate(heads, fw_tok, fw, dev, sample=False)
        mid_s = translate([s if s else "." for s in sums], fw_tok, fw, dev, sample=False)
        for v in range(variants):
            new_h = translate(mid_h, bw_tok, bw, dev, sample=(v > 0))
            new_s = translate(mid_s, bw_tok, bw, dev, sample=(v > 0))
            for i, r in enumerate(df.itertuples()):
                h_ok = safe(r.Headline, new_h[i], protect)
                s_ok = (not r.Summary) or safe(r.Summary, new_s[i], protect)
                if not (h_ok or (r.Summary and s_ok)):
                    continue
                d = r._asdict()
                d.pop("Index", None)
                d["Headline"] = new_h[i] if h_ok else r.Headline
                d["Summary"] = (new_s[i] if s_ok else r.Summary) if r.Summary else ""
                d["News_ID"] = f"{r.News_ID}_{lang}{v}"
                rows.append(d)
        del fw, bw
        if dev == "cuda":
            torch.cuda.empty_cache()
    out = pd.DataFrame(rows).drop_duplicates(subset=["Headline", "Summary"]).reset_index(drop=True)
    out["text"] = (out["Headline"].str.rstrip(". ") + ". " + out["Summary"]).str.strip()
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--synth", type=int, default=1200, help="cuantas sinteticas parafrasear")
    ap.add_argument("--variants", type=int, default=2, help="variantes por idioma pivote")
    ap.add_argument("--seed", type=int, default=7)
    a = ap.parse_args()
    protect = protected_terms(load_suppliers())

    syn = load_synth().sample(n=min(a.synth, len(load_synth())), random_state=a.seed).reset_index(drop=True)
    out = paraphrase(syn, a.variants, protect, a.seed)
    out.to_csv(DATA / "aug_synth.csv", index=False)
    print(f"aug_synth.csv: {len(out)} parafrasis de {len(syn)} sinteticas")

    train = load_news(TRAIN)
    trainval = pd.concat([train, load_news(VALID)], ignore_index=True)
    for name, base in (("aug_real_train.csv", train), ("aug_real_trainval.csv", trainval)):
        res = paraphrase(base, a.variants, protect, a.seed)
        res.to_csv(DATA / name, index=False)
        print(f"{name}: {len(res)} parafrasis de {len(base)} noticias reales")
    print("ejemplo:\n", out[["Headline", "Summary"]].head(3).to_string())


if __name__ == "__main__":
    main()
