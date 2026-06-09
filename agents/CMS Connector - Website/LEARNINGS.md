# Learnings — CMS Connector Website Agent

> Accumulated rules to prevent repeating past mistakes. The agent reads this file at the start of every run and feeds these rules into Phase 2's system prompt and into Phase 4/5 sub-step decisions.
>
> Format: `- <YYYY-MM-DD>: <one-line rule>. Triggered by: <short context>.`
>
> Rules are append-only. The user prunes them manually when they go stale.

---

## GitHub setup

- 2026-04-29: GitHub MCP at api.githubcopilot.com (claude.ai web connector) is NOT auto-registered in Claude Code CLI sessions. Don't assume MCP availability — fall back to `gh` CLI (verify active account matches the intended owner) or REST via `agents/.../github.py`. Surface MCP unavailability immediately and suggest the fallback. Triggered by: agent halted Phase 1 because spec required MCP and only `gh` CLI was available.
- 2026-04-29: Verify `gh` CLI active account matches the intended repo owner before creating repos (`gh api user --jq .login`). User may have multiple accounts in keyring. Triggered by: gh was authed as a different user than the project owner.
- 2026-06-08: Strip GitHub branch protection on the production branch during provisioning (`github.ensure_branch_unprotected`, called in `_vercel_setup` right after the Vercel protection disable). A protected, PR-only prod branch is incompatible with the S1.5 fast-forward promotion — it can only advance via PR-merge commits, which permanently diverge it from `cms-preview` and wedge every deploy ("cannot fast-forward ... diverged"). The Slack ✅ approval is the real production gate. Triggered by: it-global-services `main` was manually branch-protected; every production merge failed 422 "Update is not a fast forward".

## Phase 2 — Scan rules

- 2026-04-29: When a site has Why-Choose-Us (or pillars / value-props / differentiators) repeating cards on multiple pages with overlapping themes, default to a SINGLE shared `key_features` repeater referenced by all pages (place under "General"). Pages render all items or a slice. Triggered by: it-global-services had 6 home reasons + 4 about pillars with conceptual overlap; user merged into one shared repeater.
- 2026-06-06: The language-SWITCHER control/labels (chrome) stay excluded; DETECT the locale set from `i18n/routing.ts` + `messages/<locale>.json` and import per-locale CONTENT as first-class CMS data. Supersedes the 2026-04-29 rule about language toggles being configuration-only. Triggered by: multilingual sites (e.g. Next.js + next-intl) have real per-locale content that must be seeded into the CMS.

## Phase 4 — Integration rules

- 2026-04-29: STANDING RULE — every site this agent integrates uses Resend for email delivery (via the CMS backend's `/forms/<slug>/<form_key>` endpoint + `RESEND_FROM_EMAIL`). Always migrate sites away from third-party email clients (EmailJS, Formspree, custom SMTP) during Phase 4. Drop their imports + `NEXT_PUBLIC_*` env vars. Triggered by: it-global-services used EmailJS; user confirmed Resend is the default for all future sites.
- 2026-06-06: Provisioning order for multilingual sites: (a) seed DEFAULT locale via `PUT /projects/<slug>/services/<key>` (no `?locale=` param); (b) import each non-default locale via `PUT …?locale=<l>`; (c) set `{default_locale, locales}` LAST via `PATCH /admin/projects/<slug>`. Setting locales last prevents the backend's auto-translate from overwriting human translations imported in step (b). Triggered by: auto-translate clobbered per-locale seeds when PATCH ran before PUT imports.
- 2026-06-06: The CMS endpoint env var set in Vercel must be the locale-less base `{cms_endpoint_base}/content/{slug}`. The site's `i18n/request.ts` appends `/{locale}` at runtime. Framework-aware prefix: `NEXT_PUBLIC_CMS_ENDPOINT` for Next.js, `VITE_CMS_ENDPOINT` for Vite. Triggered by: multilingual Next.js sites needed NEXT_PUBLIC_* and locale-less base to fetch per-locale content correctly.
- 2026-04-29: Forms endpoint path is `/forms/<slug>/<form_key>` — NOT `/api/forms/submit`. Phase 4 spec doc had wrong path; it has been corrected. Triggered by: AGENTS.md said `/api/forms/submit`.
- 2026-04-29: Backend has NO public POST `/projects` endpoint to create a CMS project row. Either insert directly via Supabase Management API (PAT) or have the user click "Create New Project" in the CMS admin UI. Document this in Phase 4 sub-step 0. Triggered by: agent assumed POST `/projects` existed.
- 2026-04-29: Set the project's `allowed_origins` array (postgres `text[]`) AFTER deploys land — must include both `production_url` and the preview branch alias. The admin PATCH endpoint does not whitelist this column; update via Supabase SQL. Triggered by: PATCH returned `{"updated":3}` (skipped allowed_origins).
- 2026-04-30: `AdminProjectPatchIn` (backend Pydantic schema) silently discards unknown fields. Pre-fix, `website_url` was NOT in the model so PATCHing it was a no-op (and `{"updated":N}` reflected only the accepted fields, hiding the silent drop). Post-fix the schema now includes `website_url` so the admin endpoint accepts it. Phase 4 must always set `website_url` (in addition to `production_url`) so the project page's "Live website" card and the admin settings form both populate. Triggered by: client-side card stayed hidden because `/projects/<slug>/settings.website_url` came back null even though Phase 4 thought it had been set.
- 2026-04-29: For Next.js client sites, env-var keys are `NEXT_PUBLIC_CMS_ENDPOINT` and `NEXT_PUBLIC_CMS_PREVIEW_TOKEN` (NOT the Vite `VITE_*` variants the existing `scan.py` hard-codes). Detect framework from `next.config.*` and select the right prefix. Triggered by: it-global-services is Next.js; agent set the right vars manually.
- 2026-04-29: Backend `/content/<slug>/draft` expects header `X-CMS-Preview-Token`, NOT `Authorization: Bearer`. The CMS fetcher in the client repo must use that exact header. Triggered by: Vercel preview build failed with 401 because client used `Authorization: Bearer`.
- 2026-04-29: Static export (`output: "export"` in next.config) DISABLES ISR (`fetch(..., {next:{revalidate:60}})`) so admin CMS edits never surface on the deployed site without a rebuild. Default for CMS-driven Next.js sites: omit `output:"export"` and let Vercel run SSR + ISR. Triggered by: it-global-services had `output:"export"`; we removed it so publish reflects within 60s.
- 2026-04-29: Vercel default project setting `ssoProtection: 'all_except_custom_domains'` makes preview-branch aliases gated behind Vercel auth. The default `<project>.vercel.app` production URL is treated as a custom domain and is public. Document this so Phase 5 expects 401 on the preview alias unless a custom domain is added or sso is disabled.
- 2026-04-29: Newly created services need an explicit publish call (`POST /projects/<slug>/publish`) before the public `/content/<slug>` endpoint reflects seeded values. Without publish, production fetch returns empty service shells. Triggered by: production page rendered no content until we ran the publish call.

## Phase 5 — Testing rules

- 2026-06-06: Draft endpoints require header `X-CMS-Preview-Token: <preview_token>`, NOT `Authorization: Bearer <preview_token>`. Applies to both `/content/<slug>/draft` and `/content/<slug>/<locale>/draft`. Triggered by: preview builds returned 401 when client sent `Authorization: Bearer`.

## Phase 6 — Onboarding rules

- 2026-04-29: Backend `POST /admin/clients` 500s when the auth user already exists (e.g., a prior failed run). Fallback flow: query `auth.v1.admin.users?filter=<email>` via service_role, capture uid, then PUT password reset on `/auth/v1/admin/users/<uid>`, then upsert into `public.users` (NOT NULL `password_hash` — argon2 hash) via Supabase SQL. Triggered by: George's account created in auth but not in public.users on first attempt.
- 2026-04-29: `public.users.password_hash` is NOT NULL even though Supabase Auth handles auth-side login. Insert with `argon2 PasswordHasher().hash(plaintext)` so the CMS's own login path (`auth_service.py`) can verify. Triggered by: 23502 NOT NULL violation when inserting via SQL without password_hash.
- 2026-04-29: Cloudflare blocks `urllib.request` POSTs to api.resend.com and api.supabase.com with code 1010 (UA fingerprint). Use `curl --data-binary @file.json` instead from Bash. Triggered by: Python's stdlib HTTP client got 403/1010 on both APIs.
- 2026-04-29: Resend `from` domain default for this CMS is `noreply@roman-technologies.dev` (verified). Reply-to should be the developer admin email so clients can reply with questions.
- 2026-04-29: After ownership transfer, the developer admin still sees the project via the `is_admin` flag on admin endpoints — no need to add a parallel access table. Triggered by: confirming Stefan can still load the project after `UPDATE projects SET user_id = <client_uid>`.
- 2026-04-29: STANDING — welcome email Login URL is **always** `https://roman-technologies.dev/log-in` (the canonical client portal sign-in page). Never substitute the per-project Vercel `/dashboard/<slug>` URL. Drop the "Live website" row from the credentials table — clients reach their site via dashboard. Triggered by: user requested standardised login URL across all clients.

## Booking

- 2026-06-06: Booking detection = scheduling intent ONLY (calendar/slot picker, appointment/book/reserve/schedule flows, services-with-durations + staff + hours pattern, or an existing booking widget). A plain contact form with no scheduling intent stays on the `email_config` path — never emit a `booking` block for it. Triggered by: prompts.py booking-detection spec shipped 2026-06-05.
- 2026-06-06: Provisioning order is strictly: enable → settings → resources → services (linked to ≥1 resource) → hours. Every service MUST be linked to at least one resource or availability queries return empty. Triggered by: Phase 4 booking provisioning spec.
- 2026-06-06: Hours rows are required — without them the availability endpoint returns no slots even when services and resources exist. Triggered by: Phase 4 booking provisioning spec.
- 2026-06-06: `destination_email` defaults to `stefanromanpers@gmail.com` when Stefan provides no client email address. Always leave it blank in the manifest scan output; Stefan fills it in at the review gate. Triggered by: prompts.py booking block comment "Leave destination_email empty — Stefan sets the client email".
- 2026-06-06: `calendar_provider` is always `"none"` for clients. Never set Google Calendar or iCal at the client level. Triggered by: prompts.py booking schema.
- 2026-06-06: Always set `business_name` and `accent_color` (and `primary_color` where available) in the booking settings block so booking confirmation emails use client branding instead of falling back to Roman Technologies defaults. Triggered by: booking email templates reference these fields for the From name and header colour.
- 2026-06-06: Booking emails are host-name-neutral — the email templates do not hard-code `roman-technologies.dev`. Use the `email_copy` fields in booking settings for any company-specific wording so each client's emails carry their own identity. Triggered by: booking email layout refactored to use `business_name` from settings.

## Successful runs

- 2026-04-29: it-global-services. 25 services provisioned + published. Production https://it-global-services.vercel.app live. Both branches deployed READY. Form submit + Resend delivery verified. Owner transferred to george.nadejde@hotmail.com; welcome email sent (Resend id 758f9a34-4b5e-49d4-b464-fe92f7363a6f). Phases 1–6 clean.
