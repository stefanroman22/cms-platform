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
    """Renders the HTML body. Matches the welcome-email template
    (Resend id 758f9a34-4b5e-49d4-b464-fe92f7363a6f) — same zinc-900
    header with the inline cube SVG, "Roman Technologies / Client
    Portal" eyebrow, and #fafafa boxed sections."""
    name_safe = _escape_html(requester_name or "Unnamed")
    email_safe = _escape_html(requester_email)
    project_safe = _escape_html(project_name)
    type_safe = _escape_html(_label(PROJECT_TYPE_LABELS, project_type))
    budget_safe = _escape_html(_label(BUDGET_LABELS, budget))
    timeline_safe = _escape_html(_label(TIMELINE_LABELS, timeline))
    description_html = _escape_html(description).replace("\n", "<br>")

    return f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:0;background:#f5f5f4;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif;color:#27272a">
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#f5f5f4;padding:40px 20px">
    <tr><td align="center">
      <table width="600" cellpadding="0" cellspacing="0" style="max-width:600px;width:100%;background:#fff;border:1px solid #e4e4e7;border-radius:12px;overflow:hidden">
        <tr><td style="background:#18181b;padding:24px 32px">
          <table cellpadding="0" cellspacing="0">
            <tr>
              <td width="44" height="44" valign="middle" style="background:#18181b;border-radius:10px">
                <img src="https://roman-technologies.dev/logo_dark.png" width="44" height="44" alt="" style="display:block;border:0;outline:none;text-decoration:none;border-radius:10px">
              </td>
              <td style="vertical-align:middle;padding-left:14px">
                <p style="margin:0;color:#fff;font-size:18px;font-weight:600;letter-spacing:-0.01em">Roman Technologies</p>
                <p style="margin:2px 0 0;color:#a1a1aa;font-size:12px">Client Portal</p>
              </td>
            </tr>
          </table>
        </td></tr>
        <tr><td style="padding:32px 32px 8px">
          <h1 style="margin:0 0 12px;font-size:22px;font-weight:600;color:#18181b">New project request.</h1>
          <p style="margin:0;font-size:15px;line-height:1.55;color:#52525b">
            A new project request just came in from <strong>{name_safe}</strong>.
            The full submission is below — hit Reply to respond directly to
            the client and they will receive your message in their inbox.
          </p>
        </td></tr>
        <tr><td style="padding:8px 32px">
          <table width="100%" cellpadding="0" cellspacing="0" style="margin-top:16px;background:#fafafa;border:1px solid #e4e4e7;border-radius:8px">
            <tr><td style="padding:18px 22px">
              <p style="margin:0 0 12px;font-size:11px;font-weight:600;letter-spacing:0.08em;text-transform:uppercase;color:#71717a">Request details</p>
              <table cellpadding="0" cellspacing="0" style="font-size:14px;line-height:1.5;width:100%">
                <tr>
                  <td style="padding:4px 12px 4px 0;color:#52525b;width:120px;vertical-align:top">From</td>
                  <td style="color:#18181b;word-break:break-all"><a href="mailto:{email_safe}" style="color:#18181b;text-decoration:none">{name_safe} &lt;{email_safe}&gt;</a></td>
                </tr>
                <tr>
                  <td style="padding:4px 12px 4px 0;color:#52525b;vertical-align:top">Project name</td>
                  <td style="color:#18181b;font-weight:600">{project_safe}</td>
                </tr>
                <tr>
                  <td style="padding:4px 12px 4px 0;color:#52525b;vertical-align:top">Type</td>
                  <td style="color:#18181b">{type_safe}</td>
                </tr>
                <tr>
                  <td style="padding:4px 12px 4px 0;color:#52525b;vertical-align:top">Budget</td>
                  <td style="color:#18181b">{budget_safe}</td>
                </tr>
                <tr>
                  <td style="padding:4px 12px 4px 0;color:#52525b;vertical-align:top">Timeline</td>
                  <td style="color:#18181b">{timeline_safe}</td>
                </tr>
              </table>
            </td></tr>
          </table>
        </td></tr>
        <tr><td style="padding:8px 32px">
          <table width="100%" cellpadding="0" cellspacing="0" style="margin-top:16px;background:#fafafa;border:1px solid #e4e4e7;border-radius:8px">
            <tr><td style="padding:18px 22px">
              <p style="margin:0 0 10px;font-size:11px;font-weight:600;letter-spacing:0.08em;text-transform:uppercase;color:#71717a">Description</p>
              <p style="margin:0;font-size:14px;line-height:1.6;color:#27272a">{description_html}</p>
            </td></tr>
          </table>
          <p style="margin:14px 0 0;font-size:13px;line-height:1.5;color:#92400e;background:#fef3c7;border-left:3px solid #f59e0b;padding:10px 14px;border-radius:0 6px 6px 0">
            <strong>Reply directly</strong> to this email to write back to <a href="mailto:{email_safe}" style="color:#92400e;text-decoration:underline">{email_safe}</a>.
          </p>
        </td></tr>
        <tr><td style="padding:24px 32px 8px" align="center">
          <a href="mailto:{email_safe}" style="display:inline-block;background:#18181b;color:#fff;text-decoration:none;font-size:14px;font-weight:600;padding:12px 28px;border-radius:8px">Reply to {name_safe} &rarr;</a>
        </td></tr>
        <tr><td style="padding:32px 32px 28px;border-top:1px solid #f4f4f5">
          <p style="margin:0;font-size:12px;color:#a1a1aa;line-height:1.5">
            Sent from <a href="https://roman-technologies.dev" style="color:#71717a;text-decoration:none">roman-technologies.dev</a> &middot;
            &copy; 2026 Roman Technologies &middot; Client Portal
          </p>
        </td></tr>
      </table>
    </td></tr>
  </table>
</body>
</html>"""


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
    # TEST-002 — preview-tier short-circuit on E2E marker.
    from .e2e_email_guard import short_circuit_response, should_short_circuit

    if should_short_circuit(requester_email, requester_name or "", project_name, description):
        return short_circuit_response(f"project_request:{requester_email}")

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
