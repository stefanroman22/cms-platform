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
        "address": None,
        "city": None,
        "country": None,
        "postal_code": None,
        "lat": None,
        "lng": None,
        "phone": None,
        "email": None,
        "website_url": None,
        "facebook_url": None,
        "instagram_url": None,
        "menu_url": None,
        "design_prompt": None,
        "opening_hours": None,
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


def test_patch_closed_amount_can_be_cleared_to_null(mock_supabase, client, auth_as, admin_user):
    """Sending {closed_amount: null} must clear the column, not be stripped by
    exclude_unset. This is the regression for the 'No fields to update' bug
    that fired when the user cleared the Deal amount field after a value was
    saved (exclude_none would drop the explicit null and leave an empty patch
    dict)."""
    auth_as(admin_user)
    updated_row = _lead_row(lead_status="accepted", closed_amount=None, closed_at=None)
    mock_supabase.execute.side_effect = [
        MagicMock(data={"lead_status": "accepted", "closed_amount": 1500.0}),
        MagicMock(data=[updated_row]),
    ]
    resp = client.patch("/admin/leads/lead-1", json={"closed_amount": None})
    assert resp.status_code == 200, resp.text
    assert resp.json()["closed_amount"] is None


def test_patch_location_and_contact_fields(mock_supabase, client, auth_as, admin_user):
    """Patching location + contact fields persists each one. exclude_unset
    keeps them in the patch dict; HttpUrl / EmailStr coerce to str before DB."""
    auth_as(admin_user)
    updated = _lead_row(
        address="Main St 1",
        city="Lelystad",
        country="NL",
        postal_code="8232",
        lat=52.5,
        lng=5.5,
        phone="+31 6 12345678",
        email="hi@acme.test",
        website_url="https://acme.test/",
        facebook_url="https://facebook.com/acme",
        instagram_url="https://instagram.com/acme",
        menu_url="https://acme.test/menu",
    )
    mock_supabase.execute.return_value = MagicMock(data=[updated])
    resp = client.patch(
        "/admin/leads/lead-1",
        json={
            "address": "Main St 1",
            "city": "Lelystad",
            "country": "NL",
            "postal_code": "8232",
            "lat": 52.5,
            "lng": 5.5,
            "phone": "+31 6 12345678",
            "email": "hi@acme.test",
            "website_url": "https://acme.test/",
            "facebook_url": "https://facebook.com/acme",
            "instagram_url": "https://instagram.com/acme",
            "menu_url": "https://acme.test/menu",
        },
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["address"] == "Main St 1"
    assert body["email"] == "hi@acme.test"
    assert body["website_url"] == "https://acme.test/"


def test_patch_design_prompt_plain_text(mock_supabase, client, auth_as, admin_user):
    """design_prompt accepts arbitrary text and persists it."""
    auth_as(admin_user)
    updated = _lead_row(design_prompt="<p>Modern, minimal, dark.</p>")
    mock_supabase.execute.return_value = MagicMock(data=[updated])
    resp = client.patch(
        "/admin/leads/lead-1",
        json={"design_prompt": "<p>Modern, minimal, dark.</p>"},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["design_prompt"] == "<p>Modern, minimal, dark.</p>"


def test_patch_opening_hours_replaces_map(mock_supabase, client, auth_as, admin_user):
    """opening_hours is a full replacement of the day->string map."""
    auth_as(admin_user)
    hours = {"Monday": "9–17", "Tuesday": "Closed"}
    updated = _lead_row(opening_hours=hours)
    mock_supabase.execute.return_value = MagicMock(data=[updated])
    resp = client.patch("/admin/leads/lead-1", json={"opening_hours": hours})
    assert resp.status_code == 200, resp.text
    assert resp.json()["opening_hours"] == hours


def test_patch_invalid_email_returns_422(client, auth_as, admin_user):
    """Pydantic validation rejects malformed emails with 422 — no DB write."""
    auth_as(admin_user)
    resp = client.patch("/admin/leads/lead-1", json={"email": "not-an-email"})
    assert resp.status_code == 422


def test_patch_invalid_url_returns_422(client, auth_as, admin_user):
    """Pydantic HttpUrl rejects malformed URLs with 422."""
    auth_as(admin_user)
    resp = client.patch("/admin/leads/lead-1", json={"website_url": "not a url"})
    assert resp.status_code == 422


def test_patch_design_prompt_strips_script_tags(mock_supabase, client, auth_as, admin_user):
    """Server-side bleach must strip dangerous tags before persisting."""
    auth_as(admin_user)
    # Capture what gets sent to Supabase .update(...)
    captured = {}

    def capture_update(payload):
        captured["payload"] = payload
        chain = MagicMock()
        chain.eq.return_value.execute.return_value = MagicMock(
            data=[_lead_row(design_prompt=payload["design_prompt"])]
        )
        return chain

    mock_supabase.update.side_effect = capture_update

    resp = client.patch(
        "/admin/leads/lead-1",
        json={"design_prompt": "<p>hi</p><script>alert(1)</script>"},
    )
    assert resp.status_code == 200, resp.text
    # script tag stripped, <p>hi</p> preserved
    assert "<script>" not in captured["payload"]["design_prompt"]
    assert "<p>hi</p>" in captured["payload"]["design_prompt"]


def test_patch_design_prompt_preserves_allowed_formatting(
    mock_supabase, client, auth_as, admin_user
):
    """Bold, italic, headings, lists, links must survive sanitization."""
    auth_as(admin_user)
    captured = {}

    def capture_update(payload):
        captured["payload"] = payload
        chain = MagicMock()
        chain.eq.return_value.execute.return_value = MagicMock(
            data=[_lead_row(design_prompt=payload["design_prompt"])]
        )
        return chain

    mock_supabase.update.side_effect = capture_update

    html = (
        "<h2>Brief</h2>"
        "<p><strong>Bold</strong> <em>italic</em></p>"
        "<ul><li>Point</li></ul>"
        '<a href="https://example.com">link</a>'
    )
    resp = client.patch("/admin/leads/lead-1", json={"design_prompt": html})
    assert resp.status_code == 200, resp.text
    saved = captured["payload"]["design_prompt"]
    assert "<h2>Brief</h2>" in saved
    assert "<strong>Bold</strong>" in saved
    assert "<em>italic</em>" in saved
    assert "<ul>" in saved and "<li>Point</li>" in saved
    assert 'href="https://example.com"' in saved
    # Forced safety attrs on <a>
    assert 'rel="noopener nofollow"' in saved
    assert 'target="_blank"' in saved
