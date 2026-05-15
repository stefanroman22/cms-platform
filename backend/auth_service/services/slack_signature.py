"""Slack Events API HMAC-SHA-256 signature verification.

Slack signs each event request with the app's signing secret. We must
reject any request whose signature doesn't match. Also enforces a 5-min
replay window — old captured requests can't be replayed later.
"""

from __future__ import annotations

import hashlib
import hmac
import time

_REPLAY_WINDOW_S = 300


def verify(timestamp: str, body: bytes, signature: str, secret: str) -> bool:
    """Returns True iff signature is valid AND within the replay window."""
    if not timestamp or not signature or not secret:
        return False
    try:
        ts_int = int(timestamp)
    except (TypeError, ValueError):
        return False
    if abs(time.time() - ts_int) > _REPLAY_WINDOW_S:
        return False
    base = f"v0:{timestamp}:{body.decode('utf-8', errors='replace')}".encode()
    expected = "v0=" + hmac.new(secret.encode(), base, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)
