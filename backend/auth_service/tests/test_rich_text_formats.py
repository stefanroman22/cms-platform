import pytest

from auth_service.services.rich_text import (
    RichTextFieldError,
    field_formats,
    format_of,
    normalize_content,
)
from auth_service.services.segments import formats_of, segments_of

REPEATER = {
    "_schema": [
        {"key": "title", "label": "Title", "type": "inline"},
        {"key": "body", "label": "Body", "type": "richtext"},
        {"key": "name", "label": "Name", "type": "string"},
        {"key": "link", "label": "Link", "type": "url"},
        {"key": "tags", "label": "Tags", "type": "tags"},
    ],
    "items": [
        {
            "_id": "i1",
            "title": "A & B",
            "body": "**x**",
            "name": "N & M",
            "link": "https://a.ro",
            "tags": ["t"],
        },
    ],
}
KV = {
    "entries": {"phone": "+40 7", "about": "We & you", "bio": "<p>x</p>"},
    "_formats": {"about": "inline", "bio": "rich", "bad": "weird"},
}


def test_format_of_text_block():
    assert format_of("text_block", "title", {}) == "inline"
    assert format_of("text_block", "body", {}) == "rich"


def test_format_of_repeater_by_schema_type():
    assert format_of("repeater", "items.i1.title", REPEATER) == "inline"
    assert format_of("repeater", "items.i1.body", REPEATER) == "rich"
    assert format_of("repeater", "items.i1.name", REPEATER) == "plain"
    assert format_of("repeater", "items.i1.tags.0", REPEATER) == "plain"
    assert format_of("repeater", "items.i1.missing", REPEATER) == "plain"


def test_format_of_key_value_defaults_to_plain_and_ignores_invalid():
    assert format_of("key_value", "entries.phone", KV) == "plain"
    assert format_of("key_value", "entries.about", KV) == "inline"
    assert format_of("key_value", "entries.bio", KV) == "rich"
    assert format_of("key_value", "entries.bad", {"_formats": {"bad": "weird"}}) == "plain"


def test_format_of_other_types_plain():
    assert format_of("image", "alt", {}) == "plain"
    assert format_of("file_download", "filename", {}) == "plain"


def test_field_formats_shapes():
    assert field_formats("text_block", {}) == {"title": "inline", "body": "rich"}
    assert field_formats("repeater", REPEATER) == {
        "title": "inline",
        "body": "rich",
        "name": "plain",
        "link": "plain",
        "tags": "plain",
    }
    assert field_formats("key_value", KV) == {
        "phone": "plain",
        "about": "inline",
        "bio": "rich",
        "*": "plain",
    }
    assert field_formats("image", {}) == {"alt": "plain"}
    assert field_formats("file_download", {}) == {"filename": "plain"}
    assert field_formats("gallery", {}) == {}


def test_normalize_content_touches_only_inline_and_rich_leaves():
    out = normalize_content("repeater", REPEATER)
    item = out["items"][0]
    assert item["title"] == "A &amp; B"
    assert item["body"] == "<p><strong>x</strong></p>"  # tag-free rich → legacy
    assert item["name"] == "N & M"  # plain untouched
    assert item["link"] == "https://a.ro"
    assert item["tags"] == ["t"]
    assert out["_schema"] == REPEATER["_schema"]
    assert REPEATER["items"][0]["title"] == "A & B"  # input not mutated


def test_normalize_content_key_value():
    out = normalize_content("key_value", KV)
    assert out["entries"] == {"phone": "+40 7", "about": "We &amp; you", "bio": "<p>x</p>"}


def test_normalize_content_legacy_flag_for_inline():
    out = normalize_content("text_block", {"title": "a\nb", "body": ""}, legacy=True)
    assert out == {"title": "a<br>b", "body": ""}


def test_normalize_content_reports_path_on_limit():
    with pytest.raises(RichTextFieldError) as exc:
        normalize_content("text_block", {"title": "x" * 2001})
    assert exc.value.path == "title"
    assert exc.value.limit == 2000


def test_segments_include_inline_repeater_fields():
    segs = segments_of("repeater", REPEATER)
    assert "items.i1.title" in segs


def test_formats_of_versions():
    legacy = formats_of("repeater", REPEATER)
    assert legacy["items.i1.body"] == "markdown"
    assert legacy["items.i1.title"] == "text"
    v1 = formats_of("repeater", REPEATER, rich_text_version=1)
    assert v1["items.i1.body"] == "html"
    assert v1["items.i1.title"] == "html"
    assert v1["items.i1.name"] == "text"
    assert v1["items.i1.tags.0"] == "text"
    assert formats_of("text_block", {"title": "t", "body": "b"}, rich_text_version=1) == {
        "title": "html",
        "body": "html",
    }
