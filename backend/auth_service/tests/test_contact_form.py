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
