from datetime import datetime
from zoneinfo import ZoneInfo

from auth_service.services.booking_manage_email import (
    render_cancel_client,
    render_cancel_host,
    render_reschedule_client,
    render_reschedule_host,
)
from auth_service.services.email_layout import Brand

UTC = ZoneInfo("UTC")

TENANT_BRAND = Brand(
    business_name="Acme Corp",
    logo_url="https://acme.example/logo.png",
    accent="#ff0000",
    canonical_url="https://acme.example",
)


def test_cancel_client_branded_and_escaped():
    h = render_cancel_client(name="<b>Jo</b>", when_label="Thu 11 Jun · 10:00 (CET)")
    assert "Roman Technologies" in h
    assert "cancel" in h.lower()
    assert "&lt;b&gt;Jo&lt;/b&gt;" in h
    assert "Thu 11 Jun · 10:00 (CET)" in h


def test_cancel_host_names_the_client():
    h = render_cancel_host(name="Jo", when_label="Thu 11 Jun · 11:00 (Europe/Bucharest)")
    assert "Jo" in h
    assert "Thu 11 Jun · 11:00 (Europe/Bucharest)" in h


def test_reschedule_client_shows_new_time_links_and_addtocal():
    h = render_reschedule_client(
        name="Jo",
        new_when="Fri 12 Jun · 14:00 (CET)",
        meeting_url="https://meet.example/x",
        manage_url="https://site/manage/tok",
        new_start=datetime(2026, 6, 12, 12, 0, tzinfo=UTC),
        new_end=datetime(2026, 6, 12, 12, 45, tzinfo=UTC),
    )
    assert "Fri 12 Jun · 14:00 (CET)" in h
    assert "https://meet.example/x" in h
    assert "https://site/manage/tok" in h
    assert "Add to Google Calendar" in h
    assert "calendar.google.com/calendar/render" in h


def test_reschedule_host_shows_old_and_new():
    h = render_reschedule_host(
        name="Jo",
        old_when="Thu 11 Jun · 10:00",
        new_when="Fri 12 Jun · 14:00",
    )
    assert "Thu 11 Jun · 10:00" in h
    assert "Fri 12 Jun · 14:00" in h


# ---- P4 brand tests ----


def test_cancel_client_custom_brand():
    h = render_cancel_client(name="Jo", when_label="Thu 11 Jun · 10:00", brand=TENANT_BRAND)
    assert "Acme Corp" in h
    assert "#ff0000" in h
    assert "Roman Technologies" not in h


def test_cancel_host_custom_brand():
    h = render_cancel_host(name="Jo", when_label="Thu 11 Jun · 10:00", brand=TENANT_BRAND)
    assert "Acme Corp" in h
    assert "Roman Technologies" not in h


def test_reschedule_client_custom_brand_uses_tenant_name_in_cal():
    h = render_reschedule_client(
        name="Jo",
        new_when="Fri 12 Jun · 14:00 (CET)",
        meeting_url="https://meet.example/x",
        manage_url="https://site/manage/tok",
        new_start=datetime(2026, 6, 12, 12, 0, tzinfo=UTC),
        new_end=datetime(2026, 6, 12, 12, 45, tzinfo=UTC),
        brand=TENANT_BRAND,
    )
    assert "Acme Corp" in h
    assert "Acme+Corp" in h  # URL-encoded in the cal link
    assert "Roman Technologies" not in h
