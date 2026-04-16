from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Response, Request, status

from ..models.schemas import LoginRequest, TokenResponse, UserOut, ChangePasswordRequest, ChangeNameRequest
from ..services.auth_service import (
    authenticate_user,
    issue_tokens,
    refresh_access_token,
    revoke_refresh_token,
    get_user_from_access_token,
    change_user_password,
)
from ..core.config import settings

router = APIRouter(prefix="/auth", tags=["auth"])

REFRESH_COOKIE = "refresh_token"
ACCESS_COOKIE = "access_token"
IS_PROD = settings.ENVIRONMENT == "production"


def _set_auth_cookies(response: Response, access_token: str, raw_refresh: str, refresh_expires: datetime):
    response.set_cookie(
        key=ACCESS_COOKIE,
        value=access_token,
        httponly=True,
        secure=IS_PROD,
        samesite="lax",
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        path="/",
    )
    response.set_cookie(
        key=REFRESH_COOKIE,
        value=raw_refresh,
        httponly=True,
        secure=IS_PROD,
        samesite="lax",
        max_age=int((refresh_expires - datetime.now(timezone.utc)).total_seconds()),
        path="/",
    )


def _clear_auth_cookies(response: Response):
    response.delete_cookie(ACCESS_COOKIE, path="/")
    response.delete_cookie(REFRESH_COOKIE, path="/")


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest, response: Response):
    user = await authenticate_user(body.email, body.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    access_token, raw_refresh, refresh_expires = await issue_tokens(user, body.remember_me)
    _set_auth_cookies(response, access_token, raw_refresh, refresh_expires)
    return TokenResponse(access_token=access_token)


@router.post("/refresh", response_model=TokenResponse)
async def refresh(request: Request, response: Response):
    raw_refresh = request.cookies.get(REFRESH_COOKIE)
    if not raw_refresh:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="No refresh token")

    result = await refresh_access_token(raw_refresh)
    if not result:
        _clear_auth_cookies(response)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired refresh token")

    access_token, new_raw_refresh, new_expires = result
    _set_auth_cookies(response, access_token, new_raw_refresh, new_expires)
    return TokenResponse(access_token=access_token)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(request: Request, response: Response):
    raw_refresh = request.cookies.get(REFRESH_COOKIE)
    if raw_refresh:
        await revoke_refresh_token(raw_refresh)
    _clear_auth_cookies(response)


@router.get("/me", response_model=UserOut)
async def me(request: Request):
    token = request.cookies.get(ACCESS_COOKIE)
    if not token:
        # Also accept Bearer token in Authorization header
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]

    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    user = await get_user_from_access_token(token)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")

    return user


@router.post("/change-password", status_code=status.HTTP_204_NO_CONTENT)
async def change_password(body: ChangePasswordRequest, request: Request):
    token = request.cookies.get(ACCESS_COOKIE)
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    user = await get_user_from_access_token(token)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")

    if len(body.new_password) < 8:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="New password must be at least 8 characters.")

    success = await change_user_password(user.id, body.current_password, body.new_password)
    if not success:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Current password is incorrect.")


@router.patch("/profile", status_code=status.HTTP_200_OK)
async def update_profile(body: ChangeNameRequest, request: Request):
    token = request.cookies.get(ACCESS_COOKIE)
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    user = await get_user_from_access_token(token)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")

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
