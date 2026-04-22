# Session-Based Auth — Design Spec

**Date:** 2026-04-22
**Status:** Approved (brainstorm), ready for implementation plan
**Feature:** Replace JWT-based auth with a single-cookie, DB-backed session system. Same-origin-only (via the Next.js proxy). Sliding 30/60-day lifetime with remember_me.

---

## Motivation

The current system is a hybrid: short-lived JWT access token + DB-backed refresh token. It works, but it:

- Leaks enough structure into the cookie (JWT payload, even encoded) to make client inspection tempting.
- Requires RS256 key management (PEM files → base64 env vars on Vercel).
- Uses `SameSite=None` to survive cross-origin, which maximally widens CSRF exposure.
- Silent-refresh logic in middleware adds complexity for little benefit in a CMS-scale product.

Goal: a session system where the only thing the browser holds is an opaque 256-bit random ID, scoped to a single domain, with `SameSite=Strict` structurally blocking CSRF. Stateful, server-validated, revocable in one UPDATE.

## Non-goals (v1)

- Multi-factor auth.
- Email-based password reset.
- Content Security Policy headers (own project).
- Admin "active sessions" UI (schema is ready; UI deferred).
- IP pinning / device fingerprinting.

## Architectural Decisions (locked during brainstorm)

| # | Decision |
|---|---|
| 1 | Single opaque session cookie (`sid`), no JWT anywhere. |
| 2 | Cookie set on the frontend domain (`roman-technologies.dev`) via the existing Next.js proxy, which rewrites backend `Set-Cookie` to strip `Domain=` so the browser defaults to the frontend host. |
| 3 | `SameSite=Strict; Secure; HttpOnly` in production. Local dev uses `SameSite=Lax` (browsers reject `None`/`Strict` cross-scheme on localhost). |
| 4 | Sliding expiration, 30 days default / 60 days when `remember_me=true`. DB write for the expiry bump is **throttled** — only when <lifetime−5min remains. |
| 5 | 5 concurrent sessions per user cap (same as current `refresh_tokens`). 6th login revokes the oldest. |
| 6 | Password change revokes **all** sessions for that user, including the current one. User is forced to re-login. |
| 7 | DB table `refresh_tokens` is **renamed** to `sessions` + 3 observability columns added. No new table. |
| 8 | Clean cutover — no dual-run with JWT. Sole prod user (Stefan) gets logged out once; JWT code deleted. |
| 9 | `/auth/refresh` endpoint **deleted**. Sliding renewal happens implicitly in `validate_session`. |
| 10 | RS256 PEM keys + `python-jose` dep removed. Vercel JWT env vars deleted post-deploy. |

## System Overview

```
Browser (roman-technologies.dev)
    │  Cookie: sid=<43-char base64> (HttpOnly, Secure, SameSite=Strict)
    │
    ▼
/api/[...path] (Next.js Edge catch-all proxy, same-origin)
    │  Forwards cookie; rewrites any backend Set-Cookie
    │  by stripping Domain=... so browser uses request host.
    ▼
cms-backend-roman.vercel.app (FastAPI)
    │  sessions.validate_session(raw_sid):
    │    1. SHA-256(raw_sid) → token_hash
    │    2. SELECT * FROM sessions WHERE token_hash=$1
    │                                AND revoked=false
    │                                AND expires_at>now()
    │    3. If remaining < lifetime − 5 min → UPDATE expires_at.
    │    4. Return user.
    ▼
Supabase (sessions table)
```

---

## 1. Data Model

### Migration (Supabase MCP)

```sql
-- Table rename
ALTER TABLE refresh_tokens RENAME TO sessions;
ALTER INDEX IF EXISTS refresh_tokens_pkey            RENAME TO sessions_pkey;
ALTER INDEX IF EXISTS refresh_tokens_token_hash_key  RENAME TO sessions_token_hash_key;
ALTER INDEX IF EXISTS refresh_tokens_user_id_fkey    RENAME TO sessions_user_id_fkey;

-- Observability columns (non-auth-critical)
ALTER TABLE sessions ADD COLUMN last_used_at TIMESTAMPTZ DEFAULT NOW();
ALTER TABLE sessions ADD COLUMN user_agent TEXT;
ALTER TABLE sessions ADD COLUMN ip_address TEXT;

-- Partial index: active session lookup (hot path)
CREATE INDEX idx_sessions_active_lookup
  ON sessions (token_hash)
  WHERE revoked = false;
```

### Final schema

| Column | Type | Purpose |
|---|---|---|
| `id` | uuid | PK |
| `user_id` | uuid | FK → users.id |
| `token_hash` | text, unique | SHA-256 hex of raw `sid` |
| `expires_at` | timestamptz | Sliding; updated on throttled hits |
| `revoked` | bool | explicit logout / password change |
| `remember_me` | bool | drives 30- vs 60-day lifetime |
| `last_used_at` | timestamptz | every-hit observability |
| `user_agent` | text, nullable | snapshot at login |
| `ip_address` | text, nullable | snapshot at login |
| `created_at` | timestamptz | session start |

---

## 2. Backend Changes

### New

**`backend/auth_service/services/sessions.py`** — the session lifecycle in one file:

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

    # Enforce session cap: revoke oldest if over limit
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
        oldest = [r["id"] for r in active.data[:overflow]]
        sb.table("sessions").update({"revoked": True}).in_("id", oldest).execute()

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


async def validate_session(raw_sid: str) -> Optional[UserOut]:
    """Looks up the session. Slides expires_at if threshold passed.
    Returns the user if valid, None otherwise.
    """
    if not raw_sid:
        return None
    token_hash = hash_token(raw_sid)
    sb = get_supabase()
    result = (
        sb.table("sessions")
        .select("*, users(id, email, full_name, is_admin, is_active)")
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

    # Throttled sliding renewal
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
    sb = get_supabase()
    sb.table("sessions").update({"revoked": True}).eq("token_hash", hash_token(raw_sid)).execute()


async def revoke_all_for_user(user_id: str) -> None:
    sb = get_supabase()
    sb.table("sessions").update({"revoked": True}).eq("user_id", user_id).eq("revoked", False).execute()
```

### Modified

**`backend/auth_service/core/security.py`** — strip JWT functions, keep minimal primitives:

```python
import secrets
import hashlib


def generate_session_id() -> str:
    """256-bit cryptographically random, 43-char URL-safe base64."""
    return secrets.token_urlsafe(32)


def hash_token(raw_token: str) -> str:
    """SHA-256 hex. Deterministic; no salt needed for 256-bit random tokens."""
    return hashlib.sha256(raw_token.encode()).hexdigest()
```

Delete `create_access_token`, `create_refresh_token`, `decode_access_token`.

**`backend/auth_service/core/config.py`** — drop `PRIVATE_KEY_PATH`, `PUBLIC_KEY_PATH`, `JWT_ALGORITHM`, `ACCESS_TOKEN_EXPIRE_MINUTES`, `REFRESH_TOKEN_EXPIRE_DAYS_*`, `private_key` / `public_key` properties. Add `SESSION_COOKIE_NAME = "sid"` for discoverability.

**`backend/auth_service/routers/auth.py`** — the public surface. All routes now session-based:

- `POST /auth/login` — authenticate via `authenticate_user`, call `create_session`, set `sid` cookie.
- `POST /auth/logout` — read `sid` cookie, call `revoke_session`, clear cookie.
- `GET /auth/me` — read `sid`, call `validate_session`, return user or 401.
- `POST /auth/change-password` — verify current password, update hash, call `revoke_all_for_user`, issue a new session for the current user, return new `sid` cookie.
- `PATCH /auth/profile` — unchanged semantically; uses `validate_session` instead of JWT decode.
- **`POST /auth/refresh` — deleted.**

Cookie attributes helper:

```python
IS_PROD = settings.ENVIRONMENT == "production"

def _cookie_kwargs(max_age_seconds: int) -> dict:
    return {
        "key": "sid",
        "httponly": True,
        "secure": IS_PROD,
        "samesite": "strict" if IS_PROD else "lax",
        "max_age": max_age_seconds,
        "path": "/",
    }
```

**`backend/auth_service/routers/deps.py`** — `require_user()` uses `sessions.validate_session()` instead of JWT decode:

```python
from ..services.sessions import validate_session

async def require_user(request: Request) -> UserOut:
    sid = request.cookies.get("sid")
    user = await validate_session(sid) if sid else None
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user
```

### Deleted

- JWT code paths across `security.py`, `auth_service.py`, `config.py`.
- `python-jose[cryptography]` from `backend/requirements.txt` + `backend/auth_service/requirements.txt`.
- Env vars on Vercel: `JWT_PRIVATE_KEY_B64`, `JWT_PUBLIC_KEY_B64`, `JWT_ALGORITHM` (manual cleanup step post-deploy).

### Security headers

`main.py` already emits HSTS implicitly via Vercel. Ensure the backend adds, via a small middleware, these response headers for authenticated routes:

- `X-Frame-Options: DENY`
- `X-Content-Type-Options: nosniff`

`Content-Security-Policy` intentionally out of scope for v1.

---

## 3. Frontend Changes

### Modified

**`frontend/src/app/api/[...path]/route.ts`** — strip `Domain=` from backend Set-Cookie:

```typescript
const setCookies = upstream.headers.getSetCookie();
for (const c of setCookies) {
    // Strip any Domain=... attribute so the browser uses the request host
    // (the frontend domain, not the backend Vercel URL).
    const cleaned = c.replace(/;\s*Domain=[^;]+/gi, "");
    outHeaders.append("set-cookie", cleaned);
}
```

**`frontend/src/middleware.ts`** — two changes:

1. Cookie name `access_token` → `sid` (fast-path cache check).
2. Delete the entire `tryRefresh` / `/auth/refresh` branch (no longer needed; backend handles sliding renewal internally).

The `auth_verified` short-lived middleware cache cookie stays (avoids hitting `/auth/me` on every navigation; TTL 13 min).

### Unchanged

- Dashboard pages, editors, `PreviewPublishBar`, `PublishConfirmModal`, API calls through `/api/*`.
- Login form markup — POST body shape identical (`{email, password, remember_me}`).

---

## 4. Testing Strategy

### 4a. Backend unit tests — mocked Supabase (existing `conftest.py` pattern)

**`backend/auth_service/tests/test_sessions.py`** — 12 tests against `sessions.py`:

1. `test_create_session_stores_hashed_token_only`
2. `test_create_session_caps_at_5_revokes_oldest`
3. `test_validate_session_returns_user_when_valid`
4. `test_validate_session_returns_none_when_revoked`
5. `test_validate_session_returns_none_when_expired`
6. `test_validate_session_slides_expiry_when_threshold_passed`
7. `test_validate_session_skips_db_update_when_throttled`
8. `test_validate_session_returns_none_on_unknown_hash`
9. `test_revoke_session_sets_revoked_true`
10. `test_revoke_all_for_user_kills_every_active_session`
11. `test_remember_me_sets_60_day_lifetime`
12. `test_default_sets_30_day_lifetime`

**`backend/auth_service/tests/test_auth_router.py`** — 11 tests via TestClient:

13. `test_login_success_sets_sid_cookie_with_strict_secure_httponly`
14. `test_login_wrong_password_returns_401_no_cookie`
15. `test_login_unknown_email_returns_401_no_cookie`
16. `test_login_remember_me_sets_60_day_max_age`
17. `test_login_default_sets_30_day_max_age`
18. `test_logout_revokes_session_and_clears_cookie`
19. `test_me_returns_user_when_sid_valid`
20. `test_me_returns_401_when_sid_missing`
21. `test_me_returns_401_when_sid_invalid`
22. `test_change_password_revokes_all_sessions_and_issues_new_one`
23. `test_change_password_wrong_current_returns_400_sessions_untouched`

### 4b. Backend DB integration tests — real Supabase

**`backend/auth_service/tests/test_sessions_integration.py`** — 4 tests, gated on `CMS_RUN_DB_TESTS=1`:

24. `test_full_login_logout_cycle_against_real_db`
25. `test_session_sliding_expiry_persists_in_db`
26. `test_password_change_kills_sessions_from_other_devices`
27. `test_cleanup_removes_expired_revoked_rows`

These create a disposable test user (`test_sessions_xxxxx@internal.test`) and clean up after themselves. Not run in CI unless the env var is set.

### 4c. Frontend Vitest

- Update `middleware.test.ts` — rename cookie from `access_token` to `sid`. Add test: middleware redirects unauthenticated user on `/dashboard` to `/log-in`.

### Total

27 new/updated tests. Every auth code path covered.

---

## 5. Deployment & Edge Cases

### Rollout order

1. Apply DB migration via Supabase MCP.
2. Merge code to `master`. Both Vercel projects auto-build.
3. Clear `JWT_*` env vars on the backend Vercel project.
4. Re-login once (old JWT cookie invalid).

### Failure modes

| Scenario | Handling |
|---|---|
| Cookie stolen via physical access | Revoked on logout, or on password change. No further v1 defense. |
| XSS | Impossible to read the cookie from JS (`HttpOnly`). Authenticated calls from the compromised page still work — but `SameSite=Strict` prevents cross-site escalation. |
| DB dump leaked | Only SHA-256 hashes stored; useless without the raw `sid`. |
| Concurrent 6th login race | Both logins may revoke the same "oldest". Worst case: 4 sessions instead of 5. Acceptable. |
| Clock skew | Postgres `NOW()` authoritative; no client clock in auth path. |

### Known limits

- No IP pinning / fingerprint checks.
- No CSP.
- No `login_attempts` audit table (successful logins visible via `sessions.created_at`; failures unlogged beyond slowapi rate-limit responses).

### Out of scope (tracked follow-ups)

- MFA.
- Password reset via email.
- Admin "active sessions" UI (schema ready: `user_agent`, `last_used_at`, `ip_address`).
- CSP rollout.
