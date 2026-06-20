from auth_service.services.booking_reminder_email import render_html
from auth_service.services.email_layout import Brand

TENANT_BRAND = Brand(
    business_name="Acme Corp",
    logo_url="https://acme.example/logo.png",
    accent="#ff0000",
    canonical_url="https://acme.example",
)


def test_reminder_html_has_header_time_and_note():
    html_body = render_html(
        name="Jane",
        when_label="Today · 15:00 (Europe/London)",
        note="bring the brief",
        meeting_url="https://meet.example/abc",
    )
    assert "Roman Technologies" in html_body
    assert "Appointment reminder" in html_body
    assert "15:00 (Europe/London)" in html_body
    assert "https://meet.example/abc" in html_body


def test_reminder_html_escapes_fields():
    html_body = render_html(name="<x>", when_label="t", note="<script>", meeting_url="")
    assert "&lt;x&gt;" in html_body
    assert "&lt;script&gt;" in html_body


# ---- P4 brand tests ----


def test_reminder_html_custom_brand():
    html_body = render_html(
        name="Jane",
        when_label="Today · 15:00",
        note=None,
        meeting_url="",
        brand=TENANT_BRAND,
    )
    assert "Acme Corp" in html_body
    assert "#ff0000" in html_body
    assert "Roman Technologies" not in html_body


def test_reminder_html_default_brand_unchanged():
    """Render with no brand → same as with DEFAULT_BRAND."""
    from auth_service.services.email_layout import DEFAULT_BRAND

    html_no_brand = render_html(name="Jane", when_label="t", note=None, meeting_url="")
    html_default = render_html(
        name="Jane", when_label="t", note=None, meeting_url="", brand=DEFAULT_BRAND
    )
    assert html_no_brand == html_default


# ---- H2 per-field colour overrides ----


def test_reminder_html_per_field_heading_colour():
    html_body = render_html(
        name="Jane",
        when_label="Today · 15:00",
        note=None,
        meeting_url="https://meet.example/abc",
        copy={"reminder_heading__color": "#ff8800", "join_cta__color": "#ffffff"},
    )
    assert "color:#ff8800" in html_body


def test_reminder_html_drops_unsafe_colour():
    html_body = render_html(
        name="Jane",
        when_label="Today · 15:00",
        note=None,
        meeting_url="",
        copy={"reminder_heading__color": 'x;"><script>boom</script>'},
    )
    assert "<script>" not in html_body
    assert "boom" not in html_body


# ---- add-to-calendar button (customer reminder) ----


def test_reminder_html_has_add_to_calendar_when_times_given():
    """The reminder must offer 'Add to calendar' to the customer, even for an
    in-person business (no meeting URL)."""
    from datetime import UTC, datetime

    html_body = render_html(
        name="Jane",
        when_label="Today · 15:00",
        note=None,
        meeting_url="",  # in-person — no meeting link
        start_utc=datetime(2026, 6, 11, 13, 0, tzinfo=UTC),
        end_utc=datetime(2026, 6, 11, 13, 45, tzinfo=UTC),
        business_name="Samir Kapsalon",
    )
    assert "Add to Google Calendar" in html_body
    assert "calendar.google.com/calendar/render" in html_body


def test_reminder_html_no_add_to_calendar_without_times():
    """Back-compat: no datetimes → no calendar button (and no crash)."""
    html_body = render_html(name="Jane", when_label="t", note=None, meeting_url="")
    assert "Add to Google Calendar" not in html_body
