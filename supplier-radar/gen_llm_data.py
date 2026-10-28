"""Mas datos de entrenamiento: un LLM local REESCRIBE nuestras noticias sinteticas con estilos y vocabulario distintos.

Las etiquetas no cambian (el LLM no decide nada): solo se acepta la reescritura si conserva nombres de proveedor,
ciudades, cifras y duraciones del original. Asi el modelo ve mucha mas variedad de lenguaje que con plantillas.

  python3 gen_llm_data.py                  # 1500 noticias, modelo de Ollama elegido automaticamente
  python3 gen_llm_data.py --n 3000 --model llama3.1:8b --workers 4
Genera data/llm_synth.csv (train_text.py y train_link.py lo usan solos si existe).
"""
import argparse
import random
from concurrent.futures import ThreadPoolExecutor

import pandas as pd
from pydantic import BaseModel

from radar import llm
from radar.alerts import pick_model
from radar.config import DATA
from radar.data import load_suppliers
from radar.synth import load_synth
from augment import protected_terms, safe

STYLES = [
    "a Reuters-style wire report (dateline, neutral and terse)",
    "a local newspaper article written in plainer language",
    "a pharmaceutical trade-press article (e.g. FiercePharma style) with industry jargon",
    "a breaking-news alert: very short headline and a two-sentence summary",
    "a business-section article quoting an anonymous source or an official statement",
    "an article from a financial newswire focused on market and supply implications",
    "a regional news item that mentions the facts indirectly or with synonyms",
]


class Rewrite(BaseModel):
    headline: str
    summary: str


SYSTEM = """You rewrite news articles for a training dataset. You receive a headline and summary.
Rewrite them as {style}.
Rules:
- Keep EVERY fact: company names, places, numbers, durations, who is affected and what happens (stoppage, delay, nothing).
- Do NOT add new facts, names, places, numbers or consequences. Do NOT make it sound more or less serious.
- Use different wording and sentence structure from the original.
- English. Headline under 20 words; summary 1-3 sentences.
Answer ONLY with JSON: {{"headline": "...", "summary": "..."}}"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=1500)
    ap.add_argument("--model", default=None)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--seed", type=int, default=11)
    a = ap.parse_args()

    model = a.model or pick_model()
    if not model:
        raise SystemExit("No hay modelo de Ollama disponible. Mira `ollama list` o usa --model.")
    print("modelo:", model, flush=True)
    protect = protected_terms(load_suppliers())
    syn = load_synth().sample(n=min(a.n, len(load_synth())), random_state=a.seed).reset_index(drop=True)
    rnd = random.Random(a.seed)
    styles = [rnd.choice(STYLES) for _ in range(len(syn))]

    def work(i):
        r = syn.iloc[i]
        prompt = f"HEADLINE: {r.Headline}\nSUMMARY: {r.Summary}"
        try:
            v = llm.ask_structured(prompt, SYSTEM.format(style=styles[i]), Rewrite, retries=1, model=model, timeout=90)
        except Exception:  # noqa: BLE001
            return None
        orig = r.Headline + ". " + r.Summary
        new = v.headline.strip() + ". " + v.summary.strip()
        return (v.headline.strip(), v.summary.strip()) if safe(orig, new, protect) else None

    with ThreadPoolExecutor(a.workers) as ex:
        res = list(ex.map(work, range(len(syn))))
    rows = []
    for i, x in enumerate(res):
        if x:
            d = syn.iloc[i].to_dict()
            d["Headline"], d["Summary"] = x
            d["News_ID"] = f"{d['News_ID']}_llm"
            d["text"] = (x[0].rstrip(". ") + ". " + x[1]).strip()
            rows.append(d)
    out = pd.DataFrame(rows).drop_duplicates(subset=["text"])
    out.to_csv(DATA / "llm_synth.csv", index=False)
    print(f"llm_synth.csv: {len(out)} aceptadas de {len(syn)} ({len(out) / len(syn):.0%})")
    print(out[["Headline", "Summary"]].head(3).to_string())


if __name__ == "__main__":
    main()
