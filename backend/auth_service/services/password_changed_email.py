"""Security notification: "Your password was changed".

Sent after a dashboard password changes, from either path:

* ``admin_reset`` — ``POST /admin/clients/{email}/reset-password``. The admin
  receives the new password in the API response and passes it to the client
  out-of-band, as before.
* ``self_service`` — ``POST /auth/change-password`` from Account Settings.

The email NEVER contains a password or a reset token. Email is unencrypted and
long-lived in inboxes, so it only warns the account owner that the change
happened, links to the log-in page, and says who to contact if it wasn't them.
Sending is best-effort: callers log and swallow failures, because the password
change has already happened by the time this is sent.
"""

from __future__ import annotations

import html
from datetime import UTC, datetime
from typing import Literal

from ..core.config import settings
from . import email_layout
from .email_layout import DEFAULT_BRAND
from .email_send import send_via_resend
from .welcome_email import LOGIN_URL

Reason = Literal["admin_reset", "self_service"]


def _when(changed_at: datetime) -> str:
    return changed_at.astimezone(UTC).strftime("%a %d %b %Y, %H:%M UTC")


def _body_lines(reason: Reason) -> tuple[str, str]:
    """(what happened, what happens next) as plain text."""
    if reason == "admin_reset":
        return (
            "Roman Technologies set a new password for your dashboard account.",
            "We'll send you the new password directly, not by email. "
            "You've been signed out everywhere, so sign in again with the new one.",
        )
    return (
        "The password for your dashboard account was just changed from Account Settings.",
        "Your other devices have been signed out. If this was you, there's nothing else to do.",
    )


def render_html(
    *, email: str, reason: Reason, changed_at: datetime, login_url: str = LOGIN_URL
) -> str:
    what, nxt = _body_lines(reason)
    support = html.escape(settings.SUPPORT_EMAIL)
    inner = (
        email_layout.header("Account security", brand=DEFAULT_BRAND)
        + email_layout.accent_rule(brand=DEFAULT_BRAND)
        + email_layout.heading("Your password was changed")
        + email_layout.paragraph(html.escape(what))
        + email_layout.detail_box(
            [("Account", html.escape(email)), ("When", html.escape(_when(changed_at)))]
        )
        + email_layout.paragraph(html.escape(nxt))
        + email_layout.button(login_url, "Sign in &rarr;")
        + email_layout.callout(
            '<strong style="color:#18181b">Didn\'t expect this?</strong> '
            f"Reply to this email or write to {support} right away and we'll lock the account."
        )
        + email_layout.spacer()
        + email_layout.footer(brand=DEFAULT_BRAND)
    )
    return email_layout.shell(inner, preheader="Your dashboard password was just changed.")


def render_text(*, email: str, reason: Reason, changed_at: datetime) -> str:
    what, nxt = _body_lines(reason)
    return (
        "Your password was changed\n\n"
        f"{what}\n\n"
        f"Account: {email}\nWhen: {_when(changed_at)}\n\n"
        f"{nxt}\n\nSign in: {LOGIN_URL}\n\n"
        f"Didn't expect this? Reply to this email or write to {settings.SUPPORT_EMAIL} "
        "right away and we'll lock the account.\n"
    )


def send_password_changed_email(
    *, to_email: str, reason: Reason, changed_at: datetime | None = None
) -> dict:
    """Send the notification. Returns Resend's JSON; raises RuntimeError on
    failure (callers treat it as best-effort)."""
    from .e2e_email_guard import short_circuit_response, should_short_circuit

    if should_short_circuit(to_email):
        return short_circuit_response(f"password_changed:{to_email}")

    at = changed_at or datetime.now(UTC)
    return send_via_resend(
        to_email=to_email,
        subject="Your Roman Technologies password was changed",
        html_body=render_html(email=to_email, reason=reason, changed_at=at),
        text_body=render_text(email=to_email, reason=reason, changed_at=at),
        reply_to=settings.SUPPORT_EMAIL or None,
    )
