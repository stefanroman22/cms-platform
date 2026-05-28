# RT Scraper

## Overview

`rt-scraper` is a self-contained Python package that harvests business leads from Google Maps for Roman Technologies' outbound pipeline. It runs as a long-lived process on a Hetzner box (driven by a systemd timer), not on Vercel — it must stay isolated from the FastAPI backend because Playwright + Chromium far exceed Vercel's serverless limits. The v1 cut deliberately uses no paid APIs (no Google Places, no SerpAPI) and does not download photos; only public DOM data and image URLs are captured.

## Requirements

- Python 3.11 or newer.
- Playwright Chromium browser (installed via `python -m playwright install chromium`).
- On Linux hosts, the matching system libraries for headless Chrome (installed with `--with-deps`, requires `sudo`).
- A Supabase project with the `leads` schema from Phase A applied.

## Local development

```bash
git clone git@github.com:stefanroman22/cms-platform.git
cd cms-platform/scraper
python3.11 -m venv venv
source venv/Scripts/activate   # or venv/bin/activate on Linux/macOS
pip install -e ".[dev]"
python -m playwright install --with-deps chromium
cp .env.example .env
# Fill in SUPABASE_URL and SUPABASE_SERVICE_KEY in .env
```

## Env vars

- `SUPABASE_URL` — Supabase project URL; target of the primary upsert sink.
- `SUPABASE_SERVICE_KEY` — service-role key used server-side by the scraper to bypass RLS.
- `SCRAPER_HEADLESS` — `true` in prod; set `false` locally to watch Chromium drive.
- `SCRAPER_LOCALE_DEFAULT` — Accept-Language / UI locale fallback when a job does not specify one.
- `SCRAPER_USER_AGENT` — UA string Playwright sends on every request.
- `SCRAPER_MIN_DELAY_MS` / `SCRAPER_MAX_DELAY_MS` — bounds for the randomised inter-action sleep that keeps pacing polite.

## CLI

The package exposes a Typer-based CLI registered as the `scraper` entry point.

### Quick run (defaults)

All fields are optional. With zero arguments the scraper runs against
**Netherlands**, category **"businesses"**, **all cities country-wide**,
**reviews on (top 3 by stars)**, and the **no-website filter**.

```bash
python -m scraper.cli scrape --dry-run
```

Override any field with the matching `--option`. See `scrape --help` for the full list.

### scrape

Runs a single ad-hoc scrape. Useful for manual testing and one-off harvests.

```bash
python -m scraper.cli scrape --category restaurants --country NL --city Lelystad --max 10 --dry-run
```

`--dry-run` writes results to a local JSON file instead of Supabase; omit it for a real run.

### scrape-url

Scrape a single business by its Google Maps URL. Useful for ad-hoc lead lookup or for verifying the extraction pipeline against a known place page.

```bash
python -m scraper.cli scrape-url "https://maps.app.goo.gl/abc123" --dry-run
```

Accepts full URLs (`google.com/maps/place/...`), legacy short links (`goo.gl/maps/...`), and mobile share links (`maps.app.goo.gl/...`). Short links are expanded automatically.

Supabase is used by default; pass `--no-supabase` to skip it. `--dry-run` writes to `./lead-single.json` by default (use `--out` to override).

Filters from the search-mode `scrape` command are bypassed — the user has explicitly chosen this lead, so it is always written to the configured sinks.

### run-pending

Consumes pending `scrape_job` rows from Supabase and processes them in order. This is the command the systemd timer on the Hetzner box invokes on its schedule — no flags required.

```bash
python -m scraper.cli run-pending
```

## Sinks

- **JSON** — used by `--dry-run`; one file per invocation under `./out/`.
- **Supabase** — primary sink; upserts on `external_id` so re-runs are idempotent.

## Architecture

- `google_maps.py` — Playwright engine; owns browser lifecycle and result-card scraping.
- `pipeline.py` — orchestrates job → engine → sinks, handles retries and pacing.
- `sinks/` — pluggable output adapters (JSON / Supabase) behind a common `Sink` interface.
- `selectors.py` — centralised DOM selectors; the only file that should change when Google rearranges its markup.

## Extension points

- **About-tab attribute scraping** — currently skipped; would fill `Lead.about` with structured tags (wheelchair access, payment methods, etc.).
- **Photo downloading to Supabase Storage** — v1 stores image URLs only; later phase will fetch and rehost them.
- **Residential proxy layer in `_new_context` of `google_maps.py`** — single hook to route Playwright through a proxy provider without touching the rest of the pipeline.
- **Additional source scrapers (OSM, directories)** — new engines can ship alongside `google_maps.py` as long as they emit the same `Lead` shape into the same `Sink` contract.
- **The `automation` `lead_type` branch** — its own extraction path that drops industry-specific signals into the `Lead.extra` JSON column.

## Deploy

Production runs on a Hetzner VM via systemd timer; see `deploy/DEPLOY.md` for the full setup.

## Troubleshooting

Google selector drift → update `src/scraper/selectors.py`.
