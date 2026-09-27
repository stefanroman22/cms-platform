"""Booking reminder email to the visitor, sent by ``POST /booking/cron/reminders``
at each of the tenant's ``reminder_offsets_min`` (default 24h and 1h before).

Tenant-branded via ``email_layout``; every visible string is overridable from
the dashboard email editor (``booking_settings.email_copy``) through ``tt``.
The lead line names how far off the appointment is, derived from the offset
that triggered the send, so the 24h reminder says "tomorrow", not "in an hour".
"""

from __future__ import annotations

import html
from datetime import datetime

from . import email_layout
from .booking_i18n import copy_color, t, tt
from .email_layout import DEFAULT_BRAND, Brand
from .email_send import send_via_resend


def relative_phrase(offset_min: int | None, locale: str = "en") -> str:
    """How far away the appointment is, in words, for a reminder sent
    ``offset_min`` minutes before it starts."""
    if offset_min is None or offset_min <= 0:
        return t(locale, "rel_soon")
    if offset_min < 45:
        return t(locale, "rel_minutes", n=offset_min)
    if offset_min < 90:
        return t(locale, "rel_hour")
    if offset_min < 20 * 60:
        return t(locale, "rel_hours", n=round(offset_min / 60))
    if offset_min < 36 * 60:
        return t(locale, "rel_tomorrow")
    return t(locale, "rel_days", n=round(offset_min / 1440))


def _calendar_url(
    *,
    start_utc: datetime | None,
    end_utc: datetime | None,
    business_name: str | None,
    meeting_url: str,
) -> str:
    """Google Calendar template link, or "" without times. Offered even for
    in-person businesses (no meeting URL): people still want the event."""
    if start_utc is None or end_utc is None:
        return ""
    title = f"Booking @ {business_name}" if business_name else "Your appointment"
    details = f"Appointment with {business_name}." if business_name else "Your appointment."
    if meeting_url:
        details += f"\nJoin: {meeting_url}"
    return email_layout.google_calendar_url(
        title=title,
        start_utc=start_utc,
        end_utc=end_utc,
        details=details,
        location=meeting_url or (business_name or ""),
    )


def render_html(
    *,
    name: str,
    when_label: str,
    note: str | None,
    meeting_url: str,
    manage_url: str = "",
    start_utc: datetime | None = None,
    end_utc: datetime | None = None,
    business_name: str | None = None,
    brand: Brand | None = None,
    locale: str = "en",
    copy: dict | None = None,
    offset_min: int | None = None,
) -> str:
    _brand = brand if brand is not None else DEFAULT_BRAND
    accent = email_layout.safe_hex(_brand.accent, "#18181b")

    # Details card: only rows that carry information.
    rows = [("When", html.escape(when_label))]
    if business_name:
        rows.append(("With", html.escape(business_name)))
    if note and note.strip():
        rows.append(("Your note", html.escape(note).replace("\n", "<br>")))

    # Actions: join (online only), then add-to-calendar.
    actions = ""
    safe_meeting = email_layout.safe_url(meeting_url)
    if safe_meeting:
        actions += email_layout.button(
            safe_meeting,
            f'{tt(copy, locale, "join_cta")} &rarr;',
            accent=accent,
            text_color=copy_color(copy, "join_cta", "#ffffff"),
        )
        esc = html.escape(safe_meeting)
        actions += (
            '<tr><td style="padding:10px 32px 0" align="center">'
            '<p style="margin:0;font-size:12px;color:#a1a1aa;word-break:break-all">'
            f'<a href="{esc}" style="color:#71717a;text-decoration:underline">{esc}</a>'
            "</p></td></tr>"
        )
    cal = _calendar_url(
        start_utc=start_utc,
        end_utc=end_utc,
        business_name=business_name,
        meeting_url=meeting_url,
    )
    if cal:
        actions += email_layout.button(
            cal,
            tt(copy, locale, "add_cal_cta"),
            accent=accent,
            text_color=copy_color(copy, "add_cal_cta", "#18181b"),
            outline=True,
        )

    manage = ""
    safe_manage = email_layout.safe_url(manage_url)
    if safe_manage:
        prompt_color = copy_color(copy, "manage_prompt", "#71717a")
        manage_color = copy_color(copy, "manage_cta", "#52525b")
        manage = (
            '<tr><td style="padding:20px 32px 0" align="center">'
            f'<p style="margin:0;font-size:13px;color:{prompt_color}">'
            f'{tt(copy, locale, "manage_prompt")} '
            f'<a href="{html.escape(safe_manage)}" style="color:{manage_color};'
            f'text-decoration:underline">{tt(copy, locale, "manage_cta")}</a>.</p></td></tr>'
        )

    inner = (
        email_layout.header(
            tt(copy, locale, "header_reminder"),
            brand=_brand,
            subtitle_color=copy.get("header_reminder__color") if copy else None,
        )
        + email_layout.accent_rule(brand=_brand)
        + email_layout.heading(
            tt(copy, locale, "reminder_heading", name=html.escape(name)),
            color=copy_color(copy, "reminder_heading", "#18181b"),
        )
        + email_layout.paragraph(
            tt(copy, locale, "reminder_lead", relative=relative_phrase(offset_min, locale)),
            color=copy_color(copy, "reminder_lead", "#52525b"),
        )
        + email_layout.detail_box(rows)
        + actions
        + manage
        + email_layout.spacer()
        + email_layout.footer(brand=_brand)
    )
    return email_layout.shell(inner, preheader=when_label)


def render_text(
    *,
    name: str,
    when_label: str,
    note: str | None,
    meeting_url: str,
    business_name: str | None = None,
    manage_url: str = "",
    offset_min: int | None = None,
    locale: str = "en",
) -> str:
    lines = [
        f"See you soon, {name}." if name else "See you soon.",
        "",
        f"Your appointment is {relative_phrase(offset_min, locale)}.",
        "",
        f"When: {when_label}",
    ]
    if business_name:
        lines.append(f"With: {business_name}")
    if note and note.strip():
        lines.append(f"Your note: {note}")
    if meeting_url:
        lines.append(f"Join: {meeting_url}")
    if manage_url:
        lines.append(f"Need to change or cancel? {manage_url}")
    return "\n".join(lines) + "\n"


def send(
    *,
    to_email: str,
    name: str,
    when_label: str,
    note: str | None,
    meeting_url: str,
    manage_url: str = "",
    start_utc: datetime | None = None,
    end_utc: datetime | None = None,
    business_name: str | None = None,
    brand: Brand | None = None,
    locale: str = "en",
    copy: dict | None = None,
    offset_min: int | None = None,
) -> dict:
    from .e2e_email_guard import short_circuit_response, should_short_circuit

    if should_short_circuit(to_email, name, when_label):
        return short_circuit_response(f"booking_reminder:{to_email}")

    _brand = brand if brand is not None else DEFAULT_BRAND
    return send_via_resend(
        to_email=to_email,
        subject=tt(
            copy,
            locale,
            "reminder_subject",
            html_escape=False,
            business=business_name or _brand.business_name,
        ),
        html_body=render_html(
            name=name,
            when_label=when_label,
            note=note,
            meeting_url=meeting_url,
            manage_url=manage_url,
            start_utc=start_utc,
            end_utc=end_utc,
            business_name=business_name,
            brand=brand,
            locale=locale,
            copy=copy,
            offset_min=offset_min,
        ),
        text_body=render_text(
            name=name,
            when_label=when_label,
            note=note,
            meeting_url=meeting_url,
            business_name=business_name,
            manage_url=manage_url,
            offset_min=offset_min,
            locale=locale,
        ),
    )
