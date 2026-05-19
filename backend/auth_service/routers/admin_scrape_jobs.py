"""Admin queue management — create scrape jobs from the form, list,
cancel pending. The scraper worker is the only consumer of `status`
transitions to `running`/`done`/`failed`."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Request, status

from ..models.schemas import ScrapeJobCreate, ScrapeJobOut
from ..services.supabase_client import get_supabase_admin
from .deps import admin_user_via_bearer_or_sid

router = APIRouter(prefix="/admin/scrape-jobs", tags=["admin", "scrape-jobs"])


@router.get("", response_model=list[ScrapeJobOut])
async def list_jobs(
    request: Request,
    status_filter: str | None = Query(None, alias="status"),
    limit: int = Query(50, le=200),
) -> list[ScrapeJobOut]:
    await admin_user_via_bearer_or_sid(request)
    sb = get_supabase_admin()
    q = sb.table("scrape_jobs").select("*").order("created_at", desc=True).limit(limit)
    if status_filter:
        q = q.eq("status", status_filter)
    res = q.execute()
    return [ScrapeJobOut(**row) for row in (res.data or [])]


@router.get("/{job_id}", response_model=ScrapeJobOut)
async def get_job(job_id: str, request: Request) -> ScrapeJobOut:
    await admin_user_via_bearer_or_sid(request)
    sb = get_supabase_admin()
    res = sb.table("scrape_jobs").select("*").eq("id", job_id).maybe_single().execute()
    if not res.data:
        raise HTTPException(status_code=404, detail="Job not found")
    return ScrapeJobOut(**res.data)


@router.post("", response_model=ScrapeJobOut, status_code=status.HTTP_201_CREATED)
async def create_job(body: ScrapeJobCreate, request: Request) -> ScrapeJobOut:
    await admin_user_via_bearer_or_sid(request)
    sb = get_supabase_admin()
    res = (
        sb.table("scrape_jobs")
        .insert({"params": body.params.model_dump(), "triggered_by": "cms"})
        .execute()
    )
    if not res.data:
        raise HTTPException(status_code=500, detail="Job could not be created")
    return ScrapeJobOut(**res.data[0])


@router.patch("/{job_id}", response_model=ScrapeJobOut)
async def cancel_job(job_id: str, body: dict, request: Request) -> ScrapeJobOut:
    await admin_user_via_bearer_or_sid(request)
    if body.get("status") != "cancelled":
        raise HTTPException(status_code=422, detail="Only status=cancelled is allowed via PATCH")
    sb = get_supabase_admin()
    existing = sb.table("scrape_jobs").select("status").eq("id", job_id).maybe_single().execute()
    if not existing.data:
        raise HTTPException(status_code=404, detail="Job not found")
    if existing.data["status"] != "pending":
        raise HTTPException(status_code=409, detail="Only pending jobs can be cancelled")
    res = sb.table("scrape_jobs").update({"status": "cancelled"}).eq("id", job_id).execute()
    return ScrapeJobOut(**res.data[0])
