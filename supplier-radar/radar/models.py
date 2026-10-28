"""Inferencia con NUESTROS modelos afinados (texto + vinculacion). Se cargan una sola vez.

Ensemble: se cargan todos los directorios models/text_clf* y models/link* y se promedian sus probabilidades
(cada uno entrenado con una semilla distinta). Los umbrales calibrados se leen de models/thresholds.json.
"""
import json
import os
from pathlib import Path

from .config import MODELS
from .data import load_suppliers
from .matcher import Matcher
from .pairs import hint_prefix
from .schema import DURATIONS, IMPACTS

_cache = {}
DEFAULT_THR = {"risk": 0.5, "urgent": 0.5, "link": 0.5}


def find_dirs(prefix: str, env: str) -> list[Path]:
    if os.getenv(env):
        return [Path(p) for p in os.getenv(env).split(os.pathsep) if p]
    return sorted(d for d in MODELS.glob(prefix + "*") if d.is_dir() and (d / "config.json").exists())


def load_thresholds() -> dict:
    thr = dict(DEFAULT_THR)
    f = MODELS / "thresholds.json"
    if f.exists():
        thr.update({k: float(v) for k, v in json.loads(f.read_text(encoding="utf-8")).items() if k in thr})
    return thr


class Models:
    def __init__(self, text_dirs: list[Path], link_dirs: list[Path]):
        import torch
        from transformers import AutoModelForSequenceClassification, AutoTokenizer

        from .nn import MultiHead

        if not text_dirs or not link_dirs:
            raise FileNotFoundError("Faltan modelos en models/. Entrena primero: python3 train_text.py y python3 train_link.py")
        self.torch = torch
        self.dev = "cuda" if torch.cuda.is_available() else "cpu"
        self.texts = []
        for d in text_dirs:
            m, tok, events = MultiHead.load(d)
            self.texts.append((m.to(self.dev), tok, bool(getattr(m, "meta", {}).get("hints", False))))
            self.events = events
        self.links = []
        for d in link_dirs:
            self.links.append((AutoModelForSequenceClassification.from_pretrained(d).eval().to(self.dev),
                               AutoTokenizer.from_pretrained(d)))
        self.matcher = Matcher(load_suppliers())
        self.thr = load_thresholds()
        self.n_text, self.n_link = len(self.texts), len(self.links)

    def predict_text(self, texts: list[str]) -> list[dict]:
        """Promedia las probabilidades de todos los modelos de texto del ensemble."""
        torch = self.torch
        acc = None
        hinted = None
        for model, tok, use_hints in self.texts:
            if use_hints and hinted is None:  # igual que en el entrenamiento (solo los modelos entrenados con pista)
                hinted = [hint_prefix(self.matcher.hints(t)) + " " + t for t in texts]
            enc = tok(hinted if use_hints else texts, truncation=True, max_length=192, padding=True, return_tensors="pt").to(self.dev)
            with torch.no_grad():
                r, u, e, i, d = (o.float().softmax(-1) for o in model(enc["input_ids"], enc["attention_mask"]))
            cur = [r, u, e, i, d]
            acc = cur if acc is None else [a + c for a, c in zip(acc, cur)]
        r, u, e, i, d = (a / self.n_text for a in acc)
        out = []
        for k in range(len(texts)):
            p_stop, p_short = float(i[k][2]), float(d[k][0])  # IMPACTS[2]=stoppage, DURATIONS[0]=short
            p_direct = float(u[k][1])
            # urgencia = cabeza directa y, aparte, "para la produccion y no es corto" (dos senales independientes)
            p_urg = 0.5 * p_direct + 0.5 * p_stop * (1 - p_short)
            out.append({"p_risk": float(r[k][1]), "p_urgent": p_urg, "p_urgent_head": p_direct,
                        "event": self.events[int(e[k].argmax())],
                        "impact": IMPACTS[int(i[k].argmax())], "duration": DURATIONS[int(d[k].argmax())]})
        return out

    def score_links(self, text: str, bs: list[str], chunk: int = 64) -> list[float]:
        torch = self.torch
        total = None
        for model, tok in self.links:
            out = []
            for i in range(0, len(bs), chunk):
                part = bs[i:i + chunk]
                enc = tok([text] * len(part), part, truncation="only_first", max_length=256,
                          padding=True, return_tensors="pt").to(self.dev)
                with torch.no_grad():
                    logits = model(**enc).logits.squeeze(-1)
                out += torch.sigmoid(logits.float()).cpu().tolist()
            total = out if total is None else [a + b for a, b in zip(total, out)]
        return [t / self.n_link for t in total]


def get_models() -> Models:
    if "m" not in _cache:
        _cache["m"] = Models(find_dirs("text_clf", "RADAR_TEXT_MODEL"), find_dirs("link", "RADAR_LINK_MODEL"))
    return _cache["m"]
