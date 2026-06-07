from datetime import datetime
from unittest.mock import patch
from zoneinfo import ZoneInfo

from auth_service.services import booking_email, booking_i18n, email_layout
from auth_service.services.booking_email import render_host_html, render_visitor_html
from auth_service.services.email_layout import DEFAULT_BRAND, Brand

UTC = ZoneInfo("UTC")
BOOKING = {
    "name": "Jane <b>Doe</b>",
    "email": "jane@acme.com",
    "note": "Discuss a new site",
    "when_label": "Wed, 10 Jun 2026 · 09:00 (Europe/Bucharest)",
    "start_utc": datetime(2026, 6, 10, 6, 0, tzinfo=UTC),
    "end_utc": datetime(2026, 6, 10, 6, 45, tzinfo=UTC),
}


def test_host_email_has_header_link_no_addtocal():
    html = render_host_html(booking=BOOKING, meeting_url="https://meet.example/abc")
    assert "Roman Technologies" in html
    assert "logo_dark.png" in html
    assert "Jane &lt;b&gt;Doe&lt;/b&gt;" in html  # escaped
    assert "jane@acme.com" in html
    assert "https://meet.example/abc" in html  # explicit link + Join button
    assert "Join the meeting" in html
    # Host event is auto-created on their calendar → no add-to-cal button.
    assert "Add to Google Calendar" not in html


def test_visitor_email_includes_link_button_and_addtocal():
    html = render_visitor_html(booking=BOOKING, meeting_url="https://meet.example/abc")
    assert "https://meet.example/abc" in html
    assert "Join the meeting" in html
    assert "Add to Google Calendar" in html
    assert "calendar.google.com/calendar/render" in html
    # Client's calendar event is titled for the client's perspective.
    assert "Booking+%40+Roman+Technologies" in html


def test_visitor_email_no_meeting_block_when_no_url():
    """No meeting URL → render NO meeting-link section at all (the link is an
    opt-in extension; in-person bookings show nothing about a link)."""
    html = render_visitor_html(booking=BOOKING, meeting_url="")
    assert "Join the call" not in html
    assert "email you the link" not in html
    assert "Meeting link" not in html


def test_visitor_email_includes_manage_link_when_given():
    html = render_visitor_html(
        booking=BOOKING,
        meeting_url="https://meet.example/abc",
        manage_url="https://site/manage/tok123",
    )
    assert "Manage your booking" in html
    assert "https://site/manage/tok123" in html


def test_host_notification_uses_passed_recipient():
    booking = {
        "name": "Jane",
        "email": "j@a.com",
        "note": "",
        "when_label": "soon",
        "start_utc": None,
        "end_utc": None,
    }
    with patch("auth_service.services.booking_email._send", return_value={}) as snd:
        booking_email.send_host_notification(
            booking=booking, meeting_url="", host_email="owner@tenant.com"
        )
    assert snd.call_args.kwargs["to_email"] == "owner@tenant.com"


# ---- P4 brand tests ----

TENANT_BRAND = Brand(
    business_name="Acme Corp",
    logo_url="https://acme.example/logo.png",
    accent="#ff0000",
    canonical_url="https://acme.example",
)


def test_host_email_custom_brand_shows_tenant_name():
    html = render_host_html(booking=BOOKING, meeting_url="", brand=TENANT_BRAND)
    assert "Acme Corp" in html
    assert "acme.example/logo.png" in html
    assert "#ff0000" in html
    assert "Roman Technologies" not in html


def test_visitor_email_custom_brand_shows_tenant_name():
    html = render_visitor_html(
        booking=BOOKING, meeting_url="https://meet.example/x", brand=TENANT_BRAND
    )
    assert "Acme Corp" in html
    # add-to-cal title should use tenant name
    assert "Acme+Corp" in html
    assert "Roman Technologies" not in html


def test_default_brand_is_roman_technologies():
    """Render with no brand arg → same as DEFAULT_BRAND → Roman Technologies."""
    html_no_brand = render_host_html(booking=BOOKING, meeting_url="")
    html_default = render_host_html(booking=BOOKING, meeting_url="", brand=DEFAULT_BRAND)
    assert html_no_brand == html_default


def test_email_layout_header_default_unchanged():
    """email_layout.header('Some subtitle') with no brand must produce the
    same output as before the P4 change (byte-for-byte)."""
    result = email_layout.header("Some subtitle")
    assert "Roman Technologies" in result
    assert "logo_dark.png" in result
    assert "#18181b" in result
    assert "Some subtitle" in result


def test_from_name_flows_into_resend():
    booking = {
        "name": "Jane",
        "email": "j@a.com",
        "note": "",
        "when_label": "soon",
        "start_utc": None,
        "end_utc": None,
    }
    with patch("auth_service.services.booking_email._send", return_value={}) as snd:
        booking_email.send_host_notification(
            booking=booking, meeting_url="", from_name="Acme Bookings"
        )
    assert snd.call_args.kwargs["from_name"] == "Acme Bookings"


def test_visitor_email_copy_override():
    html = render_visitor_html(
        booking=BOOKING, meeting_url="https://m/x", copy={"confirmed_heading": "All set, {name}!"}
    )
    assert "All set, Jane" in html
    assert "You&#39;re booked" not in html


def test_visitor_email_accent_on_button():
    html = render_visitor_html(
        booking=BOOKING,
        meeting_url="https://m/x",
        brand=Brand(
            business_name="Acme",
            logo_url="https://a/l.png",
            accent="#ff0000",
            canonical_url="https://a",
        ),
    )
    assert "#ff0000" in html  # header AND join button


def test_send_internal_from_name_sets_from_header(monkeypatch):
    """_send passes from_name into the Resend 'from' field."""
    import json
    import urllib.request

    from auth_service.core.config import settings

    monkeypatch.setattr(settings, "RESEND_API_KEY", "test-key")

    captured = {}

    class FakeResp:
        def read(self):
            return b'{"id":"x"}'

        def __enter__(self):
            return self

        def __exit__(self, *a):
            pass

    def fake_urlopen(req, timeout=10):
        captured["body"] = json.loads(req.data.decode())
        return FakeResp()

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)

    from auth_service.services.booking_email import _send

    _send(to_email="x@x.com", subject="s", html_body="h", text_body="t", from_name="Acme Bookings")
    assert captured["body"]["from"].startswith("Acme Bookings <")


# ---- A1 de-Stefan tests ----


def test_no_hardcoded_host_name_in_strings():
    blob = "\n".join(booking_i18n.STRINGS["en"].values())
    assert "Stefan" not in blob


def test_visitor_html_generic_tenant_no_stefan():
    ACME_BRAND = Brand(
        business_name="Acme Salon",
        logo_url="https://acme.example/logo.png",
        accent="#18181b",
        canonical_url="https://acme.example",
    )
    html = render_visitor_html(
        booking=BOOKING,
        meeting_url="https://meet.example/abc",
        brand=ACME_BRAND,
    )
    assert "Acme Salon" in html
    assert "Stefan" not in html
