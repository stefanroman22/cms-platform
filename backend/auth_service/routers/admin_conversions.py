"""Admin-only aggregations over public.leads for the Conversions tab."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from fastapi import APIRouter, Query, Request

from ..models.schemas import (
    ConversionBreakdownRow,
    ConversionSummary,
    ConversionTimePoint,
)
from ..services.supabase_client import get_supabase_admin
from .deps import admin_user_via_bearer_or_sid

router = APIRouter(prefix="/admin/conversions", tags=["admin", "conversions"])

_PIPELINE_STATUSES = ("sent", "accepted", "refused")


def _month_key(iso_ts: str | None) -> str | None:
    if not iso_ts:
        return None
    return iso_ts[:7]


def _safe_div(num: float, den: float) -> float:
    return num / den if den else 0.0


@router.get("/summary", response_model=ConversionSummary)
async def conversion_summary(
    request: Request,
    lead_type: str | None = Query(None),
    city: str | None = Query(None),
    category: str | None = Query(None),
    since: str | None = Query(None, description="ISO month or date; filters closed_at >= since"),
) -> ConversionSummary:
    await admin_user_via_bearer_or_sid(request)
    sb = get_supabase_admin()

    q = (
        sb.table("leads")
        .select("lead_status, closed_amount, closed_at, lead_type, category, city")
        .in_("lead_status", list(_PIPELINE_STATUSES))
    )
    if lead_type:
        q = q.eq("lead_type", lead_type)
    if city:
        q = q.eq("city", city)
    if category:
        q = q.eq("category", category)
    rows: list[dict[str, Any]] = q.execute().data or []

    if since:
        rows = [
            r for r in rows if (r.get("closed_at") or "") >= since or r["lead_status"] != "accepted"
        ]

    total_sent = sum(1 for r in rows if r["lead_status"] == "sent")
    total_accepted = sum(1 for r in rows if r["lead_status"] == "accepted")
    total_refused = sum(1 for r in rows if r["lead_status"] == "refused")
    total_revenue = sum(float(r["closed_amount"]) for r in rows if r["closed_amount"] is not None)
    denom = total_sent + total_accepted + total_refused
    conversion_rate = _safe_div(total_accepted, denom)
    average_deal_size = _safe_div(total_revenue, total_accepted)

    by_month_rev: dict[str, float] = defaultdict(float)
    by_month_acc: dict[str, int] = defaultdict(int)
    by_month_sent: dict[str, int] = defaultdict(int)
    for r in rows:
        m = _month_key(r.get("closed_at"))
        if r["lead_status"] == "accepted" and m:
            by_month_rev[m] += float(r["closed_amount"] or 0)
            by_month_acc[m] += 1
        if m:
            by_month_sent[m] += 1
    timeseries = sorted(
        (
            ConversionTimePoint(
                month=m,
                revenue=by_month_rev[m],
                accepted=by_month_acc[m],
                sent=by_month_sent[m],
            )
            for m in set(by_month_rev) | set(by_month_acc) | set(by_month_sent)
        ),
        key=lambda p: p.month,
    )

    def _group_by(key: str) -> list[ConversionBreakdownRow]:
        acc: dict[str, dict[str, float]] = defaultdict(lambda: {"accepted": 0, "revenue": 0.0})
        for r in rows:
            if r["lead_status"] != "accepted":
                continue
            k = r.get(key) or "(unknown)"
            acc[k]["accepted"] += 1
            acc[k]["revenue"] += float(r["closed_amount"] or 0)
        return sorted(
            (
                ConversionBreakdownRow(key=k, accepted=int(v["accepted"]), revenue=v["revenue"])
                for k, v in acc.items()
            ),
            key=lambda r: r.revenue,
            reverse=True,
        )

    return ConversionSummary(
        total_sent=total_sent,
        total_accepted=total_accepted,
        total_refused=total_refused,
        conversion_rate=conversion_rate,
        total_revenue=total_revenue,
        average_deal_size=average_deal_size,
        timeseries=timeseries,
        by_lead_type=_group_by("lead_type"),
        by_category=_group_by("category"),
        by_city=_group_by("city"),
    )
