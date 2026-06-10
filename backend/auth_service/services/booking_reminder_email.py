"""~1h-before reminder email to the visitor. Same branded chrome; Resend-over-
urllib send with E2E guard (mirrors booking_email)."""

from __future__ import annotations

import html
import json
import urllib.error
import urllib.request

from ..core.config import settings
from . import email_layout
from .booking_i18n import copy_color, tt
from .email_layout import DEFAULT_BRAND, Brand


def render_html(
    *,
    name: str,
    when_label: str,
    note: str | None,
    meeting_url: str,
    manage_url: str = "",
    brand: Brand | None = None,
    locale: str = "en",
    copy: dict | None = None,
) -> str:
    _brand = brand if brand is not None else DEFAULT_BRAND
    accent = email_layout.safe_hex(_brand.accent, "#18181b")
    safe_name = html.escape(name)
    safe_when = html.escape(when_label)
    safe_note = html.escape(note or "—").replace("\n", "<br>")
    safe_meeting = email_layout.safe_url(meeting_url)
    if safe_meeting:
        esc = html.escape(safe_meeting)
        join_color = copy_color(copy, "join_cta", "#ffffff")
        cta = (
            '<tr><td style="padding:18px 32px 0" align="center">'
            '<p style="margin:0;font-size:13px;color:#71717a">Meeting link: '
            f'<a href="{esc}" style="color:{accent};text-decoration:underline">{esc}</a></p></td></tr>'
            '<tr><td style="padding:16px 32px 8px" align="center">'
            f'<a href="{esc}" style="display:inline-block;background:{accent};'
            f'color:{join_color};text-decoration:none;font-size:14px;font-weight:600;padding:13px 30px;border-radius:9px">'
            f'{tt(copy, locale, "join_cta")} &rarr;</a></td></tr>'
        )
    else:
        cta = ""
    box = (
        '<tr><td style="padding:8px 32px"><table width="100%" cellpadding="0" cellspacing="0" '
        'style="margin-top:16px;background:#fafafa;border:1px solid #ececee;border-radius:10px">'
        '<tr><td style="padding:18px 22px">'
        '<p style="margin:0 0 4px;font-size:11px;font-weight:700;letter-spacing:0.08em;text-transform:uppercase;color:#71717a">When</p>'
        f'<p style="margin:0 0 14px;font-size:15px;color:#18181b">{safe_when}</p>'
        '<p style="margin:0 0 4px;font-size:11px;font-weight:700;letter-spacing:0.08em;text-transform:uppercase;color:#71717a">Note</p>'
        f'<p style="margin:0;font-size:15px;color:#18181b">{safe_note}</p>'
        "</td></tr></table></td></tr>"
    )
    prompt_color = copy_color(copy, "manage_prompt", "#71717a")
    manage_color = copy_color(copy, "manage_cta", "#52525b")
    manage = ""
    safe_manage = email_layout.safe_url(manage_url)
    if safe_manage:
        manage = (
            '<tr><td style="padding:8px 32px 0" align="center">'
            f'<p style="margin:0;font-size:12px;color:{prompt_color}">{tt(copy, locale, "manage_prompt")} '
            f'<a href="{html.escape(safe_manage)}" style="color:{manage_color};text-decoration:underline">'
            f'{tt(copy, locale, "manage_cta")}</a>.</p></td></tr>'
        )
    sub_color = copy.get("header_reminder" + "__color") if copy else None
    heading_color = copy_color(copy, "reminder_heading", "#18181b")
    inner = (
        email_layout.header(
            tt(copy, locale, "header_reminder"), brand=_brand, subtitle_color=sub_color
        )
        + email_layout.accent_rule(brand=_brand)
        + f'<tr><td style="padding:32px 32px 8px"><h1 style="margin:0 0 12px;font-size:23px;font-weight:600;letter-spacing:-0.01em;color:{heading_color}">{tt(copy, locale, "reminder_heading", name=safe_name)}</h1></td></tr>'
        + box
        + cta
        + manage
        + email_layout.footer(brand=_brand)
    )
    return email_layout.shell(inner)


def render_text(*, name: str, when_label: str, note: str | None, meeting_url: str) -> str:
    link = f"Join: {meeting_url}\n" if meeting_url else ""
    return f"Reminder — your appointment is in about an hour.\n\nWhen: {when_label}\nNote: {note or '-'}\n{link}"


def send(
    *,
    to_email: str,
    name: str,
    when_label: str,
    note: str | None,
    meeting_url: str,
    manage_url: str = "",
    brand: Brand | None = None,
    locale: str = "en",
    copy: dict | None = None,
) -> dict:
    from .e2e_email_guard import short_circuit_response, should_short_circuit

    if should_short_circuit(to_email, name, when_label):
        return short_circuit_response(f"booking_reminder:{to_email}")
    if not settings.RESEND_API_KEY:
        raise RuntimeError("RESEND_API_KEY not configured on this backend")

    body = {
        "from": f"{settings.RESEND_FROM_NAME} <{settings.RESEND_FROM_EMAIL}>",
        "to": to_email,
        "subject": tt(copy, locale, "reminder_subject", html_escape=False),
        "html": render_html(
            name=name,
            when_label=when_label,
            note=note,
            meeting_url=meeting_url,
            manage_url=manage_url,
            brand=brand,
            locale=locale,
            copy=copy,
        ),
        "text": render_text(name=name, when_label=when_label, note=note, meeting_url=meeting_url),
    }
    req = urllib.request.Request(
        "https://api.resend.com/emails",
        data=json.dumps(body).encode(),
        headers={
            "Authorization": f"Bearer {settings.RESEND_API_KEY}",
            "Content-Type": "application/json",
            "User-Agent": "roman-technologies-cms-backend/1.0",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode() or "{}")
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"Resend {e.code}: {e.read().decode()}") from e
