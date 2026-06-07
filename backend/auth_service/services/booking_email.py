"""Branded booking-confirmation emails: one to the host, one to the
visitor. Mirrors issue_resolved_email's Resend-over-urllib send + E2E guard."""

from __future__ import annotations

import html
import json
import urllib.error
import urllib.request

from ..core.config import settings
from . import email_layout
from .booking_i18n import t, tt
from .email_layout import DEFAULT_BRAND, Brand


def _detail_box(rows: list[tuple[str, str]]) -> str:
    body = "".join(
        f'<p style="margin:0 0 4px;font-size:11px;font-weight:600;letter-spacing:0.08em;'
        f'text-transform:uppercase;color:#71717a">{label}</p>'
        f'<p style="margin:0 0 14px;font-size:15px;color:#18181b">{value}</p>'
        for label, value in rows
    )
    return (
        '<tr><td style="padding:8px 32px"><table width="100%" cellpadding="0" cellspacing="0" '
        'style="margin-top:16px;background:#fafafa;border:1px solid #e4e4e7;border-radius:8px">'
        f'<tr><td style="padding:18px 22px">{body}</td></tr></table></td></tr>'
    )


def _cta_block(
    *,
    meeting_url: str,
    add_to_cal_url: str = "",
    locale: str = "en",
    copy: dict | None = None,
    accent: str = "#18181b",
) -> str:
    """Explicit meeting link (as text) + a 'Join the call' button, plus an
    OPTIONAL 'Add to Google Calendar' button (only when add_to_cal_url is given).
    When the tenant has no meeting URL (e.g. in-person businesses) we render
    NOTHING — the meeting link is an opt-in extension, not a default."""
    safe_meeting = email_layout.safe_url(meeting_url)
    if not safe_meeting:
        return ""
    esc = html.escape(safe_meeting)
    add_btn = ""
    if add_to_cal_url:
        cal = html.escape(add_to_cal_url)
        add_btn = (
            f'<a href="{cal}" style="display:inline-block;margin:8px 0 0 8px;background:#fff;'
            "border:1px solid #d4d4d8;color:#18181b;text-decoration:none;font-size:14px;font-weight:600;"
            f'padding:11px 22px;border-radius:8px">{tt(copy, locale, "add_cal_cta")}</a>'
        )
    return (
        # Explicit link, spelled out.
        '<tr><td style="padding:18px 32px 0" align="center">'
        '<p style="margin:0;font-size:13px;color:#52525b">Meeting link: '
        f'<a href="{esc}" style="color:#18181b;text-decoration:underline">{esc}</a></p></td></tr>'
        # Buttons.
        '<tr><td style="padding:16px 32px 8px" align="center">'
        f'<a href="{esc}" style="display:inline-block;background:{accent};color:#fff;text-decoration:none;'
        'font-size:14px;font-weight:600;padding:12px 26px;border-radius:8px">'
        f'{tt(copy, locale, "join_cta")} &rarr;</a>'
        f"{add_btn}"
        "</td></tr>"
    )


def _add_to_cal_url(*, booking: dict, meeting_url: str, title: str) -> str:
    note = booking.get("note")
    details = "Video call with Roman Technologies."
    if meeting_url:
        details += f"\nJoin: {meeting_url}"
    if note:
        details += f"\n\nNote: {note}"
    return email_layout.google_calendar_url(
        title=title,
        start_utc=booking["start_utc"],
        end_utc=booking["end_utc"],
        details=details,
        location=meeting_url or "Google Meet",
    )


def render_host_html(
    *, booking: dict, meeting_url: str, brand: Brand | None = None, locale: str = "en"
) -> str:
    _brand = brand if brand is not None else DEFAULT_BRAND
    name = html.escape(booking["name"])
    email_addr = html.escape(booking["email"])
    when = html.escape(booking["when_label"])
    note = html.escape(booking.get("note") or "—").replace("\n", "<br>")
    # Host has the event auto-created on their calendar, so no add-to-cal button.
    cta = _cta_block(meeting_url=meeting_url, locale=locale)
    inner = (
        email_layout.header(t(locale, "header_new_booking"), brand=_brand)
        + f'<tr><td style="padding:32px 32px 8px"><h1 style="margin:0;font-size:22px;font-weight:600;color:#18181b">{t(locale, "host_new_heading")}</h1></td></tr>'
        + _detail_box([("When", when), ("Name", name), ("Email", email_addr), ("Note", note)])
        + cta
        + email_layout.footer(brand=_brand)
    )
    return email_layout.shell(inner)


def render_visitor_html(
    *,
    booking: dict,
    meeting_url: str,
    manage_url: str = "",
    brand: Brand | None = None,
    locale: str = "en",
    copy: dict | None = None,
) -> str:
    _brand = brand if brand is not None else DEFAULT_BRAND
    name = html.escape(booking["name"])
    when = html.escape(booking["when_label"])
    note = html.escape(booking.get("note") or "—").replace("\n", "<br>")
    cta = _cta_block(
        meeting_url=meeting_url,
        add_to_cal_url=_add_to_cal_url(
            booking=booking, meeting_url=meeting_url, title=f"Booking @ {_brand.business_name}"
        ),
        locale=locale,
        copy=copy,
        accent=_brand.accent,
    )
    manage = ""
    safe_manage = email_layout.safe_url(manage_url)
    if safe_manage:
        manage = (
            '<tr><td style="padding:8px 32px 0" align="center">'
            f'<p style="margin:0;font-size:12px;color:#71717a">{tt(copy, locale, "manage_prompt")} '
            f'<a href="{html.escape(safe_manage)}" style="color:#52525b;text-decoration:underline">'
            f'{tt(copy, locale, "manage_cta")}</a>.</p></td></tr>'
        )
    inner = (
        email_layout.header(tt(copy, locale, "header_confirmed"), brand=_brand)
        + f'<tr><td style="padding:32px 32px 8px"><h1 style="margin:0 0 12px;font-size:22px;font-weight:600;color:#18181b">{tt(copy, locale, "confirmed_heading", name=name)}</h1>'
        + f'<p style="margin:0;font-size:15px;line-height:1.55;color:#52525b">{tt(copy, locale, "confirmed_subtext")}</p></td></tr>'
        + _detail_box([("When", when), ("Note", note)])
        + cta
        + manage
        + email_layout.footer(brand=_brand)
    )
    return email_layout.shell(inner)


def _send(
    *, to_email: str, subject: str, html_body: str, text_body: str, from_name: str | None = None
) -> dict:
    from .e2e_email_guard import short_circuit_response, should_short_circuit

    if should_short_circuit(to_email, subject):
        return short_circuit_response(f"booking:{to_email}")
    if not settings.RESEND_API_KEY:
        raise RuntimeError("RESEND_API_KEY not configured on this backend")

    display_name = from_name or settings.RESEND_FROM_NAME
    body = {
        "from": f"{display_name} <{settings.RESEND_FROM_EMAIL}>",
        "to": to_email,
        "subject": subject,
        "html": html_body,
        "text": text_body,
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


def send_host_notification(
    *,
    booking: dict,
    meeting_url: str,
    host_email: str | None = None,
    brand: Brand | None = None,
    locale: str = "en",
    from_name: str | None = None,
) -> dict:
    link = f"Join: {meeting_url}\n" if meeting_url else ""
    text = (
        f"New call booked\n\nWhen: {booking['when_label']}\nName: {booking['name']}\n"
        f"Email: {booking['email']}\nNote: {booking.get('note') or '-'}\n{link}"
    )
    return _send(
        to_email=host_email or settings.BOOKING_HOST_EMAIL,
        subject=t(locale, "host_new_subject", name=booking["name"]),
        html_body=render_host_html(
            booking=booking, meeting_url=meeting_url, brand=brand, locale=locale
        ),
        text_body=text,
        from_name=from_name,
    )


def send_visitor_confirmation(
    *,
    booking: dict,
    meeting_url: str,
    manage_url: str = "",
    brand: Brand | None = None,
    locale: str = "en",
    from_name: str | None = None,
    copy: dict | None = None,
) -> dict:
    link_line = f"Join the call: {meeting_url}\n" if meeting_url else ""
    manage_line = f"Manage your booking: {manage_url}\n" if manage_url else ""
    text = (
        f"You're booked, {booking['name']}.\n\nWhen: {booking['when_label']}\n"
        f"Note: {booking.get('note') or '-'}\n{link_line}{manage_line}"
    )
    return _send(
        to_email=booking["email"],
        subject=tt(copy, locale, "confirm_subject"),
        html_body=render_visitor_html(
            booking=booking,
            meeting_url=meeting_url,
            manage_url=manage_url,
            brand=brand,
            locale=locale,
            copy=copy,
        ),
        text_body=text,
        from_name=from_name,
    )
