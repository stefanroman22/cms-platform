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
- [ ] `seo.py` — **SEO/GEO** dashboard CRUD (`require_project_access`) + agent bearer writes + **public** consumer
  endpoints (`/seo/public/meta`, `/seo/public/articles`, unauth, published-only); `/seo/translate` (paid DeepL,
  **rate-limit**, SEC-061); `enqueue_job` kind, `_project_id_by_slug` tenant scoping

### Services (`services/`)
- [ ] `supabase_client.py` — service-role usage, query builder, anon fallback
- [ ] `sessions.py` · `auth_service.py` · `admin_keys.py` — token entropy, constant-time compare
- [ ] `booking_*` (repo, admin_repo, availability, tenant, stats, i18n, email, manage_email, reminder_email) — tenant resolution + IDOR + email injection. **Note (SEC-059/060):** tenant `accent` must go through `safe_hex` in EVERY email button helper (`_cta_block`, `_button`), not just `header()`/`accent_rule()`.
- [ ] `seo_repo.py` — SEO table access; confirm every mutation scopes by **both** `project_id` and row `id`; `on_conflict` targets are static
- [ ] `translation/seo_translate.py` — SEO prose translation (outbound DeepL; cost amplification)
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
- [ ] `2026_06_14_seo_geo.sql` — 9 new SEO tables (`seo_runs/audits/plan_items/changes/competitors/page_meta/`
  `articles/learnings/jobs`): RLS enabled + **no** anon/authenticated policies/GRANTs (verified clean 2026-09-03,
  no live-MCP confirmation this run); `status`/`kind`/`action_kind`/`track` CHECK constraints
- [ ] `2026_06_11_booking_resource_image.sql` / `2026_06_11_booking_reminder_default_1h.sql` — RLS/grant regressions

## Frontend — Next.js (`frontend/src/`)
- [ ] `app/layout.tsx` — `dangerouslySetInnerHTML` (JSON-LD?) sink
- [ ] `components/admin/leads/sections/DesignPromptSection.tsx` — `dangerouslySetInnerHTML` sink
- [ ] `app/embed.js/` + `app/(widget)/` — the embeddable booking widget (cross-origin, postMessage, injected into client pages)
- [ ] `app/(marketing)/manage/` — public booking manage page (token in URL)
- [ ] `components/admin/leads/**` — admin rendering of scraped/lead data (stored XSS)
- [ ] `components/dashboard/seo/**` (`SeoSection`, `ArticlesTab`, `api.ts`, `types.ts`) — dashboard rendering of
  agent/human-authored SEO article `body`/`json_ld` (confirmed 2026-09-03: NOT rendered via
  `dangerouslySetInnerHTML` in this repo; the public site render lives in the generated client site, out of repo)
- [ ] `middleware.ts` — session fast-path TTL (SEC-019), locale routing (rewritten +140 as of 2026-06)
- [ ] `lib/locale.ts` + `i18n/*` + `LanguageSwitcher` — locale cookie (`maxAge`); confirm non-sensitive, no auth data
- [ ] auth/session cookie usage, API base URL, any token in localStorage
- [ ] `next.config.ts` — headers, redirects, image domains, CSP (SEC-040 `unsafe-inline`/`unsafe-eval` still present)

## Workflows (`.github/workflows/`)
> As of 2026-06-09 the CI pipeline was overhauled: `ci.yml`, `e2e.yml`, `auto-merge-dev-to-master.yml`,
> `post-deploy-smoke.yml`, `scraper-ci.yml`, `dependabot-auto-merge.yml` and `.github/dependabot.yml` were all
> **deleted**. Only three workflows remain (verified 2026-09-03).
- [ ] `solver-agent.yml` — **prompt injection via issue body**, token write scope, untrusted code execution;
  SHA-pin `checkout`/`setup-python` (SEC-024, still unpinned); harden-runner egress block present
- [ ] `promote.yml` — manual dev→main promotion; holds `PROMOTE_TOKEN` (fast-forwards protected `main`) + prod
  deploy hooks. gitleaks is a curl-download with **no checksum** (SEC-066); other actions SHA-pinned
- [ ] `codeql.yml` — static scanning
- [ ] (removed) `auto-merge-dev-to-master.yml` / `post-deploy-smoke.yml` / `dependabot-auto-merge.yml` — obsoleted
  SEC-007/023/026; no automated dep updates now (SEC-068)

## Agents (`agents/`)
- [ ] `CMS Connector - Website/` — imports **client websites** to GitHub; URL/repo validation, prompt injection, output path traversal
- [ ] `Solver - Issues/` — acts on issue content; auto-commit/push/merge based on attacker-influenceable text
- [ ] `Design Prompt creator/` · `Website Builder/` (incl. `phases/9-incremental.md` — writes `app/[locale]/<route>/page.tsx`, SEC-064) — untrusted input → prompts → privileged actions
- [ ] **`SEO-GEO Optimizer/`** — ingests **untrusted competitor/client site content** (`WebFetch`) and holds
  **pre-authorized, never-pausing service-role Supabase `execute_sql` + CMS-admin writes**. Highest-risk agent:
  data/instruction separation/fencing (SEC-058), raw-SQL interpolation in `phases/*.md` (SEC-057),
  `render_check.fetch_raw` SSRF (SEC-065), `site_change_spec.route` path safety (SEC-064). Files: `apply.py`,
  `gate.py`, `competitor.py`, `prompts.py`, `site_change_spec.py`, `render_check.py`, `phases/*`, `guidelines/*`
- [ ] GitHub token scope across all agents; **service-role SQL scope** for the SEO-GEO agent

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
