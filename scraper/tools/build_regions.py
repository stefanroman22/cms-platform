"""One-time offline seeder for src/scraper/regions/<cc>.jsonl.

NL: pulls all 342 municipality polygons from PDOK CBS Gebiedsindelingen (WFS,
WGS84, CC0), computes each bbox, best-effort enriches population from Wikidata,
and writes one JSONL line per municipality sorted population-first.

Run: ./.venv/Scripts/python.exe tools/build_regions.py nl
"""

from __future__ import annotations

import json
import sys
import urllib.parse
import urllib.request
from pathlib import Path

_PDOK = (
    "https://service.pdok.nl/cbs/gebiedsindelingen/2025/wfs/v1_0"
    "?request=GetFeature&service=WFS&version=2.0.0"
    "&typeName=gebiedsindelingen:gemeente_gegeneraliseerd"
    "&outputFormat=application/json&srsName=EPSG:4326"
)
_WIKIDATA = "https://query.wikidata.org/sparql"
_UA = "rt-scraper/1.0 (ops@romantech.example)"
_OUT = Path(__file__).resolve().parent.parent / "src" / "scraper" / "regions"


def _get(url: str, headers: dict[str, str] | None = None) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": _UA, **(headers or {})})
    with urllib.request.urlopen(req, timeout=120) as r:
        return r.read()


def _bbox(geom: dict) -> tuple[float, float, float, float]:
    xs: list[float] = []
    ys: list[float] = []

    def walk(c: object) -> None:
        if isinstance(c, list) and c and isinstance(c[0], int | float):
            xs.append(float(c[0]))
            ys.append(float(c[1]))
        elif isinstance(c, list):
            for x in c:
                walk(x)

    walk(geom["coordinates"])
    return (min(ys), min(xs), max(ys), max(xs))  # (min_lat,min_lng,max_lat,max_lng)


def _populations() -> dict[str, int]:
    """Best-effort {lowercased name: population} from Wikidata; {} on failure."""
    query = (
        "SELECT ?nameLabel ?pop WHERE { ?m wdt:P31 wd:Q2039348; wdt:P1082 ?pop; "
        "rdfs:label ?nameLabel. FILTER(LANG(?nameLabel)='nl') }"
    )
    try:
        url = f"{_WIKIDATA}?{urllib.parse.urlencode({'query': query, 'format': 'json'})}"
        data = json.loads(_get(url, {"Accept": "application/sparql-results+json"}))
        out: dict[str, int] = {}
        for b in data["results"]["bindings"]:
            out[b["nameLabel"]["value"].strip().lower()] = int(float(b["pop"]["value"]))
        return out
    except Exception as exc:  # noqa: BLE001 — population is optional
        print(f"  (population enrichment skipped: {exc})", file=sys.stderr)
        return {}


def build_nl() -> None:
    feats = json.loads(_get(_PDOK))["features"]
    if len(feats) != 342:
        print(f"WARNING: expected 342 municipalities, got {len(feats)}", file=sys.stderr)
    pops = _populations()
    rows = []
    for f in feats:
        name = f["properties"]["statnaam"]
        mn, mln, mx, mxl = _bbox(f["geometry"])
        rows.append(
            {
                "name": name,
                "country_code": "NL",
                "code": f["properties"].get("statcode"),
                "bbox": [round(mn, 6), round(mln, 6), round(mx, 6), round(mxl, 6)],
                "centroid": [round((mn + mx) / 2, 6), round((mln + mxl) / 2, 6)],
                "population": pops.get(name.strip().lower()),
                "source": "pdok-cbs-2025",
            }
        )
    rows.sort(key=lambda r: (r["population"] is None, -(r["population"] or 0), r["name"]))
    _OUT.mkdir(parents=True, exist_ok=True)
    (_OUT / "nl.jsonl").write_text(
        "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8"
    )
    print(f"wrote {len(rows)} municipalities to {_OUT / 'nl.jsonl'}")


if __name__ == "__main__":
    cc = sys.argv[1] if len(sys.argv) > 1 else "nl"
    if cc != "nl":
        raise SystemExit(f"only 'nl' is supported by this seeder; got {cc!r}")
    build_nl()
