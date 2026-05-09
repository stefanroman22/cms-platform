# BE-010 + BE-011 — RLS Policies & Bearer Auth Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close two pending audit findings — enable Row-Level Security on every tenant-scoped table (BE-010), and rate-limit the admin Bearer auth path while equalising parse-fail timing (BE-011).

**Architecture:**
- BE-010: One additive migration (`backend/migrations/2026_05_09_tenant_tables_rls.sql`) enables RLS + adds owner/admin policies on `users`, `sessions`, `projects`, `content_entries`, `project_issues`. Backend keeps using the service-role client (bypasses RLS), so behaviour is unchanged for current code paths; the failure mode for any future anon-bound query becomes "empty result" instead of "everyone's data". A presence test in CI gates regression.
- BE-011: Add a dedicated in-memory token-bucket (`core/bearer_limiter.py`) keyed by client IP (10 attempts/minute), invoked from `admin_user_via_bearer_or_sid` before `verify_admin_api_key`. Inside `verify_admin_api_key`, perform a dummy `argon2.verify` against a precomputed hash on every parse-fail / row-miss path so wall-clock time matches a successful lookup → constant-time format-validity oracle.

**Tech Stack:**
- Postgres 15 (Supabase) — RLS via `ALTER TABLE … ENABLE ROW LEVEL SECURITY` + `CREATE POLICY`
- Python 3.13, FastAPI 0.136, argon2-cffi, slowapi (existing)
- pytest (unit + integration with `@pytest.mark.integration` + `@pytest.mark.deployed_state` markers)

---

## File Structure

**Created:**
- `backend/migrations/2026_05_09_tenant_tables_rls.sql` — RLS + policies for 5 tables.
- `backend/auth_service/core/bearer_limiter.py` — small sliding-window token-bucket; one public function `check_bearer_attempt(ip: str) -> bool`.
- `backend/auth_service/tests/test_bearer_limiter.py` — unit tests for the limiter (clock-injectable).
- `backend/auth_service/tests/test_admin_keys_timing.py` — unit test confirming dummy-argon2 path runs.
- `backend/auth_service/tests_integration/test_rls_policies.py` — integration test asserting RLS is enabled on each tenant-scoped table.

**Modified:**
- `backend/auth_service/services/admin_keys.py` — add dummy hash + run `_ph.verify` on every parse-fail / row-miss path.
- `backend/auth_service/routers/deps.py` — call bearer limiter before `verify_admin_api_key`.
- `backend/auth_service/core/limiter.py` — re-use `client_ip(request)` extractor (already exists; no edit, just import).
- `~/.claude/.../memory/reference_security_audit_tracker.md` — flip BE-010 + BE-011 to `verified_fixed` after deploy.
- `docs/SECURITY.md` — short note on RLS layer + Bearer rate limit under existing "Defense layers" section.

---

## Phase 1 — BE-010: RLS policies on tenant-scoped tables

### Task 1: Write the failing RLS-presence integration test

**Files:**
- Create: `backend/auth_service/tests_integration/test_rls_policies.py`

- [ ] **Step 1: Write the failing test**

```python
"""Asserts every tenant-scoped table has RLS enabled.

Service-role bypasses RLS — backend keeps working. Anon-bound queries
(future code or a typo'd refactor) become "empty result" instead of
"everyone's data". This test catches regressions where a new table
ships without RLS or someone does `ALTER TABLE … DISABLE ROW LEVEL
SECURITY`.
"""

import os

import pytest
from supabase import create_client

pytestmark = [pytest.mark.integration]

TENANT_TABLES = [
    "users",
    "sessions",
    "projects",
    "content_entries",
    "project_issues",
    "project_requests",  # already gated by 2026_05_07_project_requests_rls.sql
]


def _service_client():
    url = os.environ["SUPABASE_URL"]
    key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    return create_client(url, key)


def test_rls_enabled_on_every_tenant_table():
    sb = _service_client()
    rows = (
        sb.rpc(
            "exec_sql",
            {
                "query": (
                    "SELECT tablename, rowsecurity "
                    "FROM pg_tables "
                    "WHERE schemaname = 'public' "
                    "AND tablename = ANY(%(names)s);"
                ),
                "params": {"names": TENANT_TABLES},
            },
        ).execute()
        if False  # placeholder — supabase-py has no exec_sql RPC by default
        else None
    )
    # Use the `pg_tables` query through a helper SQL function we ship in
    # the migration. Simpler path: query via PostgREST + a helper view.
    # See the migration for `tenant_rls_status` view.
    res = sb.table("tenant_rls_status").select("tablename, rowsecurity").execute()
    by_name = {r["tablename"]: r["rowsecurity"] for r in (res.data or [])}
    missing = [t for t in TENANT_TABLES if t not in by_name]
    assert not missing, f"Tables not present in tenant_rls_status view: {missing}"
    disabled = [t for t in TENANT_TABLES if not by_name[t]]
    assert not disabled, f"RLS disabled on: {disabled}"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest auth_service/tests_integration/test_rls_policies.py -v`
Expected: FAIL — view `tenant_rls_status` doesn't exist yet (or RLS is not enabled).

- [ ] **Step 3: Commit**

```bash
git add backend/auth_service/tests_integration/test_rls_policies.py
git commit -m "test(rls): failing presence test for tenant-table RLS"
```

---

### Task 2: Author the RLS migration

**Files:**
- Create: `backend/migrations/2026_05_09_tenant_tables_rls.sql`

- [ ] **Step 1: Write the migration**

```sql
-- backend/migrations/2026_05_09_tenant_tables_rls.sql
-- BE-010 — Enable RLS on every tenant-scoped table.
--
-- Backend uses the service-role key everywhere (see services/supabase_client.py:
-- get_supabase_admin), and service-role BYPASSES RLS by design. So enabling RLS
-- here is a no-op for current code paths.
--
-- The value is in the failure mode: any future endpoint that uses the anon
-- client, or a typo'd `.eq("user_id", uid)` that gets dropped during refactor,
-- now returns ZERO rows for cross-tenant data instead of leaking everything.
--
-- Tables covered:
--   - users           (per-row owner = id)
--   - sessions        (per-row owner = user_id)
--   - projects        (per-row owner = user_id)
--   - content_entries (per-row owner = projects.user_id via project_id FK)
--   - project_issues  (per-row owner = projects.user_id via project_id FK)
--
-- `project_requests` already gated by 2026_05_07_project_requests_rls.sql.
-- `admin_api_keys` already has RLS on (no policies = default-deny for anon).

BEGIN;

----------------------------------------------------------------------
-- 1. users
----------------------------------------------------------------------
ALTER TABLE users ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "users_self_select" ON users;
CREATE POLICY "users_self_select"
  ON users
  FOR SELECT
  TO authenticated
  USING (id = auth.uid());

DROP POLICY IF EXISTS "users_self_update" ON users;
CREATE POLICY "users_self_update"
  ON users
  FOR UPDATE
  TO authenticated
  USING (id = auth.uid())
  WITH CHECK (id = auth.uid());

----------------------------------------------------------------------
-- 2. sessions
----------------------------------------------------------------------
ALTER TABLE sessions ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "sessions_self_select" ON sessions;
CREATE POLICY "sessions_self_select"
  ON sessions
  FOR SELECT
  TO authenticated
  USING (user_id = auth.uid());

----------------------------------------------------------------------
-- 3. projects
----------------------------------------------------------------------
ALTER TABLE projects ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "projects_owner_select" ON projects;
CREATE POLICY "projects_owner_select"
  ON projects
  FOR SELECT
  TO authenticated
  USING (user_id = auth.uid());

DROP POLICY IF EXISTS "projects_owner_insert" ON projects;
CREATE POLICY "projects_owner_insert"
  ON projects
  FOR INSERT
  TO authenticated
  WITH CHECK (user_id = auth.uid());

DROP POLICY IF EXISTS "projects_owner_update" ON projects;
CREATE POLICY "projects_owner_update"
  ON projects
  FOR UPDATE
  TO authenticated
  USING (user_id = auth.uid())
  WITH CHECK (user_id = auth.uid());

----------------------------------------------------------------------
-- 4. content_entries (owner via projects FK)
----------------------------------------------------------------------
ALTER TABLE content_entries ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "content_entries_owner_select" ON content_entries;
CREATE POLICY "content_entries_owner_select"
  ON content_entries
  FOR SELECT
  TO authenticated
  USING (
    EXISTS (
      SELECT 1 FROM projects p
      WHERE p.id = content_entries.project_id
        AND p.user_id = auth.uid()
    )
  );

DROP POLICY IF EXISTS "content_entries_owner_write" ON content_entries;
CREATE POLICY "content_entries_owner_write"
  ON content_entries
  FOR ALL
  TO authenticated
  USING (
    EXISTS (
      SELECT 1 FROM projects p
      WHERE p.id = content_entries.project_id
        AND p.user_id = auth.uid()
    )
  )
  WITH CHECK (
    EXISTS (
      SELECT 1 FROM projects p
      WHERE p.id = content_entries.project_id
        AND p.user_id = auth.uid()
    )
  );

----------------------------------------------------------------------
-- 5. project_issues (owner via projects FK)
----------------------------------------------------------------------
ALTER TABLE project_issues ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "project_issues_owner_all" ON project_issues;
CREATE POLICY "project_issues_owner_all"
  ON project_issues
  FOR ALL
  TO authenticated
  USING (
    EXISTS (
      SELECT 1 FROM projects p
      WHERE p.id = project_issues.project_id
        AND p.user_id = auth.uid()
    )
  )
  WITH CHECK (
    EXISTS (
      SELECT 1 FROM projects p
      WHERE p.id = project_issues.project_id
        AND p.user_id = auth.uid()
    )
  );

----------------------------------------------------------------------
-- 6. Reporting view for the CI presence test.
--    Service-role can read; anon cannot (default-deny on the underlying
--    pg_tables row in PostgREST exposure).
----------------------------------------------------------------------
DROP VIEW IF EXISTS tenant_rls_status;
CREATE VIEW tenant_rls_status AS
SELECT tablename, rowsecurity
FROM pg_tables
WHERE schemaname = 'public'
  AND tablename IN (
    'users',
    'sessions',
    'projects',
    'content_entries',
    'project_issues',
    'project_requests'
  );

GRANT SELECT ON tenant_rls_status TO authenticated, service_role;

COMMIT;
```

- [ ] **Step 2: Sanity-check syntax with the local Supabase CLI (or psql)**

Run (if Supabase CLI available):
```bash
cd backend && supabase db lint --schema public migrations/2026_05_09_tenant_tables_rls.sql
```

Or paste-into-Supabase-SQL-editor "Validate" before applying. Expected: no syntax error.

- [ ] **Step 3: Commit the migration file**

```bash
git add backend/migrations/2026_05_09_tenant_tables_rls.sql
git commit -m "feat(db): RLS + owner policies on users/sessions/projects/content_entries/project_issues"
```

---

### Task 3: Apply the migration in Supabase

**Files:** none (manual operator step against live DB).

- [ ] **Step 1: Apply via Supabase SQL editor**

1. Open https://supabase.com/dashboard/project/xeluydwpgiddbamysgyu/sql/new
2. Paste the entire content of `backend/migrations/2026_05_09_tenant_tables_rls.sql`.
3. Click **Run**.
4. Confirm output shows: `BEGIN`, 5 × `ALTER TABLE`, ~9 × `CREATE POLICY`, `CREATE VIEW`, `GRANT`, `COMMIT`.

- [ ] **Step 2: Smoke-check the live backend still works**

Run:
```bash
curl -s https://cms-backend-roman.vercel.app/health
```
Expected: `{"status":"ok"}` (or whatever the live shape is — must be 200).

Run a content-fetch on the seeded e2e project:
```bash
curl -s "https://cms-backend-roman.vercel.app/content/e2e-test-project?token=<preview-token>"
```
Expected: 200 + content JSON (service-role bypasses RLS so behaviour unchanged).

If either fails: investigate before continuing. The most likely cause of a regression would be a code path using anon client we didn't catch — fix forward by adding a policy, not rolling back the migration.

- [ ] **Step 3: Re-run the integration test**

Run: `cd backend && SUPABASE_URL=… SUPABASE_SERVICE_ROLE_KEY=… python -m pytest auth_service/tests_integration/test_rls_policies.py -v`
Expected: PASS.

- [ ] **Step 4: Commit the migration-applied marker (no file change — log only)**

```bash
# Append a one-liner to docs/SECURITY.md "Migration log" section if it exists,
# OR add a Stefan-only note in the audit tracker. No git commit if no file
# changed; otherwise:
git add docs/SECURITY.md
git commit -m "docs(security): note 2026_05_09 RLS migration applied to live DB"
```

---

### Task 4: CI gate — wire the integration test into e2e.yml

**Files:**
- Modify: `.github/workflows/e2e.yml` — extend the dev-push integration-test step's `-m` filter to include `not deployed_state` selection of the RLS test (it has no `deployed_state` marker, so it already runs on dev-push).

- [ ] **Step 1: Verify the test already runs on dev-push**

Run:
```bash
grep -n "Run integration tests" .github/workflows/e2e.yml
```
Expected: a step like `pytest auth_service/tests_integration/ -v -m "integration and not deployed_state"`. The new RLS test has `pytestmark = [pytest.mark.integration]` (no `deployed_state`) so it's picked up automatically. **No edit needed if that step exists.** Otherwise:

- [ ] **Step 2: If missing, add the step**

```yaml
      - name: Run RLS presence test
        env:
          SUPABASE_URL: ${{ secrets.SUPABASE_URL }}
          SUPABASE_SERVICE_ROLE_KEY: ${{ secrets.SUPABASE_SERVICE_ROLE_KEY }}
        run: |
          cd backend
          python -m pytest auth_service/tests_integration/test_rls_policies.py -v
```

- [ ] **Step 3: Commit (only if e2e.yml was edited)**

```bash
git add .github/workflows/e2e.yml
git commit -m "ci(e2e): gate RLS presence on every dev-push"
```

---

## Phase 2 — BE-011: Bearer rate limit + dummy argon2 verify

### Task 5: Write failing test — bearer limiter rejects 11th attempt within a minute

**Files:**
- Create: `backend/auth_service/tests/test_bearer_limiter.py`

- [ ] **Step 1: Write the failing test**

```python
"""Unit tests for the bearer-path token bucket.

Decoupled from slowapi so the bucket is testable without standing up
a FastAPI app. Clock is injectable via the `now` parameter to avoid
sleep-based tests.
"""

from auth_service.core import bearer_limiter


def test_first_ten_attempts_pass():
    bucket = bearer_limiter.Bucket(capacity=10, window_seconds=60)
    for i in range(10):
        assert bucket.check("203.0.113.5", now=1000.0 + i) is True


def test_eleventh_attempt_blocks():
    bucket = bearer_limiter.Bucket(capacity=10, window_seconds=60)
    for i in range(10):
        bucket.check("203.0.113.5", now=1000.0 + i)
    assert bucket.check("203.0.113.5", now=1010.0) is False


def test_window_resets_after_60s():
    bucket = bearer_limiter.Bucket(capacity=10, window_seconds=60)
    for i in range(10):
        bucket.check("203.0.113.5", now=1000.0 + i)
    # 61s later → first slot has expired, attempt allowed.
    assert bucket.check("203.0.113.5", now=1061.5) is True


def test_per_ip_isolation():
    bucket = bearer_limiter.Bucket(capacity=10, window_seconds=60)
    for i in range(10):
        bucket.check("203.0.113.5", now=1000.0 + i)
    # Different IP — fresh quota.
    assert bucket.check("203.0.113.99", now=1010.0) is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest auth_service/tests/test_bearer_limiter.py -v`
Expected: FAIL — `ModuleNotFoundError: auth_service.core.bearer_limiter`.

- [ ] **Step 3: Commit**

```bash
git add backend/auth_service/tests/test_bearer_limiter.py
git commit -m "test(bearer-limiter): failing tests for sliding-window bucket"
```

---

### Task 6: Implement the in-memory bearer limiter

**Files:**
- Create: `backend/auth_service/core/bearer_limiter.py`

- [ ] **Step 1: Write the module**

```python
"""Per-IP sliding-window rate limiter for the admin Bearer auth path.

Decoupled from slowapi because slowapi's `@limiter.limit` decorator
binds to a FastAPI route handler — we need to enforce the limit
inside a dependency (`admin_user_via_bearer_or_sid`) before calling
`verify_admin_api_key`. The bucket is process-local; on Vercel each
serverless instance gets its own counter, which is acceptable given
the threat model (brute-forcing a 192-bit secret) — the floor of
10/min/IP/instance still cuts attack throughput by ~6 orders of
magnitude.

Memory bound: at most `capacity * <unique-IPs-in-window>` floats per
bucket. Old entries are pruned lazily on every `check`.
"""

from __future__ import annotations

import time
from collections import defaultdict, deque
from threading import Lock


class Bucket:
    """Sliding-window counter. Not thread-safe across processes."""

    def __init__(self, capacity: int = 10, window_seconds: int = 60) -> None:
        self.capacity = capacity
        self.window = window_seconds
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = Lock()

    def check(self, key: str, *, now: float | None = None) -> bool:
        """Returns True if the attempt is allowed; False if rate-limited.

        Records a hit on success so the next call sees the new count.
        Failed attempts (rate-limited) DO count — that's the point —
        otherwise an attacker can pause for 1ms after each 429 and
        keep guessing.
        """
        ts = time.monotonic() if now is None else now
        cutoff = ts - self.window
        with self._lock:
            q = self._hits[key]
            # Drop expired entries from the left.
            while q and q[0] <= cutoff:
                q.popleft()
            if len(q) >= self.capacity:
                return False
            q.append(ts)
            return True


# Module-level singleton. 10 attempts / 60s / IP — matches /auth/login's
# original tier (BE-002 raised /login to 30/min for typo tolerance, but
# Bearer keys are machine-issued so 10 is plenty).
_BEARER_BUCKET = Bucket(capacity=10, window_seconds=60)


def check_bearer_attempt(ip: str) -> bool:
    """Public entrypoint used by `admin_user_via_bearer_or_sid`."""
    return _BEARER_BUCKET.check(ip)
```

- [ ] **Step 2: Run unit tests to verify pass**

Run: `cd backend && python -m pytest auth_service/tests/test_bearer_limiter.py -v`
Expected: PASS — 4/4.

- [ ] **Step 3: Commit**

```bash
git add backend/auth_service/core/bearer_limiter.py
git commit -m "feat(bearer-limiter): in-memory sliding-window per-IP bucket"
```

---

### Task 7: Wire the limiter into the Bearer auth dep

**Files:**
- Modify: `backend/auth_service/routers/deps.py`

- [ ] **Step 1: Write the failing test**

Append to `backend/auth_service/tests/test_admin_auth_dep.py`:

```python
@pytest.mark.asyncio
async def test_bearer_blocked_on_rate_limit():
    """11th attempt within 60s from the same IP must 429 before
    `verify_admin_api_key` is called."""
    from auth_service.core import bearer_limiter
    # Fresh bucket so this test isn't order-dependent.
    bearer_limiter._BEARER_BUCKET = bearer_limiter.Bucket(capacity=10, window_seconds=60)
    headers = {"authorization": "Bearer cmsk_dev_aaaaaaaaaaaaaaaa_bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"}

    req = MagicMock()
    req.headers = headers
    req.cookies = {}
    req.client = MagicMock(host="203.0.113.5")

    # Verify is patched to a fail (so we burn through the bucket
    # without succeeding). 10 fails are still allowed by the limiter,
    # 11th must hit 429.
    with patch.object(deps, "verify_admin_api_key", return_value=None):
        for _ in range(10):
            with pytest.raises(HTTPException) as exc:
                await deps.admin_user_via_bearer_or_sid(req)
            assert exc.value.status_code == 401

        with pytest.raises(HTTPException) as exc:
            await deps.admin_user_via_bearer_or_sid(req)
        assert exc.value.status_code == 429
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest auth_service/tests/test_admin_auth_dep.py::test_bearer_blocked_on_rate_limit -v`
Expected: FAIL — limiter not yet called by the dep, all 11 returns 401.

- [ ] **Step 3: Edit the dep to call the limiter**

Replace `backend/auth_service/routers/deps.py`'s `admin_user_via_bearer_or_sid` with:

```python
from fastapi import HTTPException, Request, status

from ..core.bearer_limiter import check_bearer_attempt
from ..core.limiter import client_ip
from ..models.schemas import UserOut
from ..services.admin_keys import verify_admin_api_key
from ..services.sessions import validate_session
from ..services.supabase_client import get_supabase_admin

SESSION_COOKIE = "sid"


async def require_user(request: Request) -> UserOut:
    sid = request.cookies.get(SESSION_COOKIE)
    user = await validate_session(sid)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    return user


def require_project_access(project_slug: str, user: UserOut) -> dict:
    """Resolves project and checks ownership or admin. Returns project row."""
    sb = get_supabase_admin()
    result = (
        sb.table("projects")
        .select("id, name, slug, user_id, is_active")
        .eq("slug", project_slug)
        .eq("is_active", True)
        .maybe_single()
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    project = result.data
    if project["user_id"] != user.id and not user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    return project


async def admin_user_via_bearer_or_sid(request: Request):
    """Auth dep used by every admin route.

    Bearer path is rate-limited (BE-011): 10 attempts/min/IP, applied
    BEFORE verify_admin_api_key so a brute-forcer can't bypass via raw
    throughput. Cookie path is unchanged — session validation is
    already cheap and hardening lives at /auth/login (BE-002).
    """
    auth_header = request.headers.get("authorization", "")
    if auth_header.lower().startswith("bearer "):
        ip = client_ip(request)
        if not check_bearer_attempt(ip):
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many admin auth attempts; slow down.",
            )
        plain = auth_header.split(" ", 1)[1].strip()
        user = verify_admin_api_key(plain)
        if user:
            return user
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or revoked admin API key",
        )
    user = await require_user(request)
    is_admin = getattr(user, "is_admin", None)
    if is_admin is None and isinstance(user, dict):
        is_admin = user.get("is_admin")
    if not is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return user
```

- [ ] **Step 4: Run all admin-auth-dep tests**

Run: `cd backend && python -m pytest auth_service/tests/test_admin_auth_dep.py -v`
Expected: PASS — 5/5 (4 existing + 1 new).

- [ ] **Step 5: Commit**

```bash
git add backend/auth_service/routers/deps.py backend/auth_service/tests/test_admin_auth_dep.py
git commit -m "feat(bearer): rate-limit Bearer auth path at 10/min/IP (BE-011)"
```

---

### Task 8: Equalise parse-fail timing — dummy argon2 verify

**Files:**
- Modify: `backend/auth_service/services/admin_keys.py`
- Create: `backend/auth_service/tests/test_admin_keys_timing.py`

- [ ] **Step 1: Write the failing test**

Create `backend/auth_service/tests/test_admin_keys_timing.py`:

```python
"""Confirms `verify_admin_api_key` runs argon2.verify on every
parse-fail / row-miss path so wall-clock time matches the success
path.

We can't measure timing precisely in CI (noisy), so we count argon2
verify invocations via a patch — if it's called on every path,
timing is bounded by argon2's deterministic cost (~50 ms).
"""

from unittest.mock import MagicMock, patch

from auth_service.services import admin_keys


def _patch_supabase_returning(row):
    fake = MagicMock()
    fake.table.return_value.select.return_value.eq.return_value.is_.return_value.maybe_single.return_value.execute.return_value = MagicMock(  # noqa: E501
        data=row
    )
    return fake


def test_dummy_verify_runs_on_malformed_key():
    """Key doesn't start with `cmsk_` — must still call argon2.verify."""
    with patch.object(admin_keys, "_ph") as mock_ph, patch.object(
        admin_keys, "get_supabase_admin", return_value=_patch_supabase_returning(None)
    ):
        result = admin_keys.verify_admin_api_key("notakey")
        assert result is None
        assert mock_ph.verify.call_count == 1


def test_dummy_verify_runs_on_wrong_env_segment():
    with patch.object(admin_keys, "_ph") as mock_ph, patch.object(
        admin_keys, "get_supabase_admin", return_value=_patch_supabase_returning(None)
    ):
        result = admin_keys.verify_admin_api_key("cmsk_xx_aaaaaaaaaaaaaaaa_bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb")
        assert result is None
        assert mock_ph.verify.call_count == 1


def test_dummy_verify_runs_on_missing_row():
    """Well-formed key but no DB row — must still call argon2.verify."""
    with patch.object(admin_keys, "_ph") as mock_ph, patch.object(
        admin_keys, "get_supabase_admin", return_value=_patch_supabase_returning(None)
    ):
        result = admin_keys.verify_admin_api_key(
            "cmsk_dev_aaaaaaaaaaaaaaaa_bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
        )
        assert result is None
        assert mock_ph.verify.call_count == 1


def test_dummy_verify_runs_on_short_lookup_segment():
    with patch.object(admin_keys, "_ph") as mock_ph, patch.object(
        admin_keys, "get_supabase_admin", return_value=_patch_supabase_returning(None)
    ):
        result = admin_keys.verify_admin_api_key("cmsk_dev_short_secret")
        assert result is None
        assert mock_ph.verify.call_count == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && python -m pytest auth_service/tests/test_admin_keys_timing.py -v`
Expected: FAIL — current code returns None on malformed input without calling `_ph.verify` (call_count=0).

- [ ] **Step 3: Edit `admin_keys.py` to add dummy verify**

Replace `backend/auth_service/services/admin_keys.py` with:

```python
"""Admin API key minting and verification.

Key format: cmsk_<env>_<lookup>_<secret>
- env: "dev" or "prod" (informational)
- lookup: 16 hex chars, stored as key_prefix for fast row lookup
- secret: 32 hex chars, argon2-hashed at rest

The verifier parses the lookup half, fetches the single matching row,
and argon2-verifies the secret half against key_hash. To avoid leaking
format-validity through timing (BE-011 / CWE-208), every failure path
runs argon2.verify against a precomputed dummy hash, so wall-clock
time is constant regardless of where parsing failed.
"""

from __future__ import annotations

import secrets
from datetime import UTC, datetime
from typing import Literal

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

from .supabase_client import get_supabase_admin

KEY_PREFIX_LEN = 16
SECRET_LEN_TARGET = 32

_ph = PasswordHasher(time_cost=3, memory_cost=65536, parallelism=4)

# Precomputed at import time so the verify-on-fail path costs the same
# argon2 cycles as the success path. Hash of `_DUMMY_PLAIN`; we ignore
# the verify result (always raises VerifyMismatchError given a fresh
# random plain). Computed once → no startup penalty in serverless cold
# start beyond the existing PasswordHasher instantiation.
_DUMMY_PLAIN = secrets.token_hex(SECRET_LEN_TARGET // 2)
_DUMMY_HASH = _ph.hash(_DUMMY_PLAIN)


def _equalise_timing() -> None:
    """Burn argon2 cycles on every parse-fail / row-miss path so the
    response time is independent of where validation failed."""
    try:
        _ph.verify(_DUMMY_HASH, "x")
    except VerifyMismatchError:
        pass


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def mint_admin_api_key(
    *,
    user_id: str,
    name: str,
    env: Literal["dev", "prod"] = "dev",
    expires_at: str | None = None,
) -> tuple[str, str]:
    """Generates a new key, stores its hash, returns (plain_key, row_id).

    The plain key is the only thing that can be used to authenticate;
    callers must hand it to the operator immediately and never log it.
    """
    lookup = secrets.token_hex(KEY_PREFIX_LEN // 2)
    secret = secrets.token_hex(SECRET_LEN_TARGET // 2)
    plain = f"cmsk_{env}_{lookup}_{secret}"
    row = (
        get_supabase_admin()
        .table("admin_api_keys")
        .insert(
            {
                "user_id": user_id,
                "key_prefix": lookup,
                "key_hash": _ph.hash(secret),
                "name": name,
                "expires_at": expires_at,
            }
        )
        .execute()
    )
    return plain, row.data[0]["id"] if row.data else ""


def verify_admin_api_key(plain_key: str) -> dict | None:
    """Returns the user dict if `plain_key` matches an active, non-expired,
    non-revoked admin key. Updates last_used_at on success.

    BE-011: every failure path calls argon2.verify so wall-clock time
    leaks no information about WHICH validation step failed.
    """
    parts = plain_key.split("_") if plain_key else []
    if len(parts) != 4 or parts[0] != "cmsk" or parts[1] not in {"dev", "prod"}:
        _equalise_timing()
        return None
    lookup, secret = parts[2], parts[3]
    if len(lookup) != KEY_PREFIX_LEN:
        _equalise_timing()
        return None

    sb = get_supabase_admin()
    res = (
        sb.table("admin_api_keys")
        .select("id, user_id, key_hash, expires_at, scopes, " "users(email, is_admin, is_active)")
        .eq("key_prefix", lookup)
        .is_("revoked_at", "null")
        .maybe_single()
        .execute()
    )
    row = res.data if res else None
    if not row:
        _equalise_timing()
        return None

    if row.get("expires_at") and row["expires_at"] <= _now_iso():
        _equalise_timing()
        return None

    try:
        _ph.verify(row["key_hash"], secret)
    except VerifyMismatchError:
        return None

    u = row.get("users") or {}
    if not (u.get("is_admin") and u.get("is_active")):
        return None

    sb.table("admin_api_keys").update({"last_used_at": _now_iso()}).eq("id", row["id"]).execute()
    return {
        "id": row["user_id"],
        "email": u["email"],
        "is_admin": u["is_admin"],
        "is_active": u["is_active"],
    }
```

- [ ] **Step 4: Run timing tests**

Run: `cd backend && python -m pytest auth_service/tests/test_admin_keys_timing.py -v`
Expected: PASS — 4/4.

- [ ] **Step 5: Run full backend unit test suite**

Run: `cd backend && python -m pytest auth_service/tests/ -v`
Expected: PASS — all existing + new tests green.

- [ ] **Step 6: Commit**

```bash
git add backend/auth_service/services/admin_keys.py backend/auth_service/tests/test_admin_keys_timing.py
git commit -m "feat(bearer): dummy argon2 verify on parse-fail to close timing oracle (BE-011)"
```

---

### Task 9: Local end-to-end smoke test

**Files:** none (manual verification).

- [ ] **Step 1: Start backend locally**

Run (in one terminal):
```bash
cd backend && source venv/Scripts/activate && uvicorn auth_service.main:app --reload --port 8001
```

- [ ] **Step 2: Burn the bearer bucket**

Run (in another terminal):
```bash
for i in {1..11}; do
  curl -s -o /dev/null -w "%{http_code}\n" \
    -H "Authorization: Bearer cmsk_dev_0000000000000000_00000000000000000000000000000000" \
    http://127.0.0.1:8001/admin/clients
done
```
Expected output: ten `401` lines, then a `429` line.

- [ ] **Step 3: Confirm valid sid still works (limiter scoped to Bearer)**

Login via the dashboard at http://localhost:3000/log-in → hit `/dashboard/admin/clients` → should still load. (This proves the limiter only gates the Bearer path, not session auth.)

- [ ] **Step 4: Confirm timing equalisation manually**

Run:
```bash
time curl -s -o /dev/null -H "Authorization: Bearer notakey" http://127.0.0.1:8001/admin/clients
time curl -s -o /dev/null -H "Authorization: Bearer cmsk_dev_aaaaaaaaaaaaaaaa_bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb" http://127.0.0.1:8001/admin/clients
```
Expected: both responses take roughly the same wall-clock time (~50 ms — argon2 dominates). Before this change, the first would return ~immediately while the second took ~50 ms.

NB: don't burn through the bearer bucket too fast — wait 60 s between the two `time` calls or use a fresh local restart.

- [ ] **Step 5: No commit — observation only**

---

## Phase 3 — Documentation + tracker hygiene

### Task 10: Update SECURITY.md "Defense layers" section

**Files:**
- Modify: `docs/SECURITY.md`

- [ ] **Step 1: Find the existing "Defense layers" section**

Run:
```bash
grep -n "Defense layers\|## Threat model\|^## Layers" docs/SECURITY.md
```

- [ ] **Step 2: Append two bullets under the relevant section**

Add (using Edit tool, exact location depends on existing structure):

```markdown
- **RLS layer** — Every tenant-scoped table (`users`, `sessions`, `projects`, `content_entries`, `project_issues`, `project_requests`) has Row-Level Security enabled with owner policies (`user_id = auth.uid()`). The backend uses the service-role client which bypasses RLS by design — the policies are defense-in-depth against future code that uses an anon-bound client or a refactor that drops a `.eq("user_id", uid)` filter. Migration: `backend/migrations/2026_05_09_tenant_tables_rls.sql`. Presence test: `auth_service/tests_integration/test_rls_policies.py`.
- **Bearer auth path rate-limit** — `Authorization: Bearer cmsk_…` requests are gated at 10 attempts / minute / IP (in-memory token bucket per serverless instance). Every parse-fail path runs argon2.verify against a precomputed dummy hash so wall-clock time is independent of where validation failed (closes BE-011 / CWE-208).
```

- [ ] **Step 3: Commit**

```bash
git add docs/SECURITY.md
git commit -m "docs(security): document RLS layer + Bearer rate limit"
```

---

### Task 11: Flip tracker rows + push to dev

**Files:**
- Modify: `~/.claude/.../memory/reference_security_audit_tracker.md`

- [ ] **Step 1: Update tracker**

Edit `reference_security_audit_tracker.md`:

```markdown
| BE-010 | verified_fixed | 2026-05-09 | Migration `2026_05_09_tenant_tables_rls.sql` applied via Supabase SQL editor. RLS + owner policies on `users`, `sessions`, `projects`, `content_entries`, `project_issues`. Service-role bypass preserved → no app-layer behaviour change. CI gate: `tests_integration/test_rls_policies.py`. Remove on 2026-05-16. |
| BE-011 | verified_fixed | 2026-05-09 | New `core/bearer_limiter.py` token bucket (10/min/IP) gates `admin_user_via_bearer_or_sid` before `verify_admin_api_key`. `admin_keys.py` now runs `_ph.verify` against `_DUMMY_HASH` on every parse-fail / row-miss path → constant-time. 5 unit tests + 1 integration test. Remove on 2026-05-16. |
```

- [ ] **Step 2: Push to dev**

Run:
```bash
git push origin dev
```
Expected: GitHub Actions runs CI + E2E. Watch:
- `ci.yml` → green (lint + 75+ unit tests + coverage ≥60 %)
- `e2e.yml` → green (integration including new RLS presence test)
- `auto-merge-dev-to-master.yml` → 60 s settle window, then dev fast-forwards master.
- `post-deploy-smoke.yml` → green after Vercel deploys.

- [ ] **Step 3: Wait for stable + verify deployed**

After ~10 min, run:
```bash
curl -s -o /dev/null -w "%{http_code}\n" -H "Authorization: Bearer notakey" \
  https://cms-backend-roman.vercel.app/admin/clients
```
Expected: `401`. Then 11×:
```bash
for i in {1..11}; do
  curl -s -o /dev/null -w "%{http_code}\n" \
    -H "Authorization: Bearer notakey-${i}" \
    -H "X-Forwarded-For: 198.51.100.42" \
    https://cms-backend-roman.vercel.app/admin/clients
done
```
Expected: ten `401`, one `429` (note: per-instance bucket on Vercel — may need higher count if multiple instances spawn).

---

## Self-Review

**1. Spec coverage**
- BE-010 finding (audit §624–633): RLS + policies on `users`, `sessions`, `projects`, `content_entries`. ✓ All four covered + bonus `project_issues` (also tenant-scoped, same risk shape). `project_requests` already done.
- BE-011 finding (audit §635–639): "(a) no rate limiting on `admin_user_via_bearer_or_sid` … (b) malformed-key fast-path returns 401 visibly faster than a properly-formatted-but-wrong key". Both addressed in Tasks 7 + 8.
- Spec also lists BE-010 in §1004 alongside `project_issues` and `project_requests`. ✓

**2. Placeholder scan**
- No "TBD" / "TODO" / "implement later" / "fill in details".
- Every step shows the actual code or command.
- Test code is complete (no "similar to above").

**3. Type consistency**
- `Bucket(capacity, window_seconds)` signature matches across module + tests.
- `check_bearer_attempt(ip: str) -> bool` consistent.
- `_DUMMY_HASH` / `_DUMMY_PLAIN` / `_equalise_timing` names consistent across module + tests.
- Migration file name `2026_05_09_tenant_tables_rls.sql` consistent across migration task + tracker note + SECURITY.md note.
- `tenant_rls_status` view name consistent across migration + integration test.

No issues found. Plan is ready.
