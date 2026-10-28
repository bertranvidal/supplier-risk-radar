"""Paso 3: recuperar noticias etiquetadas parecidas para usarlas como ejemplos (few-shot).

Version minima con TF-IDF. Para cambiar a embeddings basta con reescribir la clase Retriever.
"""
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


class Retriever:
    def __init__(self, pool: pd.DataFrame):
        self.pool = pool.reset_index(drop=True)
        self.vec = TfidfVectorizer(ngram_range=(1, 2), sublinear_tf=True, stop_words="english")
        self.mat = self.vec.fit_transform(self.pool["text"])

    def top(self, text: str, k: int = 6, exclude_id: str | None = None) -> list[pd.Series]:
        sims = cosine_similarity(self.vec.transform([text]), self.mat)[0]
        order = sims.argsort()[::-1]
        out = []
        for i in order:
            row = self.pool.iloc[i]
            if exclude_id is not None and row.News_ID == exclude_id:
                continue
            out.append(row)
            if len(out) == k:
                break
        return out


def format_example(r: pd.Series) -> str:
    sup = r.Affected_Supplier_IDs if isinstance(r.Affected_Supplier_IDs, str) else "none"
    return (
        f"Article: {r.Headline}. {r.Summary}\n"
        f"Expert label: Is_Risk={r.Is_Risk}, Urgent={r.Urgent}, Event={r.Event_Type}, Suppliers={sup}\n"
        f"Expert reason: {r.Explanation}"
    )
