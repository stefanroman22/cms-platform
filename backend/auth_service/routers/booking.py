"""Multi-tenant booking API. Public booking flows are keyed by a tenant
public_slug resolved server-side; the anon/browser never sends a tenant id.
Authorization is app-layer with the service-role client (RLS stays
enabled-no-policy). The slot engine and DB I/O live in the booking_* services."""

from __future__ import annotations

import hashlib
import hmac
import logging
import re
import secrets
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from ..core import pg_rate_limit
from ..core.config import settings
from ..core.limiter import client_ip, limiter
from ..models.booking_contract import BOOKING_CONTRACT
from ..services import (
    booking_availability,
    booking_email,
    booking_manage_email,
    booking_reminder_email,
    booking_repo,
    booking_tenant,
    calendar_provider,
)
from ..services.booking_availability import ResourceAvailability
from ..services.booking_repo import BookingConflict
from ..services.booking_tenant import TenantConfig
from ..services.email_layout import DEFAULT_BRAND, Brand

router = APIRouter(prefix="/booking", tags=["booking"])
log = logging.getLogger(__name__)

_EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
_UTC = ZoneInfo("UTC")


def _brand_for(cfg: TenantConfig) -> Brand:
    """Build a Brand from a TenantConfig, falling back to DEFAULT_BRAND fields.
    The email accent comes from the editor's `accent_color`; `primary_color` is a
    legacy fallback (older settings stored the brand color there)."""
    accent = cfg.accent_color or cfg.primary_color
    if not cfg.business_name and not cfg.logo_url and not accent:
        return DEFAULT_BRAND
    return Brand(
        business_name=cfg.business_name or DEFAULT_BRAND.business_name,
        logo_url=cfg.logo_url or DEFAULT_BRAND.logo_url,
        accent=accent or DEFAULT_BRAND.accent,
        # Footer "Sent from <site>" points at the CLIENT's live website (never
        # roman-technologies.dev). Falls back to the manage host only if unset.
        canonical_url=cfg.website_url or settings.manage_base_url or DEFAULT_BRAND.canonical_url,
    )


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _require_tenant(slug: str) -> TenantConfig:
    cfg = booking_tenant.load_tenant_by_slug(slug)
    if cfg is None:
        raise HTTPException(status_code=404, detail="Unknown booking page")
    return cfg


def _hours_for_weekday(
    hours_rows: list[dict], resource_id: str, weekday: int
) -> list[tuple[time, time]]:
    """Per-resource hours if the resource has its own rows, else business-level
    (resource_id null). `weekday` is Postgres dow (0=Sun)."""
    own = [h for h in hours_rows if h.get("resource_id") == resource_id]
    src = own if own else [h for h in hours_rows if h.get("resource_id") is None]
    out: list[tuple[time, time]] = []
    for h in src:
        if h["weekday"] == weekday:
            out.append((time.fromisoformat(h["start_time"]), time.fromisoformat(h["end_time"])))
    return out


def _exception_for(exc_rows: list[dict], resource_id: str, day: date) -> dict | None:
    iso = day.isoformat()
    cands = [
        e
        for e in exc_rows
        if e["date"] == iso
        and (e.get("resource_id") == resource_id or e.get("resource_id") is None)
    ]
    if not cands:
        return None
    e = cands[0]
    return {
        "is_closed": e["is_closed"],
        "start_time": time.fromisoformat(e["start_time"]) if e.get("start_time") else None,
        "end_time": time.fromisoformat(e["end_time"]) if e.get("end_time") else None,
    }


def _build_resource_availability(
    *,
    cfg: TenantConfig,
    resources: list[dict],
    hours_rows: list[dict],
    exc_rows: list[dict],
    day: date,
    window_start: datetime,
    window_end: datetime,
    exclude_booking_id: str | None = None,
) -> list[ResourceAvailability]:
    dow = day.isoweekday() % 7  # ISO Mon=1..Sun=7 -> dow Sun=0..Sat=6
    rids = [r["id"] for r in resources]
    busy = booking_repo.busy_guard_intervals_by_resource(
        tenant_id=cfg.tenant_id,
        resource_ids=rids,
        window_start_utc=window_start,
        window_end_utc=window_end,
        exclude_booking_id=exclude_booking_id,
    )
    # Calendar busy (tenant #1 / google) blocks every resource — it is the host's
    # personal calendar. Noop providers return []. Best-effort: a fetch failure
    # falls back to DB-only availability.
    cal_busy: list[tuple[datetime, datetime]] = []
    if cfg.calendar_provider != "none":
        try:
            cal_busy = calendar_provider.provider_for(cfg.calendar_provider).list_busy(
                window_start, window_end
            )
        except Exception:  # noqa: BLE001
            log.exception("calendar busy fetch failed; supabase-only availability")
    out: list[ResourceAvailability] = []
    for r in resources:
        out.append(
            ResourceAvailability(
                resource_id=r["id"],
                hours=_hours_for_weekday(hours_rows, r["id"], dow),
                exception=_exception_for(exc_rows, r["id"], day),
                busy=busy.get(r["id"], []) + cal_busy,
            )
        )
    return out


def _availability_for_day(
    *, cfg: TenantConfig, service: dict, day: date, now_utc: datetime
) -> list[datetime]:
    resources = booking_repo.load_eligible_resources(cfg.tenant_id, service["id"])
    if not resources:
        return []
    tz = ZoneInfo(cfg.timezone)
    win_start = datetime.combine(day, time(0, 0), tzinfo=tz).astimezone(_UTC) - timedelta(days=1)
    win_end = win_start + timedelta(days=3)
    hours_rows = booking_repo.load_hours(cfg.tenant_id)
    exc_rows = booking_repo.load_exceptions(cfg.tenant_id, day.isoformat(), day.isoformat())
    avail = _build_resource_availability(
        cfg=cfg,
        resources=resources,
        hours_rows=hours_rows,
        exc_rows=exc_rows,
        day=day,
        window_start=win_start,
        window_end=win_end,
    )
    return booking_availability.available_starts(
        day=day,
        now_utc=now_utc,
        tz_name=cfg.timezone,
        duration_min=service["duration_min"],
        buffer_before_min=service["buffer_before_min"],
        buffer_after_min=service["buffer_after_min"],
        granularity_min=cfg.slot_granularity_min,
        lead_time_min=service["lead_time_min"],
        max_advance_days=service["max_advance_days"],
        resources=avail,
    )


def _free_resource_for(
    *,
    cfg: TenantConfig,
    service: dict,
    start_utc: datetime,
    now_utc: datetime,
    exclude_booking_id: str | None = None,
    prefer_resource_id: str | None = None,
) -> str | None:
    """Free eligible resource for `start_utc`, or None.
    `exclude_booking_id` omits that booking from the busy set (used on reschedule
    so a booking never collides with its own current guard interval).
    `prefer_resource_id` (the customer's chosen barber): if set, return that
    resource only when it is eligible AND free — never silently substitute another
    barber; if blank, fall back to the least-loaded free eligible resource."""
    resources = booking_repo.load_eligible_resources(cfg.tenant_id, service["id"])
    if prefer_resource_id:
        resources = [r for r in resources if r["id"] == prefer_resource_id]
        if not resources:
            return None  # requested barber cannot perform this service
    if not resources:
        return None
    day = start_utc.astimezone(ZoneInfo(cfg.timezone)).date()
    tz = ZoneInfo(cfg.timezone)
    win_start = datetime.combine(day, time(0, 0), tzinfo=tz).astimezone(_UTC) - timedelta(days=1)
    win_end = win_start + timedelta(days=3)
    hours_rows = booking_repo.load_hours(cfg.tenant_id)
    exc_rows = booking_repo.load_exceptions(cfg.tenant_id, day.isoformat(), day.isoformat())
    avail = _build_resource_availability(
        cfg=cfg,
        resources=resources,
        hours_rows=hours_rows,
        exc_rows=exc_rows,
        day=day,
        window_start=win_start,
        window_end=win_end,
        exclude_booking_id=exclude_booking_id,
    )
    free = booking_availability.free_resource_ids_at(
        start_utc=start_utc,
        day=day,
        tz_name=cfg.timezone,
        duration_min=service["duration_min"],
        buffer_before_min=service["buffer_before_min"],
        buffer_after_min=service["buffer_after_min"],
        granularity_min=cfg.slot_granularity_min,
        resources=avail,
    )
    if prefer_resource_id:
        return prefer_resource_id if prefer_resource_id in free else None
    # least-loaded = fewest existing busy intervals among free resources
    busy_count = {r.resource_id: len(r.busy) for r in avail}
    free.sort(key=lambda rid: busy_count.get(rid, 0))
    return free[0] if free else None


def _availability_for_range(
    *,
    cfg: TenantConfig,
    service: dict,
    d0: date,
    d1: date,
    now_utc: datetime,
    resource_id: str | None = None,
) -> list[dict]:
    """Batched availability for a whole date range. Loads resources/hours/
    exceptions/busy (and calendar busy) ONCE for the range, then computes each
    day purely — vs. _availability_for_day which re-queries per day (fine for a
    single day, far too slow for a month). Returns
    [{"date": "YYYY-MM-DD", "starts": [datetime, ...]}] for days with >=1 slot.
    `resource_id` (the customer's chosen barber): restricts the computation to that
    single barber's own calendar; an ineligible id yields no days."""
    resources = booking_repo.load_eligible_resources(cfg.tenant_id, service["id"])
    if resource_id:
        resources = [r for r in resources if r["id"] == resource_id]
    if not resources:
        return []
    tz = ZoneInfo(cfg.timezone)
    win_start = datetime.combine(d0, time(0, 0), tzinfo=tz).astimezone(_UTC) - timedelta(days=1)
    win_end = datetime.combine(d1, time(0, 0), tzinfo=tz).astimezone(_UTC) + timedelta(days=2)
    hours_rows = booking_repo.load_hours(cfg.tenant_id)
    exc_rows = booking_repo.load_exceptions(cfg.tenant_id, d0.isoformat(), d1.isoformat())
    rids = [r["id"] for r in resources]
    busy = booking_repo.busy_guard_intervals_by_resource(
        tenant_id=cfg.tenant_id,
        resource_ids=rids,
        window_start_utc=win_start,
        window_end_utc=win_end,
    )
    cal_busy: list[tuple[datetime, datetime]] = []
    if cfg.calendar_provider != "none":
        try:
            cal_busy = calendar_provider.provider_for(cfg.calendar_provider).list_busy(
                win_start, win_end
            )
        except Exception:  # noqa: BLE001
            log.exception("calendar busy fetch failed; supabase-only availability")
    out: list[dict] = []
    cur = d0
    while cur <= d1:
        dow = cur.isoweekday() % 7
        avail = [
            ResourceAvailability(
                resource_id=r["id"],
                hours=_hours_for_weekday(hours_rows, r["id"], dow),
                exception=_exception_for(exc_rows, r["id"], cur),
                busy=busy.get(r["id"], []) + cal_busy,
            )
            for r in resources
        ]
        starts = booking_availability.available_starts(
            day=cur,
            now_utc=now_utc,
            tz_name=cfg.timezone,
            duration_min=service["duration_min"],
            buffer_before_min=service["buffer_before_min"],
            buffer_after_min=service["buffer_after_min"],
            granularity_min=cfg.slot_granularity_min,
            lead_time_min=service["lead_time_min"],
            max_advance_days=service["max_advance_days"],
            resources=avail,
        )
        if starts:
            out.append({"date": cur.isoformat(), "starts": starts})
        cur += timedelta(days=1)
    return out


def _range_to_grouped(rng: list[dict]) -> dict:
    """Shape _availability_for_range output as the API's grouped response:
    {"days": [{"date": ..., "slots": [{"start_utc": iso}, ...]}, ...]}."""
    return {
        "days": [
            {"date": d["date"], "slots": [{"start_utc": s.isoformat()} for s in d["starts"]]}
            for d in rng
        ]
    }


def _when_label(start_utc: datetime, tz_name: str) -> str:
    local = start_utc.astimezone(ZoneInfo(tz_name))
    return local.strftime("%a, %d %b %Y · %H:%M ") + f"({tz_name})"


# ---------- slug-scoped public API ----------


def _public_read_limit(request: Request) -> None:
    """SEC-010/012/030/035: shared per-IP limit on the unauthenticated booking read
    endpoints (config/services/availability/manage). Backed by the Postgres limiter
    so it holds across serverless instances; generous enough for real widget use."""
    pg_rate_limit.enforce(
        f"booking_read:{client_ip(request)}",
        limit=120,
        window_seconds=60,
        detail="Too many requests. Please slow down and try again.",
    )


@router.get("/{slug}/config", dependencies=[Depends(_public_read_limit)])
def public_config(slug: str) -> JSONResponse:
    cfg = booking_tenant.load_tenant_by_slug(slug)
    if cfg is None:
        raise HTTPException(status_code=404, detail="Unknown booking page")
    return JSONResponse(
        content={
            "public_slug": cfg.public_slug,
            "business_name": cfg.business_name,
            "primary_color": cfg.primary_color,
            "accent_color": cfg.accent_color,
            "widget_color": cfg.widget_color,
            "logo_url": cfg.logo_url,
            "locale": cfg.locale,
        }
    )


@router.get("/{slug}/services", dependencies=[Depends(_public_read_limit)])
def list_services(slug: str) -> JSONResponse:
    cfg = _require_tenant(slug)
    services = booking_repo.load_active_services(cfg.tenant_id)
    return JSONResponse(
        content={
            "services": [
                {
                    "id": s["id"],
                    "name": s["name"],
                    "duration_min": s["duration_min"],
                    # Postgres numeric comes back as a string via PostgREST — coerce to
                    # a JSON number so clients can format it without parsing.
                    "price": float(s["price"]) if s.get("price") is not None else None,
                }
                for s in services
            ]
        }
    )


@router.get("/{slug}/resources", dependencies=[Depends(_public_read_limit)])
def list_resources(slug: str, service_id: str = Query("")) -> JSONResponse:
    """Active bookable resources (barbers/staff) for the barber-selection step.
    With `service_id`, returns only those eligible to perform that service; without
    it, all active resources. The UI auto-adjusts as the admin adds/removes staff."""
    cfg = _require_tenant(slug)
    if service_id.strip():
        resources = booking_repo.load_eligible_resources(cfg.tenant_id, service_id.strip())
    else:
        resources = booking_repo.load_active_resources(cfg.tenant_id)
    return JSONResponse(
        content={
            "resources": [
                {"id": r["id"], "name": r["name"], "type": r.get("type", "generic")}
                for r in resources
            ]
        }
    )


@router.get("/{slug}/availability", dependencies=[Depends(_public_read_limit)])
def availability(
    slug: str,
    service_id: str,
    from_: str = Query(..., alias="from"),
    to: str = Query(...),
    resource_id: str = Query(""),
) -> JSONResponse:
    cfg = _require_tenant(slug)
    service = booking_repo.load_service(cfg.tenant_id, service_id)
    if service is None:
        raise HTTPException(status_code=404, detail="Unknown service")
    try:
        d0 = datetime.strptime(from_, "%Y-%m-%d").date()
        d1 = datetime.strptime(to, "%Y-%m-%d").date()
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="Bad range") from exc
    rng = _availability_for_range(
        cfg=cfg,
        service=service,
        d0=d0,
        d1=d1,
        now_utc=datetime.now(UTC),
        resource_id=resource_id.strip() or None,
    )
    return JSONResponse(content=_range_to_grouped(rng))


@router.get("/{slug}/contract", dependencies=[Depends(_public_read_limit)])
def public_contract(slug: str) -> JSONResponse:
    """Machine-readable create-booking contract (version + required fields +
    per-field types). The SDK + connector validate against this; serving it
    behind the slug keeps the public-read surface consistent."""
    _require_tenant(slug)
    return JSONResponse(content=BOOKING_CONTRACT)


class CustomerIn(BaseModel):
    name: str
    email: str
    phone: str = ""
    locale: str = ""
    tz: str = ""


class CreateIn(BaseModel):
    service_id: str
    resource_id: str = ""
    start_utc: str
    customer: CustomerIn
    note: str = ""
    website: str = ""  # honeypot


@router.post("/{slug}")
@limiter.limit("5/hour", key_func=client_ip)
async def create_booking(request: Request, slug: str, body: CreateIn) -> JSONResponse:
    cfg = _require_tenant(slug)
    return _create_core(cfg, body)


def _create_core(cfg: TenantConfig, body: CreateIn) -> JSONResponse:
    """Shared create path for the slug route and the tenant-#1 legacy shim.
    Sync (supabase-py is sync); both callers are async route handlers."""
    if body.website.strip():
        return JSONResponse(content={"success": True})
    name = body.customer.name.strip()
    email = body.customer.email.strip()
    note = body.note.strip()
    # Field-level validation errors (which field, why) so a miswired client form
    # gets actionable diagnostics instead of a generic 422. Order matches the
    # contract's `required` list. Behaviour-preserving for already-valid payloads.
    if not body.service_id.strip():
        raise HTTPException(
            status_code=422,
            detail={"field": "service_id", "message": "service_id is required"},
        )
    if not name:
        raise HTTPException(
            status_code=422,
            detail={"field": "customer.name", "message": "customer.name is required"},
        )
    if not _EMAIL_RE.match(email):
        raise HTTPException(
            status_code=422,
            detail={"field": "customer.email", "message": "customer.email is invalid"},
        )
    service = booking_repo.load_service(cfg.tenant_id, body.service_id)
    if service is None:
        raise HTTPException(status_code=404, detail="Unknown service")
    try:
        start = datetime.fromisoformat(body.start_utc).astimezone(_UTC)
    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail={"field": "start_utc", "message": "start_utc must be an ISO-8601 datetime"},
        ) from exc

    now = datetime.now(UTC)
    resource_id = _free_resource_for(
        cfg=cfg,
        service=service,
        start_utc=start,
        now_utc=now,
        prefer_resource_id=body.resource_id.strip() or None,
    )
    if resource_id is None:
        raise HTTPException(status_code=409, detail="That time was just taken")

    end = start + timedelta(minutes=service["duration_min"])
    guard_start = start - timedelta(minutes=service["buffer_before_min"])
    guard_end = end + timedelta(minutes=service["buffer_after_min"])
    raw_token = secrets.token_urlsafe(32)

    customer_id = booking_repo.upsert_customer(
        tenant_id=cfg.tenant_id,
        name=name,
        email=email,
        phone=body.customer.phone or None,
        locale=body.customer.locale or cfg.locale,
        timezone=body.customer.tz or cfg.timezone,
    )
    try:
        booking_id = booking_repo.insert_booking(
            tenant_id=cfg.tenant_id,
            service_id=service["id"],
            resource_id=resource_id,
            customer_id=customer_id,
            customer_name=name,
            start_utc=start,
            end_utc=end,
            guard_start_utc=guard_start,
            guard_end_utc=guard_end,
            manage_token_hash=_hash_token(raw_token),
            source="widget",
            notes=note or None,
        )
    except BookingConflict as exc:
        raise HTTPException(status_code=409, detail="That time was just taken") from exc

    booking_repo.insert_audit(
        tenant_id=cfg.tenant_id,
        booking_id=booking_id,
        action="create",
        actor="customer",
        payload={"resource_id": resource_id},
    )

    provider = calendar_provider.provider_for(cfg.calendar_provider)
    try:
        event_id = provider.create_event(
            start_utc=start,
            end_utc=end,
            name=name,
            email=email,
            note=note,
            meeting_url=cfg.meeting_url,
        )
        if event_id:
            booking_repo.update_booking(booking_id, {"google_event_id": event_id})
    except Exception:  # noqa: BLE001
        log.exception("calendar create failed for booking %s", booking_id)

    manage_url = f"{settings.manage_base_url}/manage/{raw_token}"
    visitor_tz = body.customer.tz or cfg.timezone
    base = {"name": name, "email": email, "note": note, "start_utc": start, "end_utc": end}
    brand = _brand_for(cfg)
    locale = cfg.locale
    from_name = cfg.email_from_name or cfg.business_name or None
    try:
        key_host = f"{booking_id}:confirm_owner"
        if not booking_repo.notification_already_sent(key_host):
            booking_email.send_host_notification(
                booking={**base, "when_label": _when_label(start, cfg.timezone)},
                meeting_url=cfg.meeting_url,
                host_email=cfg.owner_notification_email,
                brand=brand,
                locale=locale,
                from_name=from_name,
            )
            try:
                booking_repo.record_notification(
                    tenant_id=cfg.tenant_id,
                    booking_id=booking_id,
                    type="confirm_owner",
                    offset_min=None,
                    idempotency_key=key_host,
                )
            except Exception:  # noqa: BLE001
                log.exception("record_notification failed for %s", key_host)
    except Exception:  # noqa: BLE001
        log.exception("host email failed")
    try:
        key_cust = f"{booking_id}:confirm_customer"
        if not booking_repo.notification_already_sent(key_cust):
            booking_email.send_visitor_confirmation(
                booking={**base, "when_label": _when_label(start, visitor_tz)},
                meeting_url=cfg.meeting_url,
                manage_url=manage_url,
                brand=brand,
                locale=locale,
                from_name=from_name,
                copy=cfg.email_copy,
            )
            try:
                booking_repo.record_notification(
                    tenant_id=cfg.tenant_id,
                    booking_id=booking_id,
                    type="confirm_customer",
                    offset_min=None,
                    idempotency_key=key_cust,
                )
            except Exception:  # noqa: BLE001
                log.exception("record_notification failed for %s", key_cust)
    except Exception:  # noqa: BLE001
        log.exception("visitor email failed")

    return JSONResponse(
        content={
            "success": True,
            "booking_id": booking_id,
            "manage_url": manage_url,
            "start": start.isoformat(),
            "end": end.isoformat(),
        }
    )


# ---------- manage by token ----------


def _load_for_manage(token: str):
    b = booking_repo.load_booking_by_token_hash(_hash_token(token))
    if not b:
        return None, None, None
    cfg = booking_tenant.load_tenant_by_id(b["tenant_id"])
    policy = booking_repo.load_policy(b["tenant_id"], b.get("service_id"))
    return b, cfg, (policy or {})


# NOTE: GET to match the existing /contact manage page's contract (zero frontend
# change in P1). Before finalizing, open frontend/src/app/(marketing)/manage/[token]/page.tsx
# and confirm every field it reads is present in this response.
@router.get("/manage/{token}", dependencies=[Depends(_public_read_limit)])
def manage_get(token: str) -> JSONResponse:
    b, cfg, policy = _load_for_manage(token)
    if not b or cfg is None:
        return JSONResponse(content={"found": False})
    cust = booking_repo.load_customer(b["customer_id"]) or {}
    start = datetime.fromisoformat(b["start_utc"]).astimezone(_UTC)
    now = datetime.now(UTC)
    confirmed = b["status"] == "confirmed"
    count = b.get("reschedule_count") or 0
    can_cancel = (
        confirmed
        and policy.get("allow_cancel", True)
        and now <= start - timedelta(hours=policy.get("cancellation_window_hours", 24))
    )
    can_resched = (
        confirmed
        and policy.get("allow_reschedule", True)
        and now <= start - timedelta(hours=policy.get("reschedule_window_hours", 24))
        and count < policy.get("max_reschedules", 2)
    )
    return JSONResponse(
        content={
            "found": True,
            "status": b["status"],
            "start_utc": b["start_utc"],
            "end_utc": b["end_utc"],
            "name": b.get("customer_name") or cust.get("name", ""),
            "visitor_timezone": cust.get("timezone") or cfg.timezone,
            "timezone": cfg.timezone,
            "reschedule_count": count,
            "max_reschedules": policy.get("max_reschedules", 2),
            "can_cancel": can_cancel,
            "can_reschedule": can_resched,
            "public_slug": cfg.public_slug,
            "service_id": b["service_id"],
        }
    )


@router.post("/manage/{token}/cancel")
@limiter.limit("10/hour", key_func=client_ip)
async def manage_cancel(request: Request, token: str) -> JSONResponse:
    b, cfg, policy = _load_for_manage(token)
    if not b or cfg is None:
        raise HTTPException(status_code=404, detail="Not found")
    if b["status"] != "confirmed":
        raise HTTPException(status_code=409, detail="Already cancelled")
    start = datetime.fromisoformat(b["start_utc"]).astimezone(_UTC)
    if not policy.get("allow_cancel", True) or datetime.now(UTC) > start - timedelta(
        hours=policy.get("cancellation_window_hours", 24)
    ):
        raise HTTPException(status_code=403, detail="Too late to cancel online")
    provider = calendar_provider.provider_for(cfg.calendar_provider)
    if b.get("google_event_id"):
        try:
            provider.delete_event(b["google_event_id"])
        except Exception:  # noqa: BLE001
            log.exception("calendar delete failed for %s", b["id"])
    booking_repo.update_booking(
        b["id"], {"status": "cancelled", "cancelled_at": datetime.now(UTC).isoformat()}
    )
    booking_repo.insert_audit(
        tenant_id=cfg.tenant_id, booking_id=b["id"], action="cancel", actor="customer"
    )
    cust = booking_repo.load_customer(b["customer_id"]) or {}
    brand = _brand_for(cfg)
    locale = cfg.locale
    from_name = cfg.email_from_name or cfg.business_name or None
    try:
        key_cancel = f"{b['id']}:cancel"
        if not booking_repo.notification_already_sent(key_cancel):
            booking_manage_email.send_cancellation(
                name=b.get("customer_name") or cust.get("name", ""),
                client_email=cust.get("email", ""),
                host_when=_when_label(start, cfg.timezone),
                client_when=_when_label(start, cust.get("timezone") or cfg.timezone),
                host_email=cfg.owner_notification_email,
                brand=brand,
                locale=locale,
                from_name=from_name,
                copy=cfg.email_copy,
            )
            try:
                booking_repo.record_notification(
                    tenant_id=cfg.tenant_id,
                    booking_id=b["id"],
                    type="cancel",
                    offset_min=None,
                    idempotency_key=key_cancel,
                )
            except Exception:  # noqa: BLE001
                log.exception("record_notification failed for %s", key_cancel)
    except Exception:  # noqa: BLE001
        log.exception("cancellation email failed")
    return JSONResponse(content={"success": True})


class RescheduleIn(BaseModel):
    slot_start: str  # the live /contact widget posts {slot_start}; keep that name


@router.post("/manage/{token}/reschedule")
@limiter.limit("10/hour", key_func=client_ip)
async def manage_reschedule(request: Request, token: str, body: RescheduleIn) -> JSONResponse:
    b, cfg, policy = _load_for_manage(token)
    if not b or cfg is None:
        raise HTTPException(status_code=404, detail="Not found")
    if b["status"] != "confirmed":
        raise HTTPException(status_code=409, detail="Already cancelled")
    old_start = datetime.fromisoformat(b["start_utc"]).astimezone(_UTC)
    now = datetime.now(UTC)
    if not policy.get("allow_reschedule", True) or now > old_start - timedelta(
        hours=policy.get("reschedule_window_hours", 24)
    ):
        raise HTTPException(status_code=403, detail="Too late to reschedule online")
    if (b.get("reschedule_count") or 0) >= policy.get("max_reschedules", 2):
        raise HTTPException(status_code=403, detail="Reschedule limit reached")
    service = booking_repo.load_service(cfg.tenant_id, b["service_id"])
    if service is None:
        raise HTTPException(status_code=404, detail="Unknown service")
    try:
        new_start = datetime.fromisoformat(body.slot_start).astimezone(_UTC)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="Bad slot_start") from exc
    # Re-validate the service booking window server-side (client is not trusted).
    if new_start < now + timedelta(minutes=service["lead_time_min"]) or new_start > now + timedelta(
        days=service["max_advance_days"]
    ):
        raise HTTPException(status_code=422, detail="Outside booking window")
    # Free-resource check, excluding this booking's own current guard so an
    # overlapping move (e.g. with buffers) is not a false self-collision.
    resource_id = _free_resource_for(
        cfg=cfg, service=service, start_utc=new_start, now_utc=now, exclude_booking_id=b["id"]
    )
    if resource_id is None:
        raise HTTPException(status_code=409, detail="That time was just taken")
    new_end = new_start + timedelta(minutes=service["duration_min"])
    new_token = secrets.token_urlsafe(32)
    try:
        booking_repo.update_booking(
            b["id"],
            {
                "start_utc": new_start.isoformat(),
                "end_utc": new_end.isoformat(),
                "guard_start_utc": (
                    new_start - timedelta(minutes=service["buffer_before_min"])
                ).isoformat(),
                "guard_end_utc": (
                    new_end + timedelta(minutes=service["buffer_after_min"])
                ).isoformat(),
                "resource_id": resource_id,
                "reschedule_count": (b.get("reschedule_count") or 0) + 1,
                "manage_token_hash": _hash_token(new_token),
            },
        )
    except BookingConflict as exc:
        raise HTTPException(status_code=409, detail="That time was just taken") from exc
    booking_repo.insert_audit(
        tenant_id=cfg.tenant_id, booking_id=b["id"], action="reschedule", actor="customer"
    )
    provider = calendar_provider.provider_for(cfg.calendar_provider)
    if b.get("google_event_id"):
        try:
            provider.update_event(b["google_event_id"], new_start, new_end)
        except Exception:  # noqa: BLE001
            log.exception("calendar patch failed for %s", b["id"])
    cust = booking_repo.load_customer(b["customer_id"]) or {}
    manage_url = f"{settings.manage_base_url}/manage/{new_token}"
    brand = _brand_for(cfg)
    locale = cfg.locale
    from_name = cfg.email_from_name or cfg.business_name or None
    try:
        key_resched = f"{b['id']}:reschedule"
        if not booking_repo.notification_already_sent(key_resched):
            booking_manage_email.send_reschedule(
                name=b.get("customer_name") or cust.get("name", ""),
                client_email=cust.get("email", ""),
                old_host_when=_when_label(old_start, cfg.timezone),
                new_host_when=_when_label(new_start, cfg.timezone),
                new_client_when=_when_label(new_start, cust.get("timezone") or cfg.timezone),
                meeting_url=cfg.meeting_url,
                manage_url=manage_url,
                new_start=new_start,
                new_end=new_end,
                host_email=cfg.owner_notification_email,
                brand=brand,
                locale=locale,
                from_name=from_name,
                copy=cfg.email_copy,
            )
            try:
                booking_repo.record_notification(
                    tenant_id=cfg.tenant_id,
                    booking_id=b["id"],
                    type="reschedule",
                    offset_min=None,
                    idempotency_key=key_resched,
                )
            except Exception:  # noqa: BLE001
                log.exception("record_notification failed for %s", key_resched)
    except Exception:  # noqa: BLE001
        log.exception("reschedule email failed")
    return JSONResponse(
        content={"success": True, "start": new_start.isoformat(), "end": new_end.isoformat()}
    )


# ---------- reminders cron ----------


@router.post("/cron/reminders")
async def send_reminders(request: Request) -> JSONResponse:
    secret = request.headers.get("x-cron-secret", "")
    # SEC-031/SEC-038: constant-time compare so the secret can't be recovered by
    # timing the response.
    if not settings.BOOKING_CRON_SECRET or not hmac.compare_digest(
        secret, settings.BOOKING_CRON_SECRET
    ):
        raise HTTPException(status_code=403, detail="Forbidden")
    now = datetime.now(UTC)
    # Scan a window wide enough to cover the largest possible offset + 5-min send window.
    # We use a generous 2-day lookahead so all plausible offsets are included.
    window_end = now + timedelta(days=2)
    rows = booking_repo.due_reminders(now_utc=now, window_end_utc=window_end)
    sent = 0
    for b in rows:
        cfg = booking_tenant.load_tenant_by_id(b["tenant_id"])
        if cfg is None or not cfg.reminders_enabled:
            continue
        if not cfg.reminder_offsets_min:
            continue
        cust = booking_repo.load_customer(b["customer_id"]) or {}
        start = datetime.fromisoformat(b["start_utc"]).astimezone(_UTC)
        brand = _brand_for(cfg)
        locale = cfg.locale
        for offset_min in cfg.reminder_offsets_min:
            # 5-minute send window: send_start <= now < send_end
            send_start = start - timedelta(minutes=offset_min + 5)
            send_end = start - timedelta(minutes=offset_min)
            if not (send_start <= now < send_end):
                continue
            key = f"{b['id']}:reminder:{offset_min}"
            if booking_repo.notification_already_sent(key):
                continue
            try:
                booking_reminder_email.send(
                    to_email=cust.get("email", ""),
                    name=b.get("customer_name") or cust.get("name", ""),
                    note=b.get("notes"),
                    when_label=_when_label(start, cust.get("timezone") or cfg.timezone),
                    meeting_url=cfg.meeting_url,
                    manage_url="",
                    brand=brand,
                    locale=locale,
                    copy=cfg.email_copy,
                )
                booking_repo.record_notification(
                    tenant_id=cfg.tenant_id,
                    booking_id=b["id"],
                    type="reminder",
                    offset_min=offset_min,
                    idempotency_key=key,
                )
                sent += 1
            except Exception:  # noqa: BLE001
                log.exception("reminder failed for %s offset %s", b.get("id"), offset_min)
    return JSONResponse(content={"sent": sent})


# ---------- legacy shims (tenant #1; keep the live widget working) ----------

_LEGACY_SLUG = "roman-technologies-website"


@router.get("/availability")
def legacy_availability(
    from_: str = Query(..., alias="from"), to: str = Query(...)
) -> JSONResponse:
    cfg = _require_tenant(_LEGACY_SLUG)
    services = booking_repo.load_active_services(cfg.tenant_id)
    if not services:
        return JSONResponse(content={"days": []})
    service = services[0]
    try:
        d0 = datetime.strptime(from_, "%Y-%m-%d").date()
        d1 = datetime.strptime(to, "%Y-%m-%d").date()
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="Bad range") from exc
    now = datetime.now(UTC)
    days, cur = [], d0
    while cur <= d1:
        if _availability_for_day(cfg=cfg, service=service, day=cur, now_utc=now):
            days.append(cur.isoformat())
        cur += timedelta(days=1)
    return JSONResponse(content={"days": days})


@router.get("/slots")
def legacy_slots(date: str, tz: str = "") -> JSONResponse:
    cfg = _require_tenant(_LEGACY_SLUG)
    services = booking_repo.load_active_services(cfg.tenant_id)
    if not services:
        return JSONResponse(content={"slots": []})
    try:
        day = datetime.strptime(date, "%Y-%m-%d").date()
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="Bad date") from exc
    starts = _availability_for_day(cfg=cfg, service=services[0], day=day, now_utc=datetime.now(UTC))
    return JSONResponse(content={"slots": [s.isoformat() for s in starts]})


class LegacyBookingRequest(BaseModel):
    slot_start: str
    name: str
    email: str
    note: str = ""
    visitor_timezone: str = ""
    website: str = ""


@router.post("")
@limiter.limit("5/hour", key_func=client_ip)
async def legacy_create(request: Request, body: LegacyBookingRequest) -> JSONResponse:
    cfg = _require_tenant(_LEGACY_SLUG)
    services = booking_repo.load_active_services(cfg.tenant_id)
    if not services:
        raise HTTPException(status_code=503, detail="Booking unavailable")
    payload = CreateIn(
        service_id=services[0]["id"],
        start_utc=body.slot_start,
        customer=CustomerIn(name=body.name, email=body.email, tz=body.visitor_timezone),
        note=body.note,
        website=body.website,
    )
    # Single code path, no re-entry into the rate-limited route.
    return _create_core(cfg, payload)
