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

    # Revoke ALL sessions (including this one) and mint a fresh session
    await revoke_all_for_user(user.id)
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
