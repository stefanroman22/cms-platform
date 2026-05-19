from unittest.mock import MagicMock


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
