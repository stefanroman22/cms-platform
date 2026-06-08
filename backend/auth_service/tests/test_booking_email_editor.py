"""Tests for the email-template schema, email-preview, and logo endpoints (A5+A6)."""

from io import BytesIO
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from auth_service.main import app
from auth_service.models.schemas import UserOut
from auth_service.services.booking_i18n import STRINGS

OWNER = UserOut(id="u1", email="o@acme.com", full_name="O", is_admin=False)
PROJECT = {"id": "t1", "name": "Acme", "slug": "acme", "user_id": "u1", "is_active": True}


@pytest.fixture
def client():
    return TestClient(app)


def _auth(user=OWNER, project=PROJECT):
    return (
        patch(
            "auth_service.routers.booking_admin.user_via_bearer_or_session",
            new=AsyncMock(return_value=user),
        ),
        patch("auth_service.routers.booking_admin.require_project_access", return_value=project),
    )


# ---- A5: email-template schema endpoint ----


def test_get_email_template_returns_fields_and_brand(client):
    row = {
        "email_copy": {"join_cta": "Join"},
        "logo_url": "https://example.com/logo.png",
        "accent_color": "#ff0000",
        "business_name": "Acme",
    }
    ru, rp = _auth()
    with (
        ru,
        rp,
        patch(
            "auth_service.routers.booking_admin.booking_admin_repo.get_settings",
            return_value=row,
        ),
    ):
        r = client.get("/projects/acme/bookings/email-template")
    assert r.status_code == 200
    body = r.json()
    assert "fields" in body and "brand" in body
    # brand keys present
    assert body["brand"]["logo_url"] == "https://example.com/logo.png"
    assert body["brand"]["accent_color"] == "#ff0000"
    assert body["brand"]["business_name"] == "Acme"
    # join_cta field should have value "Join" and default from current STRINGS
    join_field = next(f for f in body["fields"] if f["key"] == "join_cta")
    assert join_field["value"] == "Join"
    assert join_field["default"] == STRINGS["en"]["join_cta"]
    # confirm_subject should also be present
    confirm_field = next(f for f in body["fields"] if f["key"] == "confirm_subject")
    assert confirm_field["default"] == STRINGS["en"]["confirm_subject"]


def test_get_email_template_no_settings_returns_empty(client):
    ru, rp = _auth()
    with (
        ru,
        rp,
        patch(
            "auth_service.routers.booking_admin.booking_admin_repo.get_settings",
            return_value=None,
        ),
    ):
        r = client.get("/projects/acme/bookings/email-template")
    assert r.status_code == 200
    body = r.json()
    # all values should be empty string when no overrides
    for f in body["fields"]:
        assert f["value"] == ""


# ---- A6: email-preview endpoint ----


def test_email_preview_confirmation(client):
    ru, rp = _auth()
    with ru, rp:
        r = client.post(
            "/projects/acme/bookings/email-preview",
            json={
                "case": "confirmation",
                "draft": {
                    "email_copy": {"confirmed_heading": "All set, {name}!"},
                    "accent_color": "#abcdef",
                },
            },
        )
    assert r.status_code == 200
    html = r.json()["html"]
    assert "All set, Alex" in html
    assert "#abcdef" in html


def test_email_preview_reschedule(client):
    ru, rp = _auth()
    with ru, rp:
        r = client.post(
            "/projects/acme/bookings/email-preview",
            json={
                "case": "reschedule",
                "draft": {"email_copy": {"reschedule_client_heading": "Moved, {name}!"}},
            },
        )
    assert r.status_code == 200
    html = r.json()["html"]
    assert "Moved, Alex" in html


def test_email_preview_cancellation(client):
    ru, rp = _auth()
    with ru, rp:
        r = client.post(
            "/projects/acme/bookings/email-preview",
            json={
                "case": "cancellation",
                "draft": {"email_copy": {"cancel_client_heading": "Oops, {name}!"}},
            },
        )
    assert r.status_code == 200
    html = r.json()["html"]
    assert "Oops, Alex" in html


def test_email_preview_reminder(client):
    ru, rp = _auth()
    with ru, rp:
        r = client.post(
            "/projects/acme/bookings/email-preview",
            json={
                "case": "reminder",
                "draft": {"email_copy": {"reminder_heading": "Almost time, {name}!"}},
            },
        )
    assert r.status_code == 200
    html = r.json()["html"]
    assert "Almost time, Alex" in html


def test_email_preview_unknown_case(client):
    ru, rp = _auth()
    with ru, rp:
        r = client.post(
            "/projects/acme/bookings/email-preview",
            json={
                "case": "unknown_case",
                "draft": {},
            },
        )
    assert r.status_code == 422


# ---- A6: logo endpoint ----


def _make_storage_mock():
    storage = MagicMock()
    storage.from_.return_value.upload.return_value = None
    storage.from_.return_value.get_public_url.return_value = "https://cdn.example.com/path/logo.png"
    return storage


def test_logo_upload_valid(client):
    ru, rp = _auth()
    mock_sb = MagicMock()
    mock_sb.storage = _make_storage_mock()
    with (
        ru,
        rp,
        patch("auth_service.routers.booking_admin.get_supabase_admin", return_value=mock_sb),
    ):
        r = client.post(
            "/projects/acme/bookings/logo",
            files={"file": ("logo.png", BytesIO(b"PNG" * 100), "image/png")},
        )
    assert r.status_code == 200
    assert "url" in r.json()


def test_logo_upload_oversize(client):
    ru, rp = _auth()
    big_content = b"x" * (5 * 1024 * 1024 + 1)
    with ru, rp:
        r = client.post(
            "/projects/acme/bookings/logo",
            files={"file": ("logo.png", BytesIO(big_content), "image/png")},
        )
    assert r.status_code == 413


def test_logo_upload_svg_rejected(client):
    ru, rp = _auth()
    with ru, rp:
        r = client.post(
            "/projects/acme/bookings/logo",
            files={"file": ("logo.svg", BytesIO(b"<svg/>"), "image/svg+xml")},
        )
    assert r.status_code == 415


def test_logo_upload_non_image_rejected(client):
    ru, rp = _auth()
    with ru, rp:
        r = client.post(
            "/projects/acme/bookings/logo",
            files={"file": ("doc.pdf", BytesIO(b"%PDF"), "application/pdf")},
        )
    assert r.status_code == 415
