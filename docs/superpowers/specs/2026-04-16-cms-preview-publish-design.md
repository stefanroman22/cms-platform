# CMS Preview & Publish — Design Spec

**Date:** 2026-04-16
**Status:** Approved (brainstorm), ready for implementation plan
**Feature:** "See Preview" + "Publish Changes" buttons for CMS clients

---

## Problem

Today, every save in the CMS is instantly live on the client's public website. Clients have no way to:

1. Preview their changes before they go live.
2. Batch edits into a single publish event.

Laurian edits his CV → the public portfolio updates immediately, even mid-edit.

## Goal

- **See Preview** — clicking it takes the client to a live preview URL rendering their current draft content. Zero setup from the client side.
- **Publish Changes** — atomically promotes all draft content to production.
- Both buttons are available on the project overview page and on every service editor page.
- Onboarding a new client (agent run) sets up everything needed for this flow end-to-end.

## Architectural Decisions (locked during brainstorm)

| # | Decision |
|---|---|
| 1 | Preview is a Vercel preview deployment, not a local sandbox. |
| 2 | Stefan owns all client Vercel projects under one Vercel account. |
| 3 | Draft vs published stored as two JSONB columns on `content_entries`. |
| 4 | Publish is project-wide ("Publish All"), not per-service. |
| 5 | Preview deployment reads draft content via a separate endpoint, selected by a per-environment env var. |
| 6 | Agent extends to fully automate Vercel setup during onboarding. |
| 7 | GitHub repo is the source of truth for deploys (clients must have a repo). |
| 8 | One Vercel project per client, with `main` → production and a persistent `cms-preview` branch → preview. |

## System Overview

```
                                       ┌──────────────────────────┐
                                       │  Client (Laurian)        │
                                       │  uses CMS dashboard      │
                                       └────────────┬─────────────┘
                                                    │ edits + save
                                                    ▼
      ┌─────────────────────────────────────────────────────────────────┐
      │  Supabase: content_entries                                      │
      │    published_content   draft_content                            │
      └───────────────┬──────────────────────┬──────────────────────────┘
                      │ published            │ draft
                      ▼                      ▼
          ┌──────────────────────┐   ┌──────────────────────────────┐
          │ GET /content/{slug}  │   │ GET /content/{slug}/draft    │
          │ (public)             │   │ (X-CMS-Preview-Token header) │
          └──────────┬───────────┘   └──────────────┬───────────────┘
                     │                              │
                     ▼                              ▼
         ┌──────────────────────┐      ┌────────────────────────────┐
         │ Vercel: main branch  │      │ Vercel: cms-preview branch │
         │ → production_url     │      │ → preview_url              │
         └──────────────────────┘      └────────────────────────────┘
```

---

## 1. Data Model

### `content_entries` — schema change

| Column | Change |
|---|---|
| `content` (JSONB) | **Rename** to `published_content`. |
| `draft_content` (JSONB, nullable) | **Add.** Nullable; new services may not have drafts distinct from published yet. |

**Write semantics:**
- CMS admin-UI edits → update `draft_content` only.
- Agent seeding (first provision) → update both `draft_content` and `published_content` to the same value.
- Publish action → copy `draft_content` → `published_content` per row.

**"Has unpublished changes":** `published_content IS DISTINCT FROM draft_content` (Postgres null-safe).

**Services with `published_content IS NULL`** (a brand-new service created in CMS, never published) are filtered out of the public `/content/{slug}` response so unpublished services never leak to production.

### `projects` — new columns

| Column | Type | Purpose |
|---|---|---|
| `github_repo` | text | e.g. `lauriand/portfolio`. Source of Vercel deploys. |
| `vercel_project_id` | text | Returned by Vercel on project create. |
| `production_url` | text | Stable production URL (from `main` branch deployment). |
| `preview_url` | text | Stable preview URL (from `cms-preview` branch deployment). |
| `preview_token` | text | 32-char URL-safe random. Required in `X-CMS-Preview-Token` header by `/content/{slug}/draft`. |
| `last_published_at` | timestamptz, nullable | Bumped on each Publish; shown as "Last published Xh ago" in UI. |

One Supabase migration covers both tables.

---

## 2. Backend — Content & Publish Endpoints

### `GET /content/{slug}` *(existing, behavior change)*
- Public, no auth.
- Returns `published_content` for every service in the project.
- Filters out services with `published_content IS NULL`.
- Keeps existing `Cache-Control` (60s ISR-friendly).

### `GET /content/{slug}/draft` *(new)*
- Requires header `X-CMS-Preview-Token: <project.preview_token>`.
- Returns `draft_content` per service, falling back to `published_content` where `draft_content IS NULL`.
- `Cache-Control: no-store` — preview must always be fresh.
- `401` on missing/wrong token.

### `PUT /projects/{slug}/services/{service_key}` *(existing, behavior change)*
- Default (CMS admin UI): writes `draft_content` only.
- With query `?seed=true` (agent only, requires admin auth): writes both `draft_content` and `published_content`.

### `POST /projects/{slug}/publish` *(new)*
- Auth: project owner or admin.
- Executes one atomic SQL statement:
  ```sql
  UPDATE content_entries
  SET published_content = draft_content
  WHERE service_id IN (SELECT id FROM services WHERE project_slug = $1)
    AND published_content IS DISTINCT FROM draft_content;
  ```
- Also: `UPDATE projects SET last_published_at = now() WHERE slug = $1`.
- Returns `{ published_count: N, last_published_at: <ts> }`.
- No Vercel API call needed — the production deployment picks up changes on next ISR revalidation (≤ 60 s).

### `GET /projects/{slug}/status` *(new)*
- Returns `{ unpublished_count: N, last_published_at: <ts>, preview_url, production_url }`.
- Used by `PreviewPublishBar` to render badges.

### `POST /admin/projects/{slug}/rotate-preview-token` *(new, admin-only)*
- Regenerates the preview token, updates the row, calls Vercel API to update the `CMS_PREVIEW_TOKEN` env var on the preview environment.
- No UI in v1; exists as a recovery endpoint if a token leaks.

---

## 3. Agent Changes (`backend/agent/scan.py`)

### New CLI flags

| Flag | Purpose |
|---|---|
| `--github-repo OWNER/NAME` | Required for Vercel setup. |
| `--vercel-token` | Vercel API token (default: env `VERCEL_TOKEN`). |
| `--github-token` | GitHub API token for branch creation (default: env `GITHUB_TOKEN`). |
| `--skip-vercel` | Escape hatch: content-only re-provision. |

### New Vercel setup phase

Runs after existing content provisioning, only if `--github-repo` provided and `--skip-vercel` absent:

1. **Generate preview token** — 32-char URL-safe random. POST to CMS admin API to save on `projects.preview_token`.
2. **Create Vercel project** via Vercel REST API:
   - Linked to `github_repo`.
   - Framework auto-detected.
   - Save returned `vercel_project_id` via CMS admin API.
3. **Set env vars** (per Vercel environment):
   - **Production:** `CMS_ENDPOINT=https://cms.romantech.com/content/<slug>`
   - **Preview:** `CMS_ENDPOINT=https://cms.romantech.com/content/<slug>/draft`, `CMS_PREVIEW_TOKEN=<preview_token>`
4. **Create `cms-preview` branch** via GitHub API (branched from `main`). Skip if branch already exists.
5. **Trigger initial deployments:**
   - Production from `main` → capture `production_url`.
   - Preview from `cms-preview` → capture `preview_url`.
6. **Save URLs** on the `projects` row via CMS admin API.

### Idempotency rules

- Service exists → skip creation, continue to content seed.
- Vercel project exists for this `github_repo` → fetch its ID, skip create.
- `cms-preview` branch exists → skip create.
- Env vars already set → update in place (Vercel API supports upsert).

Running the agent twice against the same project must not duplicate resources, change existing tokens, or re-seed content (unless explicitly requested with a future `--reseed` flag — out of scope for v1).

### Failure modes

- Content provisioning succeeds but Vercel fails → log error loud; re-run the agent (idempotency rules skip already-provisioned content) or fix manually in Vercel + paste IDs via admin API.
- GitHub branch creation fails → agent errors out before deploying. User can create branch manually and re-run.

---

## 4. Frontend — `PreviewPublishBar` component

### Placement

One component used in two routes:

1. `/dashboard/[projectSlug]` — project overview, sticky at top.
2. `/dashboard/[projectSlug]/[serviceKey]` — service editor, sticky at top.

### Props

```ts
interface PreviewPublishBarProps {
  projectSlug: string;
}
```

Component fetches status via `GET /projects/{slug}/status` on mount and polls every 30 s while visible.

### Layout

```
┌─────────────────────────────────────────────────────────────────────┐
│  [🔗 See Preview]          2 unpublished changes  [✓ Publish Changes]│
│                            Last published 3h ago                     │
└─────────────────────────────────────────────────────────────────────┘
```

### Left: See Preview button

- Always enabled if `preview_url` is set.
- Click → `window.open(preview_url, '_blank')`.
- If `preview_url` is null → disabled state + tooltip "Preview not set up — contact admin."

### Right: Publish cluster

- **"N unpublished changes"** badge — hidden when `N = 0`.
- **Publish Changes** button:
  - Disabled (grey) when `N = 0`.
  - Enabled + primary color when `N > 0`.
  - Click → confirm modal: *"Publish N changes to production? {project.name} will update within ~1 minute."* with Publish / Cancel.
  - On confirm → `POST /projects/{slug}/publish`, then success toast "Published — live within 60 seconds," then refetch status.
- **"Last published Xh ago"** — muted text beneath button. Hidden if `last_published_at` is null.

### States

| State | Behavior |
|---|---|
| Loading status | Bar renders with disabled buttons + skeleton badges. |
| Publish in flight | Button shows spinner; both buttons disabled. |
| Publish error | Toast with server error; bar re-enables. |
| No changes (`N = 0`) | Publish disabled; badge hidden. |

---

## 5. Edge Cases

| Case | Handling |
|---|---|
| Service deleted with draft changes | Delete row; production loses service on next publish. Treat deletion as a draft action (live until Publish All). |
| Service added, never published | `published_content IS NULL` → filtered from `/content/{slug}`. Production doesn't see it until Publish. |
| Publish with zero changes | Frontend disables button; backend SQL no-ops gracefully. |
| Preview token leaked | Admin calls `POST /admin/projects/{slug}/rotate-preview-token` — regenerates + updates Vercel env var. |
| Agent re-run on existing project | Idempotency rules (§3) preserve all IDs, tokens, timestamps. |
| ISR cache lag after publish | Toast says "live within 60 seconds." Optional v2: Vercel deployment cache purge for instant. |

---

## 6. Testing Strategy

### Backend (pytest, real Supabase test project)

- `/content/{slug}` returns only `published_content`; excludes services with null published.
- `/content/{slug}/draft` requires token; returns draft with fallback to published.
- `POST /publish` copies draft→published, bumps `last_published_at`, is idempotent, handles zero-change case.
- `PUT /services/{key}?seed=true` writes both columns; default call writes only draft.

### Agent (pytest, mocked Vercel + GitHub APIs)

- Full onboarding path: services created, Vercel project created, env vars set, branch created, URLs saved.
- Idempotent re-run: no duplicate resources, no token change.
- `--skip-vercel` path still provisions content.

### Frontend (Vitest + Testing Library)

- `PreviewPublishBar` renders correctly for: no preview url, 0 changes, N changes, publishing, error.
- Confirm modal: cancel does nothing, confirm calls publish endpoint, success refetches.
- Status polling restarts on slug change.

### Manual E2E smoke test (documented in plan)

1. Run agent against Laurian's portfolio with `--github-repo lauriand/portfolio`.
2. Open the CMS dashboard; edit "CV" service; save.
3. Open `production_url` → unchanged.
4. Click "See Preview" → opens `preview_url` → change visible.
5. Click "Publish Changes" → confirm → toast.
6. Wait ≤ 60 s, refresh `production_url` → change visible.

---

## Out of Scope (v1)

- Per-service publish button.
- Version history / rollback of published content.
- Multi-tenant Vercel OAuth (each client with their own Vercel account).
- Automatic Vercel cache purge on publish.
- UI for preview token rotation.
- Reseeding content on agent re-run.

These are all additive — none require rework of v1 data model or endpoints.
