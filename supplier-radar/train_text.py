"""Afina NUESTRO modelo de texto (riesgo, urgencia, evento, impacto, duracion) desde un encoder preentrenado.

  python3 train_text.py                       # entrena con sinteticas + train real; mide en validacion
  python3 train_text.py --with-val            # version final: incluye validacion (ya no se puede medir en ella)
  python3 train_text.py --seed 11 --out models/text_clf2     # otro miembro del ensemble
  python3 train_text.py --base FacebookAI/roberta-base --epochs 5

Si existen data/aug_synth.csv y data/aug_real_*.csv (python3 augment.py) se usan automaticamente (--no-aug las ignora).
"""
import argparse
import random

import numpy as np
import pandas as pd
import torch
import torch.nn.functional as F
from transformers import AutoTokenizer, get_linear_schedule_with_warmup

from radar.config import DATA, HOLDOUT, MODELS, TRAIN, VALID
from radar.data import load_extra, load_news, load_suppliers
from radar.matcher import Matcher
from radar.pairs import hint_prefix
from radar.nn import MultiHead
from radar.schema import DURATIONS, EVENT_TYPES, IMPACTS
from radar.synth import load_synth

IGN = -100  # etiqueta ignorada en la perdida (no se conoce)


def encode_labels(df: pd.DataFrame, events: list[str]):
    """Devuelve 5 vectores: riesgo, urgente, evento, impacto, duracion.
    En las noticias reales solo se conocen riesgo/urgente/evento; impacto y duracion se deducen por reglas debiles:
    Is_Risk=N -> impacto none; Urgent=Y -> impacto stoppage; el resto se ignora (-100)."""
    risk = df["Is_Risk"].eq("Y").astype(int).values
    urg = df["Urgent"].eq("Y").astype(int).values
    ev = df["Event_Type"].map(lambda e: events.index(e) if e in events else events.index("Other risk")).values
    n = len(df)
    imp = np.full(n, IGN)
    dur = np.full(n, IGN)
    if "Supply_Impact" in df.columns:  # sinteticas: etiquetas exactas
        imp = df["Supply_Impact"].map(lambda v: IMPACTS.index(v) if v in IMPACTS else IGN).values.astype(int)
        dur = df["Duration"].map(lambda v: DURATIONS.index(v) if v in DURATIONS else IGN).values.astype(int)
    weak = imp == IGN
    imp = np.where(weak & (risk == 0), IMPACTS.index("none"), imp)
    imp = np.where(weak & (urg == 1), IMPACTS.index("stoppage"), imp)
    return risk, urg, ev, imp.astype(int), dur.astype(int)


def batches(texts, labels, tok, bs, dev, shuffle):
    idx = list(range(len(texts)))
    if shuffle:
        random.shuffle(idx)
    for i in range(0, len(idx), bs):
        j = idx[i:i + bs]
        enc = tok([texts[k] for k in j], truncation=True, max_length=192, padding=True, return_tensors="pt").to(dev)
        yield enc, [torch.tensor(l[j], device=dev) for l in labels]


def predict(model, tok, texts, dev):
    model.eval()
    out = [[] for _ in range(5)]
    with torch.no_grad():
        for enc, _ in batches(texts, [np.zeros(len(texts))], tok, 32, dev, False):
            for o, lg in zip(out, model(enc["input_ids"], enc["attention_mask"])):
                o.append(lg.float().argmax(-1).cpu().numpy())
    return [np.concatenate(o) for o in out]


def masked_ce(logits, y, smooth=0.0):
    """Entropia cruzada ignorando etiquetas -100; 0 si el lote no tiene ninguna conocida."""
    m = y != IGN
    if not m.any():
        return logits.sum() * 0.0
    return F.cross_entropy(logits[m], y[m], label_smoothing=smooth)


def load_aug(path):
    if not path.exists():
        return None
    return pd.read_csv(path).fillna({"Summary": ""})


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="FacebookAI/roberta-base")
    ap.add_argument("--epochs", type=int, default=5)
    ap.add_argument("--lr", type=float, default=3e-5)
    ap.add_argument("--bs", type=int, default=16)
    ap.add_argument("--real-weight", type=int, default=6, help="cuantas veces se repite cada noticia real")
    ap.add_argument("--smooth", type=float, default=0.03, help="label smoothing")
    ap.add_argument("--with-val", action="store_true")
    ap.add_argument("--with-holdout", action="store_true", help="version final: incluye tambien el examen independiente (ya no se puede medir en el)")
    ap.add_argument("--no-aug", action="store_true")
    ap.add_argument("--out", default=str(MODELS / "text_clf"))
    ap.add_argument("--seed", type=int, default=7)
    a = ap.parse_args()

    random.seed(a.seed); np.random.seed(a.seed); torch.manual_seed(a.seed)
    dev = "cuda" if torch.cuda.is_available() else "cpu"
    events = list(EVENT_TYPES)

    real = load_news(TRAIN)
    val = load_news(VALID)
    if a.with_val:
        real = pd.concat([real, val], ignore_index=True)
    if a.with_holdout:
        real = pd.concat([real, load_news(HOLDOUT)], ignore_index=True)
    synth = load_synth()
    parts = [synth] + [real] * a.real_weight
    msg = f"{len(synth)} sinteticas + {len(real)} reales x{a.real_weight}"
    if not a.no_aug:
        for name, df in load_extra():
            parts.append(df)
            msg += f" + {len(df)} de {name}"
        aug_r = load_aug(DATA / ("aug_real_trainval.csv" if a.with_val else "aug_real_train.csv"))
        w = max(1, a.real_weight // 2)
        if aug_r is not None:
            parts += [aug_r] * w
            msg += f" + {len(aug_r)} parafrasis reales x{w}"
    train = pd.concat(parts, ignore_index=True)
    print(f"entrenamiento: {msg} = {len(train)}", flush=True)

    tok = AutoTokenizer.from_pretrained(a.base)
    model = MultiHead.new(a.base, len(events)).to(dev)
    matcher = Matcher(load_suppliers())

    def with_hints(ts):  # el modelo ve tambien si la noticia menciona ciudad/nombre/region de proveedores (sin IDs)
        return [hint_prefix(matcher.hints(t)) + " " + t for t in ts]

    texts = with_hints(train["text"].tolist())
    labels = list(encode_labels(train, events))
    steps = a.epochs * ((len(texts) + a.bs - 1) // a.bs)
    opt = torch.optim.AdamW(model.parameters(), lr=a.lr, weight_decay=0.01)
    sch = get_linear_schedule_with_warmup(opt, int(0.1 * steps), steps)
    use_bf16 = dev == "cuda"

    for ep in range(a.epochs):
        model.train()
        tot = n = 0
        for enc, (yr, yu, ye, yi, yd) in batches(texts, labels, tok, a.bs, dev, True):
            with torch.autocast(device_type=dev, dtype=torch.bfloat16, enabled=use_bf16):
                outs = model(enc["input_ids"], enc["attention_mask"])
            lr_, lu_, le_, li_, ld_ = (o.float() for o in outs)
            loss = F.cross_entropy(lr_, yr, label_smoothing=a.smooth) + F.cross_entropy(le_, ye, label_smoothing=a.smooth)
            m = yr == 1  # la urgencia solo se aprende en noticias que son riesgo
            if m.any():
                loss = loss + F.cross_entropy(lu_[m], yu[m], label_smoothing=a.smooth)
            loss = loss + 0.7 * masked_ce(li_, yi, a.smooth) + 0.5 * masked_ce(ld_, yd, a.smooth)
            opt.zero_grad()
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            opt.step()
            sch.step()
            tot += float(loss.detach()) * len(yr)
            n += len(yr)
        print(f"epoca {ep + 1}/{a.epochs}  loss {tot / n:.4f}", flush=True)

    if not a.with_val:
        pr, pu, pe, _, _ = predict(model, tok, with_hints(val["text"].tolist()), dev)
        yr, yu, ye, _, _ = encode_labels(val, events)
        print(f"\n== VALIDACION REAL ({len(val)} noticias) ==")
        m = yr == 1  # la cabeza de urgencia solo se entrena (y solo importa) en noticias de riesgo
        print(f"Is_Risk {np.mean(pr == yr):.0%}   Urgent (solo noticias de riesgo, {int(m.sum())}) {np.mean(pu[m] == yu[m]):.0%}   Evento {np.mean(pe == ye):.0%}")
    model.save(a.out, tok, events, a.base, hints=True)
    print("guardado en", a.out)


if __name__ == "__main__":
    main()
