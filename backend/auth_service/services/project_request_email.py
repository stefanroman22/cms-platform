"""Project-request email — fired when a user submits the
"Create New Project" form in the dashboard.

Notification goes to the platform admin (stefanromanpers@gmail.com).
The requester is set as Reply-To so a single reply lands directly in
their inbox.

Anti-spam choices:
- FROM uses the verified `noreply@roman-technologies.dev` domain
  (DKIM/SPF/DMARC handled by Resend).
- Both HTML and plain-text bodies — major filters down-rank
  HTML-only mail.
- Clear, non-marketing subject line.
- No remote images, no tracking pixel — text-mark "Roman
  Technologies" logo rendered with inline CSS.
- Real, descriptive Reply-To header so this looks transactional.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request

from ..core.config import settings

ADMIN_EMAIL = "stefanromanpers@gmail.com"

PROJECT_TYPE_LABELS = {
    "website": "Website",
    "web_app": "Web Application",
    "mobile_app": "Mobile App",
    "other": "Other",
}
BUDGET_LABELS = {
    "under_1k": "Under €1,000",
    "1k_5k": "€1,000 – €5,000",
    "5k_20k": "€5,000 – €20,000",
    "20k_plus": "€20,000+",
}
TIMELINE_LABELS = {
    "asap": "As soon as possible",
    "1_month": "Within 1 month",
    "3_months": "Within 3 months",
    "6_months": "Within 6 months",
    "flexible": "Flexible",
}


def _label(d: dict[str, str], v: str | None, default: str = "Not specified") -> str:
    if not v:
        return default
    return d.get(v, v)


def _escape_html(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def render_project_request_html(
    *,
    requester_email: str,
    requester_name: str | None,
    project_name: str,
    project_type: str,
    description: str,
    budget: str | None,
    timeline: str | None,
) -> str:
    """Renders the HTML body. Inline styles only — no external CSS, no
    remote images. Header uses a CSS text-mark for the brand."""
    rows = [
        (
            "From",
            f"{_escape_html(requester_name or 'Unnamed')} &lt;{_escape_html(requester_email)}&gt;",
        ),
        ("Project name", _escape_html(project_name)),
        ("Type", _escape_html(_label(PROJECT_TYPE_LABELS, project_type))),
        ("Budget", _escape_html(_label(BUDGET_LABELS, budget))),
        ("Timeline", _escape_html(_label(TIMELINE_LABELS, timeline))),
    ]
    rows_html = "\n".join(
        "<tr>"
        f'<td style="padding:10px 14px;color:#6b7280;font-size:13px;width:140px;vertical-align:top;border-bottom:1px solid #f3f4f6">{label}</td>'
        f'<td style="padding:10px 14px;color:#1f2937;font-size:14px;font-weight:500;border-bottom:1px solid #f3f4f6">{value}</td>'
        "</tr>"
        for label, value in rows
    )
    description_html = _escape_html(description).replace("\n", "<br>")
    return f"""<!doctype html>
<html lang="en">
<head><meta charset="utf-8"><title>New project request</title></head>
<body style="margin:0;padding:0;background:#f9fafb;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;color:#1f2937">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="background:#f9fafb;padding:32px 16px">
  <tr><td align="center">
    <table role="presentation" width="600" cellpadding="0" cellspacing="0" border="0" style="max-width:600px;background:#ffffff;border-radius:12px;overflow:hidden;box-shadow:0 1px 3px rgba(0,0,0,0.06)">
      <tr><td style="padding:24px 32px;background:#111827;border-bottom:3px solid #f59e0b">
        <div style="font-family:Georgia,'Times New Roman',serif;font-size:20px;font-weight:600;color:#ffffff;letter-spacing:0.02em;line-height:1">Roman Technologies</div>
        <div style="font-size:11px;color:#9ca3af;text-transform:uppercase;letter-spacing:0.12em;margin-top:6px">CMS Platform</div>
      </td></tr>
      <tr><td style="padding:32px 32px 24px">
        <h1 style="font-size:18px;color:#111827;margin:0 0 6px;font-weight:600">New project request</h1>
        <p style="font-size:13px;color:#6b7280;margin:0;line-height:1.5">A client just submitted a project idea via the dashboard.</p>
      </td></tr>
      <tr><td style="padding:0 32px">
        <table role="presentation" cellpadding="0" cellspacing="0" border="0" style="width:100%;border-collapse:collapse;background:#fafafa;border-radius:8px;overflow:hidden;border:1px solid #f3f4f6">
          {rows_html}
        </table>
      </td></tr>
      <tr><td style="padding:24px 32px 8px">
        <h2 style="font-size:13px;color:#6b7280;margin:0 0 10px;font-weight:600;text-transform:uppercase;letter-spacing:0.06em">Description</h2>
        <div style="font-size:14px;color:#374151;line-height:1.65;background:#fafafa;padding:16px 18px;border-radius:8px;border-left:3px solid #f59e0b">{description_html}</div>
      </td></tr>
      <tr><td style="padding:24px 32px 32px">
        <p style="font-size:13px;color:#6b7280;margin:0;line-height:1.6">Hit <strong style="color:#374151">Reply</strong> to write back to <a href="mailto:{_escape_html(requester_email)}" style="color:#0369a1;text-decoration:none">{_escape_html(requester_email)}</a> directly.</p>
      </td></tr>
      <tr><td style="padding:14px 32px;background:#f9fafb;border-top:1px solid #e5e7eb;font-size:11px;color:#9ca3af;text-align:center">
        Sent from <a href="https://roman-technologies.dev" style="color:#6b7280;text-decoration:none">roman-technologies.dev</a>
      </td></tr>
    </table>
  </td></tr>
</table>
</body></html>"""


def render_project_request_text(
    *,
    requester_email: str,
    requester_name: str | None,
    project_name: str,
    project_type: str,
    description: str,
    budget: str | None,
    timeline: str | None,
) -> str:
    """Plain-text fallback. Spam filters down-rank HTML-only mail, so
    we always send both halves in a multipart message."""
    return f"""Roman Technologies — CMS Platform

NEW PROJECT REQUEST

A client just submitted a project idea via the dashboard.

  From:          {requester_name or 'Unnamed'} <{requester_email}>
  Project name:  {project_name}
  Type:          {_label(PROJECT_TYPE_LABELS, project_type)}
  Budget:        {_label(BUDGET_LABELS, budget)}
  Timeline:      {_label(TIMELINE_LABELS, timeline)}

Description:

{description}

Reply directly to this email to reach {requester_email}.

—
Sent from roman-technologies.dev
"""


def send_project_request_email(
    *,
    requester_email: str,
    requester_name: str | None,
    project_name: str,
    project_type: str,
    description: str,
    budget: str | None,
    timeline: str | None,
) -> dict:
    """POSTs to api.resend.com/emails. Returns parsed JSON on 200,
    raises RuntimeError with status + body on any other status.

    Caller is expected to wrap this in try/except and treat email
    failure as non-fatal — the project_request DB row has already
    been written."""
    if not settings.RESEND_API_KEY:
        raise RuntimeError("RESEND_API_KEY not configured on this backend")

    common = {
        "requester_email": requester_email,
        "requester_name": requester_name,
        "project_name": project_name,
        "project_type": project_type,
        "description": description,
        "budget": budget,
        "timeline": timeline,
    }

    body = {
        "from": f"{settings.RESEND_FROM_NAME} <{settings.RESEND_FROM_EMAIL}>",
        "to": ADMIN_EMAIL,
        "reply_to": requester_email,
        "subject": f"New project request: {project_name}",
        "html": render_project_request_html(**common),
        "text": render_project_request_text(**common),
    }
    req = urllib.request.Request(
        "https://api.resend.com/emails",
        data=json.dumps(body).encode(),
        headers={
            "Authorization": f"Bearer {settings.RESEND_API_KEY}",
            "Content-Type": "application/json",
            # api.resend.com sits behind Cloudflare, which 403s
            # User-Agent-less requests with error code 1010. Setting a
            # real-looking UA is the documented workaround (see
            # agents/CMS Connector - Website/LEARNINGS.md).
            "User-Agent": "roman-technologies-cms-backend/1.0",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode() or "{}")
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"Resend {e.code}: {e.read().decode()}") from e
