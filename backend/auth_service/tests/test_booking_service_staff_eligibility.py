"""Service <-> staff eligibility: a service linked to only one staff member must
never offer or auto-assign an unlinked staff member.

This pins existing correct behaviour so the Resources->Staff relabel (and any
future refactor of `_free_resource_for` / `_availability_for_day`) cannot regress
it. Eligibility is enforced at `load_eligible_resources`, which returns only the
resources linked via `booking_service_resources`; we stub that linker to return
ONLY staff A while staff B exists, then drive the real availability/assignment
code and assert B is never produced."""

from datetime import UTC, datetime, time
from unittest.mock import patch
from zoneinfo import ZoneInfo

from auth_service.routers import booking as booking_router
from auth_service.services.booking_tenant import TenantConfig

TZ = "Europe/Bucharest"

TENANT = TenantConfig(
    tenant_id="t1",
    public_slug="acme",
    timezone=TZ,
    locale="en",
    business_name="Acme",
    owner_notification_email="owner@acme.com",
    email_from_name="Acme",
    meeting_url="",
    slot_granularity_min=30,
    reminders_enabled=False,
    reminder_offsets_min=[],
    calendar_provider="none",
    is_active=True,
)
SERVICE = {
    "id": "s1",
    "tenant_id": "t1",
    "name": "Cut",
    "duration_min": 30,
    "buffer_before_min": 0,
    "buffer_after_min": 0,
    "lead_time_min": 0,
    "max_advance_days": 365,
    "is_active": True,
    "sort_order": 0,
}
# Two staff resources exist; only A is linked to the service.
STAFF_A = {"id": "staff-A", "tenant_id": "t1", "name": "Alice", "type": "staff", "is_active": True}
STAFF_B = {"id": "staff-B", "tenant_id": "t1", "name": "Bob", "type": "staff", "is_active": True}

# A weekday far in the future so lead-time/max-advance never excludes it.
DAY = datetime(2099, 6, 10).date()  # Wednesday
# 09:00-17:00 local hours for BOTH staff (so B would be offered if eligibility
# leaked). Postgres dow for Wednesday = 3.
HOURS = [
    {"resource_id": "staff-A", "weekday": 3, "start_time": "09:00", "end_time": "17:00"},
    {"resource_id": "staff-B", "weekday": 3, "start_time": "09:00", "end_time": "17:00"},
]


def _only_a(tenant_id, service_id):
    """Mirror booking_service_resources linking the service to staff A only."""
    assert service_id == "s1"
    return [STAFF_A]


def test_unlinked_staff_never_assigned_at_booking_time():
    start = datetime.combine(DAY, time(10, 0), tzinfo=ZoneInfo(TZ)).astimezone(UTC)
    now = datetime(2099, 6, 1, tzinfo=UTC)
    with (
        patch.object(booking_router.booking_repo, "load_eligible_resources", _only_a),
        patch.object(booking_router.booking_repo, "load_hours", return_value=HOURS),
        patch.object(booking_router.booking_repo, "load_exceptions", return_value=[]),
        patch.object(
            booking_router.booking_repo,
            "busy_guard_intervals_by_resource",
            return_value={},
        ),
    ):
        rid = booking_router._free_resource_for(
            cfg=TENANT, service=SERVICE, start_utc=start, now_utc=now
        )
    assert rid == "staff-A"
    assert rid != "staff-B"


def test_unlinked_staff_does_not_widen_availability():
    """Availability is computed only over eligible (linked) staff. Even though B
    has identical open hours, the day's slots come solely from A's schedule."""
    now = datetime(2099, 6, 1, tzinfo=UTC)
    with (
        patch.object(booking_router.booking_repo, "load_eligible_resources", _only_a),
        patch.object(booking_router.booking_repo, "load_hours", return_value=HOURS),
        patch.object(booking_router.booking_repo, "load_exceptions", return_value=[]),
        patch.object(
            booking_router.booking_repo,
            "busy_guard_intervals_by_resource",
            return_value={},
        ) as busy,
    ):
        starts = booking_router._availability_for_day(
            cfg=TENANT, service=SERVICE, day=DAY, now_utc=now
        )
    # Slots exist (A is open), and the busy-interval query was scoped to A only.
    assert starts, "expected available slots from the linked staff member"
    busy.assert_called_once()
    assert busy.call_args.kwargs["resource_ids"] == ["staff-A"]


def test_no_eligible_staff_yields_no_assignment():
    """A service linked to zero staff offers nothing and assigns no one."""
    start = datetime.combine(DAY, time(10, 0), tzinfo=ZoneInfo(TZ)).astimezone(UTC)
    now = datetime(2099, 6, 1, tzinfo=UTC)
    with patch.object(booking_router.booking_repo, "load_eligible_resources", return_value=[]):
        rid = booking_router._free_resource_for(
            cfg=TENANT, service=SERVICE, start_utc=start, now_utc=now
        )
        starts = booking_router._availability_for_day(
            cfg=TENANT, service=SERVICE, day=DAY, now_utc=now
        )
    assert rid is None
    assert starts == []
