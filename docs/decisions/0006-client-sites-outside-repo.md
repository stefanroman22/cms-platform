# ADR-0006: Client sites live outside this repo and connect over HTTP only

Status: Accepted
Date: 2026-09-27

## Context

Each client website is a different design and often a different framework (Next.js, Vite + React).
Clients may take their site elsewhere, and a mistake in one client's code must not affect the CMS
or other clients. Agents build and wire these sites automatically.

## Decision

- Every client site has its own GitHub repo (`stefanroman22/<name>`) and its own Vercel project.
  No client site code lives in this repo.
- Client sites talk to the CMS only over the backend's public HTTP API: `/content/{slug}…`,
  `/booking/{slug}/…` and `/forms/{slug}/{form_key}`. The CMS Connector agent
  (`agents/CMS Connector - Website/`) generates each site's integration code and provisions the
  repo, the Vercel project, the CMS project, its services and seed content.
- A tenant is a project: one `projects` row per client site, keyed by slug. Booking, content,
  and forms data are all scoped by project.
- Client Vercel projects have Vercel Authentication OFF for production and preview, so the
  dashboard's preview link works for clients. Our own projects (`cms-backend-roman`,
  `roman-technologies`) have it OFF in production (`security/RUNBOOK.md`, Vercel
  deployment-protection invariants; `scripts/disable_vercel_auth.py`).

## Consequences

- Client sites are independent: they can be rebuilt, moved or deleted without touching the CMS,
  and the CMS can be deployed without redeploying them.
- The public API is a contract with sites this repo cannot see. A breaking change to a public
  endpoint or response shape breaks live client sites silently.
- Client branches (`cms-preview`, and `main` or `master` for production) are managed by the
  connector, and `cms-preview` can go stale.
- Do NOT: change public endpoint paths or response shapes without versioning or a migration plan
  for existing sites, add per-client special cases to the backend, move client code into this repo,
  or turn Vercel Authentication on for client preview deployments.
