"""Scraper de noticias para el Supplier Risk Radar.

Recoge noticias de RSS (internacionales + nacionales) y NewsAPI,
deduplica por hash del titulo e inserta en Supabase.

  python3 scraper.py
  python3 scraper.py --dry-run
  python3 scraper.py --source rss
  python3 scraper.py --source newsapi
"""
from __future__ import annotations

import argparse
import hashlib
import os
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

import requests
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "")
NEWSAPI_KEY = os.environ.get("NEWSAPI_KEY", "")

# Fuentes RSS: prensa internacional, prensa espanola, farmaceutica, ciencia
RSS_FEEDS = [
    # Internacionales - negocio y supply chain
    "https://feeds.bbci.co.uk/news/business/rss.xml",
    "https://rss.nytimes.com/services/xml/rss/nyt/Business.xml",
    "https://www.ft.com/?format=rss",
    "https://www.supplychaindive.com/feeds/news/",
    "https://www.pharmaceutical-technology.com/feed/",
    "https://www.chemistryworld.com/rss/news.xml",
    "https://www.scmp.com/rss/4/feed",
    # Internacionales - mundo (desastres, geopolitica)
    "https://feeds.bbci.co.uk/news/world/rss.xml",
    "https://rss.nytimes.com/services/xml/rss/nyt/World.xml",
    # El Pais
    "https://feeds.elpais.com/mrss-s/pages/ep/site/elpais.com/section/economia/portada",
    "https://feeds.elpais.com/mrss-s/pages/ep/site/elpais.com/section/ciencia/portada",
    "https://feeds.elpais.com/mrss-s/pages/ep/site/elpais.com/section/sociedad/portada",
    "https://feeds.elpais.com/mrss-s/pages/ep/site/elpais.com/section/internacional/portada",
    # El Mundo
    "https://e00-elmundo.uecdn.es/elmundo/rss/economia.xml",
    "https://e00-elmundo.uecdn.es/elmundo/rss/ciencia.xml",
    "https://e00-elmundo.uecdn.es/elmundo/rss/internacional.xml",
    "https://e00-elmundo.uecdn.es/elmundo/rss/espana.xml",
    # Expansion
    "https://e00-expansion.uecdn.es/rss/economia.xml",
    "https://e00-expansion.uecdn.es/rss/empresas.xml",
    # OKDiario
    "https://okdiario.com/economia/feed",
    "https://okdiario.com/ciencia/feed",
    "https://okdiario.com/internacional/feed",
    # ABC
    "https://www.abc.es/rss/feeds/abc_Economia.xml",
    "https://www.abc.es/rss/feeds/abc_Internacional.xml",
    "https://www.abc.es/rss/feeds/abc_Ciencia.xml",
    # La Razon
    "https://www.larazon.es/rss/economia.xml",
    "https://www.larazon.es/rss/ciencia.xml",
    # RTVE
    "https://www.rtve.es/rss/economia.xml",
    # EFE
    "https://www.efe.com/rss/economia",
    "https://www.efe.com/rss/ciencia",
    # Ciencia
    "https://www.nature.com/nature.rss",
    "https://www.science.org/rss/news_current.xml",
    "https://www.newscientist.com/feed/home/",
    # Farmaceutica
    "https://www.europeanpharmaceuticalreview.com/feed/",
    "https://www.in-pharmatechnologist.com/rss/news",
    "https://www.pharmamanufacturing.com/rss/",
]

# Palabras clave para filtrar noticias relevantes (EN + ES)
_KW_EN = [
    "supply chain", "supplier", "shortage", "disruption", "logistics",
    "procurement", "manufacturing", "factory", "plant", "warehouse",
    "fire", "explosion", "flood", "earthquake", "hurricane", "typhoon",
    "strike", "protest", "sanction", "embargo", "recall", "contamination",
    "shutdown", "closure", "bankruptcy", "insolvency", "cyber attack",
    "pharmaceutical", "drug", "medicine", "active ingredient",
    "excipient", "packaging", "GMP", "FDA", "EMA", "regulatory",
    "shipping", "freight", "port", "container", "tariff", "export ban",
    "import restriction", "trade war", "chemical spill", "power outage",
    "labor dispute", "raw material", "ingredient shortage",
    "production halt", "quality issue", "batch failure", "cold chain",
    "geopolitical", "civil unrest", "natural disaster", "pandemic",
    "stockpile", "inventory", "backorder", "lead time",
]

_KW_ES = [
    "cadena de suministro", "proveedor", "escasez", "desabastecimiento",
    "logística", "fabricación", "fábrica", "planta", "almacén",
    "incendio", "explosión", "inundación", "terremoto", "huracán",
    "huelga", "protesta", "sanción", "embargo", "retirada", "contaminación",
    "cierre", "quiebra", "ciberataque", "ransomware",
    "farmacéutica", "medicamento", "principio activo", "excipiente",
    "envase", "regulación", "AEMPS",
    "transporte", "puerto", "contenedor", "arancel", "restricción",
    "importación", "exportación", "guerra comercial",
    "suministro", "distribución", "materia prima", "laboratorio",
    "corte eléctrico", "vertido químico", "fallo de producción",
    "lote defectuoso", "cadena de frío", "desastre natural",
    "conflicto geopolítico", "disturbios", "pandemia",
    "stock", "inventario", "plazo de entrega", "rotura de stock",
]

_KW_PATTERN = re.compile("|".join(re.escape(k) for k in _KW_EN + _KW_ES), re.IGNORECASE)


def _hash(title: str) -> str:
    return hashlib.sha256(title.strip().lower().encode()).hexdigest()[:16]


def _relevant(title: str, summary: str = "") -> bool:
    return bool(_KW_PATTERN.search(f"{title} {summary}"))


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _row(title, summary, url, source, pub_date) -> dict:
    return {
        "title": title[:500], "summary": summary[:2000], "url": url[:1000],
        "source": source, "published_at": pub_date or _now(), "scraped_at": _now(),
        "title_hash": _hash(title),
        "is_labeled": False, "is_risk": None, "urgent": None,
        "event_type": None, "affected_supplier_ids": None,
    }


def fetch_rss(url: str, timeout: int = 15) -> list[dict]:
    """Descarga y parsea un feed RSS/Atom."""
    articles = []
    try:
        r = requests.get(url, timeout=timeout, headers={"User-Agent": "SupplierRadar/1.0"})
        r.raise_for_status()
        root = ET.fromstring(r.content)
        ns = {"atom": "http://www.w3.org/2005/Atom"}
        items = root.findall(".//item") or root.findall(".//atom:entry", ns)

        for item in items:
            title = (item.findtext("title") or item.findtext("atom:title", namespaces=ns) or "").strip()
            summary = (item.findtext("description") or item.findtext("atom:summary", namespaces=ns) or "").strip()
            link = (item.findtext("link") or "").strip()
            if not link:
                link_el = item.find("atom:link[@href]", ns)
                if link_el is not None:
                    link = link_el.get("href", "")
            pub = (item.findtext("pubDate") or item.findtext("atom:updated", namespaces=ns) or "").strip()
            summary = re.sub(r"<[^>]+>", "", summary).strip()

            if title and _relevant(title, summary):
                articles.append(_row(title, summary, link, url.split("/")[2], pub))
    except Exception as e:
        print(f"  [!] {url.split('/')[2]}: {type(e).__name__}")
    return articles


def scrape_rss() -> list[dict]:
    """Recorre todos los feeds RSS y devuelve articulos unicos."""
    result, seen = [], set()
    for url in RSS_FEEDS:
        for a in fetch_rss(url):
            if a["title_hash"] not in seen:
                seen.add(a["title_hash"])
                result.append(a)
    print(f"  RSS total: {len(result)} articulos unicos")
    return result


def scrape_newsapi() -> list[dict]:
    """Consulta NewsAPI con varias queries orientadas al proyecto."""
    if not NEWSAPI_KEY:
        print("  NewsAPI: sin API key, saltando")
        return []

    queries = [
        "pharmaceutical supply chain disruption",
        "supplier factory fire recall",
        "drug shortage manufacturing",
        "export restriction sanctions pharma",
        "logistics port strike shipping",
        "cadena suministro farmacéutica",
        "desabastecimiento medicamentos",
    ]

    articles = []
    for q in queries:
        try:
            r = requests.get("https://newsapi.org/v2/everything",
                params={"q": q, "language": "en", "sortBy": "publishedAt",
                         "pageSize": 20, "apiKey": NEWSAPI_KEY}, timeout=15)
            for item in r.json().get("articles", []):
                title = (item.get("title") or "").strip()
                summary = (item.get("description") or "").strip()
                if title and _relevant(title, summary):
                    articles.append(_row(
                        title, summary, item.get("url", ""),
                        item.get("source", {}).get("name", "newsapi"),
                        item.get("publishedAt"),
                    ))
        except Exception as e:
            print(f"  [!] NewsAPI '{q[:25]}': {type(e).__name__}")

    seen = set()
    return [a for a in articles if not (a["title_hash"] in seen or seen.add(a["title_hash"]))]


def scrape_gdelt() -> list[dict]:
    """Consulta GDELT DOC API para noticias de supply chain / pharma."""
    queries = [
        "pharmaceutical supply chain",
        "supplier factory fire",
        "drug shortage",
        "export restriction sanctions",
        "port strike logistics",
    ]
    import time
    articles = []
    for q in queries:
        try:
            time.sleep(2)
            r = requests.get("https://api.gdeltproject.org/api/v2/doc/doc", params={
                "query": q, "mode": "artlist", "maxrecords": 20,
                "format": "json", "timespan": "5d",
            }, timeout=15)
            if r.status_code != 200:
                continue
            data = r.json()
            for item in data.get("articles", []):
                title = (item.get("title") or "").strip()
                url = item.get("url") or ""
                domain = item.get("domain") or "gdelt"
                pub = item.get("seendate") or ""
                if title and _relevant(title, ""):
                    articles.append(_row(title, "", url, domain, pub))
        except Exception as e:
            print(f"  [!] GDELT '{q[:25]}': {type(e).__name__}")

    seen = set()
    deduped = [a for a in articles if not (a["title_hash"] in seen or seen.add(a["title_hash"]))]
    print(f"  GDELT: {len(deduped)} articulos")
    return deduped


def save_to_supabase(articles: list[dict]) -> int:
    """Inserta articulos en Supabase con upsert (sin duplicados)."""
    if not SUPABASE_URL or not SUPABASE_KEY:
        print("[!] Faltan SUPABASE_URL / SUPABASE_KEY")
        return 0

    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "resolution=merge-duplicates,return=minimal",
    }
    endpoint = f"{SUPABASE_URL}/rest/v1/scraped_news?on_conflict=title_hash"

    inserted = 0
    for i in range(0, len(articles), 50):
        batch = articles[i:i + 50]
        r = requests.post(endpoint, headers=headers, json=batch)
        if r.status_code in (200, 201):
            inserted += len(batch)
        elif r.status_code == 409:
            for a in batch:
                r2 = requests.post(endpoint, headers=headers, json=[a])
                if r2.status_code in (200, 201):
                    inserted += 1
        else:
            print(f"  [!] batch {i}: {r.status_code} {r.text[:150]}")
    return inserted


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--source", choices=["rss", "newsapi", "gdelt", "all"], default="all")
    args = parser.parse_args()

    print(f"[{_now()}] scraper.py")
    articles: list[dict] = []

    if args.source in ("rss", "all"):
        articles.extend(scrape_rss())
    if args.source in ("newsapi", "all"):
        articles.extend(scrape_newsapi())
    if args.source in ("gdelt", "all"):
        articles.extend(scrape_gdelt())

    seen: set[str] = set()
    unique = [a for a in articles if not (a["title_hash"] in seen or seen.add(a["title_hash"]))]
    print(f"  Total unicos: {len(unique)}")

    if args.dry_run:
        for a in unique[:15]:
            print(f"  [{a['source']:30s}] {a['title'][:90]}")
        if len(unique) > 15:
            print(f"  ... +{len(unique) - 15} mas")
        return

    if unique:
        n = save_to_supabase(unique)
        print(f"  Guardados en Supabase: {n}")


if __name__ == "__main__":
    main()
