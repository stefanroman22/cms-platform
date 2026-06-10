"""Locale strings for booking emails + widget-facing copy.

English now; add a locale by adding a dict. ``t(locale, key, **fmt)`` falls
back to 'en' for both unknown locales and missing keys."""

from __future__ import annotations

import html

from .email_layout import safe_hex

# Suffix appended to a copy key to store that field's per-text colour override in
# the same email_copy JSONB dict — no schema/migration change needed.
COLOR_SUFFIX = "__color"

STRINGS: dict[str, dict[str, str]] = {
    "en": {
        # --- subjects (match original booking email subjects exactly) ---
        "confirm_subject": "Your booking is confirmed",
        "host_new_subject": "New booking — {name}",
        "reminder_subject": "Reminder: your upcoming appointment",
        "cancel_subject": "Your booking has been cancelled",
        "host_cancel_subject": "Cancelled — booking with {name}",
        "reschedule_subject": "Your booking has been rescheduled",
        "host_reschedule_subject": "Rescheduled — booking with {name}",
        # --- header subtitles ---
        "header_new_booking": "New booking",
        "header_confirmed": "Appointment confirmed",
        "header_reminder": "Appointment reminder",
        "header_cancelled": "Booking cancelled",
        "header_moved": "Booking moved",
        # --- body copy ---
        "confirmed_heading": "You're booked, {name}.",
        "confirmed_subtext": "Your booking is confirmed.",
        "reminder_heading": "Your appointment is in about an hour, {name}.",
        "cancel_client_heading": "Your booking has been cancelled, {name}.",
        "cancel_host_heading": "A booking was cancelled",
        "reschedule_client_heading": "Your booking has been moved, {name}.",
        "reschedule_host_heading": "A booking was rescheduled",
        "host_new_heading": "New booking",
        "manage_cta": "Manage your booking",
        "join_cta": "Join the meeting",
        "add_cal_cta": "Add to Google Calendar",
        "email_you_link": "We'll email you the meeting link before your appointment.",
        "manage_prompt": "Need to change or cancel?",
    },
}


def t(locale: str | None, key: str, **fmt: object) -> str:
    """Return the translated string for *key* in *locale*, falling back to 'en'.

    Any ``{placeholder}`` values in the string are filled from ``fmt``.
    If the key is absent from both the requested locale and 'en', the raw
    key is returned so nothing crashes.
    """
    table = STRINGS.get(locale or "en", STRINGS["en"])
    raw = table.get(key, STRINGS["en"].get(key, key))
    if fmt:
        try:
            return raw.format(**fmt)
        except KeyError:
            return raw
    return raw


def tt(
    overrides: dict | None,
    locale: str | None,
    key: str,
    *,
    html_escape: bool = True,
    **fmt: object,
) -> str:
    """Tenant override → else the locale default (t). Formats {placeholders}
    best-effort; never raises on a missing placeholder.

    SEC-044: a tenant override is untrusted input that is interpolated into the
    booking email HTML. By default the override TEMPLATE is HTML-escaped before
    placeholder substitution, so a tenant cannot inject markup; placeholder values
    (e.g. ``name``) are escaped by the caller, so they are not double-escaped. The
    built-in locale defaults go through ``t`` and are NOT escaped (they are trusted
    and may contain intentional entities). Pass ``html_escape=False`` for plain-text
    contexts such as email subject lines.
    """
    if overrides and key in overrides and overrides[key]:
        raw = str(overrides[key])
        if html_escape:
            raw = html.escape(raw)
        if fmt:
            try:
                return raw.format(**fmt)
            except (KeyError, IndexError, ValueError):
                return raw
        return raw
    return t(locale, key, **fmt)


def copy_color(overrides: dict | None, key: str, default: str) -> str:
    """Per-field text colour for *key*, read from ``overrides["{key}__color"]``.

    SEC-045: the stored value is untrusted (owner-supplied), so it is run through
    the same hex allowlist used for the tenant accent before it is ever emitted
    into a ``style="color:…"`` attribute. Anything that isn't a hex literal (or no
    override at all) falls back to *default*.
    """
    raw = (overrides or {}).get(key + COLOR_SUFFIX) if overrides else None
    return safe_hex(raw if isinstance(raw, str) else None, default)


# Editable client-facing fields, grouped for the dashboard editor. Host-facing
# keys are intentionally excluded. `group` drives the editor's case selector;
# "shared" fields render once. `color` flags the fields whose rendered text
# accepts a per-field colour override (subjects are plain-text, so they don't).
EDITABLE_EMAIL_FIELDS: list[dict[str, object]] = [
    {"key": "manage_cta", "label": "Manage-booking button", "group": "shared", "color": True},
    {"key": "join_cta", "label": "Join button", "group": "shared", "color": True},
    {"key": "add_cal_cta", "label": "Add-to-calendar button", "group": "shared", "color": True},
    {"key": "manage_prompt", "label": "Manage prompt", "group": "shared", "color": True},
    {"key": "confirm_subject", "label": "Subject", "group": "confirmation", "color": False},
    {"key": "header_confirmed", "label": "Header subtitle", "group": "confirmation", "color": True},
    {"key": "confirmed_heading", "label": "Heading", "group": "confirmation", "color": True},
    {"key": "confirmed_subtext", "label": "Subtext", "group": "confirmation", "color": True},
    {"key": "reschedule_subject", "label": "Subject", "group": "reschedule", "color": False},
    {"key": "header_moved", "label": "Header subtitle", "group": "reschedule", "color": True},
    {
        "key": "reschedule_client_heading",
        "label": "Heading",
        "group": "reschedule",
        "color": True,
    },
    {"key": "cancel_subject", "label": "Subject", "group": "cancellation", "color": False},
    {"key": "header_cancelled", "label": "Header subtitle", "group": "cancellation", "color": True},
    {"key": "cancel_client_heading", "label": "Heading", "group": "cancellation", "color": True},
    {"key": "reminder_subject", "label": "Subject", "group": "reminder", "color": False},
    {"key": "header_reminder", "label": "Header subtitle", "group": "reminder", "color": True},
    {"key": "reminder_heading", "label": "Heading", "group": "reminder", "color": True},
]
