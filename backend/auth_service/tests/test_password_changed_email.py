"""The "your password was changed" security notice (no secret in the body)."""

from datetime import UTC, datetime

import pytest

from auth_service.services import password_changed_email as pce

AT = datetime(2026, 9, 25, 14, 5, tzinfo=UTC)


@pytest.mark.parametrize("reason", ["admin_reset", "self_service"])
def test_html_uses_branded_chrome_and_states_the_change(reason):
    out = pce.render_html(email="george@example.com", reason=reason, changed_at=AT)
    assert "Roman Technologies" in out  # shared email_layout header
    assert "background:#18181b" in out
    assert "Your password was changed" in out
    assert "george@example.com" in out
    assert "Fri 25 Sep 2026, 14:05 UTC" in out
    assert "https://roman-technologies.dev/log-in" in out
    assert "Didn&#x27;t expect this?" in out or "Didn't expect this?" in out


def test_admin_reset_copy_says_password_comes_out_of_band():
    out = pce.render_text(email="g@example.com", reason="admin_reset", changed_at=AT)
    assert "not by email" in out
    assert "signed out everywhere" in out


def test_self_service_copy():
    out = pce.render_text(email="g@example.com", reason="self_service", changed_at=AT)
    assert "Account Settings" in out
    assert "other devices" in out


def test_email_address_is_escaped():
    out = pce.render_html(email="<script>x</script>@e.com", reason="self_service", changed_at=AT)
    assert "<script>" not in out
    assert "&lt;script&gt;" in out


def test_send_posts_notice_with_reply_to_and_no_password(monkeypatch):
    calls = []
    monkeypatch.setattr(pce, "send_via_resend", lambda **kw: calls.append(kw) or {"id": "r1"})
    res = pce.send_password_changed_email(
        to_email="george@example.com", reason="admin_reset", changed_at=AT
    )
    assert res == {"id": "r1"}
    (kw,) = calls
    assert kw["to_email"] == "george@example.com"
    assert kw["subject"] == "Your Roman Technologies password was changed"
    assert kw["reply_to"]
    body = (kw["html_body"] + kw["text_body"]).lower()
    # Nothing in the notice looks like a credential or a reset token.
    assert "your new password is" not in body
    assert "token" not in body


def test_send_short_circuits_e2e_marker_in_preview(monkeypatch):
    from auth_service.core.config import settings

    monkeypatch.setattr(settings, "ENVIRONMENT", "preview")
    monkeypatch.setattr(pce, "send_via_resend", lambda **_kw: pytest.fail("should not send"))
    res = pce.send_password_changed_email(
        to_email="[E2E-TEST]x@cms-test.dev", reason="self_service"
    )
    assert res.get("id")
