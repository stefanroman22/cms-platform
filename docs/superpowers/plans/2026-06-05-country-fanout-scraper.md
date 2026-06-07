# RT Scraper — Country → Cities Fan-out Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Type a country code and exhaustively cover every city (small and big) by fanning out one grid scrape job per municipality, drained by the existing job queue, extensible to new countries via a drop-in data file.

**Architecture:** A per-country JSONL registry (`regions/nl.jsonl`, 342 municipality bboxes seeded offline from PDOK/CBS) + a curated category preset + a `scrape-country` CLI command that enqueues one auto-scaled grid `scrape_jobs` row per municipality. Reuses the existing grid engine and `run-pending` worker unchanged.

**Tech Stack:** Python 3.11, Pydantic v2, Typer, Supabase, pytest, mypy strict, ruff. Build tool uses stdlib `urllib`/`json` against PDOK CBS Gebiedsindelingen WFS (CC0).

> **Commit gate (Stefan's standing rule):** Do NOT run `git commit` until Stefan explicitly says so. Keep `mypy src` + full pytest green at every phase boundary; commit commands below are staged checkpoints for his go-ahead.

> **Run from `scraper/`:** tests `./.venv/Scripts/python.exe -m pytest -q` · types `./.venv/Scripts/python.exe -m mypy src` · lint `./.venv/Scripts/python.exe -m ruff check .`

---

## File Structure

- Create: `src/scraper/regions/__init__.py` — `RegionEntry` model + `load_country` + `list_countries`.
- Create: `src/scraper/regions/nl.jsonl` — generated data (342 municipalities).
- Create: `tools/build_regions.py` — offline one-time seeder (PDOK fetch → jsonl).
- Modify: `src/scraper/categories.py` — add `CURATED_CATEGORIES`.
- Modify: `src/scraper/cli.py` — add `scrape-country` command + imports.
- Modify: `pyproject.toml` — `[tool.setuptools.package-data]` for `*.jsonl`.
- Create: `tests/test_regions.py`; Modify: `tests/test_categories.py` (new file), `tests/test_cli.py`.

---

## Task 1: Region registry model + loader (TDD)

**Files:** Create `src/scraper/regions/__init__.py`; Create `tests/test_regions.py`

- [ ] **Step 1: Write the failing loader tests** — `tests/test_regions.py`:
```python
"""Tests for the per-country region registry."""

from __future__ import annotations

import pytest

from scraper.regions import RegionEntry, list_countries, load_country


def _write(tmp_path, cc, lines):
    p = tmp_path / f"{cc}.jsonl"
    p.write_text("".join(line + "\n" for line in lines), encoding="utf-8")
    return p


def test_load_country_reads_jsonl(tmp_path):
    _write(
        tmp_path,
        "xx",
        [
            '{"name":"Foo","country_code":"XX","code":"C1","bbox":[52.0,5.0,52.1,5.1]}',
            '{"name":"Bar","country_code":"XX","code":"C2","bbox":[51.0,4.0,51.1,4.1]}',
        ],
    )
    entries = load_country("XX", base_dir=tmp_path)
    assert [e.name for e in entries] == ["Foo", "Bar"]
    assert entries[0].bbox == (52.0, 5.0, 52.1, 5.1)
    assert isinstance(entries[0], RegionEntry)


def test_load_country_skips_blank_lines(tmp_path):
    _write(tmp_path, "xx", ['{"name":"A","country_code":"XX","bbox":[1.0,2.0,3.0,4.0]}', "", "  "])
    assert len(load_country("xx", base_dir=tmp_path)) == 1


def test_load_country_unknown_raises(tmp_path):
    with pytest.raises(ValueError, match="no region file"):
        load_country("zz", base_dir=tmp_path)


def test_list_countries(tmp_path):
    _write(tmp_path, "nl", [])
    _write(tmp_path, "de", [])
    assert set(list_countries(base_dir=tmp_path)) == {"nl", "de"}
```

- [ ] **Step 2: Run — expect ImportError**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_regions.py -q`
Expected: FAIL — no module `scraper.regions`

- [ ] **Step 3: Create `src/scraper/regions/__init__.py`:**
```python
"""Per-country region registry: one <iso>.jsonl file per country, each line a
municipality/city with a precomputed bbox. Adding a country = drop in a file."""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, ConfigDict


class RegionEntry(BaseModel):
    """One administrative unit to fan a grid scrape over. bbox order matches
    grid_centers / ScrapeParams.bbox exactly: (min_lat, min_lng, max_lat, max_lng)."""

    model_config = ConfigDict(extra="ignore")

    name: str
    country_code: str
    code: str | None = None
    bbox: tuple[float, float, float, float]
    centroid: tuple[float, float] | None = None
    population: int | None = None
    source: str | None = None


def load_country(cc: str, *, base_dir: Path | None = None) -> list[RegionEntry]:
    """Load all region entries for an ISO country code. Raises ValueError if the
    country has no registry file."""
    base = base_dir or Path(__file__).parent
    path = base / f"{cc.lower()}.jsonl"
    if not path.exists():
        raise ValueError(f"no region file for country {cc!r} ({path})")
    entries: list[RegionEntry] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if line:
            entries.append(RegionEntry.model_validate_json(line))
    return entries


def list_countries(*, base_dir: Path | None = None) -> list[str]:
    """Return the ISO codes that have a registry file."""
    base = base_dir or Path(__file__).parent
    return sorted(p.stem for p in base.glob("*.jsonl"))
```

- [ ] **Step 4: Run — expect PASS**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_regions.py -q`
Expected: PASS (4 tests)

- [ ] **Step 5: Types**

Run: `./.venv/Scripts/python.exe -m mypy src`
Expected: `Success`

## Task 2: Seed tool + generate `nl.jsonl`

**Files:** Create `tools/build_regions.py`; Create `src/scraper/regions/nl.jsonl` (generated); Modify `tests/test_regions.py`

- [ ] **Step 1: Create `tools/build_regions.py`:**
```python
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
        if isinstance(c, list) and c and isinstance(c[0], (int, float)):
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
```

- [ ] **Step 2: Run the seeder to generate `nl.jsonl`**

Run: `./.venv/Scripts/python.exe tools/build_regions.py nl`
Expected: `wrote 342 municipalities to ...regions/nl.jsonl`

- [ ] **Step 3: Add the real-data registry test** to `tests/test_regions.py`:
```python
def test_load_country_nl_has_342_municipalities():
    entries = load_country("nl")
    assert len(entries) == 342
    names = {e.name for e in entries}
    assert "Amsterdam" in names and "Rotterdam" in names
    for e in entries:
        min_lat, min_lng, max_lat, max_lng = e.bbox
        assert min_lat < max_lat and min_lng < max_lng
        assert 50.0 <= min_lat <= 54.0 and 3.0 <= min_lng <= 7.5  # NL range
```

- [ ] **Step 4: Run — expect PASS**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_regions.py -q`
Expected: PASS (5 tests)

## Task 3: Curated category preset (TDD)

**Files:** Modify `src/scraper/categories.py`; Create `tests/test_categories.py`

- [ ] **Step 1: Write the failing test** — `tests/test_categories.py`:
```python
from scraper.categories import CURATED_CATEGORIES, DEFAULT_CATEGORIES


def test_curated_is_subset_of_default():
    assert set(CURATED_CATEGORIES).issubset(set(DEFAULT_CATEGORIES))


def test_curated_no_duplicates_and_reasonable_size():
    assert len(CURATED_CATEGORIES) == len(set(CURATED_CATEGORIES))
    assert 18 <= len(CURATED_CATEGORIES) <= 26


def test_curated_drops_website_saturated_categories():
    for dropped in ("pharmacy", "law firm", "accountant", "dentist", "real estate agency"):
        assert dropped not in CURATED_CATEGORIES
```

- [ ] **Step 2: Run — expect ImportError**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_categories.py -q`
Expected: FAIL — cannot import `CURATED_CATEGORIES`

- [ ] **Step 3: Add `CURATED_CATEGORIES`** to the end of `src/scraper/categories.py`:
```python
# Curated high-value subset for country-wide fan-out: independent trades, food,
# and personal services with high no-website rates. Drops website-saturated /
# regulated / chain categories (pharmacy, optician, dentist, law firm, accountant,
# real estate, travel agency, gym, etc.). The volume vs completeness dial.
CURATED_CATEGORIES: list[str] = [
    "restaurant", "cafe", "bar", "bakery", "hairdresser", "barber shop",
    "beauty salon", "nail salon", "plumber", "electrician", "carpenter",
    "painter", "roofer", "cleaning service", "landscaper", "car repair",
    "florist", "butcher", "photographer", "driving school", "tattoo parlor",
    "tailor", "dry cleaner", "bike shop",
]
```

- [ ] **Step 4: Run — expect PASS**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_categories.py -q`
Expected: PASS (3 tests)

## Task 4: `scrape-country` command + packaging (TDD)

**Files:** Modify `src/scraper/cli.py`; Modify `pyproject.toml`; Modify `tests/test_cli.py`

- [ ] **Step 1: Write the failing CLI tests** (append to `tests/test_cli.py`):
```python
def _fake_entries():
    from scraper.regions import RegionEntry

    return [
        RegionEntry(name="Alpha", country_code="NL", code="GM1", bbox=(52.0, 5.0, 52.05, 5.08)),
        RegionEntry(name="Beta", country_code="NL", code="GM2", bbox=(51.9, 4.9, 52.0, 5.0)),
    ]


def test_scrape_country_dry_run_plans_without_enqueue():
    with (
        patch("scraper.cli.load_country", return_value=_fake_entries()),
        patch("scraper.cli.create_client") as cc,
    ):
        result = runner.invoke(app, ["scrape-country", "NL", "--dry-run"])
    assert result.exit_code == 0, result.stdout
    assert "2 municipalities" in result.stdout
    cc.assert_not_called()


def test_scrape_country_enqueues_curated_jobs_with_autoscaled_max_cells():
    from scraper.categories import CURATED_CATEGORIES
    from scraper.geo import grid_centers

    captured = {}

    class FakeTable:
        def insert(self, rows):
            captured["rows"] = rows
            return self

        def execute(self):
            return None

    class FakeSB:
        def table(self, name):
            captured["table"] = name
            return FakeTable()

    with (
        patch("scraper.cli.load_country", return_value=_fake_entries()),
        patch("scraper.cli.create_client", return_value=FakeSB()),
        patch.object(__import__("scraper.cli", fromlist=["settings"]).settings, "SUPABASE_URL", "x"),
        patch.object(
            __import__("scraper.cli", fromlist=["settings"]).settings, "SUPABASE_SERVICE_KEY", "y"
        ),
    ):
        result = runner.invoke(app, ["scrape-country", "NL", "--limit", "1"])

    assert result.exit_code == 0, result.stdout
    assert captured["table"] == "scrape_jobs"
    assert len(captured["rows"]) == 1
    row = captured["rows"][0]
    assert row["status"] == "pending"
    assert row["triggered_by"] == "country-fanout"
    p = row["params"]
    assert p["categories"] == list(CURATED_CATEGORIES)
    assert p["region"] == "Alpha"
    assert tuple(p["bbox"]) == (52.0, 5.0, 52.05, 5.08)
    expected_cells = len(list(grid_centers(52.0, 5.0, 52.05, 5.08, cell_km=1.2)))
    assert p["max_cells"] == expected_cells  # auto-scaled, never rejects


def test_scrape_country_deep_uses_full_categories():
    from scraper.categories import DEFAULT_CATEGORIES

    captured = {}

    class FakeTable:
        def insert(self, rows):
            captured["rows"] = rows
            return self

        def execute(self):
            return None

    class FakeSB:
        def table(self, name):
            return FakeTable()

    with (
        patch("scraper.cli.load_country", return_value=_fake_entries()),
        patch("scraper.cli.create_client", return_value=FakeSB()),
        patch.object(__import__("scraper.cli", fromlist=["settings"]).settings, "SUPABASE_URL", "x"),
        patch.object(
            __import__("scraper.cli", fromlist=["settings"]).settings, "SUPABASE_SERVICE_KEY", "y"
        ),
    ):
        result = runner.invoke(app, ["scrape-country", "NL", "--deep", "--limit", "1"])

    assert result.exit_code == 0, result.stdout
    assert captured["rows"][0]["params"]["categories"] == list(DEFAULT_CATEGORIES)
```

- [ ] **Step 2: Run — expect FAIL** (no `scrape-country` command)

Run: `./.venv/Scripts/python.exe -m pytest tests/test_cli.py -q -k scrape_country`
Expected: FAIL

- [ ] **Step 3: Add imports to `cli.py`.** Add to the local-import group (alphabetical):
```python
from .categories import CURATED_CATEGORIES, DEFAULT_CATEGORIES
```
(before `from .config import settings`), and:
```python
from .geo import grid_centers
```
(after `from .config import settings`), and:
```python
from .regions import load_country
```
(after `from .pipeline import run_pipeline`).

- [ ] **Step 4: Add the `scrape-country` command** to `cli.py` (after the `scrape` command, before `run-pending`):
```python
@app.command("scrape-country")
def scrape_country(
    country: Annotated[str, typer.Argument(help="ISO country code, e.g. NL")],
    deep: Annotated[bool, typer.Option("--deep")] = False,
    limit: Annotated[int | None, typer.Option("--limit")] = None,
    dry_run: Annotated[bool, typer.Option("--dry-run")] = False,
    max_cells_cap: Annotated[int, typer.Option("--max-cells-cap")] = 0,
) -> None:
    """Fan a whole country out into one grid scrape job per municipality.

    Enqueues pending scrape_jobs (drained by `run-pending`). --dry-run previews
    the plan without enqueuing. --deep uses the full 46-category set instead of
    the curated high-value preset."""
    entries = load_country(country)
    if limit is not None:
        entries = entries[:limit]
    cats = list(DEFAULT_CATEGORIES if deep else CURATED_CATEGORIES)

    rows: list[dict[str, object]] = []
    total_queries = 0
    preview: list[tuple[str, int]] = []
    for e in entries:
        cells = len(list(grid_centers(*e.bbox, cell_km=1.2)))
        max_cells = cells if max_cells_cap <= 0 else min(cells, max_cells_cap)
        params = ScrapeParams(
            country=country.upper(),
            region=e.name,
            bbox=e.bbox,
            categories=cats,
            grid_cell_km=1.2,
            grid_zoom=16,
            max_cells=max_cells,
        )
        rows.append(
            {
                "status": "pending",
                "params": params.model_dump(mode="json"),
                "triggered_by": "country-fanout",
            }
        )
        preview.append((e.name, cells))
        total_queries += cells * len(cats)

    typer.echo(
        f"{len(rows)} municipalities, {len(cats)} categories, "
        f"~{total_queries} scoped queries"
    )
    if dry_run:
        for name, cells in preview[:20]:
            typer.echo(f"  {name}: {cells} cells")
        if len(preview) > 20:
            typer.echo(f"  ... and {len(preview) - 20} more")
        return
    if not settings.SUPABASE_URL or not settings.SUPABASE_SERVICE_KEY:
        raise typer.BadParameter("SUPABASE_URL + SUPABASE_SERVICE_KEY required to enqueue")
    sb = create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_KEY)
    sb.table("scrape_jobs").insert(rows).execute()
    typer.echo(f"enqueued {len(rows)} scrape jobs")
```

- [ ] **Step 5: Run the CLI tests — expect PASS**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_cli.py -q -k scrape_country`
Expected: PASS (3 tests)

- [ ] **Step 6: Add package-data to `pyproject.toml`** (after the `[tool.setuptools.packages.find]` block):
```toml
[tool.setuptools.package-data]
"scraper.regions" = ["*.jsonl"]
```

- [ ] **Step 7: Full green gate**

Run: `./.venv/Scripts/python.exe -m mypy src && ./.venv/Scripts/python.exe -m ruff check . && ./.venv/Scripts/python.exe -m pytest -q`
Expected: mypy clean; ruff clean; ALL tests PASS

- [ ] **Step 8 (commit — on Stefan's go-ahead):**
```bash
git add scraper/src/scraper/regions scraper/src/scraper/categories.py scraper/src/scraper/cli.py scraper/tools/build_regions.py scraper/pyproject.toml scraper/tests/test_regions.py scraper/tests/test_categories.py scraper/tests/test_cli.py
git commit -m "feat(scraper): country->cities fan-out (region registry + scrape-country)"
```

---

## Task 5: Verification

- [ ] **Step 1: Manual dry-run smoke**

Run: `./.venv/Scripts/python.exe -m scraper.cli scrape-country NL --dry-run`
Expected: `342 municipalities, 24 categories, ~<N> scoped queries` + a preview list.

- [ ] **Step 2: Confirm large munis don't trip the guard.** Spot-check that the
  largest-bbox municipality's planned `max_cells` ≥ its cell count (so
  `_build_grid_queries` would not raise `GridTooLargeError`).

- [ ] **Step 3: Adversarial review** — dispatch subagents/Workflow to check the diff
  vs spec: registry loader correctness, bbox order `(min_lat,min_lng,max_lat,max_lng)`
  consistent end-to-end, `scrape-country` enqueues valid `ScrapeParams` (curated cats,
  auto max_cells), no engine/`scrape-url`/`run-pending` regressions, mypy/ruff/tests green.

- [ ] **Step 4 (optional, with Supabase creds): enqueue a tiny slice live**

Run: `./.venv/Scripts/python.exe -m scraper.cli scrape-country NL --limit 2`
Expected: `enqueued 2 scrape jobs`; two `pending` rows appear in `scrape_jobs`.

---

## Self-Review (completed during planning)

**Spec coverage:** registry (Task 1) ✓; seed tool + nl.jsonl 342 (Task 2) ✓; curated preset (Task 3) ✓; `scrape-country` command + guard auto-scale + packaging (Task 4) ✓; no DB migration (reuses `scrape_jobs`) ✓; enqueue-only ✓; explicitly-OUT items not scheduled ✓.

**Placeholder scan:** none — full code in every step.

**Type consistency:** `RegionEntry.bbox: tuple[float,float,float,float]` = `(min_lat,min_lng,max_lat,max_lng)` consistent across registry, `_bbox()` seeder, `grid_centers(*bbox)`, and `ScrapeParams.bbox`; `load_country(cc, *, base_dir=None) -> list[RegionEntry]` signature matches all call sites; `CURATED_CATEGORIES`/`DEFAULT_CATEGORIES` are `list[str]`.
