"""Pares (noticia, proveedor) para el modelo de vinculacion. Sin torch: se puede probar en cualquier sitio."""
import random

import pandas as pd

from .matcher import Matcher


def profile(x) -> str:
    return f"{x.Supplier_Name} | {x.City}, {x.Country} | {x.Material_Supplied} ({x.Category})"


def pair_b(x, reasons: list[str]) -> str:
    """Segunda mitad del par: ficha del proveedor + pistas del matcher (texto)."""
    return profile(x) + " || hints: " + (", ".join(reasons) if reasons else "none")


def ids_of(cell) -> set:
    if not isinstance(cell, str) or not cell.strip():
        return set()
    return {i.strip() for i in cell.split(";") if i.strip()}


def build_pairs(news: pd.DataFrame, suppliers: pd.DataFrame, matcher: Matcher, n_neg: int | None = 8,
                seed: int = 7) -> list[tuple[str, str, int]]:
    """Positivos = proveedores afectados. Negativos = los que el matcher marca sin estar afectados (dificiles)
    + n_neg aleatorios. n_neg=None -> todos los pares (para pocas noticias)."""
    rng = random.Random(seed)
    sup = {x.Supplier_ID: x for x in suppliers.itertuples()}
    out = []
    for r in news.itertuples():
        gold = ids_of(r.Affected_Supplier_IDs)
        hmap = {h["id"]: h["reasons"] for h in matcher.hints(r.text)}
        if n_neg is None:
            chosen = list(sup)
        else:
            hard = [i for i in hmap if i not in gold]
            rest = [i for i in sup if i not in gold and i not in hmap]
            chosen = list(gold & set(sup)) + hard + rng.sample(rest, min(n_neg, len(rest)))
        for sid in chosen:
            out.append((r.text, pair_b(sup[sid], hmap.get(sid, [])), int(sid in gold)))
    return out


def hint_prefix(hints: list[dict]) -> str:
    """Pista generica (sin IDs) para el modelo de texto: que tipo de coincidencia con proveedores hay en la noticia.
    Asi no tiene que memorizar que ciudades tienen proveedores."""
    cats = sorted({r for h in hints for r in h["reasons"]})
    return "[supplier hints: " + (", ".join(cats) if cats else "none") + "]"
