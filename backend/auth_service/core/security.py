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
