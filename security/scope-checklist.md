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
- [ ] `rich_text.py` · `rich_text_legacy.py` · `rich_text_migration.py` · `content_structure.py` (ADR-0010) — the HTML sanitizer allow-list (tags/attrs, `safe_href` scheme deny, `canonical_style` CSS allow-list); stored HTML is translated via DeepL **as HTML** then re-sanitized, rendered in the dashboard AND served to public client sites
- [ ] `svg_sanitize.py` (ADR-0011) — SVG upload allow-list (elements/attrs, DOCTYPE/ENTITY reject, `href` must be `#…`, byte/depth/element caps); **is it a hard boundary and does every upload sink call it?** (the `booking_admin.upload_logo` sink does NOT — SEC-076)
- [ ] `theme.py` (ADR-0011) — tenant theme validation: hex colours, font-family charset, uploaded-font URL must be storage-prefixed with no dot-segments (CSS injection)
- [ ] `slug.py` — slug generation / URL-safety
- [ ] `storage_gc.py` — prune-unreferenced-uploads on publish (best-effort; must never fail publish)
- [ ] `google_places/` (ADR-0012 — `client.py`, `importer.py`, `mapper.py`, `photos.py`, `quota.py`, `resolve.py`, `website_enrich.py`) — **SSRF** (does `website_enrich` / `expand_short_link` host+scheme+IP-validate, re-check redirects, and pin the resolved IP?), admin gating, Google API-key handling, monthly quota, untrusted third-party data stored/rendered
- [ ] `email_send.py` — Resend transport
- [ ] `test_data.py` · `e2e_email_guard.py` — test-only paths not reachable in prod

### Core (`core/`)
- [ ] `config.py` — env validation, service-role-required-in-prod, secrets
- [ ] `security.py` · `security_headers.py` — hashing, headers, CSP
- [ ] `limiter.py` · `bearer_limiter.py` — rate limiting (note: in-memory resets per serverless invocation)
- [ ] `pg_rate_limit.py` — shared Postgres limiter: confirm it covers **all** unauth write paths (booking create/cancel/reschedule, `/forms/contact`), not just reads (SEC-058/059); note it **fails OPEN** on DB error (SEC-068)
- [ ] `main.py` — **CORS origins for both apps**, Private-Network middleware, app mounting

### Routers (uploads — new ADR-0011 sinks)
- [ ] `workspace.py` `upload_file` (~505) + `booking_admin.py` `upload_logo` (~793) — the two write sinks into the **public `cms-files` bucket**: MIME/extension normalisation (bare type, not raw `content_type`), SVG routed through `svg_sanitize`, size caps enforced before buffering, per-user/project rate limit, ownership check, storage-path traversal

### Migrations (`backend/migrations/*.sql`)
- [ ] RLS enabled + policy correctness on every PostgREST-exposed table
- [ ] Default anon/authenticated **table GRANTs REVOKE'd** even when RLS is on (pattern from `rate_limits`/`slack_processed_events`; new `google_import_usage` missed it — SEC-091)
- [ ] `tenant_rls_status` SECURITY DEFINER view
- [ ] Function `search_path` pinning (`= ''` + schema-qualified refs is the repo standard)
- [ ] Storage bucket config — `cms-files` is **public**; allowed MIME types (`2026_10_11_cms_files_bucket_svg_fonts.sql` adds `image/svg+xml` + fonts), `file_size_limit`, storage.objects RLS policies
- [ ] `pg_cron` gc jobs (`2026_09_27_*`)

## Frontend — Next.js (`frontend/src/`)
- [ ] `app/layout.tsx` — `dangerouslySetInnerHTML` (JSON-LD?) sink
- [ ] `components/admin/leads/sections/DesignPromptSection.tsx` — `dangerouslySetInnerHTML` sink
- [ ] `lib/cms-rich-text/*` (ADR-0010/0011) — the TS rich-text kit (`parse`/`normalize`/`serialize`/`style`/`href`/`legacy`/`theme`/`slug`); must mirror the backend sanitizer exactly; rendered via `splitRichWords`/`ThemeStyles`
- [ ] `middleware.ts` — the `/dashboard` auth gate (does it trust a forgeable cookie vs. a bound session proof? — SEC-087)
- [ ] `app/embed.js/` + `app/(widget)/` — the embeddable booking widget (cross-origin, postMessage, injected into client pages)
- [ ] `app/[locale]/(marketing)/manage/` — public booking manage page (token in URL)
- [ ] `components/admin/leads/**` — admin rendering of lead data (stored XSS)
- [ ] auth/session cookie usage, API base URL, any token in localStorage
- [ ] `next.config.ts` — headers, redirects, image domains, CSP

## Workflows (`.github/workflows/`)
- [ ] `promote.yml` — the only path to production: gate order, `PROMOTE_TOKEN` scope, deploy-hook secrets; **untrusted dev-branch `npm ci`/build must not share the runner with the privileged push** (SEC-077); gitleaks binary verification (SEC-065) + config read from a trusted ref not the gated branch (SEC-079); no unhashed `pip install` mixed into a `--require-hashes` step (SEC-078)
- [ ] `codeql.yml` — secret exposure, `${{ }}` injection
- [ ] `prune-vercel-previews.yml` + `scripts/prune_vercel_previews.py` — Vercel token scope, `${{ }}` injection

## Agent guardrails (`.claude/`)
- [ ] `settings.json` + `hooks/guard.mjs` — PreToolUse hooks that block pushes to `main`, `--no-verify` and prod deploys, and ask before prod SQL/migrations: **can a command shape bypass them?** Confirmed-bypassable 2026-10-15 — the command-name resolver matches literally, so `env`/absolute-path/subshell/`pnpm` (SEC-072), `git -c alias.*=` (SEC-073), `GIT_CONFIG_*` env (SEC-074), and shell writes to applied migrations (SEC-081) all evade it. Re-check after any resolver fix.

## Agents (`agents/`)
- [ ] `CMS Connector - Website/` — imports **client websites** to GitHub; URL/repo validation, prompt injection (untrusted source → scan prompt, SEC-016), **no manifest value interpolated raw into generated code** (`scan.py` slug → `lib/booking.ts`, SEC-071), the `claude` CLI invoked with a minimal `--allowedTools`/`--permission-mode` (SEC-080), output path traversal
- [ ] `Design Prompt creator/` — untrusted Google lead data → prompt → **writeback must be parameterized SQL, not `$$`-quoted raw** (SEC-085)
- [ ] `Website Builder/` — untrusted design-export README must be fenced as data, with a diff gate before file/git/npm actions (SEC-086)
- [ ] GitHub/Vercel/CMS-admin token scope across all agents; secrets reachable by the agent process during an untrusted run

## Infra / MCP-checked state (each review)
- [ ] Supabase security advisors (`get_advisors` type=security)
- [ ] Supabase performance advisors (informational)
- [ ] Supabase tables/policies/GRANTs (`list_tables`, `execute_sql` read-only)
- [ ] Vercel project posture (`get_project` for `cms-backend-roman` + frontend) — env scoping, deployment protection
