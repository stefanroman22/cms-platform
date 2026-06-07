from unittest.mock import MagicMock, patch

from auth_service.services import booking_tenant


def _sb_returning(rows):
    sb = MagicMock()
    for m in ["table", "select", "eq", "limit"]:
        getattr(sb, m).return_value = sb
    sb.execute.return_value = type("R", (), {"data": rows})()
    return sb


SETTINGS_ROW = {
    "tenant_id": "t1",
    "public_slug": "acme",
    "timezone": "Europe/Berlin",
    "locale": "en",
    "business_name": "Acme",
    "owner_notification_email": "o@acme.com",
    "email_from_name": "Acme",
    "meeting_url": "",
    "slot_granularity_min": 15,
    "reminders_enabled": True,
    "reminder_offsets_min": [60],
    "calendar_provider": "none",
    "is_active": True,
}


def test_load_by_slug_returns_config():
    with patch(
        "auth_service.services.booking_tenant.get_supabase_admin",
        return_value=_sb_returning([SETTINGS_ROW]),
    ):
        cfg = booking_tenant.load_tenant_by_slug("acme")
    assert cfg is not None
    assert cfg.tenant_id == "t1"
    assert cfg.timezone == "Europe/Berlin"
    assert cfg.calendar_provider == "none"


def test_load_by_slug_unknown_returns_none():
    with patch(
        "auth_service.services.booking_tenant.get_supabase_admin", return_value=_sb_returning([])
    ):
        assert booking_tenant.load_tenant_by_slug("nope") is None


def test_load_by_slug_inactive_returns_none():
    row = {**SETTINGS_ROW, "is_active": False}
    with patch(
        "auth_service.services.booking_tenant.get_supabase_admin", return_value=_sb_returning([row])
    ):
        assert booking_tenant.load_tenant_by_slug("acme") is None
