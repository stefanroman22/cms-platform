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
- [ ] `rich_text.py` · `rich_text_legacy.py` · `rich_text_migration.py` — **CMS rich-text → canonical HTML served on client sites** (ADR-0010/0011): tag/attr/url-scheme allow-list, `safe_href`, `canonical_style` (color/font only); the TS client-kit ports this exactly
- [ ] `svg_sanitize.py` — **allow-list rewriter for every uploaded SVG** (ADR-0011): DOCTYPE/ENTITY reject, element/attr allow-list, `href` must be local `#…`, no `data:`/`javascript:`/backslash-escape
- [ ] `theme.py` — **tenant theme → CSS/@font-face** (ADR-0011): hex colours, charset-restricted font families, font URLs pinned to the project storage prefix (no `["'()\s]`, no dot-segments)
- [ ] `storage_gc.py` — prune-unreferenced-uploads on publish (orphan reclaim)
- [ ] `slug.py` — slug normalization (localised, URL-safe; repeater slug field)
- [ ] `google_places/` (`client.py`, `importer.py`, `resolve.py`, `photos.py`, `mapper.py`, `website_enrich.py`, `quota.py`) — **lead import from a Google Maps listing** (ADR-0012): outbound Google API + **SSRF** on the business `websiteUri` / short-link redirects / photo fetch; monthly paid-API cap + per-user limit
- [ ] `test_data.py` · `e2e_email_guard.py` — test-only paths not reachable in prod

### Uploads (the new stored-file surface — ADR-0011)
- [ ] `routers/workspace.py` `upload_file` (~505) — MIME `_ALLOWED_MIME`/`_DENIED_MIME`/`_MIME_RE` bare-type normalization, `.svgz`/`+xml` deny, SVG→`sanitize_svg`, font-by-extension, tenant-derived object key `{project_slug}/{service_key}/{uuid}{ext}`, 50MB/5MB caps
- [ ] `routers/booking_admin.py` `upload_logo` (~792) — **weaker sibling of `upload_file`**: exact-string deny-list (no bare-type normalization), NO `sanitize_svg` (SEC-072); key `{tenant_id}/booking-logo/{uuid}.{ext}`
- [ ] **Serving origin:** `cms-files` (+ `lead-photos`) are PUBLIC-READ buckets on `*.supabase.co` — isolated from the app/client origins (bounds stored-XSS blast radius); uploads go only via the service-role backend
- [ ] **No per-user upload-frequency limit** on either endpoint (SEC-078)

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
- [ ] `2026_10_11_cms_files_bucket_svg_fonts.sql` — storage bucket `allowed_mime_types`; confirm `public` flag + `storage.objects` policies + inline Content-Type **(needs live DB)**
- [ ] `2026_10_11_lead_google_import.sql` — `google_import_usage` RLS-on but **no explicit REVOKE** of default anon/authenticated grants (SEC-067, re-scoped); import RPCs correctly `search_path`-pinned + service_role-only
- [ ] Default-ACL audit: every new `public` table needs an explicit `revoke all … from anon, authenticated` (RLS-only is a single-toggle barrier)

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
- [ ] `settings.json` + `hooks/guard.mjs` — PreToolUse hooks that block pushes to `main`, `--no-verify` and prod deploys, and ask before prod SQL/migrations: can a command shape bypass them? (SEC-075 — env prefix / absolute path / `$(…)` / `$VAR` all defeat the static tokenizer)
- [ ] **Tool-coverage gap:** the PreToolUse matchers only cover `Bash`, `Edit|Write|MultiEdit`, and the Supabase MCP — **not the GitHub MCP write tools** (`mcp__github__push_files/create_or_update_file/delete_file/merge_pull_request/update_pull_request_branch`), so H1 push-to-`main` is unenforced for MCP writes (SEC-071). Confirm `main` has (or does not have) server-side branch protection — ADR-0007 says the hook is the only enforcement.
- [ ] `agents/Design Prompt creator/phases/6-writeback.md` — untrusted content inlined into a `$$…$$` SQL literal with only `&<>` escaped (SEC-076)

## Agents (`agents/`)
- [ ] `CMS Connector - Website/` — imports **client websites** to GitHub; URL/repo validation, prompt injection, output path traversal
- [ ] `Design Prompt creator/` · `Website Builder/` — untrusted input → prompts → privileged actions
- [ ] GitHub token scope across all agents

## Infra / MCP-checked state (each review)
- [ ] Supabase security advisors (`get_advisors` type=security)
- [ ] Supabase performance advisors (informational)
- [ ] Supabase tables/policies/GRANTs (`list_tables`, `execute_sql` read-only)
- [ ] Vercel project posture (`get_project` for `cms-backend-roman` + frontend) — env scoping, deployment protection
