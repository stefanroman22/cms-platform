# Phase 4 — CMS integration

**Orchestration:** per the skill's *Orchestration policy (ultracode)*, orchestrate multi-agent wiring/verification via the Workflow tool when resolving service-shape mismatches, booking/UI wiring, or env-var decisions spanning many files; be exhaustive.

**Goal:** All approved services exist in the CMS, are seeded with `initial_content`. Client repo gains `cms.config.json` + `cms-provision.json`. Website is wired to the CMS. Vercel preview deployment is live.

**Inputs:** approved manifest from Phase 3, GitHub repo from Phase 1, `CMS_API_TOKEN`, `VERCEL_TOKEN`, Resend env vars on backend Vercel project.

> Sub-guidelines for this phase derive from the backend code in [`backend/`](../../../backend/). Read the backend before extending Phase 4. Specifically:
> - `backend/main.py` and `backend/auth_service/routers/projects.py` — CMS admin endpoints used to create services.
> - `backend/forms/` — how form submissions reach Resend; informs `email_config` wiring.
> - The existing `_provision()` and `_vercel_setup()` functions in [`scan.py`](../scan.py) are the reference implementations.

## Sub-steps (canonical order)

1. **Resolve client account** in the CMS (`_resolve_client`). Lookup by email; create if absent and surface generated password to the user once.
2. **Write outputs** locally: `cms.config.json` (slim, for client repo) and `cms-provision.json` (full manifest, admin keeps).

### 4.1.5 — Ensure CMS project row exists

If `GET /admin/projects/<slug>` returns 404 (or empty), POST to
`/admin/projects` with body `{slug, name, owner_email}` (use the
developer's admin email — ownership transfers to the client in
Phase 6). Otherwise reuse the existing row.

3. **Provision services** via CMS admin API — follow this exact order to avoid auto-translate clobbering human translations:
   a. `POST /projects/<slug>/services` per service (create phase; no content yet).
   b. `PUT /projects/<slug>/services/<key>` (no `?locale=` param) to seed the **default locale** content. Skip seeding for `email_config`.
   c. For each **non-default locale** in `manifest.locales`: `PUT /projects/<slug>/services/<key>?locale=<l>` with that locale's `initial_content` slice (manual override import). This preserves existing human translations from `messages/<locale>.json`.
   d. **LAST** — `PATCH /admin/projects/<slug>` with `{default_locale, locales}` to set the locale set on the project row. Doing this last prevents the backend from triggering auto-translate before all per-locale imports are in place.
4. **Wire `email_config`** to Resend:
   - Set `destination_email` in the service's content.
   - Confirm backend env vars `RESEND_API_KEY` and `RESEND_FROM_EMAIL` are set on the CMS backend Vercel project. If missing, **halt** and ask the user to set them — do not write `RESEND_API_KEY` from the agent.
   - Verify the from-domain is verified in Resend (call Resend API `/domains` if reachable; otherwise warn the user).
5. **Vercel project setup** for the client website:
   - `find_project_by_repo` → reuse if found, else `create_project`.
   - **CMS endpoint** — set `{prefix}CMS_ENDPOINT` (framework-aware prefix: `NEXT_PUBLIC_` for Next.js, `VITE_` for Vite, `PUBLIC_` for Astro/SvelteKit) to the **locale-less base** `{cms_endpoint_base}/content/{slug}` on **BOTH** production AND preview (the SAME value — do NOT suffix preview with `/draft`). The site appends `/{locale}` and `/draft` itself at fetch time; draft-vs-published is decided by the **token's presence**, not the URL.
   - **Preview token** — do **NOT** set a `NEXT_PUBLIC_*`/prefixed token (that inlines a credential into the client bundle), and do **NOT** PATCH `preview_token` onto the project row (`AdminProjectPatchIn` deliberately drops it — audit BE-004 — so the PATCH is a silent no-op that leaves the DB token NULL while Vercel has one → `/draft` 401s → drafts never show). Instead, provision it via the **rotate endpoint**, the single writer of both stores:
     - If the project row has no `preview_token`, `POST /admin/projects/{slug}/rotate-preview-token` (admin bearer). It writes the DB `preview_token` AND the Vercel **`CMS_PREVIEW_TOKEN`** (server-only key, preview target). It returns the token.
     - Mirror that token onto Vercel yourself too — `set_env_var("CMS_PREVIEW_TOKEN", token, target=["preview"])` (literal unprefixed key) — because rotate skips its Vercel write silently when the backend `VERCEL_TOKEN` is unset. Set this BEFORE triggering the build.
     - The token key is the server-only **`CMS_PREVIEW_TOKEN`** for Next.js sites (read only in server components / `i18n/request.ts`, never a client component).
     - **Vite + React 19 SPA sites** also set **`VITE_CMS_PREVIEW_TOKEN`** on the Vercel **preview** environment (preview-only; absent on production). This is the client-visible env var `src/lib/cms-content.ts` reads via `import.meta.env.VITE_CMS_PREVIEW_TOKEN` to branch draft vs. published. Value is the same DB token.
     - Re-runs are idempotent: reuse the existing DB token, never rotate when one already exists.
   - Create `cms-preview` branch from production branch if missing.
   - Trigger production + preview deployments (env + token must already be set so the build/runtime carries them).
   - PATCH the CMS project row with `github_repo`, `production_branch` (resolved in this step from Vercel `productionBranch` or GitHub `default_branch` — see [AGENTS.md → Branch standardization](../AGENTS.md)), `vercel_project_id`, `production_url`, `preview_url`. **Never** `preview_token` (see above).
   - **On the Vercel env "duplicates":** Vercel scopes env vars per environment, so the same key shows a separate **Preview** and **Production** row — that is NORMAL, not a duplicate. A genuine duplicate only appears if a re-run requests a different *target set* than the stored row (`set_env_var` matches on key + exact target set), so keep target sets stable across runs.
6. **Commit `cms.config.json`** to the client repo and push (uses Phase 1's git origin).

### 4.1.6 — Content wiring: EVERY provisioned service must drive the live site

**Non-negotiable rule:** every content service you provision must be *consumed* by
the rendered site. A service that is editable in the dashboard but does not change
the live site (because the site reads a static constant instead) is a bug — the
owner edits it, publishes, and nothing happens. This is the #1 content
failure mode (see the samir-kapsalon follow-up in `LEARNINGS.md`).

Most website-builder sites render text via **next-intl messages** and render
non-text data (images, hours, contact, brand) from **static constants in
`lib/site.ts`**. The deep-merge bridge only covers text whose service key maps to a
`t()` namespace — so `image`/`gallery` services and `opening_hours`/`contact_info`/
`general_brand_name` get silently dropped. You MUST close that gap:

0. **Draft vs published fetch (so cms-preview AND localhost show SAVED-but-unpublished
   edits).**

   **Next.js sites — `lib/cms-content.ts` branches on the server-only `CMS_PREVIEW_TOKEN`:**
   - Token present (preview deployment + localhost `.env.local`) → fetch
     `{base}/{locale}/draft` with header `X-CMS-Preview-Token: <token>` and
     `cache: "no-store"`. This shows the latest SAVED draft before publishing.
   - Token absent (production) → fetch `{base}/{locale}` (published) with
     `next: { revalidate: 60 }`.
   - **Safe fallback chain (never throw):** draft fetch not-ok/401 → retry the
     published URL; published not-ok → return the local `messages` seed. So a
     missing/0-length token or an unreachable CMS degrades gracefully, never a 500.
   - Read the token via `process.env.CMS_PREVIEW_TOKEN` in this server-only module
     (it is imported only by `i18n/request.ts`); NEVER reference it from a client
     component (that would inline the credential into the public bundle).
   - `.env.local` for localhost must set `CMS_PREVIEW_TOKEN` (matching the DB token)
     so the developer sees drafts locally exactly like cms-preview.
   The canonical multilingual reference is the samir-kapsalon `lib/cms-content.ts`
   (single-locale sites: the it-global-services `src/lib/cms.ts` pattern).

   **Vite + React 19 SPA sites — `src/lib/cms-content.ts` branches on `VITE_CMS_PREVIEW_TOKEN`:**
   - This is a client-side TanStack Query fetch (localStorage-persisted). Branch on the env var:
     - `VITE_CMS_PREVIEW_TOKEN` present (preview deploy + `.env.local`) → fetch
       `{base}/{locale}/draft` with header `X-CMS-Preview-Token: <token>`,
       `cache: 'no-store'`, TanStack `staleTime: 0`. Shows latest SAVED draft before publishing.
     - `VITE_CMS_PREVIEW_TOKEN` absent (production) → fetch `{base}/{locale}` (published)
       with a short TanStack `staleTime` (e.g. 60 000 ms). **No `next:{revalidate}` / ISR** —
       CMS publish appears on the next client load; the crawler SSG snapshot refreshes on rebuild.
   - Same safe fallback chain: draft not-ok/401 → retry published URL; published not-ok → return
     the local `src/i18n/messages/<locale>.json` seed. Never throws.
   - `.env.local` for localhost must set `VITE_CMS_PREVIEW_TOKEN` (matching the DB token)
     so the developer sees drafts locally, identical to the preview deploy.

1. **`lib/cms-content.ts`** — deep-merges the fetched per-locale payload (draft or
   published per point 0) over the local `messages/<locale>.json`. It must map EVERY
   service type, not a subset:
   - `text_block` → a message key (e.g. brand name).
   - `key_value` → the matching next-intl namespace's `entries` (ENTRY_NS map).
   - `repeater` → the namespace's items array.
   - `image` → a `site.*` url string.
   - `gallery` → a `site.*` url array.
   Inject the non-text services under a dedicated **`site`** namespace in the merged
   messages (brandName / contact / hours / heroImage / aboutImages / galleryImages /
   …). Map service keys to the site's ACTUAL `t()` namespaces — the scan's keys
   often don't match the built site's namespaces, so reconcile them here.

   **Vite + React 19 SPA — `src/lib/cms-content.ts`:** same per-service-type mapping and
   dedicated `site` namespace as above — the merge logic is IDENTICAL. The only differences are:
   - File path: `src/lib/cms-content.ts` (under `src/`).
   - Fetch mechanism: client-side **TanStack Query** with localStorage persistence (not `getMessages()`).
   - Seed path: merges over `src/i18n/messages/<locale>.json` (NOT `messages/<locale>.json`).
   - A build-time SSG snapshot bakes published content; the client refetch keeps humans fresh.
   The same `t("<service_key>.<field>")` namespaced-key shape is consumed by react-i18next `useTranslation`,
   so the same service keys and namespace layout apply across both frameworks.

2. **`lib/cms-site.ts`** — export `resolveSite(messages)` returning the site data
   with a SAFE FALLBACK to the `lib/site.ts` constants when a service is absent
   (the site must never break if the CMS is unreachable). Do the shape bridging
   here once (e.g. derive `tel:` href from a phone string, build the Instagram URL
   from a handle, split a one-line address, override only the TIMES on the weekly
   hours rows). Components call `resolveSite(await getMessages())` (Server) or
   `resolveSite(useMessages())` (Client) and read from it INSTEAD of importing the
   static constant directly.

   **Vite + React 19 SPA — `src/lib/cms-site.ts`:** `resolveSite(messages)` contract is
   UNCHANGED — same safe-fallback to `src/lib/site.ts` constants, same shape bridging. The only
   difference is that components read merged messages via the react-i18next context
   (`useTranslation`) instead of `getMessages()`. Components call
   `resolveSite(mergedMessages)` where `mergedMessages` is the TanStack-hydrated object
   from `src/lib/cms-content.ts`.

3. **Audit before declaring done — check EVERY render surface, not just one.** For
   each provisioned service key, confirm a component consumes its resolved value.
   Grep the client repo for direct imports of `lib/site.ts` constants that shadow a
   CMS service (`HERO_IMAGE`, `BUSINESS`, `HOURS`, `GALLERY_IMAGES`, …) — each such
   usage must be replaced by `resolveSite`. A service with no consumer is either
   wired or removed from the manifest; never leave it editable-but-inert.
   (Canonical reference: the samir-kapsalon `lib/cms-content.ts` + `lib/cms-site.ts`.)

   **The same data is often rendered in MULTIPLE places — wire ALL of them.** A
   service is only "wired" if *every* surface that displays it reads the CMS, not a
   parallel static duplicate. Real partial-wiring bugs found in shipped sites:
   - **Logo/brand** rendered in Home/About from CMS but HARDCODED in the Header
     (shows on every page), Footer, and MobileMenu (it-global-services).
   - **Staff name/portrait/tags** read from a static `TEAM` constant on the team
     page while only role/bio came from the CMS repeater (samir-kapsalon).
   - **CV/experience/projects** wired in the GUI views but rendered from static
     constants in a SECOND surface (a terminal emulator) (laurian portfolio).
   So for each service, grep ALL usages of its data across the repo — chrome
   (header/footer/mobile menu), every page, AND any alternate/secondary view — and
   confirm each reads the resolved CMS value. A static constant may exist ONLY as a
   fallback INSIDE the resolver, never as a parallel render path.

4. **Reconcile the DB against the manifest — no orphan services.** After
   provisioning, list `project_services` for the slug and diff against the manifest
   keys. Any service in the DB that is NOT in the manifest (and not consumed by the
   repo) is editable-but-inert clutter in the owner's dashboard (e.g. a stray
   empty `contact_intro` with a colliding `display_order`, found on laurian). Either
   wire it (add to the manifest + a render path) or DEPROVISION it (delete its
   `content_entries` + `project_services` row). Never leave a provisioned service
   the site can't render.

5. **Note on uploaded images:** CMS image uploads may be served as relative
   `/images/uploads/*` (committed to the client `public/`) or absolute URLs. If a
   future upload host differs from the site's `next.config` `images.remotePatterns`,
   `next/image` will reject it — add the host (or a loader) when wiring galleries.

### 4.1.7 — SEO-area wiring (consume the SEO/GEO Optimizer's public endpoints)

The **SEO/GEO Optimizer** agent owns the `seo_*` tables and writes per-route SEO meta
(`seo_page_meta`) + articles (`seo_articles`) autonomously. Generated sites must CONSUME its
public read endpoints so that stored SEO reaches the live site. (See
[AGENTS.md → SEO/GEO area contract](../AGENTS.md).)

**Hard rule:** NEVER provision the `seo_*` tables as content services and NEVER clobber them —
this phase only WIRES consumption of the public read endpoints.

1. **Backend base env.** The SEO endpoints live on the same backend as content; reuse the
   existing backend base (the `{prefix}CMS_ENDPOINT` base / the bare backend base already set
   for content + booking). No new secret is needed — `GET /projects/{slug}/seo/public/{meta,articles}`
   is public (ETag/ISR).

**Next.js sites:**

2. **Generate `lib/seo-meta.ts`** (mirrors `lib/cms-content.ts`: ISR + never-throw fallback).
   It exports a fetch helper that calls
   `GET {backend}/projects/{slug}/seo/public/meta?route=<route>&locale=<active-locale>` (the
   **active** next-intl locale) with `next: { revalidate: 60 }`, and on any non-ok/error
   returns `null` so the caller falls back to the build-time `seo-pro` output. It NEVER throws.
   **The per-field default-locale fallback is now SERVER-SIDE** — the public endpoint fills any
   missing/untranslated locale field from the project's default-locale row, so the helper
   fetches **one** active-locale response and **never merges locales itself** (it never sees an
   empty translated field).

3. **Wire `generateMetadata` to prefer stored meta + generate coded tags itself per locale.**
   Each page's `generateMetadata` calls the helper for the active locale; when it returns
   stored prose (`title`/`description`/`og` text + JSON-LD data), PREFER it over build-time;
   otherwise keep the build-time `seo-pro` output. The **coded tags are generated LOCALLY per
   active locale** — `canonical`, `hreflang` (`alternates.languages`), `og:locale`, and JSON-LD
   `inLanguage` are language-invariant **codes**, NOT fetched; the site emits them itself per
   locale. **SSR every locale** (each locale's content lands in the raw HTML, not just the
   default — AI/Google bots don't run JS).

4. **`/blog` only when articles exist — ACTIVE locale, server-side fallback (Next.js).** Provision/wire
   the `/blog` index + `/blog/[slug]` (fetching
   `GET {backend}/projects/{slug}/seo/public/articles?locale=<active-locale>` + `/{articleSlug}`,
   ISR + fallback) and set `projects.seo_blog_route` (e.g. `/blog`) ONLY once the SEO agent has
   created articles — typically when the SEO agent drives this via a `site-change-spec`
   `cms_wiring` block (the Website Builder incremental mode adds the route). An untranslated
   article transparently shows default-locale prose because the endpoint applies the per-field
   default fallback **server-side** — the site does not merge. Do not scaffold an empty `/blog`
   on a normal connector run.

**Vite + React 19 SPA sites:**

2. **Generate `src/lib/seo-meta.ts`** (build-time SSG snapshot + optional client TanStack refetch;
   never throws). It exports a fetch helper that calls
   `GET {backend}/projects/{slug}/seo/public/meta?route=<route>&locale=<locale>` at **build time**
   for the SSG snapshot; optionally also as a SEPARATE client TanStack Query for freshness (its
   own query — NOT the build-time in-process meta cache, which is build-process-only). On any
   non-ok/error returns `null` so the caller falls back to the build-time `seo-pro` output. It
   NEVER throws. The per-field default-locale fallback is SERVER-SIDE (same as Next): the endpoint
   fills any missing/untranslated field, the helper never merges locales itself.

3. **No `generateMetadata` — use `src/lib/head.ts` with React 19 hoisted tags.** There is no
   `generateMetadata` in Vite SPAs. Instead, `src/lib/head.ts` emits React 19 hoisted
   `<title>`, `<meta>`, and `<link>` tags. When `src/lib/seo-meta.ts` returns stored prose
   (`title`/`description`/`og` text + JSON-LD data), PREFER it over build-time; otherwise keep
   the build-time `seo-pro` output. The **coded tags are generated LOCALLY per active locale**
   — `canonical`, `hreflang`, `og:locale`, and JSON-LD `inLanguage` are emitted by `src/lib/head.ts`
   per locale without fetching. The endpoint applies per-field default-locale fallback server-side
   so the site never merges locale fields itself.

4. **`/blog` + `/blog/:slug` — pre-rendered from build-time article slugs (Vite).** Pre-render
   the `/blog` index + `/blog/:slug` from build-time article slugs fetched via
   `GET {backend}/projects/{slug}/seo/public/articles?locale=<locale>`; add a client TanStack
   refetch for freshness. Set `projects.seo_blog_route` (e.g. `/blog`) ONLY once the SEO agent
   has created articles. An untranslated article transparently shows default-locale prose because
   the endpoint applies the per-field default fallback server-side. Do not scaffold an empty
   `/blog` on a normal connector run.

### 4.2 — Booking provisioning (only if `booking.detected` in manifest)

Run after step 3 (services provisioned). Follow this sub-order exactly — do not reorder.

**a. Enable the booking backend first**

```
POST /projects/{slug}/bookings/enable
```

This must succeed before any subsequent booking calls are made. If it returns 409 (already enabled), continue.

**b. PATCH settings**

```
PATCH /projects/{slug}/bookings/settings
```

Body fields (all required):
- `destination_email` — use the value Stefan edited into the Phase-2 report; if blank/absent fall back to `stefanromanpers@gmail.com`.
- `business_name` — from manifest `booking.business_name`.
- `accent_color`, `primary_color` — brand colors from manifest.
- `calendar_provider: "none"` — always `"none"` at this stage; no calendar sync.
- `reminder_offsets` — list of hour-offsets from manifest.

**c. Create resources, then services, then hours — in this order**

1. `POST /projects/{slug}/bookings/resources` for each resource in `booking.resources`. Capture returned `resource_id` values. Include `image_url` when the manifest carries a staff portrait — it surfaces as the staff avatar on the owner's calendar and the customer booking flow. When absent/empty, both UIs fall back to a default placeholder avatar (a photo is never required). Staff avatars are editable later in the dashboard under **Bookings → Staff**.
2. `POST /projects/{slug}/bookings/services` for each service in `booking.services`. Each service must reference at least one `resource_id` from step c-1.
3. `PUT /projects/{slug}/bookings/hours` — post the weekly hours grid (weekday 0=Sun … 6=Sat, open/close times).

**d. Generate `lib/booking.ts` + set env var**

- Generate `lib/booking.ts` in the client repo. This file exports `getServices`, `getAvailability`, and `createBooking` wired to `{ENVPREFIX}BOOKING_API_BASE`.
- Set the env var with the framework-aware prefix:
  - Next.js → `NEXT_PUBLIC_BOOKING_API_BASE`
  - Vite → `VITE_BOOKING_API_BASE`
  - SvelteKit → `PUBLIC_BOOKING_API_BASE`
- Value: the **bare backend base URL** (e.g. `https://cms-backend-roman.vercel.app`). Do NOT append `/booking/{slug}` — `lib/booking.ts` appends that path itself. Appending it here would double the path and break all booking calls.

**e. Wire the design's booking UI to `lib/booking.ts`**

Connect the components listed in `booking.ui_wiring.components` (or the iframe fallback) to the generated lib:
- Service picker → `getServices()`
- Date/time selector → `getAvailability(serviceId, from, to)`
- Form submit → `createBooking(payload)` → on success, display the returned `manage_url`
- Do **not** build a reschedule/cancel UI in the client repo.

**f. Reschedule / cancel via centralized manage page**

The `manage_url` returned by `createBooking` points to the CMS-hosted `/manage/{token}` page. Customers use that page directly for rescheduling and cancellation. No client-side manage UI is needed or should be built.

## Failure feedback

| Cause | Message |
|-------|---------|
| CMS admin API 401 | "CMS admin token rejected. Refresh `CMS_API_TOKEN`." |
| Service create 409 | "Service `<key>` already exists in project `<slug>`. Choose: skip / overwrite / abort." |
| Resend env vars missing | "RESEND_API_KEY or RESEND_FROM_EMAIL not set on CMS Vercel project. Set them in Vercel dashboard, then re-run Phase 4." |
| Resend domain not verified | "Resend from-domain `<domain>` is not verified. Verify in Resend dashboard before forms will send." |
| Vercel 403 / token bad | "Vercel token rejected. Refresh `VERCEL_TOKEN`." |
| GitHub push 403 | "Cannot push to `<repo>`. Check `GITHUB_TOKEN` has write access." |

## Token tactics

- Do **not** dump full HTTP responses to chat. One status line per sub-step.
- For idempotency checks, prefer a single GET to fetch project state, then make decisions in code — avoid chained probes.
- When `_provision` runs, log only: created N services, seeded M with initial content, K skipped/conflicted.

## Model policy

Code integration is correctness-critical. Any LLM call made during this phase
(resolving service-shape mismatches, deciding overwrite vs. skip on 409
conflicts, debugging Vercel / Resend wiring, mapping client repo structure to
build commands) **must use `claude-opus-4-8`** with effort `xhigh`. Do not downgrade to Sonnet or
Haiku to save tokens — a wrong integration decision cascades through Phase 5
and into production.

## Self-improvement hook

If a failure mode recurs, append to `LEARNINGS.md` under `## Phase 4 — Integration rules`. Examples:
- `- 2026-05-03: Always verify Resend domain before pushing email_config service. Triggered by: production form 502 because domain wasn't verified.`
- `- 2026-05-15: Production deploys must use Vercel alias[0], not the per-deploy URL. Triggered by: stale URL stored in CMS project row.`
