# ADR-0009: Three environment tiers, one typed config, CORS per tier

Status: Accepted
Date: 2026-09-27

## Context

The same code runs on a laptop, on Vercel preview deployments of `dev`, and in production, all on
one database (ADR-0001). Client websites on their own domains and on `*.vercel.app` call the
backend from the browser. Past bugs came from silent config fallbacks: a missing
`FRONTEND_ORIGINS` once made production fall back to localhost-only CORS and reject every real
frontend with an opaque error.

## Decision

- **Tiers.** There are three tiers, selected by `ENVIRONMENT`, which is typed
  `Literal["development", "preview", "production"]` in `backend/auth_service/core/config.py`.
  Any other value, including typos, fails at startup.
  - `development` runs on a laptop and reads `backend/.env` / `frontend/.env.local` (git-ignored).
  - `preview` runs on Vercel preview deployments built from `dev`, with Vercel Preview env vars.
  - `production` runs on Vercel production deployments of `main`, with Vercel Production env vars.
  - Both Vercel projects must have Production Branch = `main`; otherwise the promote action's
    deploy hooks (ADR-0007) produce previews.
- **Config contract.** The typed `Settings` class in `core/config.py` is the single source of
  truth for backend variables. Env vars override `backend/.env`. A variable that is required in
  a tier gets a `model_validator` that fails startup when it is missing: production refuses to
  start without `FRONTEND_ORIGINS` or `SUPABASE_SERVICE_ROLE_KEY`.
- **Where variables live.**
  - Everything the FastAPI code reads is set on Vercel project `cms-backend-roman`.
  - The frontend project `roman-technologies` needs only the server-side `FASTAPI_URL` (ADR-0002).
  - Real values live only in the git-ignored local files and the Vercel dashboard.
  - The committed `.env.example` files hold placeholders only.
- **CORS per tier** (`backend/auth_service/main.py`):
  - development and preview allow a permissive origin regex (localhost, LAN, `*.vercel.app`) and
    enable Private Network Access.
  - production allows `FRONTEND_ORIGINS` plus `*.vercel.app`, so client sites on Vercel work, with
    credentials, and PNA off.
  - The public forms app (`/forms`) is a separate sub-app with `allow_origins=["*"]`, no
    credentials, and `POST`/`OPTIONS` only, so client sites on any domain can submit forms.
    Abuse control happens inside the handlers (rate limits), not in CORS.

## Consequences

- A misconfigured tier fails loudly at startup instead of misbehaving in production.
- A variable set on the wrong Vercel project fails silently. The frontend project never passes
  backend variables through.
- Adding a variable takes four steps: add it to `.env.example`, add it to `Settings`, set it in
  Vercel for every tier that needs it, and add a validator if it is required.
- Do NOT: read `os.environ` for new settings instead of adding them to `Settings` (the old
  `VERCEL_TOKEN` read in `routers/publish.py` is the exception, not the pattern); add a silent
  default for a production-required variable; widen the credentialed CORS allowlist to `*`; or
  add credentials or cookie-based auth to the `/forms` sub-app.
