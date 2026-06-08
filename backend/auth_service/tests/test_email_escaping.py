"""HTML-escaping of untrusted input in outbound emails (SEC-009/014/032/044/045)."""

from __future__ import annotations

from auth_service.routers.forms import _EMAIL_RE, _build_email_html
from auth_service.services import booking_i18n
from auth_service.services.email_layout import Brand, footer, header


def test_form_email_escapes_field_keys_and_values():
    payload = _build_email_html(
        project_name="<b>Acme</b>",
        form_key="contact<script>",
        fields={"name<script>": "<img src=x onerror=alert(1)>"},
        submitted_at="now",
    )
    assert "<script>" not in payload
    assert "<img src=x" not in payload
    assert "&lt;script&gt;" in payload  # rendered as text, not markup
    assert "&lt;img src=x onerror=alert(1)&gt;" in payload


def test_reply_to_regex_rejects_header_injection():
    assert _EMAIL_RE.fullmatch("user@example.com")
    assert not _EMAIL_RE.fullmatch("user@example.com\nBcc: victim@x.com")
    assert not _EMAIL_RE.fullmatch("a@b.com, c@d.com")
    assert not _EMAIL_RE.fullmatch("not-an-email")


def test_email_header_neutralises_malicious_brand():
    brand = Brand(
        business_name="</p><script>alert(1)</script>",
        logo_url="javascript:alert(1)",
        accent='#000;"><script>alert(1)</script>',
        canonical_url="javascript:alert(1)",
    )
    out = header("subtitle", brand=brand) + footer(brand=brand)
    assert "<script>" not in out
    assert "javascript:" not in out  # logo + canonical fall back to safe defaults
    assert ';"><' not in out  # accent rejected → default hex used


def test_default_brand_output_unchanged():
    # The escaping must be a no-op for the trusted default brand.
    out = header("Appointment confirmed")
    assert "Roman Technologies" in out
    assert "background:#18181b" in out
    assert "&lt;" not in out


def test_tt_escapes_tenant_override_for_html_but_not_subjects():
    overrides = {"confirmed_heading": "<script>x</script>{name}", "confirm_subject": "Cut & Co"}
    html_val = booking_i18n.tt(overrides, "en", "confirmed_heading", name="Sam")
    assert "<script>" not in html_val and "&lt;script&gt;" in html_val
    assert html_val.endswith("Sam")  # placeholder substituted after escaping
    subject = booking_i18n.tt(overrides, "en", "confirm_subject", html_escape=False)
    assert subject == "Cut & Co"  # plain-text subject not HTML-escaped


def test_tt_default_copy_not_escaped():
    # Built-in defaults are trusted and may contain apostrophes/entities.
    assert booking_i18n.tt(None, "en", "confirmed_heading", name="Sam") == "You're booked, Sam."
