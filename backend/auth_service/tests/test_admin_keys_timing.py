"""Confirms `verify_admin_api_key` runs argon2.verify on every
parse-fail / row-miss path so wall-clock time matches the success
path.

We can't measure timing precisely in CI (noisy), so we count argon2
verify invocations via a patch — if it's called on every path,
timing is bounded by argon2's deterministic cost (~50 ms).
"""

from unittest.mock import MagicMock, patch

from auth_service.services import admin_keys


def _patch_supabase_returning(row):
    fake = MagicMock()
    fake.table.return_value.select.return_value.eq.return_value.is_.return_value.maybe_single.return_value.execute.return_value = MagicMock(  # noqa: E501
        data=row
    )
    return fake


def test_dummy_verify_runs_on_malformed_key():
    """Key doesn't start with `cmsk_` — must still call argon2.verify."""
    with (
        patch.object(admin_keys, "_ph") as mock_ph,
        patch.object(
            admin_keys, "get_supabase_admin", return_value=_patch_supabase_returning(None)
        ),
    ):
        result = admin_keys.verify_admin_api_key("notakey")
        assert result is None
        mock_ph.verify.assert_called_once_with(admin_keys._DUMMY_HASH, "x")


def test_dummy_verify_runs_on_wrong_env_segment():
    with (
        patch.object(admin_keys, "_ph") as mock_ph,
        patch.object(
            admin_keys, "get_supabase_admin", return_value=_patch_supabase_returning(None)
        ),
    ):
        result = admin_keys.verify_admin_api_key(
            "cmsk_xx_aaaaaaaaaaaaaaaa_bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
        )
        assert result is None
        mock_ph.verify.assert_called_once_with(admin_keys._DUMMY_HASH, "x")


def test_dummy_verify_runs_on_missing_row():
    """Well-formed key but no DB row — must still call argon2.verify."""
    with (
        patch.object(admin_keys, "_ph") as mock_ph,
        patch.object(
            admin_keys, "get_supabase_admin", return_value=_patch_supabase_returning(None)
        ),
    ):
        result = admin_keys.verify_admin_api_key(
            "cmsk_dev_aaaaaaaaaaaaaaaa_bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
        )
        assert result is None
        mock_ph.verify.assert_called_once_with(admin_keys._DUMMY_HASH, "x")


def test_dummy_verify_runs_on_short_lookup_segment():
    with (
        patch.object(admin_keys, "_ph") as mock_ph,
        patch.object(
            admin_keys, "get_supabase_admin", return_value=_patch_supabase_returning(None)
        ),
    ):
        result = admin_keys.verify_admin_api_key("cmsk_dev_short_secret")
        assert result is None
        mock_ph.verify.assert_called_once_with(admin_keys._DUMMY_HASH, "x")
