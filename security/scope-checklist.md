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
- [ ] `booking.py` — **public** create/availability (unauth surface); **note the LEGACY shims**
      `/availability` + `/slots` (hardcoded tenant, easy to miss the `_public_read_limit` dep — SEC-058)
- [ ] `booking_admin.py` — tenant-scoped admin of bookings/services/hours; **per-staff** resource/staff/
      service linking (validate every `staff_id`/`resource_id`/`service_id` belongs to the tenant)
- [ ] `forms.py` — **public** form submission → HTML email build (XSS sink)
- [ ] `issues.py` — issue create/list, solver dispatch trigger; **`/admin/issues/{id}/status`** skips
      the project-ownership check by design (SEC-005)
- [ ] `seo.py` — **NEW** SEO/GEO: dashboard reads + human CRUD + **public** consumer endpoints;
      per-endpoint `require_project_access`; unlimited `/translate` (paid DeepL — SEC-059)
- [ ] `slack_events.py` — **public** webhook (HMAC signature must hold)
- [ ] `admin_leads.py` / `admin_conversions.py` / `admin_scrape_jobs.py` — admin-only gating
- [ ] `deps.py` bearer path — `verify_admin_api_key` must return a `UserOut` shape (SEC-046 regression watch)

### Services (`services/`)
- [ ] `supabase_client.py` — service-role usage, query builder, anon fallback
- [ ] `sessions.py` · `auth_service.py` · `admin_keys.py` — token entropy, constant-time compare
- [ ] `seo_repo.py` — **NEW** every read/write scoped by `project_id`; published-content public reads
- [ ] `booking_*` (repo, admin_repo, availability, tenant, stats, i18n, email, manage_email, reminder_email) — tenant resolution + IDOR + email injection; **`booking_email._cta_block` accent must go through `safe_hex` (SEC-060)**
- [ ] `calendar_provider.py` · `google_calendar.py` — outbound + token handling
- [ ] `content_locale.py` · `segments.py` · `translation/` (provider, deepl, null, protect, sync) — outbound DeepL, untrusted content handling
- [ ] `html_sanitizer.py` — and **whether the email builders actually call it**
- [ ] `email_layout.py` · `*_email.py` — HTML email template injection
- [ ] `slack_*` (signature, events_dedup, notify, handler) · `solver_dispatch.py` · `github_merge.py` — webhook auth, token scope
- [ ] `test_data.py` · `e2e_email_guard.py` — test-only paths not reachable in prod

### Core (`core/`) + deploy config
- [ ] `config.py` — env validation, service-role-required-in-prod, secrets
- [ ] `security.py` · `security_headers.py` — hashing, headers, CSP (app middleware only ships X-Frame-Options + X-Content-Type-Options)
- [ ] `backend/vercel.json` — **legacy `builds`/`routes` schema SUPPRESSES the `headers` block** (SEC-062); CSP/HSTS/COOP/CORP declared there are NOT delivered
- [ ] `limiter.py` · `bearer_limiter.py` · `pg_rate_limit.py` — shared Postgres limiter (fail-open on DB error); per-instance slowapi residuals
- [ ] `main.py` — **CORS origins for both apps**, Private-Network middleware, app mounting

### Migrations (`backend/migrations/*.sql`)
- [ ] RLS enabled + policy correctness on every PostgREST-exposed table
- [ ] `tenant_rls_status` SECURITY DEFINER view
- [ ] `claim_next_solver_issue` / `claim_specific_solver_issue` RPC GRANTs (anon/authenticated)
- [ ] `slack_processed_events` RLS state
- [ ] **NEW** `2026_06_14_seo_geo.sql` — 9 SEO tables: RLS enabled but **no anon/authenticated REVOKE** (SEC-064); confirm no permissive policy added later
- [ ] Regression watch: any later `CREATE OR REPLACE`/`GRANT` re-opening the 2026_06_08 anon-surface lockdown (SEC-004/013/033/042/053)
- [ ] Function `search_path` pinning

## Frontend — Next.js (`frontend/src/`)
- [ ] `app/layout.tsx` — `dangerouslySetInnerHTML` (JSON-LD?) sink
- [ ] `components/admin/leads/sections/DesignPromptSection.tsx` — `dangerouslySetInnerHTML` sink
- [ ] `app/embed.js/` + `app/(widget)/` — the embeddable booking widget (cross-origin, postMessage, injected into client pages)
- [ ] `app/(marketing)/manage/` — public booking manage page (token in URL)
- [ ] `components/admin/leads/**` — admin rendering of scraped/lead data (stored XSS)
- [ ] auth/session cookie usage, API base URL, any token in localStorage
- [ ] `next.config.ts` — headers, redirects, image domains, CSP

## Workflows (`.github/workflows/`) — **only 3 remain after the 2026-06-09 CI/CD teardown**
- [ ] `solver-agent.yml` — **prompt injection via issue body**, token write scope, untrusted code execution; residual unpinned `checkout@v4`/`setup-python@v5` (SEC-024)
- [ ] `promote.yml` — **NEW** manual prod promote (`contents:write` PAT + deploy hooks); gitleaks binary download has no checksum + no harden-runner egress block (SEC-061)
- [ ] `codeql.yml` — SHA-pinned; secret exposure, `pull_request_target`, `${{ }}` injection
- [ ] (deleted: `ci.yml`/`e2e.yml`/`auto-merge-dev-to-master.yml`/`post-deploy-smoke.yml`/`scraper-ci.yml`/`dependabot-auto-merge.yml`; Dependabot disabled — SEC-007/023/025/026 obsolete)

## Agents (`agents/`)
- [ ] `CMS Connector - Website/` — imports **client websites** to GitHub; **model-produced `project_slug` from untrusted files drives admin writes (SEC-057)**; now **strips branch protection** on client prod branch (`github.py`); URL/repo validation, prompt injection, output path traversal
- [ ] `Solver - Issues/` — acts on issue content; auto-commit/push to **cms-preview staging** (force-push removed); prod via manual promote
- [ ] `SEO-GEO Optimizer/` — **NEW** `apply.py` writes model-generated site changes; `render_check.fetch_raw` unsafe URL fetch (SEC-063); `competitor.py`/`audit.py` fetch external pages into prompts
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
