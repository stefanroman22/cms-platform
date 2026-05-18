# RT Scraper

## Overview

`rt-scraper` is a self-contained Python package that harvests business leads from Google Maps for Roman Technologies' outbound pipeline. It runs as a long-lived process on a Hetzner box (driven by a systemd timer), not on Vercel — it must stay isolated from the FastAPI backend because Playwright + Chromium far exceed Vercel's serverless limits. The v1 cut deliberately uses no paid APIs (no Google Places, no SerpAPI) and does not download photos; only public DOM data and image URLs are captured.

## Requirements

- Python 3.11 or newer.
- Playwright Chromium browser (installed via `python -m playwright install chromium`).
- On Linux hosts, the matching system libraries for headless Chrome (installed with `--with-deps`, requires `sudo`).
- A Supabase project with the `leads` schema from Phase A applied, and a Google service-account JSON for the Sheets mirror.

## Local development

```bash
git clone git@github.com:stefanroman22/cms-platform.git
cd cms-platform/scraper
python3.11 -m venv venv
source venv/Scripts/activate   # or venv/bin/activate on Linux/macOS
pip install -e ".[dev]"
python -m playwright install --with-deps chromium
cp .env.example .env
# Fill in SUPABASE_URL, SUPABASE_SERVICE_KEY, and the Google Sheets values in .env
```

## Env vars

- `SUPABASE_URL` — Supabase project URL; target of the primary upsert sink.
- `SUPABASE_SERVICE_KEY` — service-role key used server-side by the scraper to bypass RLS.
- `GOOGLE_SHEETS_CREDENTIALS_JSON` — absolute path to the Google service-account JSON file.
- `GOOGLE_SHEET_ID` — ID of the spreadsheet that mirrors the leads table for human review.
- `SCRAPER_HEADLESS` — `true` in prod; set `false` locally to watch Chromium drive.
- `SCRAPER_LOCALE_DEFAULT` — Accept-Language / UI locale fallback when a job does not specify one.
- `SCRAPER_USER_AGENT` — UA string Playwright sends on every request.
- `SCRAPER_MIN_DELAY_MS` / `SCRAPER_MAX_DELAY_MS` — bounds for the randomised inter-action sleep that keeps pacing polite.

## CLI

The package exposes a Typer-based CLI registered as the `scraper` entry point.

### scrape

Runs a single ad-hoc scrape for a given `lead_type` and country code. Useful for manual testing and one-off harvests.

```bash
python -m scraper.cli scrape restaurants NL --city Lelystad --max 10 --dry-run
```

`--dry-run` writes results to a local JSON file instead of Supabase + Sheets; omit it for a real run.

### run-pending

Consumes pending `scrape_job` rows from Supabase and processes them in order. This is the command the systemd timer on the Hetzner box invokes on its schedule — no flags required.

```bash
python -m scraper.cli run-pending
```

## Sinks

- **JSON** — used by `--dry-run`; one file per invocation under `./out/`.
- **Supabase** — primary sink; upserts on `external_id` so re-runs are idempotent.
- **Google Sheets** — append-by-header mirror so non-technical reviewers can triage leads in-browser.

## Architecture

- `google_maps.py` — Playwright engine; owns browser lifecycle and result-card scraping.
- `pipeline.py` — orchestrates job → engine → sinks, handles retries and pacing.
- `sinks/` — pluggable output adapters (JSON / Supabase / Sheets) behind a common `Sink` interface.
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
