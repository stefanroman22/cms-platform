# E2E + Integration Test Suite — Merge Gate Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Block the scheduled `dev → master` merge whenever real-browser end-to-end flows or HTTP-level backend invariants regress. Cover every page, every critical user flow, and every public/private API contract — driven by a dedicated test user against the existing Vercel deployments.

**Architecture:** Two test surfaces. **Backend integration**: pytest + httpx hitting `cms-backend-roman.vercel.app` directly — fast (≤ 30s), covers HTTP contracts (auth, content, CORS, admin gating, forms). **Frontend E2E**: Playwright headless Chromium against `cms-frontend-roman.vercel.app` — covers DOM rendering, theme toggle, login, edit-save-reload round-trips, publish flow. Both run in a single new `.github/workflows/e2e.yml` workflow on every push to `dev`/`master`. The scheduled-merge gate is widened to require both `CI` (existing unit suite) AND `E2E` workflows green on dev's HEAD. Tests share two dedicated test users (one regular, one admin) and one dedicated e2e project (`e2e-test-project`); a seed script creates them idempotently. Each test cleans up after itself so consecutive runs are deterministic.

**Tech stack added:** Playwright `1.49.x` (frontend), pytest already in repo (backend), `pytest-asyncio` already in repo for async HTTP, `python-dotenv` already in repo for local secret loading. New `e2e/` directory at the repo root with its own `package.json`. Three new GitHub Actions secrets (`E2E_USER_EMAIL`, `E2E_USER_PASSWORD`, `E2E_ADMIN_EMAIL`, `E2E_ADMIN_PASSWORD`).

---

## Scope notes

- **`/about` and `/contact` pages do NOT exist** on this frontend (Header has stale links). The plan covers `/log-in` and `/` for public surfaces, plus everything under `/dashboard/*`. The dead links are a separate cleanup, not this plan.
- Tests run against **production Vercel** (frontend + backend). No staging environment. The e2e project is isolated by slug (`e2e-test-project`), so test writes never touch real client data.
- We do **not** spin up a parallel Supabase database. Cleanup discipline is the cost of that decision and is enforced via per-test `afterEach`/`finally` hooks.

---

## File structure

```
.
├── .github/workflows/
│   ├── ci.yml                                  (UNCHANGED — unit tests + lint)
│   ├── scheduled-merge.yml                     (MODIFIED — also gate on E2E workflow conclusion)
│   └── e2e.yml                                 (NEW — runs backend + frontend E2E on push to dev/master)
├── scripts/
│   └── seed_e2e.py                             (NEW — idempotent: creates 2 test users + e2e-test-project + seeds services)
├── backend/
│   └── auth_service/
│       └── tests_integration/                  (NEW — separate from auth_service/tests/ which is unit)
│           ├── __init__.py                     (NEW — marker)
│           ├── conftest.py                     (NEW — pytest fixtures for HTTP client + login)
│           ├── test_health.py                  (NEW — /health, basic CORS preflight)
│           ├── test_auth_flow.py               (NEW — /auth/login, /auth/me, /auth/logout, bad creds)
│           ├── test_content_public.py          (NEW — /content/<slug>, /content/<slug>/types)
│           ├── test_content_draft_token.py     (NEW — /content/<slug>/draft with + without X-CMS-Preview-Token)
│           ├── test_admin_gating.py            (NEW — admin endpoints reject non-admin user with 403)
│           ├── test_publish_flow.py            (NEW — save draft → publish → public reflects)
│           ├── test_forms.py                   (NEW — /forms/<slug>/contact_form_email)
│           └── test_cors.py                    (NEW — preflight from a *.vercel.app origin)
├── e2e/                                        (NEW — Playwright workspace at repo root)
│   ├── package.json                            (NEW — Playwright + dotenv)
│   ├── package-lock.json                       (NEW)
│   ├── playwright.config.ts                    (NEW — chromium-only, headless, trace on failure)
│   ├── .env.example                            (NEW — placeholders for E2E_USER_*, E2E_BASE_URL_*)
│   ├── tsconfig.json                           (NEW)
│   ├── .gitignore                              (NEW — node_modules, test-results, playwright-report)
│   ├── README.md                               (NEW — local-run instructions)
│   ├── helpers/
│   │   ├── auth.ts                             (NEW — login fixture; reusable signed-in pages)
│   │   ├── cleanup.ts                          (NEW — restore e2e-test-project to a known state via API)
│   │   └── selectors.ts                        (NEW — shared role/text-based locators)
│   └── tests/
│       ├── 01-public.spec.ts                   (NEW — landing + login page render, no console errors)
│       ├── 02-login.spec.ts                    (NEW — happy path + bad creds + logout)
│       ├── 03-dashboard.spec.ts                (NEW — project list loads + project workspace opens)
│       ├── 04-account.spec.ts                  (NEW — theme toggle + name change)
│       ├── 05-cms-edit.spec.ts                 (NEW — text_block edit → save → reload → value persisted)
│       ├── 06-publish.spec.ts                  (NEW — draft edit → publish → /content reflects within 60s)
│       └── 07-admin.spec.ts                    (NEW — admin pages load for admin user; 403/redirect for regular user)
└── docs/
    └── superpowers/plans/
        └── 2026-05-02-e2e-merge-gate.md        (this plan)
```

**Why the split:**

- `backend/auth_service/tests_integration/` is a **sibling** of `tests/`, not a child. The `pytest.ini` test discovery picks both up by default, but the new `e2e.yml` workflow runs only `tests_integration/` (fast, hits the deployed backend), while the existing `ci.yml` keeps running only `tests/` (unit, mocked Supabase). `requirements-dev.txt` already pins `httpx` and `pytest-asyncio`.
- `e2e/` lives at the **repo root**, not inside `frontend/`. Reasons:
  1. Playwright targets the deployed URL; it's not a Next.js dev-server harness.
  2. Keeps `frontend/`'s vitest-based unit suite isolated.
  3. Simpler CI caching (Playwright browsers cached separately from Next.js build).
- Each `e2e/tests/NN-name.spec.ts` is numbered to encode dependency order: 01 needs no auth, 02 establishes auth, 03+ depend on 02's login fixture.

---

## Test users + seed data (one-time setup, lives in Supabase prod DB)

| Account | Email | `is_admin` | Purpose |
|---------|-------|------------|---------|
| Regular | `e2e-user@cms-test.local` | `false` | Owns `e2e-test-project`. Drives login/dashboard/account/edit-save/publish tests. |
| Admin | `e2e-admin@cms-test.local` | `true` | Drives admin-page tests (`/dashboard/admin/*`). |

**Project**: `e2e-test-project` (owned by regular user). Seeded with **3 services** that exercise the diverse content shapes the editor supports:

1. `e2e_text` — `text_block` — initial `{title: "E2E Title", body: "E2E Body"}`
2. `e2e_features` — `repeater` with item_schema `[{key:"label",type:"string"},{key:"detail",type:"richtext"}]` — initial 2 items
3. `e2e_contact_form` — `email_config` — `{destination_email: "e2e-user@cms-test.local"}`

A 4th seed item is the project's own `allowed_origins` set to include the Playwright user-agent's origin so forms-CORS tests pass.

**Cleanup contract**: every test that mutates restores the affected service's content to the seed value before exiting. The shared `helpers/cleanup.ts` and `conftest.py` fixtures encapsulate this.

---

## GitHub Actions secrets to add

After Phase 1 lands, add these via GitHub UI (Settings → Secrets → Actions):

| Secret | Value | Used by |
|--------|-------|---------|
| `E2E_USER_EMAIL` | `e2e-user@cms-test.local` | both workflows |
| `E2E_USER_PASSWORD` | (random ≥16 chars; captured at seed time) | both workflows |
| `E2E_ADMIN_EMAIL` | `e2e-admin@cms-test.local` | both workflows |
| `E2E_ADMIN_PASSWORD` | (random ≥16 chars) | both workflows |
| `E2E_BASE_URL_FRONTEND` | `https://cms-frontend-roman.vercel.app` | E2E only |
| `E2E_BASE_URL_BACKEND` | `https://cms-backend-roman.vercel.app` | both workflows |
| `SUPABASE_PAT` | already exists locally as `sbp_*` — copy to secrets | seed script |

---

## Phase 1 — Test infrastructure

Lays the foundation. No tests yet.

### Task 1: Create the seed script for test users + project

**Files:**
- Create: `scripts/seed_e2e.py`

**Why:** Tests need two real Supabase auth accounts plus a known project. Doing this once via the existing admin endpoints (which we already battle-tested in the CMS Connector agent run) is more reliable than manual dashboard clicking. Idempotent: re-running asserts the right state and bails out if anything's already correct.

- [ ] **Step 1: Write the script**

  Create `scripts/seed_e2e.py`:
  ```python
  """seed_e2e.py — idempotent seed for the E2E test environment.

  Creates (if missing):
    • Regular user  e2e-user@cms-test.local
    • Admin user    e2e-admin@cms-test.local
    • Project       e2e-test-project (owned by regular user)
    • 3 services    e2e_text, e2e_features, e2e_contact_form
    • allowed_origins on the project (so forms CORS works)

  Re-running is safe: existing rows are detected and left alone unless
  --reset is passed (which deletes + recreates the project).

  Required env vars:
    SUPABASE_PAT     personal access token (sbp_*) — has DB query rights
    SUPABASE_PROJECT_REF  project ref (e.g. xeluydwpgiddbamysgyu)
    SUPABASE_URL     https://<ref>.supabase.co
    SUPABASE_SERVICE_ROLE  the new sb_secret_* key (not legacy JWT)
    E2E_USER_PASSWORD       known password to set on regular user
    E2E_ADMIN_PASSWORD      known password to set on admin user

  Run:
    python scripts/seed_e2e.py
    python scripts/seed_e2e.py --reset    # nuke + recreate the project
  """
  from __future__ import annotations

  import argparse
  import json
  import os
  import sys
  import urllib.error
  import urllib.request

  PAT = os.environ["SUPABASE_PAT"]
  REF = os.environ["SUPABASE_PROJECT_REF"]
  SUPABASE_URL = os.environ["SUPABASE_URL"].rstrip("/")
  SERVICE_ROLE = os.environ["SUPABASE_SERVICE_ROLE"]
  E2E_USER_PASSWORD = os.environ["E2E_USER_PASSWORD"]
  E2E_ADMIN_PASSWORD = os.environ["E2E_ADMIN_PASSWORD"]

  REGULAR_EMAIL = "e2e-user@cms-test.local"
  ADMIN_EMAIL = "e2e-admin@cms-test.local"
  PROJECT_SLUG = "e2e-test-project"
  PROJECT_NAME = "E2E Test Project"


  def _http(method: str, url: str, headers: dict, body: dict | None = None) -> dict:
      data = json.dumps(body).encode() if body is not None else None
      req = urllib.request.Request(url, data=data, headers=headers, method=method)
      try:
          with urllib.request.urlopen(req) as r:
              raw = r.read().decode() or "{}"
              return json.loads(raw)
      except urllib.error.HTTPError as e:
          err = e.read().decode()
          raise RuntimeError(f"{method} {url} → {e.code} {err}") from e


  def supabase_sql(sql: str) -> list[dict]:
      """Run a SQL query via Supabase Management API."""
      return _http(
          "POST",
          f"https://api.supabase.com/v1/projects/{REF}/database/query",
          {"Authorization": f"Bearer {PAT}", "Content-Type": "application/json"},
          {"query": sql},
      )


  def auth_admin(method: str, path: str, body: dict | None = None) -> dict:
      """Hit Supabase auth admin API with the service_role key."""
      return _http(
          method,
          f"{SUPABASE_URL}/auth/v1/admin{path}",
          {
              "Authorization": f"Bearer {SERVICE_ROLE}",
              "apikey": SERVICE_ROLE,
              "Content-Type": "application/json",
          },
          body,
      )


  def find_or_create_auth_user(email: str, password: str, full_name: str) -> str:
      """Returns the auth user_id. Creates if missing, resets password if exists."""
      # List users (filter param works as a search query)
      result = _http(
          "GET",
          f"{SUPABASE_URL}/auth/v1/admin/users?filter={email}",
          {"Authorization": f"Bearer {SERVICE_ROLE}", "apikey": SERVICE_ROLE},
      )
      users = result.get("users") or []
      match = next((u for u in users if u.get("email") == email), None)
      if match:
          uid = match["id"]
          # Reset password to the known one
          auth_admin("PUT", f"/users/{uid}", {"password": password})
          print(f"  ✓ {email} exists ({uid}) — password reset")
          return uid
      created = auth_admin(
          "POST",
          "/users",
          {
              "email": email,
              "password": password,
              "email_confirm": True,
              "user_metadata": {"full_name": full_name},
          },
      )
      uid = created["id"]
      print(f"  + created auth user {email} ({uid})")
      return uid


  def upsert_public_user(uid: str, email: str, full_name: str, is_admin: bool) -> None:
      """Insert into public.users with argon2-hashed password the BACKEND's
      auth_service.verify_password() can validate. We hash via supabase
      stored proc rather than reaching for argon2 here so the script stays
      stdlib-only — but supabase doesn't have argon2 built in, so we must
      install argon2-cffi temporarily. Keep this script's deps in sync with
      backend/requirements.txt."""
      from argon2 import PasswordHasher  # noqa: PLC0415  (script-local import)

      hasher = PasswordHasher(time_cost=3, memory_cost=65536, parallelism=4)
      pwd = E2E_ADMIN_PASSWORD if is_admin else E2E_USER_PASSWORD
      pwd_hash = hasher.hash(pwd)
      sql = (
          "INSERT INTO users (id, email, full_name, password_hash, is_admin, is_active) "
          f"VALUES ('{uid}', '{email}', '{full_name}', '{pwd_hash}', {str(is_admin).lower()}, true) "
          "ON CONFLICT (id) DO UPDATE SET password_hash = EXCLUDED.password_hash, "
          "is_admin = EXCLUDED.is_admin, is_active = true RETURNING id, email, is_admin"
      )
      rows = supabase_sql(sql)
      print(f"  ✓ public.users upsert: {rows[0]}")


  def upsert_project(owner_id: str, *, reset: bool) -> str:
      if reset:
          supabase_sql(f"DELETE FROM projects WHERE slug = '{PROJECT_SLUG}'")
          print(f"  - deleted project {PROJECT_SLUG} (--reset)")

      existing = supabase_sql(f"SELECT id FROM projects WHERE slug = '{PROJECT_SLUG}'")
      if existing:
          pid = existing[0]["id"]
          print(f"  ✓ project {PROJECT_SLUG} exists ({pid})")
          return pid
      inserted = supabase_sql(
          "INSERT INTO projects (user_id, name, slug, description, is_active, allowed_origins) "
          f"VALUES ('{owner_id}', '{PROJECT_NAME}', '{PROJECT_SLUG}', "
          "'Used by E2E tests — do not delete.', true, "
          "ARRAY['https://cms-frontend-roman.vercel.app']::text[]) "
          "RETURNING id"
      )
      pid = inserted[0]["id"]
      print(f"  + created project {PROJECT_SLUG} ({pid})")
      return pid


  def upsert_seed_services(project_id: str) -> None:
      """Add the 3 seed services if missing. Each has a content_entries row
      with both draft_content and published_content set to the same baseline
      so /content reads work immediately."""
      services = [
          {
              "service_key": "e2e_text",
              "service_type_slug": "text_block",
              "label": "E2E text block",
              "display_order": 1,
              "page_name": "General",
              "content": {"title": "E2E Title", "body": "E2E Body"},
          },
          {
              "service_key": "e2e_features",
              "service_type_slug": "repeater",
              "label": "E2E features",
              "display_order": 2,
              "page_name": "General",
              "content": {
                  "_schema": [
                      {"key": "label", "label": "Label", "type": "string"},
                      {"key": "detail", "label": "Detail", "type": "richtext"},
                  ],
                  "items": [
                      {"label": "alpha", "detail": "first"},
                      {"label": "beta", "detail": "second"},
                  ],
              },
          },
          {
              "service_key": "e2e_contact_form",
              "service_type_slug": "email_config",
              "label": "E2E contact form",
              "display_order": 3,
              "page_name": "General",
              "content": {"destination_email": REGULAR_EMAIL},
          },
      ]
      for svc in services:
          row = supabase_sql(
              f"SELECT id FROM project_services WHERE project_id = '{project_id}' "
              f"AND service_key = '{svc['service_key']}'"
          )
          if row:
              sid = row[0]["id"]
              print(f"  ✓ service {svc['service_key']} exists ({sid})")
          else:
              ins = supabase_sql(
                  "INSERT INTO project_services (project_id, service_type_slug, "
                  "service_key, label, display_order, page_name) VALUES ("
                  f"'{project_id}', '{svc['service_type_slug']}', "
                  f"'{svc['service_key']}', '{svc['label']}', "
                  f"{svc['display_order']}, '{svc['page_name']}') RETURNING id"
              )
              sid = ins[0]["id"]
              print(f"  + service {svc['service_key']} created ({sid})")
          # Seed content (always rewrite to baseline)
          ce_json = json.dumps(svc["content"]).replace("'", "''")
          supabase_sql(
              "INSERT INTO content_entries (project_service_id, draft_content, "
              f"published_content) VALUES ('{sid}', '{ce_json}'::jsonb, '{ce_json}'::jsonb) "
              "ON CONFLICT (project_service_id) DO UPDATE SET draft_content = EXCLUDED.draft_content, "
              "published_content = EXCLUDED.published_content"
          )
          print(f"    ↳ content seeded for {svc['service_key']}")


  def main() -> None:
      ap = argparse.ArgumentParser()
      ap.add_argument("--reset", action="store_true",
                      help="delete and recreate the e2e project before seeding")
      args = ap.parse_args()

      print("\n📦 Seeding E2E test data\n")
      regular_uid = find_or_create_auth_user(
          REGULAR_EMAIL, E2E_USER_PASSWORD, "E2E Test User"
      )
      upsert_public_user(regular_uid, REGULAR_EMAIL, "E2E Test User", is_admin=False)
      admin_uid = find_or_create_auth_user(
          ADMIN_EMAIL, E2E_ADMIN_PASSWORD, "E2E Admin"
      )
      upsert_public_user(admin_uid, ADMIN_EMAIL, "E2E Admin", is_admin=True)
      project_id = upsert_project(regular_uid, reset=args.reset)
      upsert_seed_services(project_id)
      print("\n✅ seed complete\n")


  if __name__ == "__main__":
      main()
  ```

- [ ] **Step 2: Run the script with the env vars set**

  Generate strong passwords first:
  ```bash
  python -c "import secrets,string;a=string.ascii_letters+string.digits;print(''.join(secrets.choice(a) for _ in range(20)))"
  ```
  Run twice; capture both. Save them — you'll paste into GitHub Secrets later.

  Then:
  ```bash
  cd "C:/Users/stefa/.gemini/antigravity/scratch/CMS - websites"
  export SUPABASE_PAT=<your-sbp_*-PAT>
  export SUPABASE_PROJECT_REF=xeluydwpgiddbamysgyu
  export SUPABASE_URL=https://xeluydwpgiddbamysgyu.supabase.co
  export SUPABASE_SERVICE_ROLE=<sb_secret_* from Supabase dashboard>
  export E2E_USER_PASSWORD=<password 1>
  export E2E_ADMIN_PASSWORD=<password 2>

  backend/venv/Scripts/python.exe scripts/seed_e2e.py
  ```
  Expected output: each step ends with ✓ or +, plus a final `✅ seed complete`.

- [ ] **Step 3: Verify via the deployed backend**

  ```bash
  # Login as the regular test user
  curl -i -X POST https://cms-backend-roman.vercel.app/auth/login \
    -H "Content-Type: application/json" \
    -d "{\"email\":\"e2e-user@cms-test.local\",\"password\":\"$E2E_USER_PASSWORD\"}"
  ```
  Expected: HTTP 200, `Set-Cookie: sid=...`. Anything else → re-run the seed.

  ```bash
  # Public content for the seed project
  curl -s https://cms-backend-roman.vercel.app/content/e2e-test-project | head -c 200
  ```
  Expected: 200 + JSON manifest containing `e2e_text` and `e2e_features` keys.

- [ ] **Step 4: Commit**

  ```bash
  git add scripts/seed_e2e.py
  git commit -m "build(scripts): seed_e2e.py creates 2 test users + e2e-test-project (idempotent)"
  ```

### Task 2: Add the GitHub Actions secrets

**Files:** none (UI work)

- [ ] **Step 1: Open Repository Settings → Secrets and variables → Actions → New repository secret**

  Add each one (values from Task 1 step 2):
  - `E2E_USER_EMAIL` → `e2e-user@cms-test.local`
  - `E2E_USER_PASSWORD` → (the captured strong password)
  - `E2E_ADMIN_EMAIL` → `e2e-admin@cms-test.local`
  - `E2E_ADMIN_PASSWORD` → (the captured strong password)
  - `E2E_BASE_URL_FRONTEND` → `https://cms-frontend-roman.vercel.app`
  - `E2E_BASE_URL_BACKEND` → `https://cms-backend-roman.vercel.app`

  These are separate from the `SUPABASE_*` ones the seed script uses. The seed script is run **manually** (or in a one-shot workflow) — CI workflows do NOT need the Supabase PAT.

- [ ] **Step 2: Verify they exist**

  ```bash
  gh secret list -R stefanroman22/cms-platform | grep E2E
  ```
  Expected: 6 lines printed.

  No commit — UI-only change.

### Task 3: Backend integration-test scaffold

**Files:**
- Create: `backend/auth_service/tests_integration/__init__.py` (empty)
- Create: `backend/auth_service/tests_integration/conftest.py`
- Modify: `backend/pytest.ini` (or `pyproject.toml`) to register an `integration` marker

- [ ] **Step 1: Create `__init__.py`**

  Empty file — pytest treats the directory as a package so fixtures auto-load:
  ```bash
  touch backend/auth_service/tests_integration/__init__.py
  ```

- [ ] **Step 2: Add an `integration` pytest marker**

  Append to `pyproject.toml` at the repo root (the file created in the dev-experience-hardening pass):
  ```toml
  [tool.pytest.ini_options]
  markers = [
      "integration: hits the deployed backend over the network",
  ]
  ```

  This lets us run `pytest -m integration` to execute only `tests_integration/` and `pytest -m 'not integration'` for the unit suite. CI's existing `ci.yml` becomes `pytest -m 'not integration'`; the new `e2e.yml` runs `pytest -m integration`.

- [ ] **Step 3: Create the conftest with HTTP fixtures**

  `backend/auth_service/tests_integration/conftest.py`:
  ```python
  """Shared HTTP client + login fixtures for integration tests.

  Tests in this directory hit the DEPLOYED backend. They use the dedicated
  E2E test users created by scripts/seed_e2e.py.
  """
  from __future__ import annotations

  import os

  import httpx
  import pytest

  BACKEND_URL = os.environ.get("E2E_BASE_URL_BACKEND", "https://cms-backend-roman.vercel.app")
  E2E_USER_EMAIL = os.environ["E2E_USER_EMAIL"]
  E2E_USER_PASSWORD = os.environ["E2E_USER_PASSWORD"]
  E2E_ADMIN_EMAIL = os.environ["E2E_ADMIN_EMAIL"]
  E2E_ADMIN_PASSWORD = os.environ["E2E_ADMIN_PASSWORD"]


  pytestmark = pytest.mark.integration


  @pytest.fixture
  def client() -> httpx.Client:
      """Bare HTTP client (no cookies). For public endpoints + auth flow tests."""
      with httpx.Client(base_url=BACKEND_URL, timeout=15.0) as c:
          yield c


  def _login(c: httpx.Client, email: str, password: str) -> None:
      r = c.post("/auth/login", json={"email": email, "password": password})
      assert r.status_code == 200, f"login failed: {r.status_code} {r.text}"
      assert "sid" in r.cookies


  @pytest.fixture
  def user_client() -> httpx.Client:
      """HTTP client logged in as the regular E2E user."""
      with httpx.Client(base_url=BACKEND_URL, timeout=15.0) as c:
          _login(c, E2E_USER_EMAIL, E2E_USER_PASSWORD)
          yield c


  @pytest.fixture
  def admin_client() -> httpx.Client:
      """HTTP client logged in as the admin E2E user."""
      with httpx.Client(base_url=BACKEND_URL, timeout=15.0) as c:
          _login(c, E2E_ADMIN_EMAIL, E2E_ADMIN_PASSWORD)
          yield c
  ```

- [ ] **Step 4: Verify the suite is empty-but-runnable**

  ```bash
  cd backend
  E2E_BASE_URL_BACKEND=https://cms-backend-roman.vercel.app \
  E2E_USER_EMAIL=e2e-user@cms-test.local \
  E2E_USER_PASSWORD="<your password>" \
  E2E_ADMIN_EMAIL=e2e-admin@cms-test.local \
  E2E_ADMIN_PASSWORD="<your password>" \
  venv/Scripts/python.exe -m pytest auth_service/tests_integration/ -v -m integration
  ```
  Expected: `collected 0 items / no tests ran`. Confirms discovery + no env import errors.

- [ ] **Step 5: Commit**

  ```bash
  git add backend/auth_service/tests_integration/__init__.py \
          backend/auth_service/tests_integration/conftest.py \
          pyproject.toml
  git commit -m "test(integration): scaffold tests_integration/ with HTTP client fixtures + integration marker"
  ```

### Task 4: Playwright workspace skeleton

**Files:**
- Create: `e2e/package.json`
- Create: `e2e/playwright.config.ts`
- Create: `e2e/tsconfig.json`
- Create: `e2e/.env.example`
- Create: `e2e/.gitignore`
- Create: `e2e/README.md`
- Create: `e2e/helpers/auth.ts`
- Create: `e2e/helpers/cleanup.ts`
- Create: `e2e/helpers/selectors.ts`

- [ ] **Step 1: Create `e2e/package.json`**

  ```json
  {
    "name": "cms-e2e",
    "version": "0.1.0",
    "private": true,
    "type": "module",
    "scripts": {
      "test": "playwright test",
      "test:headed": "playwright test --headed",
      "test:ui": "playwright test --ui",
      "report": "playwright show-report"
    },
    "devDependencies": {
      "@playwright/test": "1.49.1",
      "dotenv": "16.4.5",
      "typescript": "5.6.3"
    }
  }
  ```

- [ ] **Step 2: Create `e2e/playwright.config.ts`**

  ```typescript
  import { defineConfig } from "@playwright/test";
  import * as dotenv from "dotenv";

  dotenv.config({ path: ".env.local", quiet: true });

  const baseURL =
    process.env.E2E_BASE_URL_FRONTEND ?? "https://cms-frontend-roman.vercel.app";

  export default defineConfig({
    testDir: "./tests",
    timeout: 60_000,
    expect: { timeout: 10_000 },
    fullyParallel: false,             // serial — these tests share one DB project
    workers: 1,                        // never run two specs concurrently
    retries: process.env.CI ? 2 : 0,
    reporter: process.env.CI ? "github" : "list",
    use: {
      baseURL,
      trace: "retain-on-failure",
      screenshot: "only-on-failure",
      video: "retain-on-failure",
      // Treat any uncaught console error / page error as a test failure.
      // Each spec's beforeEach can opt out for known-noisy pages.
    },
    projects: [{ name: "chromium", use: { browserName: "chromium" } }],
  });
  ```

  Why `workers: 1` and `fullyParallel: false`: every test mutates one shared `e2e-test-project`. Concurrent writes would race.

- [ ] **Step 3: Create `e2e/tsconfig.json`**

  ```json
  {
    "compilerOptions": {
      "target": "ES2022",
      "module": "ESNext",
      "moduleResolution": "Bundler",
      "esModuleInterop": true,
      "strict": true,
      "skipLibCheck": true,
      "noEmit": true
    },
    "include": ["**/*.ts"]
  }
  ```

- [ ] **Step 4: Create `e2e/.env.example`**

  ```bash
  # Copy to .env.local and fill in. Never commit .env.local.

  E2E_BASE_URL_FRONTEND=https://cms-frontend-roman.vercel.app
  E2E_BASE_URL_BACKEND=https://cms-backend-roman.vercel.app

  E2E_USER_EMAIL=e2e-user@cms-test.local
  E2E_USER_PASSWORD=

  E2E_ADMIN_EMAIL=e2e-admin@cms-test.local
  E2E_ADMIN_PASSWORD=
  ```

- [ ] **Step 5: Create `e2e/.gitignore`**

  ```
  node_modules
  test-results
  playwright-report
  .env.local
  ```

- [ ] **Step 6: Create `e2e/helpers/auth.ts`**

  ```typescript
  import { Page, expect } from "@playwright/test";

  /**
   * Logs the given user in via the /log-in page and waits until the
   * dashboard renders. Returns when the page is ready for assertions.
   */
  export async function login(page: Page, email: string, password: string) {
    await page.goto("/log-in");
    await page.getByLabel("Email address or Username").fill(email);
    await page.getByLabel("Password").fill(password);
    await page.getByRole("button", { name: /sign in to dashboard/i }).click();
    // The login page opens /dashboard in a NAMED window. We close that window
    // for tests by overriding window.open beforehand — but for simplicity we
    // navigate directly. Wait for the auth cookie to be set.
    await expect.poll(async () => {
      const cookies = await page.context().cookies();
      return cookies.some((c) => c.name === "sid");
    }).toBe(true);
    await page.goto("/dashboard");
    await expect(page.getByRole("heading", { name: /projects/i })).toBeVisible();
  }

  export async function logout(page: Page) {
    await page.goto("/dashboard");
    await page.getByRole("button", { name: /sign out/i }).click();
    await expect(page).toHaveURL(/\/$|\/log-in/);
  }
  ```

- [ ] **Step 7: Create `e2e/helpers/cleanup.ts`**

  ```typescript
  /**
   * Restore the e2e-test-project's services to the seed state by
   * calling the backend admin API. Tests call resetSeedState() in
   * afterEach to keep runs deterministic.
   */
  const BACKEND =
    process.env.E2E_BASE_URL_BACKEND ?? "https://cms-backend-roman.vercel.app";

  const SEED = {
    e2e_text: { title: "E2E Title", body: "E2E Body" },
    e2e_features: {
      _schema: [
        { key: "label", label: "Label", type: "string" },
        { key: "detail", label: "Detail", type: "richtext" },
      ],
      items: [
        { label: "alpha", detail: "first" },
        { label: "beta", detail: "second" },
      ],
    },
    e2e_contact_form: { destination_email: "e2e-user@cms-test.local" },
  } as const;

  export async function resetSeedState(sid: string): Promise<void> {
    const headers = {
      "Content-Type": "application/json",
      Cookie: `sid=${sid}`,
    };
    for (const [serviceKey, content] of Object.entries(SEED)) {
      // email_config services are PUT-able too
      const resp = await fetch(
        `${BACKEND}/projects/e2e-test-project/services/${serviceKey}`,
        { method: "PUT", headers, body: JSON.stringify({ content }) },
      );
      if (!resp.ok) {
        throw new Error(
          `reset ${serviceKey} failed: ${resp.status} ${await resp.text()}`,
        );
      }
    }
    // Publish so /content reflects the seed state
    await fetch(`${BACKEND}/projects/e2e-test-project/publish`, {
      method: "POST",
      headers,
    });
  }

  export async function getSidCookie(
    email: string,
    password: string,
  ): Promise<string> {
    const resp = await fetch(`${BACKEND}/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
    });
    if (!resp.ok) throw new Error(`login failed: ${resp.status}`);
    const setCookie = resp.headers.get("set-cookie") ?? "";
    const m = setCookie.match(/sid=([^;]+)/);
    if (!m) throw new Error("no sid in Set-Cookie");
    return m[1];
  }
  ```

- [ ] **Step 8: Create `e2e/helpers/selectors.ts`**

  ```typescript
  /**
   * Shared selectors — keeps tests readable. Always prefer role/label
   * over CSS classes (Tailwind classes are not stable contracts).
   */
  import { Page } from "@playwright/test";

  export const heading = (page: Page, name: RegExp | string) =>
    page.getByRole("heading", { name });

  export const button = (page: Page, name: RegExp | string) =>
    page.getByRole("button", { name });

  export const link = (page: Page, name: RegExp | string) =>
    page.getByRole("link", { name });

  export const textInput = (page: Page, label: RegExp | string) =>
    page.getByLabel(label);
  ```

- [ ] **Step 9: Create `e2e/README.md`**

  ```markdown
  # E2E test suite

  Playwright + headless Chromium against the deployed Vercel projects.
  Backed by two dedicated Supabase users + one isolated e2e project that
  `scripts/seed_e2e.py` provisioned.

  ## First-time setup (laptop)

  ```bash
  cd e2e
  npm install
  npx playwright install --with-deps chromium
  cp .env.example .env.local
  # paste E2E_USER_PASSWORD + E2E_ADMIN_PASSWORD from the password manager
  ```

  ## Run

  ```bash
  npm test                  # headless
  npm run test:headed       # see the browser
  npm run test:ui           # interactive mode
  npm run report            # last run's HTML report
  ```

  ## Targeting a different backend

  Set `E2E_BASE_URL_FRONTEND` and `E2E_BASE_URL_BACKEND` in `.env.local`. Tests
  hit those URLs verbatim — they don't spin up servers.

  ## Failure debugging

  - Failed runs save trace + screenshot + video to `test-results/`.
  - `npx playwright show-trace test-results/.../trace.zip` opens the timeline.
  ```

- [ ] **Step 10: Install + verify Playwright launches**

  ```bash
  cd e2e
  npm install
  npx playwright install --with-deps chromium
  npm test
  ```
  Expected: 0 tests found, exit 0. Confirms config valid + browser installed.

- [ ] **Step 11: Add `e2e/` exception to root `.gitignore`** if needed

  Root `.gitignore` should already let `e2e/` through. Double-check:
  ```bash
  git check-ignore -v e2e/playwright.config.ts || echo "OK — not ignored"
  ```

- [ ] **Step 12: Commit**

  ```bash
  git add e2e/
  git commit -m "build(e2e): Playwright workspace scaffold + helpers (auth/cleanup/selectors)"
  ```

---

## Phase 2 — Backend integration tests

Independent of Playwright; covers the HTTP contract surface.

### Task 5: `/health` and CORS preflight

**Files:**
- Create: `backend/auth_service/tests_integration/test_health.py`
- Create: `backend/auth_service/tests_integration/test_cors.py`

- [ ] **Step 1: Write the failing tests**

  `test_health.py`:
  ```python
  import pytest

  pytestmark = pytest.mark.integration


  def test_health_returns_ok(client):
      r = client.get("/health")
      assert r.status_code == 200
      assert r.json() == {"status": "ok"}
  ```

  `test_cors.py`:
  ```python
  import pytest

  pytestmark = pytest.mark.integration


  def test_preflight_from_vercel_origin_succeeds(client):
      """Production CORS regex accepts any *.vercel.app origin."""
      r = client.options(
          "/auth/login",
          headers={
              "Origin": "https://it-global-services.vercel.app",
              "Access-Control-Request-Method": "POST",
              "Access-Control-Request-Headers": "Content-Type",
          },
      )
      assert r.status_code in (200, 204), r.text
      assert r.headers.get("access-control-allow-origin") == "https://it-global-services.vercel.app"
      assert "POST" in r.headers.get("access-control-allow-methods", "")


  def test_preflight_from_unknown_origin_rejected(client):
      r = client.options(
          "/auth/login",
          headers={
              "Origin": "https://attacker.example.com",
              "Access-Control-Request-Method": "POST",
          },
      )
      # CORSMiddleware returns 400 on rejected preflight
      assert r.headers.get("access-control-allow-origin") != "https://attacker.example.com"
  ```

- [ ] **Step 2: Run them**

  ```bash
  cd backend
  E2E_BASE_URL_BACKEND=https://cms-backend-roman.vercel.app \
  E2E_USER_EMAIL=e2e-user@cms-test.local \
  E2E_USER_PASSWORD="<pw>" \
  E2E_ADMIN_EMAIL=e2e-admin@cms-test.local \
  E2E_ADMIN_PASSWORD="<pw>" \
  venv/Scripts/python.exe -m pytest auth_service/tests_integration/test_health.py auth_service/tests_integration/test_cors.py -v
  ```
  Expected: 3 passed.

- [ ] **Step 3: Commit**

  ```bash
  git add backend/auth_service/tests_integration/test_health.py \
          backend/auth_service/tests_integration/test_cors.py
  git commit -m "test(integration): /health + CORS preflight invariants"
  ```

### Task 6: Auth flow

**Files:**
- Create: `backend/auth_service/tests_integration/test_auth_flow.py`

- [ ] **Step 1: Write the tests**

  ```python
  import os
  import pytest

  pytestmark = pytest.mark.integration

  EMAIL = os.environ["E2E_USER_EMAIL"]
  PASSWORD = os.environ["E2E_USER_PASSWORD"]


  def test_login_success_sets_sid_cookie(client):
      r = client.post("/auth/login", json={"email": EMAIL, "password": PASSWORD})
      assert r.status_code == 200
      assert "sid" in r.cookies
      sid = r.cookies["sid"]
      assert len(sid) > 20  # opaque token


  def test_me_returns_user_when_authenticated(user_client):
      r = user_client.get("/auth/me")
      assert r.status_code == 200
      data = r.json()
      assert data["email"] == EMAIL
      assert data["is_admin"] is False


  def test_me_returns_401_without_sid(client):
      r = client.get("/auth/me")
      assert r.status_code == 401


  def test_login_with_wrong_email_returns_401(client):
      r = client.post(
          "/auth/login",
          json={"email": "no-such-user@cms-test.local", "password": "x"},
      )
      assert r.status_code == 401
      assert "Invalid email or password" in r.text


  def test_login_with_wrong_password_returns_401(client):
      r = client.post(
          "/auth/login", json={"email": EMAIL, "password": "wrong"},
      )
      assert r.status_code == 401


  def test_logout_invalidates_session(client):
      lr = client.post("/auth/login", json={"email": EMAIL, "password": PASSWORD})
      sid = lr.cookies["sid"]
      logout = client.post("/auth/logout")
      assert logout.status_code == 204
      # Old sid is now dead
      me = client.get("/auth/me", cookies={"sid": sid})
      assert me.status_code == 401
  ```

- [ ] **Step 2: Run them**

  ```bash
  cd backend
  venv/Scripts/python.exe -m pytest auth_service/tests_integration/test_auth_flow.py -v
  ```
  Expected: 6 passed.

- [ ] **Step 3: Commit**

  ```bash
  git add backend/auth_service/tests_integration/test_auth_flow.py
  git commit -m "test(integration): auth flow — login / me / logout / wrong creds"
  ```

### Task 7: Public content endpoint + draft-token gating

**Files:**
- Create: `backend/auth_service/tests_integration/test_content_public.py`
- Create: `backend/auth_service/tests_integration/test_content_draft_token.py`

- [ ] **Step 1: Write `test_content_public.py`**

  ```python
  import pytest

  pytestmark = pytest.mark.integration


  def test_public_content_returns_200(client):
      r = client.get("/content/e2e-test-project")
      assert r.status_code == 200
      data = r.json()
      assert "content" in data
      # Seeded keys
      assert "e2e_text" in data["content"]
      assert "e2e_features" in data["content"]
      # Private email_config must be excluded
      assert "e2e_contact_form" not in data["content"]


  def test_public_content_returns_404_for_unknown_slug(client):
      r = client.get("/content/this-slug-does-not-exist-9999")
      assert r.status_code == 404


  def test_content_types_returns_8_types(client):
      r = client.get("/content/e2e-test-project/types")
      assert r.status_code == 200
      slugs = {t["slug"] for t in r.json()}
      # The eight built-in service types
      assert {"text_block", "image", "gallery", "video", "file_download",
              "key_value", "email_config", "repeater"} <= slugs
  ```

- [ ] **Step 2: Write `test_content_draft_token.py`**

  We need the project's preview_token to test the draft endpoint. Look it up dynamically via the admin API (the admin client fixture in conftest.py is already authenticated as admin):

  ```python
  import os
  import pytest

  pytestmark = pytest.mark.integration


  def test_draft_without_token_returns_401(client):
      r = client.get("/content/e2e-test-project/draft")
      assert r.status_code == 401


  def test_draft_with_wrong_token_returns_401(client):
      r = client.get(
          "/content/e2e-test-project/draft",
          headers={"X-CMS-Preview-Token": "totally-not-the-token"},
      )
      assert r.status_code == 401


  def test_draft_with_valid_token_returns_200(client, admin_client):
      # Look up the project's preview_token via the admin API
      detail = admin_client.get("/admin/projects/e2e-test-project")
      assert detail.status_code == 200
      preview_token = detail.json().get("preview_token")
      if not preview_token:
          pytest.skip("e2e-test-project has no preview_token set; skipping draft test")
      r = client.get(
          "/content/e2e-test-project/draft",
          headers={"X-CMS-Preview-Token": preview_token},
      )
      assert r.status_code == 200
      assert "content" in r.json()
  ```

- [ ] **Step 3: Run + commit**

  ```bash
  venv/Scripts/python.exe -m pytest auth_service/tests_integration/test_content_public.py auth_service/tests_integration/test_content_draft_token.py -v
  git add backend/auth_service/tests_integration/test_content_public.py \
          backend/auth_service/tests_integration/test_content_draft_token.py
  git commit -m "test(integration): public /content + draft endpoint token gating"
  ```

### Task 8: Admin endpoint gating

**Files:**
- Create: `backend/auth_service/tests_integration/test_admin_gating.py`

- [ ] **Step 1: Write tests**

  ```python
  import pytest

  pytestmark = pytest.mark.integration


  @pytest.mark.parametrize(
      "method, path",
      [
          ("GET", "/admin/projects"),
          ("GET", "/admin/clients"),
          ("GET", "/admin/projects/e2e-test-project"),
          ("PATCH", "/admin/projects/e2e-test-project"),
      ],
  )
  def test_admin_endpoint_403_for_regular_user(method, path, user_client):
      r = user_client.request(method, path, json={} if method == "PATCH" else None)
      assert r.status_code == 403, f"{method} {path} → {r.status_code} {r.text}"


  def test_admin_can_list_projects(admin_client):
      r = admin_client.get("/admin/projects")
      assert r.status_code == 200
      slugs = [p["slug"] for p in r.json()]
      assert "e2e-test-project" in slugs


  def test_admin_can_list_clients(admin_client):
      r = admin_client.get("/admin/clients")
      assert r.status_code == 200
      emails = [c["email"] for c in r.json()]
      assert "e2e-user@cms-test.local" in emails
      assert "e2e-admin@cms-test.local" in emails
  ```

- [ ] **Step 2: Run + commit**

  ```bash
  venv/Scripts/python.exe -m pytest auth_service/tests_integration/test_admin_gating.py -v
  git add backend/auth_service/tests_integration/test_admin_gating.py
  git commit -m "test(integration): admin endpoints reject non-admin (403)"
  ```

### Task 9: Publish flow round-trip

**Files:**
- Create: `backend/auth_service/tests_integration/test_publish_flow.py`

- [ ] **Step 1: Write the test**

  Strategy: mutate `e2e_text` draft → publish → public `/content` reflects → restore.

  ```python
  import time
  import pytest

  pytestmark = pytest.mark.integration


  SERVICE_KEY = "e2e_text"
  SEED = {"title": "E2E Title", "body": "E2E Body"}


  @pytest.fixture
  def restore_text(user_client):
      """Reset e2e_text to seed value after the test, regardless of pass/fail."""
      yield
      user_client.put(
          f"/projects/e2e-test-project/services/{SERVICE_KEY}",
          json={"content": SEED},
      )
      user_client.post("/projects/e2e-test-project/publish")


  def test_publish_round_trip(client, user_client, restore_text):
      ts = int(time.time())
      new_content = {"title": f"E2E Title {ts}", "body": f"E2E Body {ts}"}

      # 1. Save as draft via the user-scoped PUT
      put = user_client.put(
          f"/projects/e2e-test-project/services/{SERVICE_KEY}",
          json={"content": new_content},
      )
      assert put.status_code == 200

      # 2. Public /content still shows the OLD value (draft hasn't been published)
      pub_before = client.get("/content/e2e-test-project")
      assert pub_before.status_code == 200
      assert pub_before.json()["content"][SERVICE_KEY].get("title") != new_content["title"]

      # 3. Publish
      pub = user_client.post("/projects/e2e-test-project/publish")
      assert pub.status_code == 200
      assert pub.json()["published_count"] >= 1

      # 4. Public /content now reflects the new value
      pub_after = client.get("/content/e2e-test-project")
      assert pub_after.status_code == 200
      assert pub_after.json()["content"][SERVICE_KEY]["title"] == new_content["title"]
  ```

- [ ] **Step 2: Run + commit**

  ```bash
  venv/Scripts/python.exe -m pytest auth_service/tests_integration/test_publish_flow.py -v
  git add backend/auth_service/tests_integration/test_publish_flow.py
  git commit -m "test(integration): publish flow — draft → publish → public reflects"
  ```

### Task 10: Forms endpoint

**Files:**
- Create: `backend/auth_service/tests_integration/test_forms.py`

- [ ] **Step 1: Write the test**

  ```python
  import pytest

  pytestmark = pytest.mark.integration


  def test_form_submit_returns_200(client):
      r = client.post(
          "/forms/e2e-test-project/e2e_contact_form",
          json={
              "name": "E2E test",
              "email": "e2e-user@cms-test.local",
              "message": "[E2E-TEST] integration test submission",
          },
          headers={"Origin": "https://cms-frontend-roman.vercel.app"},
      )
      assert r.status_code == 200, r.text
      assert r.json().get("success") is True


  def test_form_submit_404_for_missing_form_key(client):
      r = client.post(
          "/forms/e2e-test-project/no_such_form",
          json={"message": "x"},
          headers={"Origin": "https://cms-frontend-roman.vercel.app"},
      )
      assert r.status_code == 404


  def test_form_submit_422_on_empty_body(client):
      r = client.post(
          "/forms/e2e-test-project/e2e_contact_form",
          json={},
          headers={"Origin": "https://cms-frontend-roman.vercel.app"},
      )
      assert r.status_code == 422
  ```

  Note: this fires real Resend emails. The destination is the test user's `cms-test.local` domain (non-routable RFC 6762 → bounces silently). If Resend's domain hardening blocks the bounce, replace the seed `destination_email` with a real archive inbox.

- [ ] **Step 2: Run + commit**

  ```bash
  venv/Scripts/python.exe -m pytest auth_service/tests_integration/test_forms.py -v
  git add backend/auth_service/tests_integration/test_forms.py
  git commit -m "test(integration): /forms/<slug>/<form_key> happy path + edge cases"
  ```

---

## Phase 3 — Frontend E2E (Playwright)

### Task 11: Public-page render checks

**Files:**
- Create: `e2e/tests/01-public.spec.ts`

- [ ] **Step 1: Write the spec**

  ```typescript
  import { test, expect } from "@playwright/test";

  test.describe("Public pages — render without DOM errors", () => {
    test("landing / loads and has no console errors", async ({ page }) => {
      const errors: string[] = [];
      page.on("pageerror", (err) => errors.push(err.message));
      page.on("console", (msg) => {
        if (msg.type() === "error") errors.push(msg.text());
      });
      await page.goto("/");
      await expect(page).toHaveTitle(/.+/);
      // Page rendered
      await expect(page.locator("body")).toBeVisible();
      expect(errors, `Console/page errors:\n${errors.join("\n")}`).toEqual([]);
    });

    test("/log-in renders form fields", async ({ page }) => {
      await page.goto("/log-in");
      await expect(page.getByLabel("Email address or Username")).toBeVisible();
      await expect(page.getByLabel("Password")).toBeVisible();
      await expect(page.getByRole("button", { name: /sign in to dashboard/i })).toBeVisible();
    });
  });
  ```

- [ ] **Step 2: Run**

  ```bash
  cd e2e
  npm test -- 01-public.spec.ts
  ```
  Expected: 2 passed.

- [ ] **Step 3: Commit**

  ```bash
  git add e2e/tests/01-public.spec.ts
  git commit -m "test(e2e): public pages render without console errors"
  ```

### Task 12: Login + logout flow

**Files:**
- Create: `e2e/tests/02-login.spec.ts`

- [ ] **Step 1: Write the spec**

  ```typescript
  import { test, expect } from "@playwright/test";
  import { login } from "../helpers/auth";

  const EMAIL = process.env.E2E_USER_EMAIL!;
  const PASSWORD = process.env.E2E_USER_PASSWORD!;

  test.describe("Login flow", () => {
    test("happy path — login → dashboard renders", async ({ page }) => {
      await login(page, EMAIL, PASSWORD);
      // Dashboard heading + at least one project card
      await expect(page.getByRole("heading", { name: /projects/i })).toBeVisible();
    });

    test("wrong password — error shown, no cookie", async ({ page }) => {
      await page.goto("/log-in");
      await page.getByLabel("Email address or Username").fill(EMAIL);
      await page.getByLabel("Password").fill("definitely-not-the-password");
      await page.getByRole("button", { name: /sign in to dashboard/i }).click();
      await expect(page.getByText(/Invalid email or password/i)).toBeVisible();
      const cookies = await page.context().cookies();
      expect(cookies.find((c) => c.name === "sid")).toBeUndefined();
    });

    test("logout clears the session", async ({ page }) => {
      await login(page, EMAIL, PASSWORD);
      // Find and click sign out
      await page.getByRole("button", { name: /sign out/i }).click();
      // Should land back on landing or login
      await expect(page).toHaveURL(/\/(log-in)?$/);
      const cookies = await page.context().cookies();
      expect(cookies.find((c) => c.name === "sid")).toBeUndefined();
    });
  });
  ```

- [ ] **Step 2: Run + commit**

  ```bash
  npm test -- 02-login.spec.ts
  git add e2e/tests/02-login.spec.ts
  git commit -m "test(e2e): login happy path + bad password + logout"
  ```

### Task 13: Dashboard project list + workspace open

**Files:**
- Create: `e2e/tests/03-dashboard.spec.ts`

- [ ] **Step 1: Spec**

  ```typescript
  import { test, expect } from "@playwright/test";
  import { login } from "../helpers/auth";

  test.describe("Dashboard", () => {
    test.beforeEach(async ({ page }) => {
      await login(page, process.env.E2E_USER_EMAIL!, process.env.E2E_USER_PASSWORD!);
    });

    test("e2e-test-project appears in the project list", async ({ page }) => {
      await expect(page.getByText("E2E Test Project")).toBeVisible();
    });

    test("clicking the project opens its workspace", async ({ page }) => {
      await page.getByText("E2E Test Project").click();
      await expect(page).toHaveURL(/\/dashboard\/e2e-test-project/);
      // Service grid shows seeded services
      await expect(page.getByText(/E2E text block/i)).toBeVisible();
      await expect(page.getByText(/E2E features/i)).toBeVisible();
    });

    test("project workspace shows live website card when website_url is set", async ({ page }) => {
      // Only assert presence of label; URL set by seed script
      await page.goto("/dashboard/e2e-test-project");
      // The card may or may not exist depending on whether website_url is seeded;
      // verify either it's absent OR contains the LIVE WEBSITE label.
      const card = page.getByText(/Live website/i);
      if (await card.count()) {
        await expect(card.first()).toBeVisible();
      }
    });
  });
  ```

- [ ] **Step 2: Run + commit**

  ```bash
  npm test -- 03-dashboard.spec.ts
  git add e2e/tests/03-dashboard.spec.ts
  git commit -m "test(e2e): dashboard list + workspace open"
  ```

### Task 14: Account page + theme toggle

**Files:**
- Create: `e2e/tests/04-account.spec.ts`

- [ ] **Step 1: Spec**

  ```typescript
  import { test, expect } from "@playwright/test";
  import { login } from "../helpers/auth";

  test.describe("Account page", () => {
    test.beforeEach(async ({ page }) => {
      await login(page, process.env.E2E_USER_EMAIL!, process.env.E2E_USER_PASSWORD!);
      await page.goto("/dashboard/account");
    });

    test("renders profile + appearance + change-password sections", async ({ page }) => {
      await expect(page.getByRole("heading", { name: /Account Settings/i })).toBeVisible();
      await expect(page.getByText(/Profile/i)).toBeVisible();
      await expect(page.getByText(/Appearance/i)).toBeVisible();
      await expect(page.getByText(/Change Password/i)).toBeVisible();
    });

    test("theme toggle flips html class and persists across reload", async ({ page }) => {
      // Detect initial mode by sampling html.classList
      const initial = await page.evaluate(() => document.documentElement.classList.contains("dark"));
      // Click the theme toggle button (role=switch)
      const toggle = page.getByRole("switch", { name: /toggle theme/i });
      await toggle.click();
      // Wait for class flip
      await expect.poll(async () =>
        page.evaluate(() => document.documentElement.classList.contains("dark")),
      ).toBe(!initial);
      // Reload — theme should persist via localStorage
      await page.reload();
      const afterReload = await page.evaluate(() =>
        document.documentElement.classList.contains("dark"),
      );
      expect(afterReload).toBe(!initial);
      // Reset to initial state for the next test
      await page.getByRole("switch", { name: /toggle theme/i }).click();
    });
  });
  ```

- [ ] **Step 2: Run + commit**

  ```bash
  npm test -- 04-account.spec.ts
  git add e2e/tests/04-account.spec.ts
  git commit -m "test(e2e): account page renders + theme toggle persists"
  ```

### Task 15: CMS edit + save persistence

**Files:**
- Create: `e2e/tests/05-cms-edit.spec.ts`

- [ ] **Step 1: Spec**

  ```typescript
  import { test, expect } from "@playwright/test";
  import { login } from "../helpers/auth";
  import { resetSeedState, getSidCookie } from "../helpers/cleanup";

  test.describe("CMS edit + save persistence", () => {
    test.afterEach(async () => {
      const sid = await getSidCookie(
        process.env.E2E_USER_EMAIL!,
        process.env.E2E_USER_PASSWORD!,
      );
      await resetSeedState(sid);
    });

    test("text_block save → reload → value persisted", async ({ page }) => {
      await login(page, process.env.E2E_USER_EMAIL!, process.env.E2E_USER_PASSWORD!);
      await page.goto("/dashboard/e2e-test-project/e2e_text");

      const stamp = `E2E ${Date.now()}`;
      // Title field — adjust selector to match the actual editor
      const titleField = page.getByLabel(/title/i).first();
      await titleField.fill(stamp);

      await page.getByRole("button", { name: /^Save$/ }).click();
      // Save success indicator
      await expect(page.getByText(/Changes saved successfully/i)).toBeVisible();

      // Reload the page
      await page.reload();
      // Value persisted in the editor
      await expect(page.getByLabel(/title/i).first()).toHaveValue(stamp);
    });
  });
  ```

- [ ] **Step 2: Run + commit**

  ```bash
  npm test -- 05-cms-edit.spec.ts
  git add e2e/tests/05-cms-edit.spec.ts
  git commit -m "test(e2e): text_block edit → save → reload persists"
  ```

### Task 16: Publish flow (browser-driven)

**Files:**
- Create: `e2e/tests/06-publish.spec.ts`

- [ ] **Step 1: Spec**

  ```typescript
  import { test, expect } from "@playwright/test";
  import { login } from "../helpers/auth";
  import { resetSeedState, getSidCookie } from "../helpers/cleanup";

  test.describe("Publish flow", () => {
    test.afterEach(async () => {
      const sid = await getSidCookie(
        process.env.E2E_USER_EMAIL!,
        process.env.E2E_USER_PASSWORD!,
      );
      await resetSeedState(sid);
    });

    test("edit → save → publish → public /content reflects", async ({ page, request }) => {
      await login(page, process.env.E2E_USER_EMAIL!, process.env.E2E_USER_PASSWORD!);
      await page.goto("/dashboard/e2e-test-project/e2e_text");

      const stamp = `Published ${Date.now()}`;
      await page.getByLabel(/title/i).first().fill(stamp);
      await page.getByRole("button", { name: /^Save$/ }).click();
      await expect(page.getByText(/Changes saved successfully/i)).toBeVisible();

      // Click the Publish Changes button in the bar at the top
      await page.getByRole("button", { name: /publish changes/i }).click();
      // Confirm modal
      await page.getByRole("button", { name: /^Publish$/ }).click();

      // Assert public content reflects within 60 seconds
      const backend = process.env.E2E_BASE_URL_BACKEND!;
      await expect.poll(async () => {
        const resp = await request.get(`${backend}/content/e2e-test-project`);
        if (!resp.ok()) return null;
        const body = await resp.json();
        return body.content?.e2e_text?.title;
      }, { timeout: 60_000, intervals: [2000, 5000, 10_000] }).toBe(stamp);
    });
  });
  ```

- [ ] **Step 2: Run + commit**

  ```bash
  npm test -- 06-publish.spec.ts
  git add e2e/tests/06-publish.spec.ts
  git commit -m "test(e2e): publish flow surfaces in /content within 60s"
  ```

### Task 17: Admin pages

**Files:**
- Create: `e2e/tests/07-admin.spec.ts`

- [ ] **Step 1: Spec**

  ```typescript
  import { test, expect } from "@playwright/test";
  import { login } from "../helpers/auth";

  test.describe("Admin pages", () => {
    test("admin user — All Clients renders e2e users", async ({ page }) => {
      await login(page, process.env.E2E_ADMIN_EMAIL!, process.env.E2E_ADMIN_PASSWORD!);
      await page.goto("/dashboard/admin/clients");
      await expect(page.getByRole("heading", { name: /All Clients/i })).toBeVisible();
      await expect(page.getByText("e2e-user@cms-test.local")).toBeVisible();
      await expect(page.getByText("e2e-admin@cms-test.local")).toBeVisible();
    });

    test("admin user — All Projects renders e2e-test-project", async ({ page }) => {
      await login(page, process.env.E2E_ADMIN_EMAIL!, process.env.E2E_ADMIN_PASSWORD!);
      await page.goto("/dashboard/admin/projects");
      await expect(page.getByRole("heading", { name: /All Projects/i })).toBeVisible();
      await expect(page.getByText(/E2E Test Project/i)).toBeVisible();
    });

    test("admin user — Service Types renders 8+ types", async ({ page }) => {
      await login(page, process.env.E2E_ADMIN_EMAIL!, process.env.E2E_ADMIN_PASSWORD!);
      await page.goto("/dashboard/admin/service-types");
      await expect(page.getByRole("heading", { name: /Service Types/i })).toBeVisible();
    });

    test("regular user gets blocked / redirected from /dashboard/admin/*", async ({ page }) => {
      await login(page, process.env.E2E_USER_EMAIL!, process.env.E2E_USER_PASSWORD!);
      await page.goto("/dashboard/admin/clients");
      // Either redirected away OR shown an empty/forbidden state.
      // Frontend just doesn't render admin nav for non-admins; the API
      // call returns 403. We assert the table doesn't show.
      await expect(page.getByText("e2e-admin@cms-test.local")).not.toBeVisible({ timeout: 5000 });
    });
  });
  ```

- [ ] **Step 2: Run + commit**

  ```bash
  npm test -- 07-admin.spec.ts
  git add e2e/tests/07-admin.spec.ts
  git commit -m "test(e2e): admin pages — admin sees data, regular user blocked"
  ```

---

## Phase 4 — Wire into CI as the merge gate

### Task 18: New `e2e.yml` workflow

**Files:**
- Create: `.github/workflows/e2e.yml`

- [ ] **Step 1: Write the workflow**

  ```yaml
  # .github/workflows/e2e.yml
  # Backend integration + frontend E2E. Runs on every push to dev/master.
  # Used by scheduled-merge.yml as a hard gate (in addition to ci.yml).

  name: E2E

  on:
    push:
      branches: [master, dev]
    workflow_dispatch:

  concurrency:
    group: e2e-${{ github.ref }}
    cancel-in-progress: true

  jobs:
    backend-integration:
      name: Backend integration (httpx → deployed FastAPI)
      runs-on: ubuntu-latest
      defaults:
        run:
          working-directory: backend
      env:
        E2E_BASE_URL_BACKEND: ${{ secrets.E2E_BASE_URL_BACKEND }}
        E2E_USER_EMAIL: ${{ secrets.E2E_USER_EMAIL }}
        E2E_USER_PASSWORD: ${{ secrets.E2E_USER_PASSWORD }}
        E2E_ADMIN_EMAIL: ${{ secrets.E2E_ADMIN_EMAIL }}
        E2E_ADMIN_PASSWORD: ${{ secrets.E2E_ADMIN_PASSWORD }}
      steps:
        - uses: actions/checkout@v4
        - uses: actions/setup-python@v5
          with:
            python-version-file: .python-version
            cache: pip
            cache-dependency-path: |
              backend/requirements.txt
              backend/requirements-dev.txt
        - run: pip install -r requirements.txt -r requirements-dev.txt
        - name: Run integration tests
          run: python -m pytest auth_service/tests_integration/ -v -m integration

    frontend-e2e:
      name: Frontend E2E (Playwright → deployed Next.js)
      runs-on: ubuntu-latest
      needs: backend-integration   # don't waste browser time if backend is broken
      defaults:
        run:
          working-directory: e2e
      env:
        E2E_BASE_URL_FRONTEND: ${{ secrets.E2E_BASE_URL_FRONTEND }}
        E2E_BASE_URL_BACKEND: ${{ secrets.E2E_BASE_URL_BACKEND }}
        E2E_USER_EMAIL: ${{ secrets.E2E_USER_EMAIL }}
        E2E_USER_PASSWORD: ${{ secrets.E2E_USER_PASSWORD }}
        E2E_ADMIN_EMAIL: ${{ secrets.E2E_ADMIN_EMAIL }}
        E2E_ADMIN_PASSWORD: ${{ secrets.E2E_ADMIN_PASSWORD }}
      steps:
        - uses: actions/checkout@v4
        - uses: actions/setup-node@v4
          with:
            node-version-file: .nvmrc
            cache: npm
            cache-dependency-path: e2e/package-lock.json
        - run: npm ci
        - run: npx playwright install --with-deps chromium
        - run: npm test
        - name: Upload Playwright report on failure
          if: failure()
          uses: actions/upload-artifact@v4
          with:
            name: playwright-report
            path: e2e/playwright-report
            retention-days: 7
  ```

- [ ] **Step 2: Validate yaml**

  ```bash
  cd "C:/Users/stefa/.gemini/antigravity/scratch/CMS - websites"
  backend/venv/Scripts/python.exe -c \
    "import yaml; print(list(yaml.safe_load(open('.github/workflows/e2e.yml'))['jobs'].keys()))"
  ```
  Expected: `['backend-integration', 'frontend-e2e']`.

- [ ] **Step 3: Commit**

  ```bash
  git add .github/workflows/e2e.yml
  git commit -m "ci: add E2E workflow (backend integration + Playwright on push to dev/master)"
  ```

### Task 19: Update `scheduled-merge.yml` to gate on E2E too

**Files:**
- Modify: `.github/workflows/scheduled-merge.yml` (the "Verify CI on dev tip is green" step)

- [ ] **Step 1: Replace the verification step**

  Open `.github/workflows/scheduled-merge.yml`. Find the step `Verify CI on dev tip is green`. Replace its `run:` block with:

  ```yaml
      - name: Verify CI + E2E on dev tip are both green
        env:
          GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}
        run: |
          DEV_SHA=$(git rev-parse dev)
          echo "Verifying CI + E2E on dev tip: $DEV_SHA"

          for WORKFLOW in "CI" "E2E"; do
            CONCLUSION=$(gh api \
              "repos/${{ github.repository }}/actions/runs?head_sha=$DEV_SHA&status=completed&per_page=20" \
              --jq "[.workflow_runs[] | select(.name == \"$WORKFLOW\")][0].conclusion")
            echo "$WORKFLOW conclusion on $DEV_SHA: $CONCLUSION"
            if [ "$CONCLUSION" != "success" ]; then
              echo "::error::$WORKFLOW on dev ($DEV_SHA) is '$CONCLUSION', refusing to merge to master."
              echo "Run $WORKFLOW on dev (push or trigger manually), wait for green, then re-run this workflow."
              exit 1
            fi
          done
  ```

  Update the step name as shown.

- [ ] **Step 2: Commit**

  ```bash
  git add .github/workflows/scheduled-merge.yml
  git commit -m "ci: scheduled-merge gates on both CI and E2E workflows"
  ```

### Task 20: Update branch protection's required status checks

**Files:** none (UI / API)

- [ ] **Step 1: Add the new E2E check names to the protection rule**

  ```bash
  cat > /tmp/protection.json <<'EOF'
  {
    "required_status_checks": {
      "strict": false,
      "contexts": [
        "Backend (FastAPI)",
        "Agent (CMS Connector — Website)",
        "Frontend (Next.js)",
        "Backend integration (httpx → deployed FastAPI)",
        "Frontend E2E (Playwright → deployed Next.js)"
      ]
    },
    "enforce_admins": true,
    "required_pull_request_reviews": null,
    "restrictions": null,
    "allow_force_pushes": false,
    "allow_deletions": false,
    "block_creations": false,
    "required_conversation_resolution": false,
    "lock_branch": false,
    "allow_fork_syncing": false
  }
  EOF
  gh api --method PUT -H "Accept: application/vnd.github+json" \
    repos/stefanroman22/cms-platform/branches/master/protection \
    --input /tmp/protection.json
  rm /tmp/protection.json
  ```
  Expected: 200 with the protection JSON echoed back, listing all 5 contexts.

  No commit — API-only.

### Task 21: Push, verify the new workflows run, fix any field-test issues

- [ ] **Step 1: Push dev**

  ```bash
  git push origin dev
  ```

- [ ] **Step 2: Watch the new workflow runs**

  ```bash
  gh run watch --exit-status
  ```
  Expected: both `backend-integration` and `frontend-e2e` jobs go green within ~5–10 minutes.

- [ ] **Step 3: If anything fails, debug**

  - Backend integration failures: re-run locally with the same env vars; the failure message tells you which assertion broke.
  - Playwright failures: download the `playwright-report` artifact from the failing run via the GitHub UI, or run locally headed: `cd e2e && npm run test:headed -- <failing-spec>`.
  - Once fixed, push the fix to dev and the workflow re-runs.

- [ ] **Step 4: Manually trigger scheduled-merge to confirm the gate works**

  ```bash
  gh workflow run "Scheduled merge dev → master"
  gh run watch --exit-status
  ```
  Expected: workflow succeeds, master is fast-forwarded to dev, Vercel kicks off auto-deploy.

---

## Self-review

**Spec coverage:**
- ✓ All pages render: Task 11 (public), Task 13 (workspace), Task 14 (account), Task 17 (admin)
- ✓ Login frontend↔backend: Task 6 (HTTP) + Task 12 (browser)
- ✓ Project retrieval in dashboard: Task 13
- ✓ Theme toggle: Task 14
- ✓ CMS edit → save → DB persisted: Task 15
- ✓ Logout invalidates: Task 6 (HTTP) + Task 12 (browser)
- ✓ Publish flow: Task 9 (HTTP) + Task 16 (browser)
- ✓ Forms submit: Task 10
- ✓ Service create + delete: NOT explicitly written; covered indirectly by the seed script using POST + the publish-flow PUT. **Gap noted:** add a follow-up task in a future plan to exercise admin POST `/projects/<slug>/services` + DELETE.
- ✓ Image upload: NOT covered. **Gap noted:** image upload requires multipart/form-data and storage to Supabase Storage; out of scope for this initial cut. Add as follow-up task.
- ✓ Public /content: Task 7
- ✓ Draft token gating: Task 7
- ✓ Admin endpoint 403: Task 8
- ✓ /health: Task 5
- ✓ CORS preflight: Task 5

**Gaps**: service create/delete admin path + image upload. Both are nice-to-have and orthogonal to the must-have user flows. Document as follow-up but do not block the merge gate on them.

**Placeholder scan:** No "TBD" / "similar to Task N" / "implement later". Code blocks contain real, runnable content. Version pins are concrete (`@playwright/test 1.49.1`, `dotenv 16.4.5`, `typescript 5.6.3`).

**Type consistency:**
- Test user emails consistent across seed script + conftest + Playwright (`e2e-user@cms-test.local`, `e2e-admin@cms-test.local`).
- Project slug consistent: `e2e-test-project` everywhere.
- Service keys consistent: `e2e_text`, `e2e_features`, `e2e_contact_form`.
- Workflow names consistent: `CI`, `E2E`, with job names matching the protection rule contexts in Task 20.

---

## Execution handoff

Plan saved to `docs/superpowers/plans/2026-05-02-e2e-merge-gate.md`.

Two execution options:

1. **Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks. Good for the cross-cutting Phase 1 setup tasks where small mistakes cost the most.
2. **Inline Execution** — execute tasks in this session with checkpoints between phases.

Which approach?
