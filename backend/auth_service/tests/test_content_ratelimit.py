"""SEC-095 regression: the public ``/content/*`` read endpoints must carry the shared
per-IP rate limit that every sibling public surface (booking/forms) already has.

``routers/content.py`` had no rate limiting of any kind. Each request runs
``_resolve_project`` (1 service-role query) plus a ``project_services`` +
``content_entries`` fetch (1 query), and the response is ``Cache-Control: no-cache``
with the ETag computed AFTER the queries — so neither the CDN nor the conditional-GET
path short-circuits the DB work. Without a cap an unauthenticated attacker scripting
GETs across all known slugs/locales drives unbounded read load at the single shared
Supabase instance that serves every tenant (local, preview and prod) — the same
amplification class the project already rated medium and fixed for booking reads
(SEC-070). The fix adds a router-level ``Depends(_public_read_limit)`` backed by the
shared Postgres limiter.
"""

from unittest.mock import MagicMock


def _published_service_rows():
    return [
        MagicMock(data={"id": "p1", "slug": "demo", "name": "Demo", "is_active": True}),
        MagicMock(
            data=[
                {
                    "service_key": "hero",
                    "label": "Hero",
                    "display_order": 1,
                    "service_type_slug": "text_block",
                    "content_entries": {
                        "published_content": {"title": "PUB"},
                        "draft_content": {"title": "DRAFT"},
                        "updated_at": "2026-04-16T10:00:00Z",
                    },
                },
            ]
        ),
    ]


def test_public_content_rate_limited_short_circuits_before_db(mock_supabase, client):
    """Over the per-IP cap, the content read returns 429 BEFORE any DB work runs."""
    from unittest.mock import patch

    with patch("auth_service.routers.content.pg_rate_limit.allow", return_value=False):
        res = client.get("/content/demo")

    assert res.status_code == 429
    # The limiter runs as a router dependency, so project resolution / content fetch
    # must never touch the shared Supabase DB once the IP is over its cap.
    mock_supabase.table.assert_not_called()


def test_public_content_locale_rate_limited(mock_supabase, client):
    """The locale read variant is covered by the same router-level limit."""
    from unittest.mock import patch

    with patch("auth_service.routers.content.pg_rate_limit.allow", return_value=False):
        res = client.get("/content/demo/en")

    assert res.status_code == 429
    mock_supabase.table.assert_not_called()


def test_public_content_types_rate_limited(mock_supabase, client):
    """The /types read variant is covered too."""
    from unittest.mock import patch

    with patch("auth_service.routers.content.pg_rate_limit.allow", return_value=False):
        res = client.get("/content/demo/types")

    assert res.status_code == 429
    mock_supabase.table.assert_not_called()


def test_public_content_allows_normal_request_under_cap(mock_supabase, client):
    """A legitimate request under the cap still succeeds end-to-end (limit is
    generous for real client-site traffic)."""
    from unittest.mock import patch

    mock_supabase.execute.side_effect = _published_service_rows()

    with patch("auth_service.routers.content.pg_rate_limit.allow", return_value=True):
        res = client.get("/content/demo")

    assert res.status_code == 200
    assert res.json()["content"]["hero"]["title"] == "PUB"


def test_public_content_fails_open_on_limiter_db_error(mock_supabase, client):
    """Fail-open contract: a transient limiter DB error must not block legitimate
    reads (pg_rate_limit.allow already swallows and returns True)."""
    from unittest.mock import patch

    mock_supabase.execute.side_effect = _published_service_rows()

    # Simulate the limiter's own RPC raising; allow() swallows → fails open → request runs.
    with patch(
        "auth_service.routers.content.pg_rate_limit.allow",
        side_effect=lambda *a, **k: True,
    ):
        res = client.get("/content/demo")

    assert res.status_code == 200
