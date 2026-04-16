import os
from pathlib import Path
from typing import Optional, Tuple

from jose import jwt, JWTError
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.request import Request


PUBLIC_KEY_PATH = os.environ.get(
    "JWT_PUBLIC_KEY_PATH",
    str(Path(__file__).resolve().parent.parent / "keys" / "public.pem"),
)
JWT_ALGORITHM = "RS256"

_public_key: Optional[str] = None


def _get_public_key() -> str:
    global _public_key
    if _public_key is None:
        _public_key = Path(PUBLIC_KEY_PATH).read_text()
    return _public_key


class JWTUser:
    """Minimal user object attached to request.user after JWT validation."""
    def __init__(self, user_id: str, email: str):
        self.id = user_id
        self.email = email
        self.is_authenticated = True
        self.is_anonymous = False

    def __str__(self):
        return self.email


class JWTAuthentication(BaseAuthentication):
    def authenticate(self, request: Request) -> Optional[Tuple[JWTUser, str]]:
        token = self._extract_token(request)
        if token is None:
            return None

        try:
            payload = jwt.decode(token, _get_public_key(), algorithms=[JWT_ALGORITHM])
        except JWTError:
            raise AuthenticationFailed("Invalid or expired token")

        if payload.get("type") != "access":
            raise AuthenticationFailed("Invalid token type")

        user = JWTUser(user_id=payload["sub"], email=payload["email"])
        return (user, token)

    def _extract_token(self, request: Request) -> Optional[str]:
        # 1. HttpOnly cookie (preferred)
        token = request.COOKIES.get("access_token")
        if token:
            return token
        # 2. Authorization: Bearer <token> header (for API clients)
        auth_header = request.META.get("HTTP_AUTHORIZATION", "")
        if auth_header.startswith("Bearer "):
            return auth_header[7:]
        return None
