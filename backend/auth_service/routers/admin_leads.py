"""Admin-only CRUD over public.leads. Reads are paginated + filterable.
Writes are limited to pipeline-status and scraped-data fields (LeadUpdate)."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, Query, Request, status

from ..models.schemas import LeadOut, LeadUpdate
from ..services.html_sanitizer import sanitize_design_prompt
from ..services.supabase_client import get_supabase_admin
from .deps import admin_user_via_bearer_or_sid

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
        "ai_score",
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
    min_ai_score: int | None = Query(None),
    max_ai_score: int | None = Query(None),
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
    if min_ai_score is not None:
        q = q.gte("ai_score", min_ai_score)
    if max_ai_score is not None:
        q = q.lte("ai_score", max_ai_score)
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
    needs_current = "closed_amount" in patch or "about_attributes" in patch
    if needs_current:
        current = (
            sb.table("leads")
            .select("lead_status, closed_amount, extra")
            .eq("id", lead_id)
            .maybe_single()
            .execute()
        )
        if not current.data:
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

    res = sb.table("leads").update(patch).eq("id", lead_id).execute()
    if not res.data:
        raise HTTPException(status_code=500, detail="Update failed")
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
