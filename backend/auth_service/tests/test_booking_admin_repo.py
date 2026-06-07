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
