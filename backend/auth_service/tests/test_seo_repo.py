# backend/auth_service/tests/test_seo_repo.py
from unittest.mock import MagicMock, patch

from auth_service.services import seo_repo


def _sb():
    m = MagicMock()
    for meth in [
        "table",
        "select",
        "eq",
        "order",
        "limit",
        "maybe_single",
        "insert",
        "upsert",
        "update",
        "delete",
    ]:
        getattr(m, meth).return_value = m
    return m


def test_latest_audit_returns_first_row():
    sb = _sb()
    sb.execute.return_value.data = [
        {"seo_score": 80, "geo_score": 70, "local_score": 60, "locale": "en"}
    ]
    with patch("auth_service.services.seo_repo.get_supabase_admin", return_value=sb):
        row = seo_repo.latest_audit("proj-1")
    assert row["seo_score"] == 80


def test_upsert_page_meta_sets_updated_by():
    sb = _sb()
    sb.execute.return_value.data = [{"id": "m1", "route": "/", "locale": "en"}]
    with patch("auth_service.services.seo_repo.get_supabase_admin", return_value=sb):
        row = seo_repo.upsert_page_meta(
            "proj-1", {"route": "/", "locale": "en", "title": "Home"}, "client"
        )
    assert row["id"] == "m1"
    args = sb.upsert.call_args[0][0]
    assert args["updated_by"] == "client" and args["project_id"] == "proj-1"
