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
- [ ] `seo.py` — **NEW** SEO/GEO endpoints: authed audit/plan/apply/translate/jobs (project-ownership check via `require_project_access`), **public** `/seo/public/meta` + `/seo/public/articles` (unauth read; rate-limiting; slug enumeration). Rate-limiting gap tracked SEC-062/063.
- [ ] `projects.py` — **`admins see all projects` gate** (`if not user.is_admin: eq(user_id)`) — verify non-admins stay scoped to their own

### Services (`services/`)
- [ ] `supabase_client.py` — service-role usage, query builder, anon fallback
- [ ] `sessions.py` · `auth_service.py` · `admin_keys.py` — token entropy, constant-time compare
- [ ] `booking_*` (repo, admin_repo, availability, tenant, stats, i18n, email, manage_email, reminder_email) — tenant resolution + IDOR + email injection. **NEW: per-staff booking + booking blocks + service prices** — validate every body-supplied `service_id`/`resource_id`(staff)/`block_id` against caller's tenant. **booking_email `_cta_block` accent injection = SEC-058.**
- [ ] `seo_repo.py` · `translation/seo_translate.py` — **NEW** SEO data access (service-role; tenant scoping in app code) + outbound DeepL from SEO content (cost amplification)
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
- [ ] **NEW** `2026_06_14_seo_geo.sql` — `seo_*` tables: RLS enabled (no policies, service-role only) but **no explicit anon/authenticated REVOKE** unlike the hardened anon-surface migrations — align to SEC-004 discipline (defense-in-depth; verify live with MCP)
- [ ] **NEW** `2026_06_09_booking_blocks.sql` (GiST no-overlap exclusion — confirm tenant-composite key), `2026_06_10_booking_service_price.sql`, `2026_06_08_booking_customer_name_snapshot.sql`, `2026_06_11_*`

## Frontend — Next.js (`frontend/src/`)
- [ ] `app/layout.tsx` — `dangerouslySetInnerHTML` (JSON-LD?) sink
- [ ] `components/admin/leads/sections/DesignPromptSection.tsx` — `dangerouslySetInnerHTML` sink
- [ ] `app/embed.js/` + `app/(widget)/` — the embeddable booking widget (cross-origin, postMessage, injected into client pages)
- [ ] `app/(marketing)/manage/` — public booking manage page (token in URL)
- [ ] `components/admin/leads/**` — admin rendering of scraped/lead data (stored XSS)
- [ ] auth/session cookie usage, API base URL, any token in localStorage
- [ ] `next.config.ts` — headers, redirects, image domains, CSP (unsafe-inline/eval = SEC-040)
- [ ] `middleware.ts` — **REWRITTEN for i18n**: verify locale-prefix routing didn't open an auth bypass on protected paths + the revocation fast-path TTL
- [ ] `components/dashboard/seo/**` — **NEW** admin/client rendering of SEO data (audit for any HTML sink)

## Workflows (`.github/workflows/`)
> **Current set only** (the 2026-06 CI overhaul deleted `ci.yml`, `e2e.yml`, `auto-merge-dev-to-master.yml`, `post-deploy-smoke.yml`, `scraper-ci.yml`, `dependabot-auto-merge.yml`, and removed `dependabot.yml`).
- [ ] `solver-agent.yml` — **prompt injection via issue body**, token write scope, untrusted code execution, `@latest` CLI pin (SEC-059), remaining `@v4`/`@v5` action tags (SEC-024), harden-runner egress allowlist
- [ ] `promote.yml` — manual dev→main promote: `persist-credentials`, `PROMOTE_TOKEN` scope, gitleaks download integrity (SEC-060), gates before prod, no harden-runner
- [ ] `codeql.yml` — SHA-pinning, permissions
- [ ] `.github/dependabot.yml` — **currently ABSENT** (SEC-025): confirm re-introduction or an equivalent dependency-update mechanism

## Agents (`agents/`)
- [ ] `CMS Connector - Website/` — imports **client websites** to GitHub; URL/repo validation, prompt injection (SEC-016), output path traversal. **NEW: `github.py:ensure_branch_unprotected` STRIPS branch protection on the client prod branch** + `vercel.py` disables deployment protection — verify token scope + that this can't be steered against the wrong repo/branch (interlocks with SEC-006).
- [ ] `Solver - Issues/` — acts on issue content; auto-commit/push/merge based on attacker-influenceable text (SEC-005/006); new `backend_api.py`/`db.py`
- [ ] `SEO-GEO Optimizer/` — **NEW** agent: WebFetches competitor/client sites → LLM analyst/planner/content prompts (no data/instruction separation, SEC-061) → **autonomous publish** to the live client site (`gate.py`/GATE-FACT are visual/stat gates only, no content/link gate); `competitor.py` SSRF surface
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
