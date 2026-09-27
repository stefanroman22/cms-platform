# ADR-0002: All data access goes through the FastAPI backend

Status: Accepted
Date: 2026-09-27

## Context

The dashboard, the booking widget and client websites all need data from Supabase. Supabase makes
it easy to query the database straight from the browser with the anon key and to rely on Row Level
Security (RLS) for access control. This system's rules (who owns which project, admin vs client,
per-tenant booking limits, rate limits, input sanitising) are richer than RLS policies express well,
and one operator has to be able to reason about them in one place.

## Decision

- The browser never talks to Supabase and never sees the backend URL. The Next.js app calls its own
  `/api/[...path]` route (`frontend/src/app/api/[...path]/route.ts`), which forwards server-side to
  `FASTAPI_URL` with `cache: "no-store"`. The only caching exception is the public booking
  availability GET, whose `Cache-Control` is passed through so Vercel's CDN can serve repeats.
- FastAPI talks to Supabase with the service-role client (`get_supabase_admin()` in
  `services/supabase_client.py`), which bypasses RLS.
- Authorization is enforced in FastAPI: `routers/deps.py` checks project ownership
  (`project["user_id"] != user.id and not user.is_admin`).
- RLS is enabled on tenant tables only as defense in depth
  (`migrations/2026_05_09_tenant_tables_rls.sql`, `2026_06_08_security_anon_surface_hardening.sql`),
  in case a key or an anon path leaks.
- Client websites call the backend's public endpoints directly (`/content`, `/booking`,
  `/forms`); they never get Supabase keys either.

## Consequences

- One place to read and test every access rule; Supabase keys stay server-side.
- **The backend is the security boundary.** A missing ownership check in a router is a real data
  leak, because RLS does not stop the service-role client. Every new project-scoped endpoint must
  use the `deps.py` helpers.
- Every dashboard request pays an extra hop (browser → Next.js → FastAPI → Supabase).
- Do NOT: add `@supabase/supabase-js` or any Supabase key to the frontend or to client sites, call
  the backend URL from browser code, cache proxied responses by default, or treat RLS policies as
  the thing that protects data. Moving authorization into RLS needs a new ADR.
