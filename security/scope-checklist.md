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
- [ ] `booking_*` (repo, admin_repo, availability, tenant, stats, i18n, email, manage_email, reminder_email) — tenant resolution + IDOR + email injection; **`booking_i18n.py` `tt()` str.format on tenant copy (SEC-060)**
- [ ] `calendar_provider.py` · `google_calendar.py` — outbound + token handling
- [ ] `content_locale.py` · `content_structure.py` · `segments.py` · `translation`/DeepL — outbound DeepL, untrusted content handling; **rich text is translated as HTML then re-sanitised — confirm re-sanitise runs on output**
- [ ] **`rich_text.py` · `rich_text_legacy.py` · `rich_text_migration.py` (ADR-0010) — the canonical HTML pipeline. Allow-list tree-rebuild + `safe_href` default-deny: confirm every rich/inline write goes through `normalize_content`/`canonicalize` (a write path that skips it stores raw HTML); check the legacy markdown-lite converter, parser-differential vs the TS kit, depth/size caps (MAX_PARSE_DEPTH/MAX_MARK_DEPTH/MAX_LENGTH)**
- [ ] `html_sanitizer.py` — bleach allow-list for `leads.design_prompt`; and **whether the email builders actually call it**
- [ ] `email_layout.py` · `email_send.py` · `*_email.py` (incl. `password_changed_email.py`) — HTML email template injection; safe_hex/safe_url/html.escape on tenant brand + customer fields
- [ ] `storage_gc.py` — upload GC / pg_cron job; outbound + path handling
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
- [ ] Function `search_path` pinning

## Rich-text client kit (`client-kit/rich-text/`)
- [ ] `src/parse.ts` · `serialize.ts` · `normalize.ts` · `href.ts` · `legacy.ts` · `detect.ts` · `whitespace.ts` — the TS port of `backend/.../rich_text.py` that renders CMS content **on the public client sites**. Confirm `href.ts` is a real default-deny scheme allow-list and that `RichText.tsx` does not re-introduce an unsanitised `dangerouslySetInnerHTML` path; watch for parser-differential vs the Python canonicaliser (they must agree — pinned by `fixtures/canonical-vectors.json`)
- [ ] `src/RichText.tsx` · `splitRichWords.tsx` — the render components
- [ ] `scripts/sync-rich-text-kit.mjs` + `package-lock.json` — vendoring/supply-chain of the kit into the dashboard

## Frontend — Next.js (`frontend/src/`)
- [ ] `app/layout.tsx` — `dangerouslySetInnerHTML` (themeBootScript / JSON-LD) sinks
- [ ] `components/admin/leads/sections/DesignPromptSection.tsx` — `dangerouslySetInnerHTML` sink (DOMPurify on render — SEC-018/043 fixed)
- [ ] `components/admin/leads/sections/ContactSection.tsx` · `LeadDetailDrawer.tsx` — lead URL `href` rendering without scheme allow-list (SEC-062)
- [ ] `app/embed.js/` + `app/(widget)/` — the embeddable booking widget (cross-origin, postMessage **wildcard target origin SEC-055**, injected into client pages)
- [ ] `app/[locale]/(marketing)/manage/` — public booking manage page (token in URL)
- [ ] `components/admin/leads/**` — admin rendering of lead data (stored XSS)
- [ ] auth/session cookie usage, API base URL, any token in localStorage
- [ ] `next.config.ts` — headers, redirects, image domains, CSP

## Workflows (`.github/workflows/`) + secret scan
- [ ] `promote.yml` — the only path to production: gate order, `PROMOTE_TOKEN` scope, deploy-hook secrets, **gitleaks binary fetched without checksum (SEC-065)**
- [ ] `codeql.yml` · `prune-vercel-previews.yml` — secret exposure, `${{ }}` injection, SHA-pinning
- [ ] **`.gitleaks.toml` — the config for BOTH the pre-commit hook and the promote gate (the only pre-prod secret scan). Check `[allowlist] paths` is not disabling whole trees (SEC-071: `tests/`/`tests_integration/`/`docs/` currently excluded)**

## Agent guardrails (`.claude/`)
- [ ] `settings.json` + `hooks/guard.mjs` — PreToolUse hooks that block pushes to `main`, `--no-verify` and prod deploys, and ask before prod SQL/migrations: **can a command shape bypass them? (SEC-069: `bash -c`/`sh -c` wrappers + `$VAR`/`$(…)` expansion defeat all three — guard dispatches on the literal first token only and never recurses into wrappers/quotes/expansion)**

## Agents (`agents/`) — remaining after the Solver/scraper teardown
- [ ] `CMS Connector - Website/` — imports **client websites** to GitHub; URL/repo validation, prompt injection (SEC-016), output path traversal, **model-controlled values interpolated unescaped into generated client code (SEC-073: `public_slug` → `lib/booking.ts`)**
- [ ] `Design Prompt creator/` — untrusted scraped-lead input → prompts → **writeback into prod `leads` via MCP execute_sql (SEC-072: bare `$$` dollar-quoting)**
- [ ] `Website Builder/` — untrusted input → prompts → privileged actions
- [ ] GitHub token scope across all agents
- [ ] _(Removed 2026-08-26: `Solver - Issues/` + `scraper/` + the SEO-GEO Optimizer — do not re-add findings for these.)_

## Infra / MCP-checked state (each review)
- [ ] Supabase security advisors (`get_advisors` type=security)
- [ ] Supabase performance advisors (informational)
- [ ] Supabase tables/policies/GRANTs (`list_tables`, `execute_sql` read-only)
- [ ] Vercel project posture (`get_project` for `cms-backend-roman` + frontend) — env scoping, deployment protection
