"""Integration tests for routers/admin_conversions.py."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest


@pytest.fixture(autouse=True)
def _patch_admin_conversions_supabase(monkeypatch, mock_supabase):
    """Bind the conversions router's get_supabase_admin to the shared mock."""
    from auth_service.routers import admin_conversions

    monkeypatch.setattr(admin_conversions, "get_supabase_admin", lambda: mock_supabase)


def test_summary_requires_admin(client, auth_as, client_user):
    auth_as(client_user)
    assert client.get("/admin/conversions/summary").status_code == 403


def test_summary_empty_dataset(mock_supabase, client, auth_as, admin_user):
    auth_as(admin_user)
    mock_supabase.execute.return_value = MagicMock(data=[])
    resp = client.get("/admin/conversions/summary")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["total_sent"] == 0
    assert body["total_accepted"] == 0
    assert body["conversion_rate"] == 0.0
    assert body["total_revenue"] == 0.0
    assert body["timeseries"] == []
    assert body["by_lead_type"] == []


def test_summary_computes_conversion_rate(mock_supabase, client, auth_as, admin_user):
    auth_as(admin_user)
    rows = [
        {
            "lead_status": "sent",
            "closed_amount": None,
            "closed_at": None,
            "lead_type": "website",
            "category": "restaurants",
            "city": "Lelystad",
        },
        {
            "lead_status": "sent",
            "closed_amount": None,
            "closed_at": None,
            "lead_type": "website",
            "category": "barber",
            "city": "Almere",
        },
        {
            "lead_status": "accepted",
            "closed_amount": 1500,
            "closed_at": "2026-04-10T10:00Z",
            "lead_type": "website",
            "category": "restaurants",
            "city": "Lelystad",
        },
        {
            "lead_status": "accepted",
            "closed_amount": 2500,
            "closed_at": "2026-05-05T10:00Z",
            "lead_type": "automation",
            "category": "barber",
            "city": "Almere",
        },
        {
            "lead_status": "refused",
            "closed_amount": None,
            "closed_at": None,
            "lead_type": "website",
            "category": "barber",
            "city": "Lelystad",
        },
    ]
    mock_supabase.execute.return_value = MagicMock(data=rows)
    resp = client.get("/admin/conversions/summary")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["total_sent"] == 2
    assert body["total_accepted"] == 2
    assert body["total_refused"] == 1
    assert body["conversion_rate"] == pytest.approx(2 / 5)
    assert body["total_revenue"] == 4000.0
    assert body["average_deal_size"] == 2000.0
    months = {p["month"]: p for p in body["timeseries"]}
    assert months["2026-04"]["revenue"] == 1500.0
    assert months["2026-04"]["accepted"] == 1
    assert months["2026-05"]["revenue"] == 2500.0
    by_type = {r["key"]: r for r in body["by_lead_type"]}
    assert by_type["website"]["accepted"] == 1
    assert by_type["automation"]["accepted"] == 1
