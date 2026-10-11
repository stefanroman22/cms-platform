from unittest.mock import MagicMock

import pytest

from auth_service.core.config import settings
from auth_service.services.google_places import quota


@pytest.fixture(autouse=True)
def _cap(monkeypatch):
    monkeypatch.setattr(settings, "GOOGLE_PLACES_MONTHLY_CAP", 7)


def test_consume_ok(mock_supabase):
    mock_supabase.rpc.return_value.execute.return_value = MagicMock(data=True)
    quota.consume()
    mock_supabase.rpc.assert_called_once_with("google_import_hit", {"p_limit": 7})


def test_consume_refused_when_false(mock_supabase):
    mock_supabase.rpc.return_value.execute.return_value = MagicMock(data=False)
    with pytest.raises(quota.MonthlyCapReached):
        quota.consume()


def test_consume_refused_when_execute_returns_none(mock_supabase):
    mock_supabase.rpc.return_value.execute.return_value = None
    with pytest.raises(quota.MonthlyCapReached):
        quota.consume()


def test_consume_fails_closed_when_rpc_raises(mock_supabase):
    mock_supabase.rpc.side_effect = RuntimeError("db down")
    with pytest.raises(quota.QuotaUnavailable):
        quota.consume()


def test_ensure_not_over_raises_at_cap(mock_supabase):
    mock_supabase.rpc.return_value.execute.return_value = MagicMock(data=True)
    with pytest.raises(quota.MonthlyCapReached):
        quota.ensure_not_over()
    mock_supabase.rpc.assert_called_once_with("google_import_over", {"p_limit": 7})


def test_ensure_not_over_passes_below_cap(mock_supabase):
    mock_supabase.rpc.return_value.execute.return_value = MagicMock(data=False)
    quota.ensure_not_over()
