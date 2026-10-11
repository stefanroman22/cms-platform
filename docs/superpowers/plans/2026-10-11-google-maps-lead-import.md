# Google Maps Lead Import Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** One paste of a Google Maps link in the leads dashboard creates (or refreshes) a lead with everything the listing and the business's own website expose: identity, address, contact, hours, reviews, summaries, attributes, price level, photos with attribution, and social links.

**Architecture:** A new backend package `services/google_places/` (client, resolver, mapper, website enricher, photo downloader, importer) calls Places API (New), Maps Tools Resolution API and Place Photos with `urllib` and maps the result onto the existing `leads` columns plus seven new ones and `extra.google`. Two admin endpoints on the existing leads router expose it; the dashboard gets an import block in the Add-Lead drawer and a re-import action, photos section and business section in the detail drawer.

**Tech Stack:** FastAPI + pytest (backend, stdlib `urllib`/`html.parser`, no new deps), Supabase Postgres + Storage, Next.js 16 + Vitest + Testing Library (dashboard), Markdown skill docs.

**Spec:** `docs/decisions/0012-google-maps-lead-import.md` (read it first; it is the contract).

## Global Constraints

- Repo: `C:\Users\stefa\.gemini\antigravity\scratch\CMS - websites`. The main checkout is occupied by another session's uncommitted work (branch `feat/theme-media-typography`), so work in a dedicated worktree: `git worktree add "../CMS - websites-leads" -b feat/google-maps-lead-import dev` and run every command from `C:\Users\stefa\.gemini\antigravity\scratch\CMS - websites-leads` (create its `backend/venv` with `python -m venv backend/venv && backend/venv/Scripts/pip install -r backend/requirements.txt -r backend/requirements-dev.txt`, copy `backend/.env` and `frontend/.env.local` from the main checkout, `cd frontend && npm ci`). Line numbers in this plan refer to `dev` at `e790582`. Commit each task with a short one-line message and NO Co-Authored-By or AI attribution. Never push, never touch `dev` or `main`; the controller merges.
- **Do NOT apply the migration, create the bucket, or write to Supabase from code you run.** One DB serves prod. Backend tests use the `mock_supabase` fixture; nothing may open a real network connection in tests (patch `_urlopen`/`_open`).
- **No new Python dependency.** HTTP = `urllib.request` (10 s timeout, `User-Agent: roman-technologies-cms-backend/1.0`), HTML = `html.parser`. `requirements.txt`/`requirements.lock` stay untouched.
- Settings: `GOOGLE_MAPS_API_KEY: str = ""`, `GOOGLE_PLACES_MONTHLY_CAP: int = 90`, `GOOGLE_PLACES_MAX_PHOTOS: int = 10`. Empty key ⇒ endpoints return `503 {"detail": "Google Maps import is not configured on this backend"}`.
- Rate limits: per admin bucket `google_import:user:<user.id>` 20 per 3600 s (`pg_rate_limit.enforce`); monthly bucket `google_import:month` capped at `GOOGLE_PLACES_MONTHLY_CAP` per 31×86400 s, checked with `over_limit` before resolving and hit with `allow` right before `place_details`.
- Place Details field mask (exact string, no spaces) is `PLACE_FIELD_MASK` in Task 2; every import requests it in one call.
- Photo storage: bucket `lead-photos`, path `<lead_id>/<nn>-<sha1[:10]>.<ext>`, `maxWidthPx=1600`, max 8 MB per image, content types `image/jpeg|png|webp` (else skipped).
- Website fetch: http/https only, DNS-resolved host must be public (`ipaddress` checks), redirects re-validated, 8 s timeout, 1 MB cap, must be `text/html`.
- Enums reused verbatim: `web_presence` ∈ `none|social_only|has_website|unknown`; `price_level` stored lowercase without the `PRICE_LEVEL_` prefix (`free|inexpensive|moderate|expensive|very_expensive`); `business_status` stored as Google sends it (`OPERATIONAL`, `CLOSED_TEMPORARILY`, `CLOSED_PERMANENTLY`, `FUTURE_OPENING`).
- Social platforms (keys of `social_links`): `facebook instagram tiktok linkedin youtube x pinterest whatsapp`.
- Import never writes: `lead_type` (except on create), `website_build_status`, `ai_workflow_status`, `lead_status`, `lead_contact_type`, `payment_status`, `notes`, `design_prompt`, `languages`, `menu_url`, `closed_amount`, `closed_at`, `call_count`.
- Python: ruff + black clean (`backend/venv/Scripts/python -m ruff check . && backend/venv/Scripts/python -m black --check .` from `backend/`). Frontend: `npm run lint`, `npm run typecheck`, `npm run format:check` in `frontend/`. Run only your task's tests; the controller runs `make ci`.
- Dashboard buttons get `cursor-pointer`; animation imports come from `motion/react`; match the surrounding Tailwind/zinc style.

## Review Focus

1. **A service-area listing** (no `websiteUri`, no phone, no hours, `pureServiceAreaBusiness=true`) must import with those fields `None`, `web_presence='none'`, no enrichment attempted — Task 4 `test_map_place_minimal_listing`, Task 7 `test_import_skips_enrichment_without_website`.
2. **A Maps URL the Resolution API cannot resolve** (search URL, dead short link) must end in candidates or a clear 404/422, never a 500 — Task 3 `test_resolve_unresolvable_url_falls_back_to_text_search`, Task 7 `test_import_returns_candidates`.
3. **A hostile or useless business website** (redirect to 127.0.0.1, 5 MB page, PDF content type, DNS failure) must leave a warning and still create the lead — Task 5 `test_redirect_to_private_ip_rejected`, `test_non_html_rejected`, Task 7 `test_import_survives_enrichment_failure`.
4. **The same listing imported twice** must give 409 with the existing `lead_id`, and re-import on that lead must work — Task 7 `test_import_duplicate_409`, `test_reimport_fill_empty_keeps_existing`.
5. **One photo failing mid-batch** must not lose the others or duplicate URLs — Task 6 `test_download_photos_continues_after_failure`.

---

### Task 1: Migration, settings, schemas

**Files:**
- Create: `backend/migrations/2026_10_11_lead_google_import.sql`
- Modify: `backend/auth_service/core/config.py:31-38` (new settings block)
- Modify: `backend/.env.example:26-37` (optional-features block)
- Modify: `backend/auth_service/models/schemas.py:455-499` (`LeadOut`), `:501-565` (`LeadUpdate`), add `GoogleImportIn`/`GoogleReimportIn` after `LeadCreate`
- Test: `backend/auth_service/tests/test_lead_google_schemas.py`

**Interfaces:**
- Produces: `settings.GOOGLE_MAPS_API_KEY: str`, `settings.GOOGLE_PLACES_MONTHLY_CAP: int`, `settings.GOOGLE_PLACES_MAX_PHOTOS: int`; `LeadOut` gains `google_place_id: str | None`, `google_imported_at: str | None`, `business_status: str | None`, `primary_type: str | None`, `types: list[str]` (default `[]`), `price_level: str | None`, `social_links: dict[str, str]` (default `{}`); `LeadUpdate` gains `social_links: dict[str, str] | None` and `photo_urls: list[str] | None`; `SOCIAL_PLATFORMS: frozenset[str]` exported from `schemas.py`; `GoogleImportIn(input: str, lead_type: LeadType = "website", language: str = "en")`, `GoogleReimportIn(input: str | None = None, overwrite: bool = False, language: str = "en")`.

- [ ] **Step 1: Write the migration**

```sql
-- 2026_10_11_lead_google_import.sql — ADR-0012: import a lead from a Google Maps listing.
-- Additive only. Apply by hand (scripts/apply_supabase_migration.py or Supabase MCP)
-- before or with the code that selects these columns.

alter table public.leads
    add column if not exists google_place_id    text,
    add column if not exists google_imported_at timestamptz,
    add column if not exists business_status    text,
    add column if not exists primary_type       text,
    add column if not exists types              text[],
    add column if not exists price_level        text,
    add column if not exists social_links       jsonb not null default '{}'::jsonb;

-- One lead per Google place; NULL for manual leads, so a partial index.
create unique index if not exists leads_google_place_id_uidx
    on public.leads (google_place_id)
    where google_place_id is not null;

comment on column public.leads.google_place_id is
    'Places API place ID. The only Google value we may store indefinitely; used to re-import.';
comment on column public.leads.social_links is
    'Full social map {facebook,instagram,tiktok,linkedin,youtube,x,pinterest,whatsapp}: url. facebook_url/instagram_url mirror two of its keys.';
comment on column public.leads.price_level is
    'Google priceLevel without the PRICE_LEVEL_ prefix, lowercase (free|inexpensive|moderate|expensive|very_expensive).';

-- Public bucket for imported listing photos. Served by public URL; writes go through the
-- service-role backend only (no storage policies needed).
insert into storage.buckets (id, name, public)
values ('lead-photos', 'lead-photos', true)
on conflict (id) do nothing;
```

- [ ] **Step 2: Add settings** to `Settings` after the booking block in `config.py`:

```python
    # Google Maps lead import (ADR-0012). Empty key disables the feature.
    GOOGLE_MAPS_API_KEY: str = ""
    # Imports per calendar month across all admins. 90 keeps Place Details and
    # Place Photos (10 per import) inside Google's free tier.
    GOOGLE_PLACES_MONTHLY_CAP: int = 90
    GOOGLE_PLACES_MAX_PHOTOS: int = 10
```

and in `.env.example` under "Optional features":

```
# Lead import from a Google Maps listing (ADR-0012). Key from a billing-enabled Cloud
# project, restricted to "Places API (New)" + "Maps Tools Resolution API", no referrer.
# GOOGLE_MAPS_API_KEY=
# GOOGLE_PLACES_MONTHLY_CAP=90
# GOOGLE_PLACES_MAX_PHOTOS=10
```

- [ ] **Step 3: Write the failing schema tests** in `test_lead_google_schemas.py`:

```python
import pytest
from pydantic import ValidationError

from auth_service.models.schemas import GoogleImportIn, LeadOut, LeadUpdate


def _row(**over):
    base = {
        "id": "lead-1", "external_id": "ext-1", "primary_source": "google_maps",
        "lead_type": "website", "business_name": "Acme", "name_normalized": "acme",
        "web_presence": "none", "website_build_status": "not_started",
        "ai_workflow_status": "not_started", "lead_status": "not_sent",
        "lead_contact_type": "not_contacted", "payment_status": "not_applicable",
        "extra": {}, "photo_urls": [], "created_at": "2026-05-17T10:00:00Z",
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
    out = LeadOut(**_row(google_place_id="ChIJabc", types=["barber_shop"],
                         social_links={"tiktok": "https://www.tiktok.com/@acme"},
                         price_level="moderate", business_status="OPERATIONAL"))
    assert out.types == ["barber_shop"]
    assert out.social_links["tiktok"].endswith("@acme")


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
    upd = LeadUpdate(photo_urls=["https://x.supabase.co/storage/v1/object/public/lead-photos/l/00-a.jpg"])
    assert len(upd.photo_urls) == 1


def test_google_import_in_defaults():
    body = GoogleImportIn(input="https://maps.app.goo.gl/abc")
    assert body.lead_type == "website"
    assert body.language == "en"


def test_google_import_in_rejects_bad_language():
    with pytest.raises(ValidationError):
        GoogleImportIn(input="x", language="english")
```

- [ ] **Step 4: Run to verify failure**

Run: `cd backend && venv/Scripts/python -m pytest auth_service/tests/test_lead_google_schemas.py -q`
Expected: FAIL (`ImportError: cannot import name 'GoogleImportIn'` / unknown fields).

- [ ] **Step 5: Implement the schema changes**

In `LeadOut`, after `languages`:

```python
    # Google Maps import (ADR-0012)
    google_place_id: str | None = None
    google_imported_at: str | None = None
    business_status: str | None = None
    primary_type: str | None = None
    types: list[str] = Field(default_factory=list)
    price_level: str | None = None
    social_links: dict[str, str] = Field(default_factory=dict)
```

Above `LeadUpdate` add the platform set and a validator helper:

```python
SOCIAL_PLATFORMS = frozenset(
    {"facebook", "instagram", "tiktok", "linkedin", "youtube", "x", "pinterest", "whatsapp"}
)


def _clean_social_links(v: dict[str, str] | None) -> dict[str, str] | None:
    """Keep known platforms with a non-blank http(s) URL; drop blank values so the
    dashboard can 'clear' a platform by sending an empty string."""
    if v is None:
        return None
    out: dict[str, str] = {}
    for key, raw in v.items():
        if key not in SOCIAL_PLATFORMS:
            raise ValueError(f"unknown social platform '{key}'")
        if not isinstance(raw, str):
            raise ValueError("social link must be a string")
        url = raw.strip()
        if not url:
            continue
        if not url.lower().startswith(("http://", "https://")):
            raise ValueError(f"{key} link must start with http:// or https://")
        if len(url) > 500:
            raise ValueError(f"{key} link too long (max 500 chars)")
        out[key] = url
    return out
```

In `LeadUpdate`, after `about_attributes`:

```python
    # social links — full replacement of the platform -> url map (ADR-0012);
    # the router mirrors facebook/instagram into their legacy columns.
    social_links: dict[str, str] | None = None
    # photos — full replacement; the router deletes dropped lead-photos objects.
    photo_urls: list[str] | None = None

    @field_validator("social_links", mode="after")
    @classmethod
    def _validate_social_links(cls, v: dict[str, str] | None) -> dict[str, str] | None:
        return _clean_social_links(v)
```

After `LeadCreate`:

```python
class GoogleImportIn(BaseModel):
    """POST /admin/leads/google-import — a Maps URL, short link, place ID or free text."""

    input: str = Field(min_length=1, max_length=2000)
    lead_type: LeadType = "website"
    language: str = Field("en", pattern=r"^[a-z]{2}(-[A-Z]{2})?$")


class GoogleReimportIn(BaseModel):
    """POST /admin/leads/{id}/google-import — defaults to the stored google_place_id."""

    input: str | None = Field(None, min_length=1, max_length=2000)
    overwrite: bool = False
    language: str = Field("en", pattern=r"^[a-z]{2}(-[A-Z]{2})?$")
```

- [ ] **Step 6: Run the new tests and the existing leads tests**

Run: `cd backend && venv/Scripts/python -m pytest auth_service/tests/test_lead_google_schemas.py auth_service/tests/test_admin_leads_router.py -q`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add backend/migrations/2026_10_11_lead_google_import.sql backend/auth_service/core/config.py backend/.env.example backend/auth_service/models/schemas.py backend/auth_service/tests/test_lead_google_schemas.py
git commit -m "feat(leads): schema, settings and migration for Google Maps import"
```

---

### Task 2: Google HTTP client

**Files:**
- Create: `backend/auth_service/services/google_places/__init__.py` (empty)
- Create: `backend/auth_service/services/google_places/client.py`
- Test: `backend/auth_service/tests/test_google_places_client.py`

**Interfaces:**
- Produces: `GooglePlacesError(Exception)` with `.status: int` and `.message: str`; `PLACE_FIELD_MASK: str`; `place_details(place_id: str, *, language: str = "en") -> dict`; `resolve_maps_url(url: str) -> str | None`; `text_search(query: str, *, lat: float | None = None, lng: float | None = None, language: str = "en", page_size: int = 5) -> list[dict]` (each `{"place_id", "name", "address"}`); `photo_uri(photo_name: str, *, max_width_px: int = 1600) -> str`; `fetch_bytes(url: str, *, max_bytes: int = 8_000_000, timeout: int = 15) -> tuple[bytes, str]` (body, content-type); module-level `_urlopen(req, timeout)` that tests monkeypatch.

- [ ] **Step 1: Write the failing tests**

```python
import io
import json
import urllib.error

import pytest

from auth_service.core.config import settings
from auth_service.services.google_places import client


class _Resp(io.BytesIO):
    def __init__(self, body: bytes, headers: dict | None = None):
        super().__init__(body)
        self.headers = headers or {}

    def __enter__(self):
        return self

    def __exit__(self, *a):
        self.close()


@pytest.fixture(autouse=True)
def _key(monkeypatch):
    monkeypatch.setattr(settings, "GOOGLE_MAPS_API_KEY", "test-key")


def test_place_details_sends_key_and_field_mask(monkeypatch):
    seen = {}

    def fake(req, timeout):
        seen["url"] = req.full_url
        seen["headers"] = {k.lower(): v for k, v in req.header_items()}
        return _Resp(json.dumps({"id": "ChIJx", "displayName": {"text": "Acme"}}).encode())

    monkeypatch.setattr(client, "_urlopen", fake)
    place = client.place_details("ChIJx", language="nl")
    assert place["displayName"]["text"] == "Acme"
    assert seen["url"] == "https://places.googleapis.com/v1/places/ChIJx?languageCode=nl"
    assert seen["headers"]["x-goog-api-key"] == "test-key"
    assert seen["headers"]["x-goog-fieldmask"] == client.PLACE_FIELD_MASK
    assert "photos" in client.PLACE_FIELD_MASK and "editorialSummary" in client.PLACE_FIELD_MASK


def test_missing_key_raises_503(monkeypatch):
    monkeypatch.setattr(settings, "GOOGLE_MAPS_API_KEY", "")
    with pytest.raises(client.GooglePlacesError) as ei:
        client.place_details("ChIJx")
    assert ei.value.status == 503


def test_http_error_maps_to_google_error(monkeypatch):
    body = json.dumps({"error": {"message": "API key not valid", "status": "PERMISSION_DENIED"}})

    def fake(req, timeout):
        raise urllib.error.HTTPError(req.full_url, 403, "Forbidden", {}, io.BytesIO(body.encode()))

    monkeypatch.setattr(client, "_urlopen", fake)
    with pytest.raises(client.GooglePlacesError) as ei:
        client.place_details("ChIJx")
    assert ei.value.status == 403
    assert "API key not valid" in ei.value.message


def test_url_error_maps_to_504(monkeypatch):
    def fake(req, timeout):
        raise urllib.error.URLError("timed out")

    monkeypatch.setattr(client, "_urlopen", fake)
    with pytest.raises(client.GooglePlacesError) as ei:
        client.place_details("ChIJx")
    assert ei.value.status == 504


def test_resolve_maps_url_returns_place_id(monkeypatch):
    def fake(req, timeout):
        assert req.full_url == "https://mapstools.googleapis.com/v1:resolveMapsUrls"
        assert json.loads(req.data)["urls"] == ["https://maps.app.goo.gl/abc"]
        return _Resp(json.dumps({"entities": [{"placeId": "places/ChIJabc"}]}).encode())

    monkeypatch.setattr(client, "_urlopen", fake)
    assert client.resolve_maps_url("https://maps.app.goo.gl/abc") == "ChIJabc"


def test_resolve_maps_url_unresolved_returns_none(monkeypatch):
    def fake(req, timeout):
        return _Resp(json.dumps({"entities": [{}], "failedRequests": {"0": {"code": 3}}}).encode())

    monkeypatch.setattr(client, "_urlopen", fake)
    assert client.resolve_maps_url("https://maps.app.goo.gl/dead") is None


def test_text_search_maps_candidates(monkeypatch):
    def fake(req, timeout):
        body = json.loads(req.data)
        assert body["textQuery"] == "Samir Kapsalon Lelystad"
        assert body["pageSize"] == 5
        assert body["locationBias"]["circle"]["center"] == {"latitude": 52.5, "longitude": 5.47}
        return _Resp(json.dumps({"places": [
            {"id": "ChIJ1", "displayName": {"text": "Samir Kapsalon"}, "formattedAddress": "Stadhuisplein 1"},
            {"id": "ChIJ2", "displayName": {"text": "Samir Barber"}},
        ]}).encode())

    monkeypatch.setattr(client, "_urlopen", fake)
    out = client.text_search("Samir Kapsalon Lelystad", lat=52.5, lng=5.47)
    assert out == [
        {"place_id": "ChIJ1", "name": "Samir Kapsalon", "address": "Stadhuisplein 1"},
        {"place_id": "ChIJ2", "name": "Samir Barber", "address": None},
    ]


def test_photo_uri(monkeypatch):
    def fake(req, timeout):
        assert req.full_url == (
            "https://places.googleapis.com/v1/places/ChIJx/photos/abc/media"
            "?maxWidthPx=1600&skipHttpRedirect=true"
        )
        return _Resp(json.dumps({"name": "places/ChIJx/photos/abc", "photoUri": "https://lh3.googleusercontent.com/p/x"}).encode())

    monkeypatch.setattr(client, "_urlopen", fake)
    assert client.photo_uri("places/ChIJx/photos/abc") == "https://lh3.googleusercontent.com/p/x"


def test_fetch_bytes_caps_size_and_returns_type(monkeypatch):
    def fake(req, timeout):
        return _Resp(b"x" * 10, headers={"Content-Type": "image/jpeg"})

    monkeypatch.setattr(client, "_urlopen", fake)
    with pytest.raises(client.GooglePlacesError):
        client.fetch_bytes("https://lh3.googleusercontent.com/p/x", max_bytes=5)
    body, ctype = client.fetch_bytes("https://lh3.googleusercontent.com/p/x", max_bytes=20)
    assert body == b"x" * 10 and ctype == "image/jpeg"
```

- [ ] **Step 2: Run to verify failure**

Run: `cd backend && venv/Scripts/python -m pytest auth_service/tests/test_google_places_client.py -q`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Implement `client.py`**

```python
"""Thin urllib client for Places API (New), Place Photos and the Maps Tools Resolution
API (ADR-0012). One function per Google call; no SDK, no retries, 10 s timeouts.
Every failure surfaces as GooglePlacesError(status, message) so the router can map it."""

from __future__ import annotations

import json
import socket
import urllib.error
import urllib.parse
import urllib.request

from ...core.config import settings

USER_AGENT = "roman-technologies-cms-backend/1.0"
PLACES_BASE = "https://places.googleapis.com/v1"
RESOLVE_URL = "https://mapstools.googleapis.com/v1:resolveMapsUrls"

# Everything Place Details (New) exposes that a lead can use. Requesting any
# Enterprise + Atmosphere field bills the whole call at that SKU, so one call
# fetches it all. Keep it a single comma-separated string with no spaces.
PLACE_FIELD_MASK = ",".join(
    [
        "id", "displayName", "primaryType", "primaryTypeDisplayName", "types",
        "businessStatus", "googleMapsUri", "googleMapsLinks",
        "formattedAddress", "shortFormattedAddress", "addressComponents", "postalAddress",
        "location", "plusCode", "viewport", "timeZone", "utcOffsetMinutes",
        "pureServiceAreaBusiness",
        "nationalPhoneNumber", "internationalPhoneNumber", "websiteUri",
        "regularOpeningHours", "regularSecondaryOpeningHours",
        "rating", "userRatingCount", "reviews", "reviewSummary",
        "editorialSummary", "generativeSummary", "neighborhoodSummary",
        "priceLevel", "priceRange", "photos",
        "accessibilityOptions", "parkingOptions", "paymentOptions",
        "dineIn", "takeout", "delivery", "curbsidePickup", "reservable",
        "outdoorSeating", "liveMusic", "restroom", "goodForChildren", "goodForGroups",
        "goodForWatchingSports", "allowsDogs", "menuForChildren",
        "servesBreakfast", "servesBrunch", "servesLunch", "servesDinner", "servesBeer",
        "servesWine", "servesCocktails", "servesCoffee", "servesDessert",
        "servesVegetarianFood",
    ]
)
TEXT_SEARCH_MASK = "places.id,places.displayName,places.formattedAddress"


class GooglePlacesError(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(f"{status}: {message}")
        self.status = status
        self.message = message


def _api_key() -> str:
    key = settings.GOOGLE_MAPS_API_KEY
    if not key:
        raise GooglePlacesError(503, "Google Maps import is not configured on this backend")
    return key


def _urlopen(req: urllib.request.Request, timeout: int):
    """Single seam for tests to patch."""
    return urllib.request.urlopen(req, timeout=timeout)


def _google_message(raw: str) -> str:
    try:
        err = json.loads(raw).get("error") or {}
        return str(err.get("message") or err.get("status") or raw)[:500]
    except (ValueError, AttributeError):
        return raw[:500]


def _request_json(
    url: str,
    *,
    method: str = "GET",
    body: dict | None = None,
    field_mask: str | None = None,
    timeout: int = 10,
) -> dict:
    headers = {"X-Goog-Api-Key": _api_key(), "User-Agent": USER_AGENT, "Accept": "application/json"}
    if field_mask:
        headers["X-Goog-FieldMask"] = field_mask
    data = None
    if body is not None:
        data = json.dumps(body).encode()
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with _urlopen(req, timeout) as resp:
            return json.loads(resp.read().decode() or "{}")
    except urllib.error.HTTPError as e:
        raise GooglePlacesError(e.code, _google_message(e.read().decode(errors="replace"))) from e
    except (urllib.error.URLError, TimeoutError, socket.timeout) as e:
        raise GooglePlacesError(504, f"Google request failed: {e}") from e


def place_details(place_id: str, *, language: str = "en") -> dict:
    qs = urllib.parse.urlencode({"languageCode": language})
    return _request_json(
        f"{PLACES_BASE}/places/{urllib.parse.quote(place_id, safe='')}?{qs}",
        field_mask=PLACE_FIELD_MASK,
    )


def resolve_maps_url(url: str) -> str | None:
    """maps.app.goo.gl / google.com/maps/place URL -> place ID, or None if Google can't."""
    data = _request_json(RESOLVE_URL, method="POST", body={"urls": [url]})
    entities = data.get("entities") or [{}]
    raw = (entities[0] or {}).get("placeId") or (entities[0] or {}).get("name") or ""
    return raw.removeprefix("places/") or None


def text_search(
    query: str,
    *,
    lat: float | None = None,
    lng: float | None = None,
    language: str = "en",
    page_size: int = 5,
) -> list[dict]:
    body: dict = {"textQuery": query, "pageSize": page_size, "languageCode": language}
    if lat is not None and lng is not None:
        body["locationBias"] = {
            "circle": {"center": {"latitude": lat, "longitude": lng}, "radius": 2000.0}
        }
    data = _request_json(f"{PLACES_BASE}/places:searchText", method="POST", body=body,
                         field_mask=TEXT_SEARCH_MASK)
    out = []
    for p in data.get("places") or []:
        if not p.get("id"):
            continue
        out.append({
            "place_id": p["id"],
            "name": (p.get("displayName") or {}).get("text"),
            "address": p.get("formattedAddress"),
        })
    return out


def photo_uri(photo_name: str, *, max_width_px: int = 1600) -> str:
    """Resolve a photo resource name to a short-lived googleusercontent URL."""
    data = _request_json(
        f"{PLACES_BASE}/{photo_name}/media?maxWidthPx={max_width_px}&skipHttpRedirect=true"
    )
    uri = data.get("photoUri")
    if not uri:
        raise GooglePlacesError(502, "Place Photos returned no photoUri")
    return uri


def fetch_bytes(url: str, *, max_bytes: int = 8_000_000, timeout: int = 15) -> tuple[bytes, str]:
    """Download a public image (no API key header). Raises GooglePlacesError on size/HTTP."""
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with _urlopen(req, timeout) as resp:
            ctype = (resp.headers.get("Content-Type") or "").split(";")[0].strip().lower()
            body = resp.read(max_bytes + 1)
    except urllib.error.HTTPError as e:
        raise GooglePlacesError(e.code, f"photo download failed ({e.code})") from e
    except (urllib.error.URLError, TimeoutError, socket.timeout) as e:
        raise GooglePlacesError(504, f"photo download failed: {e}") from e
    if len(body) > max_bytes:
        raise GooglePlacesError(413, f"photo larger than {max_bytes} bytes")
    return body, ctype
```

- [ ] **Step 4: Run tests**

Run: `cd backend && venv/Scripts/python -m pytest auth_service/tests/test_google_places_client.py -q`
Expected: PASS (9 tests).

- [ ] **Step 5: Lint, commit**

```bash
cd backend && venv/Scripts/python -m ruff check . && venv/Scripts/python -m black --check .
git add backend/auth_service/services/google_places backend/auth_service/tests/test_google_places_client.py
git commit -m "feat(leads): urllib client for Places API (New)"
```

---

### Task 3: Input resolver (URL / place ID / text → place ID or candidates)

**Files:**
- Create: `backend/auth_service/services/google_places/resolve.py`
- Test: `backend/auth_service/tests/test_google_places_resolve.py`

**Interfaces:**
- Consumes: `client.resolve_maps_url`, `client.text_search`, `client._urlopen` (for short-link expansion).
- Produces: `@dataclass Resolution(place_id: str | None, candidates: list[dict])`; `classify(raw: str) -> tuple[str, str]` returning `("place_id"|"maps_url"|"text", cleaned)`; `extract_place_id_from_url(url: str) -> str | None`; `parse_name_and_coords(url: str) -> tuple[str | None, float | None, float | None]`; `expand_short_link(url: str) -> str`; `resolve(raw: str, *, language: str = "en") -> Resolution`.

- [ ] **Step 1: Write the failing tests**

```python
import io
import json

import pytest

from auth_service.core.config import settings
from auth_service.services.google_places import client, resolve


@pytest.fixture(autouse=True)
def _key(monkeypatch):
    monkeypatch.setattr(settings, "GOOGLE_MAPS_API_KEY", "test-key")


def test_classify_place_id():
    assert resolve.classify("  ChIJN1t_tDeuEmsRUsoyG83frY4 ") == ("place_id", "ChIJN1t_tDeuEmsRUsoyG83frY4")


def test_classify_maps_url_variants():
    for u in [
        "https://maps.app.goo.gl/Xyz123",
        "https://www.google.com/maps/place/Samir+Kapsalon/@52.5,5.47,17z/data=!3m1",
        "https://goo.gl/maps/abc",
        "https://maps.google.nl/?cid=123",
    ]:
        assert resolve.classify(u)[0] == "maps_url", u


def test_classify_text():
    assert resolve.classify("Samir Kapsalon, Lelystad") == ("text", "Samir Kapsalon, Lelystad")


def test_extract_place_id_from_query_param():
    u = "https://www.google.com/maps/search/?api=1&query=x&query_place_id=ChIJabc_DEF-1234567890xyz"
    assert resolve.extract_place_id_from_url(u) == "ChIJabc_DEF-1234567890xyz"


def test_extract_place_id_from_data_segment():
    u = "https://www.google.com/maps/place/X/@1,2,17z/data=!4m6!3m5!1s0x47c6:0x9a!8m2!3d52!4d5!19sChIJabc-xyz_123?entry=ttu"
    assert resolve.extract_place_id_from_url(u) == "ChIJabc-xyz_123"


def test_extract_place_id_none_for_cid_only():
    assert resolve.extract_place_id_from_url("https://maps.google.com/?cid=12345") is None


def test_parse_name_and_coords():
    u = "https://www.google.com/maps/place/Samir+Kapsalon+%26+Barber/@52.5083,5.4751,17z/data=!3m1"
    assert resolve.parse_name_and_coords(u) == ("Samir Kapsalon & Barber", 52.5083, 5.4751)


def test_parse_name_and_coords_missing():
    assert resolve.parse_name_and_coords("https://maps.app.goo.gl/abc") == (None, None, None)


def test_resolve_place_id_short_circuits(monkeypatch):
    monkeypatch.setattr(client, "_urlopen", lambda *a, **k: pytest.fail("no network expected"))
    assert resolve.resolve("ChIJN1t_tDeuEmsRUsoyG83frY4") == resolve.Resolution("ChIJN1t_tDeuEmsRUsoyG83frY4", [])


def test_resolve_url_uses_resolution_api(monkeypatch):
    monkeypatch.setattr(client, "resolve_maps_url", lambda url: "ChIJfromapi")
    assert resolve.resolve("https://maps.app.goo.gl/abc").place_id == "ChIJfromapi"


def test_resolve_url_with_embedded_id_skips_api(monkeypatch):
    monkeypatch.setattr(client, "resolve_maps_url", lambda url: pytest.fail("should not call"))
    u = "https://www.google.com/maps/place/X/@1,2,17z/data=!19sChIJembedded"
    assert resolve.resolve(u).place_id == "ChIJembedded"


def test_resolve_unresolvable_url_falls_back_to_text_search(monkeypatch):
    monkeypatch.setattr(client, "resolve_maps_url", lambda url: None)
    monkeypatch.setattr(resolve, "expand_short_link", lambda url: (
        "https://www.google.com/maps/place/Samir+Kapsalon/@52.5,5.47,17z/data=!3m1"))
    calls = {}

    def fake_search(query, *, lat=None, lng=None, language="en", page_size=5):
        calls.update(query=query, lat=lat, lng=lng)
        return [{"place_id": "ChIJ1", "name": "Samir Kapsalon", "address": "A"},
                {"place_id": "ChIJ2", "name": "Samir Barber", "address": "B"}]

    monkeypatch.setattr(client, "text_search", fake_search)
    out = resolve.resolve("https://maps.app.goo.gl/dead")
    assert out.place_id is None and len(out.candidates) == 2
    assert calls == {"query": "Samir Kapsalon", "lat": 52.5, "lng": 5.47}


def test_resolve_unresolvable_url_without_name_gives_empty(monkeypatch):
    monkeypatch.setattr(client, "resolve_maps_url", lambda url: None)
    monkeypatch.setattr(resolve, "expand_short_link", lambda url: url)
    monkeypatch.setattr(client, "text_search", lambda *a, **k: pytest.fail("nothing to search"))
    assert resolve.resolve("https://maps.app.goo.gl/dead") == resolve.Resolution(None, [])


def test_resolve_text_single_hit_is_direct(monkeypatch):
    monkeypatch.setattr(client, "text_search", lambda *a, **k: [{"place_id": "ChIJonly", "name": "X", "address": None}])
    assert resolve.resolve("Samir Kapsalon Lelystad").place_id == "ChIJonly"


def test_resolve_text_many_hits_are_candidates(monkeypatch):
    monkeypatch.setattr(client, "text_search", lambda *a, **k: [
        {"place_id": "a", "name": "A", "address": None}, {"place_id": "b", "name": "B", "address": None}])
    out = resolve.resolve("Kapsalon")
    assert out.place_id is None and [c["place_id"] for c in out.candidates] == ["a", "b"]


def test_expand_short_link_follows_redirect(monkeypatch):
    class _R(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *a):
            pass

        def geturl(self):
            return "https://www.google.com/maps/place/X/@1,2,17z"

    monkeypatch.setattr(client, "_urlopen", lambda req, timeout: _R(b""))
    assert resolve.expand_short_link("https://maps.app.goo.gl/abc").startswith("https://www.google.com/maps/place/X")


def test_expand_short_link_failure_returns_input(monkeypatch):
    def boom(req, timeout):
        raise OSError("down")

    monkeypatch.setattr(client, "_urlopen", boom)
    assert resolve.expand_short_link("https://maps.app.goo.gl/abc") == "https://maps.app.goo.gl/abc"
```

- [ ] **Step 2: Run to verify failure**

Run: `cd backend && venv/Scripts/python -m pytest auth_service/tests/test_google_places_resolve.py -q`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Implement `resolve.py`**

```python
"""Turn whatever the admin pastes into a place ID (ADR-0012).

Order: raw place ID -> ID embedded in the URL -> Maps Tools Resolution API ($0) ->
Text Search on the name/coords parsed out of the (expanded) URL -> candidates for the
admin to pick. Free text goes straight to Text Search."""

from __future__ import annotations

import re
import urllib.parse
import urllib.request
from dataclasses import dataclass, field

from . import client

PLACE_ID_RE = re.compile(r"^[A-Za-z0-9_-]{20,}$")
_QUERY_ID_RE = re.compile(r"[?&](?:query_place_id|place_id|placeid)=([A-Za-z0-9_-]{20,})")
_DATA_ID_RE = re.compile(r"!19s(ChIJ[A-Za-z0-9_-]+)")
_PLACE_PATH_RE = re.compile(r"/maps/place/([^/@?]+)(?:/@(-?\d+(?:\.\d+)?),(-?\d+(?:\.\d+)?))?")
_MAPS_HOST_RE = re.compile(
    r"^(?:www\.|maps\.)?(?:google\.[a-z.]+|goo\.gl|maps\.app\.goo\.gl|g\.page|g\.co)$"
)


@dataclass
class Resolution:
    place_id: str | None
    candidates: list[dict] = field(default_factory=list)


def classify(raw: str) -> tuple[str, str]:
    value = raw.strip()
    if PLACE_ID_RE.match(value):
        return "place_id", value
    if "://" not in value and value.lower().startswith(("maps.app.goo.gl", "goo.gl", "www.google.", "maps.google.")):
        value = "https://" + value
    try:
        host = (urllib.parse.urlsplit(value).hostname or "").lower()
    except ValueError:
        host = ""
    if host and _MAPS_HOST_RE.match(host):
        return "maps_url", value
    return "text", value


def extract_place_id_from_url(url: str) -> str | None:
    m = _QUERY_ID_RE.search(url) or _DATA_ID_RE.search(url)
    return m.group(1) if m else None


def parse_name_and_coords(url: str) -> tuple[str | None, float | None, float | None]:
    m = _PLACE_PATH_RE.search(url)
    if not m:
        return None, None, None
    name = urllib.parse.unquote_plus(m.group(1)).strip() or None
    lat = float(m.group(2)) if m.group(2) else None
    lng = float(m.group(3)) if m.group(3) else None
    return name, lat, lng


def expand_short_link(url: str) -> str:
    """Follow redirects of a goo.gl-style link; return the final URL (or the input)."""
    req = urllib.request.Request(url, headers={"User-Agent": client.USER_AGENT}, method="GET")
    try:
        with client._urlopen(req, 8) as resp:
            return resp.geturl() or url
    except Exception:  # noqa: BLE001 — any failure just means "no expansion"
        return url


def resolve(raw: str, *, language: str = "en") -> Resolution:
    kind, value = classify(raw)
    if kind == "place_id":
        return Resolution(value)

    if kind == "maps_url":
        embedded = extract_place_id_from_url(value)
        if embedded:
            return Resolution(embedded)
        pid = client.resolve_maps_url(value)
        if pid:
            return Resolution(pid)
        expanded = expand_short_link(value)
        embedded = extract_place_id_from_url(expanded)
        if embedded:
            return Resolution(embedded)
        name, lat, lng = parse_name_and_coords(expanded)
        if not name:
            return Resolution(None)
        return _from_search(client.text_search(name, lat=lat, lng=lng, language=language))

    return _from_search(client.text_search(value, language=language))


def _from_search(hits: list[dict]) -> Resolution:
    if len(hits) == 1:
        return Resolution(hits[0]["place_id"])
    return Resolution(None, hits)
```

- [ ] **Step 4: Run tests**

Run: `cd backend && venv/Scripts/python -m pytest auth_service/tests/test_google_places_resolve.py -q`
Expected: PASS (17 tests).

- [ ] **Step 5: Lint, commit**

```bash
cd backend && venv/Scripts/python -m ruff check . && venv/Scripts/python -m black --check .
git add backend/auth_service/services/google_places/resolve.py backend/auth_service/tests/test_google_places_resolve.py
git commit -m "feat(leads): resolve Maps URLs, place IDs and text to a place"
```

---

### Task 4: Mapper (Place JSON → lead columns, attributes, extra.google)

**Files:**
- Create: `backend/auth_service/services/google_places/mapper.py`
- Create: `backend/auth_service/tests/fixtures/google_place_details.json`
- Test: `backend/auth_service/tests/test_google_places_mapper.py`

**Interfaces:**
- Consumes: `website_enrich.social_platform_of(url) -> str | None` and `website_enrich.normalize_social_url(platform, url) -> str` (Task 5 — implement them there first if running out of order; the mapper imports them lazily from `.website_enrich`).
- Produces: `@dataclass MappedPlace(columns: dict, attributes: dict[str, dict[str, bool]], google: dict, photos: list[dict], website_uri: str | None)`; `map_place(place: dict, *, language: str = "en") -> MappedPlace`; `classify_web_presence(website_uri: str | None) -> tuple[str, dict[str, str]]` returning `(web_presence, social_links_from_website_uri)`; `normalize_name(name: str) -> str` (same regex as the router: lower + collapse whitespace).
  `columns` keys: `business_name, name_normalized, category, about, country, region, city, address, postal_code, lat, lng, phone, website_url, web_presence, facebook_url, instagram_url, rating, review_count, reviews, opening_hours, business_status, primary_type, types, price_level, source_url`. `photos[]` items: `{"name", "width_px", "height_px", "attributions": [{"name", "uri", "photo_uri"}], "google_maps_uri"}`.

- [ ] **Step 1: Write the fixture** `google_place_details.json` (a realistic Dutch barber):

```json
{
  "id": "ChIJsamir0000000000000000000",
  "displayName": {"text": "Samir Kapsalon", "languageCode": "nl"},
  "primaryType": "barber_shop",
  "primaryTypeDisplayName": {"text": "Barber shop", "languageCode": "en"},
  "types": ["barber_shop", "hair_salon", "point_of_interest", "establishment"],
  "businessStatus": "OPERATIONAL",
  "googleMapsUri": "https://maps.google.com/?cid=1234567890",
  "googleMapsLinks": {"directionsUri": "https://www.google.com/maps/dir/?x", "placeUri": "https://maps.google.com/?cid=1234567890", "writeAReviewUri": "https://www.google.com/maps/place//r", "reviewsUri": "https://www.google.com/maps/place//rv", "photosUri": "https://www.google.com/maps/place//ph"},
  "formattedAddress": "Stadhuisplein 12, 8232 ZX Lelystad, Netherlands",
  "shortFormattedAddress": "Stadhuisplein 12, Lelystad",
  "addressComponents": [
    {"longText": "12", "shortText": "12", "types": ["street_number"], "languageCode": "nl"},
    {"longText": "Stadhuisplein", "shortText": "Stadhuisplein", "types": ["route"], "languageCode": "nl"},
    {"longText": "Lelystad", "shortText": "Lelystad", "types": ["locality", "political"], "languageCode": "nl"},
    {"longText": "Flevoland", "shortText": "FL", "types": ["administrative_area_level_1", "political"], "languageCode": "nl"},
    {"longText": "Netherlands", "shortText": "NL", "types": ["country", "political"], "languageCode": "en"},
    {"longText": "8232 ZX", "shortText": "8232 ZX", "types": ["postal_code"], "languageCode": "nl"}
  ],
  "postalAddress": {"regionCode": "NL", "postalCode": "8232 ZX", "locality": "Lelystad", "addressLines": ["Stadhuisplein 12"]},
  "location": {"latitude": 52.5083, "longitude": 5.4751},
  "plusCode": {"globalCode": "9F47GF5G+8W", "compoundCode": "GF5G+8W Lelystad"},
  "viewport": {"low": {"latitude": 52.50, "longitude": 5.47}, "high": {"latitude": 52.51, "longitude": 5.48}},
  "timeZone": {"id": "Europe/Amsterdam"},
  "utcOffsetMinutes": 120,
  "pureServiceAreaBusiness": false,
  "nationalPhoneNumber": "0320 123456",
  "internationalPhoneNumber": "+31 320 123456",
  "websiteUri": "https://samirkapsalon.nl/",
  "regularOpeningHours": {
    "periods": [
      {"open": {"day": 1, "hour": 9, "minute": 0}, "close": {"day": 1, "hour": 18, "minute": 0}},
      {"open": {"day": 2, "hour": 9, "minute": 0}, "close": {"day": 2, "hour": 18, "minute": 0}}
    ],
    "weekdayDescriptions": [
      "Monday: 9:00 AM – 6:00 PM", "Tuesday: 9:00 AM – 6:00 PM", "Wednesday: 9:00 AM – 6:00 PM",
      "Thursday: 9:00 AM – 8:00 PM", "Friday: 9:00 AM – 6:00 PM", "Saturday: 9:00 AM – 5:00 PM", "Sunday: Closed"
    ]
  },
  "rating": 4.8,
  "userRatingCount": 212,
  "reviews": [
    {
      "name": "places/ChIJsamir/reviews/r1",
      "relativePublishTimeDescription": "2 months ago",
      "rating": 5,
      "text": {"text": "Beste kapper van Lelystad!", "languageCode": "nl"},
      "originalText": {"text": "Beste kapper van Lelystad!", "languageCode": "nl"},
      "authorAttribution": {"displayName": "Maria K.", "uri": "https://www.google.com/maps/contrib/1", "photoUri": "https://lh3.googleusercontent.com/a/1"},
      "publishTime": "2026-08-01T10:00:00Z",
      "googleMapsUri": "https://www.google.com/maps/reviews/r1"
    }
  ],
  "reviewSummary": {"text": {"text": "People praise the fades.", "languageCode": "en"}},
  "editorialSummary": {"text": "Modern barber shop with walk-ins.", "languageCode": "en"},
  "generativeSummary": {"overview": {"text": "A busy barber shop known for sharp fades.", "languageCode": "en"}, "disclosureText": {"text": "Summarized with Gemini", "languageCode": "en"}},
  "priceLevel": "PRICE_LEVEL_MODERATE",
  "priceRange": {"startPrice": {"currencyCode": "EUR", "units": "20"}, "endPrice": {"currencyCode": "EUR", "units": "40"}},
  "photos": [
    {"name": "places/ChIJsamir/photos/p1", "widthPx": 4032, "heightPx": 3024, "authorAttributions": [{"displayName": "Samir Kapsalon", "uri": "https://maps.google.com/maps/contrib/9", "photoUri": "https://lh3.googleusercontent.com/a/9"}], "googleMapsUri": "https://www.google.com/maps/place//photos/p1"},
    {"name": "places/ChIJsamir/photos/p2", "widthPx": 1080, "heightPx": 1080, "authorAttributions": [{"displayName": "Jan de Vries", "uri": "https://maps.google.com/maps/contrib/8", "photoUri": ""}], "googleMapsUri": "https://www.google.com/maps/place//photos/p2"}
  ],
  "accessibilityOptions": {"wheelchairAccessibleEntrance": true, "wheelchairAccessibleRestroom": false},
  "parkingOptions": {"freeStreetParking": true},
  "paymentOptions": {"acceptsCreditCards": true, "acceptsNfc": true, "acceptsCashOnly": false},
  "restroom": true,
  "goodForChildren": true,
  "reservable": false
}
```

- [ ] **Step 2: Write the failing tests**

```python
import json
from pathlib import Path

from auth_service.services.google_places import mapper

FIX = Path(__file__).parent / "fixtures" / "google_place_details.json"


def _place():
    return json.loads(FIX.read_text(encoding="utf-8"))


def test_map_place_columns():
    m = mapper.map_place(_place())
    c = m.columns
    assert c["business_name"] == "Samir Kapsalon"
    assert c["name_normalized"] == "samir kapsalon"
    assert c["category"] == "Barber shop"
    assert c["about"] == "Modern barber shop with walk-ins."
    assert (c["country"], c["region"], c["city"], c["postal_code"]) == ("NL", "Flevoland", "Lelystad", "8232 ZX")
    assert c["address"] == "Stadhuisplein 12, 8232 ZX Lelystad, Netherlands"
    assert (c["lat"], c["lng"]) == (52.5083, 5.4751)
    assert c["phone"] == "+31 320 123456"
    assert c["website_url"] == "https://samirkapsalon.nl/"
    assert c["web_presence"] == "has_website"
    assert c["facebook_url"] is None and c["instagram_url"] is None
    assert c["rating"] == 4.8 and c["review_count"] == 212
    assert c["business_status"] == "OPERATIONAL"
    assert c["primary_type"] == "barber_shop"
    assert c["types"] == ["barber_shop", "hair_salon", "point_of_interest", "establishment"]
    assert c["price_level"] == "moderate"
    assert c["source_url"] == "https://maps.google.com/?cid=1234567890"
    assert m.website_uri == "https://samirkapsalon.nl/"


def test_map_place_opening_hours_shape():
    m = mapper.map_place(_place())
    assert m.columns["opening_hours"]["Monday"] == "9:00 AM – 6:00 PM"
    assert m.columns["opening_hours"]["Sunday"] == "Closed"
    assert len(m.columns["opening_hours"]) == 7
    assert m.google["opening_hours"]["periods"][0]["open"]["day"] == 1


def test_map_place_reviews_shape():
    r = mapper.map_place(_place()).columns["reviews"][0]
    assert r == {
        "author": "Maria K.", "rating": 5, "text": "Beste kapper van Lelystad!",
        "relative_date": "2 months ago", "date": "2026-08-01T10:00:00Z",
        "author_uri": "https://www.google.com/maps/contrib/1",
        "author_photo_uri": "https://lh3.googleusercontent.com/a/1",
        "google_maps_uri": "https://www.google.com/maps/reviews/r1",
    }


def test_map_place_attributes_sections():
    a = mapper.map_place(_place()).attributes
    assert a["Accessibility"] == {"Wheelchair accessible entrance": True, "Wheelchair accessible restroom": False}
    assert a["Parking"] == {"Free street parking": True}
    assert a["Payments"] == {"Credit cards": True, "NFC mobile payments": True, "Cash only": False}
    assert a["Amenities"] == {"Restroom": True}
    assert a["Crowd"] == {"Good for kids": True}
    assert a["Service options"] == {"Reservations": False}
    assert "Offerings" not in a  # nothing present in the fixture


def test_map_place_google_blob():
    g = mapper.map_place(_place()).google
    assert g["place_id"] == "ChIJsamir0000000000000000000"
    assert g["maps_links"]["directionsUri"].startswith("https://")
    assert g["generative_summary"] == {"overview": "A busy barber shop known for sharp fades.", "disclosure": "Summarized with Gemini"}
    assert g["review_summary"] == "People praise the fades."
    assert g["price_range"]["startPrice"]["units"] == "20"
    assert g["time_zone"] == "Europe/Amsterdam"
    assert g["address_components"][0]["types"] == ["street_number"]
    assert g["pure_service_area_business"] is False


def test_map_place_photos():
    p = mapper.map_place(_place()).photos
    assert len(p) == 2
    assert p[0] == {
        "name": "places/ChIJsamir/photos/p1", "width_px": 4032, "height_px": 3024,
        "attributions": [{"name": "Samir Kapsalon", "uri": "https://maps.google.com/maps/contrib/9", "photo_uri": "https://lh3.googleusercontent.com/a/9"}],
        "google_maps_uri": "https://www.google.com/maps/place//photos/p1",
    }


def test_map_place_about_falls_back_to_generative():
    place = _place()
    del place["editorialSummary"]
    assert mapper.map_place(place).columns["about"] == "A busy barber shop known for sharp fades."


def test_map_place_minimal_listing():
    place = {"id": "ChIJmin", "displayName": {"text": "Mobile Dog Groomer"}, "pureServiceAreaBusiness": True}
    m = mapper.map_place(place)
    c = m.columns
    assert c["business_name"] == "Mobile Dog Groomer"
    assert c["web_presence"] == "none"
    assert c["phone"] is None and c["opening_hours"] is None and c["reviews"] == []
    assert c["country"] is None and c["rating"] is None and c["types"] == []
    assert m.attributes == {} and m.photos == [] and m.website_uri is None
    assert m.google["pure_service_area_business"] is True


def test_classify_web_presence_social_site():
    presence, links = mapper.classify_web_presence("https://www.facebook.com/samirkapsalon/")
    assert presence == "social_only"
    assert links == {"facebook": "https://www.facebook.com/samirkapsalon"}
    assert mapper.classify_web_presence(None) == ("none", {})
    assert mapper.classify_web_presence("https://samir.nl") == ("has_website", {})


def test_map_place_phone_falls_back_to_national():
    place = _place()
    del place["internationalPhoneNumber"]
    assert mapper.map_place(place).columns["phone"] == "0320 123456"
```

- [ ] **Step 3: Run to verify failure**

Run: `cd backend && venv/Scripts/python -m pytest auth_service/tests/test_google_places_mapper.py -q`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 4: Implement `mapper.py`**

```python
"""Pure mapping from a Place Details (New) response to lead columns (ADR-0012).
No I/O. Missing fields stay None/empty; nothing here raises on a sparse listing."""

from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass
class MappedPlace:
    columns: dict
    attributes: dict[str, dict[str, bool]]
    google: dict
    photos: list[dict] = field(default_factory=list)
    website_uri: str | None = None


# Flat boolean attributes -> dashboard "About" sections (extra.attributes shape).
_FLAT_SECTIONS: dict[str, dict[str, str]] = {
    "Service options": {
        "dineIn": "Dine-in", "takeout": "Takeout", "delivery": "Delivery",
        "curbsidePickup": "Curbside pickup", "reservable": "Reservations",
    },
    "Amenities": {
        "outdoorSeating": "Outdoor seating", "restroom": "Restroom", "liveMusic": "Live music",
        "goodForWatchingSports": "Good for watching sports",
    },
    "Offerings": {
        "servesBreakfast": "Breakfast", "servesBrunch": "Brunch", "servesLunch": "Lunch",
        "servesDinner": "Dinner", "servesBeer": "Beer", "servesWine": "Wine",
        "servesCocktails": "Cocktails", "servesCoffee": "Coffee", "servesDessert": "Dessert",
        "servesVegetarianFood": "Vegetarian options", "menuForChildren": "Kids' menu",
    },
    "Crowd": {"goodForChildren": "Good for kids", "goodForGroups": "Good for groups"},
    "Pets": {"allowsDogs": "Dogs allowed"},
}
# Nested option objects -> sections.
_NESTED_SECTIONS: dict[str, tuple[str, dict[str, str]]] = {
    "Accessibility": ("accessibilityOptions", {
        "wheelchairAccessibleParking": "Wheelchair accessible parking",
        "wheelchairAccessibleEntrance": "Wheelchair accessible entrance",
        "wheelchairAccessibleRestroom": "Wheelchair accessible restroom",
        "wheelchairAccessibleSeating": "Wheelchair accessible seating",
    }),
    "Parking": ("parkingOptions", {
        "freeParkingLot": "Free parking lot", "paidParkingLot": "Paid parking lot",
        "freeStreetParking": "Free street parking", "paidStreetParking": "Paid street parking",
        "valetParking": "Valet parking", "freeGarageParking": "Free garage parking",
        "paidGarageParking": "Paid garage parking",
    }),
    "Payments": ("paymentOptions", {
        "acceptsCreditCards": "Credit cards", "acceptsDebitCards": "Debit cards",
        "acceptsCashOnly": "Cash only", "acceptsNfc": "NFC mobile payments",
    }),
}


def normalize_name(name: str) -> str:
    return re.sub(r"\s+", " ", name.lower()).strip()


def _text(obj: dict | None) -> str | None:
    if not isinstance(obj, dict):
        return None
    t = obj.get("text")
    return t.strip() if isinstance(t, str) and t.strip() else None


def _address_parts(components: list[dict] | None) -> dict:
    out = {"country": None, "region": None, "city": None, "postal_code": None}
    for comp in components or []:
        types = set(comp.get("types") or [])
        if "country" in types:
            out["country"] = comp.get("shortText") or comp.get("longText")
        elif "administrative_area_level_1" in types:
            out["region"] = comp.get("longText") or comp.get("shortText")
        elif "locality" in types or ("postal_town" in types and not out["city"]):
            out["city"] = comp.get("longText") or comp.get("shortText")
        elif "postal_code" in types:
            out["postal_code"] = comp.get("longText") or comp.get("shortText")
    return out


def _hours(regular: dict | None) -> dict[str, str] | None:
    descs = (regular or {}).get("weekdayDescriptions") or []
    out: dict[str, str] = {}
    for line in descs:
        day, sep, hours = str(line).partition(":")
        if sep and day.strip():
            out[day.strip()] = hours.strip()
    return out or None


def _reviews(raw: list[dict] | None) -> list[dict]:
    out = []
    for r in raw or []:
        author = r.get("authorAttribution") or {}
        out.append({
            "author": author.get("displayName"),
            "rating": r.get("rating"),
            "text": _text(r.get("text")) or _text(r.get("originalText")),
            "relative_date": r.get("relativePublishTimeDescription"),
            "date": r.get("publishTime"),
            "author_uri": author.get("uri"),
            "author_photo_uri": author.get("photoUri"),
            "google_maps_uri": r.get("googleMapsUri"),
        })
    return out


def _attributes(place: dict) -> dict[str, dict[str, bool]]:
    out: dict[str, dict[str, bool]] = {}
    for section, keys in _FLAT_SECTIONS.items():
        vals = {label: bool(place[k]) for k, label in keys.items() if isinstance(place.get(k), bool)}
        if vals:
            out[section] = vals
    for section, (obj_key, keys) in _NESTED_SECTIONS.items():
        obj = place.get(obj_key) or {}
        vals = {label: bool(obj[k]) for k, label in keys.items() if isinstance(obj.get(k), bool)}
        if vals:
            out[section] = vals
    return out


def _photos(raw: list[dict] | None) -> list[dict]:
    out = []
    for p in raw or []:
        if not p.get("name"):
            continue
        out.append({
            "name": p["name"],
            "width_px": p.get("widthPx"),
            "height_px": p.get("heightPx"),
            "attributions": [
                {"name": a.get("displayName"), "uri": a.get("uri"), "photo_uri": a.get("photoUri")}
                for a in (p.get("authorAttributions") or [])
            ],
            "google_maps_uri": p.get("googleMapsUri"),
        })
    return out


def classify_web_presence(website_uri: str | None) -> tuple[str, dict[str, str]]:
    """A Facebook/Instagram page as 'website' means social_only; a real site has_website."""
    from .website_enrich import normalize_social_url, social_platform_of

    if not website_uri:
        return "none", {}
    platform = social_platform_of(website_uri)
    if platform in ("facebook", "instagram"):
        return "social_only", {platform: normalize_social_url(platform, website_uri)}
    return "has_website", {}


def map_place(place: dict, *, language: str = "en") -> MappedPlace:
    name = _text(place.get("displayName")) or "Unnamed business"
    website_uri = (place.get("websiteUri") or "").strip() or None
    presence, social = classify_web_presence(website_uri)
    price_level = place.get("priceLevel")
    addr = _address_parts(place.get("addressComponents"))
    loc = place.get("location") or {}
    gen = place.get("generativeSummary") or {}

    columns = {
        "business_name": name,
        "name_normalized": normalize_name(name),
        "category": _text(place.get("primaryTypeDisplayName")),
        "about": _text(place.get("editorialSummary")) or _text(gen.get("overview")),
        **addr,
        "address": place.get("formattedAddress"),
        "lat": loc.get("latitude"),
        "lng": loc.get("longitude"),
        "phone": place.get("internationalPhoneNumber") or place.get("nationalPhoneNumber"),
        "website_url": None if presence == "social_only" else website_uri,
        "web_presence": presence,
        "facebook_url": social.get("facebook"),
        "instagram_url": social.get("instagram"),
        "rating": place.get("rating"),
        "review_count": place.get("userRatingCount"),
        "reviews": _reviews(place.get("reviews")),
        "opening_hours": _hours(place.get("regularOpeningHours")),
        "business_status": place.get("businessStatus"),
        "primary_type": place.get("primaryType"),
        "types": list(place.get("types") or []),
        "price_level": price_level.removeprefix("PRICE_LEVEL_").lower() if isinstance(price_level, str) and price_level != "PRICE_LEVEL_UNSPECIFIED" else None,
        "source_url": place.get("googleMapsUri"),
    }

    google = {
        "place_id": place.get("id"),
        "language": language,
        "display_name": name,
        "short_formatted_address": place.get("shortFormattedAddress"),
        "address_components": place.get("addressComponents") or [],
        "postal_address": place.get("postalAddress"),
        "plus_code": place.get("plusCode"),
        "viewport": place.get("viewport"),
        "time_zone": (place.get("timeZone") or {}).get("id"),
        "utc_offset_minutes": place.get("utcOffsetMinutes"),
        "pure_service_area_business": bool(place.get("pureServiceAreaBusiness", False)),
        "maps_uri": place.get("googleMapsUri"),
        "maps_links": place.get("googleMapsLinks"),
        "primary_type_display_name": _text(place.get("primaryTypeDisplayName")),
        "price_range": place.get("priceRange"),
        "editorial_summary": _text(place.get("editorialSummary")),
        "generative_summary": (
            {"overview": _text(gen.get("overview")), "disclosure": _text(gen.get("disclosureText"))}
            if gen else None
        ),
        "review_summary": _text((place.get("reviewSummary") or {}).get("text")),
        "neighborhood_summary": place.get("neighborhoodSummary"),
        "opening_hours": {
            "periods": (place.get("regularOpeningHours") or {}).get("periods") or [],
            "weekday_descriptions": (place.get("regularOpeningHours") or {}).get("weekdayDescriptions") or [],
            "secondary": place.get("regularSecondaryOpeningHours") or [],
        },
        "website_uri": website_uri,
    }

    return MappedPlace(
        columns=columns,
        attributes=_attributes(place),
        google=google,
        photos=_photos(place.get("photos")),
        website_uri=website_uri,
    )
```

- [ ] **Step 5: Run tests**

Run: `cd backend && venv/Scripts/python -m pytest auth_service/tests/test_google_places_mapper.py -q`
Expected: PASS once Task 5's `social_platform_of`/`normalize_social_url` exist. If Task 5 is not done yet, create `website_enrich.py` with only those two functions from Task 5 Step 3 now; Task 5 extends the file.

- [ ] **Step 6: Lint, commit**

```bash
cd backend && venv/Scripts/python -m ruff check . && venv/Scripts/python -m black --check .
git add backend/auth_service/services/google_places/mapper.py backend/auth_service/tests/fixtures/google_place_details.json backend/auth_service/tests/test_google_places_mapper.py
git commit -m "feat(leads): map Place Details to lead columns and extra.google"
```

---

### Task 5: Website enrichment (social links, email, description) with SSRF guard

**Files:**
- Create: `backend/auth_service/services/google_places/website_enrich.py`
- Create: `backend/auth_service/tests/fixtures/website_sample.html`
- Test: `backend/auth_service/tests/test_google_places_website_enrich.py`

**Interfaces:**
- Produces: `SOCIAL_HOSTS: dict[str, tuple[str, ...]]`; `social_platform_of(url: str) -> str | None`; `normalize_social_url(platform: str, url: str) -> str`; `class UnsafeUrl(ValueError)`; `assert_public_http_url(url: str) -> None`; `fetch_html(url: str, *, timeout: int = 8, max_bytes: int = 1_000_000) -> tuple[str, str]` (final_url, html); `extract(html: str) -> dict` with keys `social_links: dict[str, str]`, `email: str | None`, `description: str | None`, `lang: str | None`; `enrich_from_website(url: str) -> dict` with keys `fetched: bool`, `final_url: str | None`, `social_links`, `email`, `description`, `lang`, `error: str | None`; module seam `_open(url, timeout)` for tests.

- [ ] **Step 1: Write the fixture** `website_sample.html`:

```html
<!doctype html>
<html lang="nl">
<head>
  <meta charset="utf-8">
  <meta name="description" content="Samir Kapsalon — moderne barbier in Lelystad.">
  <meta property="og:description" content="OG text that must not win over name=description">
  <script type="application/ld+json">
  {"@context":"https://schema.org","@type":"HairSalon","name":"Samir Kapsalon",
   "sameAs":["https://www.tiktok.com/@samirkapsalon","https://www.youtube.com/@samirkapsalon"]}
  </script>
</head>
<body>
  <a href="https://www.facebook.com/sharer/sharer.php?u=x">Share</a>
  <a href="https://www.facebook.com/samirkapsalon/">Facebook</a>
  <a href="https://instagram.com/samir.kapsalon?igshid=abc">Instagram</a>
  <a href="https://www.instagram.com/p/C123/">A post</a>
  <a href="https://wa.me/31612345678?text=hi">WhatsApp</a>
  <a href="https://twitter.com/intent/tweet?text=x">Tweet</a>
  <a href="https://x.com/samirkapsalon">X</a>
  <a href="https://nl.linkedin.com/company/samir-kapsalon">LinkedIn</a>
  <a href="https://nl.pinterest.com/samirkapsalon/">Pinterest</a>
  <a href="mailto:info@samirkapsalon.nl?subject=Afspraak">Mail</a>
  <a href="mailto:second@samirkapsalon.nl">Mail 2</a>
</body>
</html>
```

- [ ] **Step 2: Write the failing tests**

```python
import io
import socket
from pathlib import Path

import pytest

from auth_service.services.google_places import website_enrich as we

FIX = Path(__file__).parent / "fixtures" / "website_sample.html"


@pytest.mark.parametrize("url,platform", [
    ("https://www.facebook.com/samirkapsalon/", "facebook"),
    ("https://m.facebook.com/samirkapsalon", "facebook"),
    ("https://www.facebook.com/sharer/sharer.php?u=x", None),
    ("https://www.facebook.com/", None),
    ("https://instagram.com/samir.kapsalon?igshid=abc", "instagram"),
    ("https://www.instagram.com/p/C123/", None),
    ("https://www.tiktok.com/@samir", "tiktok"),
    ("https://www.tiktok.com/@samir/video/123", None),
    ("https://nl.linkedin.com/company/samir", "linkedin"),
    ("https://www.linkedin.com/shareArticle?mini=true", None),
    ("https://www.youtube.com/@samir", "youtube"),
    ("https://www.youtube.com/watch?v=abc", None),
    ("https://x.com/samir", "x"),
    ("https://twitter.com/intent/tweet?text=x", None),
    ("https://nl.pinterest.com/samir/", "pinterest"),
    ("https://wa.me/31612345678", "whatsapp"),
    ("https://samirkapsalon.nl/", None),
    ("javascript:alert(1)", None),
    ("not a url", None),
])
def test_social_platform_of(url, platform):
    assert we.social_platform_of(url) == platform


def test_normalize_social_url_strips_query_and_slash():
    assert we.normalize_social_url("instagram", "http://instagram.com/samir.kapsalon/?igshid=abc") == "https://instagram.com/samir.kapsalon"


def test_normalize_social_url_keeps_whatsapp_phone():
    assert we.normalize_social_url("whatsapp", "https://wa.me/31612345678?text=hi") == "https://wa.me/31612345678"


def test_extract_from_fixture():
    out = we.extract(FIX.read_text(encoding="utf-8"))
    assert out["social_links"] == {
        "facebook": "https://www.facebook.com/samirkapsalon",
        "instagram": "https://instagram.com/samir.kapsalon",
        "whatsapp": "https://wa.me/31612345678",
        "x": "https://x.com/samirkapsalon",
        "linkedin": "https://nl.linkedin.com/company/samir-kapsalon",
        "pinterest": "https://nl.pinterest.com/samirkapsalon",
        "tiktok": "https://www.tiktok.com/@samirkapsalon",
        "youtube": "https://www.youtube.com/@samirkapsalon",
    }
    assert out["email"] == "info@samirkapsalon.nl"
    assert out["description"] == "Samir Kapsalon — moderne barbier in Lelystad."
    assert out["lang"] == "nl"


def test_extract_uses_og_description_when_no_meta_description():
    html = '<html><head><meta property="og:description" content="Only OG"></head><body></body></html>'
    assert we.extract(html)["description"] == "Only OG"


def test_extract_empty_page():
    assert we.extract("<html></html>") == {"social_links": {}, "email": None, "description": None, "lang": None}


def _addr(ip):
    return lambda host, port, **kw: [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (ip, port))]


def test_assert_public_rejects_private(monkeypatch):
    monkeypatch.setattr(socket, "getaddrinfo", _addr("10.0.0.5"))
    with pytest.raises(we.UnsafeUrl):
        we.assert_public_http_url("https://intranet.example/")


def test_assert_public_rejects_loopback_and_scheme(monkeypatch):
    monkeypatch.setattr(socket, "getaddrinfo", _addr("127.0.0.1"))
    with pytest.raises(we.UnsafeUrl):
        we.assert_public_http_url("http://localhost/")
    with pytest.raises(we.UnsafeUrl):
        we.assert_public_http_url("ftp://example.com/")


def test_assert_public_accepts_public(monkeypatch):
    monkeypatch.setattr(socket, "getaddrinfo", _addr("93.184.216.34"))
    we.assert_public_http_url("https://example.com/")


class _Resp(io.BytesIO):
    def __init__(self, body, ctype="text/html; charset=utf-8", url="https://samirkapsalon.nl/"):
        super().__init__(body)
        self._ctype, self._url = ctype, url

    def __enter__(self):
        return self

    def __exit__(self, *a):
        pass

    def geturl(self):
        return self._url

    @property
    def headers(self):
        import email.message

        m = email.message.Message()
        m["Content-Type"] = self._ctype
        return m


def test_fetch_html_caps_bytes(monkeypatch):
    monkeypatch.setattr(socket, "getaddrinfo", _addr("93.184.216.34"))
    monkeypatch.setattr(we, "_open", lambda url, timeout: _Resp(b"<html>" + b"x" * 5000))
    final, html = we.fetch_html("https://samirkapsalon.nl/", max_bytes=100)
    assert final == "https://samirkapsalon.nl/" and len(html) == 100


def test_non_html_rejected(monkeypatch):
    monkeypatch.setattr(socket, "getaddrinfo", _addr("93.184.216.34"))
    monkeypatch.setattr(we, "_open", lambda url, timeout: _Resp(b"%PDF", ctype="application/pdf"))
    with pytest.raises(ValueError, match="not HTML"):
        we.fetch_html("https://samirkapsalon.nl/menu.pdf")


def test_redirect_to_private_ip_rejected(monkeypatch):
    """_SafeRedirects re-validates the Location target."""
    import urllib.request

    seen = []

    def getaddrinfo(host, port, **kw):
        seen.append(host)
        ip = "10.0.0.5" if host == "internal.local" else "93.184.216.34"
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (ip, port))]

    monkeypatch.setattr(socket, "getaddrinfo", getaddrinfo)
    handler = we._SafeRedirects()
    req = urllib.request.Request("https://samirkapsalon.nl/")
    with pytest.raises(we.UnsafeUrl):
        handler.redirect_request(req, None, 302, "Found", {}, "http://internal.local/admin")
    assert "internal.local" in seen


def test_enrich_from_website_reports_error_instead_of_raising(monkeypatch):
    monkeypatch.setattr(socket, "getaddrinfo", _addr("93.184.216.34"))

    def boom(url, timeout):
        raise OSError("connection refused")

    monkeypatch.setattr(we, "_open", boom)
    out = we.enrich_from_website("https://samirkapsalon.nl/")
    assert out["fetched"] is False and "connection refused" in out["error"]
    assert out["social_links"] == {} and out["email"] is None


def test_enrich_from_website_happy(monkeypatch):
    monkeypatch.setattr(socket, "getaddrinfo", _addr("93.184.216.34"))
    monkeypatch.setattr(we, "_open", lambda url, timeout: _Resp(FIX.read_bytes()))
    out = we.enrich_from_website("https://samirkapsalon.nl/")
    assert out["fetched"] is True and out["error"] is None
    assert out["social_links"]["tiktok"] == "https://www.tiktok.com/@samirkapsalon"
    assert out["final_url"] == "https://samirkapsalon.nl/"
```

- [ ] **Step 3: Run to verify failure**

Run: `cd backend && venv/Scripts/python -m pytest auth_service/tests/test_google_places_website_enrich.py -q`
Expected: FAIL (`ModuleNotFoundError` or missing names).

- [ ] **Step 4: Implement `website_enrich.py`**

```python
"""Pull social links, an email and a meta description out of the business's own
website (ADR-0012). Places API never exposes social profiles, so this is the only
source. Fetch is SSRF-guarded (public IPs only, redirects re-checked), capped at 1 MB
and 8 s, and every failure is reported, never raised, from enrich_from_website()."""

from __future__ import annotations

import ipaddress
import json
import socket
import urllib.parse
import urllib.request
from html.parser import HTMLParser

USER_AGENT = "roman-technologies-cms-backend/1.0"

SOCIAL_HOSTS: dict[str, tuple[str, ...]] = {
    "facebook": ("facebook.com", "fb.com", "fb.me"),
    "instagram": ("instagram.com",),
    "tiktok": ("tiktok.com",),
    "linkedin": ("linkedin.com",),
    "youtube": ("youtube.com", "youtu.be"),
    "x": ("x.com", "twitter.com"),
    "pinterest": ("pinterest.com",),
    "whatsapp": ("wa.me", "api.whatsapp.com", "chat.whatsapp.com"),
}
# Path fragments that mean "share/post/intent", not a profile.
_NOT_PROFILE: dict[str, tuple[str, ...]] = {
    "facebook": ("/sharer", "/share", "/dialog/", "/plugins/", "/login", "/photo", "/posts/"),
    "instagram": ("/p/", "/reel/", "/reels/", "/explore/", "/accounts/", "/stories/"),
    "tiktok": ("/video/",),
    "linkedin": ("/share", "/sharearticle", "/feed/"),
    "youtube": ("/watch", "/embed/", "/shorts/", "/playlist"),
    "x": ("/intent/", "/share", "/status/"),
    "pinterest": ("/pin/",),
    "whatsapp": (),
}


def _host_of(url: str) -> tuple[urllib.parse.SplitResult | None, str]:
    try:
        p = urllib.parse.urlsplit(url.strip())
    except ValueError:
        return None, ""
    if p.scheme not in ("http", "https") or not p.hostname:
        return None, ""
    host = p.hostname.lower()
    for prefix in ("www.", "m.", "mobile."):
        host = host.removeprefix(prefix)
    return p, host


def _platform_for_host(host: str) -> str | None:
    for platform, hosts in SOCIAL_HOSTS.items():
        for h in hosts:
            # 'nl.linkedin.com', 'nl.pinterest.com', 'pinterest.nl' style variants
            if host == h or host.endswith("." + h) or (platform == "pinterest" and host.startswith("pinterest.")):
                return platform
    return None


def social_platform_of(url: str) -> str | None:
    """Platform key when `url` is a profile/page link on a known social host, else None."""
    p, host = _host_of(url)
    if p is None:
        return None
    platform = _platform_for_host(host)
    if platform is None:
        return None
    path = p.path.lower()
    if any(frag in path for frag in _NOT_PROFILE[platform]):
        return None
    if platform != "whatsapp" and path.strip("/") == "":
        return None  # bare homepage link, not the business's page
    return platform


def normalize_social_url(platform: str, url: str) -> str:
    p = urllib.parse.urlsplit(url.strip())
    netloc = (p.hostname or "").lower()
    path = p.path.rstrip("/")
    if platform == "whatsapp" and netloc in ("api.whatsapp.com", "chat.whatsapp.com"):
        q = urllib.parse.parse_qs(p.query)
        phone = (q.get("phone") or [""])[0]
        if phone:
            return f"https://wa.me/{phone.lstrip('+')}"
    return f"https://{netloc}{path}"


class UnsafeUrl(ValueError):
    pass


def assert_public_http_url(url: str) -> None:
    p, _ = _host_of(url)
    if p is None:
        raise UnsafeUrl("only http(s) URLs with a host are allowed")
    port = p.port or (443 if p.scheme == "https" else 80)
    try:
        infos = socket.getaddrinfo(p.hostname, port, proto=socket.IPPROTO_TCP)
    except socket.gaierror as e:
        raise UnsafeUrl(f"cannot resolve {p.hostname}") from e
    if not infos:
        raise UnsafeUrl(f"cannot resolve {p.hostname}")
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if (ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved
                or ip.is_multicast or ip.is_unspecified):
            raise UnsafeUrl(f"{p.hostname} resolves to a non-public address")


class _SafeRedirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        assert_public_http_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _open(url: str, timeout: int):
    """Single seam for tests."""
    opener = urllib.request.build_opener(_SafeRedirects())
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "text/html,*/*;q=0.5"})
    return opener.open(req, timeout=timeout)


def fetch_html(url: str, *, timeout: int = 8, max_bytes: int = 1_000_000) -> tuple[str, str]:
    assert_public_http_url(url)
    with _open(url, timeout) as resp:
        ctype = (resp.headers.get("Content-Type") or "").lower()
        if "html" not in ctype:
            raise ValueError(f"not HTML ({ctype.split(';')[0] or 'no content-type'})")
        raw = resp.read(max_bytes)
        final = resp.geturl() or url
        charset = resp.headers.get_content_charset() or "utf-8"
    return final, raw.decode(charset, errors="replace")


class _Collector(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.hrefs: list[str] = []
        self.meta: dict[str, str] = {}
        self.lang: str | None = None
        self.jsonld: list[str] = []
        self._in_jsonld = False

    def handle_starttag(self, tag, attrs):
        a = {k: (v or "") for k, v in attrs}
        if tag == "a" and a.get("href"):
            self.hrefs.append(a["href"].strip())
        elif tag == "meta":
            key = (a.get("name") or a.get("property") or "").lower()
            if key in ("description", "og:description") and a.get("content", "").strip():
                self.meta.setdefault(key, a["content"].strip())
        elif tag == "html" and a.get("lang"):
            self.lang = a["lang"].strip()[:10] or None
        elif tag == "script" and (a.get("type") or "").lower() == "application/ld+json":
            self._in_jsonld = True

    def handle_endtag(self, tag):
        if tag == "script":
            self._in_jsonld = False

    def handle_data(self, data):
        if self._in_jsonld:
            self.jsonld.append(data)


def _same_as(blobs: list[str]) -> list[str]:
    found: list[str] = []

    def walk(node):
        if isinstance(node, dict):
            same = node.get("sameAs")
            if isinstance(same, str):
                found.append(same)
            elif isinstance(same, list):
                found.extend(s for s in same if isinstance(s, str))
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)

    for blob in blobs:
        try:
            walk(json.loads(blob))
        except ValueError:
            continue
    return found


def extract(html: str) -> dict:
    c = _Collector()
    c.feed(html)
    social: dict[str, str] = {}
    email: str | None = None
    for href in c.hrefs + _same_as(c.jsonld):
        if href.lower().startswith("mailto:"):
            if email is None:
                addr = href[7:].split("?", 1)[0].strip()
                if "@" in addr:
                    email = addr
            continue
        platform = social_platform_of(href)
        if platform and platform not in social:
            social[platform] = normalize_social_url(platform, href)
    description = c.meta.get("description") or c.meta.get("og:description")
    return {"social_links": social, "email": email, "description": description, "lang": c.lang}


def enrich_from_website(url: str) -> dict:
    out = {"fetched": False, "final_url": None, "social_links": {}, "email": None,
           "description": None, "lang": None, "error": None}
    try:
        final, html = fetch_html(url)
    except Exception as e:  # noqa: BLE001 — any failure is a warning, never an import failure
        out["error"] = f"{type(e).__name__}: {e}"[:300]
        return out
    out.update(extract(html))
    out["fetched"] = True
    out["final_url"] = final
    return out
```

- [ ] **Step 5: Run tests (this task + the mapper)**

Run: `cd backend && venv/Scripts/python -m pytest auth_service/tests/test_google_places_website_enrich.py auth_service/tests/test_google_places_mapper.py -q`
Expected: PASS.

- [ ] **Step 6: Lint, commit**

```bash
cd backend && venv/Scripts/python -m ruff check . && venv/Scripts/python -m black --check .
git add backend/auth_service/services/google_places/website_enrich.py backend/auth_service/tests/fixtures/website_sample.html backend/auth_service/tests/test_google_places_website_enrich.py
git commit -m "feat(leads): extract social links and email from the business website"
```

---

### Task 6: Photo download into Storage

**Files:**
- Create: `backend/auth_service/services/google_places/photos.py`
- Test: `backend/auth_service/tests/test_google_places_photos.py`

**Interfaces:**
- Consumes: `client.photo_uri`, `client.fetch_bytes`, `client.GooglePlacesError`; `mapper.normalize_name`.
- Produces: `BUCKET = "lead-photos"`; `is_owner_photo(business_name: str, attributions: list[dict]) -> bool`; `storage_path_of(url: str) -> str | None`; `download_photos(sb, lead_id: str, business_name: str, photos: list[dict], *, max_photos: int, max_width_px: int = 1600) -> tuple[list[str], list[dict], list[str]]` returning `(public_urls, photo_meta, warnings)` where each `photo_meta` item is the mapper photo dict plus `storage_path`, `url`, `owner_photo`; `delete_lead_photos(sb, lead_id: str, urls: list[str] | None = None) -> list[str]` (removes the given lead-photos URLs, or everything under `<lead_id>/` when `urls is None`; returns removed paths).

- [ ] **Step 1: Write the failing tests**

```python
from unittest.mock import MagicMock

from auth_service.services.google_places import client, photos

PUBLIC = "https://x.supabase.co/storage/v1/object/public/lead-photos/"


def _photo(n, author="Samir Kapsalon"):
    return {"name": f"places/P/photos/{n}", "width_px": 100, "height_px": 100,
            "attributions": [{"name": author, "uri": None, "photo_uri": None}], "google_maps_uri": f"https://g/{n}"}


def _sb():
    sb = MagicMock()
    store = sb.storage.from_.return_value
    store.get_public_url.side_effect = lambda path: PUBLIC + path
    return sb, store


def test_is_owner_photo():
    assert photos.is_owner_photo("Samir  Kapsalon", [{"name": "samir kapsalon"}])
    assert not photos.is_owner_photo("Samir Kapsalon", [{"name": "Jan"}])
    assert not photos.is_owner_photo("Samir Kapsalon", [])


def test_storage_path_of():
    assert photos.storage_path_of(PUBLIC + "lead-1/00-abc.jpg") == "lead-1/00-abc.jpg"
    assert photos.storage_path_of(PUBLIC + "lead-1/00-abc.jpg?v=1") == "lead-1/00-abc.jpg"
    assert photos.storage_path_of("https://x.supabase.co/storage/v1/object/public/cms-files/a.jpg") is None


def test_download_photos_uploads_and_flags_owner(monkeypatch):
    sb, store = _sb()
    monkeypatch.setattr(client, "photo_uri", lambda name, max_width_px=1600: f"https://lh3/{name[-2:]}")
    monkeypatch.setattr(client, "fetch_bytes", lambda url, max_bytes=8_000_000, timeout=15: (b"JPEGDATA" + url.encode(), "image/jpeg"))
    urls, meta, warnings = photos.download_photos(sb, "lead-1", "Samir Kapsalon",
                                                  [_photo("p1"), _photo("p2", author="Jan")], max_photos=10)
    assert warnings == []
    assert len(urls) == 2 and all(u.startswith(PUBLIC + "lead-1/") for u in urls)
    assert urls[0].endswith(".jpg") and urls[0].split("/")[-1].startswith("00-")
    assert meta[0]["owner_photo"] is True and meta[1]["owner_photo"] is False
    assert meta[0]["url"] == urls[0] and meta[0]["storage_path"].startswith("lead-1/00-")
    assert store.upload.call_count == 2
    kwargs = store.upload.call_args_list[0].kwargs
    assert kwargs["file_options"]["content-type"] == "image/jpeg"


def test_download_photos_respects_max(monkeypatch):
    sb, store = _sb()
    monkeypatch.setattr(client, "photo_uri", lambda name, max_width_px=1600: "https://lh3/x")
    monkeypatch.setattr(client, "fetch_bytes", lambda url, **k: (b"PNG", "image/png"))
    urls, meta, _ = photos.download_photos(sb, "l", "B", [_photo(str(i)) for i in range(5)], max_photos=2)
    assert len(urls) == 2 and urls[0].endswith(".png")


def test_download_photos_continues_after_failure(monkeypatch):
    sb, store = _sb()

    def uri(name, max_width_px=1600):
        if name.endswith("p2"):
            raise client.GooglePlacesError(404, "expired")
        return "https://lh3/ok"

    monkeypatch.setattr(client, "photo_uri", uri)
    monkeypatch.setattr(client, "fetch_bytes", lambda url, **k: (b"JPG", "image/jpeg"))
    urls, meta, warnings = photos.download_photos(sb, "l", "B", [_photo("p1"), _photo("p2"), _photo("p3")], max_photos=10)
    assert len(urls) == 2 and len(set(urls)) == 2 and len(meta) == 2
    assert len(warnings) == 1 and "p2" in warnings[0]


def test_download_photos_skips_unknown_content_type(monkeypatch):
    sb, store = _sb()
    monkeypatch.setattr(client, "photo_uri", lambda name, max_width_px=1600: "https://lh3/x")
    monkeypatch.setattr(client, "fetch_bytes", lambda url, **k: (b"<html>", "text/html"))
    urls, meta, warnings = photos.download_photos(sb, "l", "B", [_photo("p1")], max_photos=10)
    assert urls == [] and len(warnings) == 1 and store.upload.call_count == 0


def test_delete_lead_photos_specific_urls():
    sb, store = _sb()
    removed = photos.delete_lead_photos(sb, "lead-1", [PUBLIC + "lead-1/00-a.jpg", "https://elsewhere/x.jpg"])
    assert removed == ["lead-1/00-a.jpg"]
    store.remove.assert_called_once_with(["lead-1/00-a.jpg"])


def test_delete_lead_photos_all_under_prefix():
    sb, store = _sb()
    store.list.return_value = [{"name": "00-a.jpg", "id": "1"}, {"name": "01-b.jpg", "id": "2"}]
    removed = photos.delete_lead_photos(sb, "lead-1")
    assert removed == ["lead-1/00-a.jpg", "lead-1/01-b.jpg"]
    store.list.assert_called_once_with("lead-1", {"limit": 1000})
```

- [ ] **Step 2: Run to verify failure**

Run: `cd backend && venv/Scripts/python -m pytest auth_service/tests/test_google_places_photos.py -q`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Implement `photos.py`**

```python
"""Copy a listing's photos into the public `lead-photos` bucket (ADR-0012).

Photo resource names expire, so the image bytes are fetched now and the name is kept
only as provenance. Each photo keeps its author attribution; `owner_photo` marks the
ones the business itself uploaded (attribution name == business name)."""

from __future__ import annotations

import hashlib
import logging
import urllib.parse

from . import client
from .mapper import normalize_name

logger = logging.getLogger(__name__)

BUCKET = "lead-photos"
_EXT = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}
_PUBLIC_MARKER = f"/storage/v1/object/public/{BUCKET}/"


def is_owner_photo(business_name: str, attributions: list[dict]) -> bool:
    target = normalize_name(business_name)
    return any(normalize_name(a.get("name") or "") == target for a in attributions if a.get("name"))


def storage_path_of(url: str) -> str | None:
    """'…/object/public/lead-photos/<path>' -> '<path>' (query stripped), else None."""
    path = urllib.parse.urlsplit(url).path
    if _PUBLIC_MARKER not in path:
        return None
    return urllib.parse.unquote(path.split(_PUBLIC_MARKER, 1)[1]) or None


def download_photos(
    sb,
    lead_id: str,
    business_name: str,
    photos: list[dict],
    *,
    max_photos: int,
    max_width_px: int = 1600,
) -> tuple[list[str], list[dict], list[str]]:
    store = sb.storage.from_(BUCKET)
    urls: list[str] = []
    meta: list[dict] = []
    warnings: list[str] = []
    for index, photo in enumerate(photos[: max(0, max_photos)]):
        name = photo.get("name") or ""
        try:
            uri = client.photo_uri(name, max_width_px=max_width_px)
            body, ctype = client.fetch_bytes(uri)
        except client.GooglePlacesError as e:
            warnings.append(f"photo {name} skipped: {e.message}")
            continue
        ext = _EXT.get(ctype)
        if ext is None:
            warnings.append(f"photo {name} skipped: unsupported content type {ctype or 'unknown'}")
            continue
        digest = hashlib.sha1(body).hexdigest()[:10]
        path = f"{lead_id}/{index:02d}-{digest}{ext}"
        try:
            store.upload(path=path, file=body, file_options={"content-type": ctype, "upsert": "true"})
        except Exception as e:  # noqa: BLE001 — storage hiccup must not fail the import
            logger.exception("lead photo upload failed (%s)", path)
            warnings.append(f"photo {name} skipped: upload failed ({type(e).__name__})")
            continue
        url = store.get_public_url(path)
        urls.append(url)
        meta.append({**photo, "storage_path": path, "url": url,
                     "owner_photo": is_owner_photo(business_name, photo.get("attributions") or [])})
    return urls, meta, warnings


def delete_lead_photos(sb, lead_id: str, urls: list[str] | None = None) -> list[str]:
    store = sb.storage.from_(BUCKET)
    if urls is None:
        paths = [f"{lead_id}/{f['name']}" for f in (store.list(lead_id, {"limit": 1000}) or []) if f.get("id")]
    else:
        paths = [p for p in (storage_path_of(u) for u in urls) if p and p.startswith(f"{lead_id}/")]
    if paths:
        store.remove(paths)
    return paths
```

- [ ] **Step 4: Run tests**

Run: `cd backend && venv/Scripts/python -m pytest auth_service/tests/test_google_places_photos.py -q`
Expected: PASS (8 tests).

- [ ] **Step 5: Lint, commit**

```bash
cd backend && venv/Scripts/python -m ruff check . && venv/Scripts/python -m black --check .
git add backend/auth_service/services/google_places/photos.py backend/auth_service/tests/test_google_places_photos.py
git commit -m "feat(leads): download listing photos into lead-photos storage"
```

---

### Task 7: Importer orchestration + the two endpoints

**Files:**
- Create: `backend/auth_service/services/google_places/importer.py`
- Modify: `backend/auth_service/routers/admin_leads.py` (imports at `:6-15`; new routes between `create_lead` `:93-114` and `get_lead` `:117`)
- Modify: `backend/auth_service/tests/conftest.py:75-87` (add `"auth_service.core.pg_rate_limit.get_supabase_admin"` to `targets` so the limiter never reaches the real DB in tests)
- Test: `backend/auth_service/tests/test_google_places_importer.py`, `backend/auth_service/tests/test_admin_leads_google_import.py`

**Interfaces:**
- Consumes: `resolve.resolve`, `client.place_details`, `mapper.map_place`, `website_enrich.enrich_from_website`, `photos.download_photos`, `photos.delete_lead_photos`, `pg_rate_limit.allow/over_limit/enforce`, `settings.GOOGLE_PLACES_*`.
- Produces: `class DuplicateLead(Exception)` with `.lead_id`; `class MonthlyCapReached(Exception)`; `@dataclass ImportOutcome(lead: dict | None, candidates: list[dict], warnings: list[str])`; `GOOGLE_FIELDS: frozenset[str]`; `ALWAYS_REFRESH: frozenset[str]`; `build_row(mapped, enrichment, *, place_id, language, now_iso) -> dict` (pure); `merge_fill_empty(current: dict, incoming: dict) -> dict` (pure); `import_place(sb, *, raw_input: str, lead_type: str, language: str) -> ImportOutcome`; `reimport_place(sb, current: dict, *, raw_input: str | None, overwrite: bool, language: str) -> ImportOutcome`.
- Endpoints: `POST /admin/leads/google-import` → `201 LeadOut` | `200 {"status":"candidates","candidates":[…],"warnings":[]}` | `404` (unresolvable, no candidates) | `409 {"detail": {"message": "...", "lead_id": "..."}}` | `429` | `503`; `POST /admin/leads/{lead_id}/google-import` → `200 LeadOut` | `200 candidates` | `404` | `422` (no input and no stored place id) | `429` | `503`. Google failures: 400→422, 401/403→502, 404→404, 429→503, other→502, 504→504.

- [ ] **Step 1: Write the failing importer tests**

```python
from unittest.mock import MagicMock

import pytest

from auth_service.core.config import settings
from auth_service.services.google_places import importer, mapper, resolve
from auth_service.services.google_places.client import GooglePlacesError

PLACE = {"id": "ChIJx", "displayName": {"text": "Acme Barber"}, "websiteUri": "https://acme.nl/",
         "rating": 4.5, "userRatingCount": 10, "businessStatus": "OPERATIONAL",
         "photos": [{"name": "places/ChIJx/photos/a", "authorAttributions": []}]}


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.setattr(settings, "GOOGLE_MAPS_API_KEY", "k")
    monkeypatch.setattr(settings, "GOOGLE_PLACES_MAX_PHOTOS", 10)
    monkeypatch.setattr(importer, "over_limit", lambda *a, **k: False)
    monkeypatch.setattr(importer, "allow", lambda *a, **k: True)
    # "ChIJx" is shorter than a real place ID, so bypass the resolver by default;
    # tests that exercise resolution override this.
    monkeypatch.setattr(importer, "resolve", lambda raw, language="en": resolve.Resolution(raw))
    monkeypatch.setattr(importer, "delete_lead_photos", lambda sb, lead_id, urls=None: [])
    monkeypatch.setattr(importer.client, "place_details", lambda pid, language="en": PLACE)
    monkeypatch.setattr(importer, "enrich_from_website", lambda url: {
        "fetched": True, "final_url": url, "social_links": {"instagram": "https://instagram.com/acme"},
        "email": "hi@acme.nl", "description": "Acme desc", "lang": "nl", "error": None})
    monkeypatch.setattr(importer, "download_photos", lambda sb, lead_id, name, ph, max_photos, **k: (
        [f"https://x/lead-photos/{lead_id}/00-a.jpg"], [{"name": "places/ChIJx/photos/a", "url": "u", "owner_photo": False}], []))


def _sb(execute_results):
    sb = MagicMock()
    for m in ["table", "select", "eq", "maybe_single", "insert", "update"]:
        getattr(sb, m).return_value = sb
    sb.execute.side_effect = execute_results
    return sb


def test_build_row_merges_enrichment():
    m = mapper.map_place(PLACE)
    row = importer.build_row(m, {"fetched": True, "social_links": {"instagram": "https://instagram.com/acme", "facebook": "https://facebook.com/acme"},
                                 "email": "hi@acme.nl", "description": "D", "lang": "nl", "error": None, "final_url": "https://acme.nl/"},
                             place_id="ChIJx", language="en", now_iso="2026-10-11T00:00:00+00:00")
    assert row["google_place_id"] == "ChIJx" and row["google_imported_at"] == "2026-10-11T00:00:00+00:00"
    assert row["external_id"] == "google:ChIJx" and row["primary_source"] == "google_maps"
    assert row["social_links"] == {"instagram": "https://instagram.com/acme", "facebook": "https://facebook.com/acme"}
    assert row["facebook_url"] == "https://facebook.com/acme" and row["instagram_url"] == "https://instagram.com/acme"
    assert row["email"] == "hi@acme.nl" and row["description"] == "D"
    assert row["extra"]["google"]["website"]["lang"] == "nl"
    assert row["extra"]["attributes"] == {}
    assert "photo_urls" not in row  # photos are added after insert


def test_build_row_without_enrichment():
    row = importer.build_row(mapper.map_place(PLACE), None, place_id="ChIJx", language="en", now_iso="t")
    assert row["social_links"] == {} and row["email"] is None
    assert row["extra"]["google"]["website"] is None


def test_merge_fill_empty():
    current = {"phone": "+31", "email": None, "about": "", "types": [], "social_links": {}, "rating": 4.0,
               "extra": {"attributes": {"A": {"x": True}}, "google": {"old": 1}, "other": 1}, "notes": "keep"}
    incoming = {"phone": "+32", "email": "a@b.c", "about": "New", "types": ["t"], "social_links": {"x": "https://x.com/a"},
                "rating": 4.5, "extra": {"attributes": {"B": {"y": True}}, "google": {"new": 2}}, "google_imported_at": "t"}
    out = importer.merge_fill_empty(current, incoming)
    assert out["phone"] == "+31"            # kept: non-empty
    assert out["email"] == "a@b.c"          # filled
    assert out["about"] == "New" and out["types"] == ["t"] and out["social_links"] == {"x": "https://x.com/a"}
    assert out["rating"] == 4.5             # ALWAYS_REFRESH
    assert out["extra"] == {"attributes": {"A": {"x": True}}, "google": {"new": 2}, "other": 1}
    assert "notes" not in out


def test_import_place_creates_lead():
    sb = _sb([
        MagicMock(data=None),                                   # duplicate pre-check
        MagicMock(data=[{"id": "lead-9", "business_name": "Acme Barber", "extra": {"attributes": {}, "google": {}}}]),  # insert
        MagicMock(data=[{"id": "lead-9", "photo_urls": ["https://x/lead-photos/lead-9/00-a.jpg"]}]),  # photo update
    ])
    out = importer.import_place(sb, raw_input="ChIJx", lead_type="both", language="en")
    assert out.lead["id"] == "lead-9" and out.candidates == []
    inserted = sb.insert.call_args.args[0]
    assert inserted["lead_type"] == "both" and inserted["google_place_id"] == "ChIJx"
    assert inserted["web_presence"] == "has_website"
    updated = sb.update.call_args.args[0]
    assert updated["photo_urls"] == ["https://x/lead-photos/lead-9/00-a.jpg"]
    assert updated["extra"]["google"]["photos"][0]["name"] == "places/ChIJx/photos/a"


def test_import_returns_candidates(monkeypatch):
    monkeypatch.setattr(importer, "resolve", lambda raw, language="en": resolve.Resolution(None, [{"place_id": "a", "name": "A", "address": None}]))
    out = importer.import_place(_sb([]), raw_input="https://maps.app.goo.gl/x", lead_type="website", language="en")
    assert out.lead is None and out.candidates[0]["place_id"] == "a"


def test_import_duplicate_409():
    sb = _sb([MagicMock(data={"id": "lead-1"})])
    with pytest.raises(importer.DuplicateLead) as ei:
        importer.import_place(sb, raw_input="ChIJx", lead_type="website", language="en")
    assert ei.value.lead_id == "lead-1"


def test_import_monthly_cap(monkeypatch):
    monkeypatch.setattr(importer, "allow", lambda *a, **k: False)
    with pytest.raises(importer.MonthlyCapReached):
        importer.import_place(_sb([MagicMock(data=None)]), raw_input="ChIJx", lead_type="website", language="en")


def test_import_skips_enrichment_without_website(monkeypatch):
    monkeypatch.setattr(importer.client, "place_details", lambda pid, language="en": {"id": "ChIJx", "displayName": {"text": "Mobile"}})
    monkeypatch.setattr(importer, "enrich_from_website", lambda url: pytest.fail("must not fetch"))
    sb = _sb([MagicMock(data=None), MagicMock(data=[{"id": "l", "extra": {}}]), MagicMock(data=[{"id": "l"}])])
    out = importer.import_place(sb, raw_input="ChIJx", lead_type="website", language="en")
    assert sb.insert.call_args.args[0]["web_presence"] == "none" and out.lead["id"] == "l"


def test_import_survives_enrichment_failure(monkeypatch):
    monkeypatch.setattr(importer, "enrich_from_website", lambda url: {
        "fetched": False, "final_url": None, "social_links": {}, "email": None, "description": None, "lang": None, "error": "OSError: refused"})
    sb = _sb([MagicMock(data=None), MagicMock(data=[{"id": "l", "extra": {}}]), MagicMock(data=[{"id": "l"}])])
    out = importer.import_place(sb, raw_input="ChIJx", lead_type="website", language="en")
    assert out.lead is not None and any("refused" in w for w in out.warnings)


def test_import_google_error_propagates(monkeypatch):
    def boom(pid, language="en"):
        raise GooglePlacesError(404, "not found")

    monkeypatch.setattr(importer.client, "place_details", boom)
    with pytest.raises(GooglePlacesError):
        importer.import_place(_sb([MagicMock(data=None)]), raw_input="ChIJx", lead_type="website", language="en")


def test_reimport_fill_empty_keeps_existing(monkeypatch):
    current = {"id": "lead-1", "google_place_id": "ChIJx", "business_name": "Old Name", "phone": "+31", "email": None,
               "photo_urls": ["old"], "extra": {"attributes": {"A": {"x": True}}, "google": {}}, "notes": "n", "social_links": {}}
    sb = _sb([MagicMock(data=[{"id": "lead-1", "business_name": "Old Name"}])])
    out = importer.reimport_place(sb, current, raw_input=None, overwrite=False, language="en")
    patch = sb.update.call_args.args[0]
    assert "business_name" not in patch       # kept: non-empty on the current row
    assert patch["email"] == "hi@acme.nl" and patch["rating"] == 4.5
    assert "notes" not in patch and "lead_type" not in patch
    assert patch["photo_urls"] == ["old"]        # existing photos kept in fill-empty mode
    assert out.lead["id"] == "lead-1"


def test_reimport_overwrite_replaces_and_redownloads(monkeypatch):
    deleted = []
    monkeypatch.setattr(importer, "delete_lead_photos", lambda sb, lead_id, urls=None: deleted.append(lead_id) or [])
    current = {"id": "lead-1", "google_place_id": "ChIJx", "business_name": "Old Name", "phone": "+31",
               "photo_urls": ["old"], "extra": {"attributes": {}, "google": {}}, "social_links": {}}
    sb = _sb([MagicMock(data=[{"id": "lead-1"}])])
    importer.reimport_place(sb, current, raw_input=None, overwrite=True, language="en")
    patch = sb.update.call_args.args[0]
    assert patch["business_name"] == "Acme Barber" and deleted == ["lead-1"]
    assert patch["photo_urls"] == ["https://x/lead-photos/lead-1/00-a.jpg"]


def test_reimport_requires_input_or_place_id():
    with pytest.raises(ValueError):
        importer.reimport_place(_sb([]), {"id": "l", "google_place_id": None}, raw_input=None, overwrite=False, language="en")


def test_reimport_with_new_input_changes_place(monkeypatch):
    seen = {}
    monkeypatch.setattr(importer, "resolve", lambda raw, language="en": seen.update(raw=raw) or resolve.Resolution("ChIJnew"))
    sb = _sb([MagicMock(data=None), MagicMock(data=[{"id": "l"}])])
    importer.reimport_place(sb, {"id": "l", "google_place_id": "ChIJold", "extra": {}, "photo_urls": [], "social_links": {}},
                            raw_input="https://maps.app.goo.gl/n", overwrite=True, language="en")
    assert seen["raw"].endswith("/n") and sb.update.call_args.args[0]["google_place_id"] == "ChIJnew"
```

- [ ] **Step 2: Run to verify failure**

Run: `cd backend && venv/Scripts/python -m pytest auth_service/tests/test_google_places_importer.py -q`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Implement `importer.py`**

```python
"""Orchestrates one import: resolve -> details -> map -> enrich -> insert -> photos
(ADR-0012). Everything Google-sourced is listed in GOOGLE_FIELDS so a re-import can
fill gaps or overwrite without ever touching pipeline fields."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime

from ...core.config import settings
from ...core.pg_rate_limit import allow, over_limit
from . import client
from .mapper import MappedPlace, map_place
from .photos import delete_lead_photos, download_photos
from .resolve import resolve
from .website_enrich import enrich_from_website

logger = logging.getLogger(__name__)

MONTH_BUCKET = "google_import:month"
MONTH_WINDOW = 31 * 86400

GOOGLE_FIELDS = frozenset(
    {
        "business_name", "name_normalized", "category", "description", "about", "country", "region",
        "city", "address", "postal_code", "lat", "lng", "phone", "email", "website_url",
        "facebook_url", "instagram_url", "social_links", "web_presence", "rating", "review_count",
        "reviews", "opening_hours", "photo_urls", "business_status", "primary_type", "types",
        "price_level", "source_url", "google_place_id", "google_imported_at", "extra",
    }
)
ALWAYS_REFRESH = frozenset({"rating", "review_count", "business_status", "google_imported_at", "google_place_id"})


class DuplicateLead(Exception):
    def __init__(self, lead_id: str):
        super().__init__(lead_id)
        self.lead_id = lead_id


class MonthlyCapReached(Exception):
    pass


@dataclass
class ImportOutcome:
    lead: dict | None
    candidates: list[dict] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def _empty(v) -> bool:
    return v is None or v == "" or v == [] or v == {}


def build_row(mapped: MappedPlace, enrichment: dict | None, *, place_id: str, language: str, now_iso: str) -> dict:
    row = dict(mapped.columns)
    social: dict[str, str] = {}
    if row.get("facebook_url"):
        social["facebook"] = row["facebook_url"]
    if row.get("instagram_url"):
        social["instagram"] = row["instagram_url"]
    row["email"] = None
    if enrichment and enrichment.get("fetched"):
        for platform, url in (enrichment.get("social_links") or {}).items():
            social.setdefault(platform, url)
        row["email"] = enrichment.get("email")
        if enrichment.get("description"):
            row["description"] = enrichment["description"]
    row.setdefault("description", None)
    row["social_links"] = social
    row["facebook_url"] = social.get("facebook")
    row["instagram_url"] = social.get("instagram")
    row["google_place_id"] = place_id
    row["google_imported_at"] = now_iso
    row["external_id"] = f"google:{place_id}"
    row["primary_source"] = "google_maps"
    row["extra"] = {
        "attributes": mapped.attributes,
        "google": {**mapped.google, "place_id": place_id, "language": language, "imported_at": now_iso,
                   "photos": [], "website": enrichment},
    }
    return row


def merge_fill_empty(current: dict, incoming: dict) -> dict:
    """Patch = incoming values for Google fields that are empty on `current`, plus
    ALWAYS_REFRESH fields. `extra` keeps current keys and replaces only `google`."""
    patch: dict = {}
    for key, value in incoming.items():
        if key not in GOOGLE_FIELDS or key == "extra":
            continue
        if key in ALWAYS_REFRESH or _empty(current.get(key)):
            patch[key] = value
    cur_extra = dict(current.get("extra") or {})
    inc_extra = incoming.get("extra") or {}
    cur_extra["google"] = inc_extra.get("google", {})
    if _empty(cur_extra.get("attributes")):
        cur_extra["attributes"] = inc_extra.get("attributes", {})
    patch["extra"] = cur_extra
    return patch


def _fetch_and_map(place_id: str, language: str) -> tuple[dict, list[str]]:
    """Details + enrichment -> (row without photos, warnings). Counts the monthly hit."""
    if not allow(MONTH_BUCKET, settings.GOOGLE_PLACES_MONTHLY_CAP, MONTH_WINDOW):
        raise MonthlyCapReached()
    place = client.place_details(place_id, language=language)
    mapped = map_place(place, language=language)
    warnings: list[str] = []
    enrichment = None
    if mapped.website_uri and mapped.columns.get("web_presence") == "has_website":
        enrichment = enrich_from_website(mapped.website_uri)
        if enrichment.get("error"):
            warnings.append(f"website enrichment skipped: {enrichment['error']}")
    row = build_row(mapped, enrichment, place_id=place_id, language=language,
                    now_iso=datetime.now(UTC).isoformat())
    row["_photos"] = mapped.photos
    return row, warnings


def _attach_photos(sb, lead_id: str, row: dict, extra: dict) -> tuple[dict, list[str]]:
    urls, meta, warnings = download_photos(
        sb, lead_id, row["business_name"], row.pop("_photos", []),
        max_photos=settings.GOOGLE_PLACES_MAX_PHOTOS,
    )
    google = dict(extra.get("google") or {})
    google["photos"] = meta
    extra = {**extra, "google": google}
    return {"photo_urls": urls, "extra": extra}, warnings


def _find_duplicate(sb, place_id: str) -> str | None:
    res = sb.table("leads").select("id").eq("google_place_id", place_id).maybe_single().execute()
    return (res.data or {}).get("id") if res.data else None


def import_place(sb, *, raw_input: str, lead_type: str, language: str) -> ImportOutcome:
    if over_limit(MONTH_BUCKET, settings.GOOGLE_PLACES_MONTHLY_CAP, MONTH_WINDOW):
        raise MonthlyCapReached()
    resolution = resolve(raw_input, language=language)
    if resolution.place_id is None:
        return ImportOutcome(None, resolution.candidates)
    place_id = resolution.place_id
    existing = _find_duplicate(sb, place_id)
    if existing:
        raise DuplicateLead(existing)

    row, warnings = _fetch_and_map(place_id, language)
    photos = row.pop("_photos")
    row["lead_type"] = lead_type
    try:
        res = sb.table("leads").insert(row).execute()
    except Exception as e:  # noqa: BLE001 — unique violation raced the pre-check
        if "23505" in str(e) or "duplicate" in str(e).lower():
            raise DuplicateLead(_find_duplicate(sb, place_id) or "") from e
        raise
    if not res.data:
        raise RuntimeError("Insert failed")
    lead = res.data[0]
    row["_photos"] = photos
    photo_patch, photo_warnings = _attach_photos(sb, lead["id"], row, row["extra"])
    upd = sb.table("leads").update(photo_patch).eq("id", lead["id"]).execute()
    lead = (upd.data or [lead])[0]
    return ImportOutcome(lead, [], warnings + photo_warnings)


def reimport_place(sb, current: dict, *, raw_input: str | None, overwrite: bool, language: str) -> ImportOutcome:
    if raw_input:
        resolution = resolve(raw_input, language=language)
        if resolution.place_id is None:
            return ImportOutcome(None, resolution.candidates)
        place_id = resolution.place_id
        if place_id != current.get("google_place_id"):
            other = _find_duplicate(sb, place_id)
            if other and other != current["id"]:
                raise DuplicateLead(other)
    elif current.get("google_place_id"):
        place_id = current["google_place_id"]
    else:
        raise ValueError("This lead has no Google place ID; paste a Google Maps link to import.")

    row, warnings = _fetch_and_map(place_id, language)
    if overwrite:
        delete_lead_photos(sb, current["id"])
        photo_patch, photo_warnings = _attach_photos(sb, current["id"], row, row["extra"])
        patch = {k: v for k, v in row.items() if k in GOOGLE_FIELDS}
        patch.update(photo_patch)
        # keep non-Google keys of extra (e.g. legacy scraper data)
        patch["extra"] = {**(current.get("extra") or {}), **patch["extra"]}
    else:
        row.pop("_photos")
        patch = merge_fill_empty(current, row)
        patch["photo_urls"] = list(current.get("photo_urls") or [])
        google = dict(patch["extra"].get("google") or {})
        google["photos"] = list(((current.get("extra") or {}).get("google") or {}).get("photos") or [])
        patch["extra"]["google"] = google
        photo_warnings = []
    patch.pop("external_id", None)
    patch.pop("primary_source", None)
    res = sb.table("leads").update(patch).eq("id", current["id"]).execute()
    if not res.data:
        raise RuntimeError("Update failed")
    return ImportOutcome(res.data[0], [], warnings + photo_warnings)
```

Note for the fill-empty path: photos are **not** downloaded (existing ones kept) — the photo quota is the tightest one, and `overwrite=true` is the explicit way to refresh them.

- [ ] **Step 4: Run importer tests**

Run: `cd backend && venv/Scripts/python -m pytest auth_service/tests/test_google_places_importer.py -q`
Expected: PASS (14 tests).

- [ ] **Step 5: Write the failing router tests** in `test_admin_leads_google_import.py`

```python
from unittest.mock import MagicMock

import pytest

from auth_service.core.config import settings
from auth_service.routers import admin_leads
from auth_service.services.google_places.client import GooglePlacesError
from auth_service.services.google_places.importer import DuplicateLead, ImportOutcome, MonthlyCapReached


def _lead(**over):
    base = {
        "id": "lead-1", "external_id": "google:ChIJx", "primary_source": "google_maps",
        "lead_type": "website", "business_name": "Acme", "name_normalized": "acme",
        "web_presence": "has_website", "website_build_status": "not_started",
        "ai_workflow_status": "not_started", "lead_status": "not_sent",
        "lead_contact_type": "not_contacted", "payment_status": "not_applicable",
        "extra": {}, "photo_urls": [], "google_place_id": "ChIJx",
        "created_at": "2026-10-11T10:00:00Z", "updated_at": "2026-10-11T10:00:00Z",
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
    r = client.post("/admin/leads/google-import", json={"input": " https://maps.app.goo.gl/a ", "lead_type": "both", "language": "nl"})
    assert r.status_code == 201
    assert r.json()["google_place_id"] == "ChIJx"
    assert r.headers["x-import-warnings"] == "1"
    assert seen == {"raw_input": "https://maps.app.goo.gl/a", "lead_type": "both", "language": "nl"}


def test_import_candidates(mock_supabase, client, auth_as, admin_user, monkeypatch):
    auth_as(admin_user)
    monkeypatch.setattr(admin_leads, "import_place", lambda sb, **k: ImportOutcome(None, [{"place_id": "a", "name": "A", "address": None}]))
    r = client.post("/admin/leads/google-import", json={"input": "Kapsalon"})
    assert r.status_code == 200
    assert r.json() == {"status": "candidates", "candidates": [{"place_id": "a", "name": "A", "address": None}], "warnings": []}


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


def test_import_per_user_limit_429(mock_supabase, client, auth_as, admin_user, monkeypatch):
    auth_as(admin_user)
    from fastapi import HTTPException

    def limited(bucket, limit, window, detail="x"):
        assert bucket == "google_import:user:admin-uuid" and (limit, window) == (20, 3600)
        raise HTTPException(status_code=429, detail=detail)

    monkeypatch.setattr(admin_leads, "enforce", limited)
    assert client.post("/admin/leads/google-import", json={"input": "ChIJx"}).status_code == 429


@pytest.mark.parametrize("gstatus,expected", [(400, 422), (403, 502), (404, 404), (429, 503), (500, 502), (504, 504)])
def test_import_google_errors(mock_supabase, client, auth_as, admin_user, monkeypatch, gstatus, expected):
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
    mock_supabase.execute.return_value = MagicMock(data=None)
    assert client.post("/admin/leads/nope/google-import", json={}).status_code == 404


def test_reimport_422_without_place(mock_supabase, client, auth_as, admin_user, monkeypatch):
    auth_as(admin_user)
    mock_supabase.execute.return_value = MagicMock(data=_lead(google_place_id=None))

    def no_place(sb, current, **k):
        raise ValueError("This lead has no Google place ID; paste a Google Maps link to import.")

    monkeypatch.setattr(admin_leads, "reimport_place", no_place)
    r = client.post("/admin/leads/lead-1/google-import", json={})
    assert r.status_code == 422 and "no Google place ID" in r.json()["detail"]
```

- [ ] **Step 6: Run to verify failure**

Run: `cd backend && venv/Scripts/python -m pytest auth_service/tests/test_admin_leads_google_import.py -q`
Expected: FAIL (`AttributeError: module has no attribute 'import_place'` / 404s).

- [ ] **Step 7: Implement the routes** in `admin_leads.py`

Imports (extend the existing block):

```python
from fastapi import APIRouter, HTTPException, Query, Request, Response, status

from ..core.config import settings
from ..core.pg_rate_limit import enforce
from ..models.schemas import GoogleImportIn, GoogleReimportIn, LeadCreate, LeadOut, LeadUpdate
from ..services.google_places.client import GooglePlacesError
from ..services.google_places.importer import (
    DuplicateLead,
    ImportOutcome,
    MonthlyCapReached,
    import_place,
    reimport_place,
)
```

Helpers + routes, placed after `create_lead` and before `get_lead` (so `/google-import` is matched before `/{lead_id}` for GET-less paths — different methods anyway, but keep it explicit):

```python
_GOOGLE_STATUS = {400: 422, 401: 502, 403: 502, 404: 404, 429: 503, 504: 504}


def _google_http(e: GooglePlacesError) -> HTTPException:
    if e.status == 503:
        return HTTPException(status_code=503, detail=e.message)
    code = _GOOGLE_STATUS.get(e.status, 502)
    prefix = {404: "Place not found", 422: "Google rejected the request", 503: "Google quota exceeded, try later",
              504: "Google did not answer in time"}.get(code, "Google Places error")
    return HTTPException(status_code=code, detail=f"{prefix}: {e.message}")


def _require_google_key() -> None:
    if not settings.GOOGLE_MAPS_API_KEY:
        raise HTTPException(status_code=503, detail="Google Maps import is not configured on this backend")


def _outcome_response(outcome: ImportOutcome, response: Response, *, created: bool):
    response.headers["X-Import-Warnings"] = str(len(outcome.warnings))
    if outcome.lead is None:
        if not outcome.candidates:
            raise HTTPException(status_code=404, detail="Could not find a place for that input. Try the full Google Maps link or 'Name, City'.")
        response.status_code = 200
        return {"status": "candidates", "candidates": outcome.candidates, "warnings": outcome.warnings}
    response.status_code = 201 if created else 200
    return LeadOut(**outcome.lead)


def _run_import(fn, response: Response, *, created: bool):
    try:
        return _outcome_response(fn(), response, created=created)
    except DuplicateLead as e:
        raise HTTPException(status_code=409, detail={"message": "This Google place is already a lead.", "lead_id": e.lead_id}) from e
    except MonthlyCapReached as e:
        raise HTTPException(status_code=429, detail="Monthly Google import cap reached (GOOGLE_PLACES_MONTHLY_CAP). Raise it on cms-backend-roman if you accept the cost.") from e
    except GooglePlacesError as e:
        raise _google_http(e) from e
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e


@router.post("/google-import", response_model=None, status_code=status.HTTP_201_CREATED)
async def google_import(body: GoogleImportIn, request: Request, response: Response):
    """Create a lead from a Google Maps link / place ID / 'Name, City' (ADR-0012)."""
    user = await admin_user_via_bearer_or_sid(request)
    _require_google_key()
    enforce(f"google_import:user:{user.id}", 20, 3600, detail="Too many imports this hour; try again later.")
    sb = get_supabase_admin()
    return _run_import(
        lambda: import_place(sb, raw_input=body.input.strip(), lead_type=body.lead_type, language=body.language),
        response, created=True,
    )


@router.post("/{lead_id}/google-import", response_model=None)
async def google_reimport(lead_id: str, body: GoogleReimportIn, request: Request, response: Response):
    """Refresh an existing lead from Google: fill empty fields, or overwrite=true."""
    user = await admin_user_via_bearer_or_sid(request)
    _require_google_key()
    enforce(f"google_import:user:{user.id}", 20, 3600, detail="Too many imports this hour; try again later.")
    sb = get_supabase_admin()
    current = sb.table("leads").select("*").eq("id", lead_id).maybe_single().execute()
    if not current.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lead not found")
    raw = body.input.strip() if body.input else None
    return _run_import(
        lambda: reimport_place(sb, current.data, raw_input=raw, overwrite=body.overwrite, language=body.language),
        response, created=False,
    )
```

`response_model=None` because the handler returns either `LeadOut` or the candidates dict; FastAPI serialises both.

- [ ] **Step 8: Patch conftest** — add to `targets` in `mock_supabase`:

```python
        "auth_service.core.pg_rate_limit.get_supabase_admin",  # ADR-0012 import rate limits
```

- [ ] **Step 9: Run the router tests plus the whole leads suite**

Run: `cd backend && venv/Scripts/python -m pytest auth_service/tests/test_admin_leads_google_import.py auth_service/tests/test_admin_leads_router.py auth_service/tests/test_google_places_importer.py -q`
Expected: PASS.

- [ ] **Step 10: Lint, commit**

```bash
cd backend && venv/Scripts/python -m ruff check . && venv/Scripts/python -m black --check .
git add backend/auth_service/services/google_places/importer.py backend/auth_service/routers/admin_leads.py backend/auth_service/tests/conftest.py backend/auth_service/tests/test_google_places_importer.py backend/auth_service/tests/test_admin_leads_google_import.py
git commit -m "feat(leads): POST /admin/leads/google-import and per-lead re-import"
```

---

### Task 8: PATCH support for `social_links` (mirrored) and `photo_urls` (with Storage cleanup)

**Files:**
- Modify: `backend/auth_service/routers/admin_leads.py` (`patch_lead`, the `needs_current` block at `:148-177` of the `dev` file)
- Test: `backend/auth_service/tests/test_admin_leads_router.py` (append)

**Interfaces:**
- Consumes: `LeadUpdate.social_links`, `LeadUpdate.photo_urls` (Task 1), `photos.delete_lead_photos`, `photos.storage_path_of` (Task 6).
- Produces: PATCH semantics — `social_links` (full map) also writes `facebook_url`/`instagram_url`; `facebook_url`/`instagram_url` alone also update the matching key in `social_links`; `photo_urls` deletes dropped `lead-photos` objects and prunes `extra.google.photos` entries whose `url` was dropped.

- [ ] **Step 1: Write the failing tests** (append to `test_admin_leads_router.py`)

```python
def test_patch_social_links_mirrors_legacy_columns(mock_supabase, client, auth_as, admin_user):
    auth_as(admin_user)
    mock_supabase.execute.side_effect = [
        MagicMock(data={"lead_status": "sent", "closed_amount": None, "extra": {}, "social_links": {}, "photo_urls": []}),
        MagicMock(data=[_lead_row(social_links={"facebook": "https://facebook.com/acme"}, facebook_url="https://facebook.com/acme")]),
    ]
    resp = client.patch("/admin/leads/lead-1", json={"social_links": {"facebook": "https://facebook.com/acme", "tiktok": "https://www.tiktok.com/@acme"}})
    assert resp.status_code == 200
    sent = mock_supabase.update.call_args.args[0]
    assert sent["social_links"] == {"facebook": "https://facebook.com/acme", "tiktok": "https://www.tiktok.com/@acme"}
    assert sent["facebook_url"] == "https://facebook.com/acme" and sent["instagram_url"] is None


def test_patch_legacy_column_updates_social_links(mock_supabase, client, auth_as, admin_user):
    auth_as(admin_user)
    mock_supabase.execute.side_effect = [
        MagicMock(data={"lead_status": "sent", "closed_amount": None, "extra": {}, "social_links": {"tiktok": "https://www.tiktok.com/@acme"}, "photo_urls": []}),
        MagicMock(data=[_lead_row()]),
    ]
    resp = client.patch("/admin/leads/lead-1", json={"instagram_url": "https://instagram.com/acme"})
    assert resp.status_code == 200
    sent = mock_supabase.update.call_args.args[0]
    assert sent["social_links"] == {"tiktok": "https://www.tiktok.com/@acme", "instagram": "https://instagram.com/acme"}


def test_patch_photo_urls_deletes_dropped_objects(mock_supabase, client, auth_as, admin_user, monkeypatch):
    auth_as(admin_user)
    keep = "https://x.supabase.co/storage/v1/object/public/lead-photos/lead-1/00-a.jpg"
    drop = "https://x.supabase.co/storage/v1/object/public/lead-photos/lead-1/01-b.jpg"
    mock_supabase.execute.side_effect = [
        MagicMock(data={"lead_status": "sent", "closed_amount": None, "social_links": {}, "photo_urls": [keep, drop],
                        "extra": {"google": {"photos": [{"url": keep, "name": "a"}, {"url": drop, "name": "b"}]}}}),
        MagicMock(data=[_lead_row(photo_urls=[keep])]),
    ]
    deleted = {}
    monkeypatch.setattr("auth_service.routers.admin_leads.delete_lead_photos",
                        lambda sb, lead_id, urls=None: deleted.update(lead_id=lead_id, urls=urls) or ["lead-1/01-b.jpg"])
    resp = client.patch("/admin/leads/lead-1", json={"photo_urls": [keep]})
    assert resp.status_code == 200
    assert deleted == {"lead_id": "lead-1", "urls": [drop]}
    sent = mock_supabase.update.call_args.args[0]
    assert sent["photo_urls"] == [keep]
    assert [p["name"] for p in sent["extra"]["google"]["photos"]] == ["a"]
```

- [ ] **Step 2: Run to verify failure**

Run: `cd backend && venv/Scripts/python -m pytest auth_service/tests/test_admin_leads_router.py -q`
Expected: the three new tests FAIL (mirrors missing / KeyError).

- [ ] **Step 3: Implement** in `patch_lead`

Add the import `from ..services.google_places.photos import delete_lead_photos` to the router. Change the `needs_current` line and select:

```python
    needs_current = any(
        k in patch for k in ("closed_amount", "about_attributes", "social_links", "facebook_url", "instagram_url", "photo_urls")
    )
    if needs_current:
        current = (
            sb.table("leads")
            .select("lead_status, closed_amount, extra, social_links, photo_urls")
            .eq("id", lead_id)
            .maybe_single()
            .execute()
        )
        if not current.data:
            raise HTTPException(status_code=404, detail="Lead not found")
```

After the `about_attributes` block, before `res = sb.table("leads").update(...)`:

```python
    # ADR-0012: social_links is the full map; facebook_url/instagram_url mirror two keys.
    if "social_links" in patch:
        links = patch["social_links"] or {}
        patch["facebook_url"] = links.get("facebook")
        patch["instagram_url"] = links.get("instagram")
    elif "facebook_url" in patch or "instagram_url" in patch:
        links = dict(current.data.get("social_links") or {})
        for col, key in (("facebook_url", "facebook"), ("instagram_url", "instagram")):
            if col in patch:
                if patch[col]:
                    links[key] = str(patch[col])
                else:
                    links.pop(key, None)
        patch["social_links"] = links
    for key in ("facebook_url", "instagram_url", "website_url", "menu_url"):
        if key in patch and patch[key] is not None:
            patch[key] = str(patch[key])

    # ADR-0012: dropping a photo deletes our copy and its metadata.
    if "photo_urls" in patch:
        new_urls = list(patch["photo_urls"] or [])
        dropped = [u for u in (current.data.get("photo_urls") or []) if u not in new_urls]
        if dropped:
            delete_lead_photos(sb, lead_id, dropped)
        extra = patch.get("extra") or dict(current.data.get("extra") or {})
        google = dict(extra.get("google") or {})
        if google.get("photos"):
            google["photos"] = [p for p in google["photos"] if p.get("url") in new_urls]
            extra["google"] = google
            patch["extra"] = extra
```

(The existing `email` str-cast stays; the loop above replaces the create-path cast pattern for URLs in PATCH, which `LeadUpdate` previously left as `_LeadUrl` instances.)

- [ ] **Step 4: Run tests**

Run: `cd backend && venv/Scripts/python -m pytest auth_service/tests/test_admin_leads_router.py auth_service/tests/test_admin_leads_google_import.py -q`
Expected: PASS.

- [ ] **Step 5: Lint, commit**

```bash
cd backend && venv/Scripts/python -m ruff check . && venv/Scripts/python -m black --check .
git add backend/auth_service/routers/admin_leads.py backend/auth_service/tests/test_admin_leads_router.py
git commit -m "feat(leads): PATCH social_links mirror and photo removal"
```

---

### Task 9: Dashboard — import block in Add-Lead drawer

**Files:**
- Modify: `frontend/src/components/admin/leads/types.ts:14-58` (`Lead`), append `GoogleImportCandidate`, `GoogleImportResult`
- Modify: `frontend/src/components/admin/leads/hooks/useLeadPatch.ts:6-37` (`LeadUpdatePayload`)
- Modify: `frontend/src/components/admin/leads/AddLeadDrawer.tsx` (`Props` `:16-20`, `DrawerBody` props `:66-72`, JSX after the header `:230`)
- Modify: `frontend/src/components/admin/leads/LeadsDashboard.tsx:87-100` (add `handleImport`), and the `<AddLeadDrawer … />` usage (pass `onImport`)
- Test: `frontend/src/components/admin/leads/AddLeadDrawer.test.tsx` (append)

**Interfaces:**
- Produces (types.ts):

```ts
export interface GoogleImportCandidate { place_id: string; name: string | null; address: string | null }
export type GoogleImportResult =
  | { status: "created"; lead: Lead }
  | { status: "candidates"; candidates: GoogleImportCandidate[] };
```

  `Lead` gains `google_place_id: string | null; google_imported_at: string | null; business_status: string | null; primary_type: string | null; types: string[]; price_level: string | null; social_links: Record<string, string>;`. `LeadUpdatePayload` gains `social_links?: Record<string, string>; photo_urls?: string[];`.
- `AddLeadDrawer` prop `onImport: (input: string, leadType: LeadType) => Promise<GoogleImportResult>`.
- `LeadsDashboard.handleImport(input, leadType)` POSTs `/api/admin/leads/google-import` with `{input, lead_type}`; on 201 closes the drawer, selects the lead, refreshes; on 200 returns candidates; otherwise throws `Error(detail)` where a 409 detail object becomes `"<message> (open the existing lead)"`.

- [ ] **Step 1: Write the failing tests** (append to `AddLeadDrawer.test.tsx`)

```tsx
  it("renders the Google import block and calls onImport with input and product", async () => {
    const onImport = vi.fn().mockResolvedValue({ status: "created", lead: { id: "l1" } });
    render(<AddLeadDrawer open onClose={vi.fn()} onCreate={vi.fn()} onImport={onImport} />);
    fireEvent.change(screen.getByLabelText("Google Maps link, place ID or 'Name, City'"), {
      target: { value: " https://maps.app.goo.gl/abc " },
    });
    fireEvent.click(screen.getByRole("button", { name: /^import$/i }));
    await waitFor(() => expect(onImport).toHaveBeenCalledWith("https://maps.app.goo.gl/abc", "website"));
  });

  it("blocks import with an empty input", () => {
    const onImport = vi.fn();
    render(<AddLeadDrawer open onClose={vi.fn()} onCreate={vi.fn()} onImport={onImport} />);
    fireEvent.click(screen.getByRole("button", { name: /^import$/i }));
    expect(onImport).not.toHaveBeenCalled();
    expect(screen.getByText(/paste a google maps link/i)).toBeInTheDocument();
  });

  it("shows candidates and re-imports the chosen place id", async () => {
    const onImport = vi
      .fn()
      .mockResolvedValueOnce({
        status: "candidates",
        candidates: [
          { place_id: "ChIJ1", name: "Samir Kapsalon", address: "Stadhuisplein 1" },
          { place_id: "ChIJ2", name: "Samir Barber", address: null },
        ],
      })
      .mockResolvedValueOnce({ status: "created", lead: { id: "l1" } });
    render(<AddLeadDrawer open onClose={vi.fn()} onCreate={vi.fn()} onImport={onImport} />);
    fireEvent.change(screen.getByLabelText("Google Maps link, place ID or 'Name, City'"), {
      target: { value: "Samir" },
    });
    fireEvent.click(screen.getByRole("button", { name: /^import$/i }));
    const pick = await screen.findByRole("button", { name: /samir kapsalon/i });
    expect(screen.getByText("Stadhuisplein 1")).toBeInTheDocument();
    fireEvent.click(pick);
    await waitFor(() => expect(onImport).toHaveBeenLastCalledWith("ChIJ1", "website"));
  });

  it("surfaces an import error", async () => {
    const onImport = vi.fn().mockRejectedValue(new Error("Monthly Google import cap reached"));
    render(<AddLeadDrawer open onClose={vi.fn()} onCreate={vi.fn()} onImport={onImport} />);
    fireEvent.change(screen.getByLabelText("Google Maps link, place ID or 'Name, City'"), {
      target: { value: "ChIJx" },
    });
    fireEvent.click(screen.getByRole("button", { name: /^import$/i }));
    expect(await screen.findByText(/monthly google import cap/i)).toBeInTheDocument();
  });
```

Also update the existing renders in this file to pass `onImport={vi.fn()}` (the prop is required).

- [ ] **Step 2: Run to verify failure**

Run: `cd frontend && npx vitest run src/components/admin/leads/AddLeadDrawer.test.tsx`
Expected: FAIL (label not found / type error).

- [ ] **Step 3: Implement**

`types.ts` — extend `Lead` (after `languages`) and append the two exports from Interfaces. `useLeadPatch.ts` — append the two optional keys to `LeadUpdatePayload`.

`AddLeadDrawer.tsx`:

```tsx
import { Download, Loader2, Plus, Trash2, X } from "lucide-react";
import type { GoogleImportCandidate, GoogleImportResult, LeadCreateInput, LeadReviewInput } from "./types";

interface Props {
  open: boolean;
  onClose: () => void;
  onCreate: (payload: LeadCreateInput) => Promise<void>;
  onImport: (input: string, leadType: LeadType) => Promise<GoogleImportResult>;
}
```

Thread `onImport` through `AddLeadDrawer` → `DrawerBody`. Inside `DrawerBody` add state and handler next to the existing `saving`/`error` state:

```tsx
  // Google Maps import (ADR-0012)
  const [importInput, setImportInput] = useState("");
  const [importing, setImporting] = useState(false);
  const [importError, setImportError] = useState<string | null>(null);
  const [candidates, setCandidates] = useState<GoogleImportCandidate[]>([]);

  async function runImport(value: string) {
    const trimmed = value.trim();
    if (!trimmed) {
      setImportError("Paste a Google Maps link, place ID or 'Name, City' first.");
      return;
    }
    setImporting(true);
    setImportError(null);
    try {
      const result = await onImport(trimmed, leadType);
      if (result.status === "candidates") {
        setCandidates(result.candidates);
        if (result.candidates.length === 0) setImportError("No matching place found.");
      } else {
        setCandidates([]);
      }
    } catch (err) {
      setImportError(err instanceof Error ? err.message : "Import failed");
    } finally {
      setImporting(false);
    }
  }
```

JSX, directly under the header `<div className="flex items-start justify-between gap-2">…</div>` and before the manual form sections:

```tsx
      <section className="mt-4 rounded-lg border border-zinc-200 dark:border-zinc-800 bg-zinc-50 dark:bg-zinc-900 p-3 space-y-2">
        <div className="text-xs uppercase tracking-wider text-zinc-500 dark:text-zinc-400 font-semibold">
          Import from Google Maps
        </div>
        <div className="flex items-center gap-2">
          <input
            type="text"
            aria-label="Google Maps link, place ID or 'Name, City'"
            placeholder="https://maps.app.goo.gl/… or 'Samir Kapsalon, Lelystad'"
            value={importInput}
            onChange={(e) => setImportInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                e.preventDefault();
                runImport(importInput).catch(() => {});
              }
            }}
            disabled={importing}
            className="flex-1 rounded-md border border-zinc-200 dark:border-zinc-700 bg-white dark:bg-zinc-950 px-2.5 py-1.5 text-sm text-zinc-900 dark:text-zinc-100 focus:outline-none focus:ring-2 focus:ring-zinc-400 dark:focus:ring-zinc-600"
          />
          <button
            type="button"
            onClick={() => {
              runImport(importInput).catch(() => {});
            }}
            disabled={importing || saving}
            className={`inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-md cursor-pointer disabled:cursor-not-allowed ${dashAccent.ctaPrimary}`}
          >
            {importing ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Download className="h-3.5 w-3.5" />}
            {importing ? "Importing…" : "Import"}
          </button>
        </div>
        <p className="text-[11px] text-zinc-500 dark:text-zinc-400">
          Fills name, address, contact, hours, reviews, photos and social links. Uses the Product selected below.
        </p>
        {importError && (
          <div className="rounded-md bg-red-50 dark:bg-red-950 px-3 py-2 text-xs text-red-700 dark:text-red-300">
            {importError}
          </div>
        )}
        {candidates.length > 0 && (
          <div className="space-y-1">
            <div className="text-xs text-zinc-600 dark:text-zinc-300">Several places match — pick one:</div>
            {candidates.map((c) => (
              <button
                key={c.place_id}
                type="button"
                disabled={importing}
                onClick={() => {
                  runImport(c.place_id).catch(() => {});
                }}
                className="w-full text-left rounded-md border border-zinc-200 dark:border-zinc-700 bg-white dark:bg-zinc-950 px-3 py-2 text-xs hover:bg-zinc-100 dark:hover:bg-zinc-800 cursor-pointer disabled:cursor-not-allowed"
              >
                <div className="font-medium text-zinc-900 dark:text-zinc-100">{c.name ?? c.place_id}</div>
                {c.address && <div className="text-zinc-500 dark:text-zinc-400">{c.address}</div>}
              </button>
            ))}
          </div>
        )}
      </section>
      <div className="mt-4 text-xs uppercase tracking-wider text-zinc-400 dark:text-zinc-500">or fill in manually</div>
```

`LeadsDashboard.tsx` — add next to `handleCreate` and pass `onImport={handleImport}` to `<AddLeadDrawer>`:

```tsx
  async function handleImport(input: string, leadType: LeadType): Promise<GoogleImportResult> {
    const res = await fetch(`/api/admin/leads/google-import`, {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ input, lead_type: leadType }),
    });
    if (res.status === 201) {
      const lead: Lead = await res.json();
      setAddOpen(false);
      setSelectedLead(lead);
      await refresh();
      return { status: "created", lead };
    }
    if (res.status === 200) {
      const body = (await res.json()) as { candidates: GoogleImportCandidate[] };
      return { status: "candidates", candidates: body.candidates };
    }
    const detail = (await res.json().catch(() => ({}))) as { detail?: string | { message?: string; lead_id?: string } };
    if (typeof detail.detail === "object" && detail.detail) {
      throw new Error(`${detail.detail.message ?? "Already imported"} (lead ${detail.detail.lead_id ?? "?"})`);
    }
    throw new Error(typeof detail.detail === "string" ? detail.detail : `Import failed (${res.status})`);
  }
```

(import `LeadType` from `@/lib/leadEnums` and the two new types from `./types`).

- [ ] **Step 4: Run tests, lint, typecheck**

Run: `cd frontend && npx vitest run src/components/admin/leads && npm run lint && npm run typecheck`
Expected: PASS; no type errors (other components constructing `Lead` literals in tests use `as unknown as Lead`, so the new required fields don't break them).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/admin/leads/types.ts frontend/src/components/admin/leads/hooks/useLeadPatch.ts frontend/src/components/admin/leads/AddLeadDrawer.tsx frontend/src/components/admin/leads/AddLeadDrawer.test.tsx frontend/src/components/admin/leads/LeadsDashboard.tsx
git commit -m "feat(dashboard): import a lead from a Google Maps link"
```

---

### Task 10: Dashboard — re-import action, Photos and Business sections, social links in Contact

**Files:**
- Create: `frontend/src/components/admin/leads/sections/PhotosSection.tsx`
- Create: `frontend/src/components/admin/leads/sections/BusinessSection.tsx`
- Modify: `frontend/src/components/admin/leads/sections/ContactSection.tsx`
- Modify: `frontend/src/components/admin/leads/LeadDetailDrawer.tsx` (header actions `:229-260`, sections `:412-435`)
- Test: `frontend/src/components/admin/leads/sections/__tests__/PhotosSection.test.tsx`, `.../BusinessSection.test.tsx`, `.../ContactSection.test.tsx` (extend), `frontend/src/components/admin/leads/LeadDetailDrawer.test.tsx` (new)

**Interfaces:**
- `PhotosSection({ lead, onPatched })` reads `lead.photo_urls` and `lead.extra.google.photos[]` (`{url, attributions:[{name, uri}], google_maps_uri, owner_photo}`), renders a grid, "Owner" badge, attribution caption linking to `google_maps_uri`, and a remove button that PATCHes `{ photo_urls: remaining }` via `useLeadPatch`.
- `BusinessSection({ lead })` read-only: status, type, price level, types chips, Google summary + disclosure (`lead.extra.google.generative_summary`), imported-at date.
- `ContactSection` edit view gains six inputs (TikTok, LinkedIn, YouTube, X, Pinterest, WhatsApp URL) and sends `social_links` as the full 8-key map (facebook/instagram included) whenever any social value changed; it stops sending `facebook_url`/`instagram_url` directly.
- `LeadDetailDrawer` header gets a "Re-import" button (`RefreshCw`) that toggles an inline panel: when `lead.google_place_id` is null an input `aria-label="Google Maps link or place ID"`; a checkbox `aria-label="Overwrite existing fields"`; buttons "Import from Google" / "Cancel". POSTs `/api/admin/leads/${lead.id}/google-import` with `{ input?, overwrite }`; `200` with a `Lead` → `onPatched(lead)` and close panel; `200` with `status:"candidates"` → list buttons that re-POST with `input: place_id`; errors render in the panel.

- [ ] **Step 1: Write the failing tests**

`PhotosSection.test.tsx`:

```tsx
import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { EditingSectionProvider } from "../../context/EditingSectionContext";
import { PhotosSection } from "../PhotosSection";
import type { Lead } from "../../types";

const A = "https://x.supabase.co/storage/v1/object/public/lead-photos/l/00-a.jpg";
const B = "https://x.supabase.co/storage/v1/object/public/lead-photos/l/01-b.jpg";
const lead = {
  id: "lead-1",
  photo_urls: [A, B],
  extra: { google: { photos: [
    { url: A, owner_photo: true, attributions: [{ name: "Samir Kapsalon", uri: "https://g/c/1" }], google_maps_uri: "https://g/p/a" },
    { url: B, owner_photo: false, attributions: [{ name: "Jan", uri: null }], google_maps_uri: "https://g/p/b" },
  ] } },
} as unknown as Lead;

describe("PhotosSection", () => {
  it("renders photos with attribution and owner badge", () => {
    render(<EditingSectionProvider><PhotosSection lead={lead} onPatched={vi.fn()} /></EditingSectionProvider>);
    expect(screen.getAllByRole("img")).toHaveLength(2);
    expect(screen.getByText("Owner")).toBeInTheDocument();
    expect(screen.getByText(/Samir Kapsalon/)).toBeInTheDocument();
    expect(screen.getByText("Jan").closest("a")).toHaveAttribute("href", "https://g/p/b");
  });

  it("shows an empty state", () => {
    render(<EditingSectionProvider><PhotosSection lead={{ ...lead, photo_urls: [] } as Lead} onPatched={vi.fn()} /></EditingSectionProvider>);
    expect(screen.getByText(/no photos/i)).toBeInTheDocument();
  });

  it("removing a photo PATCHes the remaining list", async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: async () => ({ ...lead, photo_urls: [B] }) });
    vi.stubGlobal("fetch", fetchMock);
    const onPatched = vi.fn();
    render(<EditingSectionProvider><PhotosSection lead={lead} onPatched={onPatched} /></EditingSectionProvider>);
    fireEvent.click(screen.getAllByRole("button", { name: /remove photo/i })[0]);
    await waitFor(() => expect(onPatched).toHaveBeenCalled());
    expect(JSON.parse(fetchMock.mock.calls[0][1].body)).toEqual({ photo_urls: [B] });
    vi.unstubAllGlobals();
  });
});
```

`BusinessSection.test.tsx`:

```tsx
import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { BusinessSection } from "../BusinessSection";
import type { Lead } from "../../types";

describe("BusinessSection", () => {
  it("renders Google business facts", () => {
    const lead = {
      business_status: "CLOSED_TEMPORARILY", primary_type: "barber_shop", price_level: "moderate",
      types: ["barber_shop", "hair_salon"], google_imported_at: "2026-10-11T10:00:00Z",
      extra: { google: { generative_summary: { overview: "Sharp fades.", disclosure: "Summarized with Gemini" } } },
    } as unknown as Lead;
    render(<BusinessSection lead={lead} />);
    expect(screen.getByText("Closed temporarily")).toBeInTheDocument();
    expect(screen.getByText("Barber shop")).toBeInTheDocument();
    expect(screen.getByText("Moderate")).toBeInTheDocument();
    expect(screen.getByText("hair salon")).toBeInTheDocument();
    expect(screen.getByText("Sharp fades.")).toBeInTheDocument();
    expect(screen.getByText(/Summarized with Gemini/)).toBeInTheDocument();
  });

  it("renders nothing when the lead was never imported", () => {
    const { container } = render(<BusinessSection lead={{ google_place_id: null, extra: {} } as unknown as Lead} />);
    expect(container).toBeEmptyDOMElement();
  });
});
```

`ContactSection.test.tsx` — append:

```tsx
  it("sends social_links as a full map when a social URL changes", async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: async () => lead });
    vi.stubGlobal("fetch", fetchMock);
    const withSocial = { ...lead, facebook_url: "https://facebook.com/acme", social_links: { facebook: "https://facebook.com/acme" } } as Lead;
    render(<EditingSectionProvider><ContactSection lead={withSocial} onPatched={vi.fn()} /></EditingSectionProvider>);
    fireEvent.click(screen.getByLabelText("Edit Contact"));
    fireEvent.change(screen.getByLabelText("TikTok URL"), { target: { value: "tiktok.com/@acme" } });
    fireEvent.click(screen.getByRole("button", { name: /^save$/i }));
    await waitFor(() => expect(fetchMock).toHaveBeenCalled());
    const body = JSON.parse(fetchMock.mock.calls[0][1].body);
    expect(body.social_links).toEqual({ facebook: "https://facebook.com/acme", tiktok: "https://tiktok.com/@acme" });
    expect(body.facebook_url).toBeUndefined();
    vi.unstubAllGlobals();
  });
```

`LeadDetailDrawer.test.tsx` (new; the drawer renders many sections, so stub fetch and keep assertions to the panel):

```tsx
import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { LeadDetailDrawer } from "./LeadDetailDrawer";
import type { Lead } from "./types";

const base = {
  id: "lead-1", business_name: "Acme", category: "Barber", source_url: null, lead_status: "not_sent",
  website_build_status: "not_started", ai_workflow_status: "not_started", lead_contact_type: "not_contacted",
  payment_status: "not_applicable", call_count: 0, notes: null, closed_amount: null, closed_at: null,
  photo_urls: [], extra: {}, languages: [], reviews: null, opening_hours: null, social_links: {}, types: [],
  google_place_id: "ChIJx",
} as unknown as Lead;

describe("LeadDetailDrawer re-import", () => {
  it("re-imports with the stored place id and overwrite flag", async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, status: 200, json: async () => ({ ...base, business_name: "Fresh" }) });
    vi.stubGlobal("fetch", fetchMock);
    const onPatched = vi.fn();
    render(<LeadDetailDrawer lead={base} onClose={vi.fn()} onPatched={onPatched} onDeleted={vi.fn()} />);
    fireEvent.click(screen.getByRole("button", { name: /re-import/i }));
    expect(screen.queryByLabelText("Google Maps link or place ID")).not.toBeInTheDocument();
    fireEvent.click(screen.getByLabelText("Overwrite existing fields"));
    fireEvent.click(screen.getByRole("button", { name: /import from google/i }));
    await waitFor(() => expect(onPatched).toHaveBeenCalledWith(expect.objectContaining({ business_name: "Fresh" })));
    expect(fetchMock.mock.calls[0][0]).toBe("/api/admin/leads/lead-1/google-import");
    expect(JSON.parse(fetchMock.mock.calls[0][1].body)).toEqual({ overwrite: true });
    vi.unstubAllGlobals();
  });

  it("asks for a link when the lead has no place id and shows candidates", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true, status: 200,
      json: async () => ({ status: "candidates", candidates: [{ place_id: "ChIJ1", name: "Acme Barber", address: "Main 1" }], warnings: [] }),
    });
    vi.stubGlobal("fetch", fetchMock);
    render(<LeadDetailDrawer lead={{ ...base, google_place_id: null } as Lead} onClose={vi.fn()} onPatched={vi.fn()} onDeleted={vi.fn()} />);
    fireEvent.click(screen.getByRole("button", { name: /re-import/i }));
    fireEvent.change(screen.getByLabelText("Google Maps link or place ID"), { target: { value: "Acme" } });
    fireEvent.click(screen.getByRole("button", { name: /import from google/i }));
    expect(await screen.findByRole("button", { name: /acme barber/i })).toBeInTheDocument();
    expect(JSON.parse(fetchMock.mock.calls[0][1].body)).toEqual({ input: "Acme", overwrite: false });
    vi.unstubAllGlobals();
  });
});
```

Check the drawer's actual prop names at the top of `LeadDetailDrawer.tsx` (`lead`, `onClose`, `onPatched`, `onDeleted`) and adjust the test if they differ.

- [ ] **Step 2: Run to verify failure**

Run: `cd frontend && npx vitest run src/components/admin/leads`
Expected: new tests FAIL (modules/labels missing).

- [ ] **Step 3: Implement `PhotosSection.tsx`**

```tsx
"use client";

import { ExternalLink, X } from "lucide-react";
import type { Lead } from "../types";
import { useLeadPatch } from "../hooks/useLeadPatch";

interface PhotoMeta {
  url?: string;
  owner_photo?: boolean;
  attributions?: { name?: string | null; uri?: string | null }[];
  google_maps_uri?: string | null;
}

function metaFor(lead: Lead): Map<string, PhotoMeta> {
  const google = (lead.extra?.google ?? {}) as { photos?: PhotoMeta[] };
  const map = new Map<string, PhotoMeta>();
  for (const p of google.photos ?? []) if (p.url) map.set(p.url, p);
  return map;
}

export function PhotosSection({ lead, onPatched }: { lead: Lead; onPatched: (lead: Lead) => void }) {
  const { patch, saving, error } = useLeadPatch(lead.id, onPatched);
  const meta = metaFor(lead);

  async function remove(url: string) {
    await patch({ photo_urls: lead.photo_urls.filter((u) => u !== url) }).catch(() => {});
  }

  return (
    <section className="mt-5">
      <h3 className="text-xs uppercase tracking-wider text-zinc-500 dark:text-zinc-400 font-semibold mb-2">
        Photos{lead.photo_urls.length > 0 && ` (${lead.photo_urls.length})`}
      </h3>
      {error && (
        <div className="mb-2 rounded-md bg-red-50 dark:bg-red-950 px-3 py-1.5 text-xs text-red-700 dark:text-red-300">{error}</div>
      )}
      {lead.photo_urls.length === 0 ? (
        <div className="rounded-lg border border-dashed border-zinc-200 dark:border-zinc-800 bg-zinc-50 dark:bg-zinc-900 p-3 text-xs text-zinc-500 dark:text-zinc-400 italic">
          No photos imported.
        </div>
      ) : (
        <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
          {lead.photo_urls.map((url) => {
            const m = meta.get(url);
            const author = m?.attributions?.[0]?.name ?? null;
            return (
              <figure key={url} className="relative rounded-lg overflow-hidden border border-zinc-200 dark:border-zinc-800 bg-zinc-100 dark:bg-zinc-900">
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img src={url} alt={author ? `Photo by ${author}` : "Listing photo"} className="h-28 w-full object-cover" loading="lazy" />
                {m?.owner_photo && (
                  <span className="absolute left-1.5 top-1.5 rounded bg-emerald-600/90 px-1.5 py-0.5 text-[10px] font-medium text-white">Owner</span>
                )}
                <button
                  type="button"
                  aria-label="Remove photo"
                  disabled={saving}
                  onClick={() => void remove(url)}
                  className="absolute right-1.5 top-1.5 h-6 w-6 inline-flex items-center justify-center rounded-md bg-black/60 text-white hover:bg-black/80 cursor-pointer disabled:cursor-not-allowed"
                >
                  <X className="h-3.5 w-3.5" />
                </button>
                <figcaption className="px-2 py-1 text-[11px] text-zinc-600 dark:text-zinc-300 truncate">
                  {m?.google_maps_uri ? (
                    <a href={m.google_maps_uri} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1 hover:underline">
                      {author ?? "View on Google Maps"}
                      <ExternalLink className="h-3 w-3" />
                    </a>
                  ) : (
                    author ?? "—"
                  )}
                </figcaption>
              </figure>
            );
          })}
        </div>
      )}
    </section>
  );
}
```

- [ ] **Step 4: Implement `BusinessSection.tsx`**

```tsx
"use client";

import type { Lead } from "../types";

const STATUS_LABEL: Record<string, string> = {
  OPERATIONAL: "Operational",
  CLOSED_TEMPORARILY: "Closed temporarily",
  CLOSED_PERMANENTLY: "Closed permanently",
  FUTURE_OPENING: "Opening soon",
};

function humanize(v: string): string {
  const s = v.replace(/_/g, " ");
  return s.charAt(0).toUpperCase() + s.slice(1);
}

export function BusinessSection({ lead }: { lead: Lead }) {
  const google = (lead.extra?.google ?? {}) as {
    generative_summary?: { overview?: string | null; disclosure?: string | null } | null;
  };
  const summary = google.generative_summary;
  const hasAnything =
    lead.google_place_id || lead.business_status || lead.primary_type || lead.price_level || (lead.types?.length ?? 0) > 0;
  if (!hasAnything) return null;

  return (
    <section className="mt-5">
      <h3 className="text-xs uppercase tracking-wider text-zinc-500 dark:text-zinc-400 font-semibold mb-2">Business</h3>
      <div className="rounded-lg border border-zinc-200 dark:border-zinc-800 bg-zinc-50 dark:bg-zinc-900 p-3 space-y-1.5 text-xs">
        <Row label="Status" value={lead.business_status ? STATUS_LABEL[lead.business_status] ?? humanize(lead.business_status.toLowerCase()) : null} />
        <Row label="Type" value={lead.primary_type ? humanize(lead.primary_type) : null} />
        <Row label="Price level" value={lead.price_level ? humanize(lead.price_level) : null} />
        {lead.types?.length > 0 && (
          <div className="flex items-baseline gap-3">
            <span className="text-zinc-500 dark:text-zinc-400 w-24 shrink-0">Google types</span>
            <div className="flex flex-wrap gap-1">
              {lead.types.filter((t) => t !== lead.primary_type && t !== "point_of_interest" && t !== "establishment").map((t) => (
                <span key={t} className="rounded bg-zinc-200 dark:bg-zinc-800 px-1.5 py-0.5 text-[11px] text-zinc-700 dark:text-zinc-300">
                  {t.replace(/_/g, " ")}
                </span>
              ))}
            </div>
          </div>
        )}
        {summary?.overview && (
          <div className="pt-1">
            <div className="text-zinc-500 dark:text-zinc-400">Google summary</div>
            <p className="text-zinc-900 dark:text-zinc-100">{summary.overview}</p>
            {summary.disclosure && <p className="italic text-zinc-400 dark:text-zinc-500">{summary.disclosure} — research only, never quote as the client's words.</p>}
          </div>
        )}
        {lead.google_imported_at && (
          <div className="text-zinc-400 dark:text-zinc-500">Imported from Google on {new Date(lead.google_imported_at).toLocaleDateString()}</div>
        )}
      </div>
    </section>
  );
}

function Row({ label, value }: { label: string; value: string | null | undefined }) {
  return (
    <div className="flex items-baseline gap-3">
      <span className="text-zinc-500 dark:text-zinc-400 w-24 shrink-0">{label}</span>
      {value ? <span className="text-zinc-900 dark:text-zinc-100">{value}</span> : <span className="text-zinc-400 dark:text-zinc-600">—</span>}
    </div>
  );
}
```

- [ ] **Step 5: Extend `ContactSection.tsx`**

Replace the `facebook`/`instagram` state with one `social` map and add the other six platforms:

```tsx
const SOCIAL_FIELDS: { key: string; label: string }[] = [
  { key: "facebook", label: "Facebook URL" },
  { key: "instagram", label: "Instagram URL" },
  { key: "tiktok", label: "TikTok URL" },
  { key: "linkedin", label: "LinkedIn URL" },
  { key: "youtube", label: "YouTube URL" },
  { key: "x", label: "X URL" },
  { key: "pinterest", label: "Pinterest URL" },
  { key: "whatsapp", label: "WhatsApp URL" },
];

function socialOf(lead: Lead): Record<string, string> {
  const out: Record<string, string> = {};
  for (const { key } of SOCIAL_FIELDS) out[key] = lead.social_links?.[key] ?? "";
  // legacy columns win when social_links lacks them (leads created before ADR-0012)
  if (!out.facebook && lead.facebook_url) out.facebook = lead.facebook_url;
  if (!out.instagram && lead.instagram_url) out.instagram = lead.instagram_url;
  return out;
}
```

State: `const [social, setSocial] = useState<Record<string, string>>(() => socialOf(lead));` reset in the effect (add `lead.social_links` to its deps). In `buildDiff`, replace the facebook/instagram lines with:

```tsx
    const nextSocial: Record<string, string> = {};
    for (const { key } of SOCIAL_FIELDS) {
      const v = normU(social[key] ?? "");
      if (v) nextSocial[key] = v;
    }
    const cur = socialOf(lead);
    const curSocial: Record<string, string> = {};
    for (const { key } of SOCIAL_FIELDS) if (cur[key]) curSocial[key] = cur[key];
    if (JSON.stringify(nextSocial) !== JSON.stringify(curSocial)) out.social_links = nextSocial;
```

Read view: one `<Row>` per platform that has a value (plus Facebook/Instagram always, to keep the existing look). Edit view: map `SOCIAL_FIELDS` to `<IconInput>` (icons: `Facebook`, `Instagram` from lucide for the first two, `Link2` for the rest), `aria-label` = label, blur normalises with `handleUrlBlur`. `urlError` checks every social value for whitespace. Remove the `facebook`/`instagram` `useState`s and their `handleCancel` resets (reset `social` instead).

- [ ] **Step 6: Re-import panel in `LeadDetailDrawer.tsx`**

Add state next to `confirmingDelete`:

```tsx
  const [reimportOpen, setReimportOpen] = useState(false);
  const [reimportInput, setReimportInput] = useState("");
  const [reimportOverwrite, setReimportOverwrite] = useState(false);
  const [reimporting, setReimporting] = useState(false);
  const [reimportError, setReimportError] = useState<string | null>(null);
  const [reimportCandidates, setReimportCandidates] = useState<GoogleImportCandidate[]>([]);
```

Reset all six in the existing `useEffect([lead.id])`. Handler:

```tsx
  async function handleReimport(inputOverride?: string) {
    const input = (inputOverride ?? reimportInput).trim();
    if (!lead.google_place_id && !input) {
      setReimportError("Paste a Google Maps link or place ID first.");
      return;
    }
    setReimporting(true);
    setReimportError(null);
    try {
      const body: { input?: string; overwrite: boolean } = { overwrite: reimportOverwrite };
      if (input) body.input = input;
      const res = await fetch(`/api/admin/leads/${lead.id}/google-import`, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        const d = (data as { detail?: string | { message?: string } }).detail;
        throw new Error(typeof d === "object" && d ? d.message ?? "Import failed" : d ?? `Import failed (${res.status})`);
      }
      if ((data as { status?: string }).status === "candidates") {
        setReimportCandidates((data as { candidates: GoogleImportCandidate[] }).candidates);
        return;
      }
      onPatched(data as Lead);
      setReimportOpen(false);
      setReimportCandidates([]);
    } catch (err) {
      setReimportError(err instanceof Error ? err.message : "Import failed");
    } finally {
      setReimporting(false);
    }
  }
```

Header button (before the Save button):

```tsx
            <button
              type="button"
              onClick={() => setReimportOpen((v) => !v)}
              disabled={saving || deleting}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-md border border-zinc-200 dark:border-zinc-700 text-zinc-700 dark:text-zinc-200 hover:bg-zinc-100 dark:hover:bg-zinc-800 disabled:opacity-40 disabled:cursor-not-allowed cursor-pointer transition-colors"
            >
              <RefreshCw className={`h-3.5 w-3.5 ${reimporting ? "animate-spin" : ""}`} />
              Re-import
            </button>
```

Panel, rendered inside the existing `<AnimatePresence initial={false}>` next to the delete confirmation (same `motion.div` height-reveal pattern, `key="reimport"`):

```tsx
          {reimportOpen && (
            <motion.div key="reimport" initial={{ height: 0, opacity: 0 }} animate={{ height: "auto", opacity: 1 }} exit={{ height: 0, opacity: 0 }} transition={{ duration: prefersReduced ? 0 : 0.24, ease: "easeOut" }} className="overflow-hidden">
              <div className="mt-3 rounded-md border border-zinc-200 dark:border-zinc-800 bg-zinc-50 dark:bg-zinc-900 px-3 py-3 space-y-2">
                <p className="text-xs text-zinc-600 dark:text-zinc-300">
                  {lead.google_place_id
                    ? "Refresh this lead from its Google Maps listing. By default only empty fields are filled."
                    : "This lead was not imported from Google yet. Paste its Google Maps link to import."}
                </p>
                {!lead.google_place_id && (
                  <input type="text" aria-label="Google Maps link or place ID" value={reimportInput} onChange={(e) => setReimportInput(e.target.value)} disabled={reimporting}
                    className="w-full rounded-md border border-zinc-200 dark:border-zinc-700 bg-white dark:bg-zinc-950 px-2.5 py-1.5 text-sm text-zinc-900 dark:text-zinc-100 focus:outline-none focus:ring-2 focus:ring-zinc-400" />
                )}
                <label className="inline-flex items-center gap-2 text-xs text-zinc-700 dark:text-zinc-300 cursor-pointer">
                  <input type="checkbox" aria-label="Overwrite existing fields" checked={reimportOverwrite} onChange={(e) => setReimportOverwrite(e.target.checked)} disabled={reimporting} />
                  Overwrite existing fields (also re-downloads photos)
                </label>
                {reimportError && <div className="rounded-md bg-red-50 dark:bg-red-950 px-3 py-2 text-xs text-red-700 dark:text-red-300">{reimportError}</div>}
                {reimportCandidates.length > 0 && (
                  <div className="space-y-1">
                    <div className="text-xs text-zinc-600 dark:text-zinc-300">Several places match — pick one:</div>
                    {reimportCandidates.map((c) => (
                      <button key={c.place_id} type="button" disabled={reimporting} onClick={() => { handleReimport(c.place_id).catch(() => {}); }}
                        className="w-full text-left rounded-md border border-zinc-200 dark:border-zinc-700 bg-white dark:bg-zinc-950 px-3 py-2 text-xs hover:bg-zinc-100 dark:hover:bg-zinc-800 cursor-pointer disabled:cursor-not-allowed">
                        <div className="font-medium text-zinc-900 dark:text-zinc-100">{c.name ?? c.place_id}</div>
                        {c.address && <div className="text-zinc-500 dark:text-zinc-400">{c.address}</div>}
                      </button>
                    ))}
                  </div>
                )}
                <div className="flex items-center gap-2">
                  <motion.button {...press} type="button" disabled={reimporting} onClick={() => { handleReimport().catch(() => {}); }}
                    className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-md bg-zinc-900 text-white hover:bg-zinc-800 dark:bg-zinc-100 dark:text-zinc-900 dark:hover:bg-zinc-200 disabled:opacity-60 disabled:cursor-not-allowed cursor-pointer transition-colors">
                    {reimporting ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <RefreshCw className="h-3.5 w-3.5" />}
                    {reimporting ? "Importing…" : "Import from Google"}
                  </motion.button>
                  <motion.button {...press} type="button" disabled={reimporting} onClick={() => { setReimportOpen(false); setReimportError(null); setReimportCandidates([]); }}
                    className="px-3 py-1.5 text-xs font-medium rounded-md border border-zinc-200 dark:border-zinc-700 text-zinc-600 dark:text-zinc-300 hover:bg-zinc-100 dark:hover:bg-zinc-800 disabled:opacity-40 disabled:cursor-not-allowed cursor-pointer transition-colors">
                    Cancel
                  </motion.button>
                </div>
              </div>
            </motion.div>
          )}
```

Sections: insert `<BusinessSection lead={lead} />` after the closed-deal block and before `<LocationSection>`, and `<PhotosSection lead={lead} onPatched={onPatched} />` after `<OpeningHoursSection>` and before `<ReviewsList>`. Import `RefreshCw` from lucide and `GoogleImportCandidate` from `./types`.

- [ ] **Step 7: Run tests, lint, typecheck, format**

Run: `cd frontend && npx vitest run src/components/admin/leads && npm run lint && npm run typecheck && npm run format:check`
Expected: PASS. If `format:check` fails, run `npx prettier --write` on the touched files.

- [ ] **Step 8: Commit**

```bash
git add frontend/src/components/admin/leads
git commit -m "feat(dashboard): re-import from Google, photos and business sections, social links"
```

---

### Task 11: Downstream docs — design-prompt skill, agent phase, ADR status

**Files:**
- Modify: `.claude/skills/lead-to-design-prompt/SKILL.md:21-41` (Inputs table) and the "Normalize and validate" list `:49-59`
- Modify: `agents/Design Prompt creator/phases/1-load-lead.md:36-56` (whitelist + photo injection)
- Modify: `docs/decisions/0012-google-maps-lead-import.md:3` (Status)
- Modify: `agents/Design Prompt creator/LEARNINGS.md` (append one dated line; never rewrite)

**Interfaces:**
- Produces: the skill and agent read `social_links`, `business_status`, `primary_type`, `types`, `price_level`, `extra.google` (summaries, attributes detail, photos with `owner_photo`), and apply two rules: owner photos are site assets, other photos are visual reference only; `generative_summary.overview` is research input, never quoted as the client's words.

- [ ] **Step 1: Extend the SKILL.md Inputs table** — add these rows after `facebook_url, instagram_url`:

```markdown
| `social_links` | no | `{facebook,instagram,tiktok,linkedin,youtube,x,pinterest,whatsapp}` → url. Source of truth for footer social icons; `facebook_url`/`instagram_url` are mirrors of two keys |
| `business_status` | no | `CLOSED_TEMPORARILY`/`CLOSED_PERMANENTLY` → add a status banner requirement; `FUTURE_OPENING` → "opening soon" hero framing |
| `primary_type`, `types` | no | Google place types (`barber_shop`, `hair_salon`…); use alongside `category` for bucket classification (step 2) |
| `price_level` | no | `free`…`very_expensive` → price-positioning copy ("affordable", "premium"); never print the raw enum |
| `extra.google.photos[]` | no | `{url, owner_photo, attributions[{name,uri}], google_maps_uri}`. **`owner_photo=true` → usable site imagery (list in `<imagery>` as real assets). `owner_photo=false` → visual reference for art direction only; never instruct the site to embed them** |
| `extra.google.generative_summary` | no | `{overview, disclosure}` — Google's AI summary. Research input for tone/positioning only; **never quote it as the business's own words** and never include `disclosure` in site copy |
| `extra.google.review_summary`, `extra.google.editorial_summary` | no | Same rule as above; `editorial_summary` already feeds `about` |
| `extra.google.price_range`, `extra.google.opening_hours.secondary` | no | Price range for menu/pricing section hints; secondary hours (e.g. delivery) → optional hours sub-widget |
```

In step 1 "Normalize and validate the lead", add:

```markdown
- `web_presence` values are `none`, `social_only`, `has_website`, `unknown` (the DB enum). Treat `has_website` as the old "ok/outdated" case: if `website_url` is set, flag it for a legacy-tone scrape.
- Build the imagery input from `extra.google.photos`: `owner_photos = [p.url for p in photos if p.owner_photo]`, `reference_photos = the rest`. Fall back to `photo_urls` as reference-only when `extra.google.photos` is absent (pre-ADR-0012 leads).
```

(The first bullet also fixes the pre-existing `none/social_only/outdated/ok` mismatch noted during planning — keep the change to that one line.)

- [ ] **Step 2: Extend `1-load-lead.md`** — whitelist becomes:

```
business_name, category, description, about, design_prompt,
country, region, city, address, postal_code, lat, lng,
phone, email, website_url, facebook_url, instagram_url, social_links,
menu_url, web_presence, source_url,
rating, review_count, reviews,
opening_hours, extra, notes, languages,
google_place_id, business_status, primary_type, types, price_level
```

and the photo injection becomes:

```python
extra = dict(lead.get("extra") or {})
google_photos = ((extra.get("google") or {}).get("photos")) or []
if google_photos:
    extra["owner_photo_urls"] = [p["url"] for p in google_photos if p.get("owner_photo") and p.get("url")]
    extra["reference_photo_urls"] = [p["url"] for p in google_photos if not p.get("owner_photo") and p.get("url")]
elif lead.get("photo_urls"):
    extra["reference_photo_urls"] = lead["photo_urls"]  # provenance unknown → reference only
projected["extra"] = extra
```

Append to `LEARNINGS.md` under `## General`:

```
- 2026-10-11: Leads imported from Google (ADR-0012) carry `extra.google.photos[].owner_photo`; only owner photos may be used as site assets. `generative_summary` is Google's text, never the client's. Triggered by: Google Maps import feature.
```

- [ ] **Step 3: ADR status** — change line 3 of `docs/decisions/0012-google-maps-lead-import.md` to `Status: Accepted`.

- [ ] **Step 4: Verify docs render and nothing else references the old enum text**

Run: `grep -rn "outdated/ok\|outdated\`/\`ok" .claude/skills/lead-to-design-prompt agents/"Design Prompt creator"` → expected: no matches. Run `cd backend && venv/Scripts/python -m pytest auth_service/tests -q -k "lead or google"` once more (docs-only task; this is a sanity check that the branch is still green).

- [ ] **Step 5: Commit**

```bash
git add .claude/skills/lead-to-design-prompt/SKILL.md "agents/Design Prompt creator/phases/1-load-lead.md" "agents/Design Prompt creator/LEARNINGS.md" docs/decisions/0012-google-maps-lead-import.md
git commit -m "docs: design-prompt skill reads Google import fields; ADR-0012 accepted"
```

---

## Controller checklist (after the tasks, before merge to `dev`)

These steps touch production or external accounts and are not part of any task:

1. **Google Cloud (Stefan, by hand):** create/select a Cloud project with billing, enable **Places API (New)** and **Maps Tools Resolution API**, create an API key restricted to those two APIs with no application restriction. In *Google Maps Platform → Quotas* set Place Details (New) and Place Photos to a low per-minute cap (e.g. 60) as a second safety net. Paste the key into `backend/.env` as `GOOGLE_MAPS_API_KEY=` and into Vercel `cms-backend-roman` (preview + production). Log nothing in `security/RUNBOOK.md` yet; it is a new secret, not a rotation — add it to the rotation table instead.
2. **Migration:** apply `backend/migrations/2026_10_11_lead_google_import.sql` with `python scripts/apply_supabase_migration.py …` (or Supabase MCP `apply_migration`) **before** merging to `dev`, since `LeadOut` would otherwise 500 on the missing columns once deployed. It is additive and safe on the live table. Confirm the `lead-photos` bucket exists in the Supabase dashboard afterwards (public = true).
3. **Full gate:** `make ci` in the worktree, then squash-merge `feat/google-maps-lead-import` into `dev` and push `dev` (Vercel preview deploys).
4. **Manual verification on the dev preview (prod DB — use a real business you can delete afterwards, e.g. samir-kapsalon's listing):**
   - paste the short link → lead created with name, address, phone, hours, ≥1 review, photos, `web_presence`; check `extra.google.generative_summary` is present for a Dutch listing (docs don't promise it outside the US — if `null`, nothing breaks, just note it in LEARNINGS);
   - import the same link again → 409 pointing at the lead;
   - paste "Samir Kapsalon Lelystad" → either direct hit or candidate list;
   - Re-import with overwrite → photos re-downloaded, pipeline fields untouched;
   - remove one photo → object gone from the `lead-photos` bucket;
   - set `GOOGLE_MAPS_API_KEY` empty on preview → 503 with the "not configured" message;
   - delete the test lead (DELETE leaves Storage objects behind — acceptable; `delete_lead_photos(sb, lead_id)` can be called from a shell if you want them gone).
5. **Promote** via "Promote dev → main" when the preview checks pass. Delete `docs/superpowers/plans/2026-10-11-google-maps-lead-import.md` once the work is stable (CLAUDE.md: plans are temporary; the ADR stays).
