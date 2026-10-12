from unittest.mock import MagicMock

import pytest

from auth_service.services.theme import ThemeError, normalize_theme

PREFIX = "https://x.supabase.co/storage/v1/object/public/cms-files/demo/"
FONT_URL = PREFIX + "general_theme/a.woff2"


def _theme(**over):
    base = {
        "colors": [{"name": " Brand ", "value": "#ABC"}],
        "surfaces": [{"name": "Dark", "value": "#1E5AA8"}],
        "fonts": [
            {"family": "Open Sans", "source": "google", "weights": [700, 400, 400], "italic": True},
            {
                "family": "Brand Serif",
                "source": "upload",
                "files": [{"url": FONT_URL, "weight": 400, "style": "normal"}],
            },
            {"family": "Georgia", "source": "system", "extra": "dropped"},
        ],
        "body_font": "open sans",
        "heading_font": "",
    }
    base.update(over)
    return base


def test_valid_theme_round_trips_normalised():
    out = normalize_theme(_theme(), storage_prefix=PREFIX)
    assert out == {
        "colors": [{"name": "Brand", "value": "#aabbcc"}],
        "surfaces": [{"name": "Dark", "value": "#1e5aa8"}],
        "fonts": [
            {"family": "Open Sans", "source": "google", "weights": [400, 700], "italic": True},
            {
                "family": "Brand Serif",
                "source": "upload",
                "files": [{"url": FONT_URL, "weight": 400, "style": "normal"}],
            },
            {"family": "Georgia", "source": "system"},
        ],
        "body_font": "Open Sans",
        "heading_font": "",
    }


def test_missing_keys_default_and_unknown_keys_dropped():
    assert normalize_theme({"junk": 1}, storage_prefix=PREFIX) == {
        "colors": [],
        "surfaces": [],
        "fonts": [],
        "body_font": "",
        "heading_font": "",
    }


@pytest.mark.parametrize(
    "theme",
    [
        _theme(colors=[{"name": "Brand", "value": "red"}]),
        _theme(colors=[{"name": "c", "value": "#000000"}] * 25),
        _theme(surfaces=[{"name": "s", "value": "#000000"}] * 9),
        _theme(colors=[{"name": "  ", "value": "#000000"}]),
        _theme(colors=[{"name": "x" * 41, "value": "#000000"}]),
        _theme(fonts=[{"family": "Open;Sans", "source": "system"}], body_font=""),
        _theme(
            fonts=[
                {
                    "family": "Brand",
                    "source": "upload",
                    "files": [
                        {"url": "https://evil.com/a.woff2", "weight": 400, "style": "normal"}
                    ],
                }
            ],
            body_font="",
        ),
        _theme(
            fonts=[
                {
                    "family": "Brand",
                    "source": "upload",
                    "files": [{"url": PREFIX + "a).woff2", "weight": 400, "style": "normal"}],
                }
            ],
            body_font="",
        ),
        _theme(
            fonts=[
                {
                    "family": "Brand",
                    "source": "upload",
                    "files": [
                        {"url": PREFIX + "../other/a.woff2", "weight": 400, "style": "normal"}
                    ],
                }
            ],
            body_font="",
        ),
        _theme(fonts=[{"family": "Brand", "source": "upload", "files": []}], body_font=""),
        _theme(body_font="Roboto"),
        _theme(
            fonts=[
                {"family": "Open Sans", "source": "system"},
                {"family": "open sans", "source": "system"},
            ]
        ),
        _theme(
            fonts=[{"family": "Open Sans", "source": "google", "weights": [450], "italic": False}]
        ),
        _theme(
            fonts=[{"family": "Open Sans", "source": "google", "weights": [400], "italic": "yes"}]
        ),
        _theme(fonts=[{"family": "Open Sans", "source": "adobe"}]),
        _theme(fonts=[{"family": f"F{i}", "source": "system"} for i in range(13)], body_font=""),
    ],
)
def test_invalid_theme_raises(theme):
    with pytest.raises(ThemeError):
        normalize_theme(theme, storage_prefix=PREFIX)


def test_error_message_names_the_path():
    with pytest.raises(ThemeError, match=r"^colors\[0\]\.value: "):
        normalize_theme(_theme(colors=[{"name": "B", "value": "nope"}]), storage_prefix=PREFIX)


# ── Endpoints ────────────────────────────────────────────────────────────────

SVC_THEME = {
    "id": "svc-t",
    "service_key": "general_theme",
    "label": "Theme",
    "display_order": 0,
    "page_name": "General",
    "service_type_slug": "theme",
}


def _project(slug, user):
    return {"id": f"project-{slug}", "slug": slug, "default_locale": "en", "locales": ["en"]}


@pytest.fixture
def as_user(auth_as, monkeypatch, mock_supabase):
    def _set(user):
        auth_as(user)
        monkeypatch.setattr("auth_service.routers.workspace.require_project_access", _project)
        mock_supabase.storage.from_.return_value.get_public_url.return_value = PREFIX

    return _set


def _content_upserts(mock_supabase):
    return [
        c.args[0]
        for c in mock_supabase.upsert.call_args_list
        if isinstance(c.args[0], dict) and "project_service_id" in c.args[0]
    ]


def test_save_theme_with_bad_colour_is_422(mock_supabase, client, as_user, client_user):
    as_user(client_user)
    mock_supabase.execute.side_effect = [MagicMock(data=SVC_THEME), MagicMock(data=[])]
    res = client.put(
        "/projects/demo/services/general_theme",
        json={"content": _theme(colors=[{"name": "B", "value": "blue"}])},
    )
    assert res.status_code == 422
    assert "colors[0].value" in res.json()["detail"]
    assert _content_upserts(mock_supabase) == []


def test_save_theme_stores_normalised(mock_supabase, client, as_user, client_user):
    as_user(client_user)
    mock_supabase.execute.side_effect = [
        MagicMock(data=SVC_THEME),
        MagicMock(data=[]),
        MagicMock(data=[{}]),
        MagicMock(data={**SVC_THEME, "content_entries": []}),
    ]
    res = client.put("/projects/demo/services/general_theme", json={"content": _theme()})
    assert res.status_code == 200
    stored = _content_upserts(mock_supabase)[0]["draft_content"]
    assert stored == normalize_theme(_theme(), storage_prefix=PREFIX)
    assert stored["body_font"] == "Open Sans"
    mock_supabase.storage.from_.return_value.get_public_url.assert_called_with("demo/")


def test_save_theme_prefix_is_anchored_to_the_project_folder(
    mock_supabase, client, as_user, client_user
):
    # Slug "public" also appears earlier in the storage path
    # (.../object/public/cms-files/public/); the prefix must not stop there.
    as_user(client_user)
    root = "https://x.supabase.co/storage/v1/object/public/cms-files/"
    mock_supabase.storage.from_.return_value.get_public_url.return_value = root + "public/"
    mock_supabase.execute.side_effect = [MagicMock(data=SVC_THEME), MagicMock(data=[])]
    other = {"url": root + "other/general_theme/a.woff2", "weight": 400, "style": "normal"}
    res = client.put(
        "/projects/public/services/general_theme",
        json={
            "content": _theme(
                fonts=[{"family": "Brand", "source": "upload", "files": [other]}], body_font=""
            )
        },
    )
    assert res.status_code == 422
    assert "fonts[0].files[0].url" in res.json()["detail"]
    assert _content_upserts(mock_supabase) == []


def test_storage_prefix_rejects_unexpected_public_url(mock_supabase):
    from auth_service.routers.workspace import _storage_prefix

    mock_supabase.storage.from_.return_value.get_public_url.return_value = (
        "https://x.supabase.co/storage/v1/object/public/cms-files/"
    )
    with pytest.raises(RuntimeError):
        _storage_prefix("demo")
    mock_supabase.storage.from_.return_value.get_public_url.return_value = PREFIX
    assert _storage_prefix("demo") == PREFIX


def test_theme_save_on_other_locale_goes_through_default(
    mock_supabase, client, as_user, client_user, monkeypatch
):
    as_user(client_user)
    monkeypatch.setattr(
        "auth_service.routers.workspace.require_project_access",
        lambda slug, user: {
            "id": f"project-{slug}",
            "slug": slug,
            "default_locale": "en",
            "locales": ["en", "nl", "de"],
        },
    )
    mock_supabase.execute.side_effect = [
        MagicMock(data=SVC_THEME),
        MagicMock(
            data=[
                {"id": "ce-en", "locale": "en", "draft_content": {}, "translation_meta": None},
                {"id": "ce-nl", "locale": "nl", "draft_content": {}, "translation_meta": {}},
            ]
        ),
        MagicMock(data=[{}]),  # upsert en
        MagicMock(data=[{}]),  # upsert nl
        MagicMock(data=[{}]),  # upsert de
        MagicMock(data={**SVC_THEME, "content_entries": []}),
    ]
    res = client.put("/projects/demo/services/general_theme?locale=nl", json={"content": _theme()})
    assert res.status_code == 200
    # The detail comes back for the requested tab, so the dashboard caches it
    # under that locale and the editor stays usable.
    assert res.json()["locale"] == "nl"
    expected = normalize_theme(_theme(), storage_prefix=PREFIX)
    ups = _content_upserts(mock_supabase)
    assert [u["locale"] for u in ups] == ["en", "nl", "de"]
    for u in ups:
        assert u["draft_content"] == expected
        assert not u.get("translation_meta")


def test_add_theme_service_seeds_empty_theme(mock_supabase, client, as_user, admin_user):
    as_user(admin_user)
    mock_supabase.execute.side_effect = [
        MagicMock(data=[]),  # no theme service yet
        MagicMock(data=[{}]),  # project_services insert
        MagicMock(data={"id": "svc-t"}),  # new service id
        MagicMock(data=[{}]),  # content_entries insert
    ]
    res = client.post(
        "/projects/demo/services",
        json={"service_type_slug": "theme", "service_key": "general_theme", "label": "Theme"},
    )
    assert res.status_code == 201
    empty = {"colors": [], "surfaces": [], "fonts": [], "body_font": "", "heading_font": ""}
    seed = mock_supabase.insert.call_args_list[-1].args[0]
    assert seed["project_service_id"] == "svc-t"
    assert seed["locale"] == "en"
    assert seed["draft_content"] == empty
    assert seed["published_content"] == empty


def test_add_second_theme_service_is_409(mock_supabase, client, as_user, admin_user):
    as_user(admin_user)
    mock_supabase.execute.side_effect = [
        MagicMock(data=[{"id": "svc-t"}]),  # a theme service already exists
    ]
    res = client.post(
        "/projects/demo/services",
        json={"service_type_slug": "theme", "service_key": "other_theme", "label": "Theme"},
    )
    assert res.status_code == 409
    assert res.json()["detail"] == "Project already has a theme service"
    mock_supabase.insert.assert_not_called()


def test_get_theme_returns_default_locale_draft(mock_supabase, client, as_user, client_user):
    as_user(client_user)
    draft = normalize_theme(_theme(), storage_prefix=PREFIX)
    mock_supabase.execute.return_value = MagicMock(
        data=[
            {
                "service_key": "general_theme",
                "content_entries": [
                    {"locale": "en", "draft_content": draft, "published_content": {}},
                ],
            }
        ]
    )
    res = client.get("/projects/demo/theme")
    assert res.status_code == 200
    assert res.json() == {"theme": draft, "service_key": "general_theme"}
    mock_supabase.eq.assert_any_call("service_type_slug", "theme")


def test_get_theme_without_theme_service_is_null(mock_supabase, client, as_user, client_user):
    as_user(client_user)
    mock_supabase.execute.return_value = MagicMock(data=[])
    res = client.get("/projects/demo/theme")
    assert res.status_code == 200
    assert res.json() == {"theme": None, "service_key": None}
