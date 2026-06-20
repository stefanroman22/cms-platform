# SEO/GEO Foundation — Implementation Plan (Plan 1 of 4)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

> **Commit policy (Stefan's repo rule):** Do **NOT** run `git commit` automatically. The "Commit" steps below are **checkpoints** — stage the work and treat the task as done; Stefan runs the actual commits in a batch when he approves. The commands are pre-written so they're ready.

**Goal:** Build the data + API + dashboard foundation for the SEO/GEO Optimizer agent: a Supabase schema (per-client SEO memory + the agent-owned SEO/GEO CMS area), a `seo.py` backend router (reads + human CRUD + public site-consumer endpoints), and a read-only dashboard "SEO & GEO" section — so later plans (the agent itself) have something to write into and surface.

**Architecture:** Additive Supabase migration (10 tables + 3 `projects` columns, RLS service-role-only like the booking tables). A new FastAPI router `seo.py` backed by a `seo_repo.py` (mirrors `booking_admin_repo.py`), reusing the existing `user_via_bearer_or_session` + `require_project_access` auth deps so the same endpoints serve both the dashboard (session) and the agent (admin bearer). A new dashboard section cloned from `BookingsSection`, fetching via the existing `useQuery` hook and a `seo/api.ts` helper. The analytical tables (runs/audits/plan/changes/competitors) are written by the agent later via Supabase MCP; this plan only **reads** them for the dashboard and provides **human CRUD** for the content tables (page_meta/articles).

**Tech Stack:** FastAPI + Supabase (`supabase-py`), Pydantic v2, pytest + `TestClient`; Next.js 16 + TypeScript + Tailwind v4 + Motion + lucide-react + vitest/RTL.

---

## File structure

```
backend/
  migrations/2026_06_14_seo_geo.sql                 # CREATE (additive: 10 tables + 3 projects cols + RLS)
  auth_service/models/seo_schemas.py                # CREATE (Pydantic In/Out)
  auth_service/services/seo_repo.py                 # CREATE (Supabase reads + content CRUD)
  auth_service/routers/seo.py                       # CREATE (router)
  auth_service/main.py                              # MODIFY (register router)
  auth_service/tests/test_seo_repo.py               # CREATE
  auth_service/tests/test_seo_router.py             # CREATE

frontend/src/
  components/dashboard/sectionConfig.ts             # MODIFY (+ "seo" section + seoEnabled cap)
  app/dashboard/[projectSlug]/page.tsx              # MODIFY (render <SeoSection/> + seoEnabled cap)
  components/dashboard/seo/types.ts                 # CREATE
  components/dashboard/seo/api.ts                   # CREATE
  components/dashboard/seo/SeoSection.tsx           # CREATE (shell + tab strip)
  components/dashboard/seo/OverviewTab.tsx          # CREATE
  components/dashboard/seo/PlanTab.tsx              # CREATE
  components/dashboard/seo/HistoryTab.tsx           # CREATE
  components/dashboard/seo/ArticlesTab.tsx          # CREATE
  components/dashboard/seo/CompetitorsTab.tsx       # CREATE
  components/dashboard/seo/SettingsTab.tsx          # CREATE
  components/dashboard/seo/SeoSection.test.tsx      # CREATE
```

---

## Task 1: Supabase migration

**Files:**
- Create: `backend/migrations/2026_06_14_seo_geo.sql`

- [ ] **Step 1: Write the migration SQL**

```sql
-- backend/migrations/2026_06_14_seo_geo.sql
-- SEO/GEO Optimizer foundation.
--
-- Adds per-client SEO/GEO memory (runs/audits/plan/changes/competitors), the
-- agent-owned SEO/GEO CMS area (page_meta + articles, which clients & admins may
-- also CRUD), a cross-client learnings table, and a job queue for dashboard-
-- triggered runs. Plus 3 flag columns on projects.
--
-- Additive + behaviour-preserving: a project with no SEO rows behaves exactly as
-- today. RLS is enabled with NO public policies (service-role only); app-level
-- auth is enforced in code via require_project_access, mirroring the booking tables.

create extension if not exists pgcrypto with schema extensions;

-- ── project flags (per-column convention, like locales/booking) ──
alter table public.projects add column if not exists seo_enabled boolean not null default false;
alter table public.projects add column if not exists seo_blog_route text;
alter table public.projects add column if not exists seo_last_run_at timestamptz;

-- ── run lifecycle + per-client memory ──
create table if not exists public.seo_runs (
  id uuid primary key default gen_random_uuid(),
  project_id uuid not null references public.projects(id) on delete cascade,
  status text not null default 'running' check (status in ('running','completed','failed')),
  trigger text not null default 'manual',
  locale_scope text[] not null default '{}',
  scores jsonb not null default '{}',
  summary text,
  started_at timestamptz not null default now(),
  finished_at timestamptz
);
create index if not exists seo_runs_project on public.seo_runs (project_id, started_at desc);

create table if not exists public.seo_audits (
  id uuid primary key default gen_random_uuid(),
  run_id uuid not null references public.seo_runs(id) on delete cascade,
  project_id uuid not null references public.projects(id) on delete cascade,
  locale text not null,
  seo_score int not null default 0,
  geo_score int not null default 0,
  local_score int not null default 0,
  scores_detail jsonb not null default '{}',
  gate_fact_passed boolean not null default true,
  audited_at timestamptz not null default now()
);
create index if not exists seo_audits_project on public.seo_audits (project_id, audited_at desc);

create table if not exists public.seo_plan_items (
  id uuid primary key default gen_random_uuid(),
  project_id uuid not null references public.projects(id) on delete cascade,
  run_id uuid references public.seo_runs(id) on delete set null,
  track text not null check (track in ('seo','geo','local')),
  title text not null,
  description text not null default '',
  rationale text not null default '',
  priority int not null default 0,
  effort text not null default 'medium',
  action_kind text not null default 'content'
    check (action_kind in ('content','meta','schema','article','new_page','manual_human')),
  target text,
  status text not null default 'planned'
    check (status in ('planned','in_progress','applied','published','dismissed')),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create index if not exists seo_plan_items_project on public.seo_plan_items (project_id, priority desc);

create table if not exists public.seo_changes (
  id uuid primary key default gen_random_uuid(),
  project_id uuid not null references public.projects(id) on delete cascade,
  run_id uuid references public.seo_runs(id) on delete set null,
  plan_item_id uuid references public.seo_plan_items(id) on delete set null,
  kind text not null,
  target text,
  before jsonb not null default '{}',
  after jsonb not null default '{}',
  verified jsonb not null default '{}',
  reverted boolean not null default false,
  applied_at timestamptz not null default now(),
  published_at timestamptz
);
create index if not exists seo_changes_project on public.seo_changes (project_id, applied_at desc);

create table if not exists public.seo_competitors (
  id uuid primary key default gen_random_uuid(),
  project_id uuid not null references public.projects(id) on delete cascade,
  run_id uuid references public.seo_runs(id) on delete set null,
  name text not null,
  url text,
  location text,
  signals jsonb not null default '{}',
  analysis text not null default '',
  captured_at timestamptz not null default now()
);
create index if not exists seo_competitors_project on public.seo_competitors (project_id, captured_at desc);

-- ── the dedicated SEO/GEO CMS area (agent writes; client+admin CRUD; site consumes) ──
create table if not exists public.seo_page_meta (
  id uuid primary key default gen_random_uuid(),
  project_id uuid not null references public.projects(id) on delete cascade,
  route text not null,
  locale text not null,
  title text not null default '',
  description text not null default '',
  canonical text,
  og jsonb not null default '{}',
  json_ld jsonb not null default '{}',
  robots text,
  status text not null default 'draft' check (status in ('draft','published')),
  updated_by text not null default 'agent',
  updated_at timestamptz not null default now(),
  unique (project_id, route, locale)
);
create index if not exists seo_page_meta_project on public.seo_page_meta (project_id);

create table if not exists public.seo_articles (
  id uuid primary key default gen_random_uuid(),
  project_id uuid not null references public.projects(id) on delete cascade,
  slug text not null,
  locale text not null,
  title text not null default '',
  excerpt text not null default '',
  body text not null default '',
  json_ld jsonb not null default '{}',
  hero_image_url text,
  status text not null default 'draft' check (status in ('draft','published')),
  source_run_id uuid references public.seo_runs(id) on delete set null,
  updated_by text not null default 'agent',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (project_id, slug, locale)
);
create index if not exists seo_articles_project on public.seo_articles (project_id);

-- ── cross-client self-improvement (global) + job queue ──
create table if not exists public.seo_learnings (
  id uuid primary key default gen_random_uuid(),
  scope text not null default 'global',
  category text,
  rule text not null,
  source text,
  confidence text,
  created_at timestamptz not null default now()
);

create table if not exists public.seo_jobs (
  id uuid primary key default gen_random_uuid(),
  project_id uuid not null references public.projects(id) on delete cascade,
  kind text not null default 'run_full' check (kind in ('run_full','run_audit','run_articles')),
  status text not null default 'queued' check (status in ('queued','claimed','done','failed')),
  requested_by text,
  requested_at timestamptz not null default now(),
  claimed_at timestamptz,
  result jsonb not null default '{}'
);
create index if not exists seo_jobs_status on public.seo_jobs (status, requested_at);

-- ── RLS: enabled, service-role only (no public policies; app auth is in code) ──
alter table public.seo_runs        enable row level security;
alter table public.seo_audits      enable row level security;
alter table public.seo_plan_items  enable row level security;
alter table public.seo_changes     enable row level security;
alter table public.seo_competitors enable row level security;
alter table public.seo_page_meta   enable row level security;
alter table public.seo_articles    enable row level security;
alter table public.seo_learnings   enable row level security;
alter table public.seo_jobs        enable row level security;
```

- [ ] **Step 2: Apply via Supabase MCP**

Apply the migration with `mcp__supabase__apply_migration` (name: `2026_06_14_seo_geo`, the SQL above). Per Stefan's standing rule, the controller applies migrations via MCP after writing the file — do not ask.

- [ ] **Step 3: Verify the schema landed**

Run via `mcp__supabase__execute_sql`:
```sql
select table_name from information_schema.tables
where table_schema='public' and table_name like 'seo_%' order by 1;
```
Expected: `seo_articles, seo_audits, seo_changes, seo_competitors, seo_jobs, seo_learnings, seo_page_meta, seo_plan_items, seo_runs` (9 rows). And:
```sql
select column_name from information_schema.columns
where table_name='projects' and column_name like 'seo_%' order by 1;
```
Expected: `seo_blog_route, seo_enabled, seo_last_run_at`.

- [ ] **Step 4: Commit (checkpoint)**

```bash
git add backend/migrations/2026_06_14_seo_geo.sql
git commit -m "feat(seo): add SEO/GEO foundation schema (additive, RLS service-role-only)"
```

---

## Task 2: Pydantic schemas

**Files:**
- Create: `backend/auth_service/models/seo_schemas.py`

- [ ] **Step 1: Write the schemas**

```python
# backend/auth_service/models/seo_schemas.py
"""Pydantic models for the SEO/GEO router. Plain BaseModel (house style)."""
from __future__ import annotations

from pydantic import BaseModel, Field


class SeoOverviewOut(BaseModel):
    enabled: bool
    blog_route: str | None = None
    last_run_at: str | None = None
    seo_score: int | None = None
    geo_score: int | None = None
    local_score: int | None = None
    last_status: str | None = None
    locales: list[str] = Field(default_factory=list)


class SeoPlanItemOut(BaseModel):
    id: str
    track: str
    title: str
    description: str
    rationale: str
    priority: int
    effort: str
    action_kind: str
    target: str | None = None
    status: str


class SeoRunOut(BaseModel):
    id: str
    status: str
    trigger: str
    summary: str | None = None
    scores: dict = Field(default_factory=dict)
    started_at: str
    finished_at: str | None = None


class SeoChangeOut(BaseModel):
    id: str
    kind: str
    target: str | None = None
    before: dict = Field(default_factory=dict)
    after: dict = Field(default_factory=dict)
    verified: dict = Field(default_factory=dict)
    reverted: bool
    applied_at: str
    published_at: str | None = None


class SeoHistoryOut(BaseModel):
    runs: list[SeoRunOut] = Field(default_factory=list)
    changes: list[SeoChangeOut] = Field(default_factory=list)


class SeoCompetitorOut(BaseModel):
    id: str
    name: str
    url: str | None = None
    location: str | None = None
    signals: dict = Field(default_factory=dict)
    analysis: str
    captured_at: str


class SeoPageMetaIn(BaseModel):
    route: str = Field(min_length=1, max_length=2000)
    locale: str = Field(min_length=2, max_length=10)
    title: str = Field(default="", max_length=300)
    description: str = Field(default="", max_length=600)
    canonical: str | None = Field(default=None, max_length=2000)
    og: dict = Field(default_factory=dict)
    json_ld: dict = Field(default_factory=dict)
    robots: str | None = Field(default=None, max_length=200)
    status: str = "draft"


class SeoPageMetaOut(SeoPageMetaIn):
    id: str
    updated_by: str
    updated_at: str


class SeoArticleIn(BaseModel):
    slug: str = Field(min_length=1, max_length=300)
    locale: str = Field(min_length=2, max_length=10)
    title: str = Field(default="", max_length=300)
    excerpt: str = Field(default="", max_length=1000)
    body: str = ""
    json_ld: dict = Field(default_factory=dict)
    hero_image_url: str | None = Field(default=None, max_length=2000)
    status: str = "draft"


class SeoArticleOut(SeoArticleIn):
    id: str
    updated_by: str
    created_at: str
    updated_at: str


class SeoJobIn(BaseModel):
    kind: str = "run_full"


class SeoJobOut(BaseModel):
    id: str
    kind: str
    status: str
    requested_at: str
```

- [ ] **Step 2: Verify it imports**

Run from `backend/`: `python -c "from auth_service.models.seo_schemas import SeoOverviewOut, SeoArticleIn; print('ok')"`
Expected: `ok`

- [ ] **Step 3: Commit (checkpoint)**

```bash
git add backend/auth_service/models/seo_schemas.py
git commit -m "feat(seo): add SEO router Pydantic schemas"
```

---

## Task 3: Repo layer (`seo_repo.py`)

**Files:**
- Create: `backend/auth_service/services/seo_repo.py`
- Test: `backend/auth_service/tests/test_seo_repo.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/auth_service/tests/test_seo_repo.py
from unittest.mock import MagicMock, patch

from auth_service.services import seo_repo


def _sb():
    m = MagicMock()
    for meth in ["table", "select", "eq", "order", "limit", "maybe_single",
                 "insert", "upsert", "update", "delete"]:
        getattr(m, meth).return_value = m
    return m


def test_latest_audit_returns_first_row():
    sb = _sb()
    sb.execute.return_value.data = [{"seo_score": 80, "geo_score": 70, "local_score": 60, "locale": "en"}]
    with patch("auth_service.services.seo_repo.get_supabase_admin", return_value=sb):
        row = seo_repo.latest_audit("proj-1")
    assert row["seo_score"] == 80


def test_upsert_page_meta_sets_updated_by():
    sb = _sb()
    sb.execute.return_value.data = [{"id": "m1", "route": "/", "locale": "en"}]
    with patch("auth_service.services.seo_repo.get_supabase_admin", return_value=sb):
        row = seo_repo.upsert_page_meta("proj-1", {"route": "/", "locale": "en", "title": "Home"}, "client")
    assert row["id"] == "m1"
    args = sb.upsert.call_args[0][0]
    assert args["updated_by"] == "client" and args["project_id"] == "proj-1"
```

- [ ] **Step 2: Run test to verify it fails**

Run from `backend/`: `python -m pytest auth_service/tests/test_seo_repo.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'auth_service.services.seo_repo'`

- [ ] **Step 3: Write the repo**

```python
# backend/auth_service/services/seo_repo.py
"""Supabase access for the SEO/GEO router. Mirrors booking_admin_repo.py."""
from __future__ import annotations

from datetime import UTC, datetime

from .supabase_client import get_supabase_admin


def _now() -> str:
    return datetime.now(UTC).isoformat()


# ── reads (analytical tables; the agent writes these via Supabase MCP) ──
def latest_run(project_id: str) -> dict | None:
    sb = get_supabase_admin()
    res = (sb.table("seo_runs").select("*").eq("project_id", project_id)
           .order("started_at", desc=True).limit(1).execute())
    rows = res.data or []
    return rows[0] if rows else None


def latest_audit(project_id: str) -> dict | None:
    sb = get_supabase_admin()
    res = (sb.table("seo_audits").select("*").eq("project_id", project_id)
           .order("audited_at", desc=True).limit(1).execute())
    rows = res.data or []
    return rows[0] if rows else None


def plan_items(project_id: str) -> list[dict]:
    sb = get_supabase_admin()
    res = (sb.table("seo_plan_items").select("*").eq("project_id", project_id)
           .order("priority", desc=True).execute())
    return res.data or []


def runs(project_id: str, limit: int = 20) -> list[dict]:
    sb = get_supabase_admin()
    res = (sb.table("seo_runs").select("*").eq("project_id", project_id)
           .order("started_at", desc=True).limit(limit).execute())
    return res.data or []


def changes(project_id: str, limit: int = 50) -> list[dict]:
    sb = get_supabase_admin()
    res = (sb.table("seo_changes").select("*").eq("project_id", project_id)
           .order("applied_at", desc=True).limit(limit).execute())
    return res.data or []


def competitors(project_id: str, limit: int = 50) -> list[dict]:
    sb = get_supabase_admin()
    res = (sb.table("seo_competitors").select("*").eq("project_id", project_id)
           .order("captured_at", desc=True).limit(limit).execute())
    return res.data or []


# ── content CRUD (page_meta + articles; humans via dashboard, agent via bearer) ──
def list_page_meta(project_id: str) -> list[dict]:
    sb = get_supabase_admin()
    res = sb.table("seo_page_meta").select("*").eq("project_id", project_id).execute()
    return res.data or []


def upsert_page_meta(project_id: str, fields: dict, updated_by: str) -> dict:
    sb = get_supabase_admin()
    payload = {**fields, "project_id": project_id, "updated_by": updated_by, "updated_at": _now()}
    res = sb.table("seo_page_meta").upsert(payload, on_conflict="project_id,route,locale").execute()
    return (res.data or [{}])[0]


def delete_page_meta(project_id: str, meta_id: str) -> None:
    sb = get_supabase_admin()
    sb.table("seo_page_meta").delete().eq("project_id", project_id).eq("id", meta_id).execute()


def list_articles(project_id: str) -> list[dict]:
    sb = get_supabase_admin()
    res = sb.table("seo_articles").select("*").eq("project_id", project_id).execute()
    return res.data or []


def create_article(project_id: str, fields: dict, updated_by: str) -> dict:
    sb = get_supabase_admin()
    payload = {**fields, "project_id": project_id, "updated_by": updated_by,
               "created_at": _now(), "updated_at": _now()}
    res = sb.table("seo_articles").insert(payload).execute()
    return (res.data or [{}])[0]


def update_article(project_id: str, article_id: str, fields: dict, updated_by: str) -> dict:
    sb = get_supabase_admin()
    payload = {**fields, "updated_by": updated_by, "updated_at": _now()}
    res = (sb.table("seo_articles").update(payload)
           .eq("project_id", project_id).eq("id", article_id).execute())
    return (res.data or [{}])[0]


def delete_article(project_id: str, article_id: str) -> None:
    sb = get_supabase_admin()
    sb.table("seo_articles").delete().eq("project_id", project_id).eq("id", article_id).execute()


def enqueue_job(project_id: str, kind: str, requested_by: str) -> dict:
    sb = get_supabase_admin()
    res = sb.table("seo_jobs").insert(
        {"project_id": project_id, "kind": kind, "requested_by": requested_by}).execute()
    return (res.data or [{}])[0]


# ── public site consumer (published only) ──
def published_meta(project_id: str, route: str, locale: str) -> dict | None:
    sb = get_supabase_admin()
    res = (sb.table("seo_page_meta").select("*").eq("project_id", project_id)
           .eq("route", route).eq("locale", locale).eq("status", "published").limit(1).execute())
    rows = res.data or []
    return rows[0] if rows else None


def published_articles(project_id: str, locale: str) -> list[dict]:
    sb = get_supabase_admin()
    res = (sb.table("seo_articles").select("*").eq("project_id", project_id)
           .eq("locale", locale).eq("status", "published").execute())
    return res.data or []
```

- [ ] **Step 4: Run test to verify it passes**

Run from `backend/`: `python -m pytest auth_service/tests/test_seo_repo.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit (checkpoint)**

```bash
git add backend/auth_service/services/seo_repo.py backend/auth_service/tests/test_seo_repo.py
git commit -m "feat(seo): add seo_repo Supabase access layer + tests"
```

---

## Task 4: Router — read endpoints (overview / plan / history / competitors)

**Files:**
- Create: `backend/auth_service/routers/seo.py`
- Test: `backend/auth_service/tests/test_seo_router.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/auth_service/tests/test_seo_router.py
from unittest.mock import patch

from fastapi.testclient import TestClient

from auth_service.main import app
from auth_service.models.schemas import UserOut

client = TestClient(app)


def _auth(monkeypatch, admin=True):
    async def fake(request):
        return UserOut(id="u1", email="a@b.com", is_admin=admin)
    monkeypatch.setattr("auth_service.routers.seo.user_via_bearer_or_session", fake)
    monkeypatch.setattr(
        "auth_service.routers.seo.require_project_access",
        lambda slug, u: {"id": f"proj-{slug}", "slug": slug, "name": slug.title(),
                         "locales": ["en", "nl"]},
    )


def test_overview_empty(monkeypatch):
    _auth(monkeypatch)
    with (
        patch("auth_service.routers.seo.seo_repo.latest_run", return_value=None),
        patch("auth_service.routers.seo.seo_repo.latest_audit", return_value=None),
        patch("auth_service.routers.seo._project_flags", return_value={"seo_enabled": False, "seo_blog_route": None, "seo_last_run_at": None}),
    ):
        r = client.get("/projects/acme/seo/overview")
    assert r.status_code == 200
    body = r.json()
    assert body["enabled"] is False and body["seo_score"] is None
    assert body["locales"] == ["en", "nl"]


def test_plan_returns_items(monkeypatch):
    _auth(monkeypatch)
    with patch("auth_service.routers.seo.seo_repo.plan_items", return_value=[
        {"id": "i1", "track": "geo", "title": "Add stats", "description": "", "rationale": "",
         "priority": 9, "effort": "low", "action_kind": "content", "target": "/", "status": "planned"}
    ]):
        r = client.get("/projects/acme/seo/plan")
    assert r.status_code == 200
    assert r.json()[0]["title"] == "Add stats"
```

- [ ] **Step 2: Run test to verify it fails**

Run from `backend/`: `python -m pytest auth_service/tests/test_seo_router.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'auth_service.routers.seo'`

- [ ] **Step 3: Write the router (read endpoints)**

```python
# backend/auth_service/routers/seo.py
"""SEO/GEO router: dashboard reads + human CRUD + public site-consumer endpoints.

Auth: human + agent endpoints use user_via_bearer_or_session + require_project_access
(session for the dashboard, admin bearer for the agent). Public consumer endpoints
are unauthenticated (published content only), mirroring content.py.
"""
from __future__ import annotations

from fastapi import APIRouter, Request

from ..models.seo_schemas import (
    SeoCompetitorOut, SeoHistoryOut, SeoOverviewOut, SeoPlanItemOut,
)
from ..services import seo_repo
from ..services.supabase_client import get_supabase_admin
from .deps import require_project_access, user_via_bearer_or_session

router = APIRouter(tags=["seo"])


async def _scope(project_slug: str, request: Request) -> dict:
    """Auth + project scope. Returns the project row."""
    user = await user_via_bearer_or_session(request)
    return require_project_access(project_slug, user)


def _project_flags(project_id: str) -> dict:
    sb = get_supabase_admin()
    res = (sb.table("projects")
           .select("seo_enabled, seo_blog_route, seo_last_run_at")
           .eq("id", project_id).maybe_single().execute())
    return res.data or {"seo_enabled": False, "seo_blog_route": None, "seo_last_run_at": None}


@router.get("/projects/{project_slug}/seo/overview", response_model=SeoOverviewOut)
async def overview(project_slug: str, request: Request) -> SeoOverviewOut:
    project = await _scope(project_slug, request)
    flags = _project_flags(project["id"])
    run = seo_repo.latest_run(project["id"])
    audit = seo_repo.latest_audit(project["id"])
    return SeoOverviewOut(
        enabled=bool(flags.get("seo_enabled")),
        blog_route=flags.get("seo_blog_route"),
        last_run_at=flags.get("seo_last_run_at"),
        seo_score=(audit or {}).get("seo_score") if audit else None,
        geo_score=(audit or {}).get("geo_score") if audit else None,
        local_score=(audit or {}).get("local_score") if audit else None,
        last_status=(run or {}).get("status") if run else None,
        locales=list(project.get("locales") or []),
    )


@router.get("/projects/{project_slug}/seo/plan", response_model=list[SeoPlanItemOut])
async def plan(project_slug: str, request: Request) -> list[SeoPlanItemOut]:
    project = await _scope(project_slug, request)
    return [SeoPlanItemOut(**it) for it in seo_repo.plan_items(project["id"])]


@router.get("/projects/{project_slug}/seo/history", response_model=SeoHistoryOut)
async def history(project_slug: str, request: Request) -> SeoHistoryOut:
    project = await _scope(project_slug, request)
    return SeoHistoryOut(
        runs=seo_repo.runs(project["id"]),
        changes=seo_repo.changes(project["id"]),
    )


@router.get("/projects/{project_slug}/seo/competitors", response_model=list[SeoCompetitorOut])
async def competitors(project_slug: str, request: Request) -> list[SeoCompetitorOut]:
    project = await _scope(project_slug, request)
    return [SeoCompetitorOut(**c) for c in seo_repo.competitors(project["id"])]
```

- [ ] **Step 4: Run test to verify it passes**

Run from `backend/`: `python -m pytest auth_service/tests/test_seo_router.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit (checkpoint)**

```bash
git add backend/auth_service/routers/seo.py backend/auth_service/tests/test_seo_router.py
git commit -m "feat(seo): add SEO router read endpoints (overview/plan/history/competitors)"
```

---

## Task 5: Router — content CRUD (page_meta + articles)

**Files:**
- Modify: `backend/auth_service/routers/seo.py`
- Test: `backend/auth_service/tests/test_seo_router.py`

- [ ] **Step 1: Write the failing tests (append)**

```python
def test_put_page_meta(monkeypatch):
    _auth(monkeypatch)
    with patch("auth_service.routers.seo.seo_repo.upsert_page_meta",
               return_value={"id": "m1", "route": "/", "locale": "en", "title": "Home",
                             "description": "", "canonical": None, "og": {}, "json_ld": {},
                             "robots": None, "status": "draft", "updated_by": "a@b.com",
                             "updated_at": "2026-06-14T00:00:00+00:00"}) as up:
        r = client.put("/projects/acme/seo/meta",
                       json={"route": "/", "locale": "en", "title": "Home"})
    assert r.status_code == 200 and r.json()["id"] == "m1"
    assert up.call_args[0][2] == "a@b.com"  # updated_by = acting user email


def test_create_article(monkeypatch):
    _auth(monkeypatch)
    with patch("auth_service.routers.seo.seo_repo.create_article",
               return_value={"id": "a1", "slug": "guide", "locale": "en", "title": "Guide",
                             "excerpt": "", "body": "x", "json_ld": {}, "hero_image_url": None,
                             "status": "draft", "updated_by": "a@b.com",
                             "created_at": "t", "updated_at": "t"}):
        r = client.post("/projects/acme/seo/articles",
                        json={"slug": "guide", "locale": "en", "title": "Guide", "body": "x"})
    assert r.status_code == 200 and r.json()["slug"] == "guide"


def test_delete_article(monkeypatch):
    _auth(monkeypatch)
    with patch("auth_service.routers.seo.seo_repo.delete_article") as d:
        r = client.delete("/projects/acme/seo/articles/a1")
    assert r.status_code == 200 and r.json()["deleted"] is True
    d.assert_called_once()
```

- [ ] **Step 2: Run to verify they fail**

Run: `python -m pytest auth_service/tests/test_seo_router.py -k "page_meta or article" -v`
Expected: FAIL — 404 (routes not defined yet)

- [ ] **Step 3: Add the CRUD endpoints (append to `seo.py`)**

```python
# append imports at top of seo.py:
from fastapi import HTTPException, status
from ..models.seo_schemas import (
    SeoArticleIn, SeoArticleOut, SeoJobIn, SeoJobOut, SeoPageMetaIn, SeoPageMetaOut,
)


@router.get("/projects/{project_slug}/seo/meta", response_model=list[SeoPageMetaOut])
async def list_meta(project_slug: str, request: Request) -> list[SeoPageMetaOut]:
    project = await _scope(project_slug, request)
    return [SeoPageMetaOut(**m) for m in seo_repo.list_page_meta(project["id"])]


@router.put("/projects/{project_slug}/seo/meta", response_model=SeoPageMetaOut)
async def put_meta(project_slug: str, body: SeoPageMetaIn, request: Request) -> SeoPageMetaOut:
    user = await user_via_bearer_or_session(request)
    project = require_project_access(project_slug, user)
    row = seo_repo.upsert_page_meta(project["id"], body.model_dump(), user.email)
    return SeoPageMetaOut(**row)


@router.delete("/projects/{project_slug}/seo/meta/{meta_id}")
async def del_meta(project_slug: str, meta_id: str, request: Request) -> dict:
    project = await _scope(project_slug, request)
    seo_repo.delete_page_meta(project["id"], meta_id)
    return {"deleted": True}


@router.get("/projects/{project_slug}/seo/articles", response_model=list[SeoArticleOut])
async def list_articles(project_slug: str, request: Request) -> list[SeoArticleOut]:
    project = await _scope(project_slug, request)
    return [SeoArticleOut(**a) for a in seo_repo.list_articles(project["id"])]


@router.post("/projects/{project_slug}/seo/articles", response_model=SeoArticleOut)
async def create_article(project_slug: str, body: SeoArticleIn, request: Request) -> SeoArticleOut:
    user = await user_via_bearer_or_session(request)
    project = require_project_access(project_slug, user)
    row = seo_repo.create_article(project["id"], body.model_dump(), user.email)
    return SeoArticleOut(**row)


@router.put("/projects/{project_slug}/seo/articles/{article_id}", response_model=SeoArticleOut)
async def update_article(project_slug: str, article_id: str, body: SeoArticleIn,
                         request: Request) -> SeoArticleOut:
    user = await user_via_bearer_or_session(request)
    project = require_project_access(project_slug, user)
    row = seo_repo.update_article(project["id"], article_id, body.model_dump(), user.email)
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Article not found")
    return SeoArticleOut(**row)


@router.delete("/projects/{project_slug}/seo/articles/{article_id}")
async def del_article(project_slug: str, article_id: str, request: Request) -> dict:
    project = await _scope(project_slug, request)
    seo_repo.delete_article(project["id"], article_id)
    return {"deleted": True}


@router.post("/projects/{project_slug}/seo/jobs", response_model=SeoJobOut)
async def enqueue_job(project_slug: str, body: SeoJobIn, request: Request) -> SeoJobOut:
    user = await user_via_bearer_or_session(request)
    project = require_project_access(project_slug, user)
    row = seo_repo.enqueue_job(project["id"], body.kind, user.email)
    return SeoJobOut(id=row["id"], kind=row["kind"], status=row["status"],
                     requested_at=row["requested_at"])
```

- [ ] **Step 4: Run to verify they pass**

Run: `python -m pytest auth_service/tests/test_seo_router.py -v`
Expected: PASS (all)

- [ ] **Step 5: Commit (checkpoint)**

```bash
git add backend/auth_service/routers/seo.py backend/auth_service/tests/test_seo_router.py
git commit -m "feat(seo): add page_meta + article CRUD + job enqueue endpoints"
```

---

## Task 6: Router — public site-consumer endpoints

**Files:**
- Modify: `backend/auth_service/routers/seo.py`
- Test: `backend/auth_service/tests/test_seo_router.py`

- [ ] **Step 1: Write the failing tests (append)**

```python
def test_public_meta_published(monkeypatch):
    # resolve slug->id without auth
    monkeypatch.setattr("auth_service.routers.seo._project_id_by_slug",
                        lambda slug: "proj-acme")
    with patch("auth_service.routers.seo.seo_repo.published_meta",
               return_value={"title": "Home", "description": "d", "canonical": "/",
                             "og": {}, "json_ld": {}, "robots": None}):
        r = client.get("/projects/acme/seo/public/meta?route=/&locale=en")
    assert r.status_code == 200 and r.json()["title"] == "Home"


def test_public_meta_missing_returns_empty(monkeypatch):
    monkeypatch.setattr("auth_service.routers.seo._project_id_by_slug", lambda slug: "proj-acme")
    with patch("auth_service.routers.seo.seo_repo.published_meta", return_value=None):
        r = client.get("/projects/acme/seo/public/meta?route=/missing&locale=en")
    assert r.status_code == 200 and r.json() == {}
```

- [ ] **Step 2: Run to verify they fail**

Run: `python -m pytest auth_service/tests/test_seo_router.py -k public -v`
Expected: FAIL (routes not defined)

- [ ] **Step 3: Add the public endpoints (append to `seo.py`)**

```python
def _project_id_by_slug(slug: str) -> str | None:
    sb = get_supabase_admin()
    res = (sb.table("projects").select("id").eq("slug", slug)
           .eq("is_active", True).maybe_single().execute())
    return (res.data or {}).get("id")


@router.get("/projects/{project_slug}/seo/public/meta")
async def public_meta(project_slug: str, route: str, locale: str) -> dict:
    pid = _project_id_by_slug(project_slug)
    if not pid:
        return {}
    return seo_repo.published_meta(pid, route, locale) or {}


@router.get("/projects/{project_slug}/seo/public/articles")
async def public_articles(project_slug: str, locale: str) -> dict:
    pid = _project_id_by_slug(project_slug)
    if not pid:
        return {"articles": []}
    return {"articles": seo_repo.published_articles(pid, locale)}
```

- [ ] **Step 4: Run to verify they pass**

Run: `python -m pytest auth_service/tests/test_seo_router.py -v`
Expected: PASS (all)

- [ ] **Step 5: Commit (checkpoint)**

```bash
git add backend/auth_service/routers/seo.py backend/auth_service/tests/test_seo_router.py
git commit -m "feat(seo): add public site-consumer meta + articles endpoints"
```

---

## Task 7: Register the router

**Files:**
- Modify: `backend/auth_service/main.py:18-27` (imports) and `:133-144` (registration)

- [ ] **Step 1: Add the import**

In the router-imports block (alongside `from .routers.booking_admin import router as booking_admin_router`), add:
```python
from .routers.seo import router as seo_router
```

- [ ] **Step 2: Register it**

In the `app.include_router(...)` block (after `app.include_router(booking_admin_router)`), add:
```python
app.include_router(seo_router)
```

- [ ] **Step 3: Smoke test**

```python
# append to test_seo_router.py
def test_router_registered():
    paths = {r.path for r in app.routes}
    assert "/projects/{project_slug}/seo/overview" in paths
    assert "/projects/{project_slug}/seo/public/meta" in paths
```
Run: `python -m pytest auth_service/tests/test_seo_router.py::test_router_registered -v`
Expected: PASS

- [ ] **Step 4: Full backend suite green**

Run from `backend/`: `python -m pytest auth_service/tests/ -q`
Expected: all pass (existing + new SEO tests), coverage ≥ 60%.

- [ ] **Step 5: Commit (checkpoint)**

```bash
git add backend/auth_service/main.py backend/auth_service/tests/test_seo_router.py
git commit -m "feat(seo): register SEO router in app"
```

---

## Task 8: Frontend — types + api helpers

**Files:**
- Create: `frontend/src/components/dashboard/seo/types.ts`
- Create: `frontend/src/components/dashboard/seo/api.ts`

- [ ] **Step 1: Write the types**

```typescript
// frontend/src/components/dashboard/seo/types.ts
export interface SeoOverview {
  enabled: boolean;
  blog_route: string | null;
  last_run_at: string | null;
  seo_score: number | null;
  geo_score: number | null;
  local_score: number | null;
  last_status: string | null;
  locales: string[];
}

export interface SeoPlanItem {
  id: string;
  track: "seo" | "geo" | "local";
  title: string;
  description: string;
  rationale: string;
  priority: number;
  effort: string;
  action_kind: "content" | "meta" | "schema" | "article" | "new_page" | "manual_human";
  target: string | null;
  status: "planned" | "in_progress" | "applied" | "published" | "dismissed";
}

export interface SeoRun {
  id: string;
  status: string;
  trigger: string;
  summary: string | null;
  scores: Record<string, number>;
  started_at: string;
  finished_at: string | null;
}

export interface SeoChange {
  id: string;
  kind: string;
  target: string | null;
  before: Record<string, unknown>;
  after: Record<string, unknown>;
  verified: Record<string, unknown>;
  reverted: boolean;
  applied_at: string;
  published_at: string | null;
}

export interface SeoHistory {
  runs: SeoRun[];
  changes: SeoChange[];
}

export interface SeoCompetitor {
  id: string;
  name: string;
  url: string | null;
  location: string | null;
  signals: Record<string, unknown>;
  analysis: string;
  captured_at: string;
}

export interface SeoArticle {
  id: string;
  slug: string;
  locale: string;
  title: string;
  excerpt: string;
  body: string;
  json_ld: Record<string, unknown>;
  hero_image_url: string | null;
  status: "draft" | "published";
  updated_by: string;
  created_at: string;
  updated_at: string;
}
```

- [ ] **Step 2: Write the api helpers**

```typescript
// frontend/src/components/dashboard/seo/api.ts
import type {
  SeoArticle, SeoCompetitor, SeoHistory, SeoOverview, SeoPlanItem,
} from "./types";

async function throwOnError(r: Response): Promise<void> {
  if (!r.ok) {
    const body = (await r.json().catch(() => ({}))) as { detail?: string };
    throw new Error(body.detail ?? `Request failed (${r.status})`);
  }
}

export async function getOverview(slug: string): Promise<SeoOverview> {
  const r = await fetch(`/api/projects/${slug}/seo/overview`, { credentials: "include" });
  await throwOnError(r);
  return r.json();
}

export async function getPlan(slug: string): Promise<SeoPlanItem[]> {
  const r = await fetch(`/api/projects/${slug}/seo/plan`, { credentials: "include" });
  await throwOnError(r);
  return r.json();
}

export async function getHistory(slug: string): Promise<SeoHistory> {
  const r = await fetch(`/api/projects/${slug}/seo/history`, { credentials: "include" });
  await throwOnError(r);
  return r.json();
}

export async function getCompetitors(slug: string): Promise<SeoCompetitor[]> {
  const r = await fetch(`/api/projects/${slug}/seo/competitors`, { credentials: "include" });
  await throwOnError(r);
  return r.json();
}

export async function getArticles(slug: string): Promise<SeoArticle[]> {
  const r = await fetch(`/api/projects/${slug}/seo/articles`, { credentials: "include" });
  await throwOnError(r);
  return r.json();
}

export async function deleteArticle(slug: string, id: string): Promise<void> {
  const r = await fetch(`/api/projects/${slug}/seo/articles/${id}`, {
    method: "DELETE", credentials: "include",
  });
  await throwOnError(r);
}

export async function enqueueRun(slug: string, kind = "run_full"): Promise<{ id: string }> {
  const r = await fetch(`/api/projects/${slug}/seo/jobs`, {
    method: "POST", credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ kind }),
  });
  await throwOnError(r);
  return r.json();
}
```

- [ ] **Step 3: Type-check**

Run from `frontend/`: `npx tsc --noEmit`
Expected: no errors in `seo/types.ts` or `seo/api.ts`.

- [ ] **Step 4: Commit (checkpoint)**

```bash
git add frontend/src/components/dashboard/seo/types.ts frontend/src/components/dashboard/seo/api.ts
git commit -m "feat(seo): add dashboard SEO types + api helpers"
```

---

## Task 9: Frontend — SeoSection shell + tabs (read-only)

**Files:**
- Create: `frontend/src/components/dashboard/seo/SeoSection.tsx`
- Create: `frontend/src/components/dashboard/seo/{Overview,Plan,History,Articles,Competitors,Settings}Tab.tsx`
- Test: `frontend/src/components/dashboard/seo/SeoSection.test.tsx`

- [ ] **Step 1: Write the failing test**

```tsx
// frontend/src/components/dashboard/seo/SeoSection.test.tsx
import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { SeoSection } from "./SeoSection";

beforeEach(() => {
  global.fetch = vi.fn().mockResolvedValue({
    ok: true,
    json: async () => ({
      enabled: true, blog_route: null, last_run_at: null,
      seo_score: 82, geo_score: 71, local_score: 64, last_status: "completed", locales: ["en"],
    }),
  });
});

describe("SeoSection", () => {
  it("renders the tab strip", async () => {
    render(<SeoSection projectSlug="acme" isAdmin />);
    expect(screen.getByRole("button", { name: /overview/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /plan/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /competitors/i })).toBeInTheDocument();
  });

  it("switches to the Plan tab on click", async () => {
    render(<SeoSection projectSlug="acme" isAdmin />);
    fireEvent.click(screen.getByRole("button", { name: /plan/i }));
    expect(await screen.findByText(/no plan items yet/i)).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run to verify it fails**

Run from `frontend/`: `npm run test -- seo/SeoSection`
Expected: FAIL — cannot resolve `./SeoSection`.

- [ ] **Step 3: Write the six tab components (read-only)**

```tsx
// OverviewTab.tsx
import { useQuery } from "@/hooks/useQuery";
import { getOverview, enqueueRun } from "./api";
import { useState } from "react";

export function OverviewTab({ projectSlug }: { projectSlug: string }) {
  const { data, loading } = useQuery(`seo-overview:${projectSlug}`,
    () => getOverview(projectSlug), { ttl: 60 * 1000 });
  const [queued, setQueued] = useState(false);
  if (loading) return <p className="text-sm text-zinc-500">Loading…</p>;
  if (!data) return <p className="text-sm text-zinc-500">No data.</p>;
  const dial = (label: string, v: number | null) => (
    <div className="rounded-xl border border-zinc-200 p-4 dark:border-zinc-800">
      <div className="text-xs uppercase tracking-wide text-zinc-500">{label}</div>
      <div className="mt-1 text-3xl font-semibold">{v ?? "—"}</div>
    </div>
  );
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
        {dial("SEO", data.seo_score)}
        {dial("GEO (AI readiness)", data.geo_score)}
        {dial("Local", data.local_score)}
      </div>
      <button
        type="button"
        disabled={queued}
        onClick={() => { enqueueRun(projectSlug).then(() => setQueued(true)).catch(() => {}); }}
        className="rounded-lg bg-zinc-900 px-4 py-2 text-sm font-medium text-white hover:bg-zinc-700 disabled:opacity-40 dark:bg-zinc-700 dark:hover:bg-zinc-600"
      >
        {queued ? "Queued ✓" : "Run SEO agent"}
      </button>
    </div>
  );
}
```

```tsx
// PlanTab.tsx
import { useQuery } from "@/hooks/useQuery";
import { getPlan } from "./api";

export function PlanTab({ projectSlug }: { projectSlug: string }) {
  const { data, loading } = useQuery(`seo-plan:${projectSlug}`, () => getPlan(projectSlug), { ttl: 60 * 1000 });
  if (loading) return <p className="text-sm text-zinc-500">Loading…</p>;
  if (!data || data.length === 0) return <p className="text-sm text-zinc-500">No plan items yet. Run the agent.</p>;
  return (
    <ul className="space-y-2">
      {data.map((it) => (
        <li key={it.id} className="rounded-lg border border-zinc-200 p-3 dark:border-zinc-800">
          <div className="flex items-center gap-2">
            <span className="rounded bg-zinc-100 px-2 py-0.5 text-xs uppercase dark:bg-zinc-800">{it.track}</span>
            <span className="font-medium">{it.title}</span>
            <span className="ml-auto text-xs text-zinc-500">{it.status}</span>
          </div>
          {it.description && <p className="mt-1 text-sm text-zinc-600 dark:text-zinc-400">{it.description}</p>}
        </li>
      ))}
    </ul>
  );
}
```

```tsx
// HistoryTab.tsx
import { useQuery } from "@/hooks/useQuery";
import { getHistory } from "./api";

export function HistoryTab({ projectSlug }: { projectSlug: string }) {
  const { data, loading } = useQuery(`seo-history:${projectSlug}`, () => getHistory(projectSlug), { ttl: 60 * 1000 });
  if (loading) return <p className="text-sm text-zinc-500">Loading…</p>;
  if (!data || data.runs.length === 0) return <p className="text-sm text-zinc-500">No runs yet.</p>;
  return (
    <ul className="space-y-2">
      {data.runs.map((r) => (
        <li key={r.id} className="rounded-lg border border-zinc-200 p-3 dark:border-zinc-800">
          <div className="flex items-center gap-2 text-sm">
            <span className="font-medium">{r.status}</span>
            <span className="text-zinc-500">{new Date(r.started_at).toLocaleString()}</span>
          </div>
          {r.summary && <p className="mt-1 text-sm text-zinc-600 dark:text-zinc-400">{r.summary}</p>}
        </li>
      ))}
    </ul>
  );
}
```

```tsx
// ArticlesTab.tsx
import { useQuery } from "@/hooks/useQuery";
import { getArticles } from "./api";

export function ArticlesTab({ projectSlug }: { projectSlug: string }) {
  const { data, loading } = useQuery(`seo-articles:${projectSlug}`, () => getArticles(projectSlug), { ttl: 60 * 1000 });
  if (loading) return <p className="text-sm text-zinc-500">Loading…</p>;
  if (!data || data.length === 0) return <p className="text-sm text-zinc-500">No articles yet.</p>;
  return (
    <ul className="space-y-2">
      {data.map((a) => (
        <li key={a.id} className="rounded-lg border border-zinc-200 p-3 dark:border-zinc-800">
          <span className="font-medium">{a.title}</span>
          <span className="ml-2 text-xs text-zinc-500">{a.locale} · {a.status}</span>
        </li>
      ))}
    </ul>
  );
}
```

```tsx
// CompetitorsTab.tsx
import { useQuery } from "@/hooks/useQuery";
import { getCompetitors } from "./api";

export function CompetitorsTab({ projectSlug }: { projectSlug: string }) {
  const { data, loading } = useQuery(`seo-competitors:${projectSlug}`, () => getCompetitors(projectSlug), { ttl: 60 * 1000 });
  if (loading) return <p className="text-sm text-zinc-500">Loading…</p>;
  if (!data || data.length === 0) return <p className="text-sm text-zinc-500">No competitor analysis yet.</p>;
  return (
    <ul className="space-y-2">
      {data.map((c) => (
        <li key={c.id} className="rounded-lg border border-zinc-200 p-3 dark:border-zinc-800">
          <div className="font-medium">{c.name}</div>
          {c.analysis && <p className="mt-1 text-sm text-zinc-600 dark:text-zinc-400">{c.analysis}</p>}
        </li>
      ))}
    </ul>
  );
}
```

```tsx
// SettingsTab.tsx  (read-only placeholder in Plan 1; toggle wired in Plan 2)
export function SettingsTab({ projectSlug }: { projectSlug: string }) {
  return (
    <p className="text-sm text-zinc-500">
      SEO settings for <span className="font-mono">{projectSlug}</span> appear here once the
      agent has run (blog route, locale scope, enable toggle).
    </p>
  );
}
```

- [ ] **Step 4: Write the SeoSection shell**

```tsx
// SeoSection.tsx
"use client";
import { useState } from "react";
import { motion, useReducedMotion } from "motion/react";
import { OverviewTab } from "./OverviewTab";
import { PlanTab } from "./PlanTab";
import { HistoryTab } from "./HistoryTab";
import { ArticlesTab } from "./ArticlesTab";
import { CompetitorsTab } from "./CompetitorsTab";
import { SettingsTab } from "./SettingsTab";

type Tab = "overview" | "plan" | "history" | "articles" | "competitors" | "settings";
const TABS: { key: Tab; label: string }[] = [
  { key: "overview", label: "Overview" },
  { key: "plan", label: "Plan" },
  { key: "history", label: "History" },
  { key: "articles", label: "Articles" },
  { key: "competitors", label: "Competitors" },
  { key: "settings", label: "Settings" },
];

export function SeoSection({ projectSlug }: { projectSlug: string; isAdmin: boolean }) {
  const [activeTab, setActiveTab] = useState<Tab>("overview");
  const reduce = useReducedMotion();
  return (
    <div>
      <nav
        aria-label="SEO & GEO tabs"
        className="no-scrollbar mb-6 flex gap-1 overflow-x-auto overflow-y-hidden border-b border-zinc-200 pb-px dark:border-zinc-800"
      >
        {TABS.map((tab) => {
          const isActive = activeTab === tab.key;
          return (
            <button
              key={tab.key}
              type="button"
              onClick={() => setActiveTab(tab.key)}
              aria-current={isActive ? "page" : undefined}
              className="relative shrink-0 cursor-pointer rounded-t-md px-3 py-2 text-sm font-medium whitespace-nowrap"
            >
              <span className={"transition-colors duration-150 " + (isActive
                ? "text-zinc-900 dark:text-zinc-100"
                : "text-zinc-500 hover:text-zinc-800 dark:text-zinc-400 dark:hover:text-zinc-200")}>
                {tab.label}
              </span>
              {isActive && (
                <motion.span
                  layoutId="seo-tabs-underline"
                  className="absolute inset-x-2 -bottom-px h-[2px] rounded-full bg-zinc-900 dark:bg-zinc-100"
                  transition={reduce ? { duration: 0 } : { type: "spring", stiffness: 480, damping: 36, mass: 0.6 }}
                />
              )}
            </button>
          );
        })}
      </nav>
      {activeTab === "overview" && <OverviewTab projectSlug={projectSlug} />}
      {activeTab === "plan" && <PlanTab projectSlug={projectSlug} />}
      {activeTab === "history" && <HistoryTab projectSlug={projectSlug} />}
      {activeTab === "articles" && <ArticlesTab projectSlug={projectSlug} />}
      {activeTab === "competitors" && <CompetitorsTab projectSlug={projectSlug} />}
      {activeTab === "settings" && <SettingsTab projectSlug={projectSlug} />}
    </div>
  );
}
```

- [ ] **Step 5: Run to verify the test passes**

Run from `frontend/`: `npm run test -- seo/SeoSection`
Expected: PASS (2 passed)

- [ ] **Step 6: Commit (checkpoint)**

```bash
git add frontend/src/components/dashboard/seo/
git commit -m "feat(seo): add read-only SeoSection + tabs"
```

---

## Task 10: Wire the section into the dashboard + cap

**Files:**
- Modify: `frontend/src/components/dashboard/sectionConfig.ts`
- Modify: `frontend/src/app/dashboard/[projectSlug]/page.tsx`

- [ ] **Step 1: Add the section to `sectionConfig.ts`**

Add `"seo"` to the `SectionKey` union (line 10):
```typescript
export type SectionKey = "dashboard" | "cms" | "autofix" | "bookings" | "seo" | "settings";
```
Add `seoEnabled` to the `SectionCaps` type (find it in the same file — it currently has `bookingEnabled`):
```typescript
export interface SectionCaps {
  bookingEnabled: boolean;
  seoEnabled: boolean;
}
```
Import `Search` from lucide-react (alongside the existing icon imports) and add the row to `PROJECT_SECTIONS` (after the bookings row):
```typescript
  { key: "seo", label: "SEO & GEO", icon: Search, requiresCap: "seoEnabled" },
```

- [ ] **Step 2: Thread the `seoEnabled` cap**

Find where `caps` is built and passed to `visibleSections`/`isAccessibleView`:
Run from `frontend/`: `grep -rn "bookingEnabled" src/app/dashboard`
At each site that constructs the caps object for `visibleSections(isAdmin, caps)`, add `seoEnabled` sourced from the project's SEO overview. Concretely, where `bookingEnabled` is set from a fetched value, add a sibling fetch of `getOverview(projectSlug)` and set `seoEnabled: overview?.enabled ?? false`. (Admins always see the tab via the `!isAdmin` short-circuit in `visibleSections`, so a missing cap never hides it from Stefan.)

- [ ] **Step 3: Render the section in `page.tsx`**

Add the import (alongside the other section imports near line 13):
```typescript
import { SeoSection } from "@/components/dashboard/seo/SeoSection";
```
Add the conditional render (after the `bookings` block, ~line 130):
```tsx
{activeView === "seo" && (
  <SeoSection projectSlug={projectSlug} isAdmin={isAdmin} />
)}
```

- [ ] **Step 4: Build + full frontend test suite**

Run from `frontend/`:
```bash
npm run test -- seo/
npm run build
```
Expected: SEO tests pass; `next build` exits 0 with no type errors.

> **Note (Stefan's rule):** `npm run build` kills a running `next dev` on :3000 — restart `npm run dev` after if you were serving.

- [ ] **Step 5: Commit (checkpoint)**

```bash
git add frontend/src/components/dashboard/sectionConfig.ts "frontend/src/app/dashboard/[projectSlug]/page.tsx"
git commit -m "feat(seo): wire SEO & GEO section into the dashboard"
```

---

## Task 11: End-to-end manual verification

**Files:** none (verification only)

- [ ] **Step 1: Seed a fake run for a real project**

Via `mcp__supabase__execute_sql` (use a real project id from `select id, slug from projects limit 5;`):
```sql
with r as (
  insert into seo_runs (project_id, status, summary, scores)
  values ('<PROJECT_ID>', 'completed', 'Seed run for UI check', '{"seo":82,"geo":71}'::jsonb)
  returning id, project_id)
insert into seo_audits (run_id, project_id, locale, seo_score, geo_score, local_score)
select id, project_id, 'en', 82, 71, 64 from r;
update projects set seo_enabled = true, seo_last_run_at = now() where id = '<PROJECT_ID>';
insert into seo_plan_items (project_id, track, title, description, priority, action_kind, target)
values ('<PROJECT_ID>', 'geo', 'Add a sourced statistic to the homepage hero',
        'Adds one real, attributed stat — the highest-impact GEO lever.', 9, 'content', '/');
```

- [ ] **Step 2: Verify in the dashboard**

Start dev servers (`make dev` or the two commands from project memory). Log in, open the seeded project, confirm the **SEO & GEO** tab appears, the Overview shows 82 / 71 / 64, Plan shows the seeded item, History shows the run.

- [ ] **Step 3: Verify the public consumer endpoint**

```bash
curl "http://127.0.0.1:8001/projects/<SLUG>/seo/public/meta?route=/&locale=en"
```
Expected: `{}` (no published meta yet) — confirms the endpoint is live and unauthenticated.

- [ ] **Step 4: Clean up the seed**

```sql
delete from seo_runs where summary = 'Seed run for UI check';
delete from seo_plan_items where title = 'Add a sourced statistic to the homepage hero';
update projects set seo_enabled = false where id = '<PROJECT_ID>';
```

- [ ] **Step 5: Commit note (checkpoint)**

No code change; record completion in the run notes. Plan 1 is done when Tasks 1–11 pass.

---

## Self-review

**Spec coverage:** Migration + 10 tables + project flags ✓ (Task 1). `seo.py` router with reads + human CRUD + public consumer ✓ (Tasks 4–7). Dashboard "SEO & GEO" section (Overview/Plan/History/Articles/Competitors/Settings) ✓ (Tasks 9–10). Auth reuses `user_via_bearer_or_session` + `require_project_access` so the agent (bearer) and dashboard (session) share endpoints ✓. Route-collision avoided (all under `/projects/{slug}/seo/...`) ✓. Per-spec, analytical tables are agent-written via Supabase MCP later — this plan only reads them ✓.

**Deferred to later plans (correctly out of scope here):** the agent itself (Plan 2), the apply + visual-QA gate (Plan 3), cross-agent new-page orchestration (Plan 4), `seo_page_meta`/`seo_articles` consumption wired into generated sites (Plan 4, Connector change), the Settings toggle write + meta/article editor UIs (Plan 2/3 when the agent populates them).

**Placeholder scan:** none — every step has concrete code/SQL/commands.

**Type consistency:** `SeoOverviewOut`/`SeoOverview`, `SeoPlanItemOut`/`SeoPlanItem`, repo fn names (`latest_audit`, `upsert_page_meta`, `create_article`, `published_meta`) match between repo, router, tests, and api.ts. Endpoint paths match between router, tests, and api.ts (`/api` prefix on the frontend).

---

## Next plan

**Plan 2 — Agent core:** `agents/SEO-GEO Optimizer/` skill (`SKILL.md`, `AGENTS.md`, phases 0–4, `prompts.py` with the forbidden-claims block, `audit.py`, `render_check.py`, `competitor.py`, `cms_client.py`) — load context → deep competitor intel → audit (per-locale) → plan, writing `seo_runs`/`seo_audits`/`seo_plan_items`/`seo_competitors` via Supabase MCP. Written after Plan 1 is built and green.
