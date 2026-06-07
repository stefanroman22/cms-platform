"""
Tests for booking provisioning path in scan.py (_provision_booking).

Covers:
  1. Call ORDER: POST .../bookings/enable BEFORE any PATCH settings / POST resources
     / POST services / PUT hours calls.
  2. destination_email: PATCH body has owner_notification_email == "client@acme.com"
     when destination_email is set; falls back to "stefanromanpers@gmail.com" when empty.
  3. lib/booking.ts: written into out_dir; contains the public slug and
     getServices / getAvailability / createBooking.
  4. No-op: manifest without a booking block triggers zero booking API calls.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import scan

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _urlopen_resp(body: bytes = b"{}"):
    m = MagicMock()
    m.read.return_value = body
    m.__enter__ = lambda s: s
    m.__exit__ = lambda s, *a: None
    return m


def _booking_manifest(*, destination_email: str = "client@acme.com") -> dict:
    return {
        "project_slug": "acme",
        "framework": "next",
        "locales": ["en"],
        "default_locale": "en",
        "services": [],
        "booking": {
            "detected": True,
            "public_slug": "acme",
            "business_name": "Acme Salon",
            "accent_color": "#ff0000",
            "primary_color": "#ffffff",
            "logo_url": "",
            "locale": "en",
            "timezone": "Europe/Bucharest",
            "destination_email": destination_email,
            "calendar_provider": "none",
            "reminders": {"enabled": True, "offsets_min": [60, 1440]},
            "services": [{"name": "Cut", "duration_min": 45}],
            "resources": [{"name": "Sam", "type": "staff"}],
            "hours": [{"weekday": 1, "start_time": "09:00", "end_time": "17:00"}],
            "ui_wiring": {"components": [], "fallback_embed": False},
        },
    }


# ---------------------------------------------------------------------------
# Test 1: Call ORDER — enable → settings PATCH → resources → services → hours
# ---------------------------------------------------------------------------


def test_booking_provision_call_order(tmp_path):
    """
    POST .../bookings/enable must appear BEFORE PATCH .../bookings/settings,
    POST .../bookings/resources, POST .../bookings/services, and PUT .../bookings/hours.
    """
    manifest = _booking_manifest()
    call_log: list[str] = []

    # _http is used for PATCH settings call; urlopen used for POST/PUT resource calls
    resource_resp = _urlopen_resp(b'{"id": "res1"}')
    service_resp = _urlopen_resp(b'{"id": "svc1"}')

    def fake_urlopen(req):
        call_log.append(f"{req.get_method()} {req.get_full_url()}")
        url = req.get_full_url()
        if "/bookings/resources" in url:
            return _urlopen_resp(b'{"id": "res1"}')
        if "/bookings/services" in url:
            return _urlopen_resp(b'{"id": "svc1"}')
        if "/bookings/hours" in url:
            return _urlopen_resp(b"{}")
        if "/bookings/enable" in url:
            return _urlopen_resp(b"{}")
        return _urlopen_resp(b"{}")

    def fake_http(method, url, headers, body=None):
        call_log.append(f"{method} {url}")
        return {"updated": 1}

    with (
        patch("urllib.request.urlopen", side_effect=fake_urlopen),
        patch.object(scan, "_http", side_effect=fake_http),
    ):
        scan._provision_booking(
            manifest["booking"], "acme", "http://localhost:8001", "tok", tmp_path
        )

    enable_calls = [e for e in call_log if "bookings/enable" in e]
    settings_calls = [e for e in call_log if "bookings/settings" in e]
    resource_calls = [e for e in call_log if "bookings/resources" in e and "POST" in e]
    service_calls = [e for e in call_log if "bookings/services" in e and "POST" in e]
    hours_calls = [e for e in call_log if "bookings/hours" in e and ("PUT" in e or "PUT" in e)]

    assert len(enable_calls) == 1, f"Expected 1 enable call, got: {enable_calls}"
    assert len(settings_calls) >= 1, f"Expected settings PATCH, got: {settings_calls}"
    assert len(resource_calls) >= 1, f"Expected resource POST, got: {resource_calls}"
    assert len(service_calls) >= 1, f"Expected service POST, got: {service_calls}"
    assert len(hours_calls) >= 1, f"Expected hours PUT, got: {hours_calls}"

    enable_idx = next(i for i, e in enumerate(call_log) if "bookings/enable" in e)
    settings_idx = next(i for i, e in enumerate(call_log) if "bookings/settings" in e)
    first_resource_idx = next(i for i, e in enumerate(call_log) if "bookings/resources" in e)
    first_service_idx = next(i for i, e in enumerate(call_log) if "bookings/services" in e)
    hours_idx = next(i for i, e in enumerate(call_log) if "bookings/hours" in e)

    assert (
        enable_idx < settings_idx
    ), f"enable ({enable_idx}) must come before settings ({settings_idx})"
    assert (
        enable_idx < first_resource_idx
    ), f"enable ({enable_idx}) must come before first resource POST ({first_resource_idx})"
    assert (
        enable_idx < first_service_idx
    ), f"enable ({enable_idx}) must come before first service POST ({first_service_idx})"
    assert enable_idx < hours_idx, f"enable ({enable_idx}) must come before hours PUT ({hours_idx})"


# ---------------------------------------------------------------------------
# Test 2a: destination_email set → owner_notification_email == "client@acme.com"
# ---------------------------------------------------------------------------


def test_booking_settings_patch_uses_destination_email(tmp_path):
    """When destination_email is non-empty, the PATCH body has that email."""
    manifest = _booking_manifest(destination_email="client@acme.com")
    settings_bodies: list[dict] = []

    def fake_urlopen(req):
        if "/bookings/resources" in req.get_full_url():
            return _urlopen_resp(b'{"id": "res1"}')
        if "/bookings/services" in req.get_full_url():
            return _urlopen_resp(b'{"id": "svc1"}')
        return _urlopen_resp(b"{}")

    def fake_http(method, url, headers, body=None):
        if "bookings/settings" in url:
            settings_bodies.append(body or {})
        return {"updated": 1}

    with (
        patch("urllib.request.urlopen", side_effect=fake_urlopen),
        patch.object(scan, "_http", side_effect=fake_http),
    ):
        scan._provision_booking(
            manifest["booking"], "acme", "http://localhost:8001", "tok", tmp_path
        )

    assert len(settings_bodies) == 1, f"Expected 1 settings PATCH, got {settings_bodies}"
    assert (
        settings_bodies[0].get("owner_notification_email") == "client@acme.com"
    ), f"Expected client@acme.com, got {settings_bodies[0].get('owner_notification_email')}"


# ---------------------------------------------------------------------------
# Test 2b: destination_email empty → owner_notification_email == "stefanromanpers@gmail.com"
# ---------------------------------------------------------------------------


def test_booking_settings_patch_fallback_email(tmp_path):
    """When destination_email is empty, PATCH body uses stefanromanpers@gmail.com."""
    manifest = _booking_manifest(destination_email="")
    settings_bodies: list[dict] = []

    def fake_urlopen(req):
        if "/bookings/resources" in req.get_full_url():
            return _urlopen_resp(b'{"id": "res1"}')
        if "/bookings/services" in req.get_full_url():
            return _urlopen_resp(b'{"id": "svc1"}')
        return _urlopen_resp(b"{}")

    def fake_http(method, url, headers, body=None):
        if "bookings/settings" in url:
            settings_bodies.append(body or {})
        return {"updated": 1}

    with (
        patch("urllib.request.urlopen", side_effect=fake_urlopen),
        patch.object(scan, "_http", side_effect=fake_http),
    ):
        scan._provision_booking(
            manifest["booking"], "acme", "http://localhost:8001", "tok", tmp_path
        )

    assert len(settings_bodies) == 1
    assert (
        settings_bodies[0].get("owner_notification_email") == "stefanromanpers@gmail.com"
    ), f"Expected fallback email, got {settings_bodies[0].get('owner_notification_email')}"


# ---------------------------------------------------------------------------
# Test 3: lib/booking.ts written with slug + key functions
# ---------------------------------------------------------------------------


def test_booking_lib_ts_written(tmp_path):
    """lib/booking.ts is written to out_dir and contains slug + key exports."""
    manifest = _booking_manifest()

    def fake_urlopen(req):
        if "/bookings/resources" in req.get_full_url():
            return _urlopen_resp(b'{"id": "res1"}')
        if "/bookings/services" in req.get_full_url():
            return _urlopen_resp(b'{"id": "svc1"}')
        return _urlopen_resp(b"{}")

    def fake_http(method, url, headers, body=None):
        return {"updated": 1}

    with (
        patch("urllib.request.urlopen", side_effect=fake_urlopen),
        patch.object(scan, "_http", side_effect=fake_http),
    ):
        scan._provision_booking(
            manifest["booking"], "acme", "http://localhost:8001", "tok", tmp_path
        )

    lib_path = tmp_path / "lib" / "booking.ts"
    assert lib_path.exists(), f"lib/booking.ts not found at {lib_path}"

    content = lib_path.read_text(encoding="utf-8")
    assert '"acme"' in content, "booking.ts must contain the slug"
    assert "getServices" in content
    assert "getAvailability" in content
    assert "createBooking" in content
    # Next.js framework → NEXT_PUBLIC_ prefix
    assert "NEXT_PUBLIC_BOOKING_API_BASE" in content


def test_booking_lib_ts_vite_prefix(tmp_path):
    """Vite framework uses VITE_ prefix in lib/booking.ts."""
    manifest = _booking_manifest()

    def fake_urlopen(req):
        if "/bookings/resources" in req.get_full_url():
            return _urlopen_resp(b'{"id": "res1"}')
        if "/bookings/services" in req.get_full_url():
            return _urlopen_resp(b'{"id": "svc1"}')
        return _urlopen_resp(b"{}")

    def fake_http(method, url, headers, body=None):
        return {"updated": 1}

    with (
        patch("urllib.request.urlopen", side_effect=fake_urlopen),
        patch.object(scan, "_http", side_effect=fake_http),
    ):
        scan._provision_booking(
            manifest["booking"],
            "acme",
            "http://localhost:8001",
            "tok",
            tmp_path,
            framework="vite-react",
        )

    lib_path = tmp_path / "lib" / "booking.ts"
    content = lib_path.read_text(encoding="utf-8")
    assert "VITE_BOOKING_API_BASE" in content


# ---------------------------------------------------------------------------
# Test 4: No-op when booking block is absent
# ---------------------------------------------------------------------------


def test_no_booking_calls_when_booking_absent():
    """Manifests without a booking block must not trigger any booking API calls."""
    manifest = {
        "project_slug": "acme",
        "framework": "next",
        "services": [],
        # no "booking" key
    }
    call_log: list[str] = []

    def fake_urlopen(req):
        call_log.append(f"{req.get_method()} {req.get_full_url()}")
        return _urlopen_resp(b"{}")

    def fake_http(method, url, headers, body=None):
        call_log.append(f"{method} {url}")
        return {"updated": 1}

    with (
        patch("urllib.request.urlopen", side_effect=fake_urlopen),
        patch.object(scan, "_http", side_effect=fake_http),
    ):
        # Simulate _provision being called without booking
        # _provision itself handles the locale patch + service creates.
        # The key assertion: zero booking-related calls.
        scan._provision(manifest, "http://localhost:8001", "tok")

    booking_calls = [e for e in call_log if "booking" in e.lower()]
    assert (
        booking_calls == []
    ), f"Expected no booking calls for manifest without booking block, got: {booking_calls}"


# ---------------------------------------------------------------------------
# Test 5: _provision calls _provision_booking when booking.detected is True
# ---------------------------------------------------------------------------


def test_provision_delegates_to_provision_booking_when_detected(tmp_path):
    """_provision must call _provision_booking when manifest has booking.detected=True."""
    manifest = {
        "project_slug": "acme",
        "framework": "next",
        "services": [],
        "booking": {
            "detected": True,
            "public_slug": "acme",
            "business_name": "Acme",
            "accent_color": "#000",
            "primary_color": "#fff",
            "logo_url": "",
            "locale": "en",
            "timezone": "UTC",
            "destination_email": "owner@acme.com",
            "calendar_provider": "none",
            "reminders": {"enabled": False, "offsets_min": []},
            "services": [],
            "resources": [],
            "hours": [],
            "ui_wiring": {"components": [], "fallback_embed": False},
        },
    }

    with patch.object(scan, "_provision_booking") as mock_pb:
        with (
            patch("urllib.request.urlopen", side_effect=lambda req: _urlopen_resp(b"{}")),
            patch.object(scan, "_http", return_value={"updated": 1}),
        ):
            scan._provision(manifest, "http://localhost:8001", "tok", out_dir=tmp_path)

    mock_pb.assert_called_once()
    args = mock_pb.call_args
    # First positional arg: booking block
    assert args[0][0]["detected"] is True
    # Second positional arg: project slug
    assert args[0][1] == "acme"
