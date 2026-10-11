import asyncio
from unittest.mock import MagicMock

import pytest

from auth_service.core.config import settings
from auth_service.routers import admin_leads
from auth_service.services.google_places.client import GooglePlacesError
from auth_service.services.google_places.importer import (
    DuplicateLead,
    ImportOutcome,
    MissingPlaceId,
    MonthlyCapReached,
)
from auth_service.services.google_places.quota import QuotaUnavailable


def _lead(**over):
    base = {
        "id": "lead-1",
        "external_id": "google:ChIJx",
        "primary_source": "google_maps",
        "lead_type": "website",
        "business_name": "Acme",
        "name_normalized": "acme",
        "web_presence": "has_website",
        "website_build_status": "not_started",
        "ai_workflow_status": "not_started",
        "lead_status": "not_sent",
        "lead_contact_type": "not_contacted",
        "payment_status": "not_applicable",
        "extra": {},
        "photo_urls": [],
        "google_place_id": "ChIJx",
        "created_at": "2026-10-11T10:00:00Z",
        "updated_at": "2026-10-11T10:00:00Z",
    }
    base.update(over)
    return base


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.setattr(settings, "GOOGLE_MAPS_API_KEY", "k")
    monkeypatch.setattr(admin_leads, "enforce", lambda *a, **k: None)


def test_import_requires_admin(client, auth_as, client_user):
    auth_as(client_user)
    assert client.post("/admin/leads/google-import", json={"input": "x"}).status_code == 403


def test_import_blank_input_422(mock_supabase, client, auth_as, admin_user):
    auth_as(admin_user)
    r = client.post("/admin/leads/google-import", json={"input": "   "})
    assert r.status_code == 422 and "Paste a Google Maps link" in r.json()["detail"]


def test_import_503_without_key(mock_supabase, client, auth_as, admin_user, monkeypatch):
    monkeypatch.setattr(settings, "GOOGLE_MAPS_API_KEY", "")
    auth_as(admin_user)
    r = client.post("/admin/leads/google-import", json={"input": "ChIJx"})
    assert r.status_code == 503 and "not configured" in r.json()["detail"]


def test_import_created(mock_supabase, client, auth_as, admin_user, monkeypatch):
    auth_as(admin_user)
    seen = {}

    def fake(sb, *, raw_input, lead_type, language):
        seen.update(raw_input=raw_input, lead_type=lead_type, language=language)
        return ImportOutcome(_lead(), [], ["website enrichment skipped: x"])

    monkeypatch.setattr(admin_leads, "import_place", fake)
    r = client.post(
        "/admin/leads/google-import",
        json={"input": " https://maps.app.goo.gl/a ", "lead_type": "both", "language": "nl"},
    )
    assert r.status_code == 201
    assert r.json()["google_place_id"] == "ChIJx"
    assert r.headers["x-import-warnings"] == "1"
    assert seen == {"raw_input": "https://maps.app.goo.gl/a", "lead_type": "both", "language": "nl"}


def test_import_runs_off_the_event_loop(mock_supabase, client, auth_as, admin_user, monkeypatch):
    auth_as(admin_user)
    seen = {}

    def fake(sb, **k):
        try:
            asyncio.get_running_loop()
            seen["on_loop"] = True
        except RuntimeError:
            seen["on_loop"] = False
        return ImportOutcome(_lead(), [], [])

    monkeypatch.setattr(admin_leads, "import_place", fake)
    assert client.post("/admin/leads/google-import", json={"input": "ChIJx"}).status_code == 201
    assert seen == {"on_loop": False}


def test_reimport_runs_off_the_event_loop(mock_supabase, client, auth_as, admin_user, monkeypatch):
    auth_as(admin_user)
    mock_supabase.execute.return_value = MagicMock(data=_lead())
    seen = {}

    def fake(sb, current, **k):
        try:
            asyncio.get_running_loop()
            seen["on_loop"] = True
        except RuntimeError:
            seen["on_loop"] = False
        return ImportOutcome(_lead(), [], [])

    monkeypatch.setattr(admin_leads, "reimport_place", fake)
    assert client.post("/admin/leads/lead-1/google-import", json={}).status_code == 200
    assert seen == {"on_loop": False}


def test_import_candidates(mock_supabase, client, auth_as, admin_user, monkeypatch):
    auth_as(admin_user)
    monkeypatch.setattr(
        admin_leads,
        "import_place",
        lambda sb, **k: ImportOutcome(None, [{"place_id": "a", "name": "A", "address": None}]),
    )
    r = client.post("/admin/leads/google-import", json={"input": "Kapsalon"})
    assert r.status_code == 200
    assert r.json() == {
        "status": "candidates",
        "candidates": [{"place_id": "a", "name": "A", "address": None}],
        "warnings": [],
    }


def test_import_unresolvable_404(mock_supabase, client, auth_as, admin_user, monkeypatch):
    auth_as(admin_user)
    monkeypatch.setattr(admin_leads, "import_place", lambda sb, **k: ImportOutcome(None, []))
    r = client.post("/admin/leads/google-import", json={"input": "https://maps.app.goo.gl/dead"})
    assert r.status_code == 404


def test_import_duplicate_409(mock_supabase, client, auth_as, admin_user, monkeypatch):
    auth_as(admin_user)

    def dup(sb, **k):
        raise DuplicateLead("lead-7")

    monkeypatch.setattr(admin_leads, "import_place", dup)
    r = client.post("/admin/leads/google-import", json={"input": "ChIJx"})
    assert r.status_code == 409 and r.json()["detail"]["lead_id"] == "lead-7"


def test_import_monthly_cap_429(mock_supabase, client, auth_as, admin_user, monkeypatch):
    auth_as(admin_user)

    def cap(sb, **k):
        raise MonthlyCapReached()

    monkeypatch.setattr(admin_leads, "import_place", cap)
    r = client.post("/admin/leads/google-import", json={"input": "ChIJx"})
    assert r.status_code == 429 and "GOOGLE_PLACES_MONTHLY_CAP" in r.json()["detail"]


def test_import_quota_unavailable_503(mock_supabase, client, auth_as, admin_user, monkeypatch):
    auth_as(admin_user)

    def down(sb, **k):
        raise QuotaUnavailable()

    monkeypatch.setattr(admin_leads, "import_place", down)
    r = client.post("/admin/leads/google-import", json={"input": "ChIJx"})
    assert r.status_code == 503
    assert r.json()["detail"] == "Import counter unavailable; try again shortly."


def test_import_per_user_limit_429(mock_supabase, client, auth_as, admin_user, monkeypatch):
    auth_as(admin_user)
    from fastapi import HTTPException

    def limited(bucket, limit, window, detail="x"):
        assert bucket == "google_import:user:admin-uuid" and (limit, window) == (20, 3600)
        raise HTTPException(status_code=429, detail=detail)

    monkeypatch.setattr(admin_leads, "enforce", limited)
    assert client.post("/admin/leads/google-import", json={"input": "ChIJx"}).status_code == 429


@pytest.mark.parametrize(
    "gstatus,expected", [(400, 422), (403, 502), (404, 404), (429, 503), (500, 502), (504, 504)]
)
def test_import_google_errors(
    mock_supabase, client, auth_as, admin_user, monkeypatch, gstatus, expected
):
    auth_as(admin_user)

    def boom(sb, **k):
        raise GooglePlacesError(gstatus, "msg")

    monkeypatch.setattr(admin_leads, "import_place", boom)
    r = client.post("/admin/leads/google-import", json={"input": "ChIJx"})
    assert r.status_code == expected and "msg" in r.json()["detail"]


def test_reimport_ok(mock_supabase, client, auth_as, admin_user, monkeypatch):
    auth_as(admin_user)
    mock_supabase.execute.return_value = MagicMock(data=_lead())
    seen = {}

    def fake(sb, current, *, raw_input, overwrite, language):
        seen.update(cur=current["id"], raw_input=raw_input, overwrite=overwrite)
        return ImportOutcome(_lead(business_name="Fresh"), [], [])

    monkeypatch.setattr(admin_leads, "reimport_place", fake)
    r = client.post("/admin/leads/lead-1/google-import", json={"overwrite": True})
    assert r.status_code == 200 and r.json()["business_name"] == "Fresh"
    assert seen == {"cur": "lead-1", "raw_input": None, "overwrite": True}


def test_reimport_404_unknown_lead(mock_supabase, client, auth_as, admin_user):
    auth_as(admin_user)
    mock_supabase.execute.return_value = None
    assert client.post("/admin/leads/nope/google-import", json={}).status_code == 404


def test_reimport_422_without_place(mock_supabase, client, auth_as, admin_user, monkeypatch):
    auth_as(admin_user)
    mock_supabase.execute.return_value = MagicMock(data=_lead(google_place_id=None))

    def no_place(sb, current, **k):
        raise MissingPlaceId(
            "This lead has no Google place ID; paste a Google Maps link to import."
        )

    monkeypatch.setattr(admin_leads, "reimport_place", no_place)
    r = client.post("/admin/leads/lead-1/google-import", json={})
    assert r.status_code == 422 and "no Google place ID" in r.json()["detail"]
