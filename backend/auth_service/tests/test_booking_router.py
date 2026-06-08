from datetime import UTC, datetime, timedelta
from unittest.mock import patch
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient

from auth_service.core.config import settings
from auth_service.main import app
from auth_service.services.booking_tenant import TenantConfig

UTC_ZONE = ZoneInfo("UTC")
T1 = TenantConfig(
    tenant_id="a7fccf9f-35ba-4655-baba-6744cab738dc",
    public_slug="roman-technologies-website",
    timezone="Europe/Berlin",
    locale="en",
    business_name="Roman Technologies",
    owner_notification_email="stefanromanpers@gmail.com",
    email_from_name="Roman Technologies CMS",
    meeting_url="",
    slot_granularity_min=45,
    reminders_enabled=True,
    reminder_offsets_min=[60],
    calendar_provider="none",
    is_active=True,
)
SVC = {
    "id": "s1",
    "duration_min": 45,
    "buffer_before_min": 0,
    "buffer_after_min": 0,
    "lead_time_min": 120,
    "max_advance_days": 120,
}


@pytest.fixture
def client():
    return TestClient(app)


def test_legacy_slots_returns_iso(client):
    starts = [__import__("datetime").datetime(2099, 6, 10, 7, 0, tzinfo=UTC_ZONE)]
    with (
        patch("auth_service.routers.booking.booking_tenant.load_tenant_by_slug", return_value=T1),
        patch("auth_service.routers.booking.booking_repo.load_active_services", return_value=[SVC]),
        patch("auth_service.routers.booking._availability_for_day", return_value=starts),
    ):
        r = client.get("/booking/slots?date=2099-06-10&tz=Europe/London")
    assert r.status_code == 200
    assert r.json()["slots"][0].startswith("2099-06-10")


def test_legacy_booking_honeypot(client):
    with (
        patch("auth_service.routers.booking.booking_tenant.load_tenant_by_slug", return_value=T1),
        patch("auth_service.routers.booking.booking_repo.load_active_services", return_value=[SVC]),
    ):
        r = client.post(
            "/booking",
            json={
                "slot_start": "2099-06-10T06:00:00+00:00",
                "name": "Bot",
                "email": "b@b.com",
                "website": "x",
            },
        )
    assert r.status_code == 200 and r.json()["success"] is True


def test_legacy_booking_422_bad_email(client):
    with (
        patch("auth_service.routers.booking.booking_tenant.load_tenant_by_slug", return_value=T1),
        patch("auth_service.routers.booking.booking_repo.load_active_services", return_value=[SVC]),
    ):
        r = client.post(
            "/booking",
            json={"slot_start": "2099-06-10T06:00:00+00:00", "name": "J", "email": "nope"},
        )
    assert r.status_code == 422


def test_legacy_booking_happy_path(client, monkeypatch):
    monkeypatch.setattr(settings, "RESEND_API_KEY", "k")
    with (
        patch("auth_service.routers.booking.booking_tenant.load_tenant_by_slug", return_value=T1),
        patch("auth_service.routers.booking.booking_repo.load_active_services", return_value=[SVC]),
        patch("auth_service.routers.booking.booking_repo.load_service", return_value=SVC),
        patch("auth_service.routers.booking._free_resource_for", return_value="r1"),
        patch("auth_service.routers.booking.booking_repo.upsert_customer", return_value="c1"),
        patch("auth_service.routers.booking.booking_repo.insert_booking", return_value="b1"),
        patch("auth_service.routers.booking.booking_repo.insert_audit"),
        patch(
            "auth_service.routers.booking.booking_repo.notification_already_sent",
            return_value=False,
        ),
        patch("auth_service.routers.booking.booking_repo.record_notification"),
        patch("auth_service.routers.booking.booking_email.send_host_notification") as host,
        patch("auth_service.routers.booking.booking_email.send_visitor_confirmation") as vis,
    ):
        r = client.post(
            "/booking",
            json={
                "slot_start": "2099-06-10T06:00:00+00:00",
                "name": "Jane",
                "email": "jane@acme.com",
                "note": "hi",
                "visitor_timezone": "Europe/London",
            },
        )
    assert r.status_code == 200, r.text
    host.assert_called_once()
    vis.assert_called_once()


def test_reminders_requires_secret(client, monkeypatch):
    monkeypatch.setattr(settings, "BOOKING_CRON_SECRET", "s3cr3t")
    r = client.post("/booking/cron/reminders")
    assert r.status_code == 403


def _make_tenant_with_offsets(offsets, enabled=True):
    return TenantConfig(
        tenant_id="a7fccf9f-35ba-4655-baba-6744cab738dc",
        public_slug="roman-technologies-website",
        timezone="Europe/Berlin",
        locale="en",
        business_name="Roman Technologies",
        owner_notification_email="stefanromanpers@gmail.com",
        email_from_name=None,
        meeting_url="",
        slot_granularity_min=45,
        reminders_enabled=enabled,
        reminder_offsets_min=offsets,
        calendar_provider="none",
        is_active=True,
    )


def test_reminders_sends_for_due_offset(client, monkeypatch):
    """Booking 2h out → 120-min offset send window fires once."""
    monkeypatch.setattr(settings, "BOOKING_CRON_SECRET", "s3cr3t")
    monkeypatch.setattr(settings, "RESEND_API_KEY", "k")
    now = datetime.now(UTC)
    # start is exactly at now + 122 min → within window [now+117, now+122) for offset=120+5 window
    # Actually window is send_start = start - (offset+5), send_end = start - offset
    # We want now in [start - 125, start - 120) i.e. start ~= now + 122
    start_utc = now + timedelta(minutes=122)
    cfg = _make_tenant_with_offsets([1440, 120])
    due = [
        {
            "id": "b1",
            "tenant_id": "t1",
            "customer_id": "c1",
            "notes": None,
            "start_utc": start_utc.isoformat(),
        }
    ]
    with (
        patch("auth_service.routers.booking.booking_repo.due_reminders", return_value=due),
        patch("auth_service.routers.booking.booking_tenant.load_tenant_by_id", return_value=cfg),
        patch(
            "auth_service.routers.booking.booking_repo.load_customer",
            return_value={"email": "j@a.com", "name": "Jane", "timezone": "Europe/London"},
        ),
        patch(
            "auth_service.routers.booking.booking_repo.notification_already_sent",
            return_value=False,
        ) as not_sent,
        patch("auth_service.routers.booking.booking_repo.record_notification") as record,
        patch("auth_service.routers.booking.booking_reminder_email.send") as snd,
    ):
        r = client.post("/booking/cron/reminders", headers={"X-Cron-Secret": "s3cr3t"})
    assert r.status_code == 200
    assert r.json()["sent"] == 1
    snd.assert_called_once()
    record.assert_called_once()
    # key should include offset 120
    call_kwargs = record.call_args.kwargs
    assert call_kwargs["idempotency_key"] == "b1:reminder:120"
    assert call_kwargs["offset_min"] == 120


def test_reminders_use_booking_snapshot_name(client, monkeypatch):
    """Reminder email uses the booking's snapshot name, not the (possibly
    overwritten) shared customer row's name."""
    monkeypatch.setattr(settings, "BOOKING_CRON_SECRET", "s3cr3t")
    monkeypatch.setattr(settings, "RESEND_API_KEY", "k")
    now = datetime.now(UTC)
    start_utc = now + timedelta(minutes=122)
    cfg = _make_tenant_with_offsets([120])
    due = [
        {
            "id": "b1",
            "tenant_id": "t1",
            "customer_id": "c1",
            "customer_name": "Alice",
            "notes": None,
            "start_utc": start_utc.isoformat(),
        }
    ]
    with (
        patch("auth_service.routers.booking.booking_repo.due_reminders", return_value=due),
        patch("auth_service.routers.booking.booking_tenant.load_tenant_by_id", return_value=cfg),
        patch(
            "auth_service.routers.booking.booking_repo.load_customer",
            return_value={"email": "shared@a.com", "name": "Remus", "timezone": None},
        ),
        patch(
            "auth_service.routers.booking.booking_repo.notification_already_sent",
            return_value=False,
        ),
        patch("auth_service.routers.booking.booking_repo.record_notification"),
        patch("auth_service.routers.booking.booking_reminder_email.send") as snd,
    ):
        r = client.post("/booking/cron/reminders", headers={"X-Cron-Secret": "s3cr3t"})
    assert r.status_code == 200
    assert snd.call_args.kwargs["name"] == "Alice"


def test_reminders_deduped_on_second_run(client, monkeypatch):
    """Second cron run → notification_already_sent=True → nothing sent."""
    monkeypatch.setattr(settings, "BOOKING_CRON_SECRET", "s3cr3t")
    monkeypatch.setattr(settings, "RESEND_API_KEY", "k")
    now = datetime.now(UTC)
    start_utc = now + timedelta(minutes=122)
    cfg = _make_tenant_with_offsets([120])
    due = [
        {
            "id": "b1",
            "tenant_id": "t1",
            "customer_id": "c1",
            "notes": None,
            "start_utc": start_utc.isoformat(),
        }
    ]
    with (
        patch("auth_service.routers.booking.booking_repo.due_reminders", return_value=due),
        patch("auth_service.routers.booking.booking_tenant.load_tenant_by_id", return_value=cfg),
        patch(
            "auth_service.routers.booking.booking_repo.load_customer",
            return_value={"email": "j@a.com", "name": "Jane", "timezone": None},
        ),
        patch(
            "auth_service.routers.booking.booking_repo.notification_already_sent", return_value=True
        ),
        patch("auth_service.routers.booking.booking_reminder_email.send") as snd,
    ):
        r = client.post("/booking/cron/reminders", headers={"X-Cron-Secret": "s3cr3t"})
    assert r.status_code == 200
    assert r.json()["sent"] == 0
    snd.assert_not_called()


def test_reminders_not_due_offset_not_fired(client, monkeypatch):
    """Booking 25h out → only 1440-min offset could fire but send window not reached."""
    monkeypatch.setattr(settings, "BOOKING_CRON_SECRET", "s3cr3t")
    monkeypatch.setattr(settings, "RESEND_API_KEY", "k")
    now = datetime.now(UTC)
    # start = now + 25h; offset 1440min = 24h; send window = [start-1445, start-1440)
    # now is NOT in that window (now = start - 25h = start - 1500min, window is -1445 to -1440)
    start_utc = now + timedelta(hours=25)
    cfg = _make_tenant_with_offsets([1440, 120])
    due = [
        {
            "id": "b1",
            "tenant_id": "t1",
            "customer_id": "c1",
            "notes": None,
            "start_utc": start_utc.isoformat(),
        }
    ]
    with (
        patch("auth_service.routers.booking.booking_repo.due_reminders", return_value=due),
        patch("auth_service.routers.booking.booking_tenant.load_tenant_by_id", return_value=cfg),
        patch(
            "auth_service.routers.booking.booking_repo.load_customer",
            return_value={"email": "j@a.com", "name": "Jane", "timezone": None},
        ),
        patch(
            "auth_service.routers.booking.booking_repo.notification_already_sent",
            return_value=False,
        ),
        patch("auth_service.routers.booking.booking_reminder_email.send") as snd,
    ):
        r = client.post("/booking/cron/reminders", headers={"X-Cron-Secret": "s3cr3t"})
    assert r.status_code == 200
    assert r.json()["sent"] == 0
    snd.assert_not_called()


def test_reminders_disabled_nothing_sent(client, monkeypatch):
    """reminders_enabled=False → nothing sent regardless of offsets."""
    monkeypatch.setattr(settings, "BOOKING_CRON_SECRET", "s3cr3t")
    monkeypatch.setattr(settings, "RESEND_API_KEY", "k")
    now = datetime.now(UTC)
    start_utc = now + timedelta(minutes=122)
    cfg = _make_tenant_with_offsets([120], enabled=False)
    due = [
        {
            "id": "b1",
            "tenant_id": "t1",
            "customer_id": "c1",
            "notes": None,
            "start_utc": start_utc.isoformat(),
        }
    ]
    with (
        patch("auth_service.routers.booking.booking_repo.due_reminders", return_value=due),
        patch("auth_service.routers.booking.booking_tenant.load_tenant_by_id", return_value=cfg),
        patch("auth_service.routers.booking.booking_reminder_email.send") as snd,
    ):
        r = client.post("/booking/cron/reminders", headers={"X-Cron-Secret": "s3cr3t"})
    assert r.status_code == 200
    assert r.json()["sent"] == 0
    snd.assert_not_called()


def test_brand_for_uses_accent_color():
    """The email accent comes from accent_color (what the Emails editor saves),
    not primary_color. Regression: emails rendered the default dark header because
    _brand_for read primary_color while the editor wrote accent_color."""
    from dataclasses import replace

    from auth_service.routers.booking import _brand_for

    brand = _brand_for(replace(T1, accent_color="#1919d2", primary_color=None))
    assert brand.accent == "#1919d2"


def test_brand_for_falls_back_to_primary_color():
    from dataclasses import replace

    from auth_service.routers.booking import _brand_for

    brand = _brand_for(replace(T1, accent_color=None, primary_color="#abcdef"))
    assert brand.accent == "#abcdef"
