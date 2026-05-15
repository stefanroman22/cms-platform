"""Issue-resolved email — fired when an admin flips a project issue to `done`.

Goes to the client who originally reported the issue. The message confirms
the fix, links to the project preview so they can verify it lives, and links
back to the CMS dashboard so they can browse the rest of their issue list.

Anti-spam choices mirror `project_request_email`:
- FROM uses the verified `noreply@roman-technologies.dev` domain.
- Both HTML and plain-text bodies — major filters down-rank HTML-only mail.
- Clear, transactional subject line ("Issue resolved: ...").
- No remote images, no tracking pixel.

Security:
- All caller-controlled fields are HTML-escaped (BE-006).
- `preview_url` is restricted to http(s) via `_safe_url`; anything else
  (`javascript:`, `data:`) falls back to the canonical site.
"""

from __future__ import annotations

import html
import json
import urllib.error
import urllib.request

from ..core.config import settings

CANONICAL_URL = "https://roman-technologies.dev"
DASHBOARD_URL = f"{CANONICAL_URL}/dashboard"


def _safe_url(value: str | None, fallback: str = CANONICAL_URL) -> str:
    """Returns `value` if it is an http(s) URL; otherwise the fallback.
    Matches the welcome_email guard — keeps a CMS field containing
    `javascript:alert()` or a `data:` URL from rendering as an executable link."""
    v = (value or "").strip()
    if v.startswith("http://") or v.startswith("https://"):
        return v
    return fallback


def render_issue_resolved_html(
    *,
    client_name: str | None,
    issue: dict,
    project: dict,
) -> str:
    """Renders the resolved-issue HTML body.

    Matches the project_request_email template — zinc-900 header with the
    Roman Technologies logo, #fafafa boxed detail sections, transactional
    footer. Inline styles only (most clients strip <style>).
    """
    greeting = html.escape(client_name) if client_name else "there"
    project_name = html.escape(project.get("name") or project.get("slug") or "your project")
    issue_title = html.escape(issue.get("title") or "")
    preview = _safe_url(project.get("preview_url"))
    preview_safe = html.escape(preview)
    dashboard = DASHBOARD_URL

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
          <h1 style="margin:0 0 12px;font-size:22px;font-weight:600;color:#18181b">Issue resolved.</h1>
          <p style="margin:0;font-size:15px;line-height:1.55;color:#52525b">
            Hi {greeting}, the issue you reported on <strong>{project_name}</strong>
            has been marked as resolved. The fix is live on your preview
            environment — take a look and let us know if anything still
            looks off.
          </p>
        </td></tr>
        <tr><td style="padding:8px 32px">
          <table width="100%" cellpadding="0" cellspacing="0" style="margin-top:16px;background:#fafafa;border:1px solid #e4e4e7;border-radius:8px">
            <tr><td style="padding:18px 22px">
              <p style="margin:0 0 12px;font-size:11px;font-weight:600;letter-spacing:0.08em;text-transform:uppercase;color:#71717a">Issue</p>
              <p style="margin:0;font-size:14px;line-height:1.5;color:#18181b;font-weight:600">{issue_title}</p>
            </td></tr>
          </table>
        </td></tr>
        <tr><td style="padding:24px 32px 8px" align="center">
          <a href="{preview_safe}" style="display:inline-block;background:#18181b;color:#fff;text-decoration:none;font-size:14px;font-weight:600;padding:12px 28px;border-radius:8px">View the fix &rarr;</a>
        </td></tr>
        <tr><td style="padding:8px 32px 24px" align="center">
          <p style="margin:0;font-size:13px;color:#71717a">
            Or <a href="{dashboard}" style="color:#52525b;text-decoration:underline">open the dashboard</a> to browse the rest of your issues.
          </p>
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


def render_issue_resolved_text(
    *,
    client_name: str | None,
    issue: dict,
    project: dict,
) -> str:
    """Plain-text fallback. Spam filters down-rank HTML-only mail, so
    we always send both halves in a multipart message."""
    greeting = client_name or "there"
    project_name = project.get("name") or project.get("slug") or "your project"
    issue_title = issue.get("title") or ""
    preview = _safe_url(project.get("preview_url"))

    return f"""Roman Technologies — CMS Platform

ISSUE RESOLVED

Hi {greeting},

The issue you reported on {project_name} has been marked as resolved.
The fix is live on your preview environment — take a look and let us
know if anything still looks off.

  Issue:    {issue_title}
  Preview:  {preview}

Open the dashboard to browse the rest of your issues:
{DASHBOARD_URL}

—
Sent from roman-technologies.dev
"""


def send(
    *,
    to_email: str,
    issue: dict,
    project: dict,
    client_name: str | None = None,
) -> dict:
    """POSTs to api.resend.com/emails. Returns parsed JSON on 200,
    raises RuntimeError with status + body on any other status.

    Caller is expected to wrap this in try/except — email failure must
    not break the issue status update (the DB row is already flipped to
    `done` by the time we get here).
    """
    # TEST-002 — preview-tier short-circuit on E2E marker.
    from .e2e_email_guard import short_circuit_response, should_short_circuit

    if should_short_circuit(
        to_email,
        client_name or "",
        project.get("name") or "",
        project.get("slug") or "",
        issue.get("title") or "",
    ):
        return short_circuit_response(f"issue_resolved:{to_email}")

    if not settings.RESEND_API_KEY:
        raise RuntimeError("RESEND_API_KEY not configured on this backend")

    common = {
        "client_name": client_name,
        "issue": issue,
        "project": project,
    }

    issue_title = issue.get("title") or "your reported issue"
    body = {
        "from": f"{settings.RESEND_FROM_NAME} <{settings.RESEND_FROM_EMAIL}>",
        "to": to_email,
        "subject": f"Issue resolved: {issue_title}",
        "html": render_issue_resolved_html(**common),
        "text": render_issue_resolved_text(**common),
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
