# Phase 4 — CMS integration

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

3. **Provision services** via CMS admin API:
   - `POST /projects/<slug>/services` per service.
   - `PUT /projects/<slug>/services/<key>` to seed `initial_content`. Skip seeding for `email_config`.
4. **Wire `email_config`** to Resend:
   - Set `destination_email` in the service's content.
   - Confirm backend env vars `RESEND_API_KEY` and `RESEND_FROM_EMAIL` are set on the CMS backend Vercel project. If missing, **halt** and ask the user to set them — do not write `RESEND_API_KEY` from the agent.
   - Verify the from-domain is verified in Resend (call Resend API `/domains` if reachable; otherwise warn the user).
5. **Vercel project setup** for the client website:
   - `find_project_by_repo` → reuse if found, else `create_project`.
   - Set env vars: `VITE_CMS_ENDPOINT` (production + preview), `VITE_CMS_PREVIEW_TOKEN` (preview only). Reuse existing `preview_token` from CMS project row if present (idempotent).
   - Create `cms-preview` branch from production branch if missing.
   - Trigger production + preview deployments.
   - PATCH the CMS project row with `github_repo`, `production_branch` (resolved in this step from Vercel `productionBranch` or GitHub `default_branch` — see [AGENTS.md → Branch standardization](../AGENTS.md)), `vercel_project_id`, `production_url`, `preview_url`, `preview_token`.
6. **Commit `cms.config.json`** to the client repo and push (uses Phase 1's git origin).

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
build commands) **must use `claude-opus-4-7`**. Do not downgrade to Sonnet or
Haiku to save tokens — a wrong integration decision cascades through Phase 5
and into production.

## Self-improvement hook

If a failure mode recurs, append to `LEARNINGS.md` under `## Phase 4 — Integration rules`. Examples:
- `- 2026-05-03: Always verify Resend domain before pushing email_config service. Triggered by: production form 502 because domain wasn't verified.`
- `- 2026-05-15: Production deploys must use Vercel alias[0], not the per-deploy URL. Triggered by: stale URL stored in CMS project row.`
