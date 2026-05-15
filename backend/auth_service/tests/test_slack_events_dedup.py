"""Idempotency table for Slack event delivery."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from ..services import slack_events_dedup


def test_mark_processed_inserts_row():
    mock_sb = MagicMock()
    for m in ("table", "insert", "execute"):
        getattr(mock_sb, m).return_value = mock_sb
    with patch.object(slack_events_dedup, "get_supabase_admin", return_value=mock_sb):
        slack_events_dedup.mark_processed("evt-123")
    mock_sb.table.assert_called_with("slack_processed_events")
    args = mock_sb.insert.call_args.args[0]
    assert args["event_id"] == "evt-123"


def test_already_processed_true_when_row_exists():
    mock_sb = MagicMock()
    for m in ("table", "select", "eq", "maybe_single", "execute"):
        getattr(mock_sb, m).return_value = mock_sb
    mock_sb.execute.return_value = MagicMock(data={"event_id": "evt-123"})
    with patch.object(slack_events_dedup, "get_supabase_admin", return_value=mock_sb):
        assert slack_events_dedup.already_processed("evt-123") is True


def test_already_processed_false_when_row_absent():
    mock_sb = MagicMock()
    for m in ("table", "select", "eq", "maybe_single", "execute"):
        getattr(mock_sb, m).return_value = mock_sb
    mock_sb.execute.return_value = MagicMock(data=None)
    with patch.object(slack_events_dedup, "get_supabase_admin", return_value=mock_sb):
        assert slack_events_dedup.already_processed("evt-unknown") is False


def test_empty_event_id_returns_false_already_processed():
    """Defensive: missing event_id treated as not-processed (safer than blocking)."""
    assert slack_events_dedup.already_processed("") is False
    assert slack_events_dedup.already_processed(None) is False  # type: ignore[arg-type]


def test_mark_processed_swallows_db_error():
    """If the dedup insert fails, the caller still proceeds — worse to drop legitimate events."""
    mock_sb = MagicMock()
    mock_sb.table.return_value = mock_sb
    mock_sb.insert.return_value = mock_sb
    mock_sb.execute.side_effect = RuntimeError("db down")
    with patch.object(slack_events_dedup, "get_supabase_admin", return_value=mock_sb):
        slack_events_dedup.mark_processed("evt-x")  # must not raise
