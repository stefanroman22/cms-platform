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
- [ ] `seo.py` — **NEW** SEO/GEO router: dashboard reads + human/agent CRUD (`require_project_access`) + **public** consumer endpoints (`/seo/public/*`); paid DeepL `translate` + LLM `jobs` (rate-limit + IDOR + cost)

### Services (`services/`)
- [ ] `supabase_client.py` — service-role usage, query builder, anon fallback
- [ ] `sessions.py` · `auth_service.py` · `admin_keys.py` — token entropy, constant-time compare
- [ ] `booking_*` (repo, admin_repo, availability, tenant, stats, i18n, email, manage_email, reminder_email) — tenant resolution + IDOR + email injection; **per-staff overhaul** (barbers/resources/time-blocks/hours/exceptions), service price, resource image, customer-name snapshot
- [ ] `seo_repo.py` — **NEW** all SEO PostgREST reads/writes; verify every mutation is double-scoped `.eq(project_id).eq(id)` and column/sort values are literal (no injection)
- [ ] `github_merge.py` — PR-fallback when fast-forward hits a protected branch; branch-protection strip on client prod branch (token scope, who can trigger)
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
- [ ] **NEW** `2026_06_14_seo_geo.sql` — `seo_*` tables (competitors/audits/plan_items/page_meta/articles/runs/changes): RLS + anon/authenticated GRANTs revoked?
- [ ] **NEW** `2026_06_08_rate_limits.sql` — `rate_limits` table + `rate_limit_*` RPCs (SECURITY DEFINER, `search_path=''`, service_role-only)
- [ ] **NEW** booking migrations: `2026_06_08_booking_customer_name_snapshot`, `2026_06_09_booking_blocks`, `2026_06_10_booking_service_price`, `2026_06_11_booking_reminder_default_1h`, `2026_06_11_booking_resource_image`, `2026_05_18_solver_visibility`
> **Note:** live RLS/GRANT/advisor confirmation needs Supabase MCP, which was **absent** in the 2026-09-10 headless run — re-verify on a run with MCP.

## Frontend — Next.js (`frontend/src/`)
- [ ] `app/layout.tsx` — `dangerouslySetInnerHTML` (JSON-LD?) sink
- [ ] `components/admin/leads/sections/DesignPromptSection.tsx` — `dangerouslySetInnerHTML` sink **AND** the `htmlToPlainText`/CopyPromptButton `innerHTML` sink (SEC-059)
- [ ] `lib/booking-client/` — **NEW** cross-origin booking SDK (`contract.ts`, `index.ts`): message/postMessage handling, origin checks, injected into client pages
- [ ] `middleware.ts` — auth fast-path + verified-cookie TTL (session-revocation window); `i18n/` routing + locale cookie
- [ ] `app/embed.js/` + `app/(widget)/` — the embeddable booking widget (cross-origin, postMessage, injected into client pages)
- [ ] `app/(marketing)/manage/` — public booking manage page (token in URL)
- [ ] `components/admin/leads/**` — admin rendering of scraped/lead data (stored XSS)
- [ ] auth/session cookie usage, API base URL, any token in localStorage
- [ ] `next.config.ts` — headers, redirects, image domains, CSP

## Workflows (`.github/workflows/`)
> **2026-09-10:** CI teardown (`7ae1b07`) deleted `ci.yml`, `e2e.yml`, `auto-merge-dev-to-master.yml`, `post-deploy-smoke.yml`, `scraper-ci.yml`, `dependabot-auto-merge.yml` and `.github/dependabot.yml`. Only **three** workflows remain:
- [ ] `solver-agent.yml` — **prompt injection via issue body**, token write scope, untrusted code execution, harden-runner egress; action pinning (SEC-024: checkout@v4/setup-python@v5 unpinned)
- [ ] `promote.yml` — **NEW** manual `workflow_dispatch` "Promote dev → main": `PROMOTE_TOKEN` scope, `persist-credentials`, gitleaks binary pinning/checksum (SEC-060), `${{ }}` injection, fast-forward vs branch-protection
- [ ] `codeql.yml` — SAST (python + js/ts); confirm still scheduled and SHA-pinned

## Agents (`agents/`)
- [ ] `CMS Connector - Website/` — imports **client websites** to GitHub; URL/repo validation, prompt injection, output path traversal, branch-protection strip
- [ ] `Solver - Issues/` — acts on issue content; auto-commit/push/merge based on attacker-influenceable text
- [ ] `SEO-GEO Optimizer/` — **NEW** orchestrator with Supabase MCP `execute_sql`: raw-SQL construction from scraped competitor data (SEC-061), un-fenced scraped text → LLM prompts (SEC-062), competitor/render URL fetches (SSRF), publish gate has no content-security check
- [ ] `Design Prompt creator/` · `Website Builder/` — untrusted input → prompts → privileged actions; **`design_prompt` is untrusted agent-written HTML** consumed by the admin dashboard (SEC-018/043/059)
- [ ] GitHub token + Supabase MCP scope across all agents

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
