from unittest.mock import MagicMock

import pytest

from auth_service.core.config import settings
from auth_service.services.google_places import importer, mapper, resolve
from auth_service.services.google_places.client import GooglePlacesError

REAL_PLACE_ID = "ChIJN1t_tDeuEmsRUsoyG83frY4"
PLACE = {
    "id": "ChIJx",
    "displayName": {"text": "Acme Barber"},
    "websiteUri": "https://acme.nl/",
    "rating": 4.5,
    "userRatingCount": 10,
    "businessStatus": "OPERATIONAL",
    "photos": [{"name": "places/ChIJx/photos/a", "authorAttributions": []}],
}


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.setattr(settings, "GOOGLE_MAPS_API_KEY", "k")
    monkeypatch.setattr(settings, "GOOGLE_PLACES_MAX_PHOTOS", 10)
    monkeypatch.setattr(importer, "ensure_not_over", lambda: None)
    monkeypatch.setattr(importer, "consume", lambda: None)
    # "ChIJx" is shorter than a real place ID, so bypass the resolver by default;
    # tests that exercise resolution override this.
    monkeypatch.setattr(importer, "resolve", lambda raw, language="en": resolve.Resolution(raw))
    monkeypatch.setattr(importer, "delete_lead_photos", lambda sb, lead_id, urls=None: [])
    monkeypatch.setattr(importer.client, "place_details", lambda pid, language="en": PLACE)
    monkeypatch.setattr(
        importer,
        "enrich_from_website",
        lambda url: {
            "fetched": True,
            "final_url": url,
            "social_links": {"instagram": "https://instagram.com/acme"},
            "email": "hi@acme.nl",
            "description": "Acme desc",
            "lang": "nl",
            "error": None,
        },
    )
    monkeypatch.setattr(
        importer,
        "download_photos",
        lambda sb, lead_id, name, ph, max_photos, **k: (
            [f"https://x/lead-photos/{lead_id}/00-a.jpg"],
            [{"name": "places/ChIJx/photos/a", "url": "u", "owner_photo": False}],
            [],
        ),
    )


def _sb(execute_results):
    sb = MagicMock()
    for m in ["table", "select", "eq", "maybe_single", "insert", "update"]:
        getattr(sb, m).return_value = sb
    sb.execute.side_effect = execute_results
    return sb


def test_build_row_merges_enrichment():
    m = mapper.map_place(PLACE)
    row = importer.build_row(
        m,
        {
            "fetched": True,
            "social_links": {
                "instagram": "https://instagram.com/acme",
                "facebook": "https://facebook.com/acme",
            },
            "email": "hi@acme.nl",
            "description": "D",
            "lang": "nl",
            "error": None,
            "final_url": "https://acme.nl/",
        },
        place_id="ChIJx",
        language="en",
        now_iso="2026-10-11T00:00:00+00:00",
    )
    assert (
        row["google_place_id"] == "ChIJx"
        and row["google_imported_at"] == "2026-10-11T00:00:00+00:00"
    )
    assert row["external_id"] == "google:ChIJx" and row["primary_source"] == "google_maps"
    assert row["social_links"] == {
        "instagram": "https://instagram.com/acme",
        "facebook": "https://facebook.com/acme",
    }
    assert (
        row["facebook_url"] == "https://facebook.com/acme"
        and row["instagram_url"] == "https://instagram.com/acme"
    )
    assert row["email"] == "hi@acme.nl" and row["description"] == "D"
    assert row["extra"]["google"]["website"]["lang"] == "nl"
    assert row["extra"]["attributes"] == {}
    assert "photo_urls" not in row  # photos are added after insert


def test_build_row_without_enrichment():
    row = importer.build_row(
        mapper.map_place(PLACE), None, place_id="ChIJx", language="en", now_iso="t"
    )
    assert row["social_links"] == {} and row["email"] is None
    assert row["extra"]["google"]["website"] is None


def test_merge_fill_empty():
    current = {
        "phone": "+31",
        "email": None,
        "about": "",
        "types": [],
        "social_links": {},
        "rating": 4.0,
        "extra": {"attributes": {"A": {"x": True}}, "google": {"old": 1}, "other": 1},
        "notes": "keep",
    }
    incoming = {
        "phone": "+32",
        "email": "a@b.c",
        "about": "New",
        "types": ["t"],
        "social_links": {"x": "https://x.com/a"},
        "rating": 4.5,
        "extra": {"attributes": {"B": {"y": True}}, "google": {"new": 2}},
        "google_imported_at": "t",
    }
    out = importer.merge_fill_empty(current, incoming)
    assert "phone" not in out  # kept: non-empty on current, so not in the patch
    assert out["email"] == "a@b.c"  # filled
    assert (
        out["about"] == "New"
        and out["types"] == ["t"]
        and out["social_links"] == {"x": "https://x.com/a"}
    )
    assert out["rating"] == 4.5  # ALWAYS_REFRESH
    assert out["extra"] == {"attributes": {"A": {"x": True}}, "google": {"new": 2}, "other": 1}
    assert "notes" not in out


def test_import_place_creates_lead():
    sb = _sb(
        [
            None,  # duplicate pre-check
            MagicMock(
                data=[
                    {
                        "id": "lead-9",
                        "business_name": "Acme Barber",
                        "extra": {"attributes": {}, "google": {}},
                    }
                ]
            ),  # insert
            MagicMock(
                data=[{"id": "lead-9", "photo_urls": ["https://x/lead-photos/lead-9/00-a.jpg"]}]
            ),  # photo update
        ]
    )
    out = importer.import_place(sb, raw_input="ChIJx", lead_type="both", language="en")
    assert out.lead["id"] == "lead-9" and out.candidates == []
    inserted = sb.insert.call_args.args[0]
    assert inserted["lead_type"] == "both" and inserted["google_place_id"] == "ChIJx"
    assert inserted["web_presence"] == "has_website"
    updated = sb.update.call_args.args[0]
    assert updated["photo_urls"] == ["https://x/lead-photos/lead-9/00-a.jpg"]
    assert updated["extra"]["google"]["photos"][0]["name"] == "places/ChIJx/photos/a"


def test_import_returns_candidates(monkeypatch):
    monkeypatch.setattr(
        importer,
        "resolve",
        lambda raw, language="en": resolve.Resolution(
            None, [{"place_id": "a", "name": "A", "address": None}]
        ),
    )
    out = importer.import_place(
        _sb([]), raw_input="https://maps.app.goo.gl/x", lead_type="website", language="en"
    )
    assert out.lead is None and out.candidates[0]["place_id"] == "a"


def test_import_duplicate_409():
    sb = _sb([MagicMock(data={"id": "lead-1"})])
    with pytest.raises(importer.DuplicateLead) as ei:
        importer.import_place(sb, raw_input="ChIJx", lead_type="website", language="en")
    assert ei.value.lead_id == "lead-1"


def test_import_monthly_cap(monkeypatch):
    def capped():
        raise importer.MonthlyCapReached()

    monkeypatch.setattr(importer, "consume", capped)
    with pytest.raises(importer.MonthlyCapReached):
        importer.import_place(_sb([None]), raw_input="ChIJx", lead_type="website", language="en")


def test_import_quota_unavailable_blocks_details(monkeypatch):
    def down():
        raise importer.QuotaUnavailable()

    monkeypatch.setattr(importer, "consume", down)
    monkeypatch.setattr(
        importer.client, "place_details", lambda *a, **k: pytest.fail("must not call Google")
    )
    with pytest.raises(importer.QuotaUnavailable):
        # a real-shaped place ID skips the free-text slot, so this is the Details slot
        importer.import_place(
            _sb([None]), raw_input=REAL_PLACE_ID, lead_type="website", language="en"
        )


def test_import_free_text_consumes_before_resolve(monkeypatch):
    calls = []
    monkeypatch.setattr(importer, "consume", lambda: calls.append("consume"))
    monkeypatch.setattr(
        importer,
        "resolve",
        lambda raw, language="en": calls.append("resolve")
        or resolve.Resolution(None, [{"place_id": "a", "name": "A", "address": None}]),
    )
    importer.import_place(
        _sb([]), raw_input="Kapsalon, Utrecht", lead_type="website", language="en"
    )
    assert calls == ["consume", "resolve"]


def test_reimport_free_text_consumes_before_resolve(monkeypatch):
    calls = []
    monkeypatch.setattr(importer, "consume", lambda: calls.append("consume"))
    monkeypatch.setattr(
        importer,
        "resolve",
        lambda raw, language="en": calls.append("resolve")
        or resolve.Resolution(None, [{"place_id": "a", "name": "A", "address": None}]),
    )
    importer.reimport_place(
        _sb([]),
        {"id": "l", "google_place_id": "ChIJx"},
        raw_input="Kapsalon, Utrecht",
        overwrite=False,
        language="en",
    )
    assert calls == ["consume", "resolve"]


def test_import_skips_enrichment_without_website(monkeypatch):
    monkeypatch.setattr(
        importer.client,
        "place_details",
        lambda pid, language="en": {"id": "ChIJx", "displayName": {"text": "Mobile"}},
    )
    monkeypatch.setattr(importer, "enrich_from_website", lambda url: pytest.fail("must not fetch"))
    sb = _sb(
        [
            None,
            MagicMock(data=[{"id": "l", "extra": {}}]),
            MagicMock(data=[{"id": "l"}]),
        ]
    )
    out = importer.import_place(sb, raw_input="ChIJx", lead_type="website", language="en")
    assert sb.insert.call_args.args[0]["web_presence"] == "none" and out.lead["id"] == "l"


def test_import_survives_enrichment_failure(monkeypatch):
    monkeypatch.setattr(
        importer,
        "enrich_from_website",
        lambda url: {
            "fetched": False,
            "final_url": None,
            "social_links": {},
            "email": None,
            "description": None,
            "lang": None,
            "error": "OSError: refused",
        },
    )
    sb = _sb(
        [
            None,
            MagicMock(data=[{"id": "l", "extra": {}}]),
            MagicMock(data=[{"id": "l"}]),
        ]
    )
    out = importer.import_place(sb, raw_input="ChIJx", lead_type="website", language="en")
    assert out.lead is not None and any("refused" in w for w in out.warnings)


def test_import_google_error_propagates(monkeypatch):
    def boom(pid, language="en"):
        raise GooglePlacesError(404, "not found")

    monkeypatch.setattr(importer.client, "place_details", boom)
    with pytest.raises(GooglePlacesError):
        importer.import_place(
            _sb([MagicMock(data=None)]), raw_input="ChIJx", lead_type="website", language="en"
        )


def test_reimport_fill_empty_keeps_existing(monkeypatch):
    current = {
        "id": "lead-1",
        "google_place_id": "ChIJx",
        "business_name": "Old Name",
        "phone": "+31",
        "email": None,
        "photo_urls": ["old"],
        "extra": {"attributes": {"A": {"x": True}}, "google": {}},
        "notes": "n",
        "social_links": {},
    }
    sb = _sb([MagicMock(data=[{"id": "lead-1", "business_name": "Old Name"}])])
    out = importer.reimport_place(sb, current, raw_input=None, overwrite=False, language="en")
    patch = sb.update.call_args.args[0]
    assert "business_name" not in patch  # kept: non-empty on the current row
    assert patch["email"] == "hi@acme.nl" and patch["rating"] == 4.5
    assert "notes" not in patch and "lead_type" not in patch
    assert patch["photo_urls"] == ["old"]  # existing photos kept in fill-empty mode
    assert out.lead["id"] == "lead-1"


def test_reimport_overwrite_replaces_and_redownloads(monkeypatch):
    deleted = []
    sb = _sb([MagicMock(data=[{"id": "lead-1"}])])

    def fake_delete(sb_, lead_id, urls=None):
        deleted.append((lead_id, urls, sb.update.called))  # update must already have run
        return []

    monkeypatch.setattr(importer, "delete_lead_photos", fake_delete)
    current = {
        "id": "lead-1",
        "google_place_id": "ChIJx",
        "business_name": "Old Name",
        "phone": "+31",
        "photo_urls": ["old"],
        "extra": {"attributes": {}, "google": {}},
        "social_links": {},
    }
    importer.reimport_place(sb, current, raw_input=None, overwrite=True, language="en")
    patch = sb.update.call_args.args[0]
    assert patch["business_name"] == "Acme Barber"
    assert deleted == [("lead-1", ["old"], True)]
    assert patch["photo_urls"] == ["https://x/lead-photos/lead-1/00-a.jpg"]


def test_reimport_overwrite_cleanup_failure_is_a_warning(monkeypatch):
    def boom(sb_, lead_id, urls=None):
        raise OSError("storage down")

    monkeypatch.setattr(importer, "delete_lead_photos", boom)
    current = {
        "id": "lead-1",
        "google_place_id": "ChIJx",
        "photo_urls": ["old"],
        "extra": {},
        "social_links": {},
    }
    out = importer.reimport_place(
        _sb([MagicMock(data=[{"id": "lead-1"}])]),
        current,
        raw_input=None,
        overwrite=True,
        language="en",
    )
    assert out.lead["id"] == "lead-1" and "old photo cleanup failed: OSError" in out.warnings


def test_import_photo_writeback_failure_keeps_lead(monkeypatch):
    def boom(*a, **k):
        raise OSError("storage down")

    monkeypatch.setattr(importer, "download_photos", boom)
    sb = _sb([None, MagicMock(data=[{"id": "lead-9", "extra": {}}])])
    out = importer.import_place(sb, raw_input="ChIJx", lead_type="website", language="en")
    assert out.lead["id"] == "lead-9" and "photos not saved: OSError" in out.warnings


def test_reimport_requires_input_or_place_id():
    with pytest.raises(importer.MissingPlaceId):
        importer.reimport_place(
            _sb([]),
            {"id": "l", "google_place_id": None},
            raw_input=None,
            overwrite=False,
            language="en",
        )


def test_reimport_with_new_input_changes_place(monkeypatch):
    seen = {}
    monkeypatch.setattr(
        importer,
        "resolve",
        lambda raw, language="en": seen.update(raw=raw) or resolve.Resolution("ChIJnew"),
    )
    sb = _sb([None, MagicMock(data=[{"id": "l"}])])
    importer.reimport_place(
        sb,
        {
            "id": "l",
            "google_place_id": "ChIJold",
            "extra": {},
            "photo_urls": [],
            "social_links": {},
        },
        raw_input="https://maps.app.goo.gl/n",
        overwrite=True,
        language="en",
    )
    assert (
        seen["raw"].endswith("/n") and sb.update.call_args.args[0]["google_place_id"] == "ChIJnew"
    )


FAILED_ENRICHMENT = {
    "fetched": False,
    "final_url": None,
    "social_links": {},
    "email": None,
    "description": None,
    "lang": None,
    "error": "OSError: refused",
}


def test_reimport_fill_empty_downloads_photos_when_none(monkeypatch):
    current = {
        "id": "lead-1",
        "google_place_id": "ChIJx",
        "photo_urls": [],
        "extra": {"google": {}},
        "social_links": {},
    }
    sb = _sb([MagicMock(data=[{"id": "lead-1"}])])
    importer.reimport_place(sb, current, raw_input=None, overwrite=False, language="en")
    patch = sb.update.call_args.args[0]
    assert patch["photo_urls"] == ["https://x/lead-photos/lead-1/00-a.jpg"]
    assert patch["extra"]["google"]["photos"][0]["name"] == "places/ChIJx/photos/a"
    assert "_photos" not in patch and "_enriched" not in patch


def test_reimport_fill_empty_keeps_existing_photos_without_download(monkeypatch):
    monkeypatch.setattr(
        importer, "download_photos", lambda *a, **k: pytest.fail("must not download")
    )
    current = {
        "id": "lead-1",
        "google_place_id": "ChIJx",
        "photo_urls": ["old"],
        "extra": {"google": {"photos": [{"url": "old"}]}},
        "social_links": {},
    }
    sb = _sb([MagicMock(data=[{"id": "lead-1"}])])
    importer.reimport_place(sb, current, raw_input=None, overwrite=False, language="en")
    patch = sb.update.call_args.args[0]
    assert patch["photo_urls"] == ["old"]
    assert patch["extra"]["google"]["photos"] == [{"url": "old"}]


def test_reimport_overwrite_failed_fetch_keeps_website_data(monkeypatch):
    monkeypatch.setattr(importer, "enrich_from_website", lambda url: dict(FAILED_ENRICHMENT))
    current = {
        "id": "lead-1",
        "google_place_id": "ChIJx",
        "email": "keep@acme.nl",
        "description": "keep",
        "social_links": {"instagram": "https://instagram.com/keep"},
        "instagram_url": "https://instagram.com/keep",
        "photo_urls": [],
        "extra": {},
    }
    sb = _sb([MagicMock(data=[{"id": "lead-1"}])])
    importer.reimport_place(sb, current, raw_input=None, overwrite=True, language="en")
    patch = sb.update.call_args.args[0]
    for key in ("email", "social_links", "facebook_url", "instagram_url", "description"):
        assert key not in patch
    assert patch["business_name"] == "Acme Barber" and "_enriched" not in patch


def test_reimport_overwrite_social_website_merges_link(monkeypatch):
    monkeypatch.setattr(
        importer.client,
        "place_details",
        lambda pid, language="en": {
            **PLACE,
            "websiteUri": "https://www.facebook.com/acmebarber/",
        },
    )
    monkeypatch.setattr(importer, "enrich_from_website", lambda url: pytest.fail("no fetch"))
    current = {
        "id": "lead-1",
        "google_place_id": "ChIJx",
        "email": "keep@acme.nl",
        "social_links": {"instagram": "https://instagram.com/keep"},
        "photo_urls": [],
        "extra": {},
    }
    sb = _sb([MagicMock(data=[{"id": "lead-1"}])])
    importer.reimport_place(sb, current, raw_input=None, overwrite=True, language="en")
    patch = sb.update.call_args.args[0]
    assert patch["social_links"] == {
        "instagram": "https://instagram.com/keep",
        "facebook": "https://www.facebook.com/acmebarber",
    }
    assert patch["facebook_url"] == "https://www.facebook.com/acmebarber"
    assert patch["instagram_url"] == "https://instagram.com/keep"
    assert "email" not in patch and "description" not in patch
    assert patch["web_presence"] == "social_only"


def test_merge_fill_empty_treats_unknown_web_presence_as_empty():
    out = importer.merge_fill_empty(
        {"web_presence": "unknown", "extra": {}}, {"web_presence": "has_website", "extra": {}}
    )
    assert out["web_presence"] == "has_website"


def test_reimport_unique_violation_is_duplicate(monkeypatch):
    current = {
        "id": "lead-1",
        "google_place_id": "ChIJx",
        "photo_urls": ["old"],
        "extra": {},
        "social_links": {},
    }
    sb = _sb(
        [
            Exception('duplicate key value violates unique constraint (code "23505")'),
            MagicMock(data={"id": "lead-7"}),  # _find_duplicate
        ]
    )
    with pytest.raises(importer.DuplicateLead) as ei:
        importer.reimport_place(sb, current, raw_input=None, overwrite=False, language="en")
    assert ei.value.lead_id == "lead-7"


def test_import_unique_violation_falls_back_to_external_id():
    sb = _sb(
        [
            None,  # duplicate pre-check
            Exception('{"code": "23505", "message": "duplicate key"}'),  # insert
            None,  # _find_duplicate by google_place_id
            MagicMock(data={"id": "lead-5"}),  # by external_id
        ]
    )
    with pytest.raises(importer.DuplicateLead) as ei:
        importer.import_place(sb, raw_input="ChIJx", lead_type="website", language="en")
    assert ei.value.lead_id == "lead-5"
    sb.eq.assert_any_call("external_id", "google:ChIJx")


def test_import_persists_warnings(monkeypatch):
    monkeypatch.setattr(importer, "enrich_from_website", lambda url: dict(FAILED_ENRICHMENT))
    sb = _sb(
        [
            None,
            MagicMock(data=[{"id": "l", "extra": {}}]),
            MagicMock(data=[{"id": "l"}]),
        ]
    )
    importer.import_place(sb, raw_input="ChIJx", lead_type="website", language="en")
    assert "_enriched" not in sb.insert.call_args.args[0]
    updated = sb.update.call_args.args[0]
    assert updated["extra"]["google"]["import_warnings"] == [
        "website enrichment skipped: OSError: refused"
    ]


def test_reimport_persists_warnings(monkeypatch):
    monkeypatch.setattr(importer, "enrich_from_website", lambda url: dict(FAILED_ENRICHMENT))
    current = {
        "id": "lead-1",
        "google_place_id": "ChIJx",
        "photo_urls": ["old"],
        "extra": {},
        "social_links": {},
    }
    sb = _sb([MagicMock(data=[{"id": "lead-1"}])])
    out = importer.reimport_place(sb, current, raw_input=None, overwrite=False, language="en")
    patch = sb.update.call_args.args[0]
    assert patch["extra"]["google"]["import_warnings"] == out.warnings
    assert out.warnings == ["website enrichment skipped: OSError: refused"]
