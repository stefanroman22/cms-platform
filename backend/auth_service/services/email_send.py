"""One Resend POST for the account + reminder emails (Resend over urllib, no SDK)."""

from __future__ import annotations

import json
import urllib.error
import urllib.request

from ..core.config import settings


def send_via_resend(
    *,
    to_email: str,
    subject: str,
    html_body: str,
    text_body: str,
    from_name: str | None = None,
    reply_to: str | None = None,
) -> dict:
    """POST one email to api.resend.com. Returns Resend's JSON on success and
    raises ``RuntimeError`` on a missing key or any non-2xx status."""
    if not settings.RESEND_API_KEY:
        raise RuntimeError("RESEND_API_KEY not configured on this backend")

    body: dict = {
        "from": f"{from_name or settings.RESEND_FROM_NAME} <{settings.RESEND_FROM_EMAIL}>",
        "to": to_email,
        "subject": subject,
        "html": html_body,
        "text": text_body,
    }
    if reply_to:
        body["reply_to"] = reply_to
    req = urllib.request.Request(
        "https://api.resend.com/emails",
        data=json.dumps(body).encode(),
        headers={
            "Authorization": f"Bearer {settings.RESEND_API_KEY}",
            "Content-Type": "application/json",
            # api.resend.com sits behind Cloudflare, which 403s User-Agent-less
            # requests (error 1010). A real-looking UA is the documented fix.
            "User-Agent": "roman-technologies-cms-backend/1.0",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode() or "{}")
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"Resend {e.code}: {e.read().decode()}") from e
