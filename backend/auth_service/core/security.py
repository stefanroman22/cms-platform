import secrets
import hashlib
from datetime import datetime, timedelta, timezone
from typing import Optional

from jose import jwt, JWTError

from .config import settings


def create_access_token(user_id: str, email: str, is_admin: bool = False) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {
        "sub": user_id,
        "email": email,
        "is_admin": is_admin,
        "type": "access",
        "exp": expire,
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, settings.private_key, algorithm=settings.JWT_ALGORITHM)


def create_refresh_token(remember_me: bool = False) -> tuple[str, datetime]:
    """Returns (raw_token, expires_at). Store only the hash in DB."""
    raw_token = secrets.token_urlsafe(64)
    days = (
        settings.REFRESH_TOKEN_EXPIRE_DAYS_REMEMBER_ME
        if remember_me
        else settings.REFRESH_TOKEN_EXPIRE_DAYS_DEFAULT
    )
    expires_at = datetime.now(timezone.utc) + timedelta(days=days)
    return raw_token, expires_at


def hash_token(raw_token: str) -> str:
    """SHA-256 hash of the raw token — stored in DB, never the raw token."""
    return hashlib.sha256(raw_token.encode()).hexdigest()


def decode_access_token(token: str) -> Optional[dict]:
    try:
        payload = jwt.decode(token, settings.public_key, algorithms=[settings.JWT_ALGORITHM])
        if payload.get("type") != "access":
            return None
        return payload
    except JWTError:
        return None
