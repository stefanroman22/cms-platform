# Scan-Scope Checklist

The concrete file/area inventory every review must cover. As the app grows, **add new
surfaces here** so coverage keeps pace. Tick boxes are a per-review working aid (reset each run).

> Counts are indicative as of 2026-06-07 and will drift — globs, not exact counts, are authoritative.

## Backend — FastAPI (`backend/auth_service/`)

### Routers (`routers/`) — the authZ front line
- [ ] `auth.py` — login/logout/session issuance, account enumeration, reset flows
- [ ] `deps.py` — the auth + admin dependencies (every other router trusts these)
- [ ] `projects.py` — project CRUD, **admin transfer/delegation**, ownership
- [ ] `content.py` — content read/write, **public + draft-token** paths, locale-aware save. **Confirm the public reads carry the shared `_public_read_limit`** (SEC-095 — currently unlimited, unlike booking/forms)
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
- [ ] **`rich_text.py` · `rich_text_legacy.py` · `rich_text_migration.py`** (ADR-0010) — the canonicalizer is the primary stored-content XSS boundary: confirm it stays a **rebuild-from-allowlisted-tree** transform (RICH_TAGS only; `safe_href` scheme allow-list; `canonical_style` colour/font-family/font-size only) and that **translated (DeepL) HTML is re-canonicalised**
- [ ] **`html_sanitizer.py`** — scope is `leads.design_prompt` only; `bleach`-based (upstream-deprecated — maintenance watch)
- [ ] **`svg_sanitize.py`** (ADR-0011) — uploaded-SVG allow-list; DOCTYPE/ENTITY/`data:`/`javascript:`/backslash-escape/wide-BOM rejection; `href` must be `#…`; confirm how SVGs are **served**
- [ ] **`theme.py`** (ADR-0011) + `frontend layout.tsx` theme boot script — tenant theme values stay validated tokens; nothing attacker-controlled into the inline `<script>`/CSS-var context
- [ ] **`slug.py`** · **`content_structure.py`** — slug/structure-policy injection via field keys/ids; URL-safety
- [ ] **`google_places/`** (ADR-0012) — admin-triggered outbound fetch: **SSRF** (`resolve.expand_short_link` redirect guard; `website_enrich.fetch_html` check-then-connect DNS-rebind), response→admin-UI injection, Google API-key/quota handling, imported fields reaching an `href`/HTML sink

### Core (`core/`)
- [ ] `config.py` — env validation, service-role-required-in-prod, secrets
- [ ] `security.py` · `security_headers.py` — hashing, headers, CSP
- [ ] `limiter.py` · `bearer_limiter.py` — rate limiting (note: in-memory resets per serverless invocation)
- [ ] `pg_rate_limit.py` — shared Postgres limiter: confirm it covers **all** unauth write paths (booking create/cancel/reschedule, `/forms/contact`), not just reads (SEC-058/059); note it **fails OPEN** on DB error (SEC-068)
- [ ] `main.py` — **CORS origins for both apps**, Private-Network middleware, app mounting

### Migrations (`backend/migrations/*.sql`)
- [ ] RLS enabled + policy correctness on every PostgREST-exposed table
- [ ] `tenant_rls_status` SECURITY DEFINER view
- [ ] Function `search_path` pinning

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
