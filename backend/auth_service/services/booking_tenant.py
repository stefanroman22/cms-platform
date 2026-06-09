"""Resolve a tenant's booking configuration from booking_settings. A 'tenant'
is a project; the public_slug is the addressing key used by the widget."""

from __future__ import annotations

from dataclasses import dataclass, field

from .supabase_client import get_supabase_admin

_FIELDS = (
    "tenant_id, public_slug, timezone, locale, business_name, "
    "owner_notification_email, email_from_name, meeting_url, slot_granularity_min, "
    "reminders_enabled, reminder_offsets_min, calendar_provider, is_active, "
    "logo_url, primary_color, accent_color, widget_color, email_copy"
)


@dataclass(frozen=True)
class TenantConfig:
    tenant_id: str
    public_slug: str
    timezone: str
    locale: str
    business_name: str | None
    owner_notification_email: str
    email_from_name: str | None
    meeting_url: str
    slot_granularity_min: int
    reminders_enabled: bool
    reminder_offsets_min: list[int]
    calendar_provider: str
    is_active: bool
    logo_url: str | None = None
    primary_color: str | None = None
    accent_color: str | None = None
    widget_color: str | None = None
    email_copy: dict = field(default_factory=dict)
    # The client's live website URL (from projects.website_url) — used as the email
    # footer "Sent from <site>" so client emails are never branded roman-technologies.
    website_url: str | None = None


def _to_config(row: dict, *, website_url: str | None = None) -> TenantConfig:
    return TenantConfig(
        tenant_id=row["tenant_id"],
        public_slug=row["public_slug"],
        timezone=row["timezone"],
        locale=row.get("locale") or "en",
        business_name=row.get("business_name"),
        owner_notification_email=row["owner_notification_email"],
        email_from_name=row.get("email_from_name"),
        meeting_url=row.get("meeting_url") or "",
        slot_granularity_min=row.get("slot_granularity_min") or 15,
        reminders_enabled=bool(row.get("reminders_enabled")),
        reminder_offsets_min=list(row.get("reminder_offsets_min") or []),
        calendar_provider=row.get("calendar_provider") or "none",
        is_active=bool(row.get("is_active")),
        logo_url=row.get("logo_url"),
        primary_color=row.get("primary_color"),
        accent_color=row.get("accent_color"),
        widget_color=row.get("widget_color"),
        email_copy=row.get("email_copy") or {},
        website_url=website_url,
    )


def _load_where(column: str, value: str) -> TenantConfig | None:
    sb = get_supabase_admin()
    res = sb.table("booking_settings").select(_FIELDS).eq(column, value).limit(1).execute()
    rows = res.data or []
    if not rows:
        return None
    row = rows[0]
    # Best-effort lookup of the client's live site for the email footer branding.
    website_url = None
    try:
        pr = (
            sb.table("projects").select("website_url").eq("id", row["tenant_id"]).limit(1).execute()
        )
        if pr.data:
            website_url = pr.data[0].get("website_url")
    except Exception:  # noqa: BLE001
        website_url = None
    cfg = _to_config(row, website_url=website_url)
    return cfg if cfg.is_active else None


def load_tenant_by_slug(slug: str) -> TenantConfig | None:
    return _load_where("public_slug", slug)


def load_tenant_by_id(tenant_id: str) -> TenantConfig | None:
    return _load_where("tenant_id", tenant_id)
