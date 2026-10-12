from unittest.mock import MagicMock

import pytest

from auth_service.services.content_structure import (
    StructureError,
    apply_structure_rules,
    normalize_media_fields,
)
from auth_service.services.segments import segments_of

IMAGE_FIELD = {
    "key": "image",
    "type": "image",
    "label": "Banner",
    "hint": {"width": 1600, "height": 600},
}
ICON_FIELD = {"key": "icon", "type": "icon", "label": "Icon", "surface": "Dark"}
SCHEMA = [{"key": "title", "type": "string", "label": "Title"}, IMAGE_FIELD, ICON_FIELD]
ICON = {"src": "https://cdn.example.com/i.svg", "mode": "tint", "color": "#ABCDEF", "name": "star"}


def _admin_schema(schema):
    return apply_structure_rules(
        "repeater", {"_schema": schema, "items": []}, is_admin=True, stored=()
    )


def test_image_field_with_hint_is_valid():
    assert _admin_schema([IMAGE_FIELD])["_schema"] == [IMAGE_FIELD]


def test_icon_field_with_surface_is_valid():
    assert _admin_schema([ICON_FIELD])["_schema"] == [ICON_FIELD]


@pytest.mark.parametrize(
    "field",
    [
        {"key": "t", "type": "string", "label": "T", "hint": {"width": 100, "height": 100}},
        {"key": "t", "type": "string", "label": "T", "surface": "Dark"},
        {**IMAGE_FIELD, "hint": {"width": 5, "height": 600}},
        {**IMAGE_FIELD, "hint": {"width": 1600, "height": 9000}},
        {**IMAGE_FIELD, "hint": {"width": 1600}},
        {**IMAGE_FIELD, "hint": {"width": "1600", "height": 600}},
        {**ICON_FIELD, "surface": "x" * 41},
        {**ICON_FIELD, "surface": 3},
    ],
)
def test_invalid_hint_or_surface_rejected(field):
    with pytest.raises(StructureError):
        _admin_schema([field])


def _repeater(*items):
    return {"_schema": SCHEMA, "items": list(items)}


def test_icon_value_normalised():
    out = normalize_media_fields(_repeater({"_id": "a", "icon": {**ICON, "extra": "x"}}))
    assert out["items"][0]["icon"] == {
        "src": "https://cdn.example.com/i.svg",
        "mode": "tint",
        "color": "#abcdef",
        "name": "star",
    }


def test_icon_with_empty_src_becomes_none():
    out = normalize_media_fields(_repeater({"icon": {**ICON, "src": ""}}, {"icon": None}, {}))
    assert out["items"][0]["icon"] is None
    assert out["items"][1]["icon"] is None
    assert "icon" not in out["items"][2]


@pytest.mark.parametrize("value", ["", "https://cdn.example.com/i.svg", 0, False, []])
def test_empty_or_non_object_icon_becomes_none(value):
    # The pre-ADR-0011 dashboard seeds new items with `icon: ""`; a save of such
    # a repeater must not 422.
    out = normalize_media_fields(_repeater({"icon": value}))
    assert out["items"][0]["icon"] is None


@pytest.mark.parametrize(
    "icon",
    [
        {**ICON, "src": "javascript:alert(1)"},
        {**ICON, "src": "http://cdn.example.com/i.svg"},
        {**ICON, "src": "https://cdn.example.com/i(1).svg"},
        {**ICON, "mode": "fill"},
        {**ICON, "color": "blue"},
        {**ICON, "name": "x" * 65},
    ],
)
def test_invalid_icon_rejected(icon):
    with pytest.raises(StructureError):
        normalize_media_fields(_repeater({"icon": icon}))


def test_image_values():
    ok = normalize_media_fields(
        _repeater({"image": ""}, {"image": "https://cdn.example.com/a.png"})
    )
    assert [i["image"] for i in ok["items"]] == ["", "https://cdn.example.com/a.png"]
    for bad in (
        "http://cdn.example.com/a.png",
        "https://x.com/a b.png",
        'https://x.com/"a',
        None,
        "https://x.com/a(1).png",
        "https://x.com/a)b.png",
        "https://x.com/a\\b.png",
    ):
        with pytest.raises(StructureError):
            normalize_media_fields(_repeater({"image": bad}))


def test_non_media_fields_untouched():
    content = {"_schema": [{"key": "title", "type": "string"}], "items": [{"title": "  x "}]}
    assert normalize_media_fields(content) == content


def test_client_save_keeps_stored_schema_with_hint_and_surface():
    out = apply_structure_rules(
        "repeater",
        {"_schema": [{"key": "image", "type": "image", "label": "B"}], "items": []},
        is_admin=False,
        stored=({"_schema": SCHEMA, "items": []},),
    )
    assert out["_schema"] == SCHEMA
    assert out["_schema"][1]["hint"] == {"width": 1600, "height": 600}
    assert out["_schema"][2]["surface"] == "Dark"


def test_image_service_hint_kept_on_client_save():
    stored = ({"url": "https://a/x.png", "_hint": {"width": 800, "height": 600}},)
    out = apply_structure_rules(
        "image",
        {"url": "https://a/y.png", "_hint": {"width": 16, "height": 16}},
        is_admin=False,
        stored=stored,
    )
    assert out == {"url": "https://a/y.png", "_hint": {"width": 800, "height": 600}}
    # Missing incoming keeps the stored hint for an admin too.
    out = apply_structure_rules("image", {"url": "u"}, is_admin=True, stored=stored)
    assert out["_hint"] == {"width": 800, "height": 600}
    # A client cannot inject one when none is stored.
    out = apply_structure_rules(
        "image", {"url": "u", "_hint": {"width": 16, "height": 16}}, is_admin=False, stored=()
    )
    assert "_hint" not in out


def test_image_service_hint_validated_on_admin_save():
    out = apply_structure_rules(
        "image", {"url": "u", "_hint": {"width": 1200, "height": 630}}, is_admin=True, stored=()
    )
    assert out["_hint"] == {"width": 1200, "height": 630}
    with pytest.raises(StructureError):
        apply_structure_rules(
            "image", {"url": "u", "_hint": {"width": 10, "height": 630}}, is_admin=True, stored=()
        )


def test_segments_of_ignores_image_and_icon_fields():
    content = _repeater(
        {"_id": "a", "title": "Hello", "image": "https://cdn.example.com/a.png", "icon": ICON}
    )
    assert segments_of("repeater", content) == {"items.a.title": "Hello"}


# ── Endpoints ────────────────────────────────────────────────────────────────

SVC_REPEATER = {
    "id": "svc-r",
    "service_key": "services_list",
    "label": "Services",
    "display_order": 0,
    "page_name": "Services",
    "service_type_slug": "repeater",
}


def _project(slug, user):
    return {"id": f"project-{slug}", "slug": slug, "default_locale": "en", "locales": ["en"]}


@pytest.fixture
def as_user(auth_as, monkeypatch):
    def _set(user):
        auth_as(user)
        monkeypatch.setattr("auth_service.routers.workspace.require_project_access", _project)

    return _set


def test_save_repeater_normalises_media_fields(mock_supabase, client, as_user, admin_user):
    as_user(admin_user)
    mock_supabase.execute.side_effect = [
        MagicMock(data=SVC_REPEATER),
        MagicMock(data=[]),
        MagicMock(data=[{}]),
        MagicMock(data={**SVC_REPEATER, "content_entries": []}),
    ]
    res = client.put(
        "/projects/demo/services/services_list",
        json={"content": _repeater({"_id": "a", "icon": {**ICON, "extra": 1}})},
    )
    assert res.status_code == 200
    upserts = [
        c.args[0]
        for c in mock_supabase.upsert.call_args_list
        if isinstance(c.args[0], dict) and "project_service_id" in c.args[0]
    ]
    assert upserts[0]["draft_content"]["items"][0]["icon"]["color"] == "#abcdef"
    assert "extra" not in upserts[0]["draft_content"]["items"][0]["icon"]


def test_save_repeater_with_bad_image_is_422(mock_supabase, client, as_user, admin_user):
    as_user(admin_user)
    mock_supabase.execute.side_effect = [MagicMock(data=SVC_REPEATER), MagicMock(data=[])]
    res = client.put(
        "/projects/demo/services/services_list",
        json={"content": _repeater({"image": "http://x.com/a.png"})},
    )
    assert res.status_code == 422


def test_add_repeater_with_icon_and_hint_accepted(mock_supabase, client, as_user, admin_user):
    as_user(admin_user)
    mock_supabase.execute.side_effect = [
        MagicMock(data=[{}]),
        MagicMock(data={"id": "svc-r"}),
        MagicMock(data=[{}]),
    ]
    res = client.post(
        "/projects/demo/services",
        json={
            "service_type_slug": "repeater",
            "service_key": "services_list",
            "label": "Services",
            "item_schema": SCHEMA,
        },
    )
    assert res.status_code == 201
    seed = mock_supabase.insert.call_args_list[-1].args[0]
    assert seed["draft_content"]["_schema"] == SCHEMA


def test_add_repeater_with_hint_on_string_is_422(mock_supabase, client, as_user, admin_user):
    as_user(admin_user)
    res = client.post(
        "/projects/demo/services",
        json={
            "service_type_slug": "repeater",
            "service_key": "services_list",
            "item_schema": [
                {"key": "t", "type": "string", "label": "T", "hint": {"width": 99, "height": 99}}
            ],
        },
    )
    assert res.status_code == 422
    mock_supabase.insert.assert_not_called()
