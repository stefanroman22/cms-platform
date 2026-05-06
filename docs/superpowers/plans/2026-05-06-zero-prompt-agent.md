# Zero-Prompt CMS Connector Agent — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the CMS Connector — Website agent runnable with zero credential prompts after a single one-time bootstrap, by adding a long-lived admin API key path to the backend, three delegation endpoints (project create / project transfer / welcome email), and a per-agent `.env` loader; then migrating the agent to consume them.

**Architecture:** Four sequential phases. Phase A adds Bearer-token admin auth alongside the existing sid-cookie path. Phase B adds three new admin endpoints behind the same auth dependency. Phase C teaches the agent to load credentials from `agents/CMS Connector - Website/.env`. Phase D refactors the agent to use the new endpoints + Bearer header, dropping its direct Resend and Supabase Management calls. Every existing capability is preserved; the dashboard never sees a behaviour change.

**Tech Stack:** FastAPI + pydantic-settings + supabase-py 2.29 (backend), argon2-cffi (password+key hashing), python-dotenv 1.x (agent), pytest + httpx (tests), Vercel + Resend (downstream services, unchanged).

**Spec reference:** `docs/superpowers/specs/2026-05-06-zero-prompt-agent-design.md` — read it for the why before touching code.

---

## File structure

| File | Phase | Type | Responsibility |
|------|-------|------|----------------|
| `backend/migrations/2026_05_06_admin_api_keys.sql` | A | NEW | Schema for the new key table |
| `backend/auth_service/services/admin_keys.py` | A | NEW | `mint_admin_api_key()`, `verify_admin_api_key()`, format constants |
| `backend/auth_service/routers/deps.py` | A | MOD | Add `admin_user_via_bearer_or_sid()` next to `require_user` |
| `backend/auth_service/routers/workspace.py` | A | MOD | Drop local `_require_admin`, import shared dep |
| `backend/auth_service/routers/publish.py` | A | MOD | Drop local `_require_admin`, import shared dep |
| `backend/auth_service/tests/test_admin_keys.py` | A | NEW | Unit tests for `verify_admin_api_key()` |
| `backend/auth_service/tests/test_admin_auth_dep.py` | A | NEW | Unit tests for `admin_user_via_bearer_or_sid()` |
| `backend/auth_service/tests_integration/test_admin_keys.py` | A | NEW | Integration: live Bearer call → 200, revoked → 401 |
| `scripts/mint_admin_api_key.py` | A | NEW | Operator CLI |
| `backend/auth_service/services/welcome_email.py` | B | NEW | Welcome HTML template |
| `backend/auth_service/routers/workspace.py` | B | MOD | Add `POST /admin/projects`, `POST /admin/projects/{slug}/transfer`, `POST /admin/clients/{email}/welcome` |
| `backend/auth_service/models/schemas.py` | B | MOD | Add `AdminProjectCreateIn`, `ProjectTransferIn`, `WelcomeEmailIn` |
| `backend/auth_service/tests/test_admin_create_project.py` | B | NEW | Unit |
| `backend/auth_service/tests/test_admin_transfer.py` | B | NEW | Unit |
| `backend/auth_service/tests/test_admin_welcome.py` | B | NEW | Unit |
| `backend/auth_service/tests_integration/test_admin_delegation.py` | B | NEW | Integration: round-trip create + transfer + welcome |
| `agents/CMS Connector - Website/.env.example` | C | NEW | Token template |
| `agents/CMS Connector - Website/requirements.txt` | C | MOD | `python-dotenv>=1.0.0` |
| `agents/CMS Connector - Website/scan.py` | C+D | MOD | `load_dotenv` at top + Bearer everywhere + new endpoints |
| `agents/CMS Connector - Website/AGENTS.md` | D | MOD | Credentials table 6 → 4 |
| `agents/CMS Connector - Website/phases/4-integration.md` | D | MOD | Replace Resend env step + project-row insert |
| `agents/CMS Connector - Website/phases/6-confirmation.md` | D | MOD | Replace Resend POST + ownership SQL |
| `agents/CMS Connector - Website/tests/test_scan_vercel_phase.py` | D | MOD | Update mocks for Bearer + new endpoints |

---

# Phase A — Backend admin API key auth

Each task ships independently. Backend is fully usable after every task. The dashboard's existing sid-cookie path keeps working because the new Bearer dep falls through to the old check when no Authorization header is sent.

## Task 1: SQL migration for `admin_api_keys`

**Files:**
- Create: `backend/migrations/2026_05_06_admin_api_keys.sql`

- [ ] **Step 1: Write the migration**

```sql
-- backend/migrations/2026_05_06_admin_api_keys.sql
-- Long-lived admin API keys. Plain key shown once at mint time;
-- only argon2 hash + lookup prefix stored. Auth dep argon2-verifies
-- against the row matched by key_prefix.

CREATE TABLE IF NOT EXISTS admin_api_keys (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id       uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  key_prefix    text NOT NULL,
  key_hash      text NOT NULL,
  name          text NOT NULL,
  scopes        jsonb NOT NULL DEFAULT '["agent"]'::jsonb,
  last_used_at  timestamptz,
  expires_at    timestamptz,
  created_at    timestamptz NOT NULL DEFAULT now(),
  revoked_at    timestamptz,
  CONSTRAINT admin_api_keys_unique_prefix UNIQUE (key_prefix)
);

CREATE INDEX IF NOT EXISTS admin_api_keys_active
  ON admin_api_keys (user_id)
  WHERE revoked_at IS NULL;
```

- [ ] **Step 2: Apply against local Supabase**

```bash
# Read SUPABASE_PAT + SUPABASE_PROJECT_REF from your shell. Use the
# Management API SQL endpoint exactly like seed_e2e.py does.
PAT="$SUPABASE_PAT"
REF="$SUPABASE_PROJECT_REF"
curl -sS -X POST "https://api.supabase.com/v1/projects/${REF}/database/query" \
  -H "Authorization: Bearer ${PAT}" \
  -H "Content-Type: application/json" \
  -d "{\"query\": $(jq -Rs . < backend/migrations/2026_05_06_admin_api_keys.sql)}"
```

Expected: `[]` returned, table created. Verify:

```bash
curl -sS -X POST "https://api.supabase.com/v1/projects/${REF}/database/query" \
  -H "Authorization: Bearer ${PAT}" \
  -H "Content-Type: application/json" \
  -d '{"query":"SELECT column_name FROM information_schema.columns WHERE table_name = '"'"'admin_api_keys'"'"' ORDER BY ordinal_position"}'
```

Expected JSON includes `id, user_id, key_prefix, key_hash, name, scopes, last_used_at, expires_at, created_at, revoked_at`.

- [ ] **Step 3: Commit**

```bash
git add backend/migrations/2026_05_06_admin_api_keys.sql
git commit -m "build(migrations): admin_api_keys table for long-lived Bearer auth"
```

## Task 2: `verify_admin_api_key()` service

**Files:**
- Create: `backend/auth_service/services/admin_keys.py`
- Create: `backend/auth_service/tests/test_admin_keys.py`

- [ ] **Step 1: Write the failing tests**

`backend/auth_service/tests/test_admin_keys.py`:

```python
"""Unit tests for admin_keys service.

Mocked Supabase client; no network. Verifies the parse-then-argon2
flow plus the negative paths (expired, revoked, wrong secret, malformed,
inactive user).
"""
from unittest.mock import MagicMock, patch

import pytest
from argon2 import PasswordHasher

from auth_service.services import admin_keys

ph = PasswordHasher(time_cost=3, memory_cost=65536, parallelism=4)


def _row(*, key_prefix, key_hash, expires_at=None, revoked_at=None,
         is_admin=True, is_active=True):
    return {
        "id": "row-1",
        "user_id": "user-1",
        "key_prefix": key_prefix,
        "key_hash": key_hash,
        "expires_at": expires_at,
        "revoked_at": revoked_at,
        "scopes": ["agent"],
        "users": {
            "email": "admin@example.com",
            "is_admin": is_admin,
            "is_active": is_active,
        },
    }


@pytest.fixture
def mock_admin_sb():
    """Patches get_supabase_admin to return a chainable mock."""
    with patch.object(admin_keys, "get_supabase_admin") as factory:
        sb = MagicMock()
        for m in ["table", "select", "eq", "is_", "maybe_single", "update"]:
            getattr(sb, m).return_value = sb
        factory.return_value = sb
        yield sb


def test_returns_user_for_valid_key(mock_admin_sb):
    secret = "z" * 32
    row = _row(key_prefix="abcdefghijklmnop", key_hash=ph.hash(secret))
    mock_admin_sb.execute.return_value = MagicMock(data=row)

    user = admin_keys.verify_admin_api_key(f"cmsk_dev_abcdefghijklmnop_{secret}")
    assert user is not None
    assert user["id"] == "user-1"
    assert user["email"] == "admin@example.com"


def test_returns_none_for_unknown_lookup_prefix(mock_admin_sb):
    mock_admin_sb.execute.return_value = MagicMock(data=None)
    assert admin_keys.verify_admin_api_key("cmsk_dev_aaaaaaaaaaaaaaaa_zzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzz") is None


def test_returns_none_for_wrong_secret(mock_admin_sb):
    row = _row(key_prefix="abcdefghijklmnop", key_hash=ph.hash("correct" * 5))
    mock_admin_sb.execute.return_value = MagicMock(data=row)
    assert admin_keys.verify_admin_api_key("cmsk_dev_abcdefghijklmnop_" + "wrong" * 7) is None


def test_returns_none_for_expired_key(mock_admin_sb):
    row = _row(
        key_prefix="abcdefghijklmnop",
        key_hash=ph.hash("z" * 32),
        expires_at="2020-01-01T00:00:00+00:00",
    )
    mock_admin_sb.execute.return_value = MagicMock(data=row)
    assert admin_keys.verify_admin_api_key(f"cmsk_dev_abcdefghijklmnop_{'z' * 32}") is None


def test_returns_none_for_inactive_admin(mock_admin_sb):
    row = _row(key_prefix="abcdefghijklmnop", key_hash=ph.hash("z" * 32), is_active=False)
    mock_admin_sb.execute.return_value = MagicMock(data=row)
    assert admin_keys.verify_admin_api_key(f"cmsk_dev_abcdefghijklmnop_{'z' * 32}") is None


def test_returns_none_for_non_admin(mock_admin_sb):
    row = _row(key_prefix="abcdefghijklmnop", key_hash=ph.hash("z" * 32), is_admin=False)
    mock_admin_sb.execute.return_value = MagicMock(data=row)
    assert admin_keys.verify_admin_api_key(f"cmsk_dev_abcdefghijklmnop_{'z' * 32}") is None


def test_returns_none_for_malformed_key(mock_admin_sb):
    for bad in ["", "cmsk_only_three_parts", "notcmsk_dev_aaa_bbb", "cmsk_unknown_aaa_bbb"]:
        assert admin_keys.verify_admin_api_key(bad) is None
    mock_admin_sb.execute.assert_not_called()


def test_mint_returns_plain_key_with_correct_format(mock_admin_sb):
    mock_admin_sb.execute.return_value = MagicMock(data={"id": "row-2"})
    plain, row_id = admin_keys.mint_admin_api_key(
        user_id="user-1", name="agent", env="dev", expires_at=None,
    )
    assert plain.startswith("cmsk_dev_")
    parts = plain.split("_")
    assert len(parts) == 4
    assert len(parts[2]) == 16            # lookup
    assert len(parts[3]) >= 32            # secret
    assert row_id == "row-2"
```

- [ ] **Step 2: Run tests, expect failure**

```bash
cd backend
SUPABASE_URL=https://example.supabase.co SUPABASE_ANON_KEY=dummy \
SUPABASE_SERVICE_ROLE=dummy ENVIRONMENT=development \
RESEND_API_KEY=dummy RESEND_FROM_EMAIL=noreply@example.com \
venv/Scripts/python.exe -m pytest auth_service/tests/test_admin_keys.py -v
```
Expected: ImportError (`No module named admin_keys`).

- [ ] **Step 3: Implement the service**

`backend/auth_service/services/admin_keys.py`:

```python
"""Admin API key minting and verification.

Key format: cmsk_<env>_<lookup>_<secret>
- env: "dev" or "prod" (informational)
- lookup: 16 base64url chars, stored as key_prefix for fast row lookup
- secret: 32 base64url chars, argon2-hashed at rest

The verifier parses the lookup half, fetches the single matching row,
and argon2-verifies the secret half against key_hash. Constant cost
per request regardless of how many keys exist.
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
    lookup = secrets.token_urlsafe(12)[:KEY_PREFIX_LEN]
    secret = secrets.token_urlsafe(24)[:SECRET_LEN_TARGET]
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
    non-revoked admin key. Updates last_used_at on success."""
    parts = plain_key.split("_") if plain_key else []
    if len(parts) != 4 or parts[0] != "cmsk" or parts[1] not in {"dev", "prod"}:
        return None
    lookup, secret = parts[2], parts[3]
    if len(lookup) != KEY_PREFIX_LEN:
        return None

    sb = get_supabase_admin()
    res = (
        sb.table("admin_api_keys")
        .select(
            "id, user_id, key_hash, expires_at, scopes, "
            "users(email, is_admin, is_active)"
        )
        .eq("key_prefix", lookup)
        .is_("revoked_at", "null")
        .maybe_single()
        .execute()
    )
    row = res.data if res else None
    if not row:
        return None

    if row.get("expires_at") and row["expires_at"] <= _now_iso():
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

- [ ] **Step 4: Run tests, expect pass**

Same command as Step 2. Expected: 8 passed.

- [ ] **Step 5: Lint**

```bash
backend/venv/Scripts/python.exe -m ruff check backend/auth_service/services/admin_keys.py backend/auth_service/tests/test_admin_keys.py
backend/venv/Scripts/python.exe -m black --check backend/auth_service/services/admin_keys.py backend/auth_service/tests/test_admin_keys.py
```
Expected: clean.

- [ ] **Step 6: Commit**

```bash
git add backend/auth_service/services/admin_keys.py backend/auth_service/tests/test_admin_keys.py
git commit -m "feat(auth): admin API key service with prefix-indexed argon2 verify"
```

## Task 3: shared admin auth dep + workspace/publish refactor

**Files:**
- Modify: `backend/auth_service/routers/deps.py`
- Modify: `backend/auth_service/routers/workspace.py:60` (drop local `_require_admin`)
- Modify: `backend/auth_service/routers/publish.py:177` (drop local `_require_admin`)
- Create: `backend/auth_service/tests/test_admin_auth_dep.py`

- [ ] **Step 1: Write the failing tests for the new dep**

`backend/auth_service/tests/test_admin_auth_dep.py`:

```python
"""Unit tests for admin_user_via_bearer_or_sid.

Three fork points: Bearer present + valid → return user.
Bearer present + invalid → 401. No Bearer → fall through to sid path.
"""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from auth_service.routers import deps


def _request(headers: dict | None = None, cookies: dict | None = None):
    req = MagicMock()
    req.headers = headers or {}
    req.cookies = cookies or {}
    return req


@pytest.mark.asyncio
async def test_bearer_valid_returns_user():
    with patch.object(deps, "verify_admin_api_key", return_value={
        "id": "u1", "email": "a@b", "is_admin": True, "is_active": True
    }):
        user = await deps.admin_user_via_bearer_or_sid(
            _request(headers={"authorization": "Bearer cmsk_dev_xx_yy"})
        )
        assert user["id"] == "u1"


@pytest.mark.asyncio
async def test_bearer_invalid_raises_401():
    with patch.object(deps, "verify_admin_api_key", return_value=None):
        with pytest.raises(HTTPException) as exc:
            await deps.admin_user_via_bearer_or_sid(
                _request(headers={"authorization": "Bearer cmsk_dev_xx_yy"})
            )
        assert exc.value.status_code == 401


@pytest.mark.asyncio
async def test_no_bearer_falls_through_to_sid_admin():
    fake_user = MagicMock(id="u2", is_admin=True)
    with patch.object(deps, "require_user", new=AsyncMock(return_value=fake_user)):
        user = await deps.admin_user_via_bearer_or_sid(
            _request(cookies={"sid": "sess123"})
        )
        assert user is fake_user


@pytest.mark.asyncio
async def test_no_bearer_non_admin_raises_403():
    fake_user = MagicMock(id="u3", is_admin=False)
    with patch.object(deps, "require_user", new=AsyncMock(return_value=fake_user)):
        with pytest.raises(HTTPException) as exc:
            await deps.admin_user_via_bearer_or_sid(
                _request(cookies={"sid": "sess123"})
            )
        assert exc.value.status_code == 403
```

- [ ] **Step 2: Run, expect failure**

```bash
cd backend
SUPABASE_URL=https://example.supabase.co SUPABASE_ANON_KEY=dummy \
SUPABASE_SERVICE_ROLE=dummy ENVIRONMENT=development \
RESEND_API_KEY=dummy RESEND_FROM_EMAIL=noreply@example.com \
venv/Scripts/python.exe -m pytest auth_service/tests/test_admin_auth_dep.py -v
```
Expected: AttributeError (`module 'deps' has no attribute 'admin_user_via_bearer_or_sid'`).

- [ ] **Step 3: Add the new dep to `deps.py`**

Append to `backend/auth_service/routers/deps.py` (keep existing
`require_user` + `require_project_access` untouched):

```python
from fastapi import HTTPException, Request, status
from ..services.admin_keys import verify_admin_api_key
# (existing imports stay)


async def admin_user_via_bearer_or_sid(request: Request):
    """Auth dep used by every admin route.

    Accepts EITHER an `Authorization: Bearer cmsk_…` header (agent path)
    OR a `sid` cookie (dashboard path). Bearer wins if both are sent.
    Falls through to `require_user` for the cookie path so the existing
    session-validation logic keeps applying unchanged.
    """
    auth_header = request.headers.get("authorization", "")
    if auth_header.lower().startswith("bearer "):
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

- [ ] **Step 4: Run tests, expect pass**

Same command. Expected: 4 passed.

- [ ] **Step 5: Swap workspace.py to use the shared dep**

In `backend/auth_service/routers/workspace.py`:

1. Import: at the top, replace
   ```python
   from .deps import require_project_access, require_user
   ```
   with
   ```python
   from .deps import admin_user_via_bearer_or_sid, require_project_access, require_user
   ```

2. Delete the local `_require_admin` at lines 60–64:
   ```python
   async def _require_admin(request: Request) -> UserOut:
       user = await require_user(request)
       if not user.is_admin:
           raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
       return user
   ```

3. Replace every `await _require_admin(request)` (lines 280, 361, 372,
   402, 420, 434, 459, 473, 497, 527, 556) with
   `await admin_user_via_bearer_or_sid(request)`. Same call shape, same
   return type when called via the cookie path.

- [ ] **Step 6: Swap publish.py to use the shared dep**

In `backend/auth_service/routers/publish.py`:

1. Import: add
   ```python
   from .deps import admin_user_via_bearer_or_sid
   ```

2. Delete the local `_require_admin` at lines 177–183.

3. Replace `await _require_admin(request)` at line 188 with
   `await admin_user_via_bearer_or_sid(request)`.

- [ ] **Step 7: Run full unit suite to confirm no regression**

```bash
cd backend
SUPABASE_URL=https://example.supabase.co SUPABASE_ANON_KEY=dummy \
SUPABASE_SERVICE_ROLE=dummy ENVIRONMENT=development \
RESEND_API_KEY=dummy RESEND_FROM_EMAIL=noreply@example.com \
venv/Scripts/python.exe -m pytest auth_service/tests/ -q
```
Expected: all green (existing 52 + new tests).

- [ ] **Step 8: Lint**

```bash
backend/venv/Scripts/python.exe -m ruff check backend/auth_service/routers/deps.py backend/auth_service/routers/workspace.py backend/auth_service/routers/publish.py backend/auth_service/tests/test_admin_auth_dep.py
backend/venv/Scripts/python.exe -m black --check backend/auth_service/routers/deps.py backend/auth_service/routers/workspace.py backend/auth_service/routers/publish.py backend/auth_service/tests/test_admin_auth_dep.py
```
Expected: clean.

- [ ] **Step 9: Commit**

```bash
git add backend/auth_service/routers/deps.py backend/auth_service/routers/workspace.py backend/auth_service/routers/publish.py backend/auth_service/tests/test_admin_auth_dep.py
git commit -m "feat(auth): admin_user_via_bearer_or_sid dep — Bearer or sid, dedup _require_admin"
```

## Task 4: Bootstrap script `scripts/mint_admin_api_key.py`

**Files:**
- Create: `scripts/mint_admin_api_key.py`

- [ ] **Step 1: Write the script**

```python
"""mint_admin_api_key.py — interactive operator script.

Mints a new admin API key for an existing admin user and prints it
ONCE. Operator copies it into the agent's .env immediately. Lost = mint
a new one.

Required env (read from your shell, NOT from the script):
  SUPABASE_URL                  https://<ref>.supabase.co
  SUPABASE_SERVICE_ROLE_KEY     sb_secret_*

Run:
    python scripts/mint_admin_api_key.py
"""
from __future__ import annotations

import os
import sys
from datetime import UTC, datetime, timedelta

# Make backend modules importable.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from auth_service.services.admin_keys import mint_admin_api_key  # noqa: E402
from auth_service.services.supabase_client import get_supabase_admin  # noqa: E402


def main() -> int:
    # Sanity: the supabase_client module reads env at import time.
    if not os.environ.get("SUPABASE_URL") or not os.environ.get("SUPABASE_SERVICE_ROLE_KEY"):
        print("error: set SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY first.", file=sys.stderr)
        return 1

    email = input("Admin email: ").strip().lower()
    name = input("Key name (e.g. cms-connector-agent): ").strip() or "unnamed"
    env_tier = input("Env tier [dev/prod, default dev]: ").strip() or "dev"
    if env_tier not in {"dev", "prod"}:
        print(f"error: env tier must be dev or prod, got {env_tier!r}", file=sys.stderr)
        return 1
    expiry_choice = input("Expires in days [blank=never, 90, 180, 365]: ").strip()
    expires_at = None
    if expiry_choice:
        try:
            days = int(expiry_choice)
        except ValueError:
            print("error: expiry must be a number of days", file=sys.stderr)
            return 1
        expires_at = (datetime.now(UTC) + timedelta(days=days)).isoformat()

    sb = get_supabase_admin()
    res = (
        sb.table("users")
        .select("id, email, is_admin")
        .eq("email", email)
        .eq("is_admin", True)
        .maybe_single()
        .execute()
    )
    user = res.data if res else None
    if not user:
        print(f"error: no admin user with email {email!r}", file=sys.stderr)
        return 1

    plain, row_id = mint_admin_api_key(
        user_id=user["id"], name=name, env=env_tier, expires_at=expires_at,
    )

    print()
    print("=" * 64)
    print("  COPY THIS KEY NOW — it will not be shown again:")
    print()
    print(f"    {plain}")
    print()
    print(f"  Owner: {email}    Name: {name}    Row id: {row_id}")
    if expires_at:
        print(f"  Expires: {expires_at}")
    print("=" * 64)
    print()
    print("Paste into agents/CMS Connector - Website/.env as:")
    print(f"    CMS_ADMIN_API_KEY={plain}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: Static check**

```bash
python -c "import ast; ast.parse(open('scripts/mint_admin_api_key.py').read())"
backend/venv/Scripts/python.exe -m ruff check scripts/mint_admin_api_key.py
backend/venv/Scripts/python.exe -m black --check scripts/mint_admin_api_key.py
```
Expected: clean.

- [ ] **Step 3: Commit**

```bash
git add scripts/mint_admin_api_key.py
git commit -m "build(scripts): mint_admin_api_key.py operator bootstrap"
```

## Task 5: Integration tests for Bearer auth (Phase A verification)

**Files:**
- Create: `backend/auth_service/tests_integration/test_admin_keys.py`

- [ ] **Step 1: Add integration test**

`backend/auth_service/tests_integration/test_admin_keys.py`:

```python
"""Integration tests against the deployed backend for the admin Bearer
auth path. Gated by E2E_ADMIN_API_KEY (a real key minted from prod
Supabase, stored as a GitHub Actions secret)."""
import os
import pytest
import httpx

pytestmark = pytest.mark.integration

BACKEND_URL = os.environ.get("E2E_BASE_URL_BACKEND", "https://cms-backend-roman.vercel.app")
ADMIN_KEY = os.environ.get("E2E_ADMIN_API_KEY")

skip_if_no_key = pytest.mark.skipif(
    not ADMIN_KEY,
    reason="E2E_ADMIN_API_KEY not set; mint one and set the secret",
)


@skip_if_no_key
def test_bearer_admin_lists_projects():
    r = httpx.get(
        f"{BACKEND_URL}/admin/projects",
        headers={"Authorization": f"Bearer {ADMIN_KEY}"},
        timeout=15.0,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert isinstance(body, list)
    slugs = {p["slug"] for p in body}
    assert "e2e-test-project" in slugs


@skip_if_no_key
def test_bad_bearer_returns_401():
    r = httpx.get(
        f"{BACKEND_URL}/admin/projects",
        headers={"Authorization": "Bearer cmsk_dev_aaaaaaaaaaaaaaaa_zzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzz"},
        timeout=15.0,
    )
    assert r.status_code == 401


def test_no_auth_returns_401():
    r = httpx.get(f"{BACKEND_URL}/admin/projects", timeout=15.0)
    assert r.status_code == 401
```

- [ ] **Step 2: Local manual smoke**

```bash
# Mint a key against your local Supabase
export SUPABASE_URL=https://xeluydwpgiddbamysgyu.supabase.co
export SUPABASE_SERVICE_ROLE_KEY=$(grep SUPABASE_SERVICE_ROLE_KEY backend/.env | cut -d= -f2)
python scripts/mint_admin_api_key.py
# (paste your admin email, name "local-smoke", env "dev")

# Start local backend
cd backend && venv/Scripts/python.exe -m uvicorn auth_service.main:app --port 8001 &

# Probe
curl -s -H "Authorization: Bearer cmsk_dev_<your-key>" http://localhost:8001/admin/projects | head -c 200
```
Expected: JSON list of projects.

- [ ] **Step 3: Production manual smoke**

After Phase A is deployed (push dev → master via existing scheduled-merge):

```bash
# Mint a prod key
export SUPABASE_URL=https://xeluydwpgiddbamysgyu.supabase.co
export SUPABASE_SERVICE_ROLE_KEY=<copied from Vercel env>
python scripts/mint_admin_api_key.py
# (env "prod")

# Add as GH Actions secret named E2E_ADMIN_API_KEY for the integration tests above

# Curl prod
curl -s -H "Authorization: Bearer cmsk_prod_<your-key>" \
  https://cms-backend-roman.vercel.app/admin/projects | head -c 200
```
Expected: JSON list of projects.

- [ ] **Step 4: Commit**

```bash
git add backend/auth_service/tests_integration/test_admin_keys.py
git commit -m "test(integration): admin Bearer auth — valid + bad + missing"
```

---

# Phase B — Backend delegation endpoints

Each endpoint is one TDD task. They all use the dep from Phase A.

## Task 6: Welcome email template

**Files:**
- Create: `backend/auth_service/services/welcome_email.py`

- [ ] **Step 1: Move the template from the agent doc into a Python module**

`backend/auth_service/services/welcome_email.py`:

```python
"""Welcome email template + Resend POST helper.

Source of truth for the HTML that lands in a new client's inbox after
the CMS Connector agent finishes provisioning. Lives next to the code
that sends it (was previously in agents/CMS Connector - Website/phases/
6-confirmation.md).
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request

from ..core.config import settings


def render_welcome_html(
    *, full_name: str, project_name: str, website_url: str, login_url: str
) -> str:
    """Renders the welcome HTML. Inline styles only — most email clients
    strip <style>. Plain HTML, no JS, no remote fonts."""
    greeting = full_name or "there"
    return f"""<!doctype html><html><body style="font-family:system-ui,-apple-system,sans-serif;color:#1f2937;line-height:1.6;max-width:560px;margin:0 auto;padding:24px">
<h1 style="font-size:20px;margin:0 0 16px">Welcome to Roman Technologies CMS</h1>
<p>Hi {greeting},</p>
<p>Your project <strong>{project_name}</strong> is live on <a href="{website_url}" style="color:#0369a1">{website_url}</a> and ready for content edits.</p>
<p style="margin:24px 0"><a href="{login_url}" style="background:#111827;color:white;padding:10px 18px;border-radius:8px;text-decoration:none;display:inline-block">Open the CMS dashboard →</a></p>
<p>You can sign in with the email address this message was sent to. Use the password your developer shared with you, then change it from the Account Settings page.</p>
<p style="font-size:13px;color:#6b7280;margin-top:32px">Roman Technologies — stefanromanpers@gmail.com</p>
</body></html>"""


def send_welcome_email(
    *,
    to_email: str,
    full_name: str | None,
    project_name: str,
    website_url: str,
    login_url: str = "https://roman-technologies.dev/log-in",
) -> dict:
    """POSTs to api.resend.com/emails. Returns parsed JSON on 200,
    raises RuntimeError with status + body on any other status."""
    if not settings.RESEND_API_KEY:
        raise RuntimeError("RESEND_API_KEY not configured on this backend")

    body = {
        "from": f"{settings.RESEND_FROM_NAME} <{settings.RESEND_FROM_EMAIL}>",
        "to": to_email,
        "subject": f"Your {project_name} CMS is ready",
        "html": render_welcome_html(
            full_name=full_name or "",
            project_name=project_name,
            website_url=website_url,
            login_url=login_url,
        ),
    }
    req = urllib.request.Request(
        "https://api.resend.com/emails",
        data=json.dumps(body).encode(),
        headers={
            "Authorization": f"Bearer {settings.RESEND_API_KEY}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode() or "{}")
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"Resend {e.code}: {e.read().decode()}") from e
```

- [ ] **Step 2: Lint + commit**

```bash
backend/venv/Scripts/python.exe -m ruff check backend/auth_service/services/welcome_email.py
backend/venv/Scripts/python.exe -m black --check backend/auth_service/services/welcome_email.py
git add backend/auth_service/services/welcome_email.py
git commit -m "feat(welcome): HTML template + Resend POST helper (moved from agent docs)"
```

## Task 7: `POST /admin/projects` — create project row

**Files:**
- Modify: `backend/auth_service/models/schemas.py` (add `AdminProjectCreateIn`)
- Modify: `backend/auth_service/routers/workspace.py` (add endpoint)
- Create: `backend/auth_service/tests/test_admin_create_project.py`

- [ ] **Step 1: Write the failing test**

`backend/auth_service/tests/test_admin_create_project.py`:

```python
"""Unit tests for POST /admin/projects."""
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from auth_service.main import app


@pytest.fixture
def admin_user():
    return {"id": "admin-1", "email": "admin@example.com", "is_admin": True, "is_active": True}


@pytest.fixture
def client_with_admin(admin_user):
    from auth_service.routers import deps

    async def fake_dep(request):  # noqa: ARG001
        return admin_user

    app.dependency_overrides[deps.admin_user_via_bearer_or_sid] = fake_dep
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_creates_project_row_when_owner_exists(client_with_admin):
    with patch("auth_service.routers.workspace.get_supabase") as mock_sb:
        sb = mock_sb.return_value
        sb.table.return_value = sb
        sb.select.return_value = sb
        sb.eq.return_value = sb
        sb.maybe_single.return_value = sb
        sb.insert.return_value = sb
        # owner lookup returns user
        sb.execute.side_effect = [
            type("R", (), {"data": {"id": "owner-1", "email": "c@e"}})(),
            # slug uniqueness check returns None
            type("R", (), {"data": None})(),
            # insert returns row
            type("R", (), {"data": [{"id": "p1", "slug": "demo", "name": "Demo"}]})(),
        ]
        resp = client_with_admin.post(
            "/admin/projects",
            json={"slug": "demo", "name": "Demo", "owner_email": "c@e"},
        )
        assert resp.status_code == 201, resp.text
        assert resp.json()["slug"] == "demo"


def test_returns_404_when_owner_missing(client_with_admin):
    with patch("auth_service.routers.workspace.get_supabase") as mock_sb:
        sb = mock_sb.return_value
        sb.table.return_value = sb
        sb.select.return_value = sb
        sb.eq.return_value = sb
        sb.maybe_single.return_value = sb
        sb.execute.return_value = type("R", (), {"data": None})()
        resp = client_with_admin.post(
            "/admin/projects",
            json={"slug": "demo", "name": "Demo", "owner_email": "missing@e"},
        )
        assert resp.status_code == 404


def test_returns_409_when_slug_exists(client_with_admin):
    with patch("auth_service.routers.workspace.get_supabase") as mock_sb:
        sb = mock_sb.return_value
        sb.table.return_value = sb
        sb.select.return_value = sb
        sb.eq.return_value = sb
        sb.maybe_single.return_value = sb
        sb.execute.side_effect = [
            type("R", (), {"data": {"id": "owner-1"}})(),
            type("R", (), {"data": {"id": "p-existing", "slug": "demo"}})(),
        ]
        resp = client_with_admin.post(
            "/admin/projects",
            json={"slug": "demo", "name": "Demo", "owner_email": "c@e"},
        )
        assert resp.status_code == 409
```

- [ ] **Step 2: Run, expect failure**

```bash
cd backend
SUPABASE_URL=https://example.supabase.co SUPABASE_ANON_KEY=dummy \
SUPABASE_SERVICE_ROLE=dummy ENVIRONMENT=development \
RESEND_API_KEY=dummy RESEND_FROM_EMAIL=noreply@example.com \
venv/Scripts/python.exe -m pytest auth_service/tests/test_admin_create_project.py -v
```
Expected: FAIL — endpoint not implemented (404 from FastAPI).

- [ ] **Step 3: Add the schema model**

In `backend/auth_service/models/schemas.py`, add (next to existing
`AdminProjectPatchIn`):

```python
class AdminProjectCreateIn(BaseModel):
    slug: str
    name: str
    owner_email: EmailStr
    github_repo: str | None = None
```

- [ ] **Step 4: Add the endpoint**

In `backend/auth_service/routers/workspace.py`, after the existing
`admin_patch_project` (around line 432), add:

```python
@router.post("/admin/projects", status_code=status.HTTP_201_CREATED)
async def admin_create_project(body: AdminProjectCreateIn, request: Request):
    await admin_user_via_bearer_or_sid(request)
    sb = get_supabase()

    owner = (
        sb.table("users")
        .select("id, email")
        .eq("email", body.owner_email.lower().strip())
        .maybe_single()
        .execute()
    )
    if not (owner and owner.data):
        raise HTTPException(404, f"No user with email {body.owner_email!r}")

    existing = (
        sb.table("projects")
        .select("id, slug")
        .eq("slug", body.slug)
        .maybe_single()
        .execute()
    )
    if existing and existing.data:
        raise HTTPException(409, f"Project slug {body.slug!r} already exists")

    inserted = (
        sb.table("projects")
        .insert(
            {
                "user_id": owner.data["id"],
                "slug": body.slug,
                "name": body.name,
                "is_active": True,
                "github_repo": body.github_repo,
                "created_at": datetime.now(UTC).isoformat(),
            }
        )
        .execute()
    )
    return inserted.data[0] if inserted.data else {}
```

Make sure `AdminProjectCreateIn` is in the schemas-import block at
the top of the file.

- [ ] **Step 5: Run, expect pass**

Same command. Expected: 3 passed.

- [ ] **Step 6: Lint + commit**

```bash
backend/venv/Scripts/python.exe -m ruff check backend/auth_service/routers/workspace.py backend/auth_service/models/schemas.py backend/auth_service/tests/test_admin_create_project.py
backend/venv/Scripts/python.exe -m black --check backend/auth_service/routers/workspace.py backend/auth_service/models/schemas.py backend/auth_service/tests/test_admin_create_project.py
git add backend/auth_service/routers/workspace.py backend/auth_service/models/schemas.py backend/auth_service/tests/test_admin_create_project.py
git commit -m "feat(admin): POST /admin/projects creates project row"
```

## Task 8: `POST /admin/projects/{slug}/transfer`

**Files:**
- Modify: `backend/auth_service/models/schemas.py` (add `ProjectTransferIn`)
- Modify: `backend/auth_service/routers/workspace.py` (add endpoint)
- Create: `backend/auth_service/tests/test_admin_transfer.py`

- [ ] **Step 1: Write the failing test**

`backend/auth_service/tests/test_admin_transfer.py`:

```python
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from auth_service.main import app


@pytest.fixture
def client_with_admin():
    from auth_service.routers import deps

    async def fake_dep(request):  # noqa: ARG001
        return {"id": "admin-1", "is_admin": True}

    app.dependency_overrides[deps.admin_user_via_bearer_or_sid] = fake_dep
    yield TestClient(app)
    app.dependency_overrides.clear()


def _r(data):
    return type("R", (), {"data": data})()


def test_transfers_ownership(client_with_admin):
    with patch("auth_service.routers.workspace.get_supabase") as mock_sb:
        sb = mock_sb.return_value
        sb.table.return_value = sb
        sb.select.return_value = sb
        sb.eq.return_value = sb
        sb.maybe_single.return_value = sb
        sb.update.return_value = sb
        sb.execute.side_effect = [
            _r({"id": "newowner-1", "email": "new@x"}),       # target user
            _r([{"id": "p1", "slug": "demo", "user_id": "newowner-1"}]),  # update
        ]
        resp = client_with_admin.post(
            "/admin/projects/demo/transfer",
            json={"to_user_email": "new@x"},
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["user_id"] == "newowner-1"


def test_404_when_target_user_missing(client_with_admin):
    with patch("auth_service.routers.workspace.get_supabase") as mock_sb:
        sb = mock_sb.return_value
        sb.table.return_value = sb
        sb.select.return_value = sb
        sb.eq.return_value = sb
        sb.maybe_single.return_value = sb
        sb.execute.return_value = _r(None)
        resp = client_with_admin.post(
            "/admin/projects/demo/transfer",
            json={"to_user_email": "nobody@x"},
        )
        assert resp.status_code == 404
```

- [ ] **Step 2: Run, expect failure**

```bash
cd backend
venv/Scripts/python.exe -m pytest auth_service/tests/test_admin_transfer.py -v
```
Expected: FAIL — endpoint not implemented.

- [ ] **Step 3: Add the schema + endpoint**

`models/schemas.py` add:

```python
class ProjectTransferIn(BaseModel):
    to_user_email: EmailStr
```

`routers/workspace.py` after `admin_create_project`:

```python
@router.post("/admin/projects/{project_slug}/transfer")
async def admin_transfer_project(project_slug: str, body: ProjectTransferIn, request: Request):
    await admin_user_via_bearer_or_sid(request)
    sb = get_supabase()
    target = (
        sb.table("users")
        .select("id, email")
        .eq("email", body.to_user_email.lower().strip())
        .maybe_single()
        .execute()
    )
    if not (target and target.data):
        raise HTTPException(404, f"No user with email {body.to_user_email!r}")
    updated = (
        sb.table("projects")
        .update({
            "user_id": target.data["id"],
            "updated_at": datetime.now(UTC).isoformat(),
        })
        .eq("slug", project_slug)
        .execute()
    )
    if not updated.data:
        raise HTTPException(404, f"No project with slug {project_slug!r}")
    return updated.data[0]
```

- [ ] **Step 4: Run + lint + commit**

```bash
venv/Scripts/python.exe -m pytest auth_service/tests/test_admin_transfer.py -v
backend/venv/Scripts/python.exe -m ruff check backend/auth_service/routers/workspace.py backend/auth_service/tests/test_admin_transfer.py
backend/venv/Scripts/python.exe -m black --check backend/auth_service/routers/workspace.py backend/auth_service/tests/test_admin_transfer.py
git add backend/auth_service/routers/workspace.py backend/auth_service/models/schemas.py backend/auth_service/tests/test_admin_transfer.py
git commit -m "feat(admin): POST /admin/projects/{slug}/transfer changes user_id"
```

## Task 9: `POST /admin/clients/{email}/welcome`

**Files:**
- Modify: `backend/auth_service/models/schemas.py` (add `WelcomeEmailIn`)
- Modify: `backend/auth_service/routers/workspace.py` (add endpoint)
- Create: `backend/auth_service/tests/test_admin_welcome.py`

- [ ] **Step 1: Write the failing test**

`backend/auth_service/tests/test_admin_welcome.py`:

```python
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from auth_service.main import app


@pytest.fixture
def client_with_admin():
    from auth_service.routers import deps

    async def fake_dep(request):  # noqa: ARG001
        return {"id": "admin-1", "is_admin": True}

    app.dependency_overrides[deps.admin_user_via_bearer_or_sid] = fake_dep
    yield TestClient(app)
    app.dependency_overrides.clear()


def _r(data):
    return type("R", (), {"data": data})()


def test_sends_welcome_when_user_exists(client_with_admin):
    with patch("auth_service.routers.workspace.get_supabase") as mock_sb, \
         patch("auth_service.routers.workspace.send_welcome_email") as mock_send:
        sb = mock_sb.return_value
        sb.table.return_value = sb
        sb.select.return_value = sb
        sb.eq.return_value = sb
        sb.maybe_single.return_value = sb
        sb.execute.return_value = _r({"id": "u-1", "email": "c@e", "full_name": "Client"})
        mock_send.return_value = {"id": "resend_abc"}

        resp = client_with_admin.post(
            "/admin/clients/c@e/welcome",
            json={
                "project_slug": "demo",
                "project_name": "Demo Site",
                "website_url": "https://demo.example.com",
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["resend_id"] == "resend_abc"


def test_returns_404_when_user_missing(client_with_admin):
    with patch("auth_service.routers.workspace.get_supabase") as mock_sb:
        sb = mock_sb.return_value
        sb.table.return_value = sb
        sb.select.return_value = sb
        sb.eq.return_value = sb
        sb.maybe_single.return_value = sb
        sb.execute.return_value = _r(None)
        resp = client_with_admin.post(
            "/admin/clients/missing@e/welcome",
            json={"project_slug": "demo", "project_name": "Demo", "website_url": "https://x"},
        )
        assert resp.status_code == 404


def test_returns_502_on_resend_failure(client_with_admin):
    with patch("auth_service.routers.workspace.get_supabase") as mock_sb, \
         patch("auth_service.routers.workspace.send_welcome_email") as mock_send:
        sb = mock_sb.return_value
        sb.table.return_value = sb
        sb.select.return_value = sb
        sb.eq.return_value = sb
        sb.maybe_single.return_value = sb
        sb.execute.return_value = _r({"id": "u-1", "email": "c@e", "full_name": "Client"})
        mock_send.side_effect = RuntimeError("Resend 422: bad domain")

        resp = client_with_admin.post(
            "/admin/clients/c@e/welcome",
            json={"project_slug": "demo", "project_name": "Demo", "website_url": "https://x"},
        )
        assert resp.status_code == 502
        assert "Resend" in resp.json()["detail"]
```

- [ ] **Step 2: Run, expect failure**

Same command. Expected: FAIL.

- [ ] **Step 3: Add schema + endpoint**

`models/schemas.py`:
```python
class WelcomeEmailIn(BaseModel):
    project_slug: str
    project_name: str
    website_url: str
```

`routers/workspace.py` (top-of-file add `from ..services.welcome_email import send_welcome_email`), then after `admin_transfer_project`:

```python
@router.post("/admin/clients/{email}/welcome")
async def admin_send_welcome(email: str, body: WelcomeEmailIn, request: Request):
    await admin_user_via_bearer_or_sid(request)
    sb = get_supabase()
    user = (
        sb.table("users")
        .select("id, email, full_name")
        .eq("email", email.lower().strip())
        .maybe_single()
        .execute()
    )
    if not (user and user.data):
        raise HTTPException(404, f"No user with email {email!r}")
    try:
        result = send_welcome_email(
            to_email=user.data["email"],
            full_name=user.data.get("full_name"),
            project_name=body.project_name,
            website_url=body.website_url,
        )
    except RuntimeError as e:
        raise HTTPException(502, f"Resend send failed: {e}") from e
    return {"success": True, "resend_id": result.get("id")}
```

- [ ] **Step 4: Run + lint + commit**

```bash
venv/Scripts/python.exe -m pytest auth_service/tests/test_admin_welcome.py -v
backend/venv/Scripts/python.exe -m ruff check backend/auth_service/routers/workspace.py backend/auth_service/services/welcome_email.py backend/auth_service/tests/test_admin_welcome.py
backend/venv/Scripts/python.exe -m black --check backend/auth_service/routers/workspace.py backend/auth_service/services/welcome_email.py backend/auth_service/tests/test_admin_welcome.py
git add backend/auth_service/routers/workspace.py backend/auth_service/models/schemas.py backend/auth_service/tests/test_admin_welcome.py
git commit -m "feat(admin): POST /admin/clients/{email}/welcome via Resend"
```

## Task 10: Phase B integration tests + verification

**Files:**
- Create: `backend/auth_service/tests_integration/test_admin_delegation.py`

- [ ] **Step 1: Write the integration tests**

```python
"""End-to-end test: create + transfer + welcome roundtrip against the
deployed backend, using the admin Bearer key."""
import os
import time
import pytest
import httpx

pytestmark = pytest.mark.integration

BACKEND = os.environ.get("E2E_BASE_URL_BACKEND", "https://cms-backend-roman.vercel.app")
ADMIN_KEY = os.environ.get("E2E_ADMIN_API_KEY")
USER_EMAIL = os.environ.get("E2E_USER_EMAIL")
ADMIN_EMAIL = os.environ.get("E2E_ADMIN_EMAIL")

skip = pytest.mark.skipif(
    not (ADMIN_KEY and USER_EMAIL and ADMIN_EMAIL),
    reason="missing E2E_ADMIN_API_KEY/E2E_USER_EMAIL/E2E_ADMIN_EMAIL",
)

HEADERS = {"Authorization": f"Bearer {ADMIN_KEY}", "Content-Type": "application/json"}


@skip
def test_create_then_delete_throwaway_project():
    slug = f"throwaway-{int(time.time())}"
    create = httpx.post(
        f"{BACKEND}/admin/projects",
        json={"slug": slug, "name": "Throwaway E2E", "owner_email": USER_EMAIL},
        headers=HEADERS,
        timeout=15.0,
    )
    assert create.status_code == 201, create.text
    # Cleanup: PATCH is_active=false (delete-equivalent on this schema)
    httpx.request(
        "PATCH",
        f"{BACKEND}/admin/projects/{slug}",
        json={"is_active": False},
        headers=HEADERS,
        timeout=15.0,
    )


@skip
def test_transfer_round_trip_on_e2e_test_project():
    # Transfer to admin
    r1 = httpx.post(
        f"{BACKEND}/admin/projects/e2e-test-project/transfer",
        json={"to_user_email": ADMIN_EMAIL},
        headers=HEADERS,
        timeout=15.0,
    )
    assert r1.status_code == 200, r1.text
    # And back
    r2 = httpx.post(
        f"{BACKEND}/admin/projects/e2e-test-project/transfer",
        json={"to_user_email": USER_EMAIL},
        headers=HEADERS,
        timeout=15.0,
    )
    assert r2.status_code == 200, r2.text


@skip
def test_welcome_email_send():
    r = httpx.post(
        f"{BACKEND}/admin/clients/{USER_EMAIL}/welcome",
        json={
            "project_slug": "e2e-test-project",
            "project_name": "E2E Test Project",
            "website_url": "https://cms-frontend-roman.vercel.app",
        },
        headers=HEADERS,
        timeout=15.0,
    )
    assert r.status_code == 200, r.text
    assert r.json()["success"] is True
```

- [ ] **Step 2: Run all unit tests one more time**

```bash
cd backend
venv/Scripts/python.exe -m pytest auth_service/tests/ -q
```
Expected: all green.

- [ ] **Step 3: Local manual smoke**

Bring up local backend (with `RESEND_API_KEY` set in `backend/.env`),
mint a local key, run the three integration tests against
`E2E_BASE_URL_BACKEND=http://localhost:8001`. All three should pass.

- [ ] **Step 4: Commit + push to dev**

```bash
git add backend/auth_service/tests_integration/test_admin_delegation.py
git commit -m "test(integration): admin delegation roundtrip — create, transfer, welcome"
git push origin dev
```

CI will run E2E with the deployed backend. Verify all 3 new
integration tests pass on prod.

---

# Phase C — Per-agent `.env` loader

## Task 11: `.env.example` + dotenv dependency

**Files:**
- Create: `agents/CMS Connector - Website/.env.example`
- Modify: `agents/CMS Connector - Website/requirements.txt`
- Modify: `agents/CMS Connector - Website/scan.py` (add `load_dotenv` at top)

- [ ] **Step 1: Add the dotenv requirement**

In `agents/CMS Connector - Website/requirements.txt`, add a line:

```
python-dotenv>=1.0.0
```

- [ ] **Step 2: Create `.env.example`**

`agents/CMS Connector - Website/.env.example`:

```bash
# CMS Connector — Website agent. Copy to .env (gitignored) and fill in.
# .env is auto-loaded by scan.py at startup; you do NOT need to export
# these in your shell after that.

# GitHub PAT with `repo` (and `workflow` if pushing CI files).
# https://github.com/settings/tokens?type=beta
GITHUB_TOKEN=

# Vercel PAT, full account scope.
# https://vercel.com/account/tokens
VERCEL_TOKEN=

# Anthropic API key for the Phase 2 LLM scan. Optional if `claude` CLI
# is on PATH.
# https://console.anthropic.com/settings/keys
ANTHROPIC_API_KEY=

# CMS admin API key, format: cmsk_<env>_<lookup>_<secret>. Mint via
# `python scripts/mint_admin_api_key.py`. Lost = mint a new one.
CMS_ADMIN_API_KEY=

# Backend base URL (no trailing slash). Defaults to production.
CMS_API_URL=https://cms-backend-roman.vercel.app
```

- [ ] **Step 3: Add `load_dotenv` at top of `scan.py`**

In `agents/CMS Connector - Website/scan.py`, immediately after the
existing stdlib imports (line 1–10ish) and BEFORE any `click`-related
import, add:

```python
from pathlib import Path

from dotenv import load_dotenv

# Load per-agent .env (gitignored, sibling of this file). Click's
# envvar lookup happens at decoration time, so this MUST run before
# any @click.option(envvar=...) is imported. Module-top is the only
# safe location.
load_dotenv(Path(__file__).resolve().parent / ".env")
```

If `Path` and other imports already exist, dedupe.

- [ ] **Step 4: Static check**

```bash
python -c "import ast; ast.parse(open('agents/CMS Connector - Website/scan.py').read())"
backend/venv/Scripts/python.exe -m ruff check "agents/CMS Connector - Website/scan.py"
backend/venv/Scripts/python.exe -m black --check "agents/CMS Connector - Website/scan.py"
```
Expected: clean.

- [ ] **Step 5: Local smoke**

```bash
cp "agents/CMS Connector - Website/.env.example" "agents/CMS Connector - Website/.env"
# Edit the file: paste your tokens
python "agents/CMS Connector - Website/scan.py" --help | head -20
```
Expected: `--help` runs without complaining about missing env. The
real values are surfaced when we add the `--admin-key` option below.

- [ ] **Step 6: Commit**

```bash
git add "agents/CMS Connector - Website/requirements.txt" "agents/CMS Connector - Website/.env.example" "agents/CMS Connector - Website/scan.py"
git commit -m "feat(agent): per-agent .env loader (python-dotenv) + .env.example template"
```

## Task 12: Add `--admin-key` CLI option

**Files:**
- Modify: `agents/CMS Connector - Website/scan.py`

- [ ] **Step 1: Add the option next to `--api-token`**

Find the existing `--api-token` Click option (around line 446) and
add this new option immediately AFTER it:

```python
@click.option(
    "--admin-key",
    "admin_key",
    default=None,
    envvar="CMS_ADMIN_API_KEY",
    help="CMS admin API key (cmsk_…). env: CMS_ADMIN_API_KEY.",
)
```

Also add `admin_key: str | None,` to the `def main(...)` parameter
list (right after `api_token: str | None,`).

- [ ] **Step 2: Use it (still alongside --api-token for now)**

In `main()`, near the existing
```python
if provision and not api_token:
```
guard, add:
```python
if admin_key and not api_token:
    api_token = admin_key  # short-term shim until Phase D rewrites all headers to Bearer
```

This keeps the cookie path working until Task 13–17 rewrite
`_resolve_client`, `_provision`, `_vercel_setup` to use Bearer.

- [ ] **Step 3: Lint + commit**

```bash
backend/venv/Scripts/python.exe -m ruff check "agents/CMS Connector - Website/scan.py"
backend/venv/Scripts/python.exe -m black --check "agents/CMS Connector - Website/scan.py"
git add "agents/CMS Connector - Website/scan.py"
git commit -m "feat(agent): --admin-key CLI option (env CMS_ADMIN_API_KEY) shimmed to api_token"
```

---

# Phase D — Agent refactor

Each task replaces a discrete cookie/Resend/Supabase call with the new
endpoint. Tests in `tests/test_scan_*.py` get updated alongside.

## Task 13: Bearer header in `_resolve_client` and `_provision`

**Files:**
- Modify: `agents/CMS Connector - Website/scan.py:115` (`_resolve_client`) and `:250` (`_provision`)

- [ ] **Step 1: Rewrite the two helper headers**

In `_resolve_client` (line 124) replace:
```python
"Cookie": f"access_token={api_token}",
```
with:
```python
"Authorization": f"Bearer {api_token}",
```

In `_provision` (line 256) make the same swap.

(Variable `api_token` is now in fact the admin key from Task 12's
shim.)

- [ ] **Step 2: Update mocks in `tests/test_scan_vercel_phase.py`**

Find every header literal `Cookie: access_token=...` in the existing
agent unit tests and replace with `Authorization: Bearer ...`.

- [ ] **Step 3: Run full agent suite**

```bash
cd "agents/CMS Connector - Website"
../../backend/venv/Scripts/python.exe -m pytest tests/ -q
```
Expected: all green.

- [ ] **Step 4: Lint + commit**

```bash
backend/venv/Scripts/python.exe -m ruff check "agents/CMS Connector - Website/scan.py" "agents/CMS Connector - Website/tests/test_scan_vercel_phase.py"
backend/venv/Scripts/python.exe -m black --check "agents/CMS Connector - Website/scan.py" "agents/CMS Connector - Website/tests/test_scan_vercel_phase.py"
git add "agents/CMS Connector - Website/scan.py" "agents/CMS Connector - Website/tests/test_scan_vercel_phase.py"
git commit -m "refactor(agent): _resolve_client + _provision use Authorization: Bearer"
```

## Task 14: Bearer in `_vercel_setup` PATCH

**Files:**
- Modify: `agents/CMS Connector - Website/scan.py:332` (the headers dict in `_vercel_setup`)

- [ ] **Step 1: Replace cookie with Bearer**

Line 332:
```python
headers = {"Content-Type": "application/json", "Cookie": f"access_token={cms_api_token}"}
```
→
```python
headers = {"Content-Type": "application/json", "Authorization": f"Bearer {cms_api_token}"}
```

- [ ] **Step 2: Run + lint + commit**

```bash
cd "agents/CMS Connector - Website"
../../backend/venv/Scripts/python.exe -m pytest tests/ -q
backend/venv/Scripts/python.exe -m ruff check scan.py
backend/venv/Scripts/python.exe -m black --check scan.py
git add scan.py
git commit -m "refactor(agent): _vercel_setup PATCH uses Bearer header"
```

## Task 15: Phase 4 — replace project-row Supabase Management call

**Files:**
- Modify: `agents/CMS Connector - Website/scan.py:_vercel_setup` — call `POST /admin/projects` if the slug is missing
- Modify: `agents/CMS Connector - Website/phases/4-integration.md`

- [ ] **Step 1: Update `_vercel_setup` to create the row first if needed**

In `scan.py:_vercel_setup`, near line 335 (the existing
`existing = _http("GET", f"{base}/admin/projects/{slug}", headers) or {}`),
add right after the GET:

```python
if not existing:
    create = _http(
        "POST",
        f"{base}/admin/projects",
        headers,
        {"slug": slug, "name": manifest.get("project_name", slug),
         "owner_email": manifest.get("developer_email", "stefanromanpers@gmail.com")},
    )
    if create:
        existing = create
        click.echo(f"  ✓ Created CMS project row: {slug}")
```

`developer_email` defaults to the operator's email (Stefan's, per
project memory) when the manifest doesn't carry one — the row is
later transferred to the client in Phase 6.

- [ ] **Step 2: Update phase doc**

`agents/CMS Connector - Website/phases/4-integration.md` — replace the
section that says "INSERT INTO projects via Supabase Management" with:

```markdown
### 4.1.5 — Ensure CMS project row exists

If `GET /admin/projects/<slug>` returns 404, POST to
`/admin/projects` with body `{slug, name, owner_email}` (use the
developer's admin email — ownership transfers to the client in
Phase 6). Otherwise reuse the existing row.
```

- [ ] **Step 3: Run + lint + commit**

```bash
cd "agents/CMS Connector - Website"
../../backend/venv/Scripts/python.exe -m pytest tests/ -q
backend/venv/Scripts/python.exe -m ruff check scan.py
backend/venv/Scripts/python.exe -m black --check scan.py
git add scan.py phases/4-integration.md
git commit -m "refactor(agent): create CMS project row via POST /admin/projects (drops Supabase Management call)"
```

## Task 16: Phase 6 — replace ownership transfer with backend endpoint

**Files:**
- Modify: `agents/CMS Connector - Website/phases/6-confirmation.md`
- (No `scan.py` change — Phase 6 is doc-driven, executed by Claude.)

- [ ] **Step 1: Rewrite the ownership-transfer section**

In `phases/6-confirmation.md`, replace section 6.3 ("Transfer project
ownership") with:

```markdown
### 6.3 — Transfer project ownership

POST to the backend admin API (NOT Supabase Management):

```http
POST {CMS_API_URL}/admin/projects/{project_slug}/transfer
Authorization: Bearer {CMS_ADMIN_API_KEY}
Content-Type: application/json

{"to_user_email": "<client_email>"}
```

200 = ownership transferred. The previous owner (developer admin
account) keeps access via `is_admin` — admin endpoints scope by
admin flag, not ownership.
```

Remove the old SQL block referencing `UPDATE projects SET user_id = …`
via Supabase Management.

- [ ] **Step 2: Commit**

```bash
git add "agents/CMS Connector - Website/phases/6-confirmation.md"
git commit -m "docs(agent/phase6): ownership transfer via /admin/projects/{slug}/transfer"
```

## Task 17: Phase 6 — replace welcome email with backend endpoint

**Files:**
- Modify: `agents/CMS Connector - Website/phases/6-confirmation.md`

- [ ] **Step 1: Rewrite the welcome-email section**

Replace the entire "Send welcome email via Resend" block (the one
beginning with `POST to https://api.resend.com/emails`) with:

```markdown
### 6.4 — Send welcome email

POST to the backend (which uses its own RESEND_API_KEY env — the
agent never holds the secret):

```http
POST {CMS_API_URL}/admin/clients/{client_email}/welcome
Authorization: Bearer {CMS_ADMIN_API_KEY}
Content-Type: application/json

{
  "project_slug": "<project_slug>",
  "project_name": "<project_name>",
  "website_url": "<deployed website URL>"
}
```

200 with `{"success": true, "resend_id": "<id>"}` = email sent. 502 =
backend's RESEND_API_KEY misconfigured or Resend rejected; check the
detail field. 404 = client account doesn't exist (run Phase 6.1
first).

The agent no longer holds RESEND_API_KEY or RESEND_FROM_EMAIL.
```

- [ ] **Step 2: Commit**

```bash
git add "agents/CMS Connector - Website/phases/6-confirmation.md"
git commit -m "docs(agent/phase6): welcome email via /admin/clients/{email}/welcome"
```

## Task 18: Update AGENTS.md credentials table

**Files:**
- Modify: `agents/CMS Connector - Website/AGENTS.md` (lines 32–38)

- [ ] **Step 1: Replace the credentials table**

Find the existing Required-credentials block and replace with:

```markdown
## Required credentials

The four below live in `agents/CMS Connector - Website/.env` (copy
from `.env.example`, gitignored, auto-loaded by `scan.py`).

| Tool | Env var | Used in |
|------|---------|---------|
| GitHub | `GITHUB_TOKEN` | Phase 1, 4 |
| Anthropic Claude | `claude` CLI preferred; `ANTHROPIC_API_KEY` fallback | Phase 2, 5 |
| Vercel | `VERCEL_TOKEN` | Phase 4 |
| CMS admin | `CMS_ADMIN_API_KEY` (cmsk_…) | Phase 4, 5, 6 |

### Backend-only credentials

These secrets live on the backend's Vercel env, NOT on the agent's
host. The agent reaches them indirectly through admin endpoints.

| Secret | Where | Why |
|--------|-------|-----|
| `RESEND_API_KEY` | backend Vercel env | welcome email send via `POST /admin/clients/{email}/welcome` |
| `SUPABASE_SERVICE_ROLE_KEY` | backend Vercel env | project create + ownership transfer via admin endpoints |

If a credential needed by a phase is missing, halt that phase and
surface a clear remediation. Do not silently skip.
```

- [ ] **Step 2: Commit**

```bash
git add "agents/CMS Connector - Website/AGENTS.md"
git commit -m "docs(agent): credentials table 6 → 4 (Resend + Supabase moved to backend-only)"
```

## Task 19: Drop the `--api-token` shim, rename to `--admin-key` everywhere

**Files:**
- Modify: `agents/CMS Connector - Website/scan.py`

- [ ] **Step 1: Drop the legacy flag**

In `scan.py`:
1. Remove the `@click.option("--api-token", …)` decorator.
2. Remove `api_token: str | None,` from the `main()` signature.
3. Remove the shim block:
   ```python
   if admin_key and not api_token:
       api_token = admin_key
   ```
4. Replace every remaining reference to `api_token` inside `main()`
   with `admin_key`.

- [ ] **Step 2: Run agent suite**

```bash
cd "agents/CMS Connector - Website"
../../backend/venv/Scripts/python.exe -m pytest tests/ -q
```
Expected: all green.

- [ ] **Step 3: Update unit tests**

If `test_scan_vercel_phase.py` passes the literal `"vtok"` as
`api_token`, rename to `admin_key` in those tests too.

- [ ] **Step 4: Lint + commit**

```bash
backend/venv/Scripts/python.exe -m ruff check "agents/CMS Connector - Website/scan.py" "agents/CMS Connector - Website/tests/test_scan_vercel_phase.py"
backend/venv/Scripts/python.exe -m black --check "agents/CMS Connector - Website/scan.py" "agents/CMS Connector - Website/tests/test_scan_vercel_phase.py"
git add "agents/CMS Connector - Website/scan.py" "agents/CMS Connector - Website/tests/test_scan_vercel_phase.py"
git commit -m "refactor(agent): drop --api-token, --admin-key is canonical"
```

## Task 20: Functionality preservation — full smoke against local + production

**Files:** none (operator verification)

This task IS the spec's preservation matrix. Every row must be ✓
before the plan is closed.

- [ ] **Local matrix** (backend on `http://localhost:8001`):

| Capability | How to verify |
|---|---|
| Dashboard admin login | Open `http://localhost:3000/log-in`, log in. `/dashboard` loads. |
| Dashboard "All Clients" | Navigate to `/dashboard/admin/clients`. Table renders. |
| Dashboard "All Projects" | `/dashboard/admin/projects`. Table renders. |
| Dashboard PATCH project | Edit a project, save. PATCH succeeds. |
| Dashboard rotate preview token | Click rotate. New token shown. |
| Agent creates client account | Run agent through Phase 6.1, client account created. |
| Agent looks up client by email | Phase 6.1 lookup branch. |
| Agent creates project row | Phase 4 — POST /admin/projects, row appears in DB. |
| Agent saves Vercel ids on project | Phase 4 — PATCH /admin/projects/{slug}, fields written. |
| Agent creates services | Phase 4 — POST /projects/{slug}/services for each service in manifest. |
| Agent transfers project ownership | Phase 6.3 — POST /admin/projects/{slug}/transfer. SQL: `SELECT user_id FROM projects WHERE slug='…'` returns client uid. |
| Agent sends welcome email | Phase 6.4 — Resend dashboard shows the send. Inbox check. |
| Public `/content/<slug>` | curl unauthenticated, 200 + JSON. |
| Public `/forms/<slug>/<form_key>` | curl with valid origin, 200. |
| `/auth/me`, `/auth/logout` | Browser session unaffected by Bearer changes. |

- [ ] **Production matrix** (backend on `cms-backend-roman.vercel.app`):

Same set of checks. Use a sandbox client repo for the agent
end-to-end test; delete the sandbox project after.

- [ ] **Push + watch CI**

```bash
git push origin dev
gh run watch --exit-status
```

CI must show CI ✓ + E2E ✓. The new integration tests (Phase A
Task 5, Phase B Task 10) gate on the new GH Actions secret
`E2E_ADMIN_API_KEY`.

- [ ] **Promote to master**

Once green on dev, run scheduled-merge:

```bash
gh workflow run "Scheduled merge dev → master"
```

Vercel auto-deploys backend. Re-run the production matrix above
against the freshly-deployed backend.

- [ ] **Mark plan complete** when every row in both matrices is ✓.

---

## Self-review

**Spec coverage**

| Spec section | Plan task |
|---|---|
| Subsystem 1 — schema | Task 1 |
| Subsystem 1 — `verify_admin_api_key` | Task 2 |
| Subsystem 1 — central auth dep | Task 3 |
| Subsystem 1 — bootstrap script | Task 4 |
| Subsystem 1 — local + prod tests | Task 5 |
| Subsystem 2 — welcome template | Task 6 |
| Subsystem 2 — POST /admin/projects | Task 7 |
| Subsystem 2 — POST /admin/projects/{slug}/transfer | Task 8 |
| Subsystem 2 — POST /admin/clients/{email}/welcome | Task 9 |
| Subsystem 2 — integration tests | Task 10 |
| Subsystem 3 — `.env.example` + dotenv | Task 11 |
| Subsystem 3 — `--admin-key` flag | Task 12 |
| Subsystem 4 — Bearer in `_resolve_client` + `_provision` | Task 13 |
| Subsystem 4 — Bearer in `_vercel_setup` | Task 14 |
| Subsystem 4 — Phase 4 project-row migration | Task 15 |
| Subsystem 4 — Phase 6 ownership transfer migration | Task 16 |
| Subsystem 4 — Phase 6 welcome email migration | Task 17 |
| Subsystem 4 — AGENTS.md credentials shrink | Task 18 |
| Subsystem 4 — drop `--api-token` shim | Task 19 |
| Functionality preservation matrix | Task 20 (the matrix IS the task) |

No gaps.

**Placeholder scan**: every task has exact code blocks, exact
commands, exact file paths. No "TBD" / "implement later" / "similar
to Task N".

**Type consistency**:
- `verify_admin_api_key(plain_key) -> dict | None` defined Task 2,
  consumed Task 3, integration-tested Task 5.
- `mint_admin_api_key(*, user_id, name, env, expires_at) ->
  tuple[str, str]` defined Task 2, consumed Task 4 (script).
- `admin_user_via_bearer_or_sid(request)` defined Task 3, consumed
  Tasks 7, 8, 9 (endpoints) and Task 13–14 (agent indirectly via
  the Bearer header).
- `send_welcome_email(*, to_email, full_name, project_name,
  website_url, login_url=...)` defined Task 6, consumed Task 9.
- `AdminProjectCreateIn`, `ProjectTransferIn`, `WelcomeEmailIn`
  schemas added incrementally Tasks 7/8/9; each new endpoint imports
  exactly one new schema model.
- `--admin-key` flag introduced Task 12, becomes canonical Task 19.

All consistent.
