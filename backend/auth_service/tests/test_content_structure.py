import pytest

from auth_service.services.content_structure import StructureError, apply_structure_rules

STORED_SCHEMA = [{"key": "t", "label": "T", "type": "string"}]
NEW_SCHEMA = [{"key": "t", "label": "T", "type": "inline"}]


def test_client_cannot_change_repeater_schema():
    out = apply_structure_rules(
        "repeater",
        {"_schema": NEW_SCHEMA, "items": []},
        is_admin=False,
        stored=({"_schema": STORED_SCHEMA, "items": []},),
    )
    assert out["_schema"] == STORED_SCHEMA


def test_admin_can_change_repeater_schema():
    out = apply_structure_rules(
        "repeater",
        {"_schema": NEW_SCHEMA, "items": []},
        is_admin=True,
        stored=({"_schema": STORED_SCHEMA},),
    )
    assert out["_schema"] == NEW_SCHEMA


def test_missing_schema_is_grafted_for_everyone():
    for admin in (True, False):
        out = apply_structure_rules(
            "repeater", {"items": []}, is_admin=admin, stored=(None, {"_schema": STORED_SCHEMA})
        )
        assert out["_schema"] == STORED_SCHEMA


def test_admin_invalid_repeater_type_rejected():
    with pytest.raises(StructureError):
        apply_structure_rules(
            "repeater",
            {"_schema": [{"key": "t", "label": "T", "type": "html"}], "items": []},
            is_admin=True,
            stored=(),
        )


def test_client_cannot_change_formats_and_cannot_inject_them():
    out = apply_structure_rules(
        "key_value",
        {"entries": {"a": "x"}, "_formats": {"a": "rich"}},
        is_admin=False,
        stored=({"entries": {"a": "x"}, "_formats": {"a": "inline"}},),
    )
    assert out["_formats"] == {"a": "inline"}
    out2 = apply_structure_rules(
        "key_value",
        {"entries": {"a": "x"}, "_formats": {"a": "rich"}},
        is_admin=False,
        stored=({},),
    )
    assert "_formats" not in out2


def test_admin_payload_without_formats_keeps_stored():
    out = apply_structure_rules(
        "key_value", {"entries": {"a": "x"}}, is_admin=True, stored=({"_formats": {"a": "rich"}},)
    )
    assert out["_formats"] == {"a": "rich"}


def test_admin_formats_validated_and_pruned_to_entries():
    out = apply_structure_rules(
        "key_value",
        {"entries": {"a": "x"}, "_formats": {"a": "rich", "gone": "inline"}},
        is_admin=True,
        stored=(),
    )
    assert out["_formats"] == {"a": "rich"}
    with pytest.raises(StructureError):
        apply_structure_rules(
            "key_value",
            {"entries": {"a": "x"}, "_formats": {"a": "bold"}},
            is_admin=True,
            stored=(),
        )


def test_other_types_untouched():
    c = {"title": "x"}
    assert apply_structure_rules("text_block", c, is_admin=False, stored=()) is c
