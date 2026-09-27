"""Client onboarding ("welcome") email.

Sent by ``POST /admin/clients/{email}/welcome`` once the CMS Connector agent has
provisioned a client's account and project. It tells the client their site is
connected, how to sign in, and the one rule that trips everyone up (edits only
go live after Publish). It never contains the password: that is shared with the
client out-of-band, and the email says so.

Built on the shared branded chrome in ``email_layout`` (Roman Technologies
brand), like every other transactional email.
"""

from __future__ import annotations

import html

from ..core.config import settings
from . import email_layout
from .email_layout import DEFAULT_BRAND
from .email_send import send_via_resend

LOGIN_URL = "https://roman-technologies.dev/log-in"


def _safe_url(value: str, fallback: str = "https://roman-technologies.dev") -> str:
    """``value`` if it is an http(s) URL, else ``fallback`` (BE-006: a
    ``javascript:`` or ``data:`` URL renders as an inert link)."""
    return email_layout.safe_url(value, fallback)


def _safe_login_url(value: str) -> str:
    """Login links must stay on the canonical dashboard domain. Deployment
    URLs (*.vercel.app) sit behind Vercel SSO and dead-end clients on a
    'Check your email' code screen they can never pass — the exact trap a
    client hit in 2026-08. Anything off-domain falls back to the canonical
    log-in page."""
    v = (value or "").strip()
    if v.startswith("https://roman-technologies.dev/") or v == "https://roman-technologies.dev":
        return v
    return LOGIN_URL


def _first_name(full_name: str | None) -> str:
    parts = (full_name or "").split()
    return parts[0] if parts else ""


def _display_url(url: str) -> str:
    return url.removeprefix("https://").removeprefix("http://").rstrip("/")


def render_welcome_html(
    *,
    full_name: str,
    project_name: str,
    website_url: str,
    login_url: str = LOGIN_URL,
    to_email: str = "",
) -> str:
    """Welcome HTML. Every caller-controlled field is HTML-escaped (BE-006);
    ``website_url`` must be http(s) and ``login_url`` must be on the canonical
    domain (see ``_safe_login_url``)."""
    first = html.escape(_first_name(full_name))
    project = html.escape(project_name)
    website = _safe_url(website_url)
    website_esc = html.escape(website, quote=True)
    website_text = html.escape(_display_url(website))
    login = _safe_login_url(login_url)
    support = html.escape(settings.SUPPORT_EMAIL)

    greeting = f"Welcome aboard, {first}." if first else "Welcome aboard."
    account_rows = [
        (
            "Website",
            f'<a href="{website_esc}" style="color:#18181b;text-decoration:underline">'
            f"{website_text}</a>",
        ),
        ("Sign in with", html.escape(to_email) if to_email else "This email address"),
        ("Password", "Sent to you separately. We never put passwords in email."),
    ]
    steps = (
        "<strong>1.</strong> Sign in and change your password under <em>Account Settings</em>.<br>"
        "<strong>2.</strong> Open <em>CMS</em>, pick a section and edit the text or images.<br>"
        "<strong>3.</strong> Click <em>Publish Changes</em>. Your site only changes after you publish, "
        "so you can draft freely."
    )
    inner = (
        email_layout.header("Your client dashboard", brand=DEFAULT_BRAND)
        + email_layout.accent_rule(brand=DEFAULT_BRAND)
        + email_layout.heading(greeting)
        + email_layout.paragraph(
            f"<strong>{project}</strong> is now connected to your own dashboard. "
            "From there you can update your website yourself, without waiting on a developer."
        )
        + email_layout.detail_box(account_rows)
        + email_layout.button(login, "Open your dashboard &rarr;")
        + email_layout.paragraph("<strong>Getting started</strong>", color="#18181b", size=14)
        + email_layout.paragraph(steps, size=14)
        + email_layout.callout(
            "Stuck, or want something changed that the dashboard can't do? "
            f"Reply to this email or write to {support}."
        )
        + email_layout.spacer()
        + email_layout.footer(brand=DEFAULT_BRAND)
    )
    return email_layout.shell(
        inner, preheader=f"{project_name} is connected. Here's how to sign in and publish."
    )


def render_welcome_text(
    *, full_name: str, project_name: str, website_url: str, login_url: str = LOGIN_URL
) -> str:
    first = _first_name(full_name)
    return (
        f"Welcome aboard{', ' + first if first else ''}.\n\n"
        f"{project_name} is now connected to your own dashboard.\n\n"
        f"Website: {_safe_url(website_url)}\n"
        f"Dashboard: {_safe_login_url(login_url)}\n"
        "Sign in with this email address. Your password is sent to you separately.\n\n"
        "Getting started:\n"
        "1. Sign in and change your password under Account Settings.\n"
        "2. Open CMS, pick a section and edit the text or images.\n"
        "3. Click Publish Changes. Your site only changes after you publish.\n\n"
        f"Questions? Reply to this email or write to {settings.SUPPORT_EMAIL}.\n"
    )


def send_welcome_email(
    *,
    to_email: str,
    full_name: str | None,
    project_name: str,
    website_url: str,
    login_url: str = LOGIN_URL,
) -> dict:
    """Send the welcome email. Returns Resend's JSON; raises RuntimeError on
    a missing key or a non-2xx response."""
    # TEST-002 — preview-tier short-circuit on E2E marker.
    from .e2e_email_guard import short_circuit_response, should_short_circuit

    if should_short_circuit(to_email, full_name or "", project_name, website_url):
        return short_circuit_response(f"welcome:{to_email}")

    return send_via_resend(
        to_email=to_email,
        subject=f"Your {project_name} dashboard is ready",
        html_body=render_welcome_html(
            full_name=full_name or "",
            project_name=project_name,
            website_url=website_url,
            login_url=login_url,
            to_email=to_email,
        ),
        text_body=render_welcome_text(
            full_name=full_name or "",
            project_name=project_name,
            website_url=website_url,
            login_url=login_url,
        ),
        reply_to=settings.SUPPORT_EMAIL or None,
    )
