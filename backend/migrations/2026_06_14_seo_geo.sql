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
