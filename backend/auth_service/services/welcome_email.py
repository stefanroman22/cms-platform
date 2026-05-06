"""Welcome email template + Resend POST helper.

Source of truth for the HTML that lands in a new client's inbox after
the CMS Connector agent finishes provisioning. Lives next to the code
that sends it (was previously in agents/CMS Connector - Website/phases/
6-confirmation.md).
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request

from ..core.config import settings


def render_welcome_html(
    *,
    full_name: str,
    project_name: str,
    website_url: str,
    login_url: str,
) -> str:
    """Renders the welcome HTML. Inline styles only — most email clients
    strip <style>. Plain HTML, no JS, no remote fonts."""
    greeting = full_name or "there"
    return f"""<!doctype html><html><body style="font-family:system-ui,-apple-system,sans-serif;color:#1f2937;line-height:1.6;max-width:560px;margin:0 auto;padding:24px">
<h1 style="font-size:20px;margin:0 0 16px">Welcome to Roman Technologies CMS</h1>
<p>Hi {greeting},</p>
<p>Your project <strong>{project_name}</strong> is live on <a href="{website_url}" style="color:#0369a1">{website_url}</a> and ready for content edits.</p>
<p style="margin:24px 0"><a href="{login_url}" style="background:#111827;color:white;padding:10px 18px;border-radius:8px;text-decoration:none;display:inline-block">Open the CMS dashboard →</a></p>
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
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode() or "{}")
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"Resend {e.code}: {e.read().decode()}") from e
