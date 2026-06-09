"""Owner-side booking config DB helpers (Phase 2a). Service-role client;
caller passes an explicit tenant_id (= project id) for every operation."""

from __future__ import annotations

from datetime import UTC, datetime

from .supabase_client import get_supabase_admin

_DEFAULT_RESOURCE = "00000000-0000-0000-0000-000000000000"  # placeholder, unused


def get_settings(tenant_id: str) -> dict | None:
    sb = get_supabase_admin()
    res = sb.table("booking_settings").select("*").eq("tenant_id", tenant_id).limit(1).execute()
    rows = res.data or []
    return rows[0] if rows else None


def slug_taken_by_other(public_slug: str, tenant_id: str) -> bool:
    sb = get_supabase_admin()
    res = (
        sb.table("booking_settings")
        .select("tenant_id")
        .eq("public_slug", public_slug)
        .limit(1)
        .execute()
    )
    rows = res.data or []
    return bool(rows) and rows[0]["tenant_id"] != tenant_id


def update_settings(tenant_id: str, fields: dict) -> dict:
    sb = get_supabase_admin()
    fields = {**fields, "updated_at": datetime.now(UTC).isoformat()}
    res = sb.table("booking_settings").update(fields).eq("tenant_id", tenant_id).execute()
    return (res.data or [{}])[0]


def provision(
    *,
    tenant_id: str,
    public_slug: str,
    business_name: str,
    owner_email: str,
    timezone: str = "Europe/Berlin",
) -> dict:
    """Idempotent: create booking_settings + default resource/service/hours/policy
    if the tenant has no settings row yet. Returns the settings row."""
    sb = get_supabase_admin()
    existing = get_settings(tenant_id)
    if existing:
        return existing
    settings_row = (
        sb.table("booking_settings")
        .insert(
            {
                "tenant_id": tenant_id,
                "public_slug": public_slug,
                "timezone": timezone,
                "locale": "en",
                "business_name": business_name,
                "owner_notification_email": owner_email,
                "email_from_name": business_name,
                "calendar_provider": "none",
                "reminder_offsets_min": [1440, 120],
            }
        )
        .execute()
        .data[0]
    )
    resource = (
        sb.table("booking_resources")
        .insert(
            {
                "tenant_id": tenant_id,
                "name": "Staff",
                "type": "staff",
            }
        )
        .execute()
        .data[0]
    )
    service = (
        sb.table("booking_services")
        .insert(
            {
                "tenant_id": tenant_id,
                "name": "Consultation",
                "duration_min": 30,
                "lead_time_min": 120,
                "max_advance_days": 60,
            }
        )
        .execute()
        .data[0]
    )
    sb.table("booking_service_resources").insert(
        {
            "tenant_id": tenant_id,
            "service_id": service["id"],
            "resource_id": resource["id"],
        }
    ).execute()
    sb.table("booking_hours").insert(
        [
            {
                "tenant_id": tenant_id,
                "resource_id": None,
                "weekday": d,
                "start_time": "09:00",
                "end_time": "17:00",
            }
            for d in (1, 2, 3, 4, 5)
        ]
    ).execute()
    sb.table("booking_policies").insert(
        {
            "tenant_id": tenant_id,
            "service_id": None,
            "policy_text": "Reschedule up to 24h before; cancel up to 24h before.",
        }
    ).execute()
    return settings_row


# ---- services ----
def list_services(tenant_id: str) -> list[dict]:
    sb = get_supabase_admin()
    return (
        sb.table("booking_services")
        .select("*")
        .eq("tenant_id", tenant_id)
        .order("sort_order")
        .execute()
    ).data or []


def list_service_resource_links(tenant_id: str) -> list[dict]:
    sb = get_supabase_admin()
    return (
        sb.table("booking_service_resources")
        .select("service_id, resource_id")
        .eq("tenant_id", tenant_id)
        .execute()
    ).data or []


def insert_service(tenant_id: str, fields: dict) -> dict:
    sb = get_supabase_admin()
    return sb.table("booking_services").insert({**fields, "tenant_id": tenant_id}).execute().data[0]


def update_service(tenant_id: str, service_id: str, fields: dict) -> dict:
    sb = get_supabase_admin()
    res = (
        sb.table("booking_services")
        .update(fields)
        .eq("tenant_id", tenant_id)
        .eq("id", service_id)
        .execute()
    )
    return (res.data or [{}])[0]


def link_resource_to_all_services(tenant_id: str, resource_id: str) -> None:
    """Link a (newly created) resource to EVERY service of the tenant — the
    default-all rule so a new barber can immediately perform all services.
    Idempotent: existing (service_id, resource_id) links are ignored."""
    sb = get_supabase_admin()
    services = (
        sb.table("booking_services").select("id").eq("tenant_id", tenant_id).execute()
    ).data or []
    rows = [
        {"tenant_id": tenant_id, "service_id": s["id"], "resource_id": resource_id}
        for s in services
    ]
    if rows:
        sb.table("booking_service_resources").upsert(
            rows, on_conflict="service_id,resource_id", ignore_duplicates=True
        ).execute()


def set_service_resources(tenant_id: str, service_id: str, resource_ids: list[str]) -> None:
    sb = get_supabase_admin()
    sb.table("booking_service_resources").delete().eq("tenant_id", tenant_id).eq(
        "service_id", service_id
    ).execute()
    if resource_ids:
        sb.table("booking_service_resources").insert(
            [
                {"tenant_id": tenant_id, "service_id": service_id, "resource_id": rid}
                for rid in resource_ids
            ]
        ).execute()


def service_has_bookings(tenant_id: str, service_id: str) -> bool:
    sb = get_supabase_admin()
    res = (
        sb.table("bookings")
        .select("id")
        .eq("tenant_id", tenant_id)
        .eq("service_id", service_id)
        .limit(1)
        .execute()
    )
    return bool(res.data)


def delete_service(tenant_id: str, service_id: str) -> None:
    sb = get_supabase_admin()
    sb.table("booking_services").delete().eq("tenant_id", tenant_id).eq("id", service_id).execute()


# ---- resources ----
def list_resources(tenant_id: str) -> list[dict]:
    sb = get_supabase_admin()
    return (
        sb.table("booking_resources")
        .select("*")
        .eq("tenant_id", tenant_id)
        .order("sort_order")
        .execute()
    ).data or []


def insert_resource(tenant_id: str, fields: dict) -> dict:
    sb = get_supabase_admin()
    return (
        sb.table("booking_resources").insert({**fields, "tenant_id": tenant_id}).execute().data[0]
    )


def update_resource(tenant_id: str, resource_id: str, fields: dict) -> dict:
    sb = get_supabase_admin()
    res = (
        sb.table("booking_resources")
        .update(fields)
        .eq("tenant_id", tenant_id)
        .eq("id", resource_id)
        .execute()
    )
    return (res.data or [{}])[0]


def resource_has_bookings(tenant_id: str, resource_id: str) -> bool:
    sb = get_supabase_admin()
    res = (
        sb.table("bookings")
        .select("id")
        .eq("tenant_id", tenant_id)
        .eq("resource_id", resource_id)
        .limit(1)
        .execute()
    )
    return bool(res.data)


def delete_resource(tenant_id: str, resource_id: str) -> None:
    sb = get_supabase_admin()
    sb.table("booking_resources").delete().eq("tenant_id", tenant_id).eq(
        "id", resource_id
    ).execute()


# ---- hours ----
def list_hours(tenant_id: str) -> list[dict]:
    sb = get_supabase_admin()
    return (sb.table("booking_hours").select("*").eq("tenant_id", tenant_id).execute()).data or []


def replace_hours(tenant_id: str, rows: list[dict], *, resource_id: str | None = None) -> None:
    """Replace the weekly hours for ONE scope only: a specific barber
    (`resource_id` set) or the business-wide default (`resource_id` None). Each
    inserted row's resource_id is forced to the scope, and other scopes' rows are
    left untouched — so saving one barber's calendar never wipes another's."""
    sb = get_supabase_admin()
    q = sb.table("booking_hours").delete().eq("tenant_id", tenant_id)
    q = q.eq("resource_id", resource_id) if resource_id else q.is_("resource_id", "null")
    q.execute()
    if rows:
        sb.table("booking_hours").insert(
            [{**r, "tenant_id": tenant_id, "resource_id": resource_id} for r in rows]
        ).execute()


# ---- exceptions ----
def list_exceptions(tenant_id: str) -> list[dict]:
    sb = get_supabase_admin()
    return (
        sb.table("booking_exceptions")
        .select("*")
        .eq("tenant_id", tenant_id)
        .order("date")
        .execute()
    ).data or []


def insert_exception(tenant_id: str, fields: dict) -> dict:
    sb = get_supabase_admin()
    return (
        sb.table("booking_exceptions").insert({**fields, "tenant_id": tenant_id}).execute().data[0]
    )


def delete_exception(tenant_id: str, exc_id: str) -> None:
    sb = get_supabase_admin()
    sb.table("booking_exceptions").delete().eq("tenant_id", tenant_id).eq("id", exc_id).execute()


# ---- policies ----
def list_policies(tenant_id: str) -> list[dict]:
    sb = get_supabase_admin()
    return (
        sb.table("booking_policies").select("*").eq("tenant_id", tenant_id).execute()
    ).data or []


def upsert_policy(tenant_id: str, fields: dict) -> dict:
    """Upsert by (tenant_id, service_id-or-null). Delete-then-insert the matching
    scope to avoid relying on a partial unique index through PostgREST."""
    sb = get_supabase_admin()
    service_id = fields.get("service_id")
    q = sb.table("booking_policies").delete().eq("tenant_id", tenant_id)
    q = q.is_("service_id", "null") if service_id is None else q.eq("service_id", service_id)
    q.execute()
    return sb.table("booking_policies").insert({**fields, "tenant_id": tenant_id}).execute().data[0]


def owner_email(user_id: str) -> str:
    sb = get_supabase_admin()
    res = sb.table("users").select("email").eq("id", user_id).limit(1).execute()
    rows = res.data or []
    return rows[0]["email"] if rows else ""


# ---- appointments (Phase 2b) ----


def list_appointments(
    tenant_id: str,
    *,
    status: str | None,
    service_id: str | None,
    resource_id: str | None,
    date_from: str | None,
    date_to: str | None,
) -> list[dict]:
    sb = get_supabase_admin()
    q = (
        sb.table("bookings")
        .select(
            "id, status, start_utc, end_utc, reschedule_count, notes, source, "
            "service_id, resource_id, customer_id, customer_name, "
            "booking_customers(name, email, phone, timezone), "
            "booking_services(name), booking_resources(name)"
        )
        .eq("tenant_id", tenant_id)
    )
    if status:
        q = q.eq("status", status)
    if service_id:
        q = q.eq("service_id", service_id)
    if resource_id:
        q = q.eq("resource_id", resource_id)
    if date_from:
        q = q.gte("start_utc", date_from)
    if date_to:
        q = q.lte("start_utc", date_to)
    return (q.order("start_utc", desc=True).execute()).data or []


def get_booking(tenant_id: str, booking_id: str) -> dict | None:
    sb = get_supabase_admin()
    res = (
        sb.table("bookings")
        .select("*")
        .eq("tenant_id", tenant_id)
        .eq("id", booking_id)
        .limit(1)
        .execute()
    )
    rows = res.data or []
    return rows[0] if rows else None


# ---- stats (Phase 2c) ----


def list_bookings_for_stats(
    tenant_id: str,
    date_from: str | None,
    date_to: str | None,
    *,
    resource_id: str | None = None,
) -> list[dict]:
    sb = get_supabase_admin()
    q = (
        sb.table("bookings")
        .select("status, start_utc, resource_id, booking_services(name), booking_resources(name)")
        .eq("tenant_id", tenant_id)
    )
    if date_from:
        q = q.gte("start_utc", date_from)
    if date_to:
        q = q.lte("start_utc", date_to)
    if resource_id:
        q = q.eq("resource_id", resource_id)
    rows = q.execute().data or []
    for r in rows:
        r["service_name"] = (r.get("booking_services") or {}).get("name")
        r["resource_name"] = (r.get("booking_resources") or {}).get("name")
    return rows
