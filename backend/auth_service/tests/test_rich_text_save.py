from unittest.mock import MagicMock

import pytest

SVC_TEXT = {
    "id": "svc-1",
    "service_key": "hero",
    "label": "Hero",
    "display_order": 1,
    "page_name": "General",
    "service_type_slug": "text_block",
    "service_types": {"name": "Text block", "icon": "Box", "schema": {}},
}


def _project(version):
    def fake(slug, user):
        return {
            "id": f"project-{slug}",
            "slug": slug,
            "default_locale": "en",
            "locales": ["en"],
            "rich_text_version": version,
        }

    return fake


def _refetch(content):
    return MagicMock(
        data={
            **SVC_TEXT,
            "content_entries": {
                "draft_content": content,
                "published_content": {},
                "updated_at": "2026-09-27T10:00:00Z",
            },
        }
    )


def _content_upserts(mock_supabase):
    return [
        c.args[0]
        for c in mock_supabase.upsert.call_args_list
        if isinstance(c.args[0], dict) and "project_service_id" in c.args[0]
    ]


@pytest.fixture
def client_as(auth_as, monkeypatch, client_user):
    def _set(version, user=None):
        auth_as(user or client_user)
        monkeypatch.setattr(
            "auth_service.routers.workspace.require_project_access", _project(version)
        )

    return _set


def test_version0_saves_values_verbatim(mock_supabase, client, client_as):
    client_as(0)
    mock_supabase.execute.side_effect = [
        MagicMock(data=SVC_TEXT),
        MagicMock(data=[]),
        MagicMock(data=[{}]),
        _refetch({}),
    ]
    res = client.put(
        "/projects/demo/services/hero", json={"content": {"title": "A & B", "body": "**x**"}}
    )
    assert res.status_code == 200
    assert _content_upserts(mock_supabase)[0]["draft_content"] == {
        "title": "A & B",
        "body": "**x**",
    }


def test_version1_canonicalises_inline_and_rich(mock_supabase, client, client_as):
    client_as(1)
    mock_supabase.execute.side_effect = [
        MagicMock(data=SVC_TEXT),
        MagicMock(data=[]),
        MagicMock(data=[{}]),
        _refetch({}),
    ]
    res = client.put(
        "/projects/demo/services/hero",
        json={
            "content": {
                "title": "A & <b>B</b>",
                "body": '<p onclick="x">Hi<script>alert(1)</script></p><p></p>',
            }
        },
    )
    assert res.status_code == 200
    assert _content_upserts(mock_supabase)[0]["draft_content"] == {
        "title": "A &amp; <strong>B</strong>",
        "body": "<p>Hi</p>",
    }


def test_version1_too_long_is_422_with_path(mock_supabase, client, client_as):
    client_as(1)
    mock_supabase.execute.side_effect = [MagicMock(data=SVC_TEXT), MagicMock(data=[])]
    res = client.put("/projects/demo/services/hero", json={"content": {"title": "x" * 2001}})
    assert res.status_code == 422
    assert res.json()["detail"] == "Field title is too long (2001 > 2000 characters)"
    assert _content_upserts(mock_supabase) == []


def test_client_cannot_change_key_value_formats(mock_supabase, client, client_as):
    client_as(1)
    svc_kv = {**SVC_TEXT, "service_type_slug": "key_value"}
    stored = {"entries": {"about": "x"}, "_formats": {"about": "inline"}}
    mock_supabase.execute.side_effect = [
        MagicMock(data=svc_kv),
        MagicMock(
            data=[
                {
                    "id": "r1",
                    "locale": "en",
                    "draft_content": stored,
                    "published_content": stored,
                    "translation_meta": {},
                }
            ]
        ),
        MagicMock(data=[{}]),
        _refetch(stored),
    ]
    res = client.put(
        "/projects/demo/services/hero",
        json={"content": {"entries": {"about": "<p>y</p>"}, "_formats": {"about": "rich"}}},
    )
    assert res.status_code == 200
    draft = _content_upserts(mock_supabase)[0]["draft_content"]
    assert draft["_formats"] == {"about": "inline"}
    assert draft["entries"]["about"] == "y"  # canonicalised as inline, block unwrapped


def test_admin_invalid_formats_is_422(mock_supabase, client, client_as, admin_user):
    client_as(1, admin_user)
    svc_kv = {**SVC_TEXT, "service_type_slug": "key_value"}
    mock_supabase.execute.side_effect = [MagicMock(data=svc_kv), MagicMock(data=[])]
    res = client.put(
        "/projects/demo/services/hero",
        json={"content": {"entries": {"a": "x"}, "_formats": {"a": "bold"}}},
    )
    assert res.status_code == 422


def test_get_service_exposes_formats_version_and_structure_flag(mock_supabase, client, client_as):
    client_as(1)
    mock_supabase.execute.return_value = _refetch({"title": "t"})
    body = client.get("/projects/demo/services/hero").json()
    assert body["rich_text_version"] == 1
    assert body["field_formats"] == {"title": "inline", "body": "rich"}
    assert body["can_edit_structure"] is False
