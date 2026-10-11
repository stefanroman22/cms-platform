import pytest
from pydantic import ValidationError

from auth_service.models.schemas import GoogleImportIn, LeadOut, LeadUpdate


def _row(**over):
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
        "created_at": "2026-05-17T10:00:00Z",
        "updated_at": "2026-05-17T10:00:00Z",
    }
    base.update(over)
    return base


def test_lead_out_defaults_new_columns():
    out = LeadOut(**_row())
    assert out.google_place_id is None
    assert out.types == []
    assert out.social_links == {}
    assert out.price_level is None


def test_lead_out_accepts_new_columns():
    out = LeadOut(
        **_row(
            google_place_id="ChIJabc",
            types=["barber_shop"],
            social_links={"tiktok": "https://www.tiktok.com/@acme"},
            price_level="moderate",
            business_status="OPERATIONAL",
        )
    )
    assert out.types == ["barber_shop"]
    assert out.social_links["tiktok"].endswith("@acme")


def test_lead_out_none_types_becomes_empty_list():
    assert LeadOut(**_row(types=None)).types == []


def test_lead_update_social_links_rejects_unknown_platform():
    with pytest.raises(ValidationError):
        LeadUpdate(social_links={"myspace": "https://myspace.com/acme"})


def test_lead_update_social_links_rejects_non_http():
    with pytest.raises(ValidationError):
        LeadUpdate(social_links={"facebook": "javascript:alert(1)"})


def test_lead_update_social_links_drops_blank_values():
    upd = LeadUpdate(social_links={"facebook": "https://facebook.com/acme", "x": "  "})
    assert upd.social_links == {"facebook": "https://facebook.com/acme"}


def test_lead_update_photo_urls_list():
    upd = LeadUpdate(
        photo_urls=["https://x.supabase.co/storage/v1/object/public/lead-photos/l/00-a.jpg"]
    )
    assert len(upd.photo_urls) == 1


def test_google_import_in_defaults():
    body = GoogleImportIn(input="https://maps.app.goo.gl/abc")
    assert body.lead_type == "website"
    assert body.language == "en"


def test_google_import_in_rejects_bad_language():
    with pytest.raises(ValidationError):
        GoogleImportIn(input="x", language="english")
