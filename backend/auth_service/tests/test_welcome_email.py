"""Welcome / onboarding email template (rendered on the shared email_layout chrome)."""

from auth_service.services import welcome_email as we


def _render(**kw):
    args = {
        "full_name": "George Nadejde",
        "project_name": "IT Global Services",
        "website_url": "https://it-global.example",
        "to_email": "george@example.com",
    }
    args.update(kw)
    return we.render_welcome_html(**args)


def test_uses_shared_branded_chrome():
    out = _render()
    assert "Roman Technologies" in out
    assert "background:#18181b" in out  # email_layout header
    assert "Sent from" in out  # email_layout footer


def test_content_greets_by_first_name_and_explains_publish():
    out = _render()
    assert "Welcome aboard, George." in out
    assert "IT Global Services" in out
    assert "george@example.com" in out
    assert "Publish Changes" in out
    assert "https://it-global.example" in out


def test_never_contains_a_password_only_the_out_of_band_note():
    out = _render()
    assert "Sent to you separately" in out


def test_no_name_falls_back_cleanly():
    assert "Welcome aboard." in _render(full_name="")


def test_escapes_caller_fields():
    out = _render(full_name="<b>x</b>", project_name="<script>p</script>")
    assert "<script>" not in out and "<b>x" not in out
    assert "&lt;script&gt;" in out


def test_unsafe_website_url_falls_back():
    out = _render(website_url="javascript:alert(1)")
    assert "javascript:" not in out
    assert "https://roman-technologies.dev" in out


def test_login_url_guard_blocks_vercel_sso_dead_end():
    """Deployment URLs sit behind Vercel SSO — the 2026-08 client trap."""
    out = _render(login_url="https://roman-technologies-abc.vercel.app/log-in")
    assert "vercel.app" not in out
    assert 'href="https://roman-technologies.dev/log-in"' in out
    assert we._safe_login_url("https://roman-technologies.dev.evil.com/x") == we.LOGIN_URL
    assert we._safe_login_url("https://roman-technologies.dev/log-in?x=1") == (
        "https://roman-technologies.dev/log-in?x=1"
    )


def test_send_builds_resend_payload(monkeypatch):
    calls = []
    monkeypatch.setattr(we, "send_via_resend", lambda **kw: calls.append(kw) or {"id": "r1"})
    res = we.send_welcome_email(
        to_email="george@example.com",
        full_name="George",
        project_name="IT Global",
        website_url="https://it-global.example",
    )
    assert res == {"id": "r1"}
    (kw,) = calls
    assert kw["subject"] == "Your IT Global dashboard is ready"
    assert "Welcome aboard, George." in kw["text_body"]
    assert kw["reply_to"]
