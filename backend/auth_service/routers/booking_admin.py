"""Owner-facing booking config API (Phase 2a + 2b). Project-scoped; mirrors issues.py.
Auth: session → require_user → require_project_access (owner-or-admin) →
project['id'] is the booking tenant_id. `enable` additionally requires admin."""

from __future__ import annotations

import hashlib
import logging
import secrets
import uuid
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, File, HTTPException, Query, Request, UploadFile, status
from fastapi.responses import JSONResponse

from ..models.booking_admin_schemas import (
    AppointmentAction,
    AppointmentCreate,
    EmailPreviewIn,
    ExceptionIn,
    HoursReplace,
    PolicyPatch,
    ResourceIn,
    ServiceIn,
    SettingsPatch,
)
from ..services import (
    booking_admin_repo,
    booking_email,
    booking_i18n,
    booking_manage_email,
    booking_reminder_email,
    booking_repo,
    booking_tenant,
)
from ..services.booking_repo import BookingConflict
from ..services.booking_stats import compute_booking_stats
from ..services.email_layout import Brand
from ..services.supabase_client import get_supabase_admin
from .booking import (
    _availability_for_range,
    _brand_for,
    _free_resource_for,
    _range_to_grouped,
    _when_label,
)
from .deps import (
    admin_user_via_bearer_or_sid,
    require_project_access,
    user_via_bearer_or_session,
)

router = APIRouter(tags=["booking-admin"])
log = logging.getLogger(__name__)


def _notify_client_cancelled(tenant_id: str, booking: dict) -> None:
    """Email the client that the owner cancelled — same template as the public
    manage-link cancel flow. Best-effort: never blocks the cancel."""
    try:
        cfg = booking_tenant.load_tenant_by_id(tenant_id)
        cust = booking_repo.load_customer(booking["customer_id"]) or {}
        if cfg is None or not cust.get("email"):
            return
        start = datetime.fromisoformat(booking["start_utc"]).astimezone(UTC)
        booking_manage_email.send_cancellation(
            name=booking.get("customer_name") or cust.get("name", ""),
            client_email=cust["email"],
            host_when=_when_label(start, cfg.timezone),
            client_when=_when_label(start, cust.get("timezone") or cfg.timezone),
            host_email=cfg.owner_notification_email,
            brand=_brand_for(cfg),
            locale=cfg.locale,
            from_name=cfg.email_from_name or cfg.business_name,
            copy=cfg.email_copy,
        )
    except Exception:  # noqa: BLE001
        log.exception("owner cancellation email failed for %s", booking.get("id"))


def _notify_client_rescheduled(
    tenant_id: str,
    booking: dict,
    *,
    cfg,
    old_start: datetime,
    new_start: datetime,
    new_end: datetime,
) -> None:
    """Email the client that the owner moved the booking — same template as the
    public reschedule flow. Best-effort."""
    try:
        cust = booking_repo.load_customer(booking["customer_id"]) or {}
        if not cust.get("email"):
            return
        booking_manage_email.send_reschedule(
            name=booking.get("customer_name") or cust.get("name", ""),
            client_email=cust["email"],
            old_host_when=_when_label(old_start, cfg.timezone),
            new_host_when=_when_label(new_start, cfg.timezone),
            new_client_when=_when_label(new_start, cust.get("timezone") or cfg.timezone),
            meeting_url=cfg.meeting_url,
            manage_url="",
            new_start=new_start,
            new_end=new_end,
            host_email=cfg.owner_notification_email,
            brand=_brand_for(cfg),
            locale=cfg.locale,
            from_name=cfg.email_from_name or cfg.business_name,
            copy=cfg.email_copy,
        )
    except Exception:  # noqa: BLE001
        log.exception("owner reschedule email failed for %s", booking.get("id"))


async def _tenant(project_slug: str, request: Request) -> str:
    user = await user_via_bearer_or_session(request)
    project = require_project_access(project_slug, user)
    return project["id"]


@router.get("/projects/{project_slug}/bookings/settings")
async def get_settings(project_slug: str, request: Request) -> JSONResponse:
    tenant_id = await _tenant(project_slug, request)
    row = booking_admin_repo.get_settings(tenant_id)
    if not row:
        return JSONResponse(content={"enabled": False})
    return JSONResponse(content={"enabled": True, **row})


@router.post("/projects/{project_slug}/bookings/enable")
async def enable(project_slug: str, request: Request) -> JSONResponse:
    admin = await admin_user_via_bearer_or_sid(request)  # admin-only (raises 403 otherwise)
    project = require_project_access(project_slug, admin)
    owner = booking_admin_repo.owner_email(project["user_id"]) or admin.email
    row = booking_admin_repo.provision(
        tenant_id=project["id"],
        public_slug=project["slug"],
        business_name=project["name"],
        owner_email=owner,
    )
    return JSONResponse(content={"enabled": True, **row})


@router.patch("/projects/{project_slug}/bookings/settings")
async def patch_settings(project_slug: str, body: SettingsPatch, request: Request) -> JSONResponse:
    tenant_id = await _tenant(project_slug, request)
    fields = body.model_dump(exclude_unset=True, exclude_none=True)
    if "public_slug" in fields and booking_admin_repo.slug_taken_by_other(
        fields["public_slug"], tenant_id
    ):
        raise HTTPException(status_code=409, detail="That public link is already taken")
    if not fields:
        raise HTTPException(status_code=422, detail="No fields to update")
    return JSONResponse(content=booking_admin_repo.update_settings(tenant_id, fields))


# ---- services ----
def _validate_resource_ids(tenant_id: str, resource_ids: list[str]) -> None:
    """SEC-022: every resource linked to a service must belong to this tenant.

    Without this an owner of project A could link project B's resource UUID into
    A's service (a cross-tenant association write). load_eligible/list_resources are
    tenant-scoped, so membership proves ownership.
    """
    if not resource_ids:
        return
    owned = {r["id"] for r in booking_admin_repo.list_resources(tenant_id)}
    if any(rid not in owned for rid in resource_ids):
        raise HTTPException(status_code=422, detail="Unknown resource")


@router.get("/projects/{project_slug}/bookings/services")
async def list_services(project_slug: str, request: Request) -> JSONResponse:
    tenant_id = await _tenant(project_slug, request)
    services = booking_admin_repo.list_services(tenant_id)
    links = booking_admin_repo.list_service_resource_links(tenant_id)
    by_service: dict[str, list[str]] = {}
    for link in links:
        by_service.setdefault(link["service_id"], []).append(link["resource_id"])
    for s in services:
        s["resource_ids"] = by_service.get(s["id"], [])
    return JSONResponse(content={"services": services})


@router.post("/projects/{project_slug}/bookings/services", status_code=status.HTTP_201_CREATED)
async def create_service(project_slug: str, body: ServiceIn, request: Request) -> JSONResponse:
    tenant_id = await _tenant(project_slug, request)
    _validate_resource_ids(tenant_id, body.resource_ids)
    fields = body.model_dump(exclude={"resource_ids"})
    row = booking_admin_repo.insert_service(tenant_id, fields)
    booking_admin_repo.set_service_resources(tenant_id, row["id"], body.resource_ids)
    return JSONResponse(
        content={**row, "resource_ids": body.resource_ids}, status_code=status.HTTP_201_CREATED
    )


@router.patch("/projects/{project_slug}/bookings/services/{service_id}")
async def patch_service(
    project_slug: str, service_id: str, body: ServiceIn, request: Request
) -> JSONResponse:
    tenant_id = await _tenant(project_slug, request)
    _validate_resource_ids(tenant_id, body.resource_ids)
    fields = body.model_dump(exclude={"resource_ids"})
    row = booking_admin_repo.update_service(tenant_id, service_id, fields)
    booking_admin_repo.set_service_resources(tenant_id, service_id, body.resource_ids)
    return JSONResponse(content={**row, "resource_ids": body.resource_ids})


@router.delete("/projects/{project_slug}/bookings/services/{service_id}")
async def delete_service(project_slug: str, service_id: str, request: Request) -> JSONResponse:
    tenant_id = await _tenant(project_slug, request)
    if booking_admin_repo.service_has_bookings(tenant_id, service_id):
        raise HTTPException(status_code=409, detail="Service has bookings; deactivate it instead")
    booking_admin_repo.delete_service(tenant_id, service_id)
    return JSONResponse(content={"deleted": True})


# ---- resources ----
@router.get("/projects/{project_slug}/bookings/resources")
async def list_resources(project_slug: str, request: Request) -> JSONResponse:
    tenant_id = await _tenant(project_slug, request)
    return JSONResponse(content={"resources": booking_admin_repo.list_resources(tenant_id)})


@router.post("/projects/{project_slug}/bookings/resources", status_code=status.HTTP_201_CREATED)
async def create_resource(project_slug: str, body: ResourceIn, request: Request) -> JSONResponse:
    tenant_id = await _tenant(project_slug, request)
    row = booking_admin_repo.insert_resource(tenant_id, body.model_dump())
    return JSONResponse(content=row, status_code=status.HTTP_201_CREATED)


@router.patch("/projects/{project_slug}/bookings/resources/{resource_id}")
async def patch_resource(
    project_slug: str, resource_id: str, body: ResourceIn, request: Request
) -> JSONResponse:
    tenant_id = await _tenant(project_slug, request)
    return JSONResponse(
        content=booking_admin_repo.update_resource(tenant_id, resource_id, body.model_dump())
    )


@router.delete("/projects/{project_slug}/bookings/resources/{resource_id}")
async def delete_resource(project_slug: str, resource_id: str, request: Request) -> JSONResponse:
    tenant_id = await _tenant(project_slug, request)
    if booking_admin_repo.resource_has_bookings(tenant_id, resource_id):
        raise HTTPException(status_code=409, detail="Resource has bookings; deactivate it instead")
    booking_admin_repo.delete_resource(tenant_id, resource_id)
    return JSONResponse(content={"deleted": True})


# ---- hours + exceptions ----
@router.get("/projects/{project_slug}/bookings/hours")
async def get_hours(project_slug: str, request: Request) -> JSONResponse:
    tenant_id = await _tenant(project_slug, request)
    return JSONResponse(
        content={
            "hours": booking_admin_repo.list_hours(tenant_id),
            "exceptions": booking_admin_repo.list_exceptions(tenant_id),
        }
    )


@router.put("/projects/{project_slug}/bookings/hours")
async def put_hours(project_slug: str, body: HoursReplace, request: Request) -> JSONResponse:
    tenant_id = await _tenant(project_slug, request)
    rows = []
    for h in body.hours:
        if not (0 <= h.weekday <= 6) or h.start_time >= h.end_time:
            raise HTTPException(status_code=422, detail="Invalid hours interval")
        rows.append(
            {
                "resource_id": h.resource_id,
                "weekday": h.weekday,
                "start_time": h.start_time,
                "end_time": h.end_time,
            }
        )
    booking_admin_repo.replace_hours(tenant_id, rows)
    return JSONResponse(content={"hours": booking_admin_repo.list_hours(tenant_id)})


@router.post("/projects/{project_slug}/bookings/exceptions", status_code=status.HTTP_201_CREATED)
async def create_exception(project_slug: str, body: ExceptionIn, request: Request) -> JSONResponse:
    tenant_id = await _tenant(project_slug, request)
    row = booking_admin_repo.insert_exception(tenant_id, body.model_dump())
    return JSONResponse(content=row, status_code=status.HTTP_201_CREATED)


@router.delete("/projects/{project_slug}/bookings/exceptions/{exc_id}")
async def delete_exception(project_slug: str, exc_id: str, request: Request) -> JSONResponse:
    tenant_id = await _tenant(project_slug, request)
    booking_admin_repo.delete_exception(tenant_id, exc_id)
    return JSONResponse(content={"deleted": True})


# ---- policies ----
@router.get("/projects/{project_slug}/bookings/policies")
async def get_policies(project_slug: str, request: Request) -> JSONResponse:
    tenant_id = await _tenant(project_slug, request)
    return JSONResponse(content={"policies": booking_admin_repo.list_policies(tenant_id)})


@router.patch("/projects/{project_slug}/bookings/policies")
async def patch_policy(project_slug: str, body: PolicyPatch, request: Request) -> JSONResponse:
    tenant_id = await _tenant(project_slug, request)
    return JSONResponse(content=booking_admin_repo.upsert_policy(tenant_id, body.model_dump()))


# ---- appointments (Phase 2b) ----


def _flatten_appointment(row: dict) -> dict:
    """Replace nested Supabase join dicts with flat name fields."""
    out = {
        k: v
        for k, v in row.items()
        if k not in ("booking_customers", "booking_services", "booking_resources")
    }
    cust = row.get("booking_customers") or {}
    svc = row.get("booking_services") or {}
    res = row.get("booking_resources") or {}
    out["customer_name"] = row.get("customer_name") or cust.get("name")
    out["customer_email"] = cust.get("email")
    out["customer_phone"] = cust.get("phone")
    out["customer_timezone"] = cust.get("timezone")
    out["service_name"] = svc.get("name")
    out["resource_name"] = res.get("name")
    return out


@router.get("/projects/{project_slug}/bookings/appointments")
async def list_appointments(
    project_slug: str,
    request: Request,
    status: str | None = Query(None),
    service_id: str | None = Query(None),
    resource_id: str | None = Query(None),
    from_: str | None = Query(None, alias="from"),
    to: str | None = Query(None),
) -> JSONResponse:
    tenant_id = await _tenant(project_slug, request)
    rows = booking_admin_repo.list_appointments(
        tenant_id,
        status=status,
        service_id=service_id,
        resource_id=resource_id,
        date_from=from_,
        date_to=to,
    )
    return JSONResponse(content={"appointments": [_flatten_appointment(r) for r in rows]})


@router.get("/projects/{project_slug}/bookings/availability")
async def owner_availability(
    project_slug: str,
    request: Request,
    service_id: str = Query(...),
    from_: str = Query(..., alias="from"),
    to: str = Query(...),
) -> JSONResponse:
    """Owner-side availability (for the manual-create / reschedule slot pickers).
    Same slots the public widget sees, but on the authenticated owner surface."""
    tenant_id = await _tenant(project_slug, request)
    cfg = booking_tenant.load_tenant_by_id(tenant_id)
    if cfg is None:
        raise HTTPException(status_code=404, detail="Bookings not enabled")
    service = booking_repo.load_service(tenant_id, service_id)
    if service is None:
        raise HTTPException(status_code=404, detail="Unknown service")
    try:
        d0 = datetime.strptime(from_, "%Y-%m-%d").date()
        d1 = datetime.strptime(to, "%Y-%m-%d").date()
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="Bad range") from exc
    rng = _availability_for_range(cfg=cfg, service=service, d0=d0, d1=d1, now_utc=datetime.now(UTC))
    return JSONResponse(content=_range_to_grouped(rng))


@router.post("/projects/{project_slug}/bookings/appointments", status_code=status.HTTP_201_CREATED)
async def create_appointment(
    project_slug: str, body: AppointmentCreate, request: Request
) -> JSONResponse:
    tenant_id = await _tenant(project_slug, request)
    cfg = booking_tenant.load_tenant_by_id(tenant_id)
    if cfg is None:
        raise HTTPException(status_code=404, detail="Booking not enabled for this project")
    svc = booking_repo.load_service(tenant_id, body.service_id)
    if svc is None:
        raise HTTPException(status_code=404, detail="Unknown service")
    try:
        start = datetime.fromisoformat(body.start_utc).astimezone(UTC)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="Bad start_utc") from exc

    now = datetime.now(UTC)

    if body.resource_id:
        # SEC-003: a caller-supplied resource_id MUST belong to this tenant and be
        # eligible for the service. Without this check an owner of project A could
        # book against project B's resource_id (the FK is not tenant-composite and
        # the no-overlap GiST exclusion constraint is global) — a cross-tenant write
        # plus a silent calendar DoS against the victim. load_eligible_resources is
        # strictly tenant-scoped, so membership in it proves ownership + eligibility.
        eligible_ids = {r["id"] for r in booking_repo.load_eligible_resources(tenant_id, svc["id"])}
        if body.resource_id not in eligible_ids:
            raise HTTPException(status_code=422, detail="Unknown resource")
        resource_id = body.resource_id
    else:
        resource_id = _free_resource_for(cfg=cfg, service=svc, start_utc=start, now_utc=now)
        if resource_id is None:
            raise HTTPException(status_code=409, detail="No resource available at that time")

    end = start + timedelta(minutes=svc["duration_min"])
    guard_start = start - timedelta(minutes=svc["buffer_before_min"])
    guard_end = end + timedelta(minutes=svc["buffer_after_min"])

    customer_id = booking_repo.upsert_customer(
        tenant_id=tenant_id,
        name=body.customer.name,
        email=body.customer.email,
        phone=body.customer.phone,
        locale=cfg.locale,
        timezone=body.customer.tz or cfg.timezone,
    )
    manage_token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(manage_token.encode()).hexdigest()
    try:
        booking_id = booking_repo.insert_booking(
            tenant_id=tenant_id,
            service_id=svc["id"],
            resource_id=resource_id,
            customer_id=customer_id,
            customer_name=body.customer.name,
            start_utc=start,
            end_utc=end,
            guard_start_utc=guard_start,
            guard_end_utc=guard_end,
            manage_token_hash=token_hash,
            source="dashboard",
            notes=body.note,
        )
    except BookingConflict as exc:
        raise HTTPException(status_code=409, detail="That time was just taken") from exc
    booking_repo.insert_audit(
        tenant_id=tenant_id,
        booking_id=booking_id,
        action="create",
        actor="owner",
        payload={"resource_id": resource_id, "owner_override": True},
    )
    return JSONResponse(
        content={"booking_id": booking_id, "start": start.isoformat(), "end": end.isoformat()},
        status_code=status.HTTP_201_CREATED,
    )


@router.patch("/projects/{project_slug}/bookings/appointments/{booking_id}")
async def act_on_appointment(
    project_slug: str, booking_id: str, body: AppointmentAction, request: Request
) -> JSONResponse:
    tenant_id = await _tenant(project_slug, request)
    booking = booking_admin_repo.get_booking(tenant_id, booking_id)
    if booking is None:
        raise HTTPException(status_code=404, detail="Booking not found")

    now = datetime.now(UTC)
    action = body.action

    if action == "cancel":
        booking_repo.update_booking(
            booking_id,
            {
                "status": "cancelled",
                "cancelled_at": now.isoformat(),
                "cancel_reason": body.reason,
            },
        )
        booking_repo.insert_audit(
            tenant_id=tenant_id,
            booking_id=booking_id,
            action="cancel",
            actor="owner",
            payload={"reason": body.reason, "owner_override": True},
        )
        _notify_client_cancelled(tenant_id, booking)
        return JSONResponse(content={"success": True})

    if action == "no_show":
        booking_repo.update_booking(booking_id, {"status": "no_show"})
        booking_repo.insert_audit(
            tenant_id=tenant_id,
            booking_id=booking_id,
            action="no_show",
            actor="owner",
            payload={"owner_override": True},
        )
        return JSONResponse(content={"success": True})

    if action == "complete":
        booking_repo.update_booking(booking_id, {"status": "completed"})
        booking_repo.insert_audit(
            tenant_id=tenant_id,
            booking_id=booking_id,
            action="complete",
            actor="owner",
            payload={"owner_override": True},
        )
        return JSONResponse(content={"success": True})

    if action == "reschedule":
        if not body.start_utc:
            raise HTTPException(status_code=422, detail="start_utc required for reschedule")
        cfg = booking_tenant.load_tenant_by_id(tenant_id)
        if cfg is None:
            raise HTTPException(status_code=404, detail="Booking not enabled for this project")
        svc = booking_repo.load_service(tenant_id, booking["service_id"])
        if svc is None:
            raise HTTPException(status_code=404, detail="Unknown service")
        try:
            new_start = datetime.fromisoformat(body.start_utc).astimezone(UTC)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail="Bad start_utc") from exc
        resource_id = _free_resource_for(
            cfg=cfg,
            service=svc,
            start_utc=new_start,
            now_utc=now,
            exclude_booking_id=booking_id,
        )
        if resource_id is None:
            raise HTTPException(status_code=409, detail="No resource available at that time")
        new_end = new_start + timedelta(minutes=svc["duration_min"])
        new_guard_start = new_start - timedelta(minutes=svc["buffer_before_min"])
        new_guard_end = new_end + timedelta(minutes=svc["buffer_after_min"])
        try:
            booking_repo.update_booking(
                booking_id,
                {
                    "start_utc": new_start.isoformat(),
                    "end_utc": new_end.isoformat(),
                    "guard_start_utc": new_guard_start.isoformat(),
                    "guard_end_utc": new_guard_end.isoformat(),
                    "resource_id": resource_id,
                    "reschedule_count": (booking.get("reschedule_count") or 0) + 1,
                },
            )
        except BookingConflict as exc:
            raise HTTPException(status_code=409, detail="That time was just taken") from exc
        booking_repo.insert_audit(
            tenant_id=tenant_id,
            booking_id=booking_id,
            action="reschedule",
            actor="owner",
            payload={"new_start": new_start.isoformat(), "owner_override": True},
        )
        old_start = datetime.fromisoformat(booking["start_utc"]).astimezone(UTC)
        _notify_client_rescheduled(
            tenant_id, booking, cfg=cfg, old_start=old_start, new_start=new_start, new_end=new_end
        )
        return JSONResponse(
            content={"success": True, "start": new_start.isoformat(), "end": new_end.isoformat()}
        )

    raise HTTPException(status_code=422, detail=f"Unknown action: {action}")


# ---- stats (Phase 2c) ----


@router.get("/projects/{project_slug}/bookings/stats")
async def get_booking_stats(
    project_slug: str,
    request: Request,
    from_: str | None = Query(None, alias="from"),
    to: str | None = Query(None),
) -> JSONResponse:
    tenant_id = await _tenant(project_slug, request)
    cfg = booking_tenant.load_tenant_by_id(tenant_id)
    if cfg is None:
        raise HTTPException(status_code=404, detail="Bookings not enabled")
    now = datetime.now(UTC)
    date_from = from_ or (now - timedelta(days=90)).date().isoformat()
    date_to = to or (now + timedelta(days=90)).date().isoformat()
    rows = booking_admin_repo.list_bookings_for_stats(tenant_id, date_from, date_to)
    return JSONResponse(content=compute_booking_stats(rows, now_utc=now, tz_name=cfg.timezone))


# ---- email template editor ----


@router.get("/projects/{project_slug}/bookings/email-template")
async def get_email_template(project_slug: str, request: Request) -> JSONResponse:
    tenant_id = await _tenant(project_slug, request)
    row = booking_admin_repo.get_settings(tenant_id) or {}
    overrides = row.get("email_copy") or {}
    fields = [
        {**f, "default": booking_i18n.STRINGS["en"][f["key"]], "value": overrides.get(f["key"], "")}
        for f in booking_i18n.EDITABLE_EMAIL_FIELDS
    ]
    return JSONResponse(
        content={
            "brand": {
                "logo_url": row.get("logo_url"),
                "accent_color": row.get("accent_color"),
                "business_name": row.get("business_name"),
            },
            "fields": fields,
        }
    )


_SAMPLE = {
    "name": "Alex Carter",
    "email": "alex@example.com",
    "when_label": "Mon, 30 Jun 2026 · 14:30 (Europe/Berlin)",
    "note": "Looking forward to it.",
}


@router.post("/projects/{project_slug}/bookings/email-preview")
async def email_preview(project_slug: str, body: EmailPreviewIn, request: Request) -> JSONResponse:
    await _tenant(project_slug, request)
    d = body.draft
    brand = Brand(
        business_name=d.get("business_name") or "Your business",
        logo_url=d.get("logo_url") or "https://roman-technologies.dev/logo_dark.png",
        accent=d.get("accent_color") or "#18181b",
        canonical_url="https://roman-technologies.dev",
    )
    copy = d.get("email_copy") or {}
    start = datetime(2026, 6, 30, 12, 30, tzinfo=UTC)
    end = datetime(2026, 6, 30, 13, 15, tzinfo=UTC)
    booking = {**_SAMPLE, "start_utc": start, "end_utc": end}
    if body.case == "confirmation":
        html = booking_email.render_visitor_html(
            booking=booking,
            meeting_url="https://meet.example/demo",
            manage_url="https://example/m/sample",
            brand=brand,
            copy=copy,
        )
    elif body.case == "reschedule":
        html = booking_manage_email.render_reschedule_client(
            name=_SAMPLE["name"],
            new_when=_SAMPLE["when_label"],
            meeting_url="https://meet.example/demo",
            manage_url="https://example/m/sample",
            new_start=start,
            new_end=end,
            brand=brand,
            copy=copy,
        )
    elif body.case == "cancellation":
        html = booking_manage_email.render_cancel_client(
            name=_SAMPLE["name"], when_label=_SAMPLE["when_label"], brand=brand, copy=copy
        )
    elif body.case == "reminder":
        html = booking_reminder_email.render_html(
            name=_SAMPLE["name"],
            when_label=_SAMPLE["when_label"],
            note=_SAMPLE["note"],
            meeting_url="https://meet.example/demo",
            brand=brand,
            copy=copy,
        )
    else:
        raise HTTPException(status_code=422, detail="Unknown case")
    return JSONResponse(content={"html": html})


_LOGO_DENY = {"image/svg+xml", "text/html", "application/xhtml+xml"}
_LOGO_MAX = 5 * 1024 * 1024


@router.post("/projects/{project_slug}/bookings/logo")
async def upload_logo(
    project_slug: str, request: Request, file: UploadFile = File(...)
) -> JSONResponse:
    tenant_id = await _tenant(project_slug, request)
    content = await file.read()
    if len(content) > _LOGO_MAX:
        raise HTTPException(status_code=413, detail="Logo too large (max 5MB)")
    mime = file.content_type or ""
    if not mime.startswith("image/") or mime in _LOGO_DENY:
        raise HTTPException(status_code=415, detail="Logo must be a PNG/JPG/WebP image")
    ext = (file.filename or "logo").rsplit(".", 1)[-1].lower()[:8] or "png"
    path = f"{tenant_id}/booking-logo/{uuid.uuid4()}.{ext}"
    sb = get_supabase_admin()
    sb.storage.from_("cms-files").upload(
        path=path, file=content, file_options={"content-type": mime, "upsert": "false"}
    )
    url = sb.storage.from_("cms-files").get_public_url(path)
    return JSONResponse(content={"url": url})
