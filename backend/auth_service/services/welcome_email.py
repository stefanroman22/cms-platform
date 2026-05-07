"""Welcome email template + Resend POST helper.

Source of truth for the HTML that lands in a new client's inbox after
the CMS Connector agent finishes provisioning. Lives next to the code
that sends it (was previously in agents/CMS Connector - Website/phases/
6-confirmation.md).
"""

from __future__ import annotations

import html
import json
import urllib.error
import urllib.request

from ..core.config import settings


def _safe_url(value: str, fallback: str = "https://roman-technologies.dev") -> str:
    """Returns `value` if it is an http(s) URL; otherwise the fallback.
    Closes the BE-006 angle: a CMS field containing `javascript:alert()` or
    a `data:` URL renders as an inert link rather than executable bait."""
    v = (value or "").strip()
    if v.startswith("http://") or v.startswith("https://"):
        return v
    return fallback


def render_welcome_html(
    *,
    full_name: str,
    project_name: str,
    website_url: str,
    login_url: str,
) -> str:
    """Renders the welcome HTML. Inline styles only — most email clients
    strip <style>. Plain HTML, no JS, no remote fonts.

    All caller-controlled fields are HTML-escaped (BE-006); URL fields
    additionally checked for http(s) scheme via `_safe_url`."""
    greeting = html.escape(full_name) if full_name else "there"
    project = html.escape(project_name)
    website = _safe_url(website_url)
    website_text = html.escape(website)
    login = _safe_url(login_url, fallback="https://roman-technologies.dev/log-in")
    return f"""<!doctype html><html><body style="font-family:system-ui,-apple-system,sans-serif;color:#1f2937;line-height:1.6;max-width:560px;margin:0 auto;padding:24px">
<h1 style="font-size:20px;margin:0 0 16px">Welcome to Roman Technologies CMS</h1>
<p>Hi {greeting},</p>
<p>Your project <strong>{project}</strong> is live on <a href="{website}" style="color:#0369a1">{website_text}</a> and ready for content edits.</p>
<p style="margin:24px 0"><a href="{login}" style="background:#111827;color:white;padding:10px 18px;border-radius:8px;text-decoration:none;display:inline-block">Open the CMS dashboard →</a></p>
<p>You can sign in with the email address this message was sent to. Use the password your developer shared with you, then change it from the Account Settings page.</p>
<p style="font-size:13px;color:#6b7280;margin-top:32px">Roman Technologies — stefanromanpers@gmail.com</p>
</body></html>"""


def send_welcome_email(
    *,
    to_email: str,
    full_name: str | None,
    project_name: str,
    website_url: str,
    login_url: str = "https://roman-technologies.dev/log-in",
) -> dict:
    """POSTs to api.resend.com/emails. Returns parsed JSON on 200,
    raises RuntimeError with status + body on any other status."""
    # TEST-002 — preview-tier short-circuit on E2E marker.
    from .e2e_email_guard import short_circuit_response, should_short_circuit

    if should_short_circuit(to_email, full_name or "", project_name, website_url):
        return short_circuit_response(f"welcome:{to_email}")

    if not settings.RESEND_API_KEY:
        raise RuntimeError("RESEND_API_KEY not configured on this backend")

    body = {
        "from": f"{settings.RESEND_FROM_NAME} <{settings.RESEND_FROM_EMAIL}>",
        "to": to_email,
        "subject": f"Your {project_name} CMS is ready",
        "html": render_welcome_html(
            full_name=full_name or "",
            project_name=project_name,
            website_url=website_url,
            login_url=login_url,
        ),
    }
    req = urllib.request.Request(
        "https://api.resend.com/emails",
        data=json.dumps(body).encode(),
        headers={
            "Authorization": f"Bearer {settings.RESEND_API_KEY}",
            "Content-Type": "application/json",
            # api.resend.com sits behind Cloudflare, which 403s
            # User-Agent-less requests with error code 1010. Setting a
            # real-looking UA is the documented workaround.
            "User-Agent": "roman-technologies-cms-backend/1.0",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode() or "{}")
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"Resend {e.code}: {e.read().decode()}") from e
