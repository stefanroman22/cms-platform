from unittest.mock import MagicMock


def test_public_content_returns_published_content_only(mock_supabase, client):
    # Arrange — supabase returns one project + two services
    mock_supabase.execute.side_effect = [
        # _resolve_project
        MagicMock(data={"id": "p1", "slug": "demo", "name": "Demo", "is_active": True}),
        # services query
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

    res = client.get("/content/demo")

    assert res.status_code == 200
    body = res.json()
    assert body["content"]["hero"]["title"] == "PUB"  # published, not draft


def test_public_content_filters_services_with_null_published(mock_supabase, client):
    mock_supabase.execute.side_effect = [
        MagicMock(data={"id": "p1", "slug": "demo", "name": "Demo", "is_active": True}),
        MagicMock(
            data=[
                {
                    "service_key": "published_svc",
                    "label": "Has published",
                    "display_order": 1,
                    "service_type_slug": "text_block",
                    "content_entries": {
                        "published_content": {"title": "YES"},
                        "draft_content": {"title": "D"},
                        "updated_at": "2026-04-16T10:00:00Z",
                    },
                },
                {
                    "service_key": "unpublished_svc",
                    "label": "Draft only",
                    "display_order": 2,
                    "service_type_slug": "text_block",
                    "content_entries": {
                        "published_content": None,
                        "draft_content": {"title": "D"},
                        "updated_at": "2026-04-16T10:00:00Z",
                    },
                },
            ]
        ),
    ]

    res = client.get("/content/demo")

    assert res.status_code == 200
    content = res.json()["content"]
    assert "published_svc" in content
    assert "unpublished_svc" not in content


def test_draft_endpoint_requires_token(mock_supabase, client):
    mock_supabase.execute.return_value = MagicMock(
        data={
            "id": "p1",
            "slug": "demo",
            "name": "Demo",
            "is_active": True,
            "preview_token": "secret-token-xyz",
        }
    )
    res = client.get("/content/demo/draft")
    assert res.status_code == 401


def test_draft_endpoint_rejects_wrong_token(mock_supabase, client):
    mock_supabase.execute.return_value = MagicMock(
        data={
            "id": "p1",
            "slug": "demo",
            "name": "Demo",
            "is_active": True,
            "preview_token": "secret-token-xyz",
        }
    )
    res = client.get("/content/demo/draft", headers={"X-CMS-Preview-Token": "wrong"})
    assert res.status_code == 401


def test_draft_endpoint_returns_draft_with_valid_token(mock_supabase, client):
    mock_supabase.execute.side_effect = [
        MagicMock(
            data={
                "id": "p1",
                "slug": "demo",
                "name": "Demo",
                "is_active": True,
                "preview_token": "secret-token-xyz",
            }
        ),
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
    res = client.get("/content/demo/draft", headers={"X-CMS-Preview-Token": "secret-token-xyz"})
    assert res.status_code == 200
    assert res.json()["content"]["hero"]["title"] == "DRAFT"
    assert res.headers["cache-control"] == "no-store"


def test_draft_falls_back_to_published_when_draft_null(mock_supabase, client):
    mock_supabase.execute.side_effect = [
        MagicMock(
            data={
                "id": "p1",
                "slug": "demo",
                "name": "Demo",
                "is_active": True,
                "preview_token": "secret-token-xyz",
            }
        ),
        MagicMock(
            data=[
                {
                    "service_key": "hero",
                    "label": "Hero",
                    "display_order": 1,
                    "service_type_slug": "text_block",
                    "content_entries": {
                        "published_content": {"title": "PUB"},
                        "draft_content": None,
                        "updated_at": "2026-04-16T10:00:00Z",
                    },
                },
            ]
        ),
    ]
    res = client.get("/content/demo/draft", headers={"X-CMS-Preview-Token": "secret-token-xyz"})
    assert res.status_code == 200
    assert res.json()["content"]["hero"]["title"] == "PUB"


def test_draft_empty_dict_does_not_fall_back_to_published(mock_supabase, client):
    """An editor who clears all fields in a draft must see empty preview,
    not the published content — empty-dict is a real draft state, not 'no draft'."""
    mock_supabase.execute.side_effect = [
        MagicMock(
            data={
                "id": "p1",
                "slug": "demo",
                "name": "Demo",
                "is_active": True,
                "preview_token": "secret-token-xyz",
            }
        ),
        MagicMock(
            data=[
                {
                    "service_key": "hero",
                    "label": "Hero",
                    "display_order": 1,
                    "service_type_slug": "text_block",
                    "content_entries": {
                        "published_content": {"title": "PUB"},
                        "draft_content": {},
                        "updated_at": "2026-04-16T10:00:00Z",
                    },
                },
            ]
        ),
    ]
    res = client.get("/content/demo/draft", headers={"X-CMS-Preview-Token": "secret-token-xyz"})
    assert res.status_code == 200
    hero = res.json()["content"]["hero"]
    assert "title" not in hero  # draft is {} — no title should appear (not PUB's title)
    assert hero["_type"] == "text_block"


def test_public_content_returns_default_locale_row(mock_supabase, client):
    mock_supabase.execute.side_effect = [
        MagicMock(
            data={
                "id": "p1",
                "slug": "demo",
                "name": "Demo",
                "is_active": True,
                "default_locale": "nl",
                "locales": ["nl", "en"],
            }
        ),
        MagicMock(
            data=[
                {
                    "service_key": "hero",
                    "label": "Hero",
                    "display_order": 1,
                    "service_type_slug": "text_block",
                    "content_entries": [
                        {
                            "locale": "nl",
                            "published_content": {"title": "NL"},
                            "draft_content": {"title": "NL-d"},
                            "updated_at": "2026-06-05T10:00:00Z",
                        },
                        {
                            "locale": "en",
                            "published_content": {"title": "EN"},
                            "draft_content": {"title": "EN-d"},
                            "updated_at": "2026-06-05T10:00:00Z",
                        },
                    ],
                },
            ]
        ),
    ]

    res = client.get("/content/demo")
    assert res.status_code == 200
    assert res.json()["content"]["hero"]["title"] == "NL"  # project default_locale = nl


def test_public_content_exposes_rich_text_version(mock_supabase, client):
    mock_supabase.execute.side_effect = [
        MagicMock(
            data={
                "id": "p1",
                "slug": "demo",
                "name": "Demo",
                "is_active": True,
                "rich_text_version": 1,
            }
        ),
        MagicMock(data=[]),
    ]

    res = client.get("/content/demo")

    assert res.status_code == 200
    assert res.json()["rich_text_version"] == 1


def test_public_content_defaults_rich_text_version_to_zero_when_absent(mock_supabase, client):
    mock_supabase.execute.side_effect = [
        MagicMock(data={"id": "p1", "slug": "demo", "name": "Demo", "is_active": True}),
        MagicMock(data=[]),
    ]

    res = client.get("/content/demo")

    assert res.status_code == 200
    assert res.json()["rich_text_version"] == 0


def test_locale_content_exposes_rich_text_version(mock_supabase, client):
    mock_supabase.execute.side_effect = [
        MagicMock(
            data={
                "id": "p1",
                "slug": "demo",
                "name": "Demo",
                "is_active": True,
                "default_locale": "nl",
                "locales": ["nl", "en"],
                "rich_text_version": 1,
            }
        ),
        MagicMock(data=[]),
    ]

    res = client.get("/content/demo/nl")

    assert res.status_code == 200
    assert res.json()["rich_text_version"] == 1


def test_locale_content_falls_back_to_default_theme_row(mock_supabase, client):
    theme = {
        "colors": [{"name": "Brand", "value": "#1e5aa8"}],
        "surfaces": [],
        "fonts": [],
        "body_font": "",
        "heading_font": "",
    }
    mock_supabase.execute.side_effect = [
        MagicMock(
            data={
                "id": "p1",
                "slug": "demo",
                "name": "Demo",
                "is_active": True,
                "default_locale": "en",
                "locales": ["en", "nl"],
            }
        ),
        MagicMock(
            data=[
                {
                    "service_key": "general_theme",
                    "label": "Theme",
                    "display_order": 0,
                    "service_type_slug": "theme",
                    "content_entries": [
                        {"locale": "en", "published_content": theme, "draft_content": theme}
                    ],
                }
            ]
        ),
    ]

    res = client.get("/content/demo/nl")

    assert res.status_code == 200
    assert res.json()["content"]["general_theme"] == {
        "_type": "theme",
        "_label": "Theme",
        **theme,
    }


def test_types_endpoint_declares_rich_html_aliases_and_text_block_leaf_typing(
    mock_supabase, client
):
    mock_supabase.execute.side_effect = [
        MagicMock(data={"id": "p1", "slug": "demo", "name": "Demo", "is_active": True}),
        MagicMock(
            data=[
                {"service_key": "hero", "service_type_slug": "text_block", "label": "Hero"},
            ]
        ),
    ]

    res = client.get("/content/demo/types")

    assert res.status_code == 200
    body = res.text
    assert "export type InlineHtml = string;" in body
    assert "export type RichHtml = string;" in body
    assert (
        'hero: { _type: "text_block"; _label: string; title?: InlineHtml; body?: RichHtml };'
        in body
    )


def test_types_endpoint_declares_theme_icon_and_media_hints(mock_supabase, client):
    mock_supabase.execute.side_effect = [
        MagicMock(data={"id": "p1", "slug": "demo", "name": "Demo", "is_active": True}),
        MagicMock(
            data=[
                {"service_key": "general_theme", "service_type_slug": "theme", "label": "Theme"},
                {"service_key": "list", "service_type_slug": "repeater", "label": "List"},
                {"service_key": "banner", "service_type_slug": "image", "label": "Banner"},
            ]
        ),
    ]

    body = client.get("/content/demo/types").text

    assert (
        "export interface CmsIconValue { src: string; "
        'mode: "tint" | "original"; color: string; name: string }' in body
    )
    assert 'general_theme: { _type: "theme"; _label: string; colors?: ' in body
    assert 'source: "upload"; files: { url: string; weight: number; ' in body
    assert "body_font?: string; heading_font?: string };" in body
    assert '"image" | "icon"' in body
    assert "hint?: { width: number; height: number }; surface?: string" in body
    assert (
        'banner: { _type: "image"; _label: string; url?: string; alt?: string; '
        "_hint?: { width: number; height: number } };" in body
    )
