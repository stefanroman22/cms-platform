from auth_service.services.segments import segments_of, src_hash


def test_src_hash_is_stable_and_changes_with_input():
    assert src_hash("hello") == src_hash("hello")
    assert src_hash("hello") != src_hash("hellp")
    assert len(src_hash("hello")) == 16


def test_text_block_yields_title_and_body():
    out = segments_of("text_block", {"title": "Hi", "body": "Body **md**"})
    assert out == {"title": "Hi", "body": "Body **md**"}


def test_text_block_skips_empty_and_missing():
    assert segments_of("text_block", {"title": "", "body": "Only body"}) == {"body": "Only body"}
    assert segments_of("text_block", {}) == {}


def test_image_yields_alt_only():
    out = segments_of("image", {"url": "/logo.png", "alt": "Company logo"})
    assert out == {"alt": "Company logo"}


def test_file_download_yields_filename_only():
    out = segments_of("file_download", {"url": "/x.pdf", "filename": "Brochure"})
    assert out == {"filename": "Brochure"}


def test_key_value_yields_string_values_only():
    out = segments_of(
        "key_value",
        {"entries": {"email": "a@b.com", "program": "Mon-Fri", "count": 3}},
    )
    assert out == {"entries.email": "a@b.com", "entries.program": "Mon-Fri"}


def test_repeater_uses_item_id_and_field_types():
    content = {
        "_schema": [
            {"key": "title", "type": "string"},
            {"key": "desc", "type": "richtext"},
            {"key": "link", "type": "url"},
            {"key": "tags", "type": "tags"},
        ],
        "items": [
            {"_id": "abc", "title": "Hosting", "desc": "Fast", "link": "/h", "tags": ["a", "b"]},
        ],
    }
    out = segments_of("repeater", content)
    assert out == {
        "items.abc.title": "Hosting",
        "items.abc.desc": "Fast",
        "items.abc.tags.0": "a",
        "items.abc.tags.1": "b",
    }


def test_repeater_falls_back_to_index_without_id():
    content = {"_schema": [{"key": "title", "type": "string"}], "items": [{"title": "X"}]}
    assert segments_of("repeater", content) == {"items.0.title": "X"}


def test_non_text_types_yield_nothing():
    assert segments_of("gallery", {"items": ["/a.jpg", "/b.jpg"]}) == {}
    assert segments_of("video", {"url": "/v", "poster": "/p"}) == {}
    assert segments_of("email_config", {"destination_email": "x@y.com"}) == {}
