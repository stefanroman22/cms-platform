"""Shared branded email chrome — the zinc-900 header + footer used by the
issue-resolved, booking confirmation, and reminder emails. Inline styles only
(mail clients strip <style>).

New in P4: optional Brand dataclass. All new params default to DEFAULT_BRAND
(Roman Technologies), so the issue-resolved and any other existing callers that
pass no brand argument produce byte-for-byte identical output."""

from __future__ import annotations

import urllib.parse
from dataclasses import dataclass
from datetime import datetime

CANONICAL_URL = "https://roman-technologies.dev"


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


def header(subtitle: str, *, brand: Brand = DEFAULT_BRAND) -> str:
    return f"""<tr><td style="background:{brand.accent};padding:24px 32px">
  <table cellpadding="0" cellspacing="0"><tr>
    <td width="44" height="44" valign="middle" style="background:{brand.accent};border-radius:10px">
      <img src="{brand.logo_url}" width="44" height="44" alt="" style="display:block;border:0;border-radius:10px">
    </td>
    <td style="vertical-align:middle;padding-left:14px">
      <p style="margin:0;color:#fff;font-size:18px;font-weight:600;letter-spacing:-0.01em">{brand.business_name}</p>
      <p style="margin:2px 0 0;color:#a1a1aa;font-size:12px">{subtitle}</p>
    </td>
  </tr></table>
</td></tr>"""


def footer(*, brand: Brand = DEFAULT_BRAND) -> str:
    domain = brand.canonical_url.removeprefix("https://").removeprefix("http://")
    return f"""<tr><td style="padding:32px 32px 28px;border-top:1px solid #f4f4f5">
  <p style="margin:0;font-size:12px;color:#a1a1aa;line-height:1.5">
    Sent from <a href="{brand.canonical_url}" style="color:#71717a;text-decoration:none">{domain}</a> &middot;
    &copy; 2026 {brand.business_name}
  </p>
</td></tr>"""


def shell(inner: str) -> str:
    return f"""<!DOCTYPE html><html lang="en"><head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:0;background:#f5f5f4;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif;color:#27272a">
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#f5f5f4;padding:40px 20px"><tr><td align="center">
    <table width="600" cellpadding="0" cellspacing="0" style="max-width:600px;width:100%;background:#fff;border:1px solid #e4e4e7;border-radius:12px;overflow:hidden">
      {inner}
    </table>
  </td></tr></table>
</body></html>"""
