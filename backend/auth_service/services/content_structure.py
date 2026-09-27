"""Structural metadata policy for CMS content (ADR-0010).

`_schema` (repeater field definitions) and `_formats` (key_value per-entry
formats) decide how fields are edited and rendered, so only admins/agents may
change them. A client save always keeps the stored values; any payload that
omits them keeps the stored ones (the connector's items-only seed PUT)."""

from __future__ import annotations

from .rich_text import FORMATS

VALID_REPEATER_TYPES = frozenset({"string", "inline", "richtext", "url", "tags"})


class StructureError(ValueError):
    """Invalid admin-supplied structure (→ HTTP 422)."""


def _first(stored: tuple, key: str, kind: type):
    for blob in stored:
        if isinstance(blob, dict):
            val = blob.get(key)
            if isinstance(val, kind) and val:
                return val
    return None


def _validate_schema(schema: object) -> None:
    if schema is None:
        return
    if not isinstance(schema, list):
        raise StructureError("_schema must be a list")
    for field in schema:
        if not isinstance(field, dict) or not isinstance(field.get("key"), str):
            raise StructureError("_schema entries need a string 'key'")
        if field.get("type") not in VALID_REPEATER_TYPES:
            raise StructureError(
                f"_schema field '{field.get('key')}' has invalid type {field.get('type')!r}; "
                f"allowed: {', '.join(sorted(VALID_REPEATER_TYPES))}"
            )


def _validate_formats(formats: object) -> None:
    if not isinstance(formats, dict):
        raise StructureError("_formats must be an object")
    for key, fmt in formats.items():
        if fmt not in FORMATS:
            raise StructureError(f"_formats['{key}'] must be one of {', '.join(FORMATS)}")


def apply_structure_rules(
    service_type: str, content: dict, *, is_admin: bool, stored: tuple
) -> dict:
    if not isinstance(content, dict):
        return content
    if service_type == "repeater":
        stored_schema = _first(stored, "_schema", list)
        incoming = content.get("_schema")
        has_incoming = isinstance(incoming, list) and bool(incoming)
        if (not is_admin or not has_incoming) and stored_schema is not None:
            return {**content, "_schema": stored_schema}
        if is_admin and has_incoming:
            _validate_schema(incoming)
        return content
    if service_type == "key_value":
        stored_formats = _first(stored, "_formats", dict)
        if not is_admin or "_formats" not in content:
            if stored_formats is not None:
                return {**content, "_formats": stored_formats}
            return {k: v for k, v in content.items() if k != "_formats"}
        incoming = content.get("_formats") or {}
        _validate_formats(incoming)
        entries = content.get("entries")
        keys = set(entries.keys()) if isinstance(entries, dict) else set()
        return {**content, "_formats": {k: v for k, v in incoming.items() if k in keys}}
    return content
