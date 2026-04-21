# CMS Vercel Hosting Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deploy the CMS frontend (Next.js) + backend (FastAPI) to two Vercel projects so the CMS is reachable at public HTTPS URLs — unblocking hosted client previews and removing the localhost-only constraint.

**Architecture:** Two independent Vercel projects (`cms-frontend-roman`, `cms-backend-roman`). Backend runs as a single Vercel Python serverless function wrapping the existing FastAPI app. Cross-origin auth via `SameSite=None; Secure` cookies. JWT keys loaded from base64 env vars. No DB change.

**Tech Stack:** Next.js 15, FastAPI 0.115, @vercel/python runtime, Supabase (unchanged), Vercel REST API (for project/env/deploy via MCP).

**Spec:** `docs/superpowers/specs/2026-04-21-cms-vercel-hosting-design.md`

---

## File Structure

### Created

| Path | Purpose |
|---|---|
| `backend/vercel_entry.py` | Re-exports FastAPI `app` at the Vercel project root so `@vercel/python` can wrap it. |
| `backend/vercel.json` | Vercel build + route config: one Python function, catch-all route. |
| `backend/requirements.txt` | Python deps at project root (Vercel Python builder needs them here). |

### Modified

| Path | Change |
|---|---|
| `backend/auth_service/core/config.py` | `private_key` / `public_key` read `JWT_PRIVATE_KEY_B64` / `JWT_PUBLIC_KEY_B64` env vars first, fall back to file. |
| `backend/auth_service/routers/auth.py` | `_set_auth_cookies` switches to `samesite="none"` in production; `secure` already `IS_PROD`. |
| `backend/auth_service/tests/test_config.py` | NEW — unit tests for the env-var key loading. |

### Vercel project work (no local files)

- Create 2 Vercel projects via Vercel REST API (using existing `VERCEL_TOKEN` env var).
- Set env vars per project.
- Trigger first deploys.
- Smoke test.

---

## Task Order Rationale

1. **Code changes in the worktree first** (Tasks 1-3) — the feature branch captures all changes before merge.
2. **Merge to master** (Task 4) — per policy, Vercel deploys from `master`.
3. **Vercel project creation + env vars + deploys** (Tasks 5-7) — done via scripts, reproducible.
4. **Smoke test** (Task 8) — manual verification.

---

## Task 1: Config — JWT keys from env var

**Files:**
- Modify: `backend/auth_service/core/config.py`
- Create: `backend/auth_service/tests/test_config.py`

- [ ] **Step 1: Write the failing test**

Create `backend/auth_service/tests/test_config.py`:

```python
import base64
import os
from unittest.mock import patch

import pytest


SAMPLE_PRIVATE_PEM = "-----BEGIN PRIVATE KEY-----\nABCDEF\n-----END PRIVATE KEY-----\n"
SAMPLE_PUBLIC_PEM = "-----BEGIN PUBLIC KEY-----\nGHIJKL\n-----END PUBLIC KEY-----\n"


def _reimport_settings():
    """Reimport the settings module so env-var changes are picked up."""
    import importlib
    from auth_service.core import config as cfg_mod
    importlib.reload(cfg_mod)
    return cfg_mod.settings


def test_private_key_read_from_env_var_when_set():
    encoded = base64.b64encode(SAMPLE_PRIVATE_PEM.encode()).decode()
    with patch.dict(os.environ, {"JWT_PRIVATE_KEY_B64": encoded}):
        settings = _reimport_settings()
        assert settings.private_key == SAMPLE_PRIVATE_PEM


def test_public_key_read_from_env_var_when_set():
    encoded = base64.b64encode(SAMPLE_PUBLIC_PEM.encode()).decode()
    with patch.dict(os.environ, {"JWT_PUBLIC_KEY_B64": encoded}):
        settings = _reimport_settings()
        assert settings.public_key == SAMPLE_PUBLIC_PEM


def test_private_key_falls_back_to_file_when_env_unset():
    # Ensure env var is not set — local dev path
    env_without = {k: v for k, v in os.environ.items() if k != "JWT_PRIVATE_KEY_B64"}
    with patch.dict(os.environ, env_without, clear=True):
        settings = _reimport_settings()
        # The fallback reads from PRIVATE_KEY_PATH — must contain BEGIN marker.
        content = settings.private_key
        assert "-----BEGIN" in content
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && python -m pytest auth_service/tests/test_config.py -v`
Expected: the env-var tests FAIL (current config ignores env vars).

- [ ] **Step 3: Update config.py**

In `backend/auth_service/core/config.py`, add `import os` and `import base64` at the top, and replace the `private_key` / `public_key` properties with:

```python
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

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest auth_service/tests/test_config.py -v`
Expected: all 3 tests PASS.

- [ ] **Step 5: Ensure existing test suite still passes**

Run: `cd backend && python -m pytest auth_service/tests/ -v`
Expected: 20+ tests PASS, no regressions.

- [ ] **Step 6: Commit**

```bash
git add backend/auth_service/core/config.py backend/auth_service/tests/test_config.py
git commit -m "feat(config): load JWT keys from JWT_{PRIVATE,PUBLIC}_KEY_B64 env vars with file fallback"
```

---

## Task 2: Auth cookies — SameSite=None in production

**Files:**
- Modify: `backend/auth_service/routers/auth.py`

Context: cross-origin cookie (CMS frontend domain ≠ CMS backend domain) requires `SameSite=None; Secure`. Current code uses `"lax"`. We gate on `IS_PROD` (already defined in auth.py) — local dev stays `lax` so browser accepts it on `http://localhost`.

- [ ] **Step 1: Update cookie setter**

In `backend/auth_service/routers/auth.py:23-41`, replace the `_set_auth_cookies` function with:

```python
def _set_auth_cookies(response: Response, access_token: str, raw_refresh: str, refresh_expires: datetime):
    # Cross-origin (production): SameSite=None requires Secure. Browsers
    # reject SameSite=None on http://localhost, so dev stays on Lax.
    samesite = "none" if IS_PROD else "lax"
    response.set_cookie(
        key=ACCESS_COOKIE,
        value=access_token,
        httponly=True,
        secure=IS_PROD,
        samesite=samesite,
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        path="/",
    )
    response.set_cookie(
        key=REFRESH_COOKIE,
        value=raw_refresh,
        httponly=True,
        secure=IS_PROD,
        samesite=samesite,
        max_age=int((refresh_expires - datetime.now(timezone.utc)).total_seconds()),
        path="/",
    )
```

- [ ] **Step 2: Verify dev flow still works**

Run: `cd backend && source ../../backend/venv/Scripts/activate && python -m pytest auth_service/tests/ -v`
Expected: all existing tests PASS (they don't assert cookie flags, so behavior unchanged for tests).

- [ ] **Step 3: Smoke-test dev login**

Manual: stop uvicorn, restart, log in via `http://localhost:3000`. Verify login works (no code change to production paths for local dev).

- [ ] **Step 4: Commit**

```bash
git add backend/auth_service/routers/auth.py
git commit -m "feat(auth): SameSite=None;Secure cookies in production for cross-origin CMS frontend/backend"
```

---

## Task 3: Vercel backend entry point + config

**Files:**
- Create: `backend/vercel_entry.py`
- Create: `backend/vercel.json`
- Create: `backend/requirements.txt`

Context: Vercel Python builder expects (a) an ASGI-exposing Python file at the project root, (b) a `vercel.json` configuring builds + routes, (c) a `requirements.txt` at project root listing deps.

- [ ] **Step 1: Create `backend/vercel_entry.py`**

```python
"""Vercel Python entry point. Re-exports the FastAPI ASGI app so the
@vercel/python runtime can serve it as a serverless function.
"""
from auth_service.main import app  # noqa: F401 — re-export for Vercel
```

- [ ] **Step 2: Create `backend/vercel.json`**

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

- [ ] **Step 3: Create `backend/requirements.txt`**

`@vercel/python` reads `requirements.txt` from the project root. The existing `backend/auth_service/requirements.txt` has the full list; duplicate its content here (or use `-r`). Direct duplication is simpler for Vercel's resolver:

```
fastapi==0.115.6
uvicorn[standard]==0.32.1
python-jose[cryptography]==3.3.0
argon2-cffi==23.1.0
supabase==2.10.0
pydantic[email]==2.10.3
pydantic-settings==2.7.0
slowapi==0.1.9
python-dotenv==1.0.1
python-multipart==0.0.20
resend==2.7.0
httpx==0.27.2
```

Note: dev-only deps (`pytest`, `pytest-asyncio`) are omitted — Vercel doesn't need them.

- [ ] **Step 4: Verify local import still works**

Run: `cd backend && python -c "from auth_service.main import app; print(type(app).__name__)"`
Expected: `FastAPI`

- [ ] **Step 5: Commit**

```bash
git add backend/vercel_entry.py backend/vercel.json backend/requirements.txt
git commit -m "feat(deploy): add Vercel Python entry point + vercel.json + root requirements.txt"
```

---

## Task 4: Merge feat/cms-preview-publish to master

**Files:** none — this is a git operation on the main repo (not the worktree).

Per policy: master is the canonical deployment branch. Feature work must merge before Vercel deploy.

- [ ] **Step 1: Verify all tests pass on the feature branch**

Run: `cd backend && python -m pytest -v 2>&1 | tail -5`
Expected: all backend + agent tests PASS (25+ tests).

Run: `cd frontend && npm run test 2>&1 | tail -5`
Expected: 8 frontend tests PASS.

- [ ] **Step 2: Check for uncommitted changes in the worktree**

Run: `cd "c:/Users/stefa/.gemini/antigravity/scratch/CMS - websites/.worktrees/cms-preview-publish" && git status --short`
Expected: empty (clean tree).

- [ ] **Step 3: Switch to the main repo checkout and fetch feature branch**

From the main repo (`c:/Users/stefa/.gemini/antigravity/scratch/CMS - websites`):

```bash
git fetch origin feat/cms-preview-publish 2>/dev/null || true
# The feature branch lives in the worktree; merge directly from it:
git checkout master
git merge feat/cms-preview-publish --no-ff -m "Merge branch 'feat/cms-preview-publish': CMS Preview/Publish + Vercel hosting prep"
```

Expected: clean merge, no conflicts.

- [ ] **Step 4: Push master (requires GITHUB_TOKEN)**

Run: `git push origin master`
Expected: branch pushed successfully.

- [ ] **Step 5: Verify main repo is now on master, clean**

Run: `git status && git log --oneline -5`
Expected: `On branch master, nothing to commit`; log shows the merge commit.

---

## Task 5: Create Vercel backend project + env vars

**Context:** Vercel project creation happens via REST API. We already have `VERCEL_TOKEN` and `GITHUB_TOKEN` as env vars. The script creates the project, sets env vars, but does NOT trigger the first deploy (Vercel auto-deploys on `master` push).

- [ ] **Step 1: Confirm base64 of JWT keys can be generated**

Run (PowerShell-compatible):
```powershell
$priv = [Convert]::ToBase64String([IO.File]::ReadAllBytes("c:/Users/stefa/.gemini/antigravity/scratch/CMS - websites/backend/keys/private.pem"))
$pub  = [Convert]::ToBase64String([IO.File]::ReadAllBytes("c:/Users/stefa/.gemini/antigravity/scratch/CMS - websites/backend/keys/public.pem"))
# Verify length > 500 for private, > 100 for public
$priv.Length
$pub.Length
```

- [ ] **Step 2: Create `scripts/deploy/create_backend_vercel_project.py`**

```python
"""
One-shot script: create the cms-backend-roman Vercel project linked to
the CMS GitHub repo, set env vars, configure rootDirectory to backend/.

Requires env vars:
  VERCEL_TOKEN
  GITHUB_TOKEN    (for Vercel's git-app link verification)
  SUPABASE_URL, SUPABASE_ANON_KEY, SUPABASE_SERVICE_ROLE_KEY
  RESEND_API_KEY
  JWT_PRIVATE_KEY_B64, JWT_PUBLIC_KEY_B64  (generated in Step 1)

Idempotent: if the project already exists, updates env vars and exits.
"""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request

API = "https://api.vercel.com"
PROJECT_NAME = "cms-backend-roman"
GITHUB_REPO = "stefanroman22/CMS---websites"
ROOT_DIR = "backend"

def _req(method: str, path: str, body: dict | None = None) -> dict:
    token = os.environ["VERCEL_TOKEN"]
    url = f"{API}{path}"
    headers = {"Authorization": f"Bearer {token}"}
    data = None
    if body is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(body).encode()
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req) as r:
            raw = r.read().decode() or "{}"
            return json.loads(raw)
    except urllib.error.HTTPError as e:
        print(f"Vercel {method} {path} failed: {e.code}\n{e.read().decode()}", file=sys.stderr)
        raise

def find_project(name: str) -> dict | None:
    data = _req("GET", "/v9/projects?limit=100")
    for p in data.get("projects", []):
        if p.get("name") == name:
            return p
    return None

def create_project() -> str:
    payload = {
        "name": PROJECT_NAME,
        "framework": None,
        "gitRepository": {"type": "github", "repo": GITHUB_REPO},
        "rootDirectory": ROOT_DIR,
    }
    data = _req("POST", "/v11/projects", payload)
    return data["id"]

ENV_VARS = {
    "ENVIRONMENT":              ("production",                        ["production"]),
    "SUPABASE_URL":             (os.environ.get("SUPABASE_URL", ""),  ["production"]),
    "SUPABASE_ANON_KEY":        (os.environ.get("SUPABASE_ANON_KEY", ""), ["production"]),
    "SUPABASE_SERVICE_ROLE_KEY":(os.environ.get("SUPABASE_SERVICE_ROLE_KEY", ""), ["production"]),
    "JWT_PRIVATE_KEY_B64":      (os.environ.get("JWT_PRIVATE_KEY_B64", ""), ["production"]),
    "JWT_PUBLIC_KEY_B64":       (os.environ.get("JWT_PUBLIC_KEY_B64", ""), ["production"]),
    "JWT_ALGORITHM":            ("RS256",                             ["production"]),
    "RESEND_API_KEY":           (os.environ.get("RESEND_API_KEY", ""), ["production"]),
    "FRONTEND_ORIGINS":         ("https://cms-frontend-roman.vercel.app", ["production"]),
}

def upsert_env_var(project_id: str, key: str, value: str, target: list[str]) -> None:
    existing = _req("GET", f"/v9/projects/{project_id}/env")
    match = next(
        (e for e in existing.get("envs", [])
         if e.get("key") == key and set(e.get("target") or []) == set(target)),
        None,
    )
    body = {"key": key, "value": value, "type": "encrypted", "target": target}
    if match:
        _req("PATCH", f"/v9/projects/{project_id}/env/{match['id']}", body)
        print(f"  updated {key} {target}")
    else:
        _req("POST", f"/v9/projects/{project_id}/env", body)
        print(f"  created {key} {target}")

def main() -> None:
    for req_var in ("VERCEL_TOKEN", "SUPABASE_URL", "SUPABASE_ANON_KEY",
                    "SUPABASE_SERVICE_ROLE_KEY", "JWT_PRIVATE_KEY_B64",
                    "JWT_PUBLIC_KEY_B64", "RESEND_API_KEY"):
        if not os.environ.get(req_var):
            print(f"ERROR: env var {req_var} is required", file=sys.stderr)
            sys.exit(1)

    existing = find_project(PROJECT_NAME)
    if existing:
        project_id = existing["id"]
        print(f"Found existing project {PROJECT_NAME} ({project_id})")
    else:
        project_id = create_project()
        print(f"Created project {PROJECT_NAME} ({project_id})")

    for key, (value, target) in ENV_VARS.items():
        upsert_env_var(project_id, key, value, target)

    print(f"\nDone. Trigger deploy by pushing to master, or via Vercel UI.")
    print(f"Project URL: https://vercel.com/dashboard/projects/{project_id}")

if __name__ == "__main__":
    main()
```

- [ ] **Step 3: Run the script**

```powershell
# Set env vars for the script (values from backend/auth_service/.env)
$env:VERCEL_TOKEN = "<your Vercel token>"
$env:SUPABASE_URL = "<from .env>"
$env:SUPABASE_ANON_KEY = "<from .env>"
$env:SUPABASE_SERVICE_ROLE_KEY = "<from .env>"
$env:RESEND_API_KEY = "<from .env>"
$env:JWT_PRIVATE_KEY_B64 = [Convert]::ToBase64String([IO.File]::ReadAllBytes("c:/Users/stefa/.gemini/antigravity/scratch/CMS - websites/backend/keys/private.pem"))
$env:JWT_PUBLIC_KEY_B64 = [Convert]::ToBase64String([IO.File]::ReadAllBytes("c:/Users/stefa/.gemini/antigravity/scratch/CMS - websites/backend/keys/public.pem"))

cd "c:/Users/stefa/.gemini/antigravity/scratch/CMS - websites/.worktrees/cms-preview-publish"
python scripts/deploy/create_backend_vercel_project.py
```

Expected output: `Created project cms-backend-roman (prj_XXX)` followed by 9 `created VAR ['production']` lines.

- [ ] **Step 4: Trigger deploy via API (master branch)**

```powershell
PYTHONIOENCODING=utf-8 python -c "
import json, urllib.request, os
token = os.environ['VERCEL_TOKEN']
# Find project
req = urllib.request.Request('https://api.vercel.com/v9/projects?limit=100', headers={'Authorization': f'Bearer {token}'})
with urllib.request.urlopen(req) as r:
    projects = json.loads(r.read())['projects']
pid = next(p['id'] for p in projects if p['name'] == 'cms-backend-roman')
# Trigger master deploy
payload = {
    'name': 'CMS---websites',
    'project': pid,
    'gitSource': {'type': 'github', 'org': 'stefanroman22', 'repo': 'CMS---websites', 'ref': 'master'},
    'target': 'production',
}
req = urllib.request.Request('https://api.vercel.com/v13/deployments',
    data=json.dumps(payload).encode(),
    headers={'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'},
    method='POST')
with urllib.request.urlopen(req) as r:
    d = json.loads(r.read())
print('Deployment:', d['id'], 'url:', d.get('url'))
"
```

Expected: prints a deployment ID and URL. Wait ~60-120s for build.

- [ ] **Step 5: Verify `/health` returns 200**

```powershell
curl.exe -i https://cms-backend-roman.vercel.app/health
```

Expected: `HTTP/1.1 200 OK` with body `{"status":"ok"}`. If build is still in progress, retry after 30s.

- [ ] **Step 6: Commit the deploy script**

```bash
git add scripts/deploy/create_backend_vercel_project.py
git commit -m "chore(deploy): add Vercel backend project creation script"
```

---

## Task 6: Create Vercel frontend project + env vars

**Files:**
- Create: `scripts/deploy/create_frontend_vercel_project.py`

- [ ] **Step 1: Create the script**

`scripts/deploy/create_frontend_vercel_project.py`:

```python
"""
One-shot: create cms-frontend-roman Vercel project linked to same repo,
rootDirectory=frontend, set FASTAPI_URL env var to the backend URL.
"""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request

API = "https://api.vercel.com"
PROJECT_NAME = "cms-frontend-roman"
GITHUB_REPO = "stefanroman22/CMS---websites"
ROOT_DIR = "frontend"
BACKEND_URL = "https://cms-backend-roman.vercel.app"

def _req(method: str, path: str, body: dict | None = None) -> dict:
    token = os.environ["VERCEL_TOKEN"]
    url = f"{API}{path}"
    headers = {"Authorization": f"Bearer {token}"}
    data = None
    if body is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(body).encode()
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req) as r:
            raw = r.read().decode() or "{}"
            return json.loads(raw)
    except urllib.error.HTTPError as e:
        print(f"Vercel {method} {path} failed: {e.code}\n{e.read().decode()}", file=sys.stderr)
        raise

def find_project(name: str) -> dict | None:
    data = _req("GET", "/v9/projects?limit=100")
    for p in data.get("projects", []):
        if p.get("name") == name:
            return p
    return None

def create_project() -> str:
    payload = {
        "name": PROJECT_NAME,
        "framework": "nextjs",
        "gitRepository": {"type": "github", "repo": GITHUB_REPO},
        "rootDirectory": ROOT_DIR,
    }
    data = _req("POST", "/v11/projects", payload)
    return data["id"]

def upsert_env_var(project_id: str, key: str, value: str, target: list[str]) -> None:
    existing = _req("GET", f"/v9/projects/{project_id}/env")
    match = next(
        (e for e in existing.get("envs", [])
         if e.get("key") == key and set(e.get("target") or []) == set(target)),
        None,
    )
    body = {"key": key, "value": value, "type": "encrypted", "target": target}
    if match:
        _req("PATCH", f"/v9/projects/{project_id}/env/{match['id']}", body)
        print(f"  updated {key} {target}")
    else:
        _req("POST", f"/v9/projects/{project_id}/env", body)
        print(f"  created {key} {target}")

def main() -> None:
    if not os.environ.get("VERCEL_TOKEN"):
        print("ERROR: VERCEL_TOKEN is required", file=sys.stderr)
        sys.exit(1)
    existing = find_project(PROJECT_NAME)
    if existing:
        project_id = existing["id"]
        print(f"Found existing project {PROJECT_NAME} ({project_id})")
    else:
        project_id = create_project()
        print(f"Created project {PROJECT_NAME} ({project_id})")

    upsert_env_var(project_id, "FASTAPI_URL", BACKEND_URL, ["production", "preview"])

    print(f"\nDone. Project URL: https://vercel.com/dashboard/projects/{project_id}")

if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run the script**

```powershell
$env:VERCEL_TOKEN = "<your Vercel token>"
cd "c:/Users/stefa/.gemini/antigravity/scratch/CMS - websites/.worktrees/cms-preview-publish"
python scripts/deploy/create_frontend_vercel_project.py
```

Expected: `Created project cms-frontend-roman (prj_YYY)` and `created FASTAPI_URL ['production', 'preview']`.

- [ ] **Step 3: Trigger frontend deploy**

```powershell
PYTHONIOENCODING=utf-8 python -c "
import json, urllib.request, os
token = os.environ['VERCEL_TOKEN']
req = urllib.request.Request('https://api.vercel.com/v9/projects?limit=100', headers={'Authorization': f'Bearer {token}'})
with urllib.request.urlopen(req) as r:
    projects = json.loads(r.read())['projects']
pid = next(p['id'] for p in projects if p['name'] == 'cms-frontend-roman')
payload = {
    'name': 'CMS---websites',
    'project': pid,
    'gitSource': {'type': 'github', 'org': 'stefanroman22', 'repo': 'CMS---websites', 'ref': 'master'},
    'target': 'production',
}
req = urllib.request.Request('https://api.vercel.com/v13/deployments',
    data=json.dumps(payload).encode(),
    headers={'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'},
    method='POST')
with urllib.request.urlopen(req) as r:
    d = json.loads(r.read())
print('Deployment:', d['id'], 'url:', d.get('url'))
"
```

Expected: deployment ID + URL. Wait ~60-120s.

- [ ] **Step 4: Verify frontend responds**

```powershell
curl.exe -i https://cms-frontend-roman.vercel.app
```

Expected: HTTP 200 (or 307 redirect to `/log-in`).

- [ ] **Step 5: Commit the script**

```bash
git add scripts/deploy/create_frontend_vercel_project.py
git commit -m "chore(deploy): add Vercel frontend project creation script"
```

---

## Task 7: Smoke test the hosted CMS

**Files:** none (manual testing).

- [ ] **Step 1: Log in**

Navigate to `https://cms-frontend-roman.vercel.app`. Should redirect to `/log-in`. Log in with your admin credentials.

Expected: lands on Projects Overview. DevTools → Application → Cookies shows `access_token` with `SameSite=None; Secure=true`.

- [ ] **Step 2: Browse a project**

Click into `laurian-duma-portfolio`. Verify:
- PreviewPublishBar renders with See Preview (enabled — preview_url is set in DB).
- Service cards load.
- No console errors.

- [ ] **Step 3: Edit a service**

Click any service → change a field → Save. The "unpublished changes" badge should appear.

- [ ] **Step 4: Publish**

Click Publish Changes → confirm. Toast should show success. Verify in DB:
```sql
SELECT last_published_at FROM projects WHERE slug = 'laurian-duma-portfolio';
```
Expected: timestamp within the last minute.

- [ ] **Step 5: Hit the public content endpoint directly**

```powershell
curl.exe -i https://cms-backend-roman.vercel.app/content/laurian-duma-portfolio
```

Expected: HTTP 200 with JSON content matching what was just published.

- [ ] **Step 6: Smoke test ends**

Task 15 is complete when Steps 1–5 all succeed. Document any deviations in a follow-up issue.

---

## Out of Scope (tracked separately)

- Updating `backend/agent/scan.py` `DEFAULT_ENDPOINT` — separate 1-commit follow-up.
- Updating Laurian portfolio's `VITE_CMS_ENDPOINT` env var on its Vercel project to point at `https://cms-backend-roman.vercel.app/content/laurian-duma-portfolio` + `.../draft` for preview.
- Custom domain `cms.romantechnologies.com` wiring.
- Removing now-orphaned `CMS_ENDPOINT`/`CMS_PREVIEW_TOKEN` env vars on Laurian's project (superseded by `VITE_*`).
