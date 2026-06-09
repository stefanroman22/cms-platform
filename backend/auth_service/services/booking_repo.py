"""All booking-domain database I/O via the service-role Supabase client.
Authorization (tenant scoping) is the caller's responsibility — every function
takes an explicit tenant_id and filters by it."""

from __future__ import annotations

from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from .supabase_client import get_supabase_admin

_UTC = ZoneInfo("UTC")


class BookingConflict(Exception):
    """Raised when an insert/update loses the no-overlap exclusion race."""


def _is_conflict(exc: Exception) -> bool:
    msg = str(exc).lower()
    return "23p01" in msg or "23505" in msg or "exclusion" in msg or "duplicate key" in msg


# ---------- config reads ----------


def load_active_services(tenant_id: str) -> list[dict]:
    sb = get_supabase_admin()
    res = (
        sb.table("booking_services")
        .select("*")
        .eq("tenant_id", tenant_id)
        .eq("is_active", True)
        .order("sort_order")
        .execute()
    )
    return res.data or []


def load_service(tenant_id: str, service_id: str) -> dict | None:
    sb = get_supabase_admin()
    res = (
        sb.table("booking_services")
        .select("*")
        .eq("tenant_id", tenant_id)
        .eq("id", service_id)
        .limit(1)
        .execute()
    )
    rows = res.data or []
    return rows[0] if rows else None


def load_active_resources(tenant_id: str) -> list[dict]:
    """All active resources (staff/rooms/equipment) for a tenant, ordered.
    Used by the public per-barber selection step when no service filter applies."""
    sb = get_supabase_admin()
    res = (
        sb.table("booking_resources")
        .select("*")
        .eq("tenant_id", tenant_id)
        .eq("is_active", True)
        .order("sort_order")
        .execute()
    )
    return res.data or []


def load_eligible_resources(tenant_id: str, service_id: str) -> list[dict]:
    """Active resources linked to this service via booking_service_resources."""
    sb = get_supabase_admin()
    links = (
        sb.table("booking_service_resources")
        .select("resource_id")
        .eq("tenant_id", tenant_id)
        .eq("service_id", service_id)
        .execute()
    )
    ids = [r["resource_id"] for r in (links.data or [])]
    if not ids:
        return []
    res = (
        sb.table("booking_resources")
        .select("*")
        .eq("tenant_id", tenant_id)
        .eq("is_active", True)
        .in_("id", ids)
        .order("sort_order")
        .execute()
    )
    return res.data or []


def load_hours(tenant_id: str) -> list[dict]:
    sb = get_supabase_admin()
    res = sb.table("booking_hours").select("*").eq("tenant_id", tenant_id).execute()
    return res.data or []


def load_exceptions(tenant_id: str, date_from: str, date_to: str) -> list[dict]:
    sb = get_supabase_admin()
    res = (
        sb.table("booking_exceptions")
        .select("*")
        .eq("tenant_id", tenant_id)
        .gte("date", date_from)
        .lte("date", date_to)
        .execute()
    )
    return res.data or []


def load_policy(tenant_id: str, service_id: str | None) -> dict | None:
    """Service-specific policy if present, else the tenant default (service_id null)."""
    sb = get_supabase_admin()
    if service_id:
        res = (
            sb.table("booking_policies")
            .select("*")
            .eq("tenant_id", tenant_id)
            .eq("service_id", service_id)
            .limit(1)
            .execute()
        )
        if res.data:
            return res.data[0]
    res = (
        sb.table("booking_policies")
        .select("*")
        .eq("tenant_id", tenant_id)
        .is_("service_id", "null")
        .limit(1)
        .execute()
    )
    rows = res.data or []
    return rows[0] if rows else None


def busy_guard_intervals_by_resource(
    *,
    tenant_id: str,
    resource_ids: list[str],
    window_start_utc: datetime,
    window_end_utc: datetime,
    exclude_booking_id: str | None = None,
) -> dict[str, list[tuple[datetime, datetime]]]:
    """Guard intervals of confirmed+pending bookings overlapping the window,
    grouped by resource_id. `exclude_booking_id` drops that booking from the set
    (used on reschedule so a booking never conflicts with its own guard)."""
    out: dict[str, list[tuple[datetime, datetime]]] = {rid: [] for rid in resource_ids}
    if not resource_ids:
        return out
    sb = get_supabase_admin()
    q = (
        sb.table("bookings")
        .select("resource_id, guard_start_utc, guard_end_utc")
        .eq("tenant_id", tenant_id)
        .in_("resource_id", resource_ids)
        .in_("status", ["pending", "confirmed"])
        .lt("guard_start_utc", window_end_utc.isoformat())
        .gt("guard_end_utc", window_start_utc.isoformat())
    )
    if exclude_booking_id:
        q = q.neq("id", exclude_booking_id)
    res = q.execute()
    for r in res.data or []:
        rid = r["resource_id"]
        out.setdefault(rid, []).append(
            (
                datetime.fromisoformat(r["guard_start_utc"]).astimezone(_UTC),
                datetime.fromisoformat(r["guard_end_utc"]).astimezone(_UTC),
            )
        )
    return out


# ---------- writes ----------


def upsert_customer(
    *,
    tenant_id: str,
    name: str,
    email: str,
    phone: str | None,
    locale: str | None,
    timezone: str | None,
) -> str:
    sb = get_supabase_admin()
    res = (
        sb.table("booking_customers")
        .upsert(
            {
                "tenant_id": tenant_id,
                "name": name,
                "email": email,
                "phone": phone,
                "locale": locale,
                "timezone": timezone,
            },
            on_conflict="tenant_id,email",
        )
        .execute()
    )
    return (res.data or [{}])[0]["id"]


def insert_booking(
    *,
    tenant_id: str,
    service_id: str,
    resource_id: str,
    customer_id: str,
    customer_name: str,
    start_utc: datetime,
    end_utc: datetime,
    guard_start_utc: datetime,
    guard_end_utc: datetime,
    manage_token_hash: str,
    source: str,
    notes: str | None,
) -> str:
    sb = get_supabase_admin()
    try:
        res = (
            sb.table("bookings")
            .insert(
                {
                    "tenant_id": tenant_id,
                    "service_id": service_id,
                    "resource_id": resource_id,
                    "customer_id": customer_id,
                    "customer_name": customer_name,
                    "status": "confirmed",
                    "start_utc": start_utc.isoformat(),
                    "end_utc": end_utc.isoformat(),
                    "guard_start_utc": guard_start_utc.isoformat(),
                    "guard_end_utc": guard_end_utc.isoformat(),
                    "manage_token_hash": manage_token_hash,
                    "source": source,
                    "notes": notes,
                }
            )
            .execute()
        )
    except Exception as exc:  # noqa: BLE001
        if _is_conflict(exc):
            raise BookingConflict() from exc
        raise
    return (res.data or [{}])[0].get("id")


def insert_block(
    *,
    tenant_id: str,
    resource_id: str,
    start_utc: datetime,
    end_utc: datetime,
    label: str,
    manage_token_hash: str,
) -> str:
    """Insert a personal time-block on one barber's calendar: a confirmed booking
    with no customer and no service (source='block'). It participates in the
    per-resource no-overlap constraint, so it blocks that barber's availability."""
    sb = get_supabase_admin()
    try:
        res = (
            sb.table("bookings")
            .insert(
                {
                    "tenant_id": tenant_id,
                    "service_id": None,
                    "resource_id": resource_id,
                    "customer_id": None,
                    "customer_name": label,
                    "status": "confirmed",
                    "start_utc": start_utc.isoformat(),
                    "end_utc": end_utc.isoformat(),
                    "guard_start_utc": start_utc.isoformat(),
                    "guard_end_utc": end_utc.isoformat(),
                    "manage_token_hash": manage_token_hash,
                    "source": "block",
                    "notes": None,
                }
            )
            .execute()
        )
    except Exception as exc:  # noqa: BLE001
        if _is_conflict(exc):
            raise BookingConflict() from exc
        raise
    return (res.data or [{}])[0].get("id")


def update_booking(booking_id: str, fields: dict) -> None:
    sb = get_supabase_admin()
    try:
        sb.table("bookings").update(fields).eq("id", booking_id).execute()
    except Exception as exc:  # noqa: BLE001
        if _is_conflict(exc):
            raise BookingConflict() from exc
        raise


def load_booking_by_token_hash(token_hash: str) -> dict | None:
    sb = get_supabase_admin()
    res = sb.table("bookings").select("*").eq("manage_token_hash", token_hash).limit(1).execute()
    rows = res.data or []
    return rows[0] if rows else None


def insert_audit(
    *, tenant_id: str, booking_id: str | None, action: str, actor: str, payload: dict | None = None
) -> None:
    sb = get_supabase_admin()
    sb.table("booking_audit_log").insert(
        {
            "tenant_id": tenant_id,
            "booking_id": booking_id,
            "action": action,
            "actor": actor,
            "payload": payload,
        }
    ).execute()


def load_customer(customer_id: str) -> dict | None:
    sb = get_supabase_admin()
    res = sb.table("booking_customers").select("*").eq("id", customer_id).limit(1).execute()
    rows = res.data or []
    return rows[0] if rows else None


def due_reminders(*, now_utc: datetime, window_end_utc: datetime) -> list[dict]:
    sb = get_supabase_admin()
    res = (
        sb.table("bookings")
        .select("id, tenant_id, customer_id, customer_name, notes, start_utc")
        .eq("status", "confirmed")
        .is_("reminder_sent_at", "null")
        .gte("start_utc", now_utc.isoformat())
        .lte("start_utc", window_end_utc.isoformat())
        .execute()
    )
    return res.data or []


# ---------- notification idempotency (P4) ----------


def notification_already_sent(idempotency_key: str) -> bool:
    """Return True if a row with this key exists in booking_notifications_log."""
    sb = get_supabase_admin()
    res = (
        sb.table("booking_notifications_log")
        .select("id")
        .eq("idempotency_key", idempotency_key)
        .limit(1)
        .execute()
    )
    return bool(res.data)


def record_notification(
    *,
    tenant_id: str,
    booking_id: str | None,
    type: str,  # noqa: A002
    offset_min: int | None,
    idempotency_key: str,
    status: str = "sent",
    provider_id: str | None = None,
    error: str | None = None,
) -> None:
    """Insert a row into booking_notifications_log. Idempotent on the unique key
    (the DB unique constraint will raise on a duplicate, so callers must check
    ``notification_already_sent`` first or wrap in try/except)."""
    sb = get_supabase_admin()
    sent_at = datetime.now(UTC).isoformat() if status == "sent" else None
    sb.table("booking_notifications_log").insert(
        {
            "tenant_id": tenant_id,
            "booking_id": booking_id,
            "type": type,
            "offset_min": offset_min,
            "idempotency_key": idempotency_key,
            "status": status,
            "provider_id": provider_id,
            "error": error,
            "sent_at": sent_at,
        }
    ).execute()
