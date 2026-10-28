"""Informe legible de lo que dice el sistema sobre un fichero de noticias (sirve tambien SIN respuestas).

  python3 inspect_run.py data/Supplier_Risk_3_Test.xlsx            # pantalla
  python3 inspect_run.py data/Supplier_Risk_3_Test.xlsx > out/informe_test.txt

Es una REVISION DE CORDURA: sirve para ver si lo que responde el sistema tiene sentido y detectar fallos o patrones raros.
No se usa para ajustar umbrales ni reglas noticia a noticia.
"""
import argparse
import textwrap

from radar.data import load_news, load_suppliers
from radar.pipeline import analyze_news, load_pool


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("file", help="Excel with the news to inspect")
    ap.add_argument("--mode", default="models", choices=["models", "rules"])
    ap.add_argument("--summary-chars", type=int, default=420)
    a = ap.parse_args()

    news = load_news(a.file)
    res = analyze_news(news, load_pool(include_valid=True), a.mode, verbose=False)
    sup = load_suppliers().set_index("Supplier_ID")
    n = news.set_index("News_ID")
    print(f"\nINFORME ({a.file}) - {len(res)} noticias, modo {a.mode}\n" + "=" * 100)
    for r in res.itertuples():
        row = n.loc[r.News_ID]
        verdict = ("RIESGO URGENTE" if r.Urgent == "Y" else "RIESGO") if r.Is_Risk == "Y" else "no riesgo"
        print(f"\n[{r.News_ID}] {row.Headline}")
        print(textwrap.fill(row.Summary[:a.summary_chars] + ("..." if len(row.Summary) > a.summary_chars else ""),
                            width=98, initial_indent="    ", subsequent_indent="    "))
        print(f"  -> {verdict} | tipo: {r.Event_Type} | impacto: {r.Supply_Impact or '-'} / duracion: {r.Duration or '-'} | confianza: {r.Confidence}")
        ids = [i.strip() for i in r.Affected_Supplier_IDs.split(";") if i.strip()]
        for i in ids:
            if i in sup.index:
                print(f"     {i} {sup.loc[i, 'Supplier_Name']} ({sup.loc[i, 'City']}, {sup.loc[i, 'Country']}) - {sup.loc[i, 'Material_Supplied']}")
        if r.Is_Risk == "Y":
            print(f"     prioridad {r.Priority}; gasto en riesgo {r.Spend_At_Risk_EUR / 1e6:.1f} M EUR")
        print(f"     [{r.Reasoning}]")
    print("\n" + "=" * 100)
    print(f"Resumen: {int((res.Is_Risk == 'Y').sum())} riesgos, {int((res.Urgent == 'Y').sum())} urgentes, de {len(res)}")


if __name__ == "__main__":
    main()
