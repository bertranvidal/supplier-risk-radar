"""Cliente minimo de LLM (Ollama local) con salida JSON validada.

Variables de entorno:
  OLLAMA_URL    (por defecto http://localhost:11434)
  OLLAMA_MODEL  (por defecto qwen2.5:7b-instruct-q4_K_M)
"""
import json
import os
import re
import time

import requests


def model_name() -> str:
    return os.getenv("OLLAMA_MODEL", "qwen2.5:7b-instruct-q4_K_M")


def _chat(prompt: str, system: str, schema: dict | None, model: str | None = None, timeout: int = 300) -> str:
    url = os.getenv("OLLAMA_URL", "http://localhost:11434").rstrip("/")
    body = {
        "model": model or model_name(),
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
        "stream": False,
        "keep_alive": "30m",
        "options": {"temperature": 0, "seed": 7, "num_ctx": 8192},
    }
    if schema:
        body["format"] = schema
    r = requests.post(url + "/api/chat", json=body, timeout=timeout)
    r.raise_for_status()
    return r.json()["message"]["content"]


def _extract_json(text: str) -> dict:
    text = text.strip()
    try:
        return json.loads(text)
    except Exception:
        pass
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        raise ValueError("no JSON in answer: " + text[:200])
    return json.loads(m.group(0))


def ask_structured(prompt: str, system: str, model_cls, retries: int = 2, model: str | None = None, timeout: int = 300):
    """Pregunta al LLM y devuelve una instancia validada de model_cls (reintenta si falla)."""
    schema = model_cls.model_json_schema()
    last = None
    p = prompt
    for _ in range(retries + 1):
        try:
            raw = _chat(p, system, schema, model=model, timeout=timeout)
            return model_cls.model_validate(_extract_json(raw))
        except Exception as e:  # noqa: BLE001
            last = e
            p = prompt + "\n\nYour previous answer was invalid (" + str(e)[:200] + "). Answer again with valid JSON only."
            time.sleep(0.5)
    raise RuntimeError("LLM did not return valid JSON: " + str(last))
