import re
from pathlib import Path

import pandas as pd

from .config import DATA, TRAIN

# Nombres de columna aceptados (sin mayusculas, espacios ni simbolos) -> nombre canonico
ALIASES = {
    "newsid": "News_ID", "id": "News_ID", "articleid": "News_ID", "newsno": "News_ID",
    "publisheddate": "Published_Date", "date": "Published_Date",
    "source": "Source", "publisher": "Source",
    "headline": "Headline", "title": "Headline", "heading": "Headline",
    "summary": "Summary", "body": "Summary", "description": "Summary", "content": "Summary", "article": "Summary",
    "isrisk": "Is_Risk", "risk": "Is_Risk",
    "urgent": "Urgent", "urgency": "Urgent",
    "affectedsupplierids": "Affected_Supplier_IDs", "affectedsuppliers": "Affected_Supplier_IDs",
    "eventtype": "Event_Type", "explanation": "Explanation",
}
YES, NO = {"y", "yes", "true", "1", "si", "sí"}, {"n", "no", "false", "0"}


def _canon(c) -> str:
    return ALIASES.get(re.sub(r"[^a-z]", "", str(c).lower()), str(c))


def _yn(v):
    if pd.isna(v):
        return v
    s = str(v).strip().lower()
    return "Y" if s in YES else "N" if s in NO else str(v).strip().upper()


def _read(path) -> pd.DataFrame:
    """Lee la hoja de noticias de un Excel (o CSV), tolerando cabeceras desplazadas y hojas con otro nombre."""
    if isinstance(path, (str, Path)) and str(path).lower().endswith(".csv"):
        return pd.read_csv(path)
    xl = pd.ExcelFile(path)
    names = sorted(xl.sheet_names, key=lambda s: (not s.lower().startswith("news"), xl.sheet_names.index(s)))
    for sheet in names:
        for header in range(0, 8):
            try:
                df = xl.parse(sheet, header=header)
            except (ValueError, IndexError):
                break  # la hoja tiene menos filas que la cabecera probada
            cols = {_canon(c) for c in df.columns}
            if "Headline" in cols:
                return df
    raise ValueError("No se encuentra una hoja con una columna Headline/Title en " + str(path))


def load_news(path) -> pd.DataFrame:
    """Carga noticias de cualquiera de los 4 Excel, o de uno ajeno con columnas en otro orden o nombre."""
    df = _read(path)
    df = df.rename(columns={c: _canon(c) for c in df.columns})
    df = df.loc[:, ~df.columns.duplicated()]
    for c in ("Headline", "Summary"):
        if c not in df.columns:
            df[c] = ""
        df[c] = df[c].fillna("").astype(str).str.strip()
    df = df[(df["Headline"] != "") | (df["Summary"] != "")].reset_index(drop=True)
    if "News_ID" not in df.columns:
        df["News_ID"] = None
    ids = df["News_ID"].astype(object).where(df["News_ID"].notna(), None)
    df["News_ID"] = [str(v).strip() if v is not None and str(v).strip() else f"N{i + 1:03d}" for i, v in enumerate(ids)]
    dup = df["News_ID"].duplicated(keep=False)
    if dup.any():  # los IDs repetidos romperian las uniones
        df["News_ID"] = [f"{v}_{i}" if d else v for i, (v, d) in enumerate(zip(df["News_ID"], dup))]
    for c in ("Is_Risk", "Urgent"):
        if c in df.columns:
            df[c] = df[c].map(_yn)
    df["text"] = (df["Headline"].str.rstrip(". ") + ". " + df["Summary"]).str.strip()
    return df


def load_suppliers() -> pd.DataFrame:
    return pd.read_excel(TRAIN, sheet_name="Suppliers")


def load_materials() -> pd.DataFrame:
    return pd.read_excel(TRAIN, sheet_name="Materials")


def is_labelled(df: pd.DataFrame) -> bool:
    return "Is_Risk" in df.columns and df["Is_Risk"].notna().all()


EXTRA_FILES = ["aug_synth.csv", "llm_synth.csv", "neg_news.csv", "supabase_train.csv", "claude_labels.csv"]  # datos extra opcionales (augment / gen_llm_data / fetch_negatives)


def load_extra() -> list[tuple[str, pd.DataFrame]]:
    """Ficheros de entrenamiento extra que existan en data/. Todos con etiquetas por construccion."""
    out = []
    for name in EXTRA_FILES:
        f = DATA / name
        if f.exists():
            df = pd.read_csv(f)
            for c in ("Summary", "Affected_Supplier_IDs"):
                if c in df.columns:
                    df[c] = df[c].fillna("")
            if "text" not in df.columns and "Headline" in df.columns:
                df["text"] = (df["Headline"].str.rstrip(". ") + ". " + df.get("Summary", "")).str.strip()
            out.append((name, df))
    return out
