import copy

from auth_service.services.segments import apply_segments, formats_of, segments_of


def test_apply_round_trips_text_block():
    src = {"title": "Hi", "body": "Body"}
    out = apply_segments(copy.deepcopy(src), "text_block", {"title": "Hallo", "body": "Tekst"})
    assert out == {"title": "Hallo", "body": "Tekst"}


def test_apply_key_value_by_path():
    src = {"entries": {"email": "a@b.com", "program": "Mon-Fri"}}
    out = apply_segments(copy.deepcopy(src), "key_value", {"entries.program": "Ma-Vr"})
    assert out["entries"]["program"] == "Ma-Vr"
    assert out["entries"]["email"] == "a@b.com"  # untouched path preserved


def test_apply_repeater_by_item_id_and_tags():
    src = {
        "_schema": [{"key": "title", "type": "string"}, {"key": "tags", "type": "tags"}],
        "items": [{"_id": "x", "title": "Hosting", "tags": ["fast", "cheap"]}],
    }
    out = apply_segments(
        copy.deepcopy(src),
        "repeater",
        {
            "items.x.title": "Hosting NL",
            "items.x.tags.0": "snel",
        },
    )
    assert out["items"][0]["title"] == "Hosting NL"
    assert out["items"][0]["tags"] == ["snel", "cheap"]  # only index 0 replaced


def test_apply_then_segments_is_identity_for_provided_paths():
    src = {"title": "A", "body": "B"}
    vals = {"title": "X", "body": "Y"}
    out = apply_segments(copy.deepcopy(src), "text_block", vals)
    assert segments_of("text_block", out) == vals


def test_formats_marks_richtext_as_markdown():
    fmts = formats_of("text_block", {"title": "T", "body": "B"})
    assert fmts == {"title": "text", "body": "markdown"}


def test_formats_repeater_richtext_field():
    content = {
        "_schema": [{"key": "name", "type": "string"}, {"key": "desc", "type": "richtext"}],
        "items": [{"_id": "x", "name": "N", "desc": "D"}],
    }
    fmts = formats_of("repeater", content)
    assert fmts["items.x.name"] == "text"
    assert fmts["items.x.desc"] == "markdown"


def test_apply_does_not_insert_unknown_repeater_field():
    src = {
        "_schema": [{"key": "title", "type": "string"}],
        "items": [{"_id": "x"}],  # item has no "title" key
    }
    out = apply_segments(copy.deepcopy(src), "repeater", {"items.x.title": "Hi"})
    assert "title" not in out["items"][0]  # never inserted


def test_formats_image_and_file_download():
    assert formats_of("image", {"alt": "Logo"}) == {"alt": "text"}
    assert formats_of("floor_plan", {"alt": "Plan"}) == {"alt": "text"}
    assert formats_of("file_download", {"filename": "Brochure"}) == {"filename": "text"}


def test_formats_key_value():
    assert formats_of("key_value", {"entries": {"x": "v"}}) == {"entries.x": "text"}
