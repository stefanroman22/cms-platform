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
- [ ] `issues.py` — issue create/list, solver dispatch trigger
- [ ] `slack_events.py` — **public** webhook (HMAC signature must hold)
- [ ] `admin_leads.py` / `admin_conversions.py` / `admin_scrape_jobs.py` — admin-only gating

### Services (`services/`)
- [ ] `supabase_client.py` — service-role usage, query builder, anon fallback
- [ ] `sessions.py` · `auth_service.py` · `admin_keys.py` — token entropy, constant-time compare
- [ ] `booking_*` (repo, admin_repo, availability, tenant, stats, i18n, email, manage_email, reminder_email) — tenant resolution + IDOR + email injection
- [ ] `calendar_provider.py` · `google_calendar.py` — outbound + token handling
- [ ] `content_locale.py` · `segments.py` · `translation/` (provider, deepl, null, protect, sync) — outbound DeepL, untrusted content handling
- [ ] `html_sanitizer.py` — and **whether the email builders actually call it**
- [ ] `email_layout.py` · `*_email.py` — HTML email template injection
- [ ] `slack_*` (signature, events_dedup, notify, handler) · `solver_dispatch.py` · `github_merge.py` — webhook auth, token scope
- [ ] `test_data.py` · `e2e_email_guard.py` — test-only paths not reachable in prod

### Core (`core/`)
- [ ] `config.py` — env validation, service-role-required-in-prod, secrets
- [ ] `security.py` · `security_headers.py` — hashing, headers, CSP
- [ ] `limiter.py` · `bearer_limiter.py` — rate limiting (note: in-memory resets per serverless invocation)
- [ ] `main.py` — **CORS origins for both apps**, Private-Network middleware, app mounting

### Migrations (`backend/migrations/*.sql`)
- [ ] RLS enabled + policy correctness on every PostgREST-exposed table
- [ ] `tenant_rls_status` SECURITY DEFINER view
- [ ] `claim_next_solver_issue` / `claim_specific_solver_issue` RPC GRANTs (anon/authenticated)
- [ ] `slack_processed_events` RLS state
- [ ] Function `search_path` pinning

## Frontend — Next.js (`frontend/src/`)
- [ ] `app/layout.tsx` — `dangerouslySetInnerHTML` (JSON-LD?) sink
- [ ] `components/admin/leads/sections/DesignPromptSection.tsx` — `dangerouslySetInnerHTML` sink
- [ ] `app/embed.js/` + `app/(widget)/` — the embeddable booking widget (cross-origin, postMessage, injected into client pages)
- [ ] `app/(marketing)/manage/` — public booking manage page (token in URL)
- [ ] `components/admin/leads/**` — admin rendering of scraped/lead data (stored XSS)
- [ ] auth/session cookie usage, API base URL, any token in localStorage
- [ ] `next.config.ts` — headers, redirects, image domains, CSP

## Workflows (`.github/workflows/`)
- [ ] `solver-agent.yml` — **prompt injection via issue body**, token write scope, untrusted code execution
- [ ] `auto-merge-dev-to-master.yml` — required checks/reviews before reaching master→prod
- [ ] `dependabot-auto-merge.yml` — auto-merge gates
- [ ] `e2e.yml` · `ci.yml` · `post-deploy-smoke.yml` · `scraper-ci.yml` · `codeql.yml` — secret exposure, `pull_request_target`, `${{ }}` injection

## Agents (`agents/`)
- [ ] `CMS Connector - Website/` — imports **client websites** to GitHub; URL/repo validation, prompt injection, output path traversal
- [ ] `Solver - Issues/` — acts on issue content; auto-commit/push/merge based on attacker-influenceable text
- [ ] `Design Prompt creator/` · `Website Builder/` — untrusted input → prompts → privileged actions
- [ ] GitHub token scope across all agents

## Scraper (`scraper/src/scraper/`)
- [ ] `google_maps.py` · `urls.py` · `geo.py` · `pipeline.py` · `cli.py` — SSRF, URL validation, fan-out limits
- [ ] output file writes (path traversal), geocode cache (`.geocode_cache.json`) deserialization
- [ ] `tools/` — region builder
- [ ] downstream trust: is scraped data sanitized before backend/connector consume it?

## Infra / MCP-checked state (each review)
- [ ] Supabase security advisors (`get_advisors` type=security)
- [ ] Supabase performance advisors (informational)
- [ ] Supabase tables/policies/GRANTs (`list_tables`, `execute_sql` read-only)
- [ ] Vercel project posture (`get_project` for `cms-backend-roman` + frontend) — env scoping, deployment protection
