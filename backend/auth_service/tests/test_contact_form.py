from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from auth_service.core.config import settings
from auth_service.main import app


@pytest.fixture
def client():
    return TestClient(app)


def test_contact_happy_path(client, monkeypatch):
    monkeypatch.setattr(settings, "RESEND_API_KEY", "test_key")
    with patch("resend.Emails.send") as mock_send:
        mock_send.return_value = {"id": "resend_x"}
        r = client.post(
            "/forms/contact",
            json={
                "name": "Jane Doe",
                "email": "jane@acme.com",
                "company": "Acme",
                "message": "I would like a website please.",
            },
        )
        assert r.status_code == 200, r.text
        assert r.json()["success"] is True
        mock_send.assert_called_once()
        params = mock_send.call_args.args[0]
        assert params["to"] == ["stefanromanpers@gmail.com"]
        assert params["reply_to"] == "jane@acme.com"


def test_contact_honeypot_silently_accepted(client, monkeypatch):
    monkeypatch.setattr(settings, "RESEND_API_KEY", "test_key")
    with patch("resend.Emails.send") as mock_send:
        r = client.post(
            "/forms/contact",
            json={
                "name": "Bot",
                "email": "bot@spam.com",
                "message": "spam spam spam",
                "website": "http://spam.com",
            },
        )
        assert r.status_code == 200
        assert r.json()["success"] is True
        mock_send.assert_not_called()


def test_contact_422_on_empty_body(client):
    r = client.post("/forms/contact", json={})
    assert r.status_code == 422


def test_contact_422_on_bad_email(client, monkeypatch):
    monkeypatch.setattr(settings, "RESEND_API_KEY", "test_key")
    r = client.post(
        "/forms/contact",
        json={"name": "Jane", "email": "not-an-email", "message": "hello there friend"},
    )
    assert r.status_code == 422


def test_contact_502_on_resend_failure(client, monkeypatch):
    monkeypatch.setattr(settings, "RESEND_API_KEY", "test_key")
    with patch("resend.Emails.send", side_effect=RuntimeError("Resend down")):
        r = client.post(
            "/forms/contact",
            json={"name": "Jane", "email": "jane@acme.com", "message": "hello there friend"},
        )
        assert r.status_code == 502


# Each SEC-059 test stamps its own X-Forwarded-For (documentation range,
# RFC 5737) so it lands in its own slowapi + Postgres bucket and never collides
# with the other tests' per-IP counters — mirrors the integration-test convention.
def test_contact_uses_shared_cross_instance_limit(client, monkeypatch):
    """SEC-059: /contact must go through the Postgres (cross-instance) limiter,
    not only the per-process slowapi one — otherwise Resend email-spam can be
    amplified across serverless instances. Assert the shared limiter is invoked
    for a well-formed, non-honeypot submission."""
    monkeypatch.setattr(settings, "RESEND_API_KEY", "test_key")
    with (
        patch("auth_service.core.pg_rate_limit.allow", return_value=True) as mock_allow,
        patch("resend.Emails.send", return_value={"id": "resend_x"}),
    ):
        r = client.post(
            "/forms/contact",
            json={"name": "Jane Doe", "email": "jane@acme.com", "message": "hello there friend"},
            headers={"X-Forwarded-For": "198.51.100.10"},
        )
        assert r.status_code == 200, r.text
        assert mock_allow.called, "submit_contact did not consult the shared limiter"
        bucket = mock_allow.call_args.args[0] if mock_allow.call_args.args else ""
        assert bucket.startswith("forms:contact:"), bucket


def test_contact_429_when_shared_limit_exceeded(client, monkeypatch):
    """SEC-059: when the shared limiter reports the bucket is over its limit the
    endpoint must reject with 429 and never reach Resend."""
    monkeypatch.setattr(settings, "RESEND_API_KEY", "test_key")
    with (
        patch("auth_service.core.pg_rate_limit.allow", return_value=False),
        patch("resend.Emails.send") as mock_send,
    ):
        r = client.post(
            "/forms/contact",
            json={"name": "Jane Doe", "email": "jane@acme.com", "message": "hello there friend"},
            headers={"X-Forwarded-For": "198.51.100.11"},
        )
        assert r.status_code == 429, r.text
        mock_send.assert_not_called()


def test_contact_honeypot_does_not_consume_shared_limit(client, monkeypatch):
    """A honeypot hit is silently accepted and must not burn the shared bucket
    (so a bot cannot exhaust a legitimate visitor's per-IP allowance)."""
    monkeypatch.setattr(settings, "RESEND_API_KEY", "test_key")
    with patch("auth_service.core.pg_rate_limit.allow", return_value=True) as mock_allow:
        r = client.post(
            "/forms/contact",
            json={
                "name": "Bot",
                "email": "bot@spam.com",
                "message": "spam spam spam",
                "website": "http://spam.com",
            },
            headers={"X-Forwarded-For": "198.51.100.12"},
        )
        assert r.status_code == 200
        mock_allow.assert_not_called()
