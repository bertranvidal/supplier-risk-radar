"""Sondeo del modelo de texto: prueba textos sueltos y muestra que dice CADA modelo del ensemble.

  python3 probe.py --builtin                       # bateria de pruebas incluida (cierres cortos, controles)
  python3 probe.py "Titular. Resumen de la noticia."  "Otro titular. Otro resumen."
Sirve para diagnosticar fallos (por que dice X), no para medir acierto.
"""
import argparse

from radar.models import get_models
from radar.pairs import hint_prefix

BUILTIN = [
    # cierres CORTOS por mal tiempo en la ciudad de un proveedor (esperado: riesgo, no urgente)
    "Typhoon brings heavy rain to southern Vietnam, Ho Chi Minh City factories close for two days. Authorities in Ho Chi Minh City ordered factories and schools to close on Tuesday and Wednesday as a typhoon brought strong winds and flooding.",
    "Heavy snow forces Basel industrial plants to close for one day. Authorities in Basel asked factories to stay shut on Thursday because of heavy snowfall; operations are expected to resume on Friday.",
    "Flooding shuts factories in Taizhou for 48 hours. Local authorities ordered industrial plants in Taizhou to suspend operations for 48 hours after heavy rain.",
    "Storm warning: Osaka factories to close for a day. Officials in Osaka ordered manufacturers to halt work on Monday as a typhoon passes the region.",
    # cierres LARGOS (esperado: riesgo urgente)
    "Typhoon floods Ho Chi Minh City, factories shut for three weeks. Authorities ordered all factories in Ho Chi Minh City to remain closed for at least three weeks.",
    # controles: NO riesgo
    "Typhoon forecast for Ho Chi Minh City next week. Meteorologists say a typhoon may approach southern Vietnam next week; no closures have been announced.",
    "Fire destroys historic market hall in Basel's old town. A fire destroyed a 19th-century market hall; no industrial sites were affected.",
    "Typhoon closes factories in Manila for two days. Authorities in Manila ordered factories and schools to close for two days after a typhoon.",
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("texts", nargs="*")
    ap.add_argument("--builtin", action="store_true")
    a = ap.parse_args()
    texts = BUILTIN if a.builtin or not a.texts else a.texts
    m = get_models()
    torch = m.torch
    ens = m.predict_text(texts)
    per = []
    pt = [hint_prefix(m.matcher.hints(t)) + " " + t for t in texts]
    for model, tok, use_hints in m.texts:
        enc = tok(pt if use_hints else texts, truncation=True, max_length=192, padding=True, return_tensors="pt").to(m.dev)
        with torch.no_grad():
            r = model(enc["input_ids"], enc["attention_mask"])[0].float().softmax(-1)[:, 1]
        per.append(r.cpu().tolist())
    for i, t in enumerate(texts):
        e = ens[i]
        print(f"\n{t[:110]}...")
        print(f"   p_risk por modelo: {', '.join(f'{p[i]:.2f}' for p in per)}  | media {e['p_risk']:.2f}  | p_urgent {e['p_urgent']:.2f}"
              f" | {e['event']} | impacto {e['impact']} / duracion {e['duration']}")


if __name__ == "__main__":
    main()
