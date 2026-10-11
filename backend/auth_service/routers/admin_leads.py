"""Admin-only CRUD over public.leads. Reads are paginated + filterable.
Writes are limited to pipeline-status and business-data fields (LeadUpdate)."""

from __future__ import annotations

import logging
import re
from datetime import UTC, datetime
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Query, Request, Response, status
from starlette.concurrency import run_in_threadpool

from ..core.config import settings
from ..core.pg_rate_limit import enforce
from ..models.schemas import GoogleImportIn, GoogleReimportIn, LeadCreate, LeadOut, LeadUpdate
from ..services.google_places.client import GooglePlacesError
from ..services.google_places.importer import (
    DuplicateLead,
    ImportOutcome,
    MissingPlaceId,
    MonthlyCapReached,
    QuotaUnavailable,
    import_place,
    reimport_place,
)
from ..services.google_places.photos import delete_lead_photos
from ..services.html_sanitizer import sanitize_design_prompt
from ..services.supabase_client import get_supabase_admin
from .deps import admin_user_via_bearer_or_sid

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/admin/leads", tags=["admin", "leads"])

# SEC-028: columns the list endpoint may sort by. Anything else falls back to
# created_at so a caller-supplied `sort` can't inject into the PostgREST order.
_SORTABLE_COLUMNS = frozenset(
    {
        "created_at",
        "updated_at",
        "business_name",
        "rating",
        "review_count",
        "lead_status",
        "lead_type",
        "category",
        "city",
        "country",
        "closed_amount",
    }
)


@router.get("", response_model=dict)
async def list_leads(
    request: Request,
    country: str | None = Query(None),
    city: str | None = Query(None),
    category: str | None = Query(None),
    web_presence: list[str] | None = Query(None),
    lead_status: list[str] | None = Query(None),
    lead_type: str | None = Query(None),
    min_rating: float | None = Query(None),
    max_rating: float | None = Query(None),
    min_reviews: int | None = Query(None),
    max_reviews: int | None = Query(None),
    search: str | None = Query(None),
    sort: str = Query("created_at"),
    desc: bool = Query(True),
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
) -> dict:
    await admin_user_via_bearer_or_sid(request)
    sb = get_supabase_admin()
    q = sb.table("leads").select("*", count="exact")
    if country:
        q = q.eq("country", country)
    if city:
        q = q.eq("city", city)
    if category:
        q = q.eq("category", category)
    if lead_type:
        q = q.eq("lead_type", lead_type)
    if web_presence:
        q = q.in_("web_presence", web_presence)
    if lead_status:
        q = q.in_("lead_status", lead_status)
    if min_rating is not None:
        q = q.gte("rating", min_rating)
    if max_rating is not None:
        q = q.lte("rating", max_rating)
    if min_reviews is not None:
        q = q.gte("review_count", min_reviews)
    if max_reviews is not None:
        q = q.lte("review_count", max_reviews)
    if search:
        q = q.ilike("business_name", f"%{search}%")

    # SEC-028: `sort` is a caller-controlled column name passed to PostgREST
    # .order(); allowlist it so it can't be used for filter/column injection.
    if sort not in _SORTABLE_COLUMNS:
        sort = "created_at"
    q = q.order(sort, desc=desc).range(offset, offset + limit - 1)
    res = q.execute()
    items = [LeadOut(**row).model_dump() for row in (res.data or [])]
    return {"items": items, "total": getattr(res, "count", None) or len(items)}


@router.post("", response_model=LeadOut, status_code=status.HTTP_201_CREATED)
async def create_lead(body: LeadCreate, request: Request) -> LeadOut:
    """Manually create a lead from the admin dashboard. A manual insert sets
    primary_source='manual' and a generated external_id as a stable unique key."""
    await admin_user_via_bearer_or_sid(request)
    sb = get_supabase_admin()

    row = dict(body.model_dump(exclude_none=True))
    # _LeadEmail/_LeadUrl are annotated str types; Supabase wants plain strings.
    for key in ("email", "website_url", "facebook_url", "instagram_url", "menu_url"):
        if key in row and row[key] is not None:
            row[key] = str(row[key])

    row["primary_source"] = "manual"
    row["external_id"] = f"manual:{uuid4()}"
    # name_normalized is NOT NULL; lower + collapse whitespace.
    row["name_normalized"] = re.sub(r"\s+", " ", body.business_name.lower()).strip()

    res = sb.table("leads").insert(row).execute()
    if not res.data:
        raise HTTPException(status_code=500, detail="Insert failed")
    return LeadOut(**res.data[0])


_GOOGLE_STATUS = {400: 422, 401: 502, 403: 502, 404: 404, 429: 503, 504: 504}


def _google_http(e: GooglePlacesError) -> HTTPException:
    if e.status == 503:
        return HTTPException(status_code=503, detail=e.message)
    code = _GOOGLE_STATUS.get(e.status, 502)
    prefix = {
        404: "Place not found",
        422: "Google rejected the request",
        503: "Google quota exceeded, try later",
        504: "Google did not answer in time",
    }.get(code, "Google Places error")
    return HTTPException(status_code=code, detail=f"{prefix}: {e.message}")


def _require_google_key() -> None:
    if not settings.GOOGLE_MAPS_API_KEY:
        raise HTTPException(
            status_code=503, detail="Google Maps import is not configured on this backend"
        )


def _outcome_response(outcome: ImportOutcome, response: Response, *, created: bool):
    response.headers["X-Import-Warnings"] = str(len(outcome.warnings))
    if outcome.lead is None:
        if not outcome.candidates:
            raise HTTPException(
                status_code=404,
                detail="Could not find a place for that input. Try the full Google Maps link or 'Name, City'.",
            )
        response.status_code = 200
        return {
            "status": "candidates",
            "candidates": outcome.candidates,
            "warnings": outcome.warnings,
        }
    response.status_code = 201 if created else 200
    return LeadOut(**outcome.lead)


async def _run_import(fn, response: Response, *, created: bool):
    try:
        # the importer does blocking HTTP + DB calls; keep them off the event loop
        outcome = await run_in_threadpool(fn)
    except DuplicateLead as e:
        raise HTTPException(
            status_code=409,
            detail={"message": "This Google place is already a lead.", "lead_id": e.lead_id},
        ) from e
    except MonthlyCapReached as e:
        raise HTTPException(
            status_code=429,
            detail="Monthly Google import cap reached (GOOGLE_PLACES_MONTHLY_CAP). Raise it on cms-backend-roman if you accept the cost.",
        ) from e
    except QuotaUnavailable as e:
        raise HTTPException(
            status_code=503, detail="Import counter unavailable; try again shortly."
        ) from e
    except GooglePlacesError as e:
        raise _google_http(e) from e
    except MissingPlaceId as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    return _outcome_response(outcome, response, created=created)


@router.post("/google-import", response_model=None, status_code=status.HTTP_201_CREATED)
async def google_import(body: GoogleImportIn, request: Request, response: Response):
    """Create a lead from a Google Maps link / place ID / 'Name, City' (ADR-0012)."""
    user = await admin_user_via_bearer_or_sid(request)
    _require_google_key()
    enforce(
        f"google_import:user:{user.id}",
        20,
        3600,
        detail="Too many imports this hour; try again later.",
    )
    raw = body.input.strip()
    if not raw:
        raise HTTPException(422, "Paste a Google Maps link, place ID or 'Name, City'.")
    sb = get_supabase_admin()
    return await _run_import(
        lambda: import_place(sb, raw_input=raw, lead_type=body.lead_type, language=body.language),
        response,
        created=True,
    )


@router.post("/{lead_id}/google-import", response_model=None)
async def google_reimport(
    lead_id: str, body: GoogleReimportIn, request: Request, response: Response
):
    """Refresh an existing lead from Google: fill empty fields, or overwrite=true."""
    user = await admin_user_via_bearer_or_sid(request)
    _require_google_key()
    enforce(
        f"google_import:user:{user.id}",
        20,
        3600,
        detail="Too many imports this hour; try again later.",
    )
    sb = get_supabase_admin()
    current = sb.table("leads").select("*").eq("id", lead_id).maybe_single().execute()
    if not (current and current.data):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lead not found")
    raw = body.input.strip() if body.input else None
    return await _run_import(
        lambda: reimport_place(
            sb, current.data, raw_input=raw, overwrite=body.overwrite, language=body.language
        ),
        response,
        created=False,
    )


@router.get("/{lead_id}", response_model=LeadOut)
async def get_lead(lead_id: str, request: Request) -> LeadOut:
    await admin_user_via_bearer_or_sid(request)
    sb = get_supabase_admin()
    res = sb.table("leads").select("*").eq("id", lead_id).maybe_single().execute()
    if not res.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lead not found")
    return LeadOut(**res.data)


@router.patch("/{lead_id}", response_model=LeadOut)
async def patch_lead(lead_id: str, body: LeadUpdate, request: Request) -> LeadOut:
    await admin_user_via_bearer_or_sid(request)
    sb = get_supabase_admin()
    # exclude_unset (not exclude_none) is the correct PATCH semantic: a key
    # explicitly sent as null means "clear this column", a key omitted means
    # "don't touch". Using exclude_none would conflate the two and make it
    # impossible to clear closed_amount/notes via the admin UI.
    patch = dict(body.model_dump(exclude_unset=True))
    # _LeadEmail is a custom annotated type; Supabase wants a plain string.
    if "email" in patch and patch["email"] is not None:
        patch["email"] = str(patch["email"])
    if "design_prompt" in patch and patch["design_prompt"] is not None:
        patch["design_prompt"] = sanitize_design_prompt(patch["design_prompt"])
    if not patch:
        raise HTTPException(status_code=422, detail="No fields to update")

    # Gate closed_amount writes on lead_status='accepted' — either the current
    # row is already accepted, OR this same PATCH transitions it to accepted.
    # about_attributes is a virtual field that must be merged into extra.
    # A single fetch covers both branches when either is in the patch.
    needs_current = any(
        k in patch
        for k in (
            "closed_amount",
            "about_attributes",
            "social_links",
            "facebook_url",
            "instagram_url",
            "photo_urls",
        )
    )
    if needs_current:
        current = (
            sb.table("leads")
            .select("lead_status, closed_amount, extra, social_links, photo_urls")
            .eq("id", lead_id)
            .maybe_single()
            .execute()
        )
        if not (current and current.data):
            raise HTTPException(status_code=404, detail="Lead not found")

    if "closed_amount" in patch:
        new_status = patch.get("lead_status", current.data["lead_status"])
        if new_status != "accepted":
            raise HTTPException(
                status_code=422,
                detail="closed_amount can only be set when lead_status is 'accepted'",
            )
        # Auto-set closed_at on first non-null write.
        if current.data["closed_amount"] is None and patch["closed_amount"] is not None:
            patch["closed_at"] = datetime.now(UTC).isoformat()

    if "about_attributes" in patch:
        new_attrs = patch.pop("about_attributes")
        current_extra = current.data.get("extra") or {}
        if not isinstance(current_extra, dict):
            current_extra = {}
        current_extra["attributes"] = new_attrs
        patch["extra"] = current_extra

    # ADR-0012: social_links is the full map; facebook_url/instagram_url mirror two keys.
    if "social_links" in patch:
        links = patch["social_links"] or {}
        patch["social_links"] = links
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
    dropped: list[str] = []
    if "photo_urls" in patch:
        new_urls = list(patch["photo_urls"] or [])
        dropped = [u for u in (current.data.get("photo_urls") or []) if u not in new_urls]
        extra = patch.get("extra") or dict(current.data.get("extra") or {})
        google = dict(extra.get("google") or {})
        if google.get("photos"):
            google["photos"] = [p for p in google["photos"] if p.get("url") in new_urls]
            extra["google"] = google
            patch["extra"] = extra

    res = sb.table("leads").update(patch).eq("id", lead_id).execute()
    if not res.data:
        raise HTTPException(status_code=500, detail="Update failed")
    if dropped:
        try:
            delete_lead_photos(sb, lead_id, dropped)
        except Exception:  # noqa: BLE001 — row is already consistent; orphaned objects are harmless
            logger.exception("lead %s: dropped photo cleanup failed", lead_id)
    return LeadOut(**res.data[0])


@router.delete("/{lead_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_lead(lead_id: str, request: Request) -> None:
    """Hard-delete a lead. The delete returns the removed rows, so an empty
    result means the id did not exist."""
    await admin_user_via_bearer_or_sid(request)
    sb = get_supabase_admin()
    res = sb.table("leads").delete().eq("id", lead_id).execute()
    if not res.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lead not found")
