"""Tests for the issue-resolved client email service.

The service mirrors `welcome_email` + `project_request_email`:
  - HTML rendering with caller-controlled fields HTML-escaped
  - http(s)-only URL guard (defense-in-depth, BE-006)
  - `RESEND_API_KEY` required to actually POST
  - preview-tier short-circuit on the [E2E-TEST] marker
"""

from __future__ import annotations

import json
from unittest.mock import patch

import pytest

from ..services import issue_resolved_email


def _issue() -> dict:
    return {
        "id": "issue-42",
        "title": "Hero image broken",
        "description": "Stretches on mobile",
        "priority": "High",
    }


def _project() -> dict:
    return {
        "id": "project-acme",
        "slug": "acme",
        "name": "Acme Corp",
        "preview_url": "https://acme-dev.vercel.app",
    }


def test_render_html_happy_path():
    """HTML body contains the issue title, project name, and preview link."""
    html = issue_resolved_email.render_issue_resolved_html(
        client_name="Laurian",
        issue=_issue(),
        project=_project(),
    )
    assert "Hero image broken" in html
    assert "Acme Corp" in html
    assert "https://acme-dev.vercel.app" in html
    # Friendly greeting on the client name.
    assert "Laurian" in html


def test_render_html_escapes_user_controlled_fields():
    """Caller-controlled strings must be HTML-escaped (BE-006).

    A malicious <script> tag in the issue title would otherwise execute
    in Gmail's preview pane on some clients.
    """
    issue = {**_issue(), "title": "<script>alert('xss')</script>"}
    project = {**_project(), "name": "Acme & Co <bad>"}

    html = issue_resolved_email.render_issue_resolved_html(
        client_name="<b>Laurian</b>",
        issue=issue,
        project=project,
    )
    assert "<script>" not in html
    assert "&lt;script&gt;" in html
    assert "Acme &amp; Co &lt;bad&gt;" in html
    assert "<b>Laurian</b>" not in html
    assert "&lt;b&gt;Laurian&lt;/b&gt;" in html


def test_render_html_drops_non_http_preview_url():
    """`javascript:` and `data:` preview URLs render as the safe fallback."""
    project = {**_project(), "preview_url": "javascript:alert(1)"}
    html = issue_resolved_email.render_issue_resolved_html(
        client_name="Laurian",
        issue=_issue(),
        project=project,
    )
    assert "javascript:alert(1)" not in html
    # Falls back to the canonical site.
    assert "roman-technologies.dev" in html


def test_send_raises_when_resend_api_key_unset(monkeypatch):
    """No silent no-op — caller must know the email did not go out."""
    from ..core import config

    monkeypatch.setattr(config.settings, "RESEND_API_KEY", "")
    monkeypatch.setattr(config.settings, "ENVIRONMENT", "production")

    with pytest.raises(RuntimeError, match="RESEND_API_KEY"):
        issue_resolved_email.send(
            to_email="client@example.com",
            issue=_issue(),
            project=_project(),
        )


def test_send_posts_to_resend(monkeypatch):
    """Happy path: posts a multipart (html+text) body to api.resend.com."""
    from ..core import config

    monkeypatch.setattr(config.settings, "RESEND_API_KEY", "re_test")
    monkeypatch.setattr(config.settings, "ENVIRONMENT", "production")
    monkeypatch.setattr(config.settings, "RESEND_FROM_EMAIL", "noreply@roman-technologies.dev")
    monkeypatch.setattr(config.settings, "RESEND_FROM_NAME", "Roman Technologies CMS")

    captured: dict = {}

    class _FakeResp:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self):
            return b'{"id":"resend_abc"}'

    def fake_urlopen(req, timeout):  # noqa: ARG001
        captured["url"] = req.full_url
        captured["headers"] = dict(req.header_items())
        captured["body"] = json.loads(req.data.decode())
        return _FakeResp()

    with patch("urllib.request.urlopen", side_effect=fake_urlopen):
        result = issue_resolved_email.send(
            to_email="client@example.com",
            client_name="Laurian",
            issue=_issue(),
            project=_project(),
        )

    assert result == {"id": "resend_abc"}
    assert captured["url"] == "https://api.resend.com/emails"
    # Authorization header carries the API key.
    auth = {k.lower(): v for k, v in captured["headers"].items()}.get("Authorization".lower())
    assert auth == "Bearer re_test"
    body = captured["body"]
    assert body["to"] == "client@example.com"
    assert "Hero image broken" in body["subject"]
    assert "html" in body and "text" in body
    assert "Hero image broken" in body["html"]
    assert "Hero image broken" in body["text"]


def test_send_short_circuits_for_e2e_marker(monkeypatch):
    """When environment is preview and a field contains [E2E-TEST], skip Resend.

    Matches the e2e_email_guard heuristic used by welcome_email + project_request_email.
    """
    from ..core import config

    monkeypatch.setattr(config.settings, "RESEND_API_KEY", "re_test")
    monkeypatch.setattr(config.settings, "ENVIRONMENT", "preview")

    # The [E2E-TEST] marker on the project name triggers the short-circuit.
    project = {**_project(), "name": "[E2E-TEST] Acme"}
    result = issue_resolved_email.send(
        to_email="client@example.com",
        issue=_issue(),
        project=project,
    )

    # e2e_email_guard returns a stable sentinel — no real Resend POST happened.
    assert "e2e-test" in json.dumps(result).lower() or "skipped" in json.dumps(result).lower()
