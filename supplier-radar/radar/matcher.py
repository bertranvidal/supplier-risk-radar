"""Paso 1-2: 'NER ligero' + candidatos de proveedor.

Busca en la noticia nombres de proveedor, ciudades, regiones, paises y materiales
y devuelve pistas. NO decide: el LLM decide con estas pistas delante.
"""
import re
import unicodedata

import pandas as pd

from .knowledge import CITY_ALIASES, COUNTRY_ALIASES

SUFFIXES = {
    "ltd", "inc", "co", "ag", "gmbh", "sl", "sa", "sp", "z", "o", "llc", "plc", "bv", "nv",
    "srl", "spa", "as", "sdn", "bhd", "company", "corp", "limited", "pvt", "kg", "ab", "oy", "sas",
}
STOP = {"and", "of", "the", "for"}


def norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode()
    s = s.lower().replace("&", " and ")
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return " " + s.strip() + " "


def core_tokens(name: str) -> list[str]:
    toks = norm(name).split()
    while toks and toks[-1] in SUFFIXES:
        toks.pop()
    return toks


def has(text_n: str, phrase: str) -> bool:
    p = norm(phrase)
    return len(p.strip()) > 0 and p in text_n


STRENGTH = {"name": 3, "partial name": 2, "city": 2, "region": 2, "material": 2, "country": 1, "similar name": 1}


class Matcher:
    def __init__(self, suppliers: pd.DataFrame):
        self.s = suppliers.reset_index(drop=True)

    def hints(self, text: str) -> list[dict]:
        t = norm(text)
        out = []
        for _, r in self.s.iterrows():
            reasons = []
            core = core_tokens(r.Supplier_Name)
            if core and has(t, " ".join(core)):
                reasons.append("name")
            else:
                sig = [w for w in core if w not in STOP and len(w) > 2]
                hit = [w for w in sig if (" " + w + " ") in t]
                if len(hit) >= 2:
                    reasons.append("partial name")
                elif len(hit) == 1 and sig and hit[0] == sig[0]:
                    reasons.append("similar name")
            city = str(r.City)
            if has(t, city):
                reasons.append("city")
            for a in CITY_ALIASES.get(city, []):
                if has(t, a):
                    reasons.append("region")
                    break
            country = str(r.Country)
            names = COUNTRY_ALIASES.get(country) or [re.sub(r"\(.*?\)", "", country).strip()]
            if any(has(t, n) for n in names):
                reasons.append("country")
            mat = str(r.Material_Supplied).split()[0]
            if len(mat) >= 6 and (" " + norm(mat).strip() + " ") in t:
                reasons.append("material")
            if reasons:
                best = max(STRENGTH[x] for x in reasons)
                out.append({
                    "id": r.Supplier_ID, "name": r.Supplier_Name, "city": city, "country": country,
                    "reasons": reasons, "score": best,
                })
        out.sort(key=lambda d: (-d["score"], d["id"]))
        return out


def hints_text(hints: list[dict]) -> str:
    if not hints:
        return "(no supplier name, city, region, country or material from the list was detected in the text)"
    lines = []
    for h in hints:
        what = ", ".join(
            {
                "name": "full supplier name appears",
                "partial name": "part of the supplier name appears",
                "similar name": "a word of the supplier name appears (check it is really the same company)",
                "city": "its city (" + h["city"] + ") appears",
                "region": "its region appears",
                "country": "its country (" + h["country"] + ") appears",
                "material": "the material it supplies appears",
            }[x]
            for x in h["reasons"]
        )
        lines.append(f"- {h['id']} {h['name']}: {what}")
    return "\n".join(lines)
