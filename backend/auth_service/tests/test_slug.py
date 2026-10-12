"""Repeater `slug` field type: slugify parity, translation round-trip, save normalisation."""

import copy
import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from auth_service.services.content_structure import (
    VALID_REPEATER_TYPES,
    StructureError,
    normalize_slug_fields,
)
from auth_service.services.rich_text import field_formats, format_of
from auth_service.services.segments import apply_segments, formats_of, segments_of, src_hash
from auth_service.services.slug import MAX_SLUG_LENGTH, slugify
from auth_service.translation.sync import sync_locale_draft

_REPO = Path(__file__).resolve().parents[3]
_VECTORS = json.loads(
    (_REPO / "client-kit" / "rich-text" / "fixtures" / "slug-vectors.json").read_text("utf-8")
)


@pytest.mark.parametrize("vec", _VECTORS, ids=[v["name"] for v in _VECTORS])
def test_slug_vectors(vec):
    assert slugify(vec["input"]) == vec["expected"]


@pytest.mark.parametrize("vec", _VECTORS, ids=[v["name"] for v in _VECTORS])
def test_slugify_is_idempotent(vec):
    out = slugify(vec["input"])
    assert slugify(out) == out
    assert len(out) <= MAX_SLUG_LENGTH


@pytest.mark.parametrize("value", [None, 3, ["a"], {"a": 1}])
def test_slugify_non_string_is_empty(value):
    assert slugify(value) == ""


# ── Type registration ────────────────────────────────────────────────────────


def test_slug_is_a_valid_repeater_type_with_plain_format():
    assert "slug" in VALID_REPEATER_TYPES
    content = {"_schema": [{"key": "slug", "type": "slug"}], "items": [{"_id": "a", "slug": "x"}]}
    assert format_of("repeater", "items.a.slug", content) == "plain"
    assert field_formats("repeater", content) == {"slug": "plain"}


SCHEMA = [
    {"key": "title", "type": "string", "label": "Title"},
    {"key": "slug", "type": "slug", "label": "Slug"},
    {"key": "tags", "type": "tags", "label": "Tags"},
]


def _rep(*items):
    return {"_schema": SCHEMA, "items": list(items)}


# ── Segments ─────────────────────────────────────────────────────────────────


def test_segments_of_humanises_slug():
    content = _rep({"_id": "a", "title": "Laptop repairs", "slug": "laptop-repairs"})
    assert segments_of("repeater", content) == {
        "items.a.title": "Laptop repairs",
        "items.a.slug": "laptop repairs",
    }


def test_formats_of_slug_is_text():
    content = _rep({"_id": "a", "slug": "laptop-repairs"})
    assert formats_of("repeater", content) == {"items.a.slug": "text"}
    assert formats_of("repeater", content, rich_text_version=1) == {"items.a.slug": "text"}


def test_apply_segments_slugifies_translation():
    content = _rep({"_id": "a", "slug": "laptop-repairs"})
    out = apply_segments(
        copy.deepcopy(content), "repeater", {"items.a.slug": "Reparații laptopuri"}
    )
    assert out["items"][0]["slug"] == "reparatii-laptopuri"


def test_apply_segments_empty_slug_translation_keeps_existing_value_slugified():
    content = _rep({"_id": "a", "slug": "Laptop Repairs"}, {"_id": "b", "slug": "ok-slug"})
    out = apply_segments(
        copy.deepcopy(content), "repeater", {"items.a.slug": "東京", "items.b.slug": "!!"}
    )
    assert out["items"][0]["slug"] == "laptop-repairs"
    assert out["items"][1]["slug"] == "ok-slug"


def test_apply_segments_never_inserts_a_slug():
    out = apply_segments(copy.deepcopy(_rep({"_id": "a"})), "repeater", {"items.a.slug": "x y"})
    assert "slug" not in out["items"][0]


def test_segments_round_trip_for_slug_and_other_types():
    content = _rep(
        {"_id": "a", "title": "Hello - world", "slug": "hello-world", "tags": ["a-b", "c"]}
    )
    segs = segments_of("repeater", content)
    out = apply_segments(copy.deepcopy(content), "repeater", segs)
    assert out == content
    # The string field keeps its hyphen; only the slug is humanised.
    assert segs["items.a.title"] == "Hello - world"
    assert segs["items.a.tags.0"] == "a-b"


class _Upper:
    """A fake provider that 'translates' by upper-casing (keeps word boundaries)."""

    def __init__(self):
        self.calls = []

    def translate(self, texts, *, source, target, fmt):
        self.calls.append(list(texts))
        return [t.upper() for t in texts]


def test_sync_translates_humanised_slug_and_stores_slug():
    provider = _Upper()
    default = _rep({"_id": "a", "title": "Hi", "slug": "laptop-repairs"})
    out, meta = sync_locale_draft("repeater", default, None, None, None, provider, "en", "ro")
    assert provider.calls == [["Hi", "laptop repairs"]]  # DeepL sees words, not a token
    assert out["items"][0]["slug"] == "laptop-repairs"  # LAPTOP REPAIRS → slugified
    assert out["items"][0]["title"] == "HI"
    assert meta == {}


def test_sync_keeps_manual_slug_override_and_hash_is_on_humanised_text():
    default = _rep({"_id": "a", "slug": "laptop-repairs"})
    target = _rep({"_id": "a", "slug": "reparatii-laptop"})
    anchor = {"items.a.slug": {"src_hash": src_hash("laptop repairs")}}
    out, meta = sync_locale_draft(
        "repeater", default, default, target, anchor, _Upper(), "en", "ro"
    )
    assert out["items"][0]["slug"] == "reparatii-laptop"
    assert meta == anchor


# ── Save normalisation ───────────────────────────────────────────────────────


def test_normalize_slug_fields():
    content = _rep(
        {"_id": "a", "title": "Keep  Me", "slug": "Laptop Repairs & Maintenance"},
        {"_id": "b", "slug": ""},
        {"_id": "c"},
        "not-a-dict",
    )
    out = normalize_slug_fields(content)
    assert out["items"][0] == {
        "_id": "a",
        "title": "Keep  Me",
        "slug": "laptop-repairs-maintenance",
    }
    assert out["items"][1]["slug"] == ""
    assert "slug" not in out["items"][2]
    assert out["items"][3] == "not-a-dict"
    assert content["items"][0]["slug"] == "Laptop Repairs & Maintenance"  # input not mutated


def test_normalize_slug_fields_keeps_numbers_and_empties_none():
    out = normalize_slug_fields(
        _rep({"_id": "a", "slug": 2026}, {"_id": "b", "slug": 1.5}, {"_id": "c", "slug": None})
    )
    assert [i["slug"] for i in out["items"]] == ["2026", "1-5", ""]


@pytest.mark.parametrize("value", [True, False, {"a": 1}, ["a"]])
def test_normalize_slug_fields_rejects_other_non_strings(value):
    with pytest.raises(StructureError, match=r"items\[0\]\.slug"):
        normalize_slug_fields(_rep({"_id": "a", "slug": value}))


def test_save_with_non_string_slug_is_422(mock_supabase, client, auth_as, admin_user, monkeypatch):
    auth_as(admin_user)
    monkeypatch.setattr("auth_service.routers.workspace.require_project_access", _project(["en"]))
    mock_supabase.execute.side_effect = [MagicMock(data=SVC), MagicMock(data=[])]
    res = client.put(
        "/projects/demo/services/services_catalog",
        json={"content": _rep({"_id": "a", "slug": {"x": 1}})},
    )
    assert res.status_code == 422
    assert "items[0].slug" in res.json()["detail"]


def test_normalize_slug_fields_without_slug_fields_is_unchanged():
    content = {"_schema": [{"key": "t", "type": "string"}], "items": [{"t": "A B"}]}
    assert normalize_slug_fields(content) == content
    assert normalize_slug_fields({"items": "x"}) == {"items": "x"}


SVC = {
    "id": "svc-r",
    "service_key": "services_catalog",
    "label": "Services",
    "display_order": 0,
    "page_name": "Services",
    "service_type_slug": "repeater",
}


def _project(locales):
    def _get(slug, user):
        return {
            "id": "project-demo",
            "slug": "demo",
            "default_locale": locales[0],
            "locales": locales,
        }

    return _get


def _upserts(mock_supabase):
    return [
        c.args[0]
        for c in mock_supabase.upsert.call_args_list
        if isinstance(c.args[0], dict) and "project_service_id" in c.args[0]
    ]


@pytest.mark.parametrize("seed", [False, True])
def test_default_locale_save_normalises_slug(
    mock_supabase, client, auth_as, admin_user, monkeypatch, seed
):
    auth_as(admin_user)
    monkeypatch.setattr(
        "auth_service.routers.workspace.require_project_access", _project(["en", "ro"])
    )
    mock_supabase.execute.side_effect = [
        MagicMock(data=SVC),
        MagicMock(data=[]),
        MagicMock(data=[{}]),
        MagicMock(data=[{}]),
        MagicMock(data={**SVC, "content_entries": []}),
    ]
    res = client.put(
        f"/projects/demo/services/services_catalog?seed={'true' if seed else 'false'}",
        json={"content": _rep({"_id": "a", "slug": "Laptop Repairs and Maintenance"})},
    )
    assert res.status_code == 200
    ups = {u["locale"]: u for u in _upserts(mock_supabase)}
    assert ups["en"]["draft_content"]["items"][0]["slug"] == "laptop-repairs-and-maintenance"
    # NullProvider echoes the humanised source; the stored ro slug is URL-safe again.
    assert ups["ro"]["draft_content"]["items"][0]["slug"] == "laptop-repairs-and-maintenance"
    if seed:
        assert ups["en"]["published_content"]["items"][0]["slug"] == (
            "laptop-repairs-and-maintenance"
        )


def test_client_override_save_normalises_slug_and_marks_manual(
    mock_supabase, client, auth_as, client_user, monkeypatch
):
    auth_as(client_user)
    monkeypatch.setattr(
        "auth_service.routers.workspace.require_project_access", _project(["en", "ro"])
    )
    en = _rep({"_id": "a", "slug": "laptop-repairs"})
    ro = _rep({"_id": "a", "slug": "laptop-repairs"})
    mock_supabase.execute.side_effect = [
        MagicMock(data=SVC),
        MagicMock(
            data=[
                {"locale": "en", "draft_content": en, "translation_meta": {}},
                {"locale": "ro", "draft_content": ro, "translation_meta": {}},
            ]
        ),
        MagicMock(data=[{}]),
        MagicMock(data={**SVC, "content_entries": []}),
    ]
    res = client.put(
        "/projects/demo/services/services_catalog?locale=ro",
        json={"content": _rep({"_id": "a", "slug": "Reparații Laptop"})},
    )
    assert res.status_code == 200
    (ro_up,) = _upserts(mock_supabase)
    assert ro_up["draft_content"]["items"][0]["slug"] == "reparatii-laptop"
    assert ro_up["translation_meta"] == {"items.a.slug": {"src_hash": src_hash("laptop repairs")}}


def test_client_override_resaving_same_slug_is_not_manual(
    mock_supabase, client, auth_as, client_user, monkeypatch
):
    auth_as(client_user)
    monkeypatch.setattr(
        "auth_service.routers.workspace.require_project_access", _project(["en", "ro"])
    )
    en = _rep({"_id": "a", "slug": "laptop-repairs"})
    mock_supabase.execute.side_effect = [
        MagicMock(data=SVC),
        MagicMock(
            data=[
                {"locale": "en", "draft_content": en, "translation_meta": {}},
                {"locale": "ro", "draft_content": copy.deepcopy(en), "translation_meta": {}},
            ]
        ),
        MagicMock(data=[{}]),
        MagicMock(data={**SVC, "content_entries": []}),
    ]
    res = client.put(
        "/projects/demo/services/services_catalog?locale=ro",
        json={"content": _rep({"_id": "a", "slug": "Laptop Repairs"})},
    )
    assert res.status_code == 200
    (ro_up,) = _upserts(mock_supabase)
    assert ro_up["translation_meta"] == {}


def test_admin_retype_string_to_slug_slugifies_every_locale_and_keeps_overrides(
    mock_supabase, client, auth_as, admin_user, monkeypatch
):
    """The it-global-services fix path: `slug` was a `string` field, so stored rows
    hold spaced (machine-translated) values. Retyping it to `slug` on an admin save
    slugifies every locale; RO keeps its own (auto) wording, DE its manual override."""
    auth_as(admin_user)
    monkeypatch.setattr(
        "auth_service.routers.workspace.require_project_access", _project(["en", "ro", "de"])
    )
    old_schema = [
        {"key": "title", "type": "string", "label": "Title"},
        {"key": "slug", "type": "string", "label": "Slug"},
    ]
    new_schema = [{**old_schema[0]}, {**old_schema[1], "type": "slug"}]

    def _row(locale, title, slug, meta):
        content = {"_schema": old_schema, "items": [{"_id": "a", "title": title, "slug": slug}]}
        return {
            "locale": locale,
            "draft_content": content,
            "published_content": content,
            "translation_meta": meta,
        }

    de_meta = {"items.a.slug": {"src_hash": src_hash("laptop repairs and maintenance")}}
    mock_supabase.execute.side_effect = [
        MagicMock(data=SVC),
        MagicMock(
            data=[
                _row("en", "Laptop repairs", "laptop repairs and maintenance", {}),
                _row("ro", "Reparații laptop", "Reparații și întreținere laptopuri", {}),
                _row("de", "Laptop-Reparatur", "Laptop Reparatur und Wartung", de_meta),
            ]
        ),
        MagicMock(data=[{}]),
        MagicMock(data=[{}]),
        MagicMock(data=[{}]),
        MagicMock(data={**SVC, "content_entries": []}),
    ]
    res = client.put(
        "/projects/demo/services/services_catalog",
        json={
            "content": {
                "_schema": new_schema,
                "items": [
                    {
                        "_id": "a",
                        "title": "Laptop repairs",
                        "slug": "laptop repairs and maintenance",
                    }
                ],
            }
        },
    )
    assert res.status_code == 200
    ups = {u["locale"]: u for u in _upserts(mock_supabase)}
    assert set(ups) == {"en", "ro", "de"}
    slugs = {loc: u["draft_content"]["items"][0]["slug"] for loc, u in ups.items()}
    assert slugs == {
        "en": "laptop-repairs-and-maintenance",
        "ro": "reparatii-si-intretinere-laptopuri",  # auto, source unchanged → kept
        "de": "laptop-reparatur-und-wartung",  # manual override kept
    }
    assert ups["de"]["translation_meta"] == de_meta
    assert ups["ro"]["draft_content"]["items"][0]["title"] == "Reparații laptop"
    for u in ups.values():
        assert u["draft_content"]["_schema"] == new_schema


def test_public_types_list_slug():
    from auth_service.routers.content import _TS_TYPE_MAP

    assert '"tags" | "slug" | "image" | "icon"' in _TS_TYPE_MAP["repeater"]
