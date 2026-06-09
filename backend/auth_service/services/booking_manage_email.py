"""Branded cancellation / reschedule emails (host + client). Mirrors
booking_email's Resend-over-urllib + E2E guard."""

from __future__ import annotations

import html
import json
import logging
import urllib.error
import urllib.request
from datetime import datetime

from ..core.config import settings
from . import email_layout
from .booking_i18n import t, tt
from .email_layout import DEFAULT_BRAND, Brand

log = logging.getLogger(__name__)


def _box(rows: list[tuple[str, str]]) -> str:
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


def _heading(text: str) -> str:
    return (
        '<tr><td style="padding:32px 32px 8px">'
        f'<h1 style="margin:0;font-size:22px;font-weight:600;color:#18181b">{text}</h1></td></tr>'
    )


def _button(*, url: str, label: str, accent: str = "#18181b") -> str:
    safe = email_layout.safe_url(url)
    if not safe:
        return ""
    return (
        '<tr><td style="padding:20px 32px 8px" align="center">'
        f'<a href="{html.escape(safe)}" style="display:inline-block;background:{accent};color:#fff;'
        'text-decoration:none;font-size:14px;font-weight:600;padding:12px 28px;border-radius:8px">'
        f"{label} &rarr;</a></td></tr>"
    )


def render_cancel_client(
    *,
    name: str,
    when_label: str,
    brand: Brand | None = None,
    locale: str = "en",
    copy: dict | None = None,
) -> str:
    _brand = brand if brand is not None else DEFAULT_BRAND
    inner = (
        email_layout.header(tt(copy, locale, "header_cancelled"), brand=_brand)
        + _heading(f"{tt(copy, locale, 'cancel_client_heading', name=html.escape(name))}")
        + _box([("Was", html.escape(when_label))])
        + email_layout.footer(brand=_brand)
    )
    return email_layout.shell(inner)


def render_cancel_host(
    *, name: str, when_label: str, brand: Brand | None = None, locale: str = "en"
) -> str:
    _brand = brand if brand is not None else DEFAULT_BRAND
    inner = (
        email_layout.header(t(locale, "header_cancelled"), brand=_brand)
        + _heading(t(locale, "cancel_host_heading"))
        + _box([("Client", html.escape(name)), ("Was", html.escape(when_label))])
        + email_layout.footer(brand=_brand)
    )
    return email_layout.shell(inner)


def render_reschedule_client(
    *,
    name: str,
    new_when: str,
    meeting_url: str,
    manage_url: str,
    new_start: datetime,
    new_end: datetime,
    brand: Brand | None = None,
    locale: str = "en",
    copy: dict | None = None,
) -> str:
    _brand = brand if brand is not None else DEFAULT_BRAND
    add_to_cal = email_layout.google_calendar_url(
        title=f"Booking @ {_brand.business_name}",
        start_utc=new_start,
        end_utc=new_end,
        details=f"Appointment with {_brand.business_name}."
        + (f"\nJoin: {meeting_url}" if meeting_url else ""),
        location=meeting_url or _brand.business_name,
    )
    safe_cal = email_layout.safe_url(add_to_cal)
    addcal_btn = ""
    if safe_cal:
        addcal_btn = (
            '<tr><td style="padding:0 32px 8px" align="center">'
            f'<a href="{html.escape(safe_cal)}" style="display:inline-block;background:#fff;'
            "border:1px solid #d4d4d8;color:#18181b;text-decoration:none;font-size:14px;font-weight:600;"
            f'padding:11px 26px;border-radius:8px">{tt(copy, locale, "add_cal_cta")}</a></td></tr>'
        )
    # Manage link as a small bottom-of-email text link (matches the confirmation
    # email), not a prominent button. Only shown when a manage URL is present.
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
        email_layout.header(tt(copy, locale, "header_moved"), brand=_brand)
        + _heading(tt(copy, locale, "reschedule_client_heading", name=html.escape(name)))
        + _box([("New time", html.escape(new_when))])
        + _button(url=meeting_url, label=tt(copy, locale, "join_cta"), accent=_brand.accent)
        + addcal_btn
        + manage
        + email_layout.footer(brand=_brand)
    )
    return email_layout.shell(inner)


def render_reschedule_host(
    *, name: str, old_when: str, new_when: str, brand: Brand | None = None, locale: str = "en"
) -> str:
    _brand = brand if brand is not None else DEFAULT_BRAND
    inner = (
        email_layout.header(t(locale, "header_moved"), brand=_brand)
        + _heading(t(locale, "reschedule_host_heading"))
        + _box(
            [
                ("Client", html.escape(name)),
                ("From", html.escape(old_when)),
                ("To", html.escape(new_when)),
            ]
        )
        + email_layout.footer(brand=_brand)
    )
    return email_layout.shell(inner)


def _send(
    *, to_email: str, subject: str, html_body: str, text_body: str, from_name: str | None = None
) -> dict:
    from .e2e_email_guard import short_circuit_response, should_short_circuit

    if should_short_circuit(to_email, subject):
        return short_circuit_response(f"booking_manage:{to_email}")
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


def _safe_send(**kwargs) -> None:
    """Best-effort send — one recipient failing must not break the other."""
    try:
        _send(**kwargs)
    except Exception:  # noqa: BLE001
        log.exception("booking-manage email failed (%s)", kwargs.get("to_email"))


def send_cancellation(
    *,
    name: str,
    client_email: str,
    host_when: str,
    client_when: str,
    host_email: str | None = None,
    brand: Brand | None = None,
    locale: str = "en",
    from_name: str | None = None,
    copy: dict | None = None,
) -> None:
    _safe_send(
        to_email=host_email or settings.BOOKING_HOST_EMAIL,
        subject=t(locale, "host_cancel_subject", name=name),
        html_body=render_cancel_host(name=name, when_label=host_when, brand=brand, locale=locale),
        text_body=f"A booking was cancelled.\nClient: {name}\nWas: {host_when}\n",
        from_name=from_name,
    )
    _safe_send(
        to_email=client_email,
        subject=tt(copy, locale, "cancel_subject", html_escape=False),
        html_body=render_cancel_client(
            name=name, when_label=client_when, brand=brand, locale=locale, copy=copy
        ),
        text_body=f"Your booking is cancelled.\nWas: {client_when}\n",
        from_name=from_name,
    )


def send_reschedule(
    *,
    name: str,
    client_email: str,
    old_host_when: str,
    new_host_when: str,
    new_client_when: str,
    meeting_url: str,
    manage_url: str,
    new_start: datetime,
    new_end: datetime,
    host_email: str | None = None,
    brand: Brand | None = None,
    locale: str = "en",
    from_name: str | None = None,
    copy: dict | None = None,
) -> None:
    _safe_send(
        to_email=host_email or settings.BOOKING_HOST_EMAIL,
        subject=t(locale, "host_reschedule_subject", name=name),
        html_body=render_reschedule_host(
            name=name, old_when=old_host_when, new_when=new_host_when, brand=brand, locale=locale
        ),
        text_body=f"A booking was rescheduled.\nClient: {name}\nFrom: {old_host_when}\nTo: {new_host_when}\n",
        from_name=from_name,
    )
    _safe_send(
        to_email=client_email,
        subject=tt(copy, locale, "reschedule_subject", html_escape=False),
        html_body=render_reschedule_client(
            name=name,
            new_when=new_client_when,
            meeting_url=meeting_url,
            manage_url=manage_url,
            new_start=new_start,
            new_end=new_end,
            brand=brand,
            locale=locale,
            copy=copy,
        ),
        text_body=f"Your booking has been moved to {new_client_when}.\nManage: {manage_url}\n",
        from_name=from_name,
    )
