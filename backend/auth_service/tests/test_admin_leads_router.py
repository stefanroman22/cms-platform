from unittest.mock import MagicMock


def _lead_row(**overrides):
    base = {
        "id": "lead-1",
        "external_id": "ext-1",
        "primary_source": "google_maps",
        "lead_type": "website",
        "business_name": "Acme",
        "name_normalized": "acme",
        "web_presence": "none",
        "website_build_status": "not_started",
        "ai_workflow_status": "not_started",
        "lead_status": "not_sent",
        "lead_contact_type": "not_contacted",
        "payment_status": "not_applicable",
        "extra": {},
        "photo_urls": [],
        "closed_amount": None,
        "closed_at": None,
        "created_at": "2026-05-17T10:00:00Z",
        "updated_at": "2026-05-17T10:00:00Z",
    }
    base.update(overrides)
    return base


def test_list_leads_requires_admin(client, auth_as, client_user):
    auth_as(client_user)
    resp = client.get("/admin/leads")
    assert resp.status_code == 403


def test_list_leads_admin_happy_path(mock_supabase, client, auth_as, admin_user):
    auth_as(admin_user)
    mock_supabase.execute.return_value = MagicMock(
        data=[
            {
                "id": "lead-1",
                "external_id": "ext-1",
                "primary_source": "google_maps",
                "lead_type": "website",
                "business_name": "Acme",
                "name_normalized": "acme",
                "web_presence": "none",
                "website_build_status": "not_started",
                "ai_workflow_status": "not_started",
                "lead_status": "not_sent",
                "lead_contact_type": "not_contacted",
                "payment_status": "not_applicable",
                "extra": {},
                "photo_urls": [],
                "created_at": "2026-05-17T10:00:00Z",
                "updated_at": "2026-05-17T10:00:00Z",
            }
        ]
    )
    resp = client.get("/admin/leads?city=Lelystad&limit=50")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["items"]) == 1
    assert body["items"][0]["business_name"] == "Acme"


def test_patch_lead_status(mock_supabase, client, auth_as, admin_user):
    auth_as(admin_user)
    mock_supabase.execute.return_value = MagicMock(
        data=[
            {
                "id": "lead-1",
                "external_id": "ext-1",
                "primary_source": "google_maps",
                "lead_type": "website",
                "business_name": "Acme",
                "name_normalized": "acme",
                "web_presence": "none",
                "website_build_status": "not_started",
                "ai_workflow_status": "not_started",
                "lead_status": "sent",
                "lead_contact_type": "not_contacted",
                "payment_status": "not_applicable",
                "extra": {},
                "photo_urls": [],
                "created_at": "2026-05-17T10:00:00Z",
                "updated_at": "2026-05-17T10:00:00Z",
            }
        ]
    )
    resp = client.patch("/admin/leads/lead-1", json={"lead_status": "sent"})
    assert resp.status_code == 200
    assert resp.json()["lead_status"] == "sent"


def test_patch_closed_amount_rejected_when_not_accepted(mock_supabase, client, auth_as, admin_user):
    """closed_amount may only be set when the lead is (or becomes) accepted."""
    auth_as(admin_user)
    mock_supabase.execute.side_effect = [
        MagicMock(data={"lead_status": "sent", "closed_amount": None}),  # pre-SELECT
    ]
    resp = client.patch("/admin/leads/lead-1", json={"closed_amount": 1500})
    assert resp.status_code == 422
    assert "accepted" in resp.json()["detail"].lower()


def test_patch_closed_amount_allowed_when_accepted(mock_supabase, client, auth_as, admin_user):
    """When the lead is already accepted, closed_amount can be set."""
    auth_as(admin_user)
    updated_row = _lead_row(
        lead_status="accepted", closed_amount=1500.0, closed_at="2026-05-20T10:00:00Z"
    )
    mock_supabase.execute.side_effect = [
        MagicMock(data={"lead_status": "accepted", "closed_amount": None}),
        MagicMock(data=[updated_row]),
    ]
    resp = client.patch("/admin/leads/lead-1", json={"closed_amount": 1500})
    assert resp.status_code == 200, resp.text
    assert resp.json()["closed_amount"] == 1500.0


def test_patch_status_and_amount_together_allowed(mock_supabase, client, auth_as, admin_user):
    """Setting lead_status='accepted' and closed_amount in the same PATCH succeeds."""
    auth_as(admin_user)
    updated_row = _lead_row(
        lead_status="accepted", closed_amount=2500.0, closed_at="2026-05-20T10:00:00Z"
    )
    mock_supabase.execute.side_effect = [
        MagicMock(data={"lead_status": "sent", "closed_amount": None}),
        MagicMock(data=[updated_row]),
    ]
    resp = client.patch(
        "/admin/leads/lead-1",
        json={"lead_status": "accepted", "closed_amount": 2500},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["closed_amount"] == 2500.0
