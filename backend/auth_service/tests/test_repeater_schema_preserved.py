"""A repeater's `_schema` (per-item field definitions) is structural metadata,
seeded at create time from `item_schema`. A content write that omits it — the
connector's items-only seed PUT, or any client that round-trips only `items` —
must NOT wipe it, or the dashboard shows an uneditable "no field schema defined"
repeater. Regression: every repeater on a provisioned project lost its schema
because the seed PUT full-replaced the content the create step had seeded."""

from auth_service.routers.workspace import _grafted_repeater_content, _repeater_schema_of

SCHEMA = [
    {"key": "day", "label": "Day", "type": "string"},
    {"key": "open", "label": "Opens", "type": "string"},
]


def test_repeater_schema_of_returns_nonempty_schema():
    assert _repeater_schema_of({"_schema": SCHEMA, "items": []}) == SCHEMA


def test_repeater_schema_of_none_for_missing_or_empty():
    assert _repeater_schema_of({"items": [{"day": "Mon"}]}) is None
    assert _repeater_schema_of({"_schema": [], "items": []}) is None
    assert _repeater_schema_of(None) is None
    assert _repeater_schema_of("nope") is None


def test_keeps_incoming_schema_untouched():
    content = {"_schema": SCHEMA, "items": [{"day": "Mon"}]}
    # Even with a different fallback, the incoming schema wins.
    out = _grafted_repeater_content(content, {"_schema": [{"key": "x"}]})
    assert out is content


def test_grafts_schema_onto_items_only_payload_from_default_locale():
    incoming = {"items": [{"day": "Mon", "open": "09:00"}]}
    stored_default = {"_schema": SCHEMA, "items": []}
    out = _grafted_repeater_content(incoming, stored_default)
    assert out["_schema"] == SCHEMA
    assert out["items"] == [{"day": "Mon", "open": "09:00"}]


def test_falls_back_through_blobs_in_order():
    incoming = {"items": []}
    # First two fallbacks have no usable schema; the third supplies it.
    out = _grafted_repeater_content(incoming, None, {"_schema": []}, {"_schema": SCHEMA})
    assert out["_schema"] == SCHEMA


def test_unchanged_when_no_schema_available_anywhere():
    incoming = {"items": [{"day": "Mon"}]}
    out = _grafted_repeater_content(incoming, {"items": []}, None)
    assert out == incoming
    assert "_schema" not in out
