"""Display options (ADR-0013): toggle / select / color field types, in repeaters
and in the `options` service."""

from unittest.mock import MagicMock

import pytest

from auth_service.models.schemas import RepeaterItemField
from auth_service.services.content_structure import (
    StructureError,
    _validate_schema,
    apply_structure_rules,
    normalize_option_fields,
    normalize_options,
    validate_options_schema,
)
from auth_service.services.rich_text import field_formats, normalize_content
from auth_service.services.segments import segments_of
from auth_service.services.service_types import SERVICE_TYPES
from auth_service.translation.sync import sync_locale_draft

WIDTHS = [{"value": "narrow", "label": "Narrow"}, {"value": "wide", "label": "Wide"}]
TOGGLE = {"key": "show_title", "label": "Show title", "type": "toggle", "default": True}
SELECT = {
    "key": "content_width",
    "label": "Content width",
    "type": "select",
    "options": WIDTHS,
    "default": "wide",
}
COLOR = {"key": "background", "label": "Background", "type": "color"}
SCHEMA = [TOGGLE, SELECT, COLOR]


# ── Field definitions ────────────────────────────────────────────────────────


def test_option_fields_valid_in_repeater_schema():
    schema = [*SCHEMA, {"key": "title", "label": "Title", "type": "string"}]
    _validate_schema(schema)
    _validate_schema([{**COLOR, "default": "#FFF"}, {**COLOR, "default": ""}])
    _validate_schema([{**TOGGLE, "default": False}, {**SELECT, "default": None}])


def test_select_option_bounds():
    opts = [{"value": f"v{i}", "label": f"V{i}"} for i in range(24)]
    _validate_schema([{**SELECT, "options": opts, "default": "v23"}])
    for bad in ([], WIDTHS[:1], [*opts, {"value": "v24", "label": "V24"}]):
        with pytest.raises(StructureError):
            _validate_schema([{**SELECT, "options": bad, "default": None}])


@pytest.mark.parametrize(
    "field",
    [
        # options / default only on option types
        {"key": "t", "label": "T", "type": "string", "default": "x"},
        {"key": "t", "label": "T", "type": "image", "options": WIDTHS},
        # select needs options
        {"key": "w", "label": "W", "type": "select"},
        {"key": "w", "label": "W", "type": "select", "options": "narrow"},
        {**SELECT, "options": [WIDTHS[0], "wide"]},
        {**SELECT, "options": [WIDTHS[0], {"value": "wide"}]},
        {**SELECT, "options": [WIDTHS[0], {"value": "wide", "label": "W", "x": 1}]},
        {**SELECT, "options": [WIDTHS[0], {"value": "Wide", "label": "W"}], "default": None},
        {**SELECT, "options": [WIDTHS[0], {"value": "-wide", "label": "W"}], "default": None},
        {**SELECT, "options": [WIDTHS[0], {"value": "w" * 41, "label": "W"}], "default": None},
        {**SELECT, "options": [WIDTHS[0], {"value": "wide\n", "label": "W"}]},
        {**SELECT, "options": [WIDTHS[0], {"value": 3, "label": "W"}], "default": None},
        {**SELECT, "options": [WIDTHS[0], {"value": "narrow", "label": "N"}], "default": None},
        {**SELECT, "options": [WIDTHS[0], {"value": "wide", "label": ""}]},
        {**SELECT, "options": [WIDTHS[0], {"value": "wide", "label": "x" * 81}]},
        {**SELECT, "default": "full"},
        {**SELECT, "default": ""},
        {**SELECT, "default": ["wide"]},
        # toggle
        {**TOGGLE, "default": 1},
        {**TOGGLE, "default": "true"},
        {**TOGGLE, "options": WIDTHS},
        # color
        {**COLOR, "default": "red"},
        {**COLOR, "default": False},
        {**COLOR, "options": WIDTHS},
        # hint / surface stay media-only
        {**COLOR, "surface": "Dark"},
    ],
)
def test_invalid_option_field_rejected(field):
    with pytest.raises(StructureError):
        _validate_schema([field])


def test_options_schema_accepts_option_fields_only():
    validate_options_schema(SCHEMA)
    with pytest.raises(StructureError, match="invalid type 'string'"):
        validate_options_schema([*SCHEMA, {"key": "t", "label": "T", "type": "string"}])


@pytest.mark.parametrize(
    "schema",
    [
        None,
        [],
        {"show_title": TOGGLE},
        [{**TOGGLE, "key": f"k{i}"} for i in range(41)],
        [TOGGLE, {**COLOR, "key": "show_title"}],
        [{**TOGGLE, "key": "Show"}],
        [{**TOGGLE, "key": "show-title"}],
        [{**TOGGLE, "key": "k" * 41}],
        [{**TOGGLE, "key": 3}],
        [{**TOGGLE, "label": ""}],
        [{**TOGGLE, "label": "x" * 121}],
        [{k: v for k, v in TOGGLE.items() if k != "label"}],
        [{**SELECT, "options": WIDTHS[:1]}],
        [{**TOGGLE, "default": "yes"}],
    ],
)
def test_invalid_options_schema_rejected(schema):
    with pytest.raises(StructureError):
        validate_options_schema(schema)


def test_options_schema_limits_accepted():
    validate_options_schema([{**TOGGLE, "key": f"k{i}", "label": "x" * 120} for i in range(40)])


def test_item_field_model_keeps_options_and_false_default():
    field = RepeaterItemField(key="show", label="Show", type="toggle", default=False)
    assert field.model_dump(exclude_none=True) == {
        "key": "show",
        "label": "Show",
        "type": "toggle",
        "default": False,
    }
    select = RepeaterItemField(**SELECT)
    assert select.model_dump(exclude_none=True) == SELECT


# ── Repeater item values ─────────────────────────────────────────────────────


def _repeater(*items):
    return {"_schema": SCHEMA, "items": list(items)}


def test_repeater_option_values_validated_and_colour_normalised():
    out = normalize_option_fields(
        _repeater(
            {"_id": "a", "show_title": False, "content_width": "narrow", "background": "#ABC"},
            {"_id": "b", "content_width": "", "background": ""},
        )
    )
    assert out["items"][0] == {
        "_id": "a",
        "show_title": False,
        "content_width": "narrow",
        "background": "#aabbcc",
    }
    assert out["items"][1] == {"_id": "b", "content_width": "", "background": ""}


def test_repeater_missing_option_key_left_missing():
    content = _repeater({"_id": "a", "title": "x"})
    assert normalize_option_fields(content) == content


@pytest.mark.parametrize(
    "item",
    [
        {"show_title": 1},
        {"show_title": "true"},
        {"show_title": None},
        {"content_width": "full"},
        {"content_width": None},
        {"content_width": False},
        {"background": "blue"},
        {"background": None},
        {"background": 0},
    ],
)
def test_repeater_invalid_option_value_rejected(item):
    with pytest.raises(StructureError, match=r"^items\[1\]\."):
        normalize_option_fields(_repeater({}, item))


def test_repeater_without_option_fields_untouched():
    content = {"_schema": [{"key": "t", "type": "string"}], "items": [{"t": 1}]}
    assert normalize_option_fields(content) is content


def test_repeater_malformed_schema_entries_skipped():
    content = {"_schema": ["x", {"type": "toggle"}, TOGGLE], "items": [{"show_title": True}]}
    assert normalize_option_fields(content)["items"] == [{"show_title": True}]


def test_repeater_option_values_never_translated():
    content = _repeater({"_id": "a", "content_width": "wide", "background": "#aabbcc"})
    assert segments_of("repeater", content) == {}
    assert field_formats("repeater", content) == {
        "show_title": "plain",
        "content_width": "plain",
        "background": "plain",
    }


# ── Options service content ──────────────────────────────────────────────────


def test_normalize_options_fills_defaults_and_drops_unknown_keys():
    out = normalize_options(
        {"_schema": SCHEMA, "values": {"background": "#FFF", "stale": True}, "extra": 1}
    )
    assert out == {
        "_schema": SCHEMA,
        "values": {"show_title": True, "content_width": "wide", "background": "#ffffff"},
    }


def test_normalize_options_zero_values_without_defaults():
    schema = [
        {"key": "a", "label": "A", "type": "toggle"},
        {"key": "b", "label": "B", "type": "select", "options": WIDTHS},
        {"key": "c", "label": "C", "type": "color"},
        {"key": "d", "label": "D", "type": "color", "default": "#ABC"},
    ]
    out = normalize_options({"_schema": schema, "values": "nope"})
    assert out["values"] == {"a": False, "b": "", "c": "", "d": "#aabbcc"}


def test_normalize_options_keeps_valid_values():
    values = {"show_title": False, "content_width": "", "background": "#123456"}
    assert normalize_options({"_schema": SCHEMA, "values": values})["values"] == values


@pytest.mark.parametrize(
    "values",
    [
        {"show_title": "false"},
        {"content_width": "full"},
        {"background": "#12345"},
    ],
)
def test_normalize_options_invalid_value_rejected(values):
    with pytest.raises(StructureError, match=r"^values\."):
        normalize_options({"_schema": SCHEMA, "values": values})


def test_normalize_options_without_schema():
    assert normalize_options({"values": {"x": True}}) == {"values": {}}
    assert normalize_options({"_schema": [], "values": {"x": True}}) == {"values": {}}


def test_client_cannot_change_options_schema():
    tampered = [{**SELECT, "options": [*WIDTHS, {"value": "full", "label": "Full"}]}]
    out = apply_structure_rules(
        "options",
        {"_schema": tampered, "values": {}},
        is_admin=False,
        stored=({"_schema": SCHEMA, "values": {}},),
    )
    assert out["_schema"] == SCHEMA
    with pytest.raises(StructureError):
        normalize_options({**out, "values": {"content_width": "full"}})


def test_client_cannot_inject_options_schema():
    out = apply_structure_rules(
        "options", {"_schema": SCHEMA, "values": {}}, is_admin=False, stored=(None, None)
    )
    assert "_schema" not in out


def test_admin_save_without_schema_keeps_stored():
    out = apply_structure_rules(
        "options", {"values": {}}, is_admin=True, stored=(None, {"_schema": SCHEMA})
    )
    assert out["_schema"] == SCHEMA


def test_admin_options_schema_validated():
    new = [{**TOGGLE, "default": False}]
    out = apply_structure_rules(
        "options", {"_schema": new, "values": {}}, is_admin=True, stored=({"_schema": SCHEMA},)
    )
    assert out["_schema"] == new
    with pytest.raises(StructureError):
        apply_structure_rules(
            "options",
            {"_schema": [{"key": "t", "label": "T", "type": "string"}]},
            is_admin=True,
            stored=(),
        )


def test_options_content_passes_translation_untouched():
    content = normalize_options({"_schema": SCHEMA, "values": {}})
    assert segments_of("options", content) == {}
    assert normalize_content("options", content) == content
    assert field_formats("options", content) == {}
    provider = MagicMock()
    new, meta = sync_locale_draft(
        "options", content, {}, {"values": {"show_title": False}}, {}, provider, "en", "nl"
    )
    assert new == content and new is not content
    assert meta == {}
    provider.translate.assert_not_called()


def test_options_service_type_registered():
    assert SERVICE_TYPES["options"] == ("Display Options", "SlidersHorizontal")
    assert list(SERVICE_TYPES) == sorted(SERVICE_TYPES)


# ── Endpoints ────────────────────────────────────────────────────────────────

SVC_OPTIONS = {
    "id": "svc-o",
    "service_key": "home_page_options",
    "label": "Home page options",
    "display_order": 0,
    "page_name": "Home",
    "service_type_slug": "options",
}
STORED = {"_schema": SCHEMA, "values": {"show_title": True}}


def _project(slug, user):
    return {"id": f"project-{slug}", "slug": slug, "default_locale": "en", "locales": ["en"]}


@pytest.fixture
def as_user(auth_as, monkeypatch):
    def _set(user, project=_project):
        auth_as(user)
        monkeypatch.setattr("auth_service.routers.workspace.require_project_access", project)

    return _set


def _content_upserts(mock_supabase):
    return [
        c.args[0]
        for c in mock_supabase.upsert.call_args_list
        if isinstance(c.args[0], dict) and "project_service_id" in c.args[0]
    ]


def test_client_save_normalises_options(mock_supabase, client, as_user, client_user):
    as_user(client_user)
    mock_supabase.execute.side_effect = [
        MagicMock(data=SVC_OPTIONS),
        MagicMock(data=[{"id": "ce-en", "locale": "en", "draft_content": STORED}]),
        MagicMock(data=[{}]),
        MagicMock(data={**SVC_OPTIONS, "content_entries": []}),
    ]
    res = client.put(
        "/projects/demo/services/home_page_options",
        json={
            "content": {
                "_schema": [TOGGLE],  # a client cannot change the schema
                "values": {"background": "#ABCDEF", "x": 1},
            }
        },
    )
    assert res.status_code == 200
    assert _content_upserts(mock_supabase)[0]["draft_content"] == {
        "_schema": SCHEMA,
        "values": {"show_title": True, "content_width": "wide", "background": "#abcdef"},
    }


def test_save_options_with_invalid_value_is_422(mock_supabase, client, as_user, client_user):
    as_user(client_user)
    mock_supabase.execute.side_effect = [
        MagicMock(data=SVC_OPTIONS),
        MagicMock(data=[{"id": "ce-en", "locale": "en", "draft_content": STORED}]),
    ]
    res = client.put(
        "/projects/demo/services/home_page_options",
        json={"content": {"values": {"content_width": "full"}}},
    )
    assert res.status_code == 422
    assert res.json()["detail"].startswith("values.content_width")
    assert _content_upserts(mock_supabase) == []


def test_options_save_on_other_locale_goes_through_default(
    mock_supabase, client, as_user, client_user
):
    as_user(
        client_user,
        lambda slug, user: {
            "id": f"project-{slug}",
            "slug": slug,
            "default_locale": "en",
            "locales": ["en", "nl", "de"],
        },
    )
    mock_supabase.execute.side_effect = [
        MagicMock(data=SVC_OPTIONS),
        MagicMock(
            data=[
                {"id": "ce-en", "locale": "en", "draft_content": STORED, "translation_meta": None},
                {"id": "ce-nl", "locale": "nl", "draft_content": {}, "translation_meta": {}},
            ]
        ),
        MagicMock(data=[{}]),  # upsert en
        MagicMock(data=[{}]),  # upsert nl
        MagicMock(data=[{}]),  # upsert de
        MagicMock(data={**SVC_OPTIONS, "content_entries": []}),
    ]
    res = client.put(
        "/projects/demo/services/home_page_options?locale=nl",
        json={"content": {"values": {"show_title": False}}},
    )
    assert res.status_code == 200
    assert res.json()["locale"] == "nl"
    expected = {
        "_schema": SCHEMA,
        "values": {"show_title": False, "content_width": "wide", "background": ""},
    }
    ups = _content_upserts(mock_supabase)
    assert [u["locale"] for u in ups] == ["en", "nl", "de"]
    for u in ups:
        assert u["draft_content"] == expected
        assert not u.get("translation_meta")


def test_save_repeater_validates_option_values(mock_supabase, client, as_user, admin_user):
    as_user(admin_user)
    svc = {**SVC_OPTIONS, "service_key": "services_list", "service_type_slug": "repeater"}
    mock_supabase.execute.side_effect = [
        MagicMock(data=svc),
        MagicMock(data=[]),
        MagicMock(data=[{}]),
        MagicMock(data={**svc, "content_entries": []}),
    ]
    res = client.put(
        "/projects/demo/services/services_list",
        json={"content": _repeater({"_id": "a", "background": "#FFF"}, {"_id": "b"})},
    )
    assert res.status_code == 200
    items = _content_upserts(mock_supabase)[0]["draft_content"]["items"]
    assert items == [{"_id": "a", "background": "#ffffff"}, {"_id": "b"}]

    mock_supabase.execute.side_effect = [MagicMock(data=svc), MagicMock(data=[])]
    res = client.put(
        "/projects/demo/services/services_list",
        json={"content": _repeater({"_id": "a", "show_title": "yes"})},
    )
    assert res.status_code == 422
    assert res.json()["detail"].startswith("items[0].show_title")


def test_add_options_service_seeds_defaults(mock_supabase, client, as_user, admin_user):
    as_user(admin_user)
    mock_supabase.execute.side_effect = [
        MagicMock(data=[{}]),  # project_services insert
        MagicMock(data={"id": "svc-o"}),  # new service id
        MagicMock(data=[{}]),  # content_entries insert
    ]
    res = client.post(
        "/projects/demo/services",
        json={
            "service_type_slug": "options",
            "service_key": "home_page_options",
            "label": "Home page options",
            "item_schema": [*SCHEMA, {"key": "dense", "label": "Dense", "type": "toggle"}],
        },
    )
    assert res.status_code == 201
    seed = mock_supabase.insert.call_args_list[-1].args[0]
    expected = {
        "_schema": [*SCHEMA, {"key": "dense", "label": "Dense", "type": "toggle"}],
        "values": {
            "show_title": True,
            "content_width": "wide",
            "background": "",
            "dense": False,
        },
    }
    assert seed["project_service_id"] == "svc-o"
    assert seed["locale"] == "en"
    assert seed["draft_content"] == expected
    assert seed["published_content"] == expected


def test_add_options_service_requires_item_schema(mock_supabase, client, as_user, admin_user):
    as_user(admin_user)
    res = client.post(
        "/projects/demo/services",
        json={"service_type_slug": "options", "service_key": "home_page_options"},
    )
    assert res.status_code == 422
    assert res.json()["detail"] == "item_schema is required when creating an options service"
    mock_supabase.insert.assert_not_called()


@pytest.mark.parametrize(
    "item_schema",
    [
        [{"key": "title", "label": "Title", "type": "string"}],
        [{"key": "w", "label": "W", "type": "select", "options": WIDTHS[:1]}],
        [TOGGLE, {**COLOR, "key": "show_title"}],
    ],
)
def test_add_options_service_rejects_bad_schema(
    mock_supabase, client, as_user, admin_user, item_schema
):
    as_user(admin_user)
    res = client.post(
        "/projects/demo/services",
        json={
            "service_type_slug": "options",
            "service_key": "home_page_options",
            "item_schema": item_schema,
        },
    )
    assert res.status_code == 422
    mock_supabase.insert.assert_not_called()


def test_add_repeater_with_option_fields_accepted(mock_supabase, client, as_user, admin_user):
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
            "item_schema": [{**TOGGLE, "default": False}, SELECT, COLOR],
        },
    )
    assert res.status_code == 201
    seed = mock_supabase.insert.call_args_list[-1].args[0]
    assert seed["draft_content"] == {
        "_schema": [{**TOGGLE, "default": False}, SELECT, COLOR],
        "items": [],
    }


def test_add_repeater_with_default_on_string_is_422(mock_supabase, client, as_user, admin_user):
    as_user(admin_user)
    res = client.post(
        "/projects/demo/services",
        json={
            "service_type_slug": "repeater",
            "service_key": "services_list",
            "item_schema": [{"key": "t", "label": "T", "type": "string", "default": "x"}],
        },
    )
    assert res.status_code == 422
    mock_supabase.insert.assert_not_called()
