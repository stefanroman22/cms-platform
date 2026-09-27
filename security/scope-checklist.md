# Scan-Scope Checklist

The concrete file/area inventory every review must cover. As the app grows, **add new
surfaces here** so coverage keeps pace. Tick boxes are a per-review working aid (reset each run).

> Counts are indicative as of 2026-06-07 and will drift — globs, not exact counts, are authoritative.

## Backend — FastAPI (`backend/auth_service/`)

### Routers (`routers/`) — the authZ front line
- [ ] `auth.py` — login/logout/session issuance, account enumeration, reset flows
- [ ] `deps.py` — the auth + admin dependencies (every other router trusts these)
- [ ] `projects.py` — project CRUD, **admin transfer/delegation**, ownership
- [ ] `content.py` — content read/write, **public + draft-token** paths, locale-aware save
- [ ] `workspace.py` — workspace save (locale-aware), ownership on mutation
- [ ] `publish.py` — publish flow, who can publish whose project
- [ ] `booking.py` — **public** create/availability (unauth surface)
- [ ] `booking_admin.py` — tenant-scoped admin of bookings/services/hours
- [ ] `forms.py` — **public** form submission → HTML email build (XSS sink)
- [ ] `admin_leads.py` / `admin_conversions.py` — admin-only gating

### Services (`services/`)
- [ ] `supabase_client.py` — service-role usage, query builder, anon fallback
- [ ] `sessions.py` · `auth_service.py` · `admin_keys.py` — token entropy, constant-time compare
- [ ] `booking_*` (repo, admin_repo, availability, tenant, stats, i18n, email, manage_email, reminder_email) — tenant resolution + IDOR + email injection
- [ ] `calendar_provider.py` · `google_calendar.py` — outbound + token handling
- [ ] `content_locale.py` · `segments.py` · `translation/` (provider, deepl, null, protect, sync) — outbound DeepL, untrusted content handling
- [ ] `html_sanitizer.py` — and **whether the email builders actually call it**
- [ ] `email_layout.py` · `*_email.py` — HTML email template injection
- [ ] `test_data.py` · `e2e_email_guard.py` — test-only paths not reachable in prod

### Core (`core/`)
- [ ] `config.py` — env validation, service-role-required-in-prod, secrets
- [ ] `security.py` · `security_headers.py` — hashing, headers, CSP
- [ ] `limiter.py` · `bearer_limiter.py` — rate limiting (note: in-memory resets per serverless invocation)
- [ ] `pg_rate_limit.py` — shared Postgres limiter: confirm it covers **all** unauth write paths (booking create/cancel/reschedule, `/forms/contact`), not just reads (SEC-058/059); note it **fails OPEN** on DB error (SEC-068)
- [ ] `main.py` — **CORS origins for both apps**, Private-Network middleware, app mounting

### Migrations (`backend/migrations/*.sql`)
- [ ] RLS enabled + policy correctness on every PostgREST-exposed table
- [ ] `tenant_rls_status` SECURITY DEFINER view
- [ ] Leftovers of removed features still in the DB until `2026_08_26_drop_removed_feature_tables.sql` is applied: `claim_*_solver_issue` RPC GRANTs, `slack_processed_events` / `project_issues` / `scrape_jobs` RLS state
- [ ] Function `search_path` pinning
- [ ] `2026_06_14_seo_geo.sql` — the `seo_*` tables: prefer an explicit `REVOKE ALL … FROM anon, authenticated` over relying only on the RLS toggle (SEC-067); check for any SECURITY DEFINER SEO routines + pinned `search_path`

## Frontend — Next.js (`frontend/src/`)
- [ ] `app/layout.tsx` — `dangerouslySetInnerHTML` (JSON-LD?) sink
- [ ] `components/admin/leads/sections/DesignPromptSection.tsx` — `dangerouslySetInnerHTML` sink
- [ ] `app/embed.js/` + `app/(widget)/` — the embeddable booking widget (cross-origin, postMessage, injected into client pages)
- [ ] `app/[locale]/(marketing)/manage/` — public booking manage page (token in URL)
- [ ] `components/admin/leads/**` — admin rendering of lead data (stored XSS)
- [ ] auth/session cookie usage, API base URL, any token in localStorage
- [ ] `next.config.ts` — headers, redirects, image domains, CSP

## Workflows (`.github/workflows/`)
- [ ] `promote.yml` — the only path to production: gate order, `PROMOTE_TOKEN` scope, deploy-hook secrets
- [ ] `codeql.yml` — secret exposure, `${{ }}` injection

## Agent guardrails (`.claude/`)
- [ ] `settings.json` + `hooks/guard.mjs` — PreToolUse hooks that block pushes to `main`, `--no-verify` and prod deploys, and ask before prod SQL/migrations: can a command shape bypass them?

## Agents (`agents/`)
- [ ] `CMS Connector - Website/` — imports **client websites** to GitHub; URL/repo validation, prompt injection, output path traversal
- [ ] `Design Prompt creator/` · `Website Builder/` — untrusted input → prompts → privileged actions
- [ ] GitHub token scope across all agents

## Infra / MCP-checked state (each review)
- [ ] Supabase security advisors (`get_advisors` type=security)
- [ ] Supabase performance advisors (informational)
- [ ] Supabase tables/policies/GRANTs (`list_tables`, `execute_sql` read-only)
- [ ] Vercel project posture (`get_project` for `cms-backend-roman` + frontend) — env scoping, deployment protection
