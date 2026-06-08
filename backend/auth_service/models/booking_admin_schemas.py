"""Request/response models for the owner-facing booking config API (Phase 2a)."""

from __future__ import annotations

from pydantic import BaseModel


class SettingsPatch(BaseModel):
    timezone: str | None = None
    locale: str | None = None
    business_name: str | None = None
    logo_url: str | None = None
    primary_color: str | None = None
    accent_color: str | None = None
    email_from_name: str | None = None
    owner_notification_email: str | None = None
    meeting_url: str | None = None
    slot_granularity_min: int | None = None
    reminders_enabled: bool | None = None
    reminder_offsets_min: list[int] | None = None
    calendar_provider: str | None = None
    public_slug: str | None = None
    email_copy: dict | None = None


class EmailPreviewIn(BaseModel):
    case: str
    draft: dict = {}


class ServiceIn(BaseModel):
    name: str
    description: str = ""
    color: str = ""
    duration_min: int
    buffer_before_min: int = 0
    buffer_after_min: int = 0
    lead_time_min: int = 0
    max_advance_days: int = 60
    is_active: bool = True
    sort_order: int = 0
    resource_ids: list[str] = []


class ResourceIn(BaseModel):
    name: str
    type: str = "generic"
    capacity: int = 1
    is_active: bool = True
    sort_order: int = 0


class HoursRow(BaseModel):
    resource_id: str | None = None
    weekday: int  # 0=Sun .. 6=Sat
    start_time: str  # "HH:MM"
    end_time: str


class HoursReplace(BaseModel):
    hours: list[HoursRow]


class ExceptionIn(BaseModel):
    resource_id: str | None = None
    date: str  # "YYYY-MM-DD"
    is_closed: bool = True
    start_time: str | None = None
    end_time: str | None = None


class PolicyPatch(BaseModel):
    service_id: str | None = None  # null = tenant default
    allow_reschedule: bool = True
    reschedule_window_hours: int = 24
    max_reschedules: int = 2
    allow_cancel: bool = True
    cancellation_window_hours: int = 24
    policy_text: str = ""


class CustomerCreate(BaseModel):
    name: str
    email: str
    phone: str | None = None
    tz: str | None = None


class AppointmentCreate(BaseModel):
    service_id: str
    resource_id: str | None = None
    start_utc: str
    customer: CustomerCreate
    note: str | None = None


class AppointmentAction(BaseModel):
    action: str  # "cancel" | "reschedule" | "no_show" | "complete"
    start_utc: str | None = None  # required for reschedule
    reason: str | None = None
