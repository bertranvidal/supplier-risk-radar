"""Modelo de texto con cinco cabezas sobre un encoder preentrenado:
riesgo, urgencia (directa), tipo de evento, impacto en el suministro y duracion."""
import json
from pathlib import Path

import torch
import torch.nn as nn
from transformers import AutoConfig, AutoModel, AutoTokenizer

from .schema import DURATIONS, IMPACTS


class MultiHead(nn.Module):
    def __init__(self, enc, n_events: int):
        super().__init__()
        self.enc = enc
        h = enc.config.hidden_size
        self.drop = nn.Dropout(0.1)
        self.risk = nn.Linear(h, 2)
        self.urg = nn.Linear(h, 2)
        self.ev = nn.Linear(h, n_events)
        self.imp = nn.Linear(h, len(IMPACTS))
        self.dur = nn.Linear(h, len(DURATIONS))

    @classmethod
    def new(cls, base: str, n_events: int):
        return cls(AutoModel.from_pretrained(base), n_events)

    def forward(self, input_ids, attention_mask):
        out = self.enc(input_ids=input_ids, attention_mask=attention_mask).last_hidden_state
        m = attention_mask.unsqueeze(-1).to(out.dtype)
        pooled = self.drop((out * m).sum(1) / m.sum(1).clamp(min=1))
        return self.risk(pooled), self.urg(pooled), self.ev(pooled), self.imp(pooled), self.dur(pooled)

    def save(self, d, tokenizer, events: list[str], base: str, hints: bool = False):
        d = Path(d)
        d.mkdir(parents=True, exist_ok=True)
        self.enc.config.save_pretrained(d)
        tokenizer.save_pretrained(d)
        torch.save({k: v.cpu() for k, v in self.state_dict().items()}, d / "weights.pt")
        (d / "meta.json").write_text(json.dumps({"events": events, "base": base, "version": 3 if hints else 2, "hints": hints}), encoding="utf-8")

    @classmethod
    def load(cls, d):
        d = Path(d)
        meta = json.loads((d / "meta.json").read_text(encoding="utf-8"))
        enc = AutoModel.from_config(AutoConfig.from_pretrained(d))
        m = cls(enc, len(meta["events"]))
        m.load_state_dict(torch.load(d / "weights.pt", map_location="cpu"))
        m.meta = meta  # meta["hints"]: el modelo se entreno con la pista de proveedores como prefijo
        return m.eval(), AutoTokenizer.from_pretrained(d), meta["events"]
