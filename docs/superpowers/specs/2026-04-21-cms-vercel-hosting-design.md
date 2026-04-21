# CMS on Vercel — Design Spec

**Date:** 2026-04-21
**Status:** Approved (brainstorm), ready for implementation plan
**Feature:** Host the CMS platform (Next.js frontend + FastAPI backend) on Vercel, publicly reachable over HTTPS.

---

## Motivation

The CMS is currently localhost-only. That's fine for developer work but blocks three scenarios:
- Hosted client preview deployments (on Vercel) can't fetch from `http://localhost:8001` — Chrome's Local Network Access policy blocks HTTPS → HTTP loopback as of Chrome 123+, even with server-side PNA headers.
- Sharing the CMS admin UI with teammates requires tunneling.
- The agent's `scan.py` hardcodes `https://cms.romantechnologies.com/content` as the public endpoint — currently unreachable.

Goal: a reachable, production-ready CMS URL that client websites (and their Vercel preview builds) can query directly.

## Non-goals (v1)

- Custom domain (`cms.romantechnologies.com`) — Vercel subdomains only for now.
- Migrating Supabase; existing CMS Supabase project is reused.
- Production observability (Sentry, rate limit tuning). Existing `slowapi` config stays as-is.
- Automatic promotion of all existing client portfolios. Only Laurian's portfolio env var is updated (follow-up commit).

## Architectural Decisions (locked during brainstorm)

| # | Decision |
|---|---|
| 1 | Two independent Vercel projects: `cms-frontend-roman` + `cms-backend-roman`. |
| 2 | Frontend's existing `/api/[...path]/route.ts` catch-all proxy is repointed at the backend Vercel URL via `FASTAPI_URL` env var (no code change needed — already env-var-driven). |
| 3 | Backend wraps existing FastAPI app as one Vercel Python serverless function (`vercel_entry.py` re-exports `app`). |
| 4 | JWT keys embedded as base64-encoded env vars (`JWT_PRIVATE_KEY_B64`, `JWT_PUBLIC_KEY_B64`). `config.py` reads env var first, falls back to file for local dev. |
| 5 | `access_token` cookie switches to `SameSite=None; Secure` in production (required for cross-origin frontend↔backend on different Vercel subdomains). |
| 6 | Backend CORS adds the frontend Vercel URL to its allowed origins list in production. |
| 7 | `master` is the canonical deployment branch. `feat/cms-preview-publish` merges to `master` before deployment. |
| 8 | No schema migration. Supabase remains the CMS DB unchanged. |

## System Overview

```
                     Internet (HTTPS)
                           │
            ┌──────────────┼──────────────┐
            ▼              ▼              ▼
  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐
  │   Admin UI   │  │  Laurian's   │  │ Other client │
  │ user browser │  │   Vercel     │  │   websites   │
  │              │  │   preview    │  │              │
  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘
         │                 │                  │
         │ login/edit      │ fetch content    │ fetch content
         │                 │                  │
         ▼                 ▼                  ▼
  ┌─────────────────────────────────────────────────────┐
  │  cms-frontend-roman.vercel.app  (Next.js App Router)│
  │    /dashboard, /log-in, /api/* (proxy)              │
  └───────────────────────┬─────────────────────────────┘
                          │ /api/* → FASTAPI_URL
                          ▼
  ┌─────────────────────────────────────────────────────┐
  │  cms-backend-roman.vercel.app (FastAPI serverless)  │
  │    /auth, /projects, /content, /workspace, /publish │
  │    /forms (mounted sub-app), /admin                 │
  └───────────────────────┬─────────────────────────────┘
                          │
                          ▼
                   ┌──────────────┐
                   │   Supabase   │
                   │  (unchanged) │
                   └──────────────┘
```

---

## 1. Backend — Vercel Python Function

### New files

**`backend/vercel_entry.py`** (at the same level as `auth_service/` so the Python import resolves against the Vercel project root):
```python
"""Vercel Python entry point. Re-exports the FastAPI ASGI app so the
Vercel Python runtime can wrap it as a serverless function.
"""
from auth_service.main import app  # noqa: F401 — re-export for @vercel/python

# Vercel's @vercel/python builder discovers the ASGI `app` by name.
```

**`backend/vercel.json`** (the Vercel project root is `backend/`, so the paths are relative to that):
```json
{
  "builds": [
    { "src": "vercel_entry.py", "use": "@vercel/python" }
  ],
  "routes": [
    { "src": "/(.*)", "dest": "/vercel_entry.py" }
  ]
}
```

**`backend/requirements.txt`** (Vercel Python builder reads this from project root):
Copy `backend/auth_service/requirements.txt` content here, or make `backend/requirements.txt` a one-liner that `-r auth_service/requirements.txt`. The builder needs to see all deps at the project root level.

### Modified files

**`backend/auth_service/core/config.py`** — new key-loading logic:

```python
import base64
from pathlib import Path

@property
def private_key(self) -> str:
    env_b64 = os.environ.get("JWT_PRIVATE_KEY_B64")
    if env_b64:
        return base64.b64decode(env_b64).decode("utf-8")
    return Path(self.PRIVATE_KEY_PATH).read_text()

@property
def public_key(self) -> str:
    env_b64 = os.environ.get("JWT_PUBLIC_KEY_B64")
    if env_b64:
        return base64.b64decode(env_b64).decode("utf-8")
    return Path(self.PUBLIC_KEY_PATH).read_text()
```

(Actual import of `os` + `base64` is already in the file — spec code above is minimal.)

**`backend/auth_service/main.py`** — CORS origin regex is already extended in dev to include `*.vercel.app`. No change needed for production because `cors_origins` is driven from the `FRONTEND_ORIGINS` env var.

**Cookie settings** — wherever `access_token` / `refresh_token` cookies are set (likely `routers/auth.py`), in production:
- `samesite="none"`
- `secure=True`
- `httponly=True` (already the case)
- `domain` left unset (default → request host)

A helper like `_cookie_kwargs(request)` that returns the right combo based on `settings.ENVIRONMENT` keeps the cookie setter tidy.

### Vercel env vars (backend project)

| Var | Value | Scope |
|---|---|---|
| `ENVIRONMENT` | `production` | Production |
| `SUPABASE_URL` | (from existing `.env`) | Production |
| `SUPABASE_ANON_KEY` | (from existing `.env`) | Production |
| `SUPABASE_SERVICE_ROLE_KEY` | (from existing `.env`) | Production |
| `JWT_PRIVATE_KEY_B64` | base64 of `backend/keys/private.pem` | Production |
| `JWT_PUBLIC_KEY_B64` | base64 of `backend/keys/public.pem` | Production |
| `JWT_ALGORITHM` | `RS256` | Production |
| `RESEND_API_KEY` | (from existing `.env`) | Production |
| `FRONTEND_ORIGINS` | `https://cms-frontend-roman.vercel.app` | Production |

---

## 2. Frontend — Next.js on Vercel

### No code changes needed
`src/app/api/[...path]/route.ts` already reads `FASTAPI_URL` from `process.env`. Next.js auto-detects on Vercel. Zero config.

### Vercel env vars (frontend project)

| Var | Value | Scope |
|---|---|---|
| `FASTAPI_URL` | `https://cms-backend-roman.vercel.app` | Production + Preview |

`NODE_ENV=production` is set automatically by Vercel on production builds.

---

## 3. Deployment Flow

1. Merge `feat/cms-preview-publish` to `master` in the main repo. Push master.
2. Generate base64 of both PEM keys (PowerShell `[Convert]::ToBase64String(...)`).
3. Create Vercel project `cms-backend-roman`:
   - GitHub repo: `stefanroman22/CMS---websites`
   - Root directory: `backend/`
   - Framework preset: Other (custom — let `vercel.json` drive it).
4. Set backend env vars (all listed above).
5. Trigger first deploy on `master`. Verify `https://cms-backend-roman.vercel.app/health` returns `{"status":"ok"}`.
6. Create Vercel project `cms-frontend-roman`:
   - Same repo.
   - Root directory: `frontend/`.
   - Framework preset: Next.js (auto).
7. Set `FASTAPI_URL=https://cms-backend-roman.vercel.app`.
8. Trigger first deploy on `master`. Visit `https://cms-frontend-roman.vercel.app`.
9. Smoke test via UI: log in, browse to a project, edit a service, Publish Changes, confirm the draft/publish flow works across the two Vercel domains.

---

## 4. Follow-up Tasks (tracked but not part of this spec)

| # | Task | Est |
|---|---|---|
| F1 | Update `backend/agent/scan.py` `DEFAULT_ENDPOINT` to `https://cms-backend-roman.vercel.app/content` | 2 min |
| F2 | Update Laurian's portfolio Vercel env vars (`VITE_CMS_ENDPOINT`) to point at the public CMS backend URL | 2 min |
| F3 | Custom domain (`cms.romantechnologies.com`) wiring when DNS is ready | 10 min |
| F4 | Test end-to-end: Vercel-hosted Laurian portfolio preview → public CMS draft endpoint | 5 min |

These aren't in this spec's scope but are documented for follow-through.

---

## 5. Failure Modes & Handling

| Scenario | Handling |
|---|---|
| Vercel Python cold start >10s | FastAPI startup is lean (no DB connection pool eager-init; Supabase client is lazy). Should be <2s in practice. If cold starts hurt UX, add keepalive cron (out of scope). |
| Backend request body >4.5 MB | Vercel hobby tier caps at 4.5 MB. File uploads go directly to Supabase Storage, not through backend → OK. |
| Cookie not sent cross-origin | Verify `SameSite=None; Secure` landed. Browser DevTools → Application → Cookies shows the flags. |
| CORS blocked | Check `FRONTEND_ORIGINS` env var + backend `main.py` regex for the frontend's Vercel URL. |
| JWT key encoding bug | `config.py` unit test: seed env var with base64 of known PEM, verify `private_key` returns decoded value. |

---

## 6. Testing Strategy

### Backend unit tests (new)
- `test_config_reads_private_key_from_env_var` — seed `JWT_PRIVATE_KEY_B64`, verify decoded output matches original PEM.
- `test_config_falls_back_to_file_when_env_unset` — existing behavior preserved.

### Backend smoke tests (manual, post-deploy)
- `GET /health` on backend URL returns 200.
- `GET /content/laurian-duma-portfolio` returns published content.
- `POST /auth/login` with valid credentials returns 200 + sets cookies.

### Frontend smoke tests (manual, post-deploy)
- Load `https://cms-frontend-roman.vercel.app` → redirects to log-in.
- Log in → lands on project overview.
- Click into a service, edit a field, Save → "unpublished changes" badge appears.
- Click Publish Changes → success toast.
- DB check: `last_published_at` updated.

### Cross-origin cookie check
DevTools → Network → see `Set-Cookie` on the `/auth/login` response has `SameSite=None` and `Secure`. Subsequent `/auth/me` requests include the cookie.

---

## 7. Merge to master

Before deployment, the following branch merges happen:
- `feat/cms-preview-publish` → `master` (in main repo)

After this spec's implementation lands, it will be the first commit on `master` from this new spec. Agent / CMS deployments always pull from `master`.
