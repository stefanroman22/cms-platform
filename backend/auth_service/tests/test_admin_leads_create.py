from unittest.mock import MagicMock


def _created_row(**overrides):
    """A minimal leads row as Supabase would return it after insert."""
    base = {
        "id": "lead-new",
        "external_id": "manual:abc-123",
        "primary_source": "manual",
        "lead_type": "website",
        "business_name": "Manual Co",
        "name_normalized": "manual co",
        "web_presence": "unknown",
        "website_build_status": "not_started",
        "ai_workflow_status": "not_started",
        "lead_status": "not_sent",
        "lead_contact_type": "not_contacted",
        "payment_status": "not_applicable",
        "extra": {},
        "photo_urls": [],
        "languages": [],
        "reviews": None,
        "address": None,
        "city": None,
        "country": None,
        "region": None,
        "postal_code": None,
        "lat": None,
        "lng": None,
        "phone": None,
        "email": None,
        "website_url": None,
        "facebook_url": None,
        "instagram_url": None,
        "menu_url": None,
        "description": None,
        "about": None,
        "design_prompt": None,
        "opening_hours": None,
        "rating": None,
        "review_count": None,
        "notes": None,
        "closed_amount": None,
        "closed_at": None,
        "created_at": "2026-06-08T10:00:00Z",
        "updated_at": "2026-06-08T10:00:00Z",
    }
    base.update(overrides)
    return base


def test_create_lead_requires_admin(client, auth_as, client_user):
    """Non-admin callers cannot create leads."""
    auth_as(client_user)
    resp = client.post("/admin/leads", json={"business_name": "Manual Co"})
    assert resp.status_code == 403


def test_create_lead_happy_path(mock_supabase, client, auth_as, admin_user):
    """A minimal payload inserts and returns the created lead as LeadOut.
    primary_source is forced to 'manual'."""
    auth_as(admin_user)
    captured = {}

    def capture_insert(payload):
        captured["payload"] = payload
        chain = MagicMock()
        chain.execute.return_value = MagicMock(
            data=[
                _created_row(
                    business_name=payload["business_name"],
                    lead_type=payload.get("lead_type", "website"),
                    primary_source=payload["primary_source"],
                    external_id=payload["external_id"],
                )
            ]
        )
        return chain

    mock_supabase.insert.side_effect = capture_insert

    resp = client.post(
        "/admin/leads",
        json={"business_name": "Manual Co", "lead_type": "website"},
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["id"]
    assert body["business_name"] == "Manual Co"
    assert body["primary_source"] == "manual"
    # The router forces primary_source and a manual external_id on the insert.
    assert captured["payload"]["primary_source"] == "manual"
    assert captured["payload"]["external_id"].startswith("manual:")


def test_create_lead_reviews_round_trip(mock_supabase, client, auth_as, admin_user):
    """A posted reviews array is persisted and echoed back in the response."""
    auth_as(admin_user)
    reviews = [{"author": "Jane", "rating": 5, "text": "Great", "date": "2026-01-01"}]

    def capture_insert(payload):
        chain = MagicMock()
        chain.execute.return_value = MagicMock(data=[_created_row(reviews=payload.get("reviews"))])
        return chain

    mock_supabase.insert.side_effect = capture_insert

    resp = client.post(
        "/admin/leads",
        json={"business_name": "Manual Co", "reviews": reviews},
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["reviews"] == reviews


def test_create_lead_missing_business_name_returns_422(client, auth_as, admin_user):
    """business_name is required."""
    auth_as(admin_user)
    resp = client.post("/admin/leads", json={"lead_type": "website"})
    assert resp.status_code == 422


def test_create_lead_blank_business_name_returns_422(client, auth_as, admin_user):
    """An empty business_name fails min_length validation."""
    auth_as(admin_user)
    resp = client.post("/admin/leads", json={"business_name": ""})
    assert resp.status_code == 422


def test_create_lead_invalid_email_returns_422(client, auth_as, admin_user):
    """Malformed email is rejected before any DB write."""
    auth_as(admin_user)
    resp = client.post(
        "/admin/leads",
        json={"business_name": "Manual Co", "email": "not-an-email"},
    )
    assert resp.status_code == 422
