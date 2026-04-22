# Session-Based Auth Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the JWT + refresh-token hybrid with a single opaque session cookie (`sid`), backed by a renamed DB table. Sliding 30/60-day lifetime, `SameSite=Strict` in production for CSRF-free cross-origin, clean cutover.

**Architecture:** New `services/sessions.py` owns the session lifecycle (create / validate / revoke / revoke-all). `auth.py` router becomes a thin wrapper. `deps.py::require_user` reads `sid` and delegates to `sessions.validate_session`. Frontend proxy strips `Domain=` from backend Set-Cookie so the cookie is scoped to `roman-technologies.dev`. DB table `refresh_tokens` renamed to `sessions` + 3 observability columns.

**Tech Stack:** FastAPI 0.115, Supabase (Postgres), Next.js 15 middleware, pytest, Vitest.

**Spec:** `docs/superpowers/specs/2026-04-22-session-auth-design.md`

**Testing approach:** Mocked-Supabase unit tests for all auth code paths (existing `conftest.py` pattern). Integration tests gated behind `CMS_RUN_DB_TESTS=1` create + clean up a disposable test user.

**Rollout window:** Tasks 1–10 land locally on the feature branch without touching prod. Task 11 applies the DB migration + pushes master; a ~1–2 minute prod-auth outage is expected while Vercel rebuilds. Run at a quiet time.

---

## File Structure

### Created

| Path | Responsibility |
|---|---|
| `backend/auth_service/services/sessions.py` | Session lifecycle: `create_session`, `validate_session`, `revoke_session`, `revoke_all_for_user`. |
| `backend/auth_service/tests/test_sessions.py` | 12 unit tests for `sessions.py`. |
| `backend/auth_service/tests/test_auth_router.py` | 11 integration-ish tests against `/auth/*` via TestClient. |
| `backend/auth_service/tests/test_sessions_integration.py` | 4 real-DB tests gated on `CMS_RUN_DB_TESTS=1`. |
| `backend/auth_service/core/security_headers.py` | Minimal middleware adding `X-Frame-Options`, `X-Content-Type-Options`. |
| `backend/migrations/2026_04_22_sessions_rename.sql` | Record of the DB migration applied via MCP. |

### Modified

| Path | Change |
|---|---|
| `backend/auth_service/core/security.py` | Drop JWT functions. Keep `generate_session_id`, `hash_token`. |
| `backend/auth_service/core/config.py` | Drop JWT settings (`PRIVATE_KEY_PATH`, `PUBLIC_KEY_PATH`, `JWT_ALGORITHM`, `ACCESS_TOKEN_EXPIRE_MINUTES`, `REFRESH_TOKEN_EXPIRE_DAYS_*`, `private_key`, `public_key`). Add `SESSION_COOKIE_NAME = "sid"`. |
| `backend/auth_service/services/auth_service.py` | Delete `issue_tokens`, `refresh_access_token`, `revoke_refresh_token`, `get_user_from_access_token`. Keep `authenticate_user`, `change_user_password`, `verify_password`, `hash_password`. |
| `backend/auth_service/routers/auth.py` | Replace two-cookie flow with single `sid` cookie. Delete `/auth/refresh`. `/auth/change-password` revokes all sessions + issues fresh one. |
| `backend/auth_service/routers/deps.py` | `require_user` reads `sid`, delegates to `sessions.validate_session`. |
| `backend/auth_service/main.py` | Wire the security-headers middleware. |
| `backend/auth_service/tests/conftest.py` | Adjust `auth_as` fixture to patch `validate_session` instead of `require_user` (if needed). |
| `backend/auth_service/tests/test_config.py` | Delete JWT-key tests; file becomes tiny or deletable. |
| `backend/requirements.txt` | Remove `python-jose[cryptography]`. |
| `backend/auth_service/requirements.txt` | Remove `python-jose[cryptography]`. |
| `frontend/src/app/api/[...path]/route.ts` | Strip `Domain=` from forwarded `Set-Cookie` headers. |
| `frontend/src/middleware.ts` | Rename cookie `access_token` → `sid`. Delete `tryRefresh` + `/auth/refresh` branch. |
| `frontend/src/components/dashboard/__tests__/` (existing tests) | Update references to `access_token` cookie name if any. |

---

## Task Order Rationale

1. **Code-only tasks first (1–10):** all edits land on the feature branch, tests pass against mocked Supabase. Zero prod impact.
2. **Flip last (Task 11):** apply DB migration + merge + push master. Vercel auto-redeploys; ~1–2 min auth outage during build.
3. **Verify (Task 12):** smoke test hosted CMS. Log in, DB check, verify `/auth/refresh` is gone, `sid` cookie has right flags.

---

## Task 1: Strip JWT from `security.py`, add session helpers

**Files:**
- Modify: `backend/auth_service/core/security.py`
- Modify: `backend/auth_service/tests/test_config.py` (delete JWT-key tests)

- [ ] **Step 1: Rewrite `security.py` with only the two functions we keep**

Replace the entire contents of `backend/auth_service/core/security.py` with:

```python
import hashlib
import secrets


def generate_session_id() -> str:
    """256-bit cryptographically random token, 43-char URL-safe base64."""
    return secrets.token_urlsafe(32)


def hash_token(raw_token: str) -> str:
    """SHA-256 hex of the raw token. Deterministic; no salt needed
    for a 256-bit random token.
    """
    return hashlib.sha256(raw_token.encode()).hexdigest()
```

- [ ] **Step 2: Delete the JWT-key tests in `test_config.py`**

The existing test file (`backend/auth_service/tests/test_config.py`) tests env-var-driven JWT key loading. After we drop JWT, those tests are obsolete. Delete the file:

```bash
rm backend/auth_service/tests/test_config.py
```

- [ ] **Step 3: Verify nothing still imports the deleted functions**

Run: `cd backend && grep -rn "create_access_token\|create_refresh_token\|decode_access_token" auth_service/`
Expected: only hits in `auth_service.py` (handled in Task 3) and `routers/auth.py` (handled in Task 4). No other files reference them.

- [ ] **Step 4: Commit**

```bash
git add backend/auth_service/core/security.py backend/auth_service/tests/test_config.py
git commit -m "refactor(security): drop JWT helpers; keep generate_session_id + hash_token"
```

---

## Task 2: Create `sessions.py` service + 12 unit tests

**Files:**
- Create: `backend/auth_service/services/sessions.py`
- Create: `backend/auth_service/tests/test_sessions.py`

- [ ] **Step 1: Write the failing test file**

Create `backend/auth_service/tests/test_sessions.py`:

```python
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest


SAMPLE_USER = {"id": "user-1", "email": "u@example.com", "is_admin": False, "is_active": True, "full_name": "Test User"}


@pytest.fixture
def sessions_module(mock_supabase):
    """Import sessions lazily so the mock patch targets land first."""
    from auth_service.services import sessions as mod
    return mod


async def test_create_session_stores_hashed_token_only(mock_supabase, sessions_module):
    mock_supabase.execute.return_value = MagicMock(data=[])  # no active sessions
    raw_sid, expires_at = await sessions_module.create_session(SAMPLE_USER, remember_me=False)

    assert len(raw_sid) >= 32
    # Verify insert payload stored hash, not raw token
    insert_payload = mock_supabase.insert.call_args_list[0].args[0]
    assert insert_payload["token_hash"] != raw_sid
    assert len(insert_payload["token_hash"]) == 64  # sha256 hex


async def test_create_session_caps_at_5_revokes_oldest(mock_supabase, sessions_module):
    # 5 existing active sessions — next login must revoke oldest
    mock_supabase.execute.side_effect = [
        MagicMock(data=[{"id": f"s{i}", "created_at": f"2026-01-0{i+1}"} for i in range(5)]),
        MagicMock(data=[]),  # revoke UPDATE
        MagicMock(data=[{"id": "new"}]),  # insert
    ]
    await sessions_module.create_session(SAMPLE_USER, remember_me=False)

    # Oldest one (s0) should be in the revoke call
    update_calls = [c for c in mock_supabase.update.call_args_list if c.args and c.args[0].get("revoked") is True]
    assert any(update_calls), "Expected a revoke UPDATE"


async def test_validate_session_returns_user_when_valid(mock_supabase, sessions_module):
    now = datetime.now(timezone.utc)
    mock_supabase.execute.return_value = MagicMock(data={
        "id": "s1",
        "token_hash": "abc",
        "expires_at": (now + timedelta(days=29)).isoformat(),
        "remember_me": False,
        "users": SAMPLE_USER,
    })
    user = await sessions_module.validate_session("some-raw-sid")
    assert user is not None
    assert user.id == "user-1"


async def test_validate_session_returns_none_when_revoked(mock_supabase, sessions_module):
    # .eq("revoked", False) → supabase returns data=None (filtered out)
    mock_supabase.execute.return_value = MagicMock(data=None)
    user = await sessions_module.validate_session("some-raw-sid")
    assert user is None


async def test_validate_session_returns_none_when_expired(mock_supabase, sessions_module):
    past = datetime.now(timezone.utc) - timedelta(minutes=1)
    mock_supabase.execute.return_value = MagicMock(data={
        "id": "s1",
        "expires_at": past.isoformat(),
        "remember_me": False,
        "users": SAMPLE_USER,
    })
    user = await sessions_module.validate_session("raw")
    assert user is None


async def test_validate_session_slides_expiry_when_threshold_passed(mock_supabase, sessions_module):
    now = datetime.now(timezone.utc)
    # Session was issued many days ago → remaining < (30 days - 5 min)
    mock_supabase.execute.return_value = MagicMock(data={
        "id": "s1",
        "expires_at": (now + timedelta(days=1)).isoformat(),
        "remember_me": False,
        "users": SAMPLE_USER,
    })
    user = await sessions_module.validate_session("raw")
    assert user is not None

    update_calls = [
        c for c in mock_supabase.update.call_args_list
        if isinstance(c.args[0], dict) and "expires_at" in c.args[0]
    ]
    assert len(update_calls) >= 1, "Expected a sliding expiry UPDATE"


async def test_validate_session_skips_db_update_when_throttled(mock_supabase, sessions_module):
    now = datetime.now(timezone.utc)
    # Issued very recently → remaining is basically full → no update
    mock_supabase.execute.return_value = MagicMock(data={
        "id": "s1",
        "expires_at": (now + timedelta(days=30)).isoformat(),
        "remember_me": False,
        "users": SAMPLE_USER,
    })
    await sessions_module.validate_session("raw")
    update_calls = [
        c for c in mock_supabase.update.call_args_list
        if isinstance(c.args[0], dict) and "expires_at" in c.args[0]
    ]
    assert len(update_calls) == 0, "Should NOT bump expires_at within the renewal window"


async def test_validate_session_returns_none_on_unknown_hash(mock_supabase, sessions_module):
    mock_supabase.execute.return_value = MagicMock(data=None)
    user = await sessions_module.validate_session("nonexistent")
    assert user is None


async def test_validate_session_returns_none_on_empty_input(mock_supabase, sessions_module):
    user = await sessions_module.validate_session("")
    assert user is None
    user = await sessions_module.validate_session(None)
    assert user is None


async def test_revoke_session_sets_revoked_true(mock_supabase, sessions_module):
    mock_supabase.execute.return_value = MagicMock(data=[{"id": "s1"}])
    await sessions_module.revoke_session("raw")
    update_payloads = [c.args[0] for c in mock_supabase.update.call_args_list if isinstance(c.args[0], dict)]
    assert any(p.get("revoked") is True for p in update_payloads)


async def test_revoke_all_for_user_kills_every_active_session(mock_supabase, sessions_module):
    mock_supabase.execute.return_value = MagicMock(data=[])
    await sessions_module.revoke_all_for_user("user-1")
    update_payloads = [c.args[0] for c in mock_supabase.update.call_args_list if isinstance(c.args[0], dict)]
    assert any(p.get("revoked") is True for p in update_payloads)


async def test_remember_me_sets_60_day_lifetime(mock_supabase, sessions_module):
    mock_supabase.execute.return_value = MagicMock(data=[])
    _, expires = await sessions_module.create_session(SAMPLE_USER, remember_me=True)
    expected_min = datetime.now(timezone.utc) + timedelta(days=59)
    assert expires > expected_min


async def test_default_sets_30_day_lifetime(mock_supabase, sessions_module):
    mock_supabase.execute.return_value = MagicMock(data=[])
    _, expires = await sessions_module.create_session(SAMPLE_USER, remember_me=False)
    expected_min = datetime.now(timezone.utc) + timedelta(days=29)
    expected_max = datetime.now(timezone.utc) + timedelta(days=31)
    assert expected_min < expires < expected_max
```

- [ ] **Step 2: Run tests — expect import failure (`sessions` module missing)**

Run: `cd backend && python -m pytest auth_service/tests/test_sessions.py -v`
Expected: `ModuleNotFoundError: No module named 'auth_service.services.sessions'`

- [ ] **Step 3: Implement `sessions.py`**

Create `backend/auth_service/services/sessions.py`:

```python
from datetime import datetime, timedelta, timezone
from typing import Optional

from .supabase_client import get_supabase
from ..core.security import generate_session_id, hash_token
from ..models.schemas import UserOut

DEFAULT_DAYS = 30
REMEMBER_ME_DAYS = 60
RENEWAL_WINDOW = timedelta(minutes=5)
MAX_SESSIONS_PER_USER = 5


async def create_session(
    user: dict,
    remember_me: bool,
    user_agent: Optional[str] = None,
    ip: Optional[str] = None,
) -> tuple[str, datetime]:
    """Issues a fresh session. Returns (raw_sid, expires_at).

    Caller writes the `sid` cookie with raw_sid; only the hash lives in DB.
    """
    raw_sid = generate_session_id()
    token_hash = hash_token(raw_sid)
    days = REMEMBER_ME_DAYS if remember_me else DEFAULT_DAYS
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(days=days)

    sb = get_supabase()

    active = (
        sb.table("sessions")
        .select("id, created_at")
        .eq("user_id", user["id"])
        .eq("revoked", False)
        .order("created_at", desc=False)
        .execute()
    )
    if active.data and len(active.data) >= MAX_SESSIONS_PER_USER:
        overflow = len(active.data) - MAX_SESSIONS_PER_USER + 1
        oldest_ids = [r["id"] for r in active.data[:overflow]]
        sb.table("sessions").update({"revoked": True}).in_("id", oldest_ids).execute()

    sb.table("sessions").insert({
        "user_id": user["id"],
        "token_hash": token_hash,
        "expires_at": expires_at.isoformat(),
        "revoked": False,
        "remember_me": remember_me,
        "last_used_at": now.isoformat(),
        "user_agent": user_agent,
        "ip_address": ip,
    }).execute()

    return raw_sid, expires_at


async def validate_session(raw_sid: Optional[str]) -> Optional[UserOut]:
    """Returns the user for a valid sid, or None. Slides expires_at when
    remaining lifetime falls below (full_lifetime - RENEWAL_WINDOW).
    """
    if not raw_sid:
        return None
    token_hash = hash_token(raw_sid)
    sb = get_supabase()
    result = (
        sb.table("sessions")
        .select("id, expires_at, remember_me, users(id, email, full_name, is_admin, is_active)")
        .eq("token_hash", token_hash)
        .eq("revoked", False)
        .single()
        .execute()
    )
    if not result.data:
        return None
    row = result.data
    now = datetime.now(timezone.utc)
    expires_at = datetime.fromisoformat(row["expires_at"])
    if expires_at < now:
        return None

    user = row.get("users")
    if not user or not user.get("is_active"):
        return None

    remaining = expires_at - now
    full_lifetime = timedelta(days=REMEMBER_ME_DAYS if row.get("remember_me") else DEFAULT_DAYS)
    if remaining < full_lifetime - RENEWAL_WINDOW:
        new_expires = now + full_lifetime
        sb.table("sessions").update({
            "expires_at": new_expires.isoformat(),
            "last_used_at": now.isoformat(),
        }).eq("id", row["id"]).execute()

    return UserOut(
        id=user["id"],
        email=user["email"],
        full_name=user.get("full_name"),
        is_admin=bool(user.get("is_admin", False)),
    )


async def revoke_session(raw_sid: str) -> None:
    """Marks the single session for this sid as revoked. No-op on unknown sid."""
    if not raw_sid:
        return
    sb = get_supabase()
    sb.table("sessions").update({"revoked": True}).eq("token_hash", hash_token(raw_sid)).execute()


async def revoke_all_for_user(user_id: str) -> None:
    """Marks every active session for this user as revoked. Used on password change."""
    sb = get_supabase()
    sb.table("sessions").update({"revoked": True}).eq("user_id", user_id).eq("revoked", False).execute()
```

- [ ] **Step 4: Verify tests pass**

Run: `cd backend && python -m pytest auth_service/tests/test_sessions.py -v`
Expected: `12 passed`.

- [ ] **Step 5: Commit**

```bash
git add backend/auth_service/services/sessions.py backend/auth_service/tests/test_sessions.py
git commit -m "feat(sessions): session lifecycle service + 12 unit tests"
```

---

## Task 3: Slim `auth_service.py` — remove JWT helpers

**Files:**
- Modify: `backend/auth_service/services/auth_service.py`

- [ ] **Step 1: Replace `auth_service.py` with the slimmed-down version**

Replace the entire file contents with:

```python
from typing import Optional

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, VerificationError, InvalidHashError

from .supabase_client import get_supabase

ph = PasswordHasher(
    time_cost=3,       # OWASP recommended
    memory_cost=65536, # 64 MB
    parallelism=4,
)


def verify_password(plain: str, hashed: str) -> bool:
    try:
        ph.verify(hashed, plain)
        return True
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def hash_password(plain: str) -> str:
    return ph.hash(plain)


async def authenticate_user(email: str, password: str) -> Optional[dict]:
    sb = get_supabase()
    result = (
        sb.table("users")
        .select("*")
        .eq("email", email)
        .eq("is_active", True)
        .single()
        .execute()
    )
    if not result.data:
        return None
    user = result.data
    if not verify_password(password, user["password_hash"]):
        return None
    return user


async def change_user_password(user_id: str, current_password: str, new_password: str) -> bool:
    """Returns True on success, False if current_password is wrong."""
    sb = get_supabase()
    result = (
        sb.table("users")
        .select("password_hash")
        .eq("id", user_id)
        .eq("is_active", True)
        .single()
        .execute()
    )
    if not result.data:
        return False
    if not verify_password(current_password, result.data["password_hash"]):
        return False
    new_hash = hash_password(new_password)
    sb.table("users").update({"password_hash": new_hash}).eq("id", user_id).execute()
    return True
```

- [ ] **Step 2: Verify no lingering imports break the module**

Run: `cd backend && python -c "from auth_service.services.auth_service import authenticate_user, change_user_password, verify_password, hash_password; print('OK')"`
Expected: `OK`.

- [ ] **Step 3: Commit**

```bash
git add backend/auth_service/services/auth_service.py
git commit -m "refactor(auth_service): drop JWT/refresh token helpers; keep password + auth only"
```

---

## Task 4: Rewrite `auth.py` router + 11 tests

**Files:**
- Modify: `backend/auth_service/routers/auth.py`
- Create: `backend/auth_service/tests/test_auth_router.py`

- [ ] **Step 1: Write failing test file**

Create `backend/auth_service/tests/test_auth_router.py`:

```python
from unittest.mock import MagicMock, patch

import pytest


def _sample_user_row():
    # plain-password "correct-password" hashed with argon2 (replace at runtime)
    return {
        "id": "u1",
        "email": "admin@example.com",
        "password_hash": "$argon2id$v=19$m=65536,t=3,p=4$DUMMY",
        "full_name": "Admin",
        "is_admin": True,
        "is_active": True,
    }


@pytest.fixture
def auth_deps(monkeypatch):
    """Patch authenticate_user + session helpers so tests drive outcomes directly."""
    async def fake_authenticate(email, password):
        if email == "admin@example.com" and password == "correct-password":
            return _sample_user_row()
        return None

    async def fake_create_session(user, remember_me, user_agent=None, ip=None):
        from datetime import datetime, timedelta, timezone
        return "raw-sid-12345", datetime.now(timezone.utc) + timedelta(days=60 if remember_me else 30)

    async def fake_validate(raw):
        from auth_service.models.schemas import UserOut
        if raw == "raw-sid-12345":
            return UserOut(id="u1", email="admin@example.com", full_name="Admin", is_admin=True)
        return None

    async def fake_revoke_session(raw):
        return None

    async def fake_revoke_all(uid):
        return None

    async def fake_change_pw(user_id, current, new):
        return current == "correct-password"

    monkeypatch.setattr("auth_service.routers.auth.authenticate_user", fake_authenticate)
    monkeypatch.setattr("auth_service.routers.auth.create_session", fake_create_session)
    monkeypatch.setattr("auth_service.routers.auth.validate_session", fake_validate)
    monkeypatch.setattr("auth_service.routers.auth.revoke_session", fake_revoke_session)
    monkeypatch.setattr("auth_service.routers.auth.revoke_all_for_user", fake_revoke_all)
    monkeypatch.setattr("auth_service.routers.auth.change_user_password", fake_change_pw)


def test_login_success_sets_sid_cookie_with_strict_secure_httponly(client, auth_deps):
    res = client.post("/auth/login", json={"email": "admin@example.com", "password": "correct-password", "remember_me": False})
    assert res.status_code == 200
    set_cookie = res.headers.get("set-cookie", "")
    assert "sid=raw-sid-12345" in set_cookie
    assert "HttpOnly" in set_cookie
    # Secure + SameSite=Strict only in production; in tests ENVIRONMENT=development
    # so we assert the other flags universally:
    assert "Path=/" in set_cookie


def test_login_wrong_password_returns_401_no_cookie(client, auth_deps):
    res = client.post("/auth/login", json={"email": "admin@example.com", "password": "wrong"})
    assert res.status_code == 401
    assert "sid=" not in res.headers.get("set-cookie", "")


def test_login_unknown_email_returns_401_no_cookie(client, auth_deps):
    res = client.post("/auth/login", json={"email": "nobody@example.com", "password": "anything"})
    assert res.status_code == 401


def test_login_remember_me_sets_60_day_max_age(client, auth_deps):
    res = client.post("/auth/login", json={"email": "admin@example.com", "password": "correct-password", "remember_me": True})
    set_cookie = res.headers.get("set-cookie", "")
    # max-age in seconds. 60 days = 5_184_000
    assert "Max-Age=5184000" in set_cookie


def test_login_default_sets_30_day_max_age(client, auth_deps):
    res = client.post("/auth/login", json={"email": "admin@example.com", "password": "correct-password", "remember_me": False})
    set_cookie = res.headers.get("set-cookie", "")
    assert "Max-Age=2592000" in set_cookie  # 30 days


def test_logout_revokes_session_and_clears_cookie(client, auth_deps):
    client.cookies.set("sid", "raw-sid-12345")
    res = client.post("/auth/logout")
    assert res.status_code == 204
    # Response has a Set-Cookie that expires sid immediately
    set_cookie = res.headers.get("set-cookie", "")
    assert 'sid=""' in set_cookie or "sid=;" in set_cookie


def test_me_returns_user_when_sid_valid(client, auth_deps):
    client.cookies.set("sid", "raw-sid-12345")
    res = client.get("/auth/me")
    assert res.status_code == 200
    assert res.json()["email"] == "admin@example.com"


def test_me_returns_401_when_sid_missing(client, auth_deps):
    client.cookies.clear()
    res = client.get("/auth/me")
    assert res.status_code == 401


def test_me_returns_401_when_sid_invalid(client, auth_deps):
    client.cookies.set("sid", "bogus")
    res = client.get("/auth/me")
    assert res.status_code == 401


def test_change_password_revokes_all_sessions_and_issues_new_one(client, auth_deps):
    client.cookies.set("sid", "raw-sid-12345")
    res = client.post("/auth/change-password", json={"current_password": "correct-password", "new_password": "NewStrongPass123"})
    assert res.status_code == 204
    # A fresh sid cookie is issued
    set_cookie = res.headers.get("set-cookie", "")
    assert "sid=" in set_cookie


def test_change_password_wrong_current_returns_400(client, auth_deps):
    client.cookies.set("sid", "raw-sid-12345")
    res = client.post("/auth/change-password", json={"current_password": "wrong", "new_password": "NewStrongPass123"})
    assert res.status_code == 400
```

- [ ] **Step 2: Run tests — expect import errors (functions don't exist yet)**

Run: `cd backend && python -m pytest auth_service/tests/test_auth_router.py -v`
Expected: `ImportError` on `create_session` / `validate_session` etc. from `auth_service.routers.auth`.

- [ ] **Step 3: Rewrite `routers/auth.py`**

Replace the entire file contents with:

```python
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Request, Response, status

from ..core.config import settings
from ..models.schemas import ChangeNameRequest, ChangePasswordRequest, LoginRequest, TokenResponse, UserOut
from ..services.auth_service import authenticate_user, change_user_password
from ..services.sessions import (
    DEFAULT_DAYS,
    REMEMBER_ME_DAYS,
    create_session,
    revoke_all_for_user,
    revoke_session,
    validate_session,
)

router = APIRouter(prefix="/auth", tags=["auth"])

SESSION_COOKIE = "sid"
IS_PROD = settings.ENVIRONMENT == "production"


def _set_session_cookie(response: Response, raw_sid: str, remember_me: bool) -> None:
    days = REMEMBER_ME_DAYS if remember_me else DEFAULT_DAYS
    response.set_cookie(
        key=SESSION_COOKIE,
        value=raw_sid,
        httponly=True,
        secure=IS_PROD,
        samesite="strict" if IS_PROD else "lax",
        max_age=days * 24 * 60 * 60,
        path="/",
    )


def _clear_session_cookie(response: Response) -> None:
    response.delete_cookie(SESSION_COOKIE, path="/")


def _client_meta(request: Request) -> tuple[str | None, str | None]:
    ua = request.headers.get("user-agent")
    # Vercel puts the real client IP in x-forwarded-for
    fwd = request.headers.get("x-forwarded-for", "")
    ip = fwd.split(",")[0].strip() if fwd else (request.client.host if request.client else None)
    return ua, ip


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest, request: Request, response: Response):
    user = await authenticate_user(body.email, body.password)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")

    user_agent, ip = _client_meta(request)
    raw_sid, _expires_at = await create_session(user, body.remember_me, user_agent=user_agent, ip=ip)
    _set_session_cookie(response, raw_sid, body.remember_me)
    # TokenResponse remains in the contract for backward compat, but the body is unused
    # by the frontend (cookie is the source of truth).
    return TokenResponse(access_token="session")


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(request: Request, response: Response):
    sid = request.cookies.get(SESSION_COOKIE)
    if sid:
        await revoke_session(sid)
    _clear_session_cookie(response)


@router.get("/me", response_model=UserOut)
async def me(request: Request):
    sid = request.cookies.get(SESSION_COOKIE)
    user = await validate_session(sid)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    return user


@router.post("/change-password", status_code=status.HTTP_204_NO_CONTENT)
async def change_password(body: ChangePasswordRequest, request: Request, response: Response):
    sid = request.cookies.get(SESSION_COOKIE)
    user = await validate_session(sid)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    if len(body.new_password) < 8:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="New password must be at least 8 characters.")

    success = await change_user_password(user.id, body.current_password, body.new_password)
    if not success:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Current password is incorrect.")

    # Revoke ALL sessions (including this one) and mint a fresh session for this user.
    await revoke_all_for_user(user.id)
    # Re-fetch the user dict so create_session has a `dict` shape (not UserOut)
    from ..services.supabase_client import get_supabase
    sb = get_supabase()
    fresh_user = sb.table("users").select("*").eq("id", user.id).single().execute().data
    user_agent, ip = _client_meta(request)
    raw_sid, _ = await create_session(fresh_user, remember_me=False, user_agent=user_agent, ip=ip)
    _set_session_cookie(response, raw_sid, remember_me=False)


@router.patch("/profile", status_code=status.HTTP_200_OK)
async def update_profile(body: ChangeNameRequest, request: Request):
    sid = request.cookies.get(SESSION_COOKIE)
    user = await validate_session(sid)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    name = body.full_name.strip()
    if not name:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Full name cannot be empty.")
    if len(name) > 100:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Full name must be 100 characters or fewer.")

    from ..services.supabase_client import get_supabase
    sb = get_supabase()
    sb.table("users").update({
        "full_name": name,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }).eq("id", user.id).execute()

    return {"full_name": name}
```

- [ ] **Step 4: Run the new tests**

Run: `cd backend && python -m pytest auth_service/tests/test_auth_router.py -v`
Expected: `11 passed`.

- [ ] **Step 5: Commit**

```bash
git add backend/auth_service/routers/auth.py backend/auth_service/tests/test_auth_router.py
git commit -m "feat(auth): session-based login/logout/me/change-password + 11 tests"
```

---

## Task 5: Update `deps.py::require_user` to use sessions

**Files:**
- Modify: `backend/auth_service/routers/deps.py`

- [ ] **Step 1: Rewrite `deps.py::require_user`**

In `backend/auth_service/routers/deps.py`, replace:

```python
from ..services.auth_service import get_user_from_access_token
```

with:

```python
from ..services.sessions import validate_session
```

And replace the `require_user` function body:

```python
async def require_user(request: Request) -> UserOut:
    sid = request.cookies.get("sid")
    user = await validate_session(sid) if sid else None
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    return user
```

Also delete the now-unused `ACCESS_COOKIE = "access_token"` line.

- [ ] **Step 2: Run the full test suite**

Run: `cd backend && python -m pytest auth_service/tests/ -v`
Expected: all tests PASS (including the existing workspace/content/publish tests that use `require_user` via `auth_as`).

- [ ] **Step 3: Commit**

```bash
git add backend/auth_service/routers/deps.py
git commit -m "refactor(deps): require_user reads sid cookie + delegates to validate_session"
```

---

## Task 6: Add security-headers middleware

**Files:**
- Create: `backend/auth_service/core/security_headers.py`
- Modify: `backend/auth_service/main.py`

- [ ] **Step 1: Create the middleware**

`backend/auth_service/core/security_headers.py`:

```python
"""Minimal security headers emitted on every response.

- X-Frame-Options: DENY  — prevents the CMS being rendered inside an
  iframe, blocking clickjacking.
- X-Content-Type-Options: nosniff — browser won't MIME-sniff; guards
  against content-type confusion attacks.

HSTS is emitted by Vercel's edge layer already.
Content-Security-Policy is deliberately out of scope for v1.
"""


class SecurityHeadersMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def send_with_headers(message):
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                headers.append((b"x-frame-options", b"DENY"))
                headers.append((b"x-content-type-options", b"nosniff"))
                message["headers"] = headers
            await send(message)

        await self.app(scope, receive, send_with_headers)
```

- [ ] **Step 2: Register the middleware**

In `backend/auth_service/main.py`, after the CORS `add_middleware(...)` block, add:

```python
from .core.security_headers import SecurityHeadersMiddleware

app.add_middleware(SecurityHeadersMiddleware)
```

- [ ] **Step 3: Verify via the existing test fixture**

Run: `cd backend && python -m pytest auth_service/tests/ -v`
Expected: all tests still pass (headers are additive — don't break anything).

- [ ] **Step 4: Manual smoke — hit /health and inspect headers**

Run: `cd backend && source ../../../backend/venv/Scripts/activate && uvicorn auth_service.main:app --port 8001 &` (or in a separate shell)
Then: `curl.exe -i http://localhost:8001/health | grep -iE "(x-frame|x-content)"`
Expected: both headers present.

- [ ] **Step 5: Commit**

```bash
git add backend/auth_service/core/security_headers.py backend/auth_service/main.py
git commit -m "feat(headers): emit X-Frame-Options and X-Content-Type-Options on every response"
```

---

## Task 7: Drop python-jose dep + config cleanup

**Files:**
- Modify: `backend/auth_service/core/config.py`
- Modify: `backend/requirements.txt`
- Modify: `backend/auth_service/requirements.txt`

- [ ] **Step 1: Slim `config.py`**

In `backend/auth_service/core/config.py`, remove these Settings fields (they're no longer used):

- `PRIVATE_KEY_PATH`
- `PUBLIC_KEY_PATH`
- `JWT_ALGORITHM`
- `ACCESS_TOKEN_EXPIRE_MINUTES`
- `REFRESH_TOKEN_EXPIRE_DAYS_DEFAULT`
- `REFRESH_TOKEN_EXPIRE_DAYS_REMEMBER_ME`

Remove the `private_key` and `public_key` `@property` methods. Remove the `import base64` and `import os` if they're now unused (they might still be used elsewhere — check before deleting).

Add one line for discoverability:

```python
SESSION_COOKIE_NAME: str = "sid"
```

- [ ] **Step 2: Remove `python-jose` from requirements**

In `backend/requirements.txt` remove the line:

```
python-jose[cryptography]==3.3.0
```

In `backend/auth_service/requirements.txt` remove the same line.

- [ ] **Step 3: Verify nothing references `jose`**

Run: `cd backend && grep -rn "from jose\|import jose" auth_service/`
Expected: no hits.

- [ ] **Step 4: Run full test suite**

Run: `cd backend && python -m pytest auth_service/tests/ -v`
Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add backend/auth_service/core/config.py backend/requirements.txt backend/auth_service/requirements.txt
git commit -m "chore: drop python-jose dep + JWT config fields (replaced by sessions.py)"
```

---

## Task 8: Frontend proxy strips `Domain=` from Set-Cookie

**Files:**
- Modify: `frontend/src/app/api/[...path]/route.ts`

- [ ] **Step 1: Update the proxy**

In `frontend/src/app/api/[...path]/route.ts`, locate the existing Set-Cookie forwarding loop:

```typescript
const setCookies = upstream.headers.getSetCookie();
for (const c of setCookies) {
    outHeaders.append("set-cookie", c);
}
```

Replace with:

```typescript
const setCookies = upstream.headers.getSetCookie();
for (const c of setCookies) {
    // Strip any Domain=... attribute so the browser uses the request host
    // (the frontend custom domain). Without this, the cookie would be
    // scoped to the backend's Vercel URL and not be sent on subsequent
    // frontend requests.
    const cleaned = c.replace(/;\s*Domain=[^;]+/gi, "");
    outHeaders.append("set-cookie", cleaned);
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/app/api/[...path]/route.ts
git commit -m "fix(proxy): strip Domain= from backend Set-Cookie so cookies attach to frontend host"
```

---

## Task 9: Frontend middleware — rename cookie + drop refresh

**Files:**
- Modify: `frontend/src/middleware.ts`

- [ ] **Step 1: Read current middleware**

Open `frontend/src/middleware.ts`. Expect the existing legacy-host redirect + auth logic with `access_token` cookie name and `tryRefresh` function.

- [ ] **Step 2: Apply three edits**

Edit 1 — rename the constant (if any) and the cookie reads. Change every `access_token` reference in this file to `sid`.

Edit 2 — delete the `tryRefresh` function entirely.

Edit 3 — remove the call site. In the middleware body, find and delete this block:

```typescript
// ── Silent refresh if access token expired ────────────────────────────────
if (!isAuthenticated) {
    const refreshRes = await tryRefresh(cookieHeader);
    if (refreshRes) {
        isAuthenticated = true;
        const destination = isProtected
            ? NextResponse.next()
            : NextResponse.redirect(new URL("/dashboard", request.url));
        // Forward all Set-Cookie headers from the refresh response
        const newCookies = refreshRes.headers.getSetCookie();
        for (const c of newCookies) {
            destination.headers.append("set-cookie", c);
        }
        markVerified(destination);
        return destination;
    }
}
```

After removal, the control flow goes directly from the `/auth/me` check to the `if (isProtected && !isAuthenticated)` redirect.

- [ ] **Step 3: Build the frontend to catch type errors**

Run: `cd frontend && npm run build 2>&1 | tail -20`
Expected: build succeeds. If TypeScript errors, fix them before continuing.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/middleware.ts
git commit -m "feat(middleware): use sid cookie; drop silent refresh (backend handles sliding renewal)"
```

---

## Task 10: Real-DB integration tests

**Files:**
- Create: `backend/auth_service/tests/test_sessions_integration.py`

- [ ] **Step 1: Create the test file**

`backend/auth_service/tests/test_sessions_integration.py`:

```python
"""Real-DB integration tests for the sessions module.

Gated by env var CMS_RUN_DB_TESTS=1 so CI/unit test runs skip them.

Each test creates a disposable test user with a recognizable email prefix
and cleans up after itself in a teardown fixture.
"""
import os
import uuid
from datetime import datetime, timedelta, timezone

import pytest

skip_if_no_db = pytest.mark.skipif(
    os.environ.get("CMS_RUN_DB_TESTS") != "1",
    reason="Set CMS_RUN_DB_TESTS=1 to run real-DB tests",
)


@pytest.fixture
async def test_user():
    """Creates and tears down a disposable test user."""
    from auth_service.services.supabase_client import get_supabase_admin
    from auth_service.services.auth_service import hash_password

    sb = get_supabase_admin()
    email = f"test_sessions_{uuid.uuid4().hex[:8]}@internal.test"
    user_row = {
        "email": email,
        "password_hash": hash_password("test-pw-12345"),
        "full_name": "Session Test",
        "is_admin": False,
        "is_active": True,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    insert_res = sb.table("users").insert(user_row).execute()
    user = insert_res.data[0]

    yield user

    # Cleanup: delete any sessions and the user itself
    sb.table("sessions").delete().eq("user_id", user["id"]).execute()
    sb.table("users").delete().eq("id", user["id"]).execute()


@skip_if_no_db
async def test_full_login_logout_cycle_against_real_db(test_user):
    from auth_service.services.sessions import create_session, validate_session, revoke_session
    raw_sid, _ = await create_session(test_user, remember_me=False)
    user = await validate_session(raw_sid)
    assert user is not None
    assert user.email == test_user["email"]
    await revoke_session(raw_sid)
    user = await validate_session(raw_sid)
    assert user is None


@skip_if_no_db
async def test_session_sliding_expiry_persists_in_db(test_user):
    """If we manually set expires_at to a short-remaining value, a validate
    should push it forward."""
    from auth_service.services.sessions import create_session, validate_session
    from auth_service.services.supabase_client import get_supabase_admin
    from auth_service.core.security import hash_token

    raw_sid, _ = await create_session(test_user, remember_me=False)
    sb = get_supabase_admin()
    # Force expiry to ~1 day from now (well below the 5-min threshold-of-full-life)
    new_expiry = datetime.now(timezone.utc) + timedelta(days=1)
    sb.table("sessions").update(
        {"expires_at": new_expiry.isoformat()}
    ).eq("token_hash", hash_token(raw_sid)).execute()

    # Validate — should bump expiry back to ~30 days
    await validate_session(raw_sid)

    # Read back and verify
    row = sb.table("sessions").select("expires_at").eq("token_hash", hash_token(raw_sid)).single().execute().data
    expires_at = datetime.fromisoformat(row["expires_at"])
    assert expires_at > datetime.now(timezone.utc) + timedelta(days=29)


@skip_if_no_db
async def test_password_change_kills_sessions_from_other_devices(test_user):
    """Create 3 sessions, revoke all, verify all 3 become invalid."""
    from auth_service.services.sessions import create_session, validate_session, revoke_all_for_user
    sids = []
    for _ in range(3):
        raw, _ = await create_session(test_user, remember_me=False)
        sids.append(raw)

    for s in sids:
        assert await validate_session(s) is not None

    await revoke_all_for_user(test_user["id"])

    for s in sids:
        assert await validate_session(s) is None


@skip_if_no_db
async def test_create_session_caps_at_5(test_user):
    """Creating 6 sessions should revoke the oldest, leaving 5 active."""
    from auth_service.services.sessions import create_session, validate_session

    sids = []
    for _ in range(6):
        raw, _ = await create_session(test_user, remember_me=False)
        sids.append(raw)

    # Oldest (sids[0]) should be revoked; rest should be valid
    assert await validate_session(sids[0]) is None
    for s in sids[1:]:
        assert await validate_session(s) is not None
```

- [ ] **Step 2: Run without the gate env var — should skip**

Run: `cd backend && python -m pytest auth_service/tests/test_sessions_integration.py -v`
Expected: all 4 tests SKIPPED with "Set CMS_RUN_DB_TESTS=1 to run real-DB tests".

- [ ] **Step 3: Commit (do NOT run them against the real DB yet — that happens after migration in Task 11)**

```bash
git add backend/auth_service/tests/test_sessions_integration.py
git commit -m "test(sessions): real-DB integration tests gated on CMS_RUN_DB_TESTS"
```

---

## Task 11: Apply DB migration + merge + deploy

**Files:**
- Create: `backend/migrations/2026_04_22_sessions_rename.sql`

⚠️ **This task causes a ~1–2 minute auth outage on prod.** Schedule for a time nobody else uses the CMS.

- [ ] **Step 1: Write the migration SQL file in the repo (for record)**

Create `backend/migrations/2026_04_22_sessions_rename.sql`:

```sql
-- Applied 2026-04-22 via Supabase MCP to project xeluydwpgiddbamysgyu (CMS)
-- Renames refresh_tokens → sessions and adds observability columns.

ALTER TABLE refresh_tokens RENAME TO sessions;
ALTER INDEX IF EXISTS refresh_tokens_pkey            RENAME TO sessions_pkey;
ALTER INDEX IF EXISTS refresh_tokens_token_hash_key  RENAME TO sessions_token_hash_key;
ALTER INDEX IF EXISTS refresh_tokens_user_id_fkey    RENAME TO sessions_user_id_fkey;

ALTER TABLE sessions ADD COLUMN last_used_at TIMESTAMPTZ DEFAULT NOW();
ALTER TABLE sessions ADD COLUMN user_agent TEXT;
ALTER TABLE sessions ADD COLUMN ip_address TEXT;

CREATE INDEX idx_sessions_active_lookup
  ON sessions (token_hash)
  WHERE revoked = false;
```

- [ ] **Step 2: Commit the migration record**

```bash
git add backend/migrations/2026_04_22_sessions_rename.sql
git commit -m "db: rename refresh_tokens → sessions + observability columns"
```

- [ ] **Step 3: Merge the feature branch to master**

In the main repo (not the worktree):

```bash
cd "c:/Users/stefa/.gemini/antigravity/scratch/CMS - websites"
git fetch origin master
git checkout master
git pull
git merge feat/cms-preview-publish --no-ff -m "Merge feat/cms-preview-publish: session-based auth"
```

- [ ] **Step 4: Push master (triggers Vercel build)**

Run:

```bash
git push "https://stefanroman22:<GITHUB_TOKEN>@github.com/stefanroman22/cms-platform.git" master
```

(Or whichever remote/credential method works — just `git push origin master` is fine if your Git credentials are set.)

- [ ] **Step 5: IMMEDIATELY apply the Supabase migration**

Use the Supabase MCP (`mcp__supabase__apply_migration`) with the project_id `xeluydwpgiddbamysgyu`, migration name `2026_04_22_sessions_rename`, and the SQL from Step 1.

- [ ] **Step 6: Wait for the Vercel backend redeploy to finish (~1–2 min)**

Poll via Vercel API or watch the dashboard at https://vercel.com/dashboard. Once the latest deployment for `cms-backend-roman` is `READY`, the system is back up.

- [ ] **Step 7: Run the real-DB integration tests against prod Supabase**

```bash
cd backend
CMS_RUN_DB_TESTS=1 python -m pytest auth_service/tests/test_sessions_integration.py -v
```

Expected: 4 passed. These create and clean up their own test users.

---

## Task 12: Post-deploy smoke test + env-var cleanup

**Files:** none (manual verification + Vercel env var cleanup).

- [ ] **Step 1: Log in via the CMS UI**

Visit `https://roman-technologies.dev/log-in`. Enter admin creds, tick "remember me" on a second attempt later. Verify:

- Login succeeds.
- DevTools → Application → Cookies → `roman-technologies.dev` shows `sid` with `HttpOnly=true`, `Secure=true`, `SameSite=Strict`.
- No `access_token` or `refresh_token` cookies present.
- `Max-Age` ≈ 2,592,000 (30 days) or 5,184,000 (60 days with remember_me).

- [ ] **Step 2: Verify /auth/me works + security headers are present**

Open DevTools → Network → reload `/dashboard` and inspect the response headers of any `/api/auth/me` request:

- `x-frame-options: DENY`
- `x-content-type-options: nosniff`

- [ ] **Step 3: Verify /auth/refresh is gone**

Run: `curl.exe -i -X POST https://cms-backend-roman.vercel.app/auth/refresh`
Expected: HTTP 405 Method Not Allowed or 404. If it returns 200, the deploy didn't pick up the new code; retry.

- [ ] **Step 4: Delete orphaned JWT env vars on Vercel**

The backend no longer needs `JWT_PRIVATE_KEY_B64`, `JWT_PUBLIC_KEY_B64`, or `JWT_ALGORITHM`. Delete them via the Vercel API or dashboard:

```python
# scripts/deploy/delete_jwt_env_vars.py (one-off, ad-hoc)
import json, os, urllib.request

token = os.environ["VERCEL_TOKEN"]
pid = "prj_uqWx3NgmJXeVMAwiSci4C2pYTxM8"  # cms-backend-roman

req = urllib.request.Request(
    f"https://api.vercel.com/v9/projects/{pid}/env",
    headers={"Authorization": f"Bearer {token}"},
)
envs = json.loads(urllib.request.urlopen(req).read())["envs"]

to_delete = ["JWT_PRIVATE_KEY_B64", "JWT_PUBLIC_KEY_B64", "JWT_ALGORITHM"]
for e in envs:
    if e["key"] in to_delete:
        url = f"https://api.vercel.com/v9/projects/{pid}/env/{e['id']}"
        urllib.request.urlopen(urllib.request.Request(
            url, method="DELETE",
            headers={"Authorization": f"Bearer {token}"},
        ))
        print(f"  deleted {e['key']} {e.get('target')}")

print("Done.")
```

- [ ] **Step 5: Smoke test the full session lifecycle**

1. Log in with remember_me = false. Check sid Max-Age = 30 days.
2. Log out. Sid cookie cleared. DB session row has `revoked=true`.
3. Log in with remember_me = true. Check Max-Age = 60 days.
4. Go to `/dashboard/account` → change password. Verify:
   - You stay logged in (fresh session issued).
   - Old session in DB (from step 3) is now `revoked=true`.
5. Log out. Done.

- [ ] **Step 6: Record completion**

If all six steps pass, add a note to `docs/superpowers/plans/2026-04-22-session-auth.md`:

```markdown
## Completion — 2026-04-22

- [x] DB migration applied
- [x] Backend + frontend deployed
- [x] Integration tests pass
- [x] Smoke test passes
- [x] JWT env vars cleaned up
```

Commit:

```bash
git add docs/superpowers/plans/2026-04-22-session-auth.md
git commit -m "docs: record session-auth rollout completion"
```

---

## Out of Scope (tracked follow-ups)

- MFA (TOTP / WebAuthn).
- Password reset via Resend email.
- Content Security Policy (own project).
- Admin "Active Sessions" UI — schema columns (`user_agent`, `last_used_at`, `ip_address`) are ready.
- Audit log of failed logins (currently only successful logins are visible via `sessions.created_at`; failures hit the rate limiter but aren't recorded).
- Delete the now-unused `backend/keys/` directory (private.pem, public.pem) — safe to remove once you've confirmed you'll never re-enable JWT.
