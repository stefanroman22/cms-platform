"""Shared branded email chrome — the zinc-900 header + footer used by every
transactional email (booking confirmation / reminder / manage, client welcome,
password changed). Inline styles only (mail clients strip <style>). New emails
compose ``shell(header + accent_rule + <blocks> + footer)`` from the helpers
below; don't hand-roll a standalone template.

New in P4: optional Brand dataclass. All new params default to DEFAULT_BRAND
(Roman Technologies), so the issue-resolved and any other existing callers that
pass no brand argument produce byte-for-byte identical output."""

from __future__ import annotations

import html
import re
import urllib.parse
from dataclasses import dataclass
from datetime import datetime

CANONICAL_URL = "https://roman-technologies.dev"

# A CSS hex colour literal — the only shape a tenant accent is allowed to take, so
# it can never break out of the style="background:{accent}" attribute (SEC-045).
_HEX_COLOUR_RE = re.compile(r"#[0-9a-fA-F]{3,8}")


@dataclass(frozen=True)
class Brand:
    """Per-tenant email branding. Fields map directly to booking_settings columns."""

    business_name: str
    logo_url: str
    accent: str  # CSS hex colour for the header background
    canonical_url: str


DEFAULT_BRAND = Brand(
    business_name="Roman Technologies",
    logo_url=f"{CANONICAL_URL}/logo_dark.png",
    accent="#18181b",
    canonical_url=CANONICAL_URL,
)


def google_calendar_url(
    *, title: str, start_utc: datetime, end_utc: datetime, details: str, location: str
) -> str:
    """A pre-filled 'Add to Google Calendar' link (no API needed). The invitee
    clicks it to drop the event on their own calendar."""
    params = {
        "action": "TEMPLATE",
        "text": title,
        "dates": f"{start_utc.strftime('%Y%m%dT%H%M%SZ')}/{end_utc.strftime('%Y%m%dT%H%M%SZ')}",
        "details": details,
        "location": location,
    }
    return "https://calendar.google.com/calendar/render?" + urllib.parse.urlencode(params)


def safe_url(value: str | None, fallback: str = "") -> str:
    """Return ``value`` only if it is an http(s) URL, else ``fallback``.

    Mirrors issue_resolved_email's guard (BE-006): keeps a ``javascript:`` or
    ``data:`` URL from rendering as an executable link in an email href.
    """
    v = (value or "").strip()
    if v.startswith("http://") or v.startswith("https://"):
        return v
    return fallback


def safe_hex(value: str | None, fallback: str) -> str:
    """A CSS hex colour literal or ``fallback`` (SEC-045).

    The single allowlist used everywhere a tenant-controlled colour is emitted
    into a ``style`` attribute — the tenant accent and the per-field text colours
    in ``email_copy`` both go through here, so an arbitrary string can never break
    out of the style attribute.
    """
    v = (value or "").strip()
    return v if _HEX_COLOUR_RE.fullmatch(v) else fallback


def _safe_accent(value: str) -> str:
    """Tenant accent colour, restricted to a hex literal (SEC-045)."""
    return safe_hex(value, DEFAULT_BRAND.accent)


def header(
    subtitle: str, *, brand: Brand = DEFAULT_BRAND, subtitle_color: str | None = None
) -> str:
    # SEC-044 / SEC-045: business_name, logo_url, accent and the subtitle (tenant
    # email_copy) are tenant-controlled. Escape text, allowlist the accent colour,
    # and force logo_url to an http(s) URL so none can break out of the markup.
    accent = _safe_accent(brand.accent)
    logo = html.escape(safe_url(brand.logo_url, DEFAULT_BRAND.logo_url), quote=True)
    business_name = html.escape(brand.business_name)
    subtitle = html.escape(subtitle)
    # Per-field colour override for the subtitle (email_copy "{key}__color"), else a
    # soft muted-white that stays legible on any accent (SEC-045 allowlists the hex).
    sub_color = safe_hex(subtitle_color, "#d4d4d8")
    return f"""<tr><td style="background:{accent};padding:26px 32px">
  <table cellpadding="0" cellspacing="0"><tr>
    <td width="46" height="46" valign="middle" style="background:rgba(255,255,255,0.12);border-radius:11px">
      <img src="{logo}" width="46" height="46" alt="" style="display:block;border:0;border-radius:11px">
    </td>
    <td style="vertical-align:middle;padding-left:14px">
      <p style="margin:0;color:#fff;font-size:18px;font-weight:600;letter-spacing:-0.01em">{business_name}</p>
      <p style="margin:3px 0 0;color:{sub_color};font-size:12px;letter-spacing:0.02em">{subtitle}</p>
    </td>
  </tr></table>
</td></tr>"""


def accent_rule(*, brand: Brand = DEFAULT_BRAND) -> str:
    """A thin accent bar directly under the header — carries the tenant colour
    into the body so the email reads as on-brand, not just a dark header strip."""
    accent = _safe_accent(brand.accent)
    return f'<tr><td style="height:4px;background:{accent};line-height:4px;font-size:0">&nbsp;</td></tr>'


def footer(*, brand: Brand = DEFAULT_BRAND) -> str:
    canonical = safe_url(brand.canonical_url, DEFAULT_BRAND.canonical_url)
    domain = html.escape(canonical.removeprefix("https://").removeprefix("http://"))
    business_name = html.escape(brand.business_name)
    return f"""<tr><td style="padding:32px 32px 28px;border-top:1px solid #f4f4f5">
  <p style="margin:0;font-size:12px;color:#a1a1aa;line-height:1.5">
    Sent from <a href="{html.escape(canonical, quote=True)}" style="color:#71717a;text-decoration:none">{domain}</a> &middot;
    &copy; 2026 {business_name}
  </p>
</td></tr>"""


# ---- body building blocks -------------------------------------------------
#
# Every argument named ``*_html`` must already be safe markup: escape untrusted
# text with ``html.escape`` (or ``booking_i18n.tt``) before passing it in. URLs
# and colours are sanitised here, so callers can pass them raw.


def heading(text_html: str, *, color: str = "#18181b") -> str:
    color = safe_hex(color, "#18181b")
    return (
        '<tr><td style="padding:32px 32px 4px">'
        f'<h1 style="margin:0;font-size:23px;font-weight:600;letter-spacing:-0.01em;'
        f'line-height:1.3;color:{color}">{text_html}</h1></td></tr>'
    )


def paragraph(text_html: str, *, color: str = "#52525b", size: int = 15) -> str:
    color = safe_hex(color, "#52525b")
    return (
        f'<tr><td style="padding:12px 32px 0"><p style="margin:0;font-size:{int(size)}px;'
        f'line-height:1.6;color:{color}">{text_html}</p></td></tr>'
    )


def detail_box(rows: list[tuple[str, str]]) -> str:
    """Grey key/value card. ``rows`` = [(label_html, value_html), ...]."""
    if not rows:
        return ""
    last = len(rows) - 1
    body = "".join(
        f'<p style="margin:0 0 4px;font-size:11px;font-weight:700;letter-spacing:0.08em;'
        f'text-transform:uppercase;color:#71717a">{label}</p>'
        f'<p style="margin:0 0 {0 if i == last else 14}px;font-size:15px;line-height:1.5;'
        f'color:#18181b">{value}</p>'
        for i, (label, value) in enumerate(rows)
    )
    return (
        '<tr><td style="padding:20px 32px 4px"><table width="100%" cellpadding="0" cellspacing="0" '
        'style="background:#fafafa;border:1px solid #ececee;border-radius:10px">'
        f'<tr><td style="padding:18px 22px">{body}</td></tr></table></td></tr>'
    )


def button(
    url: str,
    label_html: str,
    *,
    accent: str = DEFAULT_BRAND.accent,
    text_color: str = "#ffffff",
    outline: bool = False,
) -> str:
    """A centred call-to-action. Returns "" when ``url`` is not http(s)."""
    safe = safe_url(url)
    if not safe:
        return ""
    accent = _safe_accent(accent)
    text_color = safe_hex(text_color, "#ffffff")
    bg = "#ffffff" if outline else accent
    return (
        '<tr><td style="padding:24px 32px 4px" align="center">'
        f'<a href="{html.escape(safe, quote=True)}" style="display:inline-block;background:{bg};'
        f"border:1px solid {accent};color:{text_color};text-decoration:none;font-size:14px;"
        f'font-weight:600;padding:13px 28px;border-radius:9px">{label_html}</a></td></tr>'
    )


def callout(text_html: str) -> str:
    """A quiet bordered note for secondary-but-important information."""
    return (
        '<tr><td style="padding:24px 32px 0"><table width="100%" cellpadding="0" cellspacing="0" '
        'style="border-left:3px solid #d4d4d8"><tr><td style="padding:2px 0 2px 14px">'
        f'<p style="margin:0;font-size:13px;line-height:1.6;color:#71717a">{text_html}</p>'
        "</td></tr></table></td></tr>"
    )


def spacer(px: int = 32) -> str:
    """Vertical breathing room, e.g. between the last block and the footer rule."""
    return (
        f'<tr><td style="height:{int(px)}px;line-height:{int(px)}px;font-size:0">&nbsp;</td></tr>'
    )


def _preheader(text: str) -> str:
    """Hidden inbox-preview line (the grey snippet next to the subject)."""
    return (
        '<div style="display:none;max-height:0;overflow:hidden;opacity:0;color:transparent">'
        f"{html.escape(text)}</div>"
    )


def shell(inner: str, *, preheader: str = "") -> str:
    pre = _preheader(preheader) if preheader else ""
    return f"""<!DOCTYPE html><html lang="en"><head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:0;background:#fafafa;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif;color:#27272a">{pre}
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#fafafa;padding:44px 20px"><tr><td align="center">
    <table width="600" cellpadding="0" cellspacing="0" style="max-width:600px;width:100%;background:#fff;border:1px solid #ececee;border-radius:14px;overflow:hidden;box-shadow:0 1px 3px rgba(24,24,27,0.06)">
      {inner}
    </table>
  </td></tr></table>
</body></html>"""
