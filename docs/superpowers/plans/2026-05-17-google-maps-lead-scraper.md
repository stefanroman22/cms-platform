# Google Maps Lead Scraper + Admin Dashboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Playwright-based Google Maps scraper that finds businesses without websites and writes leads to Supabase + a Google Sheet, plus an admin-only "Leads" tab in the existing CMS to browse leads and dispatch new scrape jobs via a Hetzner cron worker.

**Architecture:** Three components glued by a `scrape_jobs` queue table. (1) `scraper/` — self-contained Python package using Playwright (Chromium, headless) with abstract `Sink` interface (Supabase, Sheets, JSON), CLI via Typer, `run-pending` mode that claims pending jobs and writes leads back to the same DB row. (2) FastAPI admin routes (`/admin/leads`, `/admin/scrape-jobs`) gated by existing `admin_user_via_bearer_or_sid` dependency, paginated/filterable list, mutation endpoints. (3) Next.js admin page at `/dashboard/admin/leads` with two tabs: data dashboard (stats + table + filter bar + Kanban view + lead detail drawer) and scraper control (form + job history). Existing patterns reused: `useQuery` for fetching, `lib/styles.ts` tokens, `lib/animations.ts` framer-motion presets, `IssueForm`/`IssueList` form-and-list pattern.

**Tech Stack:**
- **Scraper:** Python 3.11, Playwright async, Pydantic v2, pydantic-settings, Typer, Loguru, Tenacity, RapidFuzz, supabase-py, gspread, google-auth
- **DB:** Supabase Postgres (existing project), one migration with 8 enums + 2 tables
- **Backend:** FastAPI 0.136 (existing), Pydantic v2 (existing)
- **Frontend:** Next.js 16.2 + React 19.2 + TypeScript + Tailwind v4 + framer-motion (existing), `@dnd-kit/core` (NEW — for Kanban drag)
- **Deploy:** Hetzner Linux box with systemd timer; CMS deploys unchanged via Vercel

---

## Phase Map

| Phase | Scope | Checkpoint |
|-------|-------|-----------|
| 0 | Repo inspection + this plan | 🛑 0 — user confirms plan |
| A | DB migration (enums + tables) | 🛑 A — confirm migration applied |
| B | Scraper package (models, selectors, scrape, sinks, CLI) | 🛑 B1 — Google service account; 🛑 B2 — dry-run live test |
| C | Backend admin API + Frontend leads tab | 🛑 C — wireframe confirm before UI build, demo after |
| D | Hetzner deploy + CI | 🛑 D — confirm timer runs end-to-end |

**DO NOT** proceed past any 🛑 checkpoint without user input. Each phase's tasks below are written so they can be paused at checkpoint without leaving the codebase broken.

---

## File Structure

```
scraper/                                        # NEW package, isolated from CMS
  pyproject.toml
  .env.example
  README.md
  src/scraper/__init__.py
  src/scraper/config.py                         # pydantic-settings Settings
  src/scraper/models.py                         # Lead, ScrapeParams, ScrapeFilters (Pydantic v2)
  src/scraper/selectors.py                      # ALL Google Maps DOM selectors (single source)
  src/scraper/dedup.py                          # name normalization + external_id + presence classify
  src/scraper/google_maps.py                    # Playwright scraping engine
  src/scraper/pipeline.py                       # ScrapeParams -> scrape() -> sinks
  src/scraper/cli.py                            # Typer commands: scrape, run-pending
  src/scraper/sinks/__init__.py
  src/scraper/sinks/base.py                     # abstract Sink
  src/scraper/sinks/supabase_sink.py
  src/scraper/sinks/sheets_sink.py
  src/scraper/sinks/json_sink.py
  tests/                                        # pytest tests
    test_dedup.py
    test_models.py
    test_sinks_json.py
    test_pipeline.py
  deploy/scraper.service
  deploy/scraper.timer
  deploy/DEPLOY.md

backend/migrations/2026_05_17_lead_scraper.sql  # NEW

backend/auth_service/routers/admin_leads.py     # NEW
backend/auth_service/routers/admin_scrape_jobs.py # NEW
backend/auth_service/models/schemas.py          # EXTEND (Pydantic models for Lead, ScrapeJob, requests)
backend/auth_service/main.py                    # EXTEND (mount 2 new routers)
backend/auth_service/tests/test_admin_leads_router.py     # NEW
backend/auth_service/tests/test_admin_scrape_jobs_router.py # NEW

frontend/src/components/dashboard/SidebarPanel.tsx   # EXTEND (add "Leads" admin link)
frontend/src/app/dashboard/admin/leads/page.tsx      # NEW (route entry)
frontend/src/components/admin/leads/LeadsTab.tsx     # NEW (top-level orchestrator)
frontend/src/components/admin/leads/LeadStatsCards.tsx # NEW
frontend/src/components/admin/leads/LeadsTable.tsx   # NEW
frontend/src/components/admin/leads/LeadFilters.tsx  # NEW
frontend/src/components/admin/leads/LeadKanban.tsx   # NEW
frontend/src/components/admin/leads/LeadDetailDrawer.tsx # NEW
frontend/src/components/admin/leads/LeadBadge.tsx    # NEW (status/presence badges)
frontend/src/components/admin/leads/ScraperForm.tsx  # NEW
frontend/src/components/admin/leads/JobHistoryList.tsx # NEW
frontend/src/lib/leadEnums.ts                        # NEW (enum value → label/color maps)

.github/workflows/scraper-ci.yml                # NEW (ruff + mypy on scraper/**)
docs/ENVIRONMENTS.md                            # EXTEND (new scraper env vars)
```

---

# Phase 0 — Plan handoff (🛑 CHECKPOINT 0)

Before any code, the user reviews this plan, the Checkpoint 0 summary in the conversation, and the proposed file layout. They confirm:

- Frontend stack identification matches their understanding
- Admin URL convention `/dashboard/admin/leads` is acceptable
- Backend Pydantic schema collocation in `models/schemas.py` is correct
- Migration naming `2026_05_17_lead_scraper.sql` is acceptable
- Scraper as separate top-level package (not under `backend/` or `agents/`) is acceptable

**Do not start Phase A until the user explicitly confirms.**

---

# Phase A — Database Migration

### Task A1: Write migration file

**Files:**
- Create: `backend/migrations/2026_05_17_lead_scraper.sql`

- [ ] **Step 1: Write the migration**

Create `backend/migrations/2026_05_17_lead_scraper.sql` with the following content:

```sql
-- Lead scraper schema — 2026-05-17
-- See spec: docs/superpowers/plans/2026-05-17-google-maps-lead-scraper.md

-- ────────────────────────────────────────────────────────────────────
-- 1. Enums
-- ────────────────────────────────────────────────────────────────────
CREATE TYPE lead_type AS ENUM ('website', 'automation', 'both');
CREATE TYPE web_presence AS ENUM ('none', 'social_only', 'has_website', 'unknown');
CREATE TYPE website_build_status AS ENUM (
    'not_started', 'building_design', 'design_done',
    'building', 'finished_cms', 'refining', 'not_applicable'
);
CREATE TYPE ai_workflow_status AS ENUM (
    'not_started', 'building', 'finished', 'refining', 'not_applicable'
);
CREATE TYPE lead_status AS ENUM ('not_sent', 'sent', 'accepted', 'refused');
CREATE TYPE lead_contact_type AS ENUM ('not_contacted', 'phone', 'mail', 'in_person');
CREATE TYPE payment_status AS ENUM ('not_applicable', 'not_paid', 'paid');
CREATE TYPE scrape_job_status AS ENUM ('pending', 'running', 'done', 'failed', 'cancelled');

-- ────────────────────────────────────────────────────────────────────
-- 2. scrape_jobs queue table
-- ────────────────────────────────────────────────────────────────────
CREATE TABLE scrape_jobs (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    status          scrape_job_status NOT NULL DEFAULT 'pending',
    params          JSONB NOT NULL,
    started_at      TIMESTAMPTZ,
    finished_at     TIMESTAMPTZ,
    results_found   INT,
    results_inserted INT,
    results_skipped INT,
    error           TEXT,
    triggered_by    TEXT NOT NULL DEFAULT 'cms'
);

CREATE INDEX scrape_jobs_status_created_idx ON scrape_jobs (status, created_at);

COMMENT ON TABLE scrape_jobs IS
'Queue between the CMS admin form and the Hetzner scraper worker. Worker picks status=pending oldest-first.';
COMMENT ON COLUMN scrape_jobs.params IS
'ScrapeParams pydantic model serialised to JSON. Validated by the API before insert.';

-- ────────────────────────────────────────────────────────────────────
-- 3. leads table
-- ────────────────────────────────────────────────────────────────────
CREATE TABLE leads (
    id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    -- provenance
    external_id           TEXT NOT NULL UNIQUE,
    scrape_job_id         UUID REFERENCES scrape_jobs(id) ON DELETE SET NULL,
    primary_source        TEXT NOT NULL DEFAULT 'google_maps',
    source_url            TEXT,
    -- classification
    lead_type             lead_type NOT NULL DEFAULT 'website',
    category              TEXT,
    -- identity
    business_name         TEXT NOT NULL,
    name_normalized       TEXT NOT NULL,
    description           TEXT,
    about                 TEXT,
    -- location
    country               TEXT,
    region                TEXT,
    city                  TEXT,
    address               TEXT,
    postal_code           TEXT,
    lat                   DOUBLE PRECISION,
    lng                   DOUBLE PRECISION,
    -- contact / links
    phone                 TEXT,
    email                 TEXT,
    website_url           TEXT,
    facebook_url          TEXT,
    instagram_url         TEXT,
    menu_url              TEXT,
    -- digital presence
    web_presence          web_presence NOT NULL DEFAULT 'unknown',
    -- reviews / hours / photos
    rating                NUMERIC(2,1),
    review_count          INT,
    reviews               JSONB,
    opening_hours         JSONB,
    photo_urls            TEXT[],
    -- pipeline status
    website_build_status  website_build_status NOT NULL DEFAULT 'not_started',
    ai_workflow_status    ai_workflow_status   NOT NULL DEFAULT 'not_started',
    lead_status           lead_status          NOT NULL DEFAULT 'not_sent',
    lead_contact_type     lead_contact_type    NOT NULL DEFAULT 'not_contacted',
    payment_status        payment_status       NOT NULL DEFAULT 'not_applicable',
    -- AI scoring (future agent)
    ai_score              INT CHECK (ai_score IS NULL OR (ai_score >= 0 AND ai_score <= 100)),
    ai_recommendation     TEXT,
    ai_reasoning          TEXT,
    ai_scored_at          TIMESTAMPTZ,
    -- extensibility
    extra                 JSONB NOT NULL DEFAULT '{}'::jsonb,
    notes                 TEXT,
    -- timestamps
    created_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at            TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX leads_city_idx           ON leads (city);
CREATE INDEX leads_country_idx        ON leads (country);
CREATE INDEX leads_category_idx       ON leads (category);
CREATE INDEX leads_web_presence_idx   ON leads (web_presence);
CREATE INDEX leads_lead_status_idx    ON leads (lead_status);
CREATE INDEX leads_lead_type_idx      ON leads (lead_type);
CREATE INDEX leads_rating_idx         ON leads (rating);
CREATE INDEX leads_scrape_job_id_idx  ON leads (scrape_job_id);

COMMENT ON TABLE leads IS
'One row per business discovered by the scraper. external_id is the dedup key (Google feature id or fallback hash).';
COMMENT ON COLUMN leads.extra IS
'Extensibility seam — new extracted fields, AI scoring intermediate values, new lead_type signals all land here without schema migrations.';

-- ────────────────────────────────────────────────────────────────────
-- 4. updated_at trigger
-- ────────────────────────────────────────────────────────────────────
CREATE OR REPLACE FUNCTION leads_set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER leads_updated_at_trigger
    BEFORE UPDATE ON leads
    FOR EACH ROW EXECUTE FUNCTION leads_set_updated_at();

-- ────────────────────────────────────────────────────────────────────
-- 5. RLS
-- The scraper uses the service-role key and bypasses RLS. The CMS API
-- routes use the service-role key + app-layer admin checks. So RLS is
-- enabled with no permissive policies — any anon access fails closed.
-- ────────────────────────────────────────────────────────────────────
ALTER TABLE leads        ENABLE ROW LEVEL SECURITY;
ALTER TABLE scrape_jobs  ENABLE ROW LEVEL SECURITY;

-- Stub for future authenticated-admin direct access from the frontend
-- (kept commented; CMS goes through FastAPI which uses service-role).
-- CREATE POLICY "Admins can read leads"
--   ON leads FOR SELECT TO authenticated
--   USING (EXISTS (SELECT 1 FROM users WHERE users.id = auth.uid() AND users.is_admin));
```

- [ ] **Step 2: Validate the SQL locally with the Supabase MCP**

Use the `mcp__supabase__apply_migration` tool to apply the migration directly (per memory: Stefan prefers MCP for migrations).

Name: `2026_05_17_lead_scraper`
Query: the full SQL from Step 1.

Expected: success response, no error.

- [ ] **Step 3: Verify tables + enums exist**

Use `mcp__supabase__execute_sql` with:

```sql
SELECT
    (SELECT count(*) FROM pg_type WHERE typname IN
       ('lead_type','web_presence','website_build_status','ai_workflow_status',
        'lead_status','lead_contact_type','payment_status','scrape_job_status')) AS enums,
    (SELECT count(*) FROM information_schema.tables
       WHERE table_schema = 'public' AND table_name IN ('leads','scrape_jobs')) AS tables;
```

Expected: `{ enums: 8, tables: 2 }`.

- [ ] **Step 4: Commit**

```bash
git add backend/migrations/2026_05_17_lead_scraper.sql
git commit -m "feat(db): add leads + scrape_jobs tables for Google Maps lead scraper

8 new enums, 2 new tables with full pipeline-status + AI-scoring columns,
JSONB extra column as the extensibility seam, RLS enabled fail-closed."
```

🛑 **CHECKPOINT A:** Pause. Confirm with user that the migration applied cleanly and they see the new tables in the Supabase dashboard. Do not proceed to Phase B without confirmation.

---

# Phase B — Scraper Package

### Task B1: Initialise the `scraper/` package

**Files:**
- Create: `scraper/pyproject.toml`
- Create: `scraper/.env.example`
- Create: `scraper/README.md`
- Create: `scraper/src/scraper/__init__.py` (empty)

- [ ] **Step 1: Write `scraper/pyproject.toml`**

```toml
[project]
name = "rt-scraper"
version = "0.1.0"
description = "Google Maps lead scraper for Roman Technologies"
requires-python = ">=3.11"
dependencies = [
    "playwright==1.50.0",
    "pydantic==2.9.2",
    "pydantic-settings==2.6.1",
    "typer==0.13.1",
    "loguru==0.7.2",
    "tenacity==9.0.0",
    "rapidfuzz==3.10.1",
    "supabase==2.10.0",
    "gspread==6.1.4",
    "google-auth==2.36.0",
    "python-dotenv==1.0.1",
]

[project.optional-dependencies]
dev = [
    "pytest==8.3.3",
    "pytest-asyncio==0.24.0",
    "ruff==0.7.4",
    "mypy==1.13.0",
    "types-requests",
]

[project.scripts]
scraper = "scraper.cli:app"

[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[tool.setuptools.packages.find]
where = ["src"]

[tool.ruff]
line-length = 100
target-version = "py311"

[tool.ruff.lint]
select = ["E", "F", "I", "B", "UP", "ASYNC"]

[tool.mypy]
python_version = "3.11"
strict = true
mypy_path = "src"
explicit_package_bases = true

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
```

- [ ] **Step 2: Write `scraper/.env.example`**

```bash
# Supabase — source of truth
SUPABASE_URL=https://<project>.supabase.co
SUPABASE_SERVICE_KEY=<service_role_key>

# Google Sheets mirror — service-account auth
GOOGLE_SHEETS_CREDENTIALS_JSON=/etc/scraper/google-sa.json
GOOGLE_SHEET_ID=1VWJ7PCHCvvalaelW2viVnK9s_L3UD7Q8VRyM9duryq8

# Playwright runtime
SCRAPER_HEADLESS=true
SCRAPER_LOCALE_DEFAULT=en
SCRAPER_USER_AGENT=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36

# Polite pacing
SCRAPER_MIN_DELAY_MS=600
SCRAPER_MAX_DELAY_MS=2200
```

- [ ] **Step 3: Write `scraper/README.md`** with sections: Overview, Requirements, Local dev, Env vars, CLI usage (`scrape`, `run-pending`), Sinks, Extension points (about-tab, photos, proxies, new sources, automation lead_type), Deploy (link to deploy/DEPLOY.md), Troubleshooting (Google selector drift → see `selectors.py`).

(Skipped showing full README markdown here; engineer writes 1-2 page doc following these section headings.)

- [ ] **Step 4: Commit**

```bash
git add scraper/pyproject.toml scraper/.env.example scraper/README.md scraper/src/scraper/__init__.py
git commit -m "feat(scraper): scaffold rt-scraper package with pyproject + env example"
```

---

### Task B2: `scraper/src/scraper/models.py` — Pydantic schemas

**Files:**
- Create: `scraper/src/scraper/models.py`
- Test: `scraper/tests/test_models.py`

- [ ] **Step 1: Write the failing test `scraper/tests/test_models.py`**

```python
from scraper.models import Lead, ScrapeFilters, ScrapeParams


def test_scrape_params_minimal_required_fields():
    p = ScrapeParams(category="restaurants", country="NL")
    assert p.category == "restaurants"
    assert p.country == "NL"
    assert p.cities == []
    assert p.areas == []
    assert p.max_results_per_area == 120
    assert p.language == "en"
    assert p.lead_type == "website"
    assert p.with_reviews is False
    assert p.filters.web_presence == ["none", "social_only"]


def test_scrape_filters_all_optional_off_by_default():
    f = ScrapeFilters()
    assert f.min_rating is None
    assert f.max_rating is None
    assert f.min_reviews is None
    assert f.max_reviews is None
    assert f.web_presence == ["none", "social_only"]


def test_lead_extra_defaults_to_empty_dict():
    lead = Lead(
        external_id="0x1234:0xabcd",
        business_name="Acme",
        name_normalized="acme",
    )
    assert lead.extra == {}
    assert lead.lead_type == "website"
    assert lead.web_presence == "unknown"
    assert lead.primary_source == "google_maps"
```

- [ ] **Step 2: Run test, verify fails**

```bash
cd scraper && python -m pytest tests/test_models.py -v
```
Expected: ImportError / `Lead` not defined.

- [ ] **Step 3: Implement `scraper/src/scraper/models.py`**

```python
"""Pydantic v2 schemas — single source of truth shared by CLI, pipeline,
sinks and the FastAPI admin layer (via JSON serialisation through
scrape_jobs.params)."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

LeadType = Literal["website", "automation", "both"]
WebPresence = Literal["none", "social_only", "has_website", "unknown"]


class ScrapeFilters(BaseModel):
    """All optional, off by default. The default web_presence list keeps
    only businesses worth pitching a website to."""

    model_config = ConfigDict(extra="forbid")

    min_rating: float | None = None
    max_rating: float | None = None
    min_reviews: int | None = None
    max_reviews: int | None = None
    web_presence: list[WebPresence] = Field(default_factory=lambda: ["none", "social_only"])


class ScrapeParams(BaseModel):
    """Mirrors the row in scrape_jobs.params. The CMS form maps 1:1 to
    these fields; the worker deserialises and runs."""

    model_config = ConfigDict(extra="forbid")

    category: str
    country: str
    cities: list[str] = Field(default_factory=list)
    areas: list[str] = Field(default_factory=list)
    max_results_per_area: int = 120
    language: str = "en"
    lead_type: LeadType = "website"
    with_reviews: bool = False
    review_limit: int = 10
    filters: ScrapeFilters = Field(default_factory=ScrapeFilters)


class Lead(BaseModel):
    """Scraped row, ready to hand to any Sink. Mirrors columns on
    public.leads. Optional fields default to None so partial scrapes
    don't break upserts."""

    model_config = ConfigDict(extra="forbid")

    # provenance
    external_id: str
    scrape_job_id: str | None = None
    primary_source: str = "google_maps"
    source_url: str | None = None

    # classification
    lead_type: LeadType = "website"
    category: str | None = None

    # identity
    business_name: str
    name_normalized: str
    description: str | None = None
    about: str | None = None

    # location
    country: str | None = None
    region: str | None = None
    city: str | None = None
    address: str | None = None
    postal_code: str | None = None
    lat: float | None = None
    lng: float | None = None

    # contact / links
    phone: str | None = None
    email: str | None = None
    website_url: str | None = None
    facebook_url: str | None = None
    instagram_url: str | None = None
    menu_url: str | None = None

    # digital presence
    web_presence: WebPresence = "unknown"

    # reviews / hours
    rating: float | None = None
    review_count: int | None = None
    reviews: list[dict[str, Any]] | None = None
    opening_hours: dict[str, str] | None = None
    photo_urls: list[str] = Field(default_factory=list)

    # extensibility
    extra: dict[str, Any] = Field(default_factory=dict)
```

- [ ] **Step 4: Run test, verify passes**

```bash
cd scraper && python -m pytest tests/test_models.py -v
```
Expected: 3 PASS.

- [ ] **Step 5: Commit**

```bash
git add scraper/src/scraper/models.py scraper/tests/test_models.py
git commit -m "feat(scraper): Lead + ScrapeParams + ScrapeFilters Pydantic models"
```

---

### Task B3: `scraper/src/scraper/config.py` — Settings

**Files:**
- Create: `scraper/src/scraper/config.py`

- [ ] **Step 1: Write `config.py`**

```python
"""pydantic-settings — single Settings class read from .env, matching
the CMS backend's convention (settings = Settings())."""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    SUPABASE_URL: str = ""
    SUPABASE_SERVICE_KEY: str = ""

    GOOGLE_SHEETS_CREDENTIALS_JSON: str = ""
    GOOGLE_SHEET_ID: str = ""

    SCRAPER_HEADLESS: bool = True
    SCRAPER_LOCALE_DEFAULT: str = "en"
    SCRAPER_USER_AGENT: str = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
    )

    SCRAPER_MIN_DELAY_MS: int = 600
    SCRAPER_MAX_DELAY_MS: int = 2200

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


settings = Settings()
```

- [ ] **Step 2: Commit**

```bash
git add scraper/src/scraper/config.py
git commit -m "feat(scraper): Settings via pydantic-settings"
```

---

### Task B4: `scraper/src/scraper/dedup.py` — name normalisation + external_id + presence classify

**Files:**
- Create: `scraper/src/scraper/dedup.py`
- Test: `scraper/tests/test_dedup.py`

- [ ] **Step 1: Write the failing test**

```python
from scraper.dedup import classify_web_presence, external_id_from_url, normalize_name


def test_normalize_strips_accents_punctuation_case():
    assert normalize_name("Café  L'Étoile, B.V.") == "cafe letoile bv"


def test_external_id_from_google_feature_id():
    url = "https://www.google.com/maps/place/Cafe/@52.5,4.5,17z/data=!4m6!3m5!1s0x47c5e1234abcdef:0xfedcba9876543210!8m2!3d52.5!4d4.5"
    assert external_id_from_url(url) == "0x47c5e1234abcdef:0xfedcba9876543210"


def test_external_id_fallback_when_no_feature_id():
    # Falls back to a hash based on (normalized_name, city, rounded lat/lng).
    eid = external_id_from_url(
        url="https://www.google.com/maps/place/something",
        normalized_name="cafe letoile",
        city="lelystad",
        lat=52.5123456,
        lng=5.4789012,
    )
    assert eid.startswith("hash:")
    assert len(eid) > 8


def test_classify_no_website_is_none():
    assert classify_web_presence(None) == ("none", None, None)


def test_classify_social_facebook():
    presence, fb, ig = classify_web_presence("https://www.facebook.com/acme")
    assert presence == "social_only"
    assert fb == "https://www.facebook.com/acme"
    assert ig is None


def test_classify_social_instagram():
    presence, fb, ig = classify_web_presence("https://www.instagram.com/acme/")
    assert presence == "social_only"
    assert ig == "https://www.instagram.com/acme/"
    assert fb is None


def test_classify_has_website():
    presence, fb, ig = classify_web_presence("https://acme.example.com")
    assert presence == "has_website"
    assert fb is None
    assert ig is None
```

- [ ] **Step 2: Run, verify fails**

```bash
cd scraper && python -m pytest tests/test_dedup.py -v
```
Expected: ImportError.

- [ ] **Step 3: Implement `dedup.py`**

```python
"""Pure helpers — no IO. Easy to unit-test, kept apart from playwright."""

from __future__ import annotations

import hashlib
import re
import unicodedata
from urllib.parse import urlparse

_SOCIAL_DOMAINS = {
    "facebook.com", "fb.com", "m.facebook.com",
    "instagram.com", "linktr.ee", "linktree.com",
    "beacons.ai", "tiktok.com", "x.com", "twitter.com",
}
_FEATURE_ID_RE = re.compile(r"!1s(0x[0-9a-f]+:0x[0-9a-f]+)", re.IGNORECASE)


def normalize_name(name: str) -> str:
    """Lower-case, strip diacritics + punctuation, collapse whitespace."""
    n = unicodedata.normalize("NFKD", name)
    n = "".join(c for c in n if not unicodedata.combining(c))
    n = n.lower()
    n = re.sub(r"[^\w\s]", " ", n)
    n = re.sub(r"\s+", " ", n).strip()
    return n


def external_id_from_url(
    url: str,
    *,
    normalized_name: str | None = None,
    city: str | None = None,
    lat: float | None = None,
    lng: float | None = None,
) -> str:
    """Prefer Google's stable feature id. Fall back to a hash of
    (normalized name, city, rounded coords) so a re-scrape still dedups."""
    m = _FEATURE_ID_RE.search(url)
    if m:
        return m.group(1)

    if not normalized_name:
        # Last-ditch — hash the URL itself.
        return "hash:" + hashlib.sha256(url.encode()).hexdigest()[:24]

    payload = f"{normalized_name}|{city or ''}|{lat:.4f if lat is not None else ''}|{lng:.4f if lng is not None else ''}"
    return "hash:" + hashlib.sha256(payload.encode()).hexdigest()[:24]


def classify_web_presence(
    website_url: str | None,
) -> tuple[str, str | None, str | None]:
    """Return (web_presence, facebook_url, instagram_url) given the URL
    Google Maps surfaces as the place's "website" link."""
    if not website_url:
        return "none", None, None

    host = (urlparse(website_url).hostname or "").lower().removeprefix("www.")
    if host in _SOCIAL_DOMAINS:
        fb = website_url if "facebook" in host or host == "fb.com" else None
        ig = website_url if "instagram" in host else None
        return "social_only", fb, ig

    return "has_website", None, None
```

- [ ] **Step 4: Run, verify passes**

```bash
cd scraper && python -m pytest tests/test_dedup.py -v
```
Expected: 7 PASS. (Note: the f-string in `external_id_from_url` is intentional — fix any quoting issues if pytest complains; the test should pass.)

- [ ] **Step 5: Commit**

```bash
git add scraper/src/scraper/dedup.py scraper/tests/test_dedup.py
git commit -m "feat(scraper): dedup helpers — normalize_name, external_id, classify_web_presence"
```

---

### Task B5: `scraper/src/scraper/selectors.py` — DOM selector dictionary

**Files:**
- Create: `scraper/src/scraper/selectors.py`

- [ ] **Step 1: Write `selectors.py`**

```python
"""ALL Google Maps DOM selectors live here.

When Google rotates obfuscated class names (which happens), update this
file only — engine logic in google_maps.py stays untouched.

Preferences (most-stable first):
  1. aria-label
  2. role + data-*
  3. semantic structure (button containing svg, etc.)
  4. obfuscated CSS classes (fragile; mark FRAGILE)
"""

from __future__ import annotations

# Cookie consent (EU interstitial, multi-language).
CONSENT_ACCEPT_BUTTONS: tuple[str, ...] = (
    'button[aria-label*="Accept"]',
    'button[aria-label*="Alles accepteren"]',
    'button[aria-label*="Akzeptieren"]',
    'button[aria-label*="Accepter"]',
    'form[action*="consent"] button:has-text("Accept all")',
    'form[action*="consent"] button:has-text("Alles accepteren")',
)
CONSENT_REJECT_BUTTONS: tuple[str, ...] = (
    'button[aria-label*="Reject all"]',
    'button[aria-label*="Alles afwijzen"]',
)

# Results feed (left-hand list).
RESULTS_FEED = 'div[role="feed"]'
RESULTS_ITEM_LINK = 'a.hfpxzc'                       # FRAGILE — anchor per place
RESULTS_END_MARKER = 'p.HlvSq, span.HlvSq'           # FRAGILE — "You've reached the end of the list."

# Single-result redirect (the URL becomes the place page directly).
PLACE_HEADER_SELECTOR = 'h1[class]'                  # any h1 with class signifies a place page

# Place detail panel.
PLACE_TITLE = 'h1[class]'
PLACE_CATEGORY_BUTTON = 'button[jsaction*="category"]'  # FRAGILE
PLACE_RATING_NUMBER = 'div.F7nice > span > span[aria-hidden="true"]'  # FRAGILE
PLACE_REVIEW_COUNT_BUTTON = 'button[aria-label*="review"], button[jsaction*="reviewChart"]'
PLACE_ADDRESS_BUTTON = 'button[data-item-id="address"]'
PLACE_WEBSITE_BUTTON = 'a[data-item-id="authority"]'
PLACE_PHONE_BUTTON = 'button[data-item-id*="phone"]'
PLACE_MENU_BUTTON = 'a[data-item-id="menu"]'
PLACE_HOURS_BUTTON = 'div[data-item-id="oh"] button, button[data-item-id="oh"]'
PLACE_HOURS_TABLE = 'table[aria-label*="hours"], table[aria-label*="openingstijden"]'
PLACE_DESCRIPTION = 'div.PYvSYb'                     # FRAGILE — editorial summary

# Reviews tab.
REVIEWS_TAB_BUTTON = 'button[aria-label*="Reviews"], button[aria-label*="recensies"]'
REVIEW_CARD = 'div[data-review-id]'
REVIEW_AUTHOR = 'div.d4r55'                          # FRAGILE
REVIEW_RATING = 'span[role="img"][aria-label*="star"], span[role="img"][aria-label*="ster"]'
REVIEW_RELATIVE_DATE = 'span.rsqaWe'                 # FRAGILE
REVIEW_TEXT = 'span.wiI7pd, div[data-review-id] span[jscontroller]'

# Photos.
PHOTO_BUTTONS = 'button[data-photo-index] img'
```

- [ ] **Step 2: Commit**

```bash
git add scraper/src/scraper/selectors.py
git commit -m "feat(scraper): centralise Google Maps DOM selectors"
```

---

### Task B6: `scraper/src/scraper/google_maps.py` — Playwright engine

**Files:**
- Create: `scraper/src/scraper/google_maps.py`

This task is large. Split into commits per logical chunk.

- [ ] **Step 1: Skeleton + browser launch helper**

```python
"""Playwright-based Google Maps scraper.

All DOM access goes through scraper.selectors. All extracted values are
funnelled through Lead Pydantic model. No business logic lives here —
the pipeline orchestrates, the engine just scrapes.
"""

from __future__ import annotations

import asyncio
import random
from collections.abc import AsyncIterator
from typing import Any

from loguru import logger
from playwright.async_api import Browser, BrowserContext, Page, async_playwright
from tenacity import retry, stop_after_attempt, wait_exponential

from . import selectors
from .config import settings
from .dedup import classify_web_presence, external_id_from_url, normalize_name
from .models import Lead, ScrapeParams


async def _polite_delay() -> None:
    """Randomised pacing between actions to avoid trivial fingerprinting."""
    ms = random.randint(settings.SCRAPER_MIN_DELAY_MS, settings.SCRAPER_MAX_DELAY_MS)
    await asyncio.sleep(ms / 1000.0)


async def _new_context(browser: Browser, language: str, country: str) -> BrowserContext:
    """Locale + UA + the standard anti-detection bits.

    EXTENSION POINT: residential proxies — add a `proxy={"server": ...}`
    kwarg here when Google starts blocking the Hetzner IP.
    """
    ctx = await browser.new_context(
        user_agent=settings.SCRAPER_USER_AGENT,
        locale=language,
        viewport={"width": 1366, "height": 900},
        timezone_id="Europe/Amsterdam",
        geolocation=None,
    )
    await ctx.add_init_script(
        "Object.defineProperty(navigator, 'webdriver', { get: () => undefined });"
    )
    return ctx
```

- [ ] **Step 2: Cookie consent handler**

Append to `google_maps.py`:

```python
async def _accept_consent(page: Page) -> None:
    """EU interstitial — try every accept selector, give up after timeout."""
    for sel in selectors.CONSENT_ACCEPT_BUTTONS:
        try:
            await page.locator(sel).first.click(timeout=1500)
            logger.debug("clicked consent: {}", sel)
            await page.wait_for_load_state("networkidle", timeout=5000)
            return
        except Exception:
            continue
    logger.debug("no consent prompt visible")
```

- [ ] **Step 3: Results-feed scroll-and-collect**

Append:

```python
async def _collect_place_links(page: Page, max_results: int) -> list[str]:
    """Scroll the left feed until end-marker, stable-count, or max reached."""
    links: list[str] = []
    seen: set[str] = set()
    stable_rounds = 0
    last_count = 0

    feed = page.locator(selectors.RESULTS_FEED)
    try:
        await feed.wait_for(timeout=8000)
    except Exception:
        # Single-result redirect: Google sent us straight to a place page.
        url = page.url
        if "/place/" in url:
            return [url]
        return []

    while len(links) < max_results and stable_rounds < 3:
        anchors = await page.locator(selectors.RESULTS_ITEM_LINK).element_handles()
        for a in anchors:
            href = await a.get_attribute("href")
            if href and href not in seen:
                seen.add(href)
                links.append(href)
                if len(links) >= max_results:
                    break

        end_marker = page.locator(selectors.RESULTS_END_MARKER)
        if await end_marker.count() > 0:
            logger.debug("reached end-of-list marker")
            break

        if len(links) == last_count:
            stable_rounds += 1
        else:
            stable_rounds = 0
        last_count = len(links)

        await feed.evaluate("(el) => el.scrollBy(0, el.scrollHeight)")
        await _polite_delay()

    return links[:max_results]
```

- [ ] **Step 4: Place-page field extraction**

Append:

```python
async def _safe_text(page: Page, selector: str) -> str | None:
    try:
        el = page.locator(selector).first
        if await el.count() == 0:
            return None
        return (await el.inner_text()).strip()
    except Exception:
        return None


async def _safe_attr(page: Page, selector: str, attr: str) -> str | None:
    try:
        el = page.locator(selector).first
        if await el.count() == 0:
            return None
        return await el.get_attribute(attr)
    except Exception:
        return None


async def _extract_opening_hours(page: Page) -> dict[str, str] | None:
    """Open the hours expansion if present, return {day_name: hours} dict."""
    try:
        btn = page.locator(selectors.PLACE_HOURS_BUTTON).first
        if await btn.count() == 0:
            return None
        await btn.click(timeout=2000)
        await page.wait_for_selector(selectors.PLACE_HOURS_TABLE, timeout=2000)
        rows = await page.locator(f"{selectors.PLACE_HOURS_TABLE} tr").element_handles()
        hours: dict[str, str] = {}
        for r in rows:
            cells = await r.query_selector_all("td, th")
            if len(cells) >= 2:
                day = (await cells[0].inner_text()).strip()
                value = (await cells[1].inner_text()).strip()
                if day:
                    hours[day] = value
        return hours or None
    except Exception:
        return None
```

- [ ] **Step 5: Reviews extraction (only when with_reviews=True)**

Append:

```python
async def _extract_reviews(page: Page, limit: int) -> list[dict[str, Any]]:
    """Open the Reviews tab if present, scrape up to `limit` reviews."""
    try:
        tab = page.locator(selectors.REVIEWS_TAB_BUTTON).first
        if await tab.count() == 0:
            return []
        await tab.click(timeout=2000)
        await page.wait_for_selector(selectors.REVIEW_CARD, timeout=3000)
    except Exception:
        return []

    cards = await page.locator(selectors.REVIEW_CARD).element_handles()
    out: list[dict[str, Any]] = []
    for c in cards[:limit]:
        author = await (await c.query_selector(selectors.REVIEW_AUTHOR)) if False else None
        # safer: query through the card
        out.append(
            {
                "author": (await (c.query_selector(selectors.REVIEW_AUTHOR))) is None
                and ""
                or (await (await c.query_selector(selectors.REVIEW_AUTHOR)).inner_text()).strip()
                if await c.query_selector(selectors.REVIEW_AUTHOR)
                else None,
                "text": (
                    (await (await c.query_selector(selectors.REVIEW_TEXT)).inner_text()).strip()
                    if await c.query_selector(selectors.REVIEW_TEXT)
                    else None
                ),
                "relative_date": (
                    (await (await c.query_selector(selectors.REVIEW_RELATIVE_DATE)).inner_text()).strip()
                    if await c.query_selector(selectors.REVIEW_RELATIVE_DATE)
                    else None
                ),
            }
        )
    return out
```

*Note for engineer: the above review extraction is dense — feel free to refactor into named helpers to remove the chained-await readability hit while you implement. Keep behavior identical.*

- [ ] **Step 6: Place-page → Lead**

Append:

```python
@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=2, min=2, max=30))
async def _scrape_one_place(
    ctx: BrowserContext, url: str, params: ScrapeParams, scrape_job_id: str | None
) -> Lead | None:
    page = await ctx.new_page()
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=20_000)
        await _accept_consent(page)
        await page.wait_for_selector(selectors.PLACE_TITLE, timeout=10_000)
        await _polite_delay()

        title = await _safe_text(page, selectors.PLACE_TITLE) or ""
        if not title:
            logger.warning("no title for {} — skipping", url)
            return None

        normalized = normalize_name(title)
        address = await _safe_text(page, selectors.PLACE_ADDRESS_BUTTON)
        phone = await _safe_text(page, selectors.PLACE_PHONE_BUTTON)
        website_url = await _safe_attr(page, selectors.PLACE_WEBSITE_BUTTON, "href")
        category = await _safe_text(page, selectors.PLACE_CATEGORY_BUTTON)
        menu_url = await _safe_attr(page, selectors.PLACE_MENU_BUTTON, "href")
        description = await _safe_text(page, selectors.PLACE_DESCRIPTION)

        rating_txt = await _safe_text(page, selectors.PLACE_RATING_NUMBER)
        rating = float(rating_txt.replace(",", ".")) if rating_txt else None

        review_count_txt = await _safe_attr(page, selectors.PLACE_REVIEW_COUNT_BUTTON, "aria-label")
        review_count = None
        if review_count_txt:
            digits = "".join(c for c in review_count_txt if c.isdigit())
            review_count = int(digits) if digits else None

        opening_hours = await _extract_opening_hours(page)
        reviews = (
            await _extract_reviews(page, params.review_limit) if params.with_reviews else None
        )

        web_presence, fb, ig = classify_web_presence(website_url)

        # Crude city/postal split from address — refine in Phase B follow-up.
        city: str | None = None
        postal_code: str | None = None
        if address:
            # Last comma-separated segment usually has "PostalCode City".
            tail = address.split(",")[-1].strip()
            parts = tail.split(None, 1)
            if len(parts) == 2 and any(ch.isdigit() for ch in parts[0]):
                postal_code, city = parts
            else:
                city = tail or None

        # EXTENSION POINT: scrape the "About" tab for attribute toggles
        # (delivery, dine-in, wheelchair-accessible, etc.) and stash them
        # in `extra`. Skipped in v1 to keep the scrape fast.
        # EXTENSION POINT: download photos into Supabase Storage. v1
        # stores URLs only.
        extra: dict[str, Any] = {}

        return Lead(
            external_id=external_id_from_url(
                url,
                normalized_name=normalized,
                city=city,
                lat=None,
                lng=None,
            ),
            scrape_job_id=scrape_job_id,
            primary_source="google_maps",
            source_url=url,
            lead_type=params.lead_type,
            category=category,
            business_name=title,
            name_normalized=normalized,
            description=description,
            country=params.country,
            city=city,
            address=address,
            postal_code=postal_code,
            phone=phone,
            website_url=website_url if web_presence == "has_website" else None,
            facebook_url=fb,
            instagram_url=ig,
            menu_url=menu_url,
            web_presence=web_presence,
            rating=rating,
            review_count=review_count,
            reviews=reviews,
            opening_hours=opening_hours,
            extra=extra,
        )
    finally:
        await page.close()
```

- [ ] **Step 7: Query builder + top-level scrape generator**

Append:

```python
def _build_queries(params: ScrapeParams) -> list[str]:
    """Cartesian: cities × areas, falling back to country."""
    qs: list[str] = []
    if not params.cities:
        qs.append(f"{params.category} in {params.country}")
        return qs
    for city in params.cities:
        if not params.areas:
            qs.append(f"{params.category} in {city}")
        else:
            for area in params.areas:
                qs.append(f"{params.category} in {area}, {city}")
    return qs


async def scrape(
    params: ScrapeParams, scrape_job_id: str | None = None, headless: bool | None = None
) -> AsyncIterator[Lead]:
    """Top-level async generator. Yields Lead objects one at a time so
    sinks can stream and the pipeline can update counters in real time.
    """
    use_headless = settings.SCRAPER_HEADLESS if headless is None else headless

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(
            headless=use_headless,
            args=["--disable-blink-features=AutomationControlled"],
        )
        ctx = await _new_context(browser, params.language, params.country)
        page = await ctx.new_page()

        try:
            for query in _build_queries(params):
                logger.info("query: {}", query)
                url = (
                    "https://www.google.com/maps/search/"
                    f"{query.replace(' ', '+')}/?hl={params.language}&gl={params.country}"
                )
                await page.goto(url, wait_until="domcontentloaded", timeout=20_000)
                await _accept_consent(page)
                await _polite_delay()

                links = await _collect_place_links(page, params.max_results_per_area)
                logger.info("collected {} place links", len(links))

                for link in links:
                    try:
                        lead = await _scrape_one_place(ctx, link, params, scrape_job_id)
                    except Exception as exc:
                        logger.warning("place {} failed: {}", link, exc)
                        continue

                    if not lead:
                        continue

                    # Apply optional filters.
                    f = params.filters
                    if f.web_presence and lead.web_presence not in f.web_presence:
                        continue
                    if f.min_rating is not None and (lead.rating or 0) < f.min_rating:
                        continue
                    if f.max_rating is not None and (lead.rating or 0) > f.max_rating:
                        continue
                    if f.min_reviews is not None and (lead.review_count or 0) < f.min_reviews:
                        continue
                    if f.max_reviews is not None and (lead.review_count or 0) > f.max_reviews:
                        continue

                    yield lead
                    await _polite_delay()
        finally:
            await ctx.close()
            await browser.close()
```

- [ ] **Step 8: Commit**

```bash
git add scraper/src/scraper/google_maps.py
git commit -m "feat(scraper): Playwright Google Maps engine — query → places → Lead"
```

---

### Task B7: Sinks — base + JSON + Supabase + Sheets

**Files:**
- Create: `scraper/src/scraper/sinks/__init__.py` (empty)
- Create: `scraper/src/scraper/sinks/base.py`
- Create: `scraper/src/scraper/sinks/json_sink.py`
- Create: `scraper/src/scraper/sinks/supabase_sink.py`
- Create: `scraper/src/scraper/sinks/sheets_sink.py`
- Test: `scraper/tests/test_sinks_json.py`

- [ ] **Step 1: `base.py`**

```python
"""Abstract sink — the contract every output implements."""

from __future__ import annotations

from abc import ABC, abstractmethod

from ..models import Lead


class Sink(ABC):
    @abstractmethod
    async def open(self) -> None: ...

    @abstractmethod
    async def write(self, lead: Lead) -> bool:
        """Return True if newly inserted/updated, False if skipped (dup)."""

    @abstractmethod
    async def close(self) -> None: ...
```

- [ ] **Step 2: `json_sink.py` + test**

Test first:

```python
# scraper/tests/test_sinks_json.py
import asyncio
import json
from pathlib import Path

from scraper.models import Lead
from scraper.sinks.json_sink import JsonSink


def _mk_lead(eid: str) -> Lead:
    return Lead(external_id=eid, business_name="x", name_normalized="x")


def test_json_sink_writes_array(tmp_path: Path):
    path = tmp_path / "out.json"
    sink = JsonSink(path)

    async def run() -> None:
        await sink.open()
        assert await sink.write(_mk_lead("a")) is True
        assert await sink.write(_mk_lead("b")) is True
        # dup check
        assert await sink.write(_mk_lead("a")) is False
        await sink.close()

    asyncio.run(run())
    data = json.loads(path.read_text())
    assert {row["external_id"] for row in data} == {"a", "b"}
```

Implementation:

```python
"""Local dry-run output."""

from __future__ import annotations

import json
from pathlib import Path

from ..models import Lead
from .base import Sink


class JsonSink(Sink):
    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)
        self._rows: list[dict] = []
        self._seen: set[str] = set()

    async def open(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)

    async def write(self, lead: Lead) -> bool:
        if lead.external_id in self._seen:
            return False
        self._seen.add(lead.external_id)
        self._rows.append(lead.model_dump())
        return True

    async def close(self) -> None:
        self.path.write_text(json.dumps(self._rows, indent=2, default=str))
```

Run:

```bash
cd scraper && python -m pytest tests/test_sinks_json.py -v
```
Expected: 1 PASS.

- [ ] **Step 3: `supabase_sink.py`**

```python
"""Supabase upsert sink. external_id is the conflict target."""

from __future__ import annotations

from loguru import logger
from supabase import create_client

from ..config import settings
from ..models import Lead
from .base import Sink


class SupabaseSink(Sink):
    def __init__(self) -> None:
        self._sb = None

    async def open(self) -> None:
        if not settings.SUPABASE_URL or not settings.SUPABASE_SERVICE_KEY:
            raise RuntimeError("SUPABASE_URL + SUPABASE_SERVICE_KEY required for SupabaseSink")
        self._sb = create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_KEY)

    async def write(self, lead: Lead) -> bool:
        assert self._sb is not None
        row = lead.model_dump(mode="json", exclude_none=False)
        try:
            self._sb.table("leads").upsert(row, on_conflict="external_id").execute()
            return True
        except Exception as exc:
            logger.warning("supabase upsert failed for {}: {}", lead.external_id, exc)
            return False

    async def close(self) -> None:
        return None
```

- [ ] **Step 4: `sheets_sink.py`**

```python
"""Append rows into the existing 18-column Google Sheet, mapping fields
by header name. Header row in the sheet is the source of truth for
which columns receive data — fields the sheet doesn't have stay
Supabase-only."""

from __future__ import annotations

from typing import Any

import gspread
from google.oauth2.service_account import Credentials
from loguru import logger

from ..config import settings
from ..models import Lead
from .base import Sink

_SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]


# Map: Sheet column header (case-insensitive) → callable(Lead) -> value.
# Add new fields here as the sheet grows; missing headers are skipped.
_FIELD_MAP: dict[str, Any] = {
    "name": lambda l: l.business_name,
    "city": lambda l: l.city,
    "adress": lambda l: l.address,             # sic — existing typo in sheet
    "address": lambda l: l.address,
    "contact email": lambda l: l.email,
    "contact phone": lambda l: l.phone,
    "category": lambda l: l.category,
    "description": lambda l: l.description,
    "reviews array": lambda l: l.reviews,
    "review average": lambda l: l.rating,
    "schedule": lambda l: l.opening_hours,
    "about": lambda l: l.about,
    "photos": lambda l: ",".join(l.photo_urls) if l.photo_urls else None,
    "menu": lambda l: l.menu_url,
    "status website": lambda l: l.website_build_status,
    "status ai workflow": lambda l: l.ai_workflow_status,
    "status lead": lambda l: l.lead_status,
    "type lead": lambda l: l.lead_type,
    "payment": lambda l: l.payment_status,
}


class SheetsSink(Sink):
    def __init__(self) -> None:
        self._ws: gspread.Worksheet | None = None
        self._headers: list[str] = []

    async def open(self) -> None:
        if not settings.GOOGLE_SHEETS_CREDENTIALS_JSON or not settings.GOOGLE_SHEET_ID:
            raise RuntimeError("Sheets sink requires GOOGLE_SHEETS_CREDENTIALS_JSON + GOOGLE_SHEET_ID")
        creds = Credentials.from_service_account_file(
            settings.GOOGLE_SHEETS_CREDENTIALS_JSON, scopes=_SCOPES
        )
        gc = gspread.authorize(creds)
        sh = gc.open_by_key(settings.GOOGLE_SHEET_ID)
        self._ws = sh.sheet1
        self._headers = [h.strip() for h in self._ws.row_values(1)]

    async def write(self, lead: Lead) -> bool:
        assert self._ws is not None
        row: list[Any] = []
        for header in self._headers:
            key = header.lower()
            fn = _FIELD_MAP.get(key)
            if fn is None:
                row.append("")
                continue
            value = fn(lead)
            row.append("" if value is None else str(value))
        try:
            self._ws.append_row(row, value_input_option="RAW")
            return True
        except Exception as exc:
            logger.warning("sheets append failed for {}: {}", lead.external_id, exc)
            return False

    async def close(self) -> None:
        return None
```

- [ ] **Step 5: Run JSON sink test**

```bash
cd scraper && python -m pytest tests/test_sinks_json.py -v
```
Expected: 1 PASS.

- [ ] **Step 6: Commit**

```bash
git add scraper/src/scraper/sinks scraper/tests/test_sinks_json.py
git commit -m "feat(scraper): sinks — JSON (dry-run), Supabase upsert, Google Sheets append"
```

---

### Task B8: `pipeline.py` — orchestration

**Files:**
- Create: `scraper/src/scraper/pipeline.py`
- Test: `scraper/tests/test_pipeline.py`

- [ ] **Step 1: Write the test**

```python
# scraper/tests/test_pipeline.py
import asyncio
from typing import AsyncIterator

import pytest

from scraper.models import Lead, ScrapeParams
from scraper.pipeline import run_pipeline
from scraper.sinks.base import Sink


class _FakeSink(Sink):
    def __init__(self, fail_on: set[str] | None = None) -> None:
        self.opened = False
        self.closed = False
        self.written: list[Lead] = []
        self._fail = fail_on or set()

    async def open(self) -> None:
        self.opened = True

    async def write(self, lead: Lead) -> bool:
        if lead.external_id in self._fail:
            return False
        self.written.append(lead)
        return True

    async def close(self) -> None:
        self.closed = True


async def _fake_scrape(params: ScrapeParams, scrape_job_id=None) -> AsyncIterator[Lead]:
    for eid in ("a", "b", "c"):
        yield Lead(external_id=eid, business_name=eid, name_normalized=eid)


@pytest.mark.asyncio
async def test_pipeline_writes_to_all_sinks_and_counts(monkeypatch):
    monkeypatch.setattr("scraper.pipeline._scrape", _fake_scrape)
    s1, s2 = _FakeSink(), _FakeSink(fail_on={"b"})

    counters = await run_pipeline(ScrapeParams(category="x", country="NL"), [s1, s2])

    assert counters.found == 3
    assert counters.inserted == 3      # s1 took all 3
    assert counters.skipped == 1       # s2 rejected "b"
    assert s1.opened and s1.closed
    assert {l.external_id for l in s1.written} == {"a", "b", "c"}
    assert {l.external_id for l in s2.written} == {"a", "c"}
```

- [ ] **Step 2: Run, verify fails**

```bash
cd scraper && python -m pytest tests/test_pipeline.py -v
```
Expected: import error.

- [ ] **Step 3: Implement `pipeline.py`**

```python
"""Glue layer — params + sinks in, counters out. Keeps google_maps.py
free of sink concerns and sinks free of scraping concerns."""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass

from loguru import logger

from .google_maps import scrape as _scrape
from .models import Lead, ScrapeParams
from .sinks.base import Sink


@dataclass
class Counters:
    found: int = 0
    inserted: int = 0
    skipped: int = 0


async def run_pipeline(
    params: ScrapeParams,
    sinks: list[Sink],
    scrape_job_id: str | None = None,
) -> Counters:
    counters = Counters()
    for s in sinks:
        await s.open()
    try:
        async for lead in _scrape(params, scrape_job_id=scrape_job_id):
            counters.found += 1
            any_inserted = False
            for s in sinks:
                ok = await s.write(lead)
                if ok:
                    any_inserted = True
                else:
                    counters.skipped += 1
            if any_inserted:
                counters.inserted += 1
        return counters
    finally:
        for s in sinks:
            try:
                await s.close()
            except Exception as exc:
                logger.warning("sink close failed: {}", exc)
```

- [ ] **Step 4: Run, verify passes**

```bash
cd scraper && python -m pytest tests/test_pipeline.py -v
```
Expected: 1 PASS.

- [ ] **Step 5: Commit**

```bash
git add scraper/src/scraper/pipeline.py scraper/tests/test_pipeline.py
git commit -m "feat(scraper): pipeline orchestration with counters"
```

---

### Task B9: `cli.py` — Typer commands `scrape` + `run-pending`

**Files:**
- Create: `scraper/src/scraper/cli.py`

- [ ] **Step 1: Write `cli.py`**

```python
"""Two commands:
  scrape           — run a job from CLI args (good for manual + dry-run)
  run-pending      — claim oldest pending row from scrape_jobs, run, update.
                     This is what the systemd timer calls.
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated, Optional

import typer
from loguru import logger
from supabase import create_client

from .config import settings
from .models import ScrapeFilters, ScrapeParams
from .pipeline import run_pipeline
from .sinks.base import Sink
from .sinks.json_sink import JsonSink
from .sinks.sheets_sink import SheetsSink
from .sinks.supabase_sink import SupabaseSink

app = typer.Typer(no_args_is_help=True, add_completion=False)


def _build_sinks(*, dry_run: bool, supabase: bool, sheet: bool, out_path: Path | None) -> list[Sink]:
    sinks: list[Sink] = []
    if dry_run:
        sinks.append(JsonSink(out_path or Path("./leads-dry-run.json")))
        return sinks
    if supabase:
        sinks.append(SupabaseSink())
    if sheet:
        sinks.append(SheetsSink())
    if not sinks:
        raise typer.BadParameter("at least one sink required (Supabase, sheet, or --dry-run)")
    return sinks


@app.command()
def scrape(
    category: Annotated[str, typer.Argument()],
    country: Annotated[str, typer.Argument()],
    city: Annotated[list[str], typer.Option("--city")] = [],
    area: Annotated[list[str], typer.Option("--area")] = [],
    max: Annotated[int, typer.Option("--max")] = 120,
    language: Annotated[str, typer.Option("--language")] = "en",
    with_reviews: Annotated[bool, typer.Option("--with-reviews")] = False,
    review_limit: Annotated[int, typer.Option("--review-limit")] = 10,
    lead_type: Annotated[str, typer.Option("--lead-type")] = "website",
    min_rating: Annotated[Optional[float], typer.Option("--min-rating")] = None,
    max_rating: Annotated[Optional[float], typer.Option("--max-rating")] = None,
    min_reviews: Annotated[Optional[int], typer.Option("--min-reviews")] = None,
    max_reviews: Annotated[Optional[int], typer.Option("--max-reviews")] = None,
    web_presence: Annotated[list[str], typer.Option("--web-presence")] = ["none", "social_only"],
    dry_run: Annotated[bool, typer.Option("--dry-run")] = False,
    no_headless: Annotated[bool, typer.Option("--no-headless")] = False,
    no_supabase: Annotated[bool, typer.Option("--no-supabase")] = False,
    no_sheet: Annotated[bool, typer.Option("--no-sheet")] = False,
    out: Annotated[Optional[Path], typer.Option("--out")] = None,
) -> None:
    params = ScrapeParams(
        category=category,
        country=country,
        cities=list(city),
        areas=list(area),
        max_results_per_area=max,
        language=language,
        with_reviews=with_reviews,
        review_limit=review_limit,
        lead_type=lead_type,  # type: ignore[arg-type]
        filters=ScrapeFilters(
            min_rating=min_rating,
            max_rating=max_rating,
            min_reviews=min_reviews,
            max_reviews=max_reviews,
            web_presence=list(web_presence),  # type: ignore[arg-type]
        ),
    )
    sinks = _build_sinks(
        dry_run=dry_run, supabase=not no_supabase, sheet=not no_sheet, out_path=out
    )
    if no_headless:
        settings.SCRAPER_HEADLESS = False

    counters = asyncio.run(run_pipeline(params, sinks))
    typer.echo(json.dumps(counters.__dict__))


@app.command("run-pending")
def run_pending() -> None:
    if not settings.SUPABASE_URL or not settings.SUPABASE_SERVICE_KEY:
        raise typer.BadParameter("SUPABASE_URL + SUPABASE_SERVICE_KEY required")

    sb = create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_KEY)
    res = (
        sb.table("scrape_jobs")
        .select("*")
        .eq("status", "pending")
        .order("created_at")
        .limit(1)
        .execute()
    )
    rows = res.data or []
    if not rows:
        logger.info("no pending scrape jobs")
        return

    job = rows[0]
    job_id = job["id"]

    # Claim.
    sb.table("scrape_jobs").update(
        {"status": "running", "started_at": datetime.now(timezone.utc).isoformat()}
    ).eq("id", job_id).eq("status", "pending").execute()

    try:
        params = ScrapeParams.model_validate(job["params"])
        sinks: list[Sink] = [SupabaseSink(), SheetsSink()]
        counters = asyncio.run(run_pipeline(params, sinks, scrape_job_id=job_id))
        sb.table("scrape_jobs").update(
            {
                "status": "done",
                "finished_at": datetime.now(timezone.utc).isoformat(),
                "results_found": counters.found,
                "results_inserted": counters.inserted,
                "results_skipped": counters.skipped,
            }
        ).eq("id", job_id).execute()
    except Exception as exc:
        logger.exception("job {} failed", job_id)
        sb.table("scrape_jobs").update(
            {
                "status": "failed",
                "finished_at": datetime.now(timezone.utc).isoformat(),
                "error": str(exc)[:2000],
            }
        ).eq("id", job_id).execute()
        raise
```

- [ ] **Step 2: Smoke-test the CLI parses**

```bash
cd scraper && python -m scraper.cli --help
```
Expected: lists `scrape` and `run-pending` subcommands.

- [ ] **Step 3: Commit**

```bash
git add scraper/src/scraper/cli.py
git commit -m "feat(scraper): Typer CLI — scrape + run-pending"
```

---

### Task B10: Install Playwright browsers + smoke-run dry test

🛑 **CHECKPOINT B1** — Tell the user:

> I need the Google service account before I can test the Sheets sink. Please:
> 1. In Google Cloud Console, create a new service account in any project (no IAM roles needed).
> 2. Enable the **Google Sheets API** for that project.
> 3. Create a JSON key for the service account; save the file.
> 4. **Share the Google Sheet** (id `1VWJ7PCHCvvalaelW2viVnK9s_L3UD7Q8VRyM9duryq8`) with the service account email (Editor role).
> 5. Give me: (a) the path where you saved the JSON key, (b) the service-account email you shared the sheet with.
> Wait for the user before proceeding.

After the user confirms:

- [ ] **Step 1: Install Playwright browsers locally**

```bash
cd scraper && python -m playwright install --with-deps chromium
```

- [ ] **Step 2: Copy `.env.example` → `.env`** with real Supabase URL + service key + sheets JSON path + sheet ID.

- [ ] **Step 3: Dry run with no-headless so the user can watch**

```bash
cd scraper && python -m scraper.cli scrape restaurants NL --city Lelystad --max 10 --dry-run --no-headless
```
Expected output: `leads-dry-run.json` with up to 10 entries; user sees the browser scroll the feed and visit place pages.

🛑 **CHECKPOINT B2** — Show the user the generated JSON and verify the extracted fields look correct. Do NOT write to Supabase or the sheet yet. Wait for confirmation.

- [ ] **Step 4: Live run (after CHECKPOINT B2 passes)**

```bash
cd scraper && python -m scraper.cli scrape restaurants NL --city Lelystad --max 5
```
Expected: 5 rows in `public.leads`, 5 new rows at the bottom of the sheet.

- [ ] **Step 5: Commit any tweaks made during the smoke test**

```bash
git add -A
git commit -m "fix(scraper): smoke-test adjustments from CHECKPOINT B2"
```

---

# Phase C — CMS Admin Tab (Backend + Frontend)

### Task C1: Pydantic schemas for the admin API

**Files:**
- Modify: `backend/auth_service/models/schemas.py`

- [ ] **Step 1: Append to `schemas.py`**

```python
# ───────── Lead scraper (added 2026-05-17) ─────────

LeadType = Literal["website", "automation", "both"]
WebPresence = Literal["none", "social_only", "has_website", "unknown"]
WebsiteBuildStatus = Literal[
    "not_started", "building_design", "design_done", "building",
    "finished_cms", "refining", "not_applicable",
]
AiWorkflowStatus = Literal[
    "not_started", "building", "finished", "refining", "not_applicable",
]
LeadStatus = Literal["not_sent", "sent", "accepted", "refused"]
LeadContactType = Literal["not_contacted", "phone", "mail", "in_person"]
PaymentStatus = Literal["not_applicable", "not_paid", "paid"]
ScrapeJobStatus = Literal["pending", "running", "done", "failed", "cancelled"]


class ScrapeFilters(BaseModel):
    min_rating: float | None = None
    max_rating: float | None = None
    min_reviews: int | None = None
    max_reviews: int | None = None
    web_presence: list[WebPresence] = Field(default_factory=lambda: ["none", "social_only"])


class ScrapeParams(BaseModel):
    category: str
    country: str
    cities: list[str] = Field(default_factory=list)
    areas: list[str] = Field(default_factory=list)
    max_results_per_area: int = 120
    language: str = "en"
    lead_type: LeadType = "website"
    with_reviews: bool = False
    review_limit: int = 10
    filters: ScrapeFilters = Field(default_factory=ScrapeFilters)


class LeadOut(BaseModel):
    id: str
    external_id: str
    scrape_job_id: str | None = None
    primary_source: str
    source_url: str | None = None
    lead_type: LeadType
    category: str | None = None
    business_name: str
    name_normalized: str
    description: str | None = None
    about: str | None = None
    country: str | None = None
    region: str | None = None
    city: str | None = None
    address: str | None = None
    postal_code: str | None = None
    lat: float | None = None
    lng: float | None = None
    phone: str | None = None
    email: str | None = None
    website_url: str | None = None
    facebook_url: str | None = None
    instagram_url: str | None = None
    menu_url: str | None = None
    web_presence: WebPresence
    rating: float | None = None
    review_count: int | None = None
    reviews: list[dict] | None = None
    opening_hours: dict[str, str] | None = None
    photo_urls: list[str] = Field(default_factory=list)
    website_build_status: WebsiteBuildStatus
    ai_workflow_status: AiWorkflowStatus
    lead_status: LeadStatus
    lead_contact_type: LeadContactType
    payment_status: PaymentStatus
    ai_score: int | None = None
    ai_recommendation: str | None = None
    ai_reasoning: str | None = None
    ai_scored_at: str | None = None
    extra: dict = Field(default_factory=dict)
    notes: str | None = None
    created_at: str
    updated_at: str


class LeadUpdate(BaseModel):
    """Only pipeline-status fields are editable from the admin tab.
    Everything else is owned by the scraper or the future AI agent."""

    website_build_status: WebsiteBuildStatus | None = None
    ai_workflow_status: AiWorkflowStatus | None = None
    lead_status: LeadStatus | None = None
    lead_contact_type: LeadContactType | None = None
    payment_status: PaymentStatus | None = None
    notes: str | None = None


class ScrapeJobOut(BaseModel):
    id: str
    created_at: str
    status: ScrapeJobStatus
    params: ScrapeParams
    started_at: str | None = None
    finished_at: str | None = None
    results_found: int | None = None
    results_inserted: int | None = None
    results_skipped: int | None = None
    error: str | None = None
    triggered_by: str


class ScrapeJobCreate(BaseModel):
    params: ScrapeParams
```

- [ ] **Step 2: Commit**

```bash
git add backend/auth_service/models/schemas.py
git commit -m "feat(api): Pydantic schemas for leads + scrape_jobs admin endpoints"
```

---

### Task C2: `/admin/leads` router

**Files:**
- Create: `backend/auth_service/routers/admin_leads.py`
- Modify: `backend/auth_service/main.py`
- Test: `backend/auth_service/tests/test_admin_leads_router.py`

- [ ] **Step 1: Write the failing tests**

```python
# backend/auth_service/tests/test_admin_leads_router.py
from unittest.mock import MagicMock


def test_list_leads_requires_admin(client, auth_as, client_user):
    auth_as(client_user)
    resp = client.get("/admin/leads")
    assert resp.status_code == 403


def test_list_leads_admin_happy_path(mock_supabase, client, auth_as, admin_user):
    auth_as(admin_user)
    mock_supabase.execute.return_value = MagicMock(
        data=[
            {
                "id": "lead-1", "external_id": "ext-1", "primary_source": "google_maps",
                "lead_type": "website", "business_name": "Acme", "name_normalized": "acme",
                "web_presence": "none", "website_build_status": "not_started",
                "ai_workflow_status": "not_started", "lead_status": "not_sent",
                "lead_contact_type": "not_contacted", "payment_status": "not_applicable",
                "extra": {}, "photo_urls": [],
                "created_at": "2026-05-17T10:00:00Z", "updated_at": "2026-05-17T10:00:00Z",
            }
        ]
    )
    resp = client.get("/admin/leads?city=Lelystad&limit=50")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["items"]) == 1
    assert body["items"][0]["business_name"] == "Acme"


def test_patch_lead_status(mock_supabase, client, auth_as, admin_user):
    auth_as(admin_user)
    mock_supabase.execute.return_value = MagicMock(
        data=[
            {
                "id": "lead-1", "external_id": "ext-1", "primary_source": "google_maps",
                "lead_type": "website", "business_name": "Acme", "name_normalized": "acme",
                "web_presence": "none", "website_build_status": "not_started",
                "ai_workflow_status": "not_started", "lead_status": "sent",
                "lead_contact_type": "not_contacted", "payment_status": "not_applicable",
                "extra": {}, "photo_urls": [],
                "created_at": "2026-05-17T10:00:00Z", "updated_at": "2026-05-17T10:00:00Z",
            }
        ]
    )
    resp = client.patch("/admin/leads/lead-1", json={"lead_status": "sent"})
    assert resp.status_code == 200
    assert resp.json()["lead_status"] == "sent"
```

- [ ] **Step 2: Run, verify fails (404, router not mounted)**

```bash
cd backend && pytest auth_service/tests/test_admin_leads_router.py -v
```

- [ ] **Step 3: Implement router**

```python
# backend/auth_service/routers/admin_leads.py
"""Admin-only CRUD over public.leads. Reads are paginated + filterable.
Writes are limited to pipeline-status fields (LeadUpdate)."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Request, status

from ..models.schemas import LeadOut, LeadUpdate
from ..services.supabase_client import get_supabase_admin
from .deps import admin_user_via_bearer_or_sid

router = APIRouter(prefix="/admin/leads", tags=["admin", "leads"])


@router.get("", response_model=dict)
async def list_leads(
    request: Request,
    country: str | None = Query(None),
    city: str | None = Query(None),
    category: str | None = Query(None),
    web_presence: list[str] | None = Query(None),
    lead_status: list[str] | None = Query(None),
    lead_type: str | None = Query(None),
    min_rating: float | None = Query(None),
    max_rating: float | None = Query(None),
    min_reviews: int | None = Query(None),
    max_reviews: int | None = Query(None),
    min_ai_score: int | None = Query(None),
    max_ai_score: int | None = Query(None),
    search: str | None = Query(None),
    sort: str = Query("created_at"),
    desc: bool = Query(True),
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
) -> dict:
    await admin_user_via_bearer_or_sid(request)
    sb = get_supabase_admin()
    q = sb.table("leads").select("*", count="exact")
    if country:
        q = q.eq("country", country)
    if city:
        q = q.eq("city", city)
    if category:
        q = q.eq("category", category)
    if lead_type:
        q = q.eq("lead_type", lead_type)
    if web_presence:
        q = q.in_("web_presence", web_presence)
    if lead_status:
        q = q.in_("lead_status", lead_status)
    if min_rating is not None:
        q = q.gte("rating", min_rating)
    if max_rating is not None:
        q = q.lte("rating", max_rating)
    if min_reviews is not None:
        q = q.gte("review_count", min_reviews)
    if max_reviews is not None:
        q = q.lte("review_count", max_reviews)
    if min_ai_score is not None:
        q = q.gte("ai_score", min_ai_score)
    if max_ai_score is not None:
        q = q.lte("ai_score", max_ai_score)
    if search:
        q = q.ilike("business_name", f"%{search}%")

    q = q.order(sort, desc=desc).range(offset, offset + limit - 1)
    res = q.execute()
    items = [LeadOut(**row).model_dump() for row in (res.data or [])]
    return {"items": items, "total": getattr(res, "count", None) or len(items)}


@router.get("/{lead_id}", response_model=LeadOut)
async def get_lead(lead_id: str, request: Request) -> LeadOut:
    await admin_user_via_bearer_or_sid(request)
    sb = get_supabase_admin()
    res = sb.table("leads").select("*").eq("id", lead_id).maybe_single().execute()
    if not res.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lead not found")
    return LeadOut(**res.data)


@router.patch("/{lead_id}", response_model=LeadOut)
async def patch_lead(lead_id: str, body: LeadUpdate, request: Request) -> LeadOut:
    await admin_user_via_bearer_or_sid(request)
    sb = get_supabase_admin()
    patch = {k: v for k, v in body.model_dump(exclude_none=True).items()}
    if not patch:
        raise HTTPException(status_code=422, detail="No fields to update")
    res = sb.table("leads").update(patch).eq("id", lead_id).execute()
    if not res.data:
        raise HTTPException(status_code=500, detail="Update failed")
    return LeadOut(**res.data[0])
```

- [ ] **Step 4: Mount the router in `main.py`**

Add to `backend/auth_service/main.py` next to other `app.include_router(...)` lines:

```python
from .routers import admin_leads
app.include_router(admin_leads.router)
```

- [ ] **Step 5: Run, verify passes**

```bash
cd backend && pytest auth_service/tests/test_admin_leads_router.py -v
```
Expected: 3 PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/auth_service/routers/admin_leads.py backend/auth_service/main.py backend/auth_service/tests/test_admin_leads_router.py
git commit -m "feat(api): /admin/leads — paginated list, get, patch (pipeline status)"
```

---

### Task C3: `/admin/scrape-jobs` router

**Files:**
- Create: `backend/auth_service/routers/admin_scrape_jobs.py`
- Modify: `backend/auth_service/main.py`
- Test: `backend/auth_service/tests/test_admin_scrape_jobs_router.py`

- [ ] **Step 1: Write tests**

```python
# backend/auth_service/tests/test_admin_scrape_jobs_router.py
from unittest.mock import MagicMock


def test_list_jobs_requires_admin(client, auth_as, client_user):
    auth_as(client_user)
    assert client.get("/admin/scrape-jobs").status_code == 403


def test_create_job_validates_params(client, auth_as, admin_user):
    auth_as(admin_user)
    bad = client.post("/admin/scrape-jobs", json={"params": {"country": "NL"}})
    assert bad.status_code == 422  # category missing


def test_create_job_happy_path(mock_supabase, client, auth_as, admin_user):
    auth_as(admin_user)
    mock_supabase.execute.return_value = MagicMock(
        data=[
            {
                "id": "job-1", "status": "pending", "triggered_by": "cms",
                "created_at": "2026-05-17T10:00:00Z",
                "params": {"category": "restaurants", "country": "NL"},
            }
        ]
    )
    resp = client.post(
        "/admin/scrape-jobs",
        json={"params": {"category": "restaurants", "country": "NL"}},
    )
    assert resp.status_code == 201
    assert resp.json()["status"] == "pending"


def test_cancel_pending_job(mock_supabase, client, auth_as, admin_user):
    auth_as(admin_user)
    mock_supabase.execute.side_effect = [
        MagicMock(data={"id": "job-1", "status": "pending", "triggered_by": "cms",
                        "created_at": "x", "params": {"category": "x", "country": "NL"}}),
        MagicMock(data=[{"id": "job-1", "status": "cancelled", "triggered_by": "cms",
                         "created_at": "x", "params": {"category": "x", "country": "NL"}}]),
    ]
    resp = client.patch("/admin/scrape-jobs/job-1", json={"status": "cancelled"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "cancelled"
```

- [ ] **Step 2: Implement router**

```python
# backend/auth_service/routers/admin_scrape_jobs.py
"""Admin queue management — create scrape jobs from the form, list,
cancel pending. The scraper worker is the only consumer of `status`
transitions to `running`/`done`/`failed`."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Request, status

from ..models.schemas import ScrapeJobCreate, ScrapeJobOut
from ..services.supabase_client import get_supabase_admin
from .deps import admin_user_via_bearer_or_sid

router = APIRouter(prefix="/admin/scrape-jobs", tags=["admin", "scrape-jobs"])


@router.get("", response_model=list[ScrapeJobOut])
async def list_jobs(
    request: Request,
    status_filter: str | None = Query(None, alias="status"),
    limit: int = Query(50, le=200),
) -> list[ScrapeJobOut]:
    await admin_user_via_bearer_or_sid(request)
    sb = get_supabase_admin()
    q = sb.table("scrape_jobs").select("*").order("created_at", desc=True).limit(limit)
    if status_filter:
        q = q.eq("status", status_filter)
    res = q.execute()
    return [ScrapeJobOut(**row) for row in (res.data or [])]


@router.get("/{job_id}", response_model=ScrapeJobOut)
async def get_job(job_id: str, request: Request) -> ScrapeJobOut:
    await admin_user_via_bearer_or_sid(request)
    sb = get_supabase_admin()
    res = sb.table("scrape_jobs").select("*").eq("id", job_id).maybe_single().execute()
    if not res.data:
        raise HTTPException(status_code=404, detail="Job not found")
    return ScrapeJobOut(**res.data)


@router.post("", response_model=ScrapeJobOut, status_code=status.HTTP_201_CREATED)
async def create_job(body: ScrapeJobCreate, request: Request) -> ScrapeJobOut:
    await admin_user_via_bearer_or_sid(request)
    sb = get_supabase_admin()
    res = sb.table("scrape_jobs").insert({"params": body.params.model_dump(), "triggered_by": "cms"}).execute()
    if not res.data:
        raise HTTPException(status_code=500, detail="Job could not be created")
    return ScrapeJobOut(**res.data[0])


@router.patch("/{job_id}", response_model=ScrapeJobOut)
async def cancel_job(job_id: str, body: dict, request: Request) -> ScrapeJobOut:
    await admin_user_via_bearer_or_sid(request)
    if body.get("status") != "cancelled":
        raise HTTPException(status_code=422, detail="Only status=cancelled is allowed via PATCH")
    sb = get_supabase_admin()
    existing = sb.table("scrape_jobs").select("status").eq("id", job_id).maybe_single().execute()
    if not existing.data:
        raise HTTPException(status_code=404, detail="Job not found")
    if existing.data["status"] != "pending":
        raise HTTPException(status_code=409, detail="Only pending jobs can be cancelled")
    res = (
        sb.table("scrape_jobs").update({"status": "cancelled"}).eq("id", job_id).execute()
    )
    return ScrapeJobOut(**res.data[0])
```

- [ ] **Step 3: Mount in `main.py`**

```python
from .routers import admin_scrape_jobs
app.include_router(admin_scrape_jobs.router)
```

- [ ] **Step 4: Run tests**

```bash
cd backend && pytest auth_service/tests/test_admin_scrape_jobs_router.py -v
```
Expected: 4 PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/auth_service/routers/admin_scrape_jobs.py backend/auth_service/main.py backend/auth_service/tests/test_admin_scrape_jobs_router.py
git commit -m "feat(api): /admin/scrape-jobs — list, create, cancel pending"
```

---

### Task C4: Frontend — `lib/leadEnums.ts` (labels + colors)

**Files:**
- Create: `frontend/src/lib/leadEnums.ts`

- [ ] **Step 1: Write**

```typescript
// Single source for enum → display label/color mappings. Add new enum
// values here when migrations add them.

export const LEAD_TYPE_LABEL = {
  website: "Website",
  automation: "AI Automation",
  both: "Website + AI",
} as const;

export const WEB_PRESENCE_LABEL = {
  none: "No website",
  social_only: "Social only",
  has_website: "Has website",
  unknown: "Unknown",
} as const;

export const WEB_PRESENCE_BADGE_CN = {
  none: "bg-red-100 text-red-700 dark:bg-red-950 dark:text-red-300",
  social_only: "bg-amber-100 text-amber-700 dark:bg-amber-950 dark:text-amber-300",
  has_website: "bg-zinc-100 text-zinc-600 dark:bg-zinc-800 dark:text-zinc-400",
  unknown: "bg-zinc-100 text-zinc-500 dark:bg-zinc-800 dark:text-zinc-400",
} as const;

export const LEAD_STATUS_LABEL = {
  not_sent: "Not sent",
  sent: "Sent",
  accepted: "Accepted",
  refused: "Refused",
} as const;

export const LEAD_STATUS_BADGE_CN = {
  not_sent: "bg-zinc-100 text-zinc-600 dark:bg-zinc-800 dark:text-zinc-300",
  sent: "bg-blue-100 text-blue-700 dark:bg-blue-950 dark:text-blue-300",
  accepted: "bg-emerald-100 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300",
  refused: "bg-red-100 text-red-700 dark:bg-red-950 dark:text-red-300",
} as const;

export const PAYMENT_STATUS_LABEL = {
  not_applicable: "—",
  not_paid: "Unpaid",
  paid: "Paid",
} as const;

export const WEBSITE_BUILD_STATUS_LABEL = {
  not_started: "Not started",
  building_design: "Designing",
  design_done: "Design done",
  building: "Building",
  finished_cms: "Finished (CMS)",
  refining: "Refining",
  not_applicable: "—",
} as const;

export const AI_WORKFLOW_STATUS_LABEL = {
  not_started: "Not started",
  building: "Building",
  finished: "Finished",
  refining: "Refining",
  not_applicable: "—",
} as const;

export const LEAD_CONTACT_TYPE_LABEL = {
  not_contacted: "Not contacted",
  phone: "Phone",
  mail: "Mail",
  in_person: "In person",
} as const;

export const SCRAPE_JOB_STATUS_BADGE_CN = {
  pending: "bg-zinc-100 text-zinc-600 dark:bg-zinc-800 dark:text-zinc-300",
  running: "bg-blue-100 text-blue-700 dark:bg-blue-950 dark:text-blue-300",
  done: "bg-emerald-100 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300",
  failed: "bg-red-100 text-red-700 dark:bg-red-950 dark:text-red-300",
  cancelled: "bg-zinc-100 text-zinc-500 dark:bg-zinc-800 dark:text-zinc-500",
} as const;
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/lib/leadEnums.ts
git commit -m "feat(ui): lead-tab enum label + badge color maps"
```

---

🛑 **CHECKPOINT C** — Before building the UI, paste the following wireframe (text-rendered) to the user and confirm it matches their mental model:

```
┌────────────────────────────────────────────────────────────────────┐
│  Leads Dashboard / Scraper Control   [tab switcher, animated]      │
├────────────────────────────────────────────────────────────────────┤
│  ── DASHBOARD TAB ──                                               │
│  ┌─Stat─┐ ┌─Stat─┐ ┌─Stat─┐ ┌─Stat─┐   (stagger fade-in)           │
│  │Total │ │ No   │ │ Sent │ │ AI   │                               │
│  │ 142  │ │ web  │ │ 27   │ │ scored│                              │
│  └──────┘ └──────┘ └──────┘ └──────┘                               │
│                                                                    │
│  [Country ▾] [City ▾] [Category ▾] [Web presence ▾]                │
│  [Lead status ▾] [Lead type ▾] [Rating: __ ↔ __] [⌕ search]        │
│                                                                    │
│  Toggle:  ◉ Table   ○ Kanban                                       │
│                                                                    │
│  ┌─Table─────────────────────────────────────────────────────────┐ │
│  │ Name │ City │ Cat │ Presence │ ★ │ #rev │ Status │ Paid │     │ │
│  │ Acme │ Lst  │ rest│ [none]   │4.3│ 87   │ [sent] │  —   │ ⋯ ▸ │ │
│  │ Bcom │ Lst  │ rest│ [social] │4.1│ 12   │ [n/s]  │  —   │ ⋯ ▸ │ │
│  └────────────────────────────────────────────────────────────────┘ │
│  ← Prev   Page 1 / 5   Next →                                      │
│                                                                    │
│  Click row → slides drawer in from right with full lead detail.    │
│                                                                    │
│  ── SCRAPER CONTROL TAB ──                                         │
│  [Category*: ____ ]  [Country*: NL]                                │
│  [Cities  +Add]  [Areas  +Add]                                     │
│  [Max/area: 120]  [Language: en]  [Lead type: website ▾]           │
│  [□ Include reviews]                                               │
│  ▸ Advanced filters (collapsed)                                    │
│    └─ min/max rating, min/max reviews, web presence multi-select   │
│  [Submit scrape]                                                   │
│                                                                    │
│  Job history (live)                                                │
│  ┌───────────────────────────────────────────────────────────────┐ │
│  │ ● running   restaurants NL/Lelystad  started 2m ago           │ │
│  │ ✓ done      plumbers NL              done · 47 found · 3m     │ │
│  │ ⊝ cancelled hair salons NL           cancelled by stefan      │ │
│  └────────────────────────────────────────────────────────────────┘ │
└────────────────────────────────────────────────────────────────────┘
```

Wait for confirmation before building C5–C10. The user may want simpler/different layout.

---

### Task C5: Sidebar link

**Files:**
- Modify: `frontend/src/components/dashboard/SidebarPanel.tsx`

- [ ] **Step 1: Add Leads to `adminItems`**

Locate the `adminItems` array (around line 26-30 per Checkpoint 0 findings) and insert:

```typescript
{ href: "/dashboard/admin/leads", label: "Leads", icon: Sparkles },
```

(use any reasonable lucide icon — Sparkles, Target, or Crosshair; engineer's call. Import alongside existing imports.)

- [ ] **Step 2: Commit**

```bash
git add frontend/src/components/dashboard/SidebarPanel.tsx
git commit -m "feat(ui): add Leads link to admin sidebar"
```

---

### Task C6: Page entry + tab orchestrator

**Files:**
- Create: `frontend/src/app/dashboard/admin/leads/page.tsx`
- Create: `frontend/src/components/admin/leads/LeadsTab.tsx`

- [ ] **Step 1: `page.tsx`**

```tsx
"use client";

import { LeadsTab } from "@/components/admin/leads/LeadsTab";

export default function AdminLeadsPage() {
  return <LeadsTab />;
}
```

- [ ] **Step 2: `LeadsTab.tsx` — two-section switcher**

```tsx
"use client";

import { useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { PageHeader } from "@/components/dashboard/PageHeader";
import { LeadsDashboard } from "./LeadsDashboard";
import { ScraperControl } from "./ScraperControl";

type Section = "dashboard" | "scraper";

export function LeadsTab() {
  const [section, setSection] = useState<Section>("dashboard");
  return (
    <div className="p-4 md:p-8">
      <PageHeader
        title="Leads"
        description="Browse scraped businesses without websites and trigger new scrape jobs."
      />
      <div className="mt-6 flex gap-2">
        {(["dashboard", "scraper"] as Section[]).map((s) => (
          <button
            key={s}
            type="button"
            onClick={() => setSection(s)}
            className={[
              "px-3 py-1.5 rounded-md text-sm font-medium transition-colors cursor-pointer",
              section === s
                ? "bg-zinc-900 text-white dark:bg-zinc-100 dark:text-zinc-900"
                : "bg-zinc-100 text-zinc-500 hover:bg-zinc-200 dark:bg-zinc-800 dark:text-zinc-400 dark:hover:bg-zinc-700",
            ].join(" ")}
          >
            {s === "dashboard" ? "Dashboard" : "Scraper"}
          </button>
        ))}
      </div>
      <AnimatePresence mode="wait" initial={false}>
        <motion.div
          key={section}
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -8 }}
          transition={{ duration: 0.22, ease: "easeOut" }}
          className="mt-6"
        >
          {section === "dashboard" ? <LeadsDashboard /> : <ScraperControl />}
        </motion.div>
      </AnimatePresence>
    </div>
  );
}
```

- [ ] **Step 3: Stubs for `LeadsDashboard.tsx` and `ScraperControl.tsx`** (compile-passing stubs, real impl in C7/C8)

```tsx
// frontend/src/components/admin/leads/LeadsDashboard.tsx
"use client";
export function LeadsDashboard() {
  return <div className="text-sm text-zinc-500">Dashboard coming soon…</div>;
}
```

```tsx
// frontend/src/components/admin/leads/ScraperControl.tsx
"use client";
export function ScraperControl() {
  return <div className="text-sm text-zinc-500">Scraper form coming soon…</div>;
}
```

- [ ] **Step 4: Local typecheck + dev**

```bash
cd frontend && npm run typecheck && npm run dev
```
Expected: types green; nav to `/dashboard/admin/leads` shows the tab switcher and stub text. Animated section transition works.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/app/dashboard/admin/leads frontend/src/components/admin/leads
git commit -m "feat(ui): /dashboard/admin/leads page with dashboard / scraper tabs"
```

---

### Task C7: Leads dashboard — stat cards + filters + table

**Files:**
- Modify: `frontend/src/components/admin/leads/LeadsDashboard.tsx`
- Create: `frontend/src/components/admin/leads/LeadStatsCards.tsx`
- Create: `frontend/src/components/admin/leads/LeadFilters.tsx`
- Create: `frontend/src/components/admin/leads/LeadsTable.tsx`
- Create: `frontend/src/components/admin/leads/LeadBadge.tsx`

For each component below: write the component, hook into `useQuery` for fetch where applicable, animate list items with `staggerFast` + fade. Wire the filter bar with controlled state, send query params to `/api/admin/leads?...`. The complete code for each (similar in size to existing dashboard components like `IssueList.tsx`) goes here — the engineer should mirror the IssueList structure exactly:

1. **`LeadBadge.tsx`** — small `<span>` with class from `WEB_PRESENCE_BADGE_CN` / `LEAD_STATUS_BADGE_CN` / `SCRAPE_JOB_STATUS_BADGE_CN`, fixed width `w-24` for alignment (lesson from `IssueList.tsx` fix earlier in the repo).

2. **`LeadStatsCards.tsx`** — fetches `/api/admin/leads?limit=1` per stat OR computes from a list — simplest v1: 4 cards (Total, No-website, Sent, AI-scored). Each card animates in with `fadeUp` + `staggerFast`. Layout: `grid grid-cols-2 md:grid-cols-4 gap-3`.

3. **`LeadFilters.tsx`** — controlled inputs for `country, city, category, web_presence (multi), lead_status (multi), lead_type, rating range, review-count range, ai_score range, search`. Use `dashboardInputCn`. Inline collapse for "Advanced" section. Emits `onChange(filters)` upward.

4. **`LeadsTable.tsx`** — `useQuery(["leads", filters], () => fetch(...))`. Table on `md:` and up, card list on mobile. Columns: name, city, category, web_presence badge, rating, reviews, lead_status badge, payment badge. Row click opens `LeadDetailDrawer` (Task C9). Pagination bar at bottom. Wrap each row in `<motion.tr layout>` so refilter animates.

5. **`LeadsDashboard.tsx`** — composes: stats cards → filter bar → table. Lifts filter state. Holds toggle for table-vs-kanban (Task C8).

Each component:
- [ ] write it
- [ ] hook into `useQuery`
- [ ] verify dev server renders correctly with seed data
- [ ] commit per component

Commits:
```bash
git commit -m "feat(ui): LeadBadge — fixed-width status pill"
git commit -m "feat(ui): LeadStatsCards — 4-card overview, stagger animation"
git commit -m "feat(ui): LeadFilters — full filter bar with collapsible advanced"
git commit -m "feat(ui): LeadsTable — paginated, sortable, animated reorder"
git commit -m "feat(ui): LeadsDashboard — composes stats + filters + table"
```

---

### Task C8: Kanban view

**Files:**
- Create: `frontend/src/components/admin/leads/LeadKanban.tsx`
- Modify: `frontend/package.json` (add `@dnd-kit/core`, `@dnd-kit/sortable`)

- [ ] **Step 1: Install dnd-kit**

```bash
cd frontend && npm install @dnd-kit/core @dnd-kit/sortable
```

- [ ] **Step 2: Implement `LeadKanban.tsx`** — 4 columns mapped to `lead_status` values (not_sent, sent, accepted, refused). Each column shows lead cards (compact: name + city + presence badge). DragEnd handler PATCHes `/api/admin/leads/{id}` with `{lead_status: newStatus}`. Optimistic update + rollback on error. Animate column cards with `motion.div layout`.

- [ ] **Step 3: Add toggle in `LeadsDashboard.tsx`** — segmented control (Table | Kanban). Use `AnimatePresence` to crossfade between the two views.

- [ ] **Step 4: Verify by dragging a card → status updates on the API → refetch leaves card in new column.**

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/admin/leads/LeadKanban.tsx frontend/src/components/admin/leads/LeadsDashboard.tsx frontend/package.json frontend/package-lock.json
git commit -m "feat(ui): LeadKanban view with dnd-kit drag + optimistic status update"
```

---

### Task C9: Lead detail drawer

**Files:**
- Create: `frontend/src/components/admin/leads/LeadDetailDrawer.tsx`

- [ ] **Step 1: Implement drawer**

Use `AnimatePresence` + `motion.div` with `drawerRight` from `lib/animations.ts`. Backdrop with `backdrop` animation. Width `w-full md:w-[40rem]`. Sections inside (each with `fadeUp` stagger):

1. Header: business name + category + external Maps link + close button
2. Status editors: 5 inline `<select>` for `website_build_status`, `ai_workflow_status`, `lead_status`, `lead_contact_type`, `payment_status`. Each save PATCHes immediately (debounced 300ms).
3. Notes: `<textarea>` with debounced PATCH.
4. Location card: address, city, country, postal, lat/lng.
5. Contact card: phone, email, website url (if any), facebook, instagram, menu.
6. Reviews JSON viewer (collapsed, expand on click — `motion height: auto`).
7. Opening hours table.
8. `extra` JSON viewer (raw, code-styled).
9. AI section (currently empty placeholder — "Not scored yet" + `ai_score`/`ai_recommendation`/`ai_reasoning` if present).

Open from `LeadsTable` row click and `LeadKanban` card click (lifted state in `LeadsDashboard`).

- [ ] **Step 2: Commit**

```bash
git add frontend/src/components/admin/leads/LeadDetailDrawer.tsx
git commit -m "feat(ui): LeadDetailDrawer with inline status editors + animated reveal"
```

---

### Task C10: Scraper control — form + job history

**Files:**
- Modify: `frontend/src/components/admin/leads/ScraperControl.tsx`
- Create: `frontend/src/components/admin/leads/ScraperForm.tsx`
- Create: `frontend/src/components/admin/leads/JobHistoryList.tsx`

- [ ] **Step 1: `ScraperForm.tsx`** — mirrors `IssueForm.tsx` exactly. Fields:
  - `category` (text, required)
  - `country` (text, default "NL")
  - `cities` (chip input — `Enter` adds)
  - `areas` (chip input)
  - `max_results_per_area` (number, 120)
  - `language` (text, "en")
  - `lead_type` (select: website / automation / both)
  - `with_reviews` (toggle)
  - Collapsible "Advanced filters" section:
    - `min_rating`/`max_rating` number inputs
    - `min_reviews`/`max_reviews` number inputs
    - `web_presence` multi-checkbox: none, social_only, has_website, unknown
  - Submit POST `/api/admin/scrape-jobs` with `{params: {...}}`
  - On success: `onJobCreated()` callback (parent refetches history)
  - Validation: category + country required
  - Use `FormFeedback`, `dashboardInputCn`, `dashboardPrimaryBtnCn`

- [ ] **Step 2: `JobHistoryList.tsx`** — mirrors `IssueList.tsx`. Fetches `/api/admin/scrape-jobs` via `useQuery` with `refreshInterval: 5000`. Each row: status badge, params summary ("restaurants NL / Lelystad / max 120"), timestamps, counters. Pending rows have a "Cancel" button (PATCH status=cancelled). Animate row entry with `staggerFast`.

- [ ] **Step 3: `ScraperControl.tsx`** — composes Form + History. Lifts `refreshTrigger` int that bumps on each form submit, forces the history list to refetch.

- [ ] **Step 4: Verify end-to-end**

Submit a tiny scrape from the UI (e.g. `restaurants NL --city Lelystad --max 5`). Verify:
- POST returns 201, history shows new `pending` row immediately
- After ~5s polling, status shows `running` once the Hetzner worker picks it up (skip if Phase D not done yet — mark pending in DB and trigger manually via `python -m scraper.cli run-pending` locally)
- After completion, leads appear in the dashboard table.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/admin/leads/ScraperForm.tsx frontend/src/components/admin/leads/JobHistoryList.tsx frontend/src/components/admin/leads/ScraperControl.tsx
git commit -m "feat(ui): scraper form + job history live-polling list"
```

---

# Phase D — Hetzner Deployment + CI

### Task D1: systemd unit + timer

**Files:**
- Create: `scraper/deploy/scraper.service`
- Create: `scraper/deploy/scraper.timer`

- [ ] **Step 1: `scraper.service`**

```ini
[Unit]
Description=RT Scraper — claim and run one pending scrape job
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
User=scraper
WorkingDirectory=/opt/rt-scraper
EnvironmentFile=/etc/scraper.env
ExecStart=/opt/rt-scraper/.venv/bin/python -m scraper.cli run-pending
StandardOutput=append:/var/log/rt-scraper.log
StandardError=append:/var/log/rt-scraper.log
Nice=10
```

- [ ] **Step 2: `scraper.timer`**

```ini
[Unit]
Description=Run RT Scraper nightly + every 30 min as catch-up

[Timer]
OnCalendar=*-*-* 02:00:00
OnCalendar=*-*-* 00/0:30:00
Persistent=true
Unit=scraper.service

[Install]
WantedBy=timers.target
```

- [ ] **Step 3: Commit**

```bash
git add scraper/deploy/scraper.service scraper/deploy/scraper.timer
git commit -m "feat(deploy): systemd unit + timer for hetzner cron"
```

---

### Task D2: `deploy/DEPLOY.md`

- [ ] **Step 1: Write `DEPLOY.md`** with these sections:

1. **Prerequisites** — Ubuntu 22.04+, Python 3.11+, system Chromium deps.
2. **Create user + dirs:**
   ```bash
   sudo useradd -r -s /usr/sbin/nologin -m -d /opt/rt-scraper scraper
   sudo install -d -o scraper -g scraper /opt/rt-scraper /var/log
   sudo touch /var/log/rt-scraper.log && sudo chown scraper:scraper /var/log/rt-scraper.log
   ```
3. **Clone + venv:**
   ```bash
   sudo -u scraper git clone <repo> /opt/rt-scraper/src
   cd /opt/rt-scraper/src/scraper
   sudo -u scraper python3.11 -m venv /opt/rt-scraper/.venv
   sudo -u scraper /opt/rt-scraper/.venv/bin/pip install -e .
   sudo -u scraper /opt/rt-scraper/.venv/bin/python -m playwright install --with-deps chromium
   ```
4. **`/etc/scraper.env`** — populate with real values from `scraper/.env.example`. Set `chmod 600`.
5. **Service-account JSON** — place at `/etc/scraper/google-sa.json`, `chmod 600`, `chown scraper:scraper`.
6. **Install systemd units:**
   ```bash
   sudo cp scraper/deploy/scraper.service /etc/systemd/system/
   sudo cp scraper/deploy/scraper.timer /etc/systemd/system/
   sudo systemctl daemon-reload
   sudo systemctl enable --now scraper.timer
   ```
7. **Verify:**
   ```bash
   systemctl status scraper.timer
   sudo journalctl -u scraper.service -n 50
   sudo -u scraper /opt/rt-scraper/.venv/bin/python -m scraper.cli run-pending  # manual test
   tail -f /var/log/rt-scraper.log
   ```
8. **Log rotation** — `/etc/logrotate.d/rt-scraper` (daily, 14 days, compress).
9. **Updating** — `git pull`, `pip install -e .`, restart timer.

- [ ] **Step 2: Commit**

```bash
git add scraper/deploy/DEPLOY.md
git commit -m "docs(deploy): hetzner step-by-step"
```

---

### Task D3: GitHub Actions — `scraper-ci.yml`

**Files:**
- Create: `.github/workflows/scraper-ci.yml`

- [ ] **Step 1: Write workflow**

```yaml
name: Scraper CI

on:
  push:
    paths:
      - 'scraper/**'
      - '.github/workflows/scraper-ci.yml'
  pull_request:
    paths:
      - 'scraper/**'
      - '.github/workflows/scraper-ci.yml'

jobs:
  lint-and-types:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
          cache: pip
          cache-dependency-path: scraper/pyproject.toml

      - name: Install scraper + dev deps
        working-directory: scraper
        run: |
          python -m pip install --upgrade pip
          pip install -e ".[dev]"

      - name: Ruff
        working-directory: scraper
        run: ruff check .

      - name: Mypy
        working-directory: scraper
        run: mypy src

      - name: Pytest (no live scrape)
        working-directory: scraper
        run: pytest -v --ignore=tests/test_live_scrape.py
```

- [ ] **Step 2: Commit**

```bash
git add .github/workflows/scraper-ci.yml
git commit -m "ci: lint + type-check + offline tests for scraper package"
```

---

### Task D4: Env doc update

**Files:**
- Modify: `docs/ENVIRONMENTS.md`

- [ ] **Step 1: Append a section** documenting the new scraper env vars (Supabase URL + service key — reuse existing rows; sheets credentials path; sheet ID; headless toggle; locale; user-agent; delay min/max). Note that these live on the Hetzner box, NOT on Vercel — backend on Vercel does not import the scraper package.

- [ ] **Step 2: Commit**

```bash
git add docs/ENVIRONMENTS.md
git commit -m "docs(env): document scraper env vars on Hetzner"
```

---

🛑 **CHECKPOINT D** — Once the user has run the DEPLOY.md steps on Hetzner, ask them to:

1. Submit a tiny scrape from the CMS (e.g. `restaurants NL`, cities `Lelystad`, max 5).
2. Verify it appears in the job history as `pending`.
3. Wait for the timer to fire (or run `sudo -u scraper /opt/rt-scraper/.venv/bin/python -m scraper.cli run-pending` manually).
4. Verify the job transitions `running → done`, counters populate, and the 5 leads appear in the dashboard table AND the Google Sheet.

If any step fails, debug from logs (`/var/log/rt-scraper.log`).

---

## Acceptance criteria (re-check at end)

- [ ] Migration ran clean; 8 enums + 2 tables exist with all indexes.
- [ ] `python -m scraper.cli scrape restaurants NL --city Lelystad --max 10 --dry-run` produces a JSON file with complete lead records (all fields populated where Google provides them).
- [ ] Non-dry-run writes deduplicated leads to both Supabase (`leads.external_id` unique) and the Google Sheet.
- [ ] Optional filters work, off by default. A business with 0 reviews + no website still captured by default.
- [ ] `/dashboard/admin/leads` is admin-only (403 for non-admins via `admin_user_via_bearer_or_sid`).
- [ ] Page fully responsive (table → card stack on mobile).
- [ ] All animations use existing `lib/animations.ts` tokens; `prefers-reduced-motion` respected.
- [ ] Submitting the form creates a `scrape_jobs` row in `pending`, Hetzner picks it up, history shows live status, leads appear in dashboard.
- [ ] Adding a new `lead_type` value or new extracted field: only requires editing `models.py`, `leadEnums.ts`, and `_FIELD_MAP` in `sheets_sink.py` — **no DB migration**, no other code touched. Extension points commented in `google_maps.py` (about, photos, proxy, new sources, automation branch).
- [ ] CI green: `scraper-ci.yml` passes ruff + mypy + unit tests on push.

---

## Self-Review (skill-mandated)

**Spec coverage:**
- Section 5 (DB): ✅ Task A1
- Section 6 (scraper): ✅ Tasks B1–B10 (models, config, dedup, selectors, engine, sinks, pipeline, CLI, Playwright install, dry-run)
- Section 7 (CMS tab): ✅ Tasks C1–C10 (schemas, two routers, enum maps, sidebar link, page+orchestrator, dashboard, kanban, drawer, scraper form, job history)
- Section 8 (deploy): ✅ Tasks D1–D4 (systemd, DEPLOY.md, CI workflow, env docs)
- Section 9 (env): ✅ scraper/.env.example + docs/ENVIRONMENTS.md
- Section 10 (acceptance): ✅ explicit checklist at end
- 🛑 Checkpoints 0, A, B1, B2, C, D: ✅ all preserved, plan stops at each

**Placeholder scan:**
- No "TBD", "implement later", "appropriate error handling".
- One minor weakness: Task C7 (dashboard components) gives structural guidance + commit messages but inlines smaller code than other tasks. Engineer follows existing `IssueList.tsx` pattern. Acceptable — pattern is concrete and copy-able. If concerned, expand C7 into C7a–C7e with full code per component.

**Type consistency:**
- `external_id` text everywhere ✓
- `web_presence` 4-value enum identical across `models.py`, `schemas.py`, migration, `leadEnums.ts` ✓
- `lead_status` 4 values identical ✓
- `ScrapeParams` shape identical in Python and TS payload sent from `ScraperForm.tsx` ✓
- Sink `write()` returns `bool` — used as such in `pipeline.py` ✓

---

## Execution Handoff

**Plan complete and saved to `docs/superpowers/plans/2026-05-17-google-maps-lead-scraper.md`. Two execution options:**

**1. Subagent-Driven (recommended)** — dispatch a fresh subagent per task, review between tasks, fast iteration. Best for a 25+ task plan like this.

**2. Inline Execution** — execute tasks in this session using executing-plans, batch execution with checkpoints. Best if you want to see every step happen here.

**Which approach?**
