"""Public content reads must not select ``draft_content``.

Every client-site page view runs a public ``/content`` read against the shared Supabase
database. Those responses only ever contain published content, so fetching the draft
column too would read up to twice the bytes for nothing (Supabase Disk IO budget). The
draft endpoints, which need it, must keep selecting it.
"""

from unittest.mock import MagicMock, patch

_PROJECT = {
    "id": "p1",
    "slug": "demo",
    "name": "Demo",
    "is_active": True,
    "default_locale": "en",
    "locales": ["en"],
    "preview_token": "tok",
}


def _rows():
    return [
        MagicMock(data=_PROJECT),
        MagicMock(
            data=[
                {
                    "service_key": "hero",
                    "label": "Hero",
                    "display_order": 1,
                    "service_type_slug": "text_block",
                    "content_entries": [
                        {
                            "locale": "en",
                            "published_content": {"title": "PUB"},
                            "draft_content": {"title": "DRAFT"},
                            "updated_at": "2026-04-16T10:00:00Z",
                        }
                    ],
                },
            ]
        ),
    ]


def _content_selects(mock_supabase) -> list[str]:
    return [
        call.args[0]
        for call in mock_supabase.select.call_args_list
        if call.args and "content_entries" in call.args[0]
    ]


def _get(mock_supabase, client, path, **kwargs):
    mock_supabase.execute.side_effect = _rows()
    with patch("auth_service.routers.content.pg_rate_limit.allow", return_value=True):
        return client.get(path, **kwargs)


def test_public_reads_skip_draft_content(mock_supabase, client):
    for path in ("/content/demo", "/content/demo/en"):
        mock_supabase.select.reset_mock()
        res = _get(mock_supabase, client, path)
        assert res.status_code == 200, (path, res.text)
        assert res.json()["content"]["hero"]["title"] == "PUB"
        selects = _content_selects(mock_supabase)
        assert selects, path
        assert all("draft_content" not in s for s in selects), (path, selects)


def test_draft_locale_read_still_selects_draft_content(mock_supabase, client):
    res = _get(
        mock_supabase, client, "/content/demo/en/draft", headers={"X-CMS-Preview-Token": "tok"}
    )
    assert res.status_code == 200, res.text
    assert res.json()["content"]["hero"]["title"] == "DRAFT"
    assert any("draft_content" in s for s in _content_selects(mock_supabase))
