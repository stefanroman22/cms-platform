from unittest.mock import MagicMock, patch

from auth_service.services import booking_admin_repo


def _sb():
    sb = MagicMock()
    for m in [
        "table",
        "select",
        "insert",
        "update",
        "upsert",
        "delete",
        "eq",
        "neq",
        "in_",
        "is_",
        "limit",
        "order",
        "maybe_single",
    ]:
        getattr(sb, m).return_value = sb
    return sb


def _exec(sb, data):
    sb.execute.return_value = type("R", (), {"data": data})()
    return sb


def test_get_settings_returns_none_when_absent():
    sb = _exec(_sb(), [])
    with patch("auth_service.services.booking_admin_repo.get_supabase_admin", return_value=sb):
        assert booking_admin_repo.get_settings("t1") is None


def test_slug_taken_by_other_detects_clash():
    sb = _exec(_sb(), [{"tenant_id": "other"}])
    with patch("auth_service.services.booking_admin_repo.get_supabase_admin", return_value=sb):
        assert booking_admin_repo.slug_taken_by_other("acme", "t1") is True


def test_slug_taken_by_other_false_for_self():
    sb = _exec(_sb(), [{"tenant_id": "t1"}])
    with patch("auth_service.services.booking_admin_repo.get_supabase_admin", return_value=sb):
        assert booking_admin_repo.slug_taken_by_other("acme", "t1") is False


def test_resource_has_bookings_true():
    sb = _exec(_sb(), [{"id": "b1"}])
    with patch("auth_service.services.booking_admin_repo.get_supabase_admin", return_value=sb):
        assert booking_admin_repo.resource_has_bookings("t1", "r1") is True


def _sb_with_range():
    sb = _sb()
    for m in ["gte", "lte", "lt"]:
        getattr(sb, m).return_value = sb
    return sb


def test_stats_repo_uses_gte_and_exclusive_lt():
    """The repo treats `date_to` as an EXCLUSIVE upper bound (`lt`), not inclusive —
    the router pre-resolves it to the start of the day after `to`, so the whole
    final day is included even though `start_utc` is a timestamptz."""
    sb = _exec(_sb_with_range(), [])
    with patch("auth_service.services.booking_admin_repo.get_supabase_admin", return_value=sb):
        booking_admin_repo.list_bookings_for_stats(
            "t1", "2026-06-11T00:00:00+00:00", "2026-06-12T00:00:00+00:00"
        )
    sb.gte.assert_called_once_with("start_utc", "2026-06-11T00:00:00+00:00")
    sb.lt.assert_called_once_with("start_utc", "2026-06-12T00:00:00+00:00")
    assert sb.lte.call_count == 0  # the inclusive upper bound must NOT be used


def test_appointments_repo_uses_exclusive_lt():
    sb = _exec(_sb_with_range(), [])
    with patch("auth_service.services.booking_admin_repo.get_supabase_admin", return_value=sb):
        booking_admin_repo.list_appointments(
            "t1",
            status=None,
            service_id=None,
            resource_id=None,
            date_from="2026-06-11T00:00:00+00:00",
            date_to="2026-06-12T00:00:00+00:00",
        )
    sb.lt.assert_called_once_with("start_utc", "2026-06-12T00:00:00+00:00")
    assert sb.lte.call_count == 0


def test_local_day_to_utc_tz_aware_exclusive_bounds():
    """The router helper interprets date-only `from`/`to` as TENANT-LOCAL days and
    returns tz-aware UTC instants — inclusive lower, exclusive (next-day) upper —
    so single-day/range windows are correct for non-UTC tenants too."""
    from auth_service.routers.booking_admin import _local_day_to_utc

    # UTC tenant: midnight maps 1:1; exclusive upper = next midnight.
    assert _local_day_to_utc("2026-06-11", "UTC") == "2026-06-11T00:00:00+00:00"
    assert _local_day_to_utc("2026-06-11", "UTC", end_exclusive=True) == "2026-06-12T00:00:00+00:00"
    # Europe/Berlin in June is CEST (UTC+2): local midnight is 22:00 UTC the day before.
    assert _local_day_to_utc("2026-06-11", "Europe/Berlin") == "2026-06-10T22:00:00+00:00"
    assert (
        _local_day_to_utc("2026-06-11", "Europe/Berlin", end_exclusive=True)
        == "2026-06-11T22:00:00+00:00"
    )
    # Missing date → no bound.
    assert _local_day_to_utc(None, "UTC") is None
