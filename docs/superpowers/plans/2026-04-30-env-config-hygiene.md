# Environment Configuration Hygiene — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Eliminate the leaked secrets currently committed in this repo, sanitize all `.env*` files, remove dead Django-era code, standardize the environment-tier semantics (`development | preview | production`), and ship a top-level developer guide that makes local-vs-production setup unambiguous.

**Architecture:** Four-pass remediation, ordered by severity. **Pass A** rotates every leaked credential at its provider — this is non-negotiable because the keys are in this repo's git history and rewriting history is out of scope. **Pass B** sanitizes the tracked example files and removes the duplicate Django-era `.env`. **Pass C** deletes the legacy Django code that no longer runs. **Pass D** strengthens the typed config, fixes wrong default URLs, adds frontend env templates, and writes the developer documentation.

**Tech Stack:** FastAPI + pydantic-settings (backend), Next.js 15 (frontend), Vercel deployment (env vars in dashboard), Supabase (Postgres + Auth), Resend (transactional email).

---

## Threat model — what's currently leaked

These keys are visible in committed files at `HEAD`:

| Where | Secret | Blast radius |
|-------|--------|--------------|
| `backend/.env.example:12` | `DB_PASSWORD=Stefanb***********!` | Full Postgres write access |
| `backend/auth_service/.env.example:5` | `SUPABASE_DB_URL=...[Stefanb***********!]@db...` | Same DB password (URL-embedded) |
| `backend/auth_service/.env.example:2` | `SUPABASE_ANON_KEY=eyJ...wsm-_...` | Public-facing anon key (lower risk, but still rotate) |
| `backend/auth_service/.env.example:4` | `SUPABASE_SERVICE_ROLE_KEY=eyJ...ghteW...` | **Bypasses RLS.** Highest impact. |
| `backend/auth_service/.env.example:11` | `RESEND_API_KEY=re_cENrXnX5_*REDACTED*` | Send email from `roman-technologies.dev` as anyone |

These keys exist in **earlier git commits** as well. Sanitizing the current files does **not** remove them from history. Rotation at the provider is the only remediation. We are intentionally not rewriting git history (force-push to `master` would invalidate everyone's clones and isn't worth it for a project at this stage).

---

## File structure

After this plan runs, the repo's env-config surface will look like this:

```
.gitignore                          (already correct: `.env`, `.env.*`, `!.env.example`)
README.md                           (NEW — top-level local-vs-prod guide)
docs/
  ENVIRONMENTS.md                   (NEW — detailed env-var contract per tier)
  SECURITY.md                       (NEW — rotation log; what was rotated when)
backend/
  .env                              (LOCAL ONLY — moved from auth_service/.env)
  .env.example                      (REWRITTEN — placeholders only, no secrets)
  vercel.json                       (UNCHANGED)
  vercel_entry.py                   (UNCHANGED)
  requirements.txt                  (UNCHANGED)
  auth_service/                     (FastAPI app — unchanged structure)
    core/config.py                  (MODIFIED — fix Resend defaults, fail-loud in prod, ENVIRONMENT Literal)
    main.py                         (MODIFIED — env-tier branching uses Literal)
  ─ DELETED ─
  core/                             (legacy Django settings.py / asgi.py / wsgi.py / urls.py)
  manage.py
  db.sqlite3
  migrations/
  projects/
  .env                              (legacy Django .env — replaced by backend/.env)
  auth_service/.env                 (moved up to backend/.env)
  auth_service/.env.example         (replaced by backend/.env.example at the level the app actually reads)
frontend/
  .env.example                      (NEW — placeholders for FASTAPI_URL etc.)
  .env.local                        (LOCAL ONLY — already ignored)
agents/CMS Connector - Website/
  scan.py                           (MODIFIED — fix DEFAULT_ENDPOINT)
  phases/4-integration.md           (MODIFIED — fix CMS endpoint references)
  AGENTS.md                         (MODIFIED — fix glossary URL)
```

**Single source of truth for backend env**: `backend/.env` (auto-loaded by pydantic-settings). The current `backend/auth_service/.env` will be moved up one directory so the env file lives at the same level as the deployable unit (`backend/`), matching how Vercel treats the project root.

**Single source of truth for frontend env**: `frontend/.env.local` (already in use; gitignored). The new `frontend/.env.example` documents the contract.

**Production env vars**: live in the Vercel dashboard for each project (`cms-backend-roman`, `cms-frontend-roman`). The new `docs/ENVIRONMENTS.md` documents which keys each project requires.

---

## Pass A — Rotate every leaked credential (no code changes)

These tasks are operational, not coded. Each must be confirmed complete before moving on. **Do not** sanitize the files in Pass B until rotation is done — the leaked keys would still be active.

### Task A1: Rotate the Supabase service_role key

**Why first:** Highest blast radius. Bypasses Row-Level Security; whoever holds it can read/write any row in any table.

- [ ] **Step 1: Open Supabase dashboard**

  Navigate: https://supabase.com/dashboard/project/xeluydwpgiddbamysgyu/settings/api-keys

- [ ] **Step 2: Generate a new `service_role` legacy JWT secret**

  Click "Roll JWT secret" (under "JWT Settings"). Confirm the rotation. Both `anon` and `service_role` JWTs are re-signed; both old tokens stop working immediately.

- [ ] **Step 3: Capture the two new tokens**

  Copy the new `anon` and `service_role` values shown on the API page. Save them to your password manager.

- [ ] **Step 4: Update Vercel env on `cms-backend-roman`**

  Vercel dashboard → `cms-backend-roman` → Settings → Environment Variables.
  Update `SUPABASE_SERVICE_ROLE_KEY` and `SUPABASE_ANON_KEY` for **all three** environments (Production, Preview, Development).

- [ ] **Step 5: Trigger a fresh Vercel deploy**

  In `cms-backend-roman` → Deployments → click "Redeploy" on the latest production deploy with "use existing Build Cache" off.

- [ ] **Step 6: Verify backend boots with new keys**

  ```bash
  curl -s https://cms-backend-roman.vercel.app/health
  ```
  Expected: `{"status":"ok"}`. If 500, check Vercel runtime logs for "Invalid API key".

- [ ] **Step 7: Verify the OLD service_role token no longer works**

  Use the old leaked token to attempt a query:
  ```bash
  curl -s -H "Authorization: Bearer <OLD_SERVICE_ROLE_KEY>" \
    https://xeluydwpgiddbamysgyu.supabase.co/rest/v1/users?select=id
  ```
  Expected: 401 Unauthorized. If still 200, rotation failed — re-roll.

### Task A2: Rotate the Supabase database password

**Why:** Embedded inside `SUPABASE_DB_URL`, used by Django migrations historically. Direct Postgres access bypasses every API gate.

- [ ] **Step 1: Open Supabase database settings**

  Navigate: https://supabase.com/dashboard/project/xeluydwpgiddbamysgyu/settings/database

- [ ] **Step 2: Reset the database password**

  "Reset database password" → generate strong password (≥ 32 chars, mixed case + digits + symbols). Save to password manager.

- [ ] **Step 3: Confirm no service depends on the OLD password**

  ```bash
  grep -rn "Stefanb*****" "C:/Users/stefa/.gemini/antigravity/scratch/CMS - websites" 2>/dev/null
  ```
  Expected: matches in `.env.example` files only (those get sanitized in Pass B). No matches in source code.

- [ ] **Step 4: Update local `backend/.env` with the new password**

  Open `backend/auth_service/.env` (until Pass B moves it). Replace the embedded password in `SUPABASE_DB_URL`:
  ```
  SUPABASE_DB_URL=postgresql://postgres.[<NEW_PASSWORD>]@db.xeluydwpgiddbamysgyu.supabase.co:5432/postgres
  ```

- [ ] **Step 5: Update Vercel env**

  `cms-backend-roman` → Environment Variables → `SUPABASE_DB_URL` (all 3 envs). Redeploy. The FastAPI service does not currently use `SUPABASE_DB_URL` for runtime queries (it uses the Supabase HTTP API via `SUPABASE_*_KEY`), so the redeploy is precautionary.

### Task A3: Rotate the Resend API key

- [ ] **Step 1: Revoke the leaked key**

  https://resend.com/api-keys → click `re_cENrXnX5_*REDACTED*` → Delete.

- [ ] **Step 2: Create a new restricted-scope key**

  "Create API key" → name "cms-backend-prod" → Permission: "Sending access" (NOT "Full access"). Copy the new `re_*` value.

- [ ] **Step 3: Update Vercel env**

  `cms-backend-roman` → Environment Variables → `RESEND_API_KEY` (Production + Preview). Redeploy.

- [ ] **Step 4: Update local `backend/auth_service/.env`** with the new key.

- [ ] **Step 5: Smoke-test email path**

  After Vercel redeploys, submit a test contact form on https://it-global-services.vercel.app/contact (any of the 4 fields filled) and confirm the email arrives at `office@itglobalservices.ro`. If 502, check `RESEND_API_KEY` was set on **Production** target (not just Preview).

### Task A4: Log the rotation

- [ ] **Step 1: Create `docs/SECURITY.md`**

  ```markdown
  # Security Log

  All credential rotations are recorded here. Do not delete entries — they are
  the audit trail when a leak is suspected.

  | Date | What was rotated | Why | Operator |
  |------|------------------|-----|----------|
  | 2026-04-30 | Supabase `service_role` JWT secret (rolls both anon and service_role) | Old key was committed in `backend/auth_service/.env.example` and visible in git history | Stefan |
  | 2026-04-30 | Supabase database password | Old password (`Stefanb***********!`) was embedded in `SUPABASE_DB_URL` in committed `.env.example` files | Stefan |
  | 2026-04-30 | Resend API key `re_cENrXnX5_*` | Old key was committed in `backend/auth_service/.env.example` and visible in git history | Stefan |

  ## Reporting a suspected leak

  Email stefanromanpers@gmail.com. Don't open a public issue. Don't push the
  details to a branch. Rotate immediately if in doubt — rotations are cheap.
  ```

- [ ] **Step 2: Commit**

  ```bash
  git add docs/SECURITY.md
  git commit -m "docs: log 2026-04-30 credential rotation (env-hygiene plan Pass A)"
  ```

---

## Pass B — Sanitize tracked `.env*` files and consolidate

The leaked keys are now dead, but the placeholders left in the tracked example files still suggest "fill in this real value here" wrong patterns. Replace them with **clearly fake** placeholders so a future contributor can't mistake them for live credentials.

### Task B1: Move `backend/auth_service/.env` → `backend/.env`

**Why:** The FastAPI app's `Settings` class auto-loads from a path computed relative to `core/config.py` — currently `backend/auth_service/.env`. We move it up one level to `backend/.env` so the env file lives at the deploy unit boundary, matching every other Vercel-deployed project in the org. This is also what `docs/ENVIRONMENTS.md` will document.

**Files:**
- Move: `backend/auth_service/.env` → `backend/.env`
- Modify: `backend/auth_service/core/config.py:31` (env_file path)

- [ ] **Step 1: Move the file (preserving content)**

  ```bash
  mv "backend/auth_service/.env" "backend/.env"
  ```

- [ ] **Step 2: Update the `env_file` path in `Settings`**

  Open `backend/auth_service/core/config.py`. Replace:
  ```python
      model_config = {
          "env_file": str(Path(__file__).resolve().parent.parent / ".env"),
          "env_file_encoding": "utf-8",
          "extra": "ignore",
      }
  ```
  With:
  ```python
      model_config = {
          # Single source of truth: backend/.env (sibling of vercel_entry.py).
          # Pass B of the env-hygiene plan moved it up from auth_service/.
          "env_file": str(Path(__file__).resolve().parents[2] / ".env"),
          "env_file_encoding": "utf-8",
          "extra": "ignore",
      }
  ```

- [ ] **Step 3: Verify the FastAPI app still boots locally**

  ```bash
  cd backend && source venv/Scripts/activate && \
    uvicorn auth_service.main:app --port 8001 --reload
  ```
  Expected: starts without `ValidationError: SUPABASE_URL field required`. If it errors, the path is wrong — `parents[2]` should resolve to `backend/`.

- [ ] **Step 4: Hit `/health`**

  ```bash
  curl -s http://localhost:8001/health
  ```
  Expected: `{"status":"ok"}`.

- [ ] **Step 5: Commit**

  ```bash
  git add backend/auth_service/core/config.py
  git commit -m "refactor(config): move backend env_file from auth_service/.env to backend/.env"
  ```

### Task B2: Delete the legacy Django `backend/.env` template's contents and rewrite

**Files:**
- Modify: `backend/.env.example` (rewrite from scratch — placeholders only)
- Delete: `backend/auth_service/.env.example` (its content is folded into `backend/.env.example`)

The new file lives at the same level as `backend/.env` (which is what the app actually reads). The old `backend/auth_service/.env.example` becomes redundant.

- [ ] **Step 1: Replace `backend/.env.example` with a clean template**

  Overwrite `backend/.env.example` entirely with:

  ```bash
  # backend/.env.example — copy to backend/.env and fill in REAL values.
  # NEVER commit backend/.env. Real secrets live in:
  #   • Local development: backend/.env (this file's sibling, gitignored)
  #   • Production:        Vercel dashboard → cms-backend-roman → Environment Variables
  # See docs/ENVIRONMENTS.md for the full contract.

  # ── Environment tier ─────────────────────────────────────────────
  # development | preview | production
  ENVIRONMENT=development

  # ── Supabase ─────────────────────────────────────────────────────
  SUPABASE_URL=https://YOUR_PROJECT_REF.supabase.co
  SUPABASE_ANON_KEY=REPLACE_WITH_ANON_KEY_FROM_SUPABASE_DASHBOARD
  SUPABASE_SERVICE_ROLE_KEY=REPLACE_WITH_SERVICE_ROLE_KEY_FROM_SUPABASE_DASHBOARD

  # Direct PostgreSQL connection — only needed for ad-hoc psql access; the
  # FastAPI app uses the HTTP API, not this URL.
  SUPABASE_DB_URL=postgresql://postgres.[REPLACE_WITH_DB_PASSWORD]@db.YOUR_PROJECT_REF.supabase.co:5432/postgres

  # ── CORS / origins ───────────────────────────────────────────────
  # Comma-separated. Used in production to gate which frontends may call
  # authenticated endpoints. *.vercel.app is allowed automatically (regex).
  FRONTEND_ORIGINS=http://localhost:3000,http://127.0.0.1:3000

  # ── Resend (transactional email) ─────────────────────────────────
  RESEND_API_KEY=REPLACE_WITH_RESEND_API_KEY
  RESEND_FROM_EMAIL=noreply@roman-technologies.dev
  RESEND_FROM_NAME=Roman Technologies CMS
  ```

- [ ] **Step 2: Delete the now-redundant `backend/auth_service/.env.example`**

  ```bash
  git rm "backend/auth_service/.env.example"
  ```

- [ ] **Step 3: Confirm no source file still imports the old path**

  ```bash
  grep -rn "auth_service/\.env\.example\|auth_service/.env" \
    backend/ frontend/ agents/ docs/ 2>/dev/null \
    | grep -v "node_modules\|__pycache__\|\.git/"
  ```
  Expected: no matches (the path is documentation-only at this point).

- [ ] **Step 4: Confirm the placeholders are clearly fake**

  ```bash
  grep -E "Stefanbaschet|eyJhbG|re_[a-zA-Z0-9_]{15,}" backend/.env.example
  ```
  Expected: no matches.

- [ ] **Step 5: Commit**

  ```bash
  git add backend/.env.example backend/auth_service/.env.example
  git commit -m "security: sanitize backend/.env.example; drop duplicate auth_service/.env.example"
  ```

### Task B3: Delete the legacy Django `backend/.env` if it still exists locally

**Files:**
- Delete (local only — file is gitignored): `backend/.env` ONLY IF it contains the OLD Django-shaped vars (`DJANGO_SECRET_KEY`, `DJANGO_DEBUG`).

If `backend/.env` already contains the new FastAPI vars (because Task B1 moved it), skip this task.

- [ ] **Step 1: Inspect what's in `backend/.env` right now**

  ```bash
  head -3 backend/.env
  ```
  - If first line is `DJANGO_SECRET=...` → it's the legacy file, proceed.
  - If first line is `SUPABASE_URL=...` → it's the moved file from B1, skip the rest of this task.

- [ ] **Step 2: If legacy: delete it**

  ```bash
  rm backend/.env
  ```
  Then re-do Task B1 to put the FastAPI `.env` in place.

- [ ] **Step 3: Verify the app still boots**

  ```bash
  cd backend && source venv/Scripts/activate && \
    uvicorn auth_service.main:app --port 8001 &
  sleep 2 && curl -s http://localhost:8001/health
  ```
  Expected: `{"status":"ok"}`.

---

## Pass C — Delete legacy Django code

The repo migrated from Django to FastAPI. Django-era files no longer run but inflate cognitive load and reviewer surface. Each is independently safe to delete because the FastAPI app has zero imports from any of them.

### Task C1: Verify no live import paths touch the Django dirs

**Files:** (read-only verification)

- [ ] **Step 1: Grep for any active import**

  ```bash
  grep -rn "from core\|from backend\.core\|backend\.core\|manage\.py\|backend\.projects" \
    backend/auth_service/ backend/vercel_entry.py 2>/dev/null
  ```
  Expected: no matches. If any match, halt this Pass and surface the file — there is a live dependency to migrate first.

- [ ] **Step 2: Confirm Vercel build doesn't reference Django**

  ```bash
  cat backend/vercel.json
  cat backend/vercel_entry.py
  ```
  Expected: only references `auth_service.main:app`. No `manage.py`, no `core.wsgi`.

### Task C2: Delete the Django code

**Files (all deleted):**
- `backend/core/` (entire dir: `settings.py`, `asgi.py`, `wsgi.py`, `urls.py`, `authentication.py`, `__init__.py`)
- `backend/manage.py`
- `backend/db.sqlite3`
- `backend/migrations/` (entire dir)
- `backend/projects/` (entire dir — old Django app)

- [ ] **Step 1: Delete the files via git**

  ```bash
  git rm -r backend/core backend/manage.py backend/migrations backend/projects
  rm -f backend/db.sqlite3   # gitignored — local rm only
  ```

- [ ] **Step 2: Verify the FastAPI service still boots**

  ```bash
  cd backend && source venv/Scripts/activate && \
    uvicorn auth_service.main:app --port 8001 &
  sleep 2 && curl -s http://localhost:8001/health
  kill %1
  ```
  Expected: `{"status":"ok"}`.

- [ ] **Step 3: Run the backend test suite**

  ```bash
  cd backend && python -m pytest auth_service/tests/ -q
  ```
  Expected: all green. (If a test imports from `core.*`, it was a Django-era test — delete it.)

- [ ] **Step 4: Commit**

  ```bash
  git add -A
  git commit -m "chore: remove legacy Django code (post-FastAPI migration cleanup)"
  ```

### Task C3: Drop the Django line from `requirements.txt`

**Files:**
- Modify: `backend/requirements.txt` (remove `Django==*` and `djangorestframework==*` and `django-cors-headers==*` if present)

- [ ] **Step 1: Inspect**

  ```bash
  grep -in "django" backend/requirements.txt
  ```

- [ ] **Step 2: Remove any `Django*` lines**

  Edit `backend/requirements.txt`, delete every line whose package name starts with `Django`, `django-`, or `djangorestframework`.

- [ ] **Step 3: Reinstall to confirm the lock still resolves**

  ```bash
  cd backend && source venv/Scripts/activate && \
    pip install --upgrade -r requirements.txt
  ```
  Expected: no errors.

- [ ] **Step 4: Run the FastAPI suite again**

  ```bash
  python -m pytest auth_service/tests/ -q
  ```

- [ ] **Step 5: Commit**

  ```bash
  git add backend/requirements.txt
  git commit -m "chore(deps): remove Django from requirements.txt"
  ```

---

## Pass D — Fix wrong defaults, add templates, harden config

Even with secrets rotated and legacy gone, several defaults still steer new contributors toward wrong values.

### Task D1: Fix `RESEND_FROM_EMAIL` default in `config.py`

**Why:** Default points at `noreply@romantechnologies.com` (parked on hugedomains.com — Resend cannot send from it). Production uses `noreply@roman-technologies.dev`.

**Files:**
- Modify: `backend/auth_service/core/config.py` (line referencing `RESEND_FROM_EMAIL`)
- Modify: `backend/auth_service/tests/test_*.py` (any test asserting the old default — likely none, but verify)

- [ ] **Step 1: Write a failing test**

  Create `backend/auth_service/tests/test_config_defaults.py`:
  ```python
  from auth_service.core.config import Settings


  def test_resend_from_email_default_uses_verified_domain(monkeypatch):
      """The default RESEND_FROM_EMAIL must be a domain that's actually
      verified in Resend. The legacy default (noreply@romantechnologies.com)
      pointed at a parked domain and would 403 every email."""
      # Ensure no env var influences the default
      for k in [
          "RESEND_FROM_EMAIL",
          "SUPABASE_URL",
          "SUPABASE_ANON_KEY",
      ]:
          monkeypatch.delenv(k, raising=False)
      # Provide the required fields with dummy values
      monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
      monkeypatch.setenv("SUPABASE_ANON_KEY", "dummy")
      s = Settings(_env_file=None)  # ignore on-disk .env
      assert s.RESEND_FROM_EMAIL == "noreply@roman-technologies.dev"
  ```

- [ ] **Step 2: Run it; expect FAIL**

  ```bash
  cd backend && python -m pytest auth_service/tests/test_config_defaults.py -v
  ```
  Expected: FAIL — current default is `noreply@romantechnologies.com`.

- [ ] **Step 3: Update the default**

  In `backend/auth_service/core/config.py`, change:
  ```python
      RESEND_FROM_EMAIL: str = "noreply@romantechnologies.com"
  ```
  to:
  ```python
      RESEND_FROM_EMAIL: str = "noreply@roman-technologies.dev"
  ```

- [ ] **Step 4: Run again; expect PASS**

  ```bash
  python -m pytest auth_service/tests/test_config_defaults.py -v
  ```

- [ ] **Step 5: Commit**

  ```bash
  git add backend/auth_service/core/config.py backend/auth_service/tests/test_config_defaults.py
  git commit -m "fix(config): default RESEND_FROM_EMAIL to verified roman-technologies.dev"
  ```

### Task D2: Make `ENVIRONMENT` a typed Literal

**Why:** The current `ENVIRONMENT: str = "development"` accepts any string. `main.py` branches on `== "development"` only; everything else (`"prod"`, `"PRODUCTION"`, `""`, typo) silently goes through the production path. Vercel preview deployments are particularly ambiguous.

**Files:**
- Modify: `backend/auth_service/core/config.py`
- Modify: `backend/auth_service/main.py:50,98` (replace string compare with enum compare)

- [ ] **Step 1: Write a failing test**

  Append to `backend/auth_service/tests/test_config_defaults.py`:
  ```python
  import pytest
  from pydantic import ValidationError


  def test_environment_must_be_one_of_three_tiers(monkeypatch):
      monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
      monkeypatch.setenv("SUPABASE_ANON_KEY", "dummy")
      monkeypatch.setenv("ENVIRONMENT", "prod")  # not in the allowed set
      with pytest.raises(ValidationError):
          Settings(_env_file=None)


  def test_environment_accepts_preview_tier(monkeypatch):
      monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
      monkeypatch.setenv("SUPABASE_ANON_KEY", "dummy")
      monkeypatch.setenv("ENVIRONMENT", "preview")
      s = Settings(_env_file=None)
      assert s.ENVIRONMENT == "preview"
  ```

- [ ] **Step 2: Run; expect FAIL**

  ```bash
  python -m pytest auth_service/tests/test_config_defaults.py -v
  ```

- [ ] **Step 3: Type ENVIRONMENT as a Literal**

  In `backend/auth_service/core/config.py`, change the imports + field:
  ```python
  from pydantic_settings import BaseSettings
  from pathlib import Path
  from typing import Literal

  Environment = Literal["development", "preview", "production"]

  class Settings(BaseSettings):
      # ... existing fields ...

      ENVIRONMENT: Environment = "development"
  ```

- [ ] **Step 4: Update the runtime branches in `main.py`**

  In `backend/auth_service/main.py`, replace every `settings.ENVIRONMENT == "development"` check with the same compare (still valid against the Literal). Add a comment block above the CORS section documenting the three tiers:

  ```python
  # CORS / PNA branch on ENVIRONMENT:
  #   development → permissive regex (localhost, LAN, *.vercel.app); PNA enabled
  #   preview     → same regex (Vercel preview deployments behave like dev)
  #   production  → strict allowlist + *.vercel.app for client websites
  IS_PROD = settings.ENVIRONMENT == "production"
  ```

  Then use `IS_PROD` in the CORS kwargs ternary:
  ```python
  _cors_kwargs: dict = (
      {"allow_origin_regex": _prod_origin_regex()}
      if IS_PROD
      else {
          "allow_origin_regex": (
              r"http://(localhost|127\.0\.0\.1|192\.168\.\d{1,3}\.\d{1,3})(:\d+)?"
              r"|https://[a-zA-Z0-9.-]+\.vercel\.app"
          )
      }
  )
  ```

  And the PNA gate:
  ```python
  if not IS_PROD:
      app.add_middleware(_PrivateNetworkAccessMiddleware)
  ```

- [ ] **Step 5: Run all backend tests**

  ```bash
  python -m pytest auth_service/tests/ -q
  ```
  Expected: all green.

- [ ] **Step 6: Set `ENVIRONMENT=preview` on Vercel preview env**

  Vercel dashboard → `cms-backend-roman` → Environment Variables → `ENVIRONMENT`. Set:
  - Production: `production`
  - Preview: `preview`
  - Development: `development`

- [ ] **Step 7: Commit**

  ```bash
  git add backend/auth_service/core/config.py backend/auth_service/main.py backend/auth_service/tests/test_config_defaults.py
  git commit -m "feat(config): ENVIRONMENT is now Literal[development|preview|production]"
  ```

### Task D3: Make missing `FRONTEND_ORIGINS` fail loud in production

**Why:** The current default falls back to localhost-only. If someone deploys to production without setting `FRONTEND_ORIGINS`, CORS preflights from the real frontend silently 403 — and the dev sees an obscure CORS console error rather than a startup failure.

**Files:**
- Modify: `backend/auth_service/core/config.py`
- Modify: `backend/auth_service/tests/test_config_defaults.py`

- [ ] **Step 1: Write a failing test**

  Append to `backend/auth_service/tests/test_config_defaults.py`:
  ```python
  def test_frontend_origins_required_in_production(monkeypatch):
      monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
      monkeypatch.setenv("SUPABASE_ANON_KEY", "dummy")
      monkeypatch.setenv("ENVIRONMENT", "production")
      monkeypatch.delenv("FRONTEND_ORIGINS", raising=False)
      with pytest.raises(ValidationError, match="FRONTEND_ORIGINS"):
          Settings(_env_file=None)


  def test_frontend_origins_optional_in_development(monkeypatch):
      monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
      monkeypatch.setenv("SUPABASE_ANON_KEY", "dummy")
      monkeypatch.setenv("ENVIRONMENT", "development")
      monkeypatch.delenv("FRONTEND_ORIGINS", raising=False)
      s = Settings(_env_file=None)
      assert "localhost" in s.FRONTEND_ORIGINS
  ```

- [ ] **Step 2: Run; expect FAIL**

- [ ] **Step 3: Add a model_validator to `Settings`**

  In `backend/auth_service/core/config.py`:
  ```python
  from pydantic import model_validator

  class Settings(BaseSettings):
      # ... existing fields ...

      @model_validator(mode="after")
      def _require_origins_in_prod(self):
          if self.ENVIRONMENT == "production" and not self.cors_origins:
              raise ValueError(
                  "FRONTEND_ORIGINS must be set when ENVIRONMENT=production. "
                  "Define it in the Vercel dashboard for cms-backend-roman."
              )
          return self
  ```

- [ ] **Step 4: Run; expect PASS**

- [ ] **Step 5: Verify production env on Vercel has `FRONTEND_ORIGINS`**

  Vercel dashboard → `cms-backend-roman` → Settings → Environment Variables. Confirm `FRONTEND_ORIGINS` exists for Production target with value:
  ```
  https://roman-technologies.dev,https://www.roman-technologies.dev,https://cms-frontend-roman.vercel.app
  ```
  (Adjust to actual canonical hosts.)

- [ ] **Step 6: Commit**

  ```bash
  git add backend/auth_service/core/config.py backend/auth_service/tests/test_config_defaults.py
  git commit -m "fix(config): require FRONTEND_ORIGINS in production (fail-loud)"
  ```

### Task D4: Fix the agent's `DEFAULT_ENDPOINT` (parked domain)

**Why:** `agents/CMS Connector - Website/scan.py:62` defaults to `https://cms.romantechnologies.com/content`. `romantechnologies.com` is parked on hugedomains.com — won't resolve. Real backend is `https://cms-backend-roman.vercel.app`.

**Files:**
- Modify: `agents/CMS Connector - Website/scan.py:62` (`DEFAULT_ENDPOINT`)
- Modify: `agents/CMS Connector - Website/AGENTS.md` (Glossary section if URL is referenced)
- Modify: `agents/CMS Connector - Website/phases/4-integration.md` (any URL reference)
- Modify: `cms-client-template/README.md` (line 207 sets `--api-url https://cms.romantechnologies.com`)

- [ ] **Step 1: Update `scan.py` default**

  Change:
  ```python
  DEFAULT_ENDPOINT = "https://cms.romantechnologies.com/content"
  ```
  to:
  ```python
  DEFAULT_ENDPOINT = "https://cms-backend-roman.vercel.app/content"
  ```

  Also update `DEFAULT_CMS_API`:
  ```python
  DEFAULT_CMS_API = "https://cms-backend-roman.vercel.app"
  ```

- [ ] **Step 2: Update agent docs**

  In `agents/CMS Connector - Website/phases/6-confirmation.md`, the cms_dashboard_url uses `cms-frontend-roman.vercel.app` — confirm correct.
  In `cms-client-template/README.md`, change `--api-url https://cms.romantechnologies.com` to `--api-url https://cms-backend-roman.vercel.app`.

- [ ] **Step 3: Run agent tests**

  ```bash
  /c/Users/stefa/.gemini/antigravity/scratch/CMS\ -\ websites/backend/venv/Scripts/python.exe \
    -m pytest "agents/CMS Connector - Website/tests/" -q
  ```
  Expected: 14 passed (no test asserts the URL string; this is a default change).

- [ ] **Step 4: Commit**

  ```bash
  git add "agents/CMS Connector - Website/scan.py" "cms-client-template/README.md"
  git commit -m "fix(agent): point DEFAULT_ENDPOINT at the real backend (parked domain → cms-backend-roman.vercel.app)"
  ```

### Task D5: Add `frontend/.env.example`

**Files:**
- Create: `frontend/.env.example`

- [ ] **Step 1: Write the template**

  Create `frontend/.env.example`:
  ```bash
  # frontend/.env.example — copy to frontend/.env.local and fill in.
  # NEVER commit .env.local. See docs/ENVIRONMENTS.md for the contract.

  # Server-side only — used by the Next.js proxy route + middleware to reach
  # the FastAPI backend. Public traffic never sees this URL directly.
  FASTAPI_URL=http://localhost:8001

  # Optional — only set if you need to override the canonical host the
  # middleware redirects to. Defaults to roman-technologies.dev in prod.
  # CANONICAL_HOST=roman-technologies.dev
  ```

- [ ] **Step 2: Commit**

  ```bash
  git add frontend/.env.example
  git commit -m "docs(frontend): add .env.example documenting FASTAPI_URL contract"
  ```

---

## Pass E — Documentation

The remaining tasks ship the developer-facing guide so the next contributor gets local-vs-prod right on day one.

### Task E1: Write `docs/ENVIRONMENTS.md`

**Files:**
- Create: `docs/ENVIRONMENTS.md`

- [ ] **Step 1: Author the contract doc**

  Create `docs/ENVIRONMENTS.md`:

  ```markdown
  # Environments

  Three tiers: **development**, **preview**, **production**. Each maps to a
  specific deploy surface and a specific source of env vars.

  ## Tier matrix

  | Tier | Where it runs | Source of env vars | Trigger |
  |------|---------------|-------------------|---------|
  | development | your laptop | `backend/.env` + `frontend/.env.local` (gitignored) | `uvicorn`/`npm run dev` |
  | preview | Vercel preview deployment | Vercel dashboard → "Preview" env | push to any non-main branch |
  | production | Vercel production deployment | Vercel dashboard → "Production" env | merge to `master` |

  ## Backend env contract (`cms-backend-roman` on Vercel)

  | Var | Required in | Notes |
  |-----|-------------|-------|
  | `ENVIRONMENT` | all | One of `development` / `preview` / `production`. Drives CORS + PNA logic. |
  | `SUPABASE_URL` | all | https://<ref>.supabase.co |
  | `SUPABASE_ANON_KEY` | all | Public-readable. Fine in client bundles. |
  | `SUPABASE_SERVICE_ROLE_KEY` | all | **Server-only.** Bypasses RLS. |
  | `SUPABASE_DB_URL` | optional | Only used for ad-hoc psql, not by the app. |
  | `FRONTEND_ORIGINS` | **production only** | Comma-separated list. Backend refuses to start in prod without this. |
  | `RESEND_API_KEY` | preview + production | Sends transactional email. |
  | `RESEND_FROM_EMAIL` | optional | Defaults to `noreply@roman-technologies.dev`. |
  | `RESEND_FROM_NAME` | optional | Defaults to `Roman Technologies CMS`. |

  ## Frontend env contract (`cms-frontend-roman` on Vercel)

  | Var | Required in | Notes |
  |-----|-------------|-------|
  | `FASTAPI_URL` | all | Server-only. Used by `app/api/[...path]/route.ts` to proxy. Set to the backend's URL for that tier. |

  ## What lives where

  - **Local secrets**: `backend/.env` (auto-loaded by pydantic-settings) and
    `frontend/.env.local` (auto-loaded by Next.js).
  - **Production secrets**: Vercel dashboard → project → Settings → Environment Variables.
  - **Examples**: `backend/.env.example` and `frontend/.env.example`. Both are
    committed; both contain only placeholder values.

  ## Adding a new env var

  1. Add it to the relevant `.env.example`.
  2. Add it to the typed `Settings` class (backend) or document it in
     `frontend/.env.example` (frontend).
  3. Set it in the Vercel dashboard for every tier that needs it.
  4. If it's required, add a `model_validator` so the app fails to start
     when missing. Silent fallbacks cause the hardest production bugs.

  ## Rotating a secret

  See `docs/SECURITY.md` for the rotation log and procedure.
  ```

- [ ] **Step 2: Commit**

  ```bash
  git add docs/ENVIRONMENTS.md
  git commit -m "docs: add ENVIRONMENTS.md — three-tier env-var contract"
  ```

### Task E2: Write top-level `README.md`

**Why:** No project README exists. New contributors land on the repo and have to dig through `docs/superpowers/plans/` to figure out what runs where.

**Files:**
- Create: `README.md` (top-level, replacing the empty/minimal one if present)

- [ ] **Step 1: Inspect existing README**

  ```bash
  ls README.md && head -20 README.md
  ```

- [ ] **Step 2: Author the project README**

  Create or overwrite `README.md`:

  ```markdown
  # Roman Technologies CMS

  Headless CMS platform for managing client websites. Two services, one repo.

  ## Architecture

  ```
  ┌─────────────────────┐         ┌──────────────────────┐
  │  cms-frontend-roman │  proxy  │  cms-backend-roman   │
  │  (Next.js 15)       │ ──────▶ │  (FastAPI)           │
  │  roman-technologies │         │  Vercel Python       │
  │  .dev               │         │  serverless          │
  └─────────────────────┘         └──────────┬───────────┘
                                              │
                                       ┌──────┴───────┐
                                       │   Supabase   │
                                       │   (Postgres) │
                                       └──────────────┘
  ```

  - **`backend/`** — FastAPI service. Deployed by `backend/vercel.json` to
    `cms-backend-roman.vercel.app`. Handles auth, content read/write, forms
    (Resend), and admin endpoints.
  - **`frontend/`** — Next.js dashboard at `roman-technologies.dev`. Talks to
    the backend via a server-side proxy at `/api/[...path]` so the browser
    never sees the FastAPI URL directly.
  - **`agents/CMS Connector - Website/`** — Python CLI that scans a client
    website, generates the CMS provisioning manifest, creates services,
    deploys to Vercel, and onboards the client. See `agents/README.md`.
  - **`cms-client-template/`** — drop-in npm package that lets a client
    website call `/content/<slug>` and render CMS-driven content.

  ## Local development

  ### Backend

  ```bash
  cd backend
  python -m venv venv
  source venv/Scripts/activate     # Git Bash on Windows
  pip install -r requirements.txt
  cp .env.example .env             # then fill in SUPABASE_*, RESEND_*
  uvicorn auth_service.main:app --reload --port 8001
  ```

  Hits `http://localhost:8001/health` → `{"status":"ok"}`.

  ### Frontend

  ```bash
  cd frontend
  npm install
  cp .env.example .env.local       # FASTAPI_URL=http://localhost:8001 by default
  npm run dev
  ```

  Hits `http://localhost:3000`.

  ### Tests

  ```bash
  # Backend
  cd backend && python -m pytest auth_service/tests/ -q

  # Frontend
  cd frontend && npm test

  # Agent
  cd "agents/CMS Connector - Website" && python -m pytest tests/ -q
  ```

  ## Production

  Both services deploy to Vercel on push to `master`. Env vars live in each
  Vercel project's dashboard. See [docs/ENVIRONMENTS.md](docs/ENVIRONMENTS.md)
  for the full contract.

  ## Security

  Credential rotations are logged in [docs/SECURITY.md](docs/SECURITY.md).
  Suspected leak? Email stefanromanpers@gmail.com — don't open a public issue.
  ```

- [ ] **Step 3: Commit**

  ```bash
  git add README.md
  git commit -m "docs: top-level README with architecture, local dev, and env-var pointers"
  ```

### Task E3: Final verification — boot every surface

- [ ] **Step 1: Backend boots locally**

  ```bash
  cd backend && source venv/Scripts/activate && \
    uvicorn auth_service.main:app --port 8001 &
  sleep 2 && curl -s http://localhost:8001/health
  kill %1
  ```
  Expected: `{"status":"ok"}`.

- [ ] **Step 2: Backend tests pass**

  ```bash
  python -m pytest auth_service/tests/ -q
  ```
  Expected: all green, including the three new config tests from D1/D2/D3.

- [ ] **Step 3: Frontend builds**

  ```bash
  cd frontend && npm run build
  ```
  Expected: build succeeds; type-check is clean.

- [ ] **Step 4: Agent tests pass**

  ```bash
  cd "agents/CMS Connector - Website" && \
    /c/Users/stefa/.gemini/antigravity/scratch/CMS\ -\ websites/backend/venv/Scripts/python.exe \
    -m pytest tests/ -q
  ```
  Expected: 14 passed.

- [ ] **Step 5: Push to master, watch Vercel deploys**

  ```bash
  git push origin master
  ```

- [ ] **Step 6: Smoke test production**

  ```bash
  curl -s https://cms-backend-roman.vercel.app/health
  curl -s https://cms-backend-roman.vercel.app/content/it-global-services | head -c 200
  curl -sI https://roman-technologies.dev/log-in | head -3
  ```
  Expected: 200 / JSON / 200 respectively.

- [ ] **Step 7: Confirm rotation didn't break anything**

  Submit a test contact form on https://it-global-services.vercel.app/contact and confirm Resend delivers email. Sign in to https://roman-technologies.dev/log-in with admin credentials and confirm dashboard loads.

---

## Self-review

**Spec coverage:**
- ✓ #1 leaked DB password → Task A2
- ✓ #2 leaked SUPABASE keys + RESEND key → Tasks A1, A3
- ✓ #3 dual `.env` files → Tasks B1, B3
- ✓ #4 legacy Django code → Tasks C1, C2, C3
- ✓ #5 wrong `RESEND_FROM_EMAIL` default → Task D1
- ✓ #6 wrong agent `DEFAULT_ENDPOINT` → Task D4
- ✓ #7 missing `frontend/.env.example` → Task D5
- ✓ #8 no `.env.production` template → covered by `docs/ENVIRONMENTS.md` (Task E1) — Vercel dashboard is the production env source, not a file
- ✓ #9 binary ENVIRONMENT semantics → Task D2
- ✓ #10 silent localhost CORS fallback → Task D3
- ✓ #11 `db.sqlite3` cruft → Task C2
- ✓ #12 no top-level README → Task E2
- ✓ History rewrite avoidance → noted explicitly in the threat model + Pass A introduction

**Placeholder scan:** No "TBD" / "implement later" / "similar to Task N" anywhere. All file paths are absolute or repo-rooted, all code blocks contain the actual content.

**Type consistency:** `Environment` Literal defined once in Task D2; reused identically in Tasks D2 and D3. `Settings` class fields referenced by name (`FRONTEND_ORIGINS`, `cors_origins`, `ENVIRONMENT`, `RESEND_FROM_EMAIL`) — same names everywhere.

---

## Execution handoff

Plan saved to `docs/superpowers/plans/2026-04-30-env-config-hygiene.md`.

**Pass A is operational, not coded** — credential rotation must be done by Stefan in the Supabase / Resend / Vercel dashboards. The agent cannot rotate provider-side secrets.

**Passes B–E are coded** and follow the standard TDD pattern.

Two execution options:

1. **Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks. Good for the long Pass D refactors.
2. **Inline Execution** — execute tasks in this session with checkpoints between Passes.

Which approach?
