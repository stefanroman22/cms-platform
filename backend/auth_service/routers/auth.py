from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, Request, Response, status

from ..core import pg_rate_limit
from ..core.config import settings
from ..core.limiter import limiter
from ..models.schemas import (
    ChangeNameRequest,
    ChangePasswordRequest,
    LoginRequest,
    TokenResponse,
    UserOut,
)
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

# SEC-011/SEC-020: per-account login lockout. After this many failed attempts for
# one email within the window, further attempts are refused (shared across Vercel
# instances via the Postgres limiter). Generous enough to tolerate typos but far
# below any realistic brute-force throughput.
_LOGIN_FAIL_LIMIT = 10
_LOGIN_FAIL_WINDOW_SECONDS = 900  # 15 minutes
IS_PROD = settings.ENVIRONMENT == "production"


# SEC-021: preview deployments are served over HTTPS too, so the session cookie
# must carry the Secure flag there as well — not only in production. SameSite stays
# `lax` outside production because the preview frontend and backend are different
# origins and `strict` would stop the cookie from being sent on those requests.
_IS_HTTPS_ENV = settings.ENVIRONMENT in ("production", "preview")


def _set_session_cookie(response: Response, raw_sid: str, remember_me: bool) -> None:
    days = REMEMBER_ME_DAYS if remember_me else DEFAULT_DAYS
    response.set_cookie(
        key=SESSION_COOKIE,
        value=raw_sid,
        httponly=True,
        secure=_IS_HTTPS_ENV,
        samesite="strict" if IS_PROD else "lax",
        max_age=days * 24 * 60 * 60,
        path="/",
    )


def _clear_session_cookie(response: Response) -> None:
    response.delete_cookie(SESSION_COOKIE, path="/")


def _client_meta(request: Request) -> tuple[str | None, str | None]:
    ua = request.headers.get("user-agent")
    fwd = request.headers.get("x-forwarded-for", "")
    ip = fwd.split(",")[0].strip() if fwd else (request.client.host if request.client else None)
    return ua, ip


@router.post("/login", response_model=TokenResponse)
# Bumped 10 → 30/minute. Real users typing the wrong password (sticky
# shift, swapped layouts) can blow past 10/minute legitimately, and
# E2E suite logins from a single runner IP collide on the bucket
# because Vercel rewrites X-Forwarded-For at the edge (prepends the
# real client IP), so per-test XFF doesn't isolate the bucket. 30/min
# still locks out a brute-force script (~28k attempts/day vs realistic
# password keyspace) but tolerates the legitimate-typo case.
@limiter.limit("30/minute")
async def login(body: LoginRequest, request: Request, response: Response):
    fail_bucket = f"login_fail:{body.email.strip().lower()}"
    if pg_rate_limit.over_limit(fail_bucket, _LOGIN_FAIL_LIMIT, _LOGIN_FAIL_WINDOW_SECONDS):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many failed login attempts. Please wait a few minutes and try again.",
        )

    user = await authenticate_user(body.email, body.password)
    if not user:
        # Count the failure (per-account) and reject. The over_limit gate above
        # locks the account out once the threshold is crossed.
        pg_rate_limit.allow(fail_bucket, _LOGIN_FAIL_LIMIT, _LOGIN_FAIL_WINDOW_SECONDS)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password"
        )

    # Successful login clears the account's failure counter.
    pg_rate_limit.reset(fail_bucket)

    user_agent, ip = _client_meta(request)
    raw_sid, _expires_at = await create_session(
        user, body.remember_me, user_agent=user_agent, ip=ip
    )
    _set_session_cookie(response, raw_sid, body.remember_me)
    # TokenResponse remains in the contract for backward compat; body is unused
    # by the frontend — the cookie is the source of truth.
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
@limiter.limit("3/minute")
async def change_password(body: ChangePasswordRequest, request: Request, response: Response):
    sid = request.cookies.get(SESSION_COOKIE)
    user = await validate_session(sid)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    if len(body.new_password) < 8:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="New password must be at least 8 characters.",
        )

    success = await change_user_password(user.id, body.current_password, body.new_password)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Current password is incorrect."
        )

    # Revoke ALL sessions (including this one) and mint a fresh session
    await revoke_all_for_user(user.id)
    from ..services.supabase_client import get_supabase_admin

    sb = get_supabase_admin()
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
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Full name cannot be empty."
        )
    if len(name) > 100:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Full name must be 100 characters or fewer.",
        )

    from ..services.supabase_client import get_supabase_admin

    sb = get_supabase_admin()
    # Verify the update actually hit a row. If the eq filter matched
    # zero rows (e.g. user.id mismatch between auth and public schemas)
    # supabase silently returns 200 with `data=[]`. Without this guard
    # the dashboard's optimistic update would say "saved" while the DB
    # still holds the old value — exactly the bug we're closing.
    res = (
        sb.table("users")
        .update(
            {
                "full_name": name,
                "updated_at": datetime.now(UTC).isoformat(),
            }
        )
        .eq("id", user.id)
        .execute()
    )
    if not res.data:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Profile update did not persist (no matching user row).",
        )

    return {"full_name": name}
