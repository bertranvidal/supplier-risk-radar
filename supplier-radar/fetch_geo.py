"""Conocimiento geografico estructurado: sitúa cada ciudad de proveedor dentro de su provincia/estado (GeoNames).

Descarga datos publicos de GeoNames (CC BY 4.0, https://www.geonames.org) y genera data/geo_regions.json:
  { "Ahmedabad": ["gujarat", ...], ... }
que el matcher usa para vincular noticias que mencionan solo la region ('Gujarat', 'Lombardy', 'Zhejiang').

  python3 fetch_geo.py            # requires internet
"""
import io
import json
import re
import unicodedata
import urllib.request
import zipfile

import pandas as pd

from radar.config import DATA
from radar.data import load_suppliers

BASE = "https://download.geonames.org/export/dump/"
COUNTRY_OVERRIDES = {"USA": "US", "Puerto Rico (USA)": "PR"}


def norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def build(cities_txt: str, admin_txt: str, country_txt: str, suppliers: pd.DataFrame) -> dict:
    iso = {}
    for line in country_txt.splitlines():
        if line and not line.startswith("#"):
            p = line.split("\t")
            iso[norm(p[4])] = p[0]
    admin = {}
    for line in admin_txt.splitlines():
        p = line.split("\t")
        if len(p) >= 3:
            admin[p[0]] = (p[1], p[2])
    rows = []
    for line in cities_txt.splitlines():
        p = line.split("\t")
        if len(p) >= 15:
            rows.append((p[1], p[2], p[3], p[8], p[10], int(p[14] or 0)))
    out = {}
    for s in suppliers.itertuples():
        cc = COUNTRY_OVERRIDES.get(s.Country) or iso.get(norm(s.Country))
        key = norm(s.City)
        cand = [r for r in rows if r[3] == cc and (norm(r[0]) == key or norm(r[1]) == key or key in {norm(a) for a in r[2].split(",")})]
        if not cand:
            continue
        top = max(r[5] for r in cand)
        main = [r for r in cand if r[5] >= 0.3 * top]
        if len({r[4] for r in main}) > 1:  # ciudad ambigua (varias del mismo nombre): no se adivina
            continue
        r = max(main, key=lambda x: x[5])
        names = set()
        for n in admin.get(f"{cc}.{r[4]}", ()):
            names.add(norm(n))
        names.discard(key)  # solo el nombre de la region (provincia/estado); NO los nombres alternativos de la ciudad
        out[s.City] = sorted(n for n in names if len(n) >= 4)[:15]
    return out


def download(name: str) -> str:
    with urllib.request.urlopen(BASE + name, timeout=120) as r:
        raw = r.read()
    if name.endswith(".zip"):
        z = zipfile.ZipFile(io.BytesIO(raw))
        return z.read(z.namelist()[0]).decode("utf-8")
    return raw.decode("utf-8")


if __name__ == "__main__":
    res = build(download("cities15000.zip"), download("admin1CodesASCII.txt"), download("countryInfo.txt"), load_suppliers())
    (DATA / "geo_regions.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{len(res)} ciudades con region -> data/geo_regions.json")
    for c, a in list(res.items())[:12]:
        print(" ", c, "->", ", ".join(a[:6]))
