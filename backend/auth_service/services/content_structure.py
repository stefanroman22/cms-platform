"""Structural metadata policy for CMS content (ADR-0010).

`_schema` (repeater field definitions) and `_formats` (key_value per-entry
formats) decide how fields are edited and rendered, so only admins/agents may
change them. A client save always keeps the stored values; any payload that
omits them keeps the stored ones (the connector's items-only seed PUT).

ADR-0011 adds the same rule for media size hints: `_schema` field `hint` /
`surface` ride along with `_schema`, and an image service's `_hint` is kept
like `_formats`."""

from __future__ import annotations

import re

from .rich_text import FORMATS
from .segments import repeater_schema
from .theme import normalize_hex

VALID_REPEATER_TYPES = frozenset({"string", "inline", "richtext", "url", "tags", "image", "icon"})
_MEDIA_TYPES = frozenset({"image", "icon"})
HINT_MIN, HINT_MAX = 16, 8000
MAX_SURFACE_LENGTH = 40
MAX_ICON_NAME_LENGTH = 64
_ICON_MODES = ("tint", "original")
# Mirrors UNSAFE_SRC_RE in client-kit/rich-text/src/CmsIcon.tsx (src goes into a CSS mask url()).
# Image URLs use the same rule.
_ICON_UNSAFE_RE = re.compile(r"[\"'()\\\s]")


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
        hint, surface = field.get("hint"), field.get("surface")
        if (hint is not None or surface is not None) and field["type"] not in _MEDIA_TYPES:
            raise StructureError(
                f"_schema field '{field['key']}': hint and surface are only allowed on "
                "image and icon fields"
            )
        if hint is not None:
            _validate_hint(hint, f"_schema field '{field['key']}' hint")
        if surface is not None and (
            not isinstance(surface, str) or len(surface) > MAX_SURFACE_LENGTH
        ):
            raise StructureError(
                f"_schema field '{field['key']}' surface must be a string of at most "
                f"{MAX_SURFACE_LENGTH} characters"
            )


def _validate_hint(hint: object, where: str) -> None:
    if not isinstance(hint, dict) or set(hint) != {"width", "height"}:
        raise StructureError(f"{where} must be {{width, height}}")
    for dim in ("width", "height"):
        v = hint[dim]
        if not isinstance(v, int) or isinstance(v, bool) or not HINT_MIN <= v <= HINT_MAX:
            raise StructureError(f"{where}.{dim} must be an integer from {HINT_MIN} to {HINT_MAX}")


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
        if not is_admin or not has_incoming:
            if stored_schema is not None:
                return {**content, "_schema": stored_schema}
            return {k: v for k, v in content.items() if k != "_schema"}
        _validate_schema(incoming)
        return content
    if service_type == "image":
        stored_hint = _first(stored, "_hint", dict)
        incoming = content.get("_hint")
        if not is_admin or incoming is None:
            if stored_hint is not None:
                return {**content, "_hint": stored_hint}
            return {k: v for k, v in content.items() if k != "_hint"}
        _validate_hint(incoming, "_hint")
        return content
    if service_type == "key_value":
        # A present-but-empty `_formats` on the draft is authoritative (the last
        # formatted entry was switched to plain), so don't fall back to older blobs.
        stored_formats = None
        for blob in stored:
            if isinstance(blob, dict) and isinstance(blob.get("_formats"), dict):
                stored_formats = blob["_formats"]
                break
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


def _image_value(value: object, where: str) -> str:
    if value == "":
        return value
    if (
        not isinstance(value, str)
        or not value.startswith("https://")
        or _ICON_UNSAFE_RE.search(value)
    ):
        raise StructureError(f"{where} must be an https:// URL or empty")
    return value


def _icon_value(value: object, where: str) -> dict | None:
    # `""` (seeded by the pre-ADR-0011 dashboard) and any other non-object mean no icon.
    if not isinstance(value, dict):
        return None
    src = value.get("src", "")
    if src == "":
        return None
    if not isinstance(src, str) or not src.startswith("https://") or _ICON_UNSAFE_RE.search(src):
        raise StructureError(f"{where}.src must be an https:// URL")
    mode = value.get("mode")
    if mode not in _ICON_MODES:
        raise StructureError(f"{where}.mode must be tint or original")
    color = value.get("color", "")
    if color != "":
        color = normalize_hex(color)
        if color is None:
            raise StructureError(f"{where}.color must be a hex colour or empty")
    name = value.get("name", "")
    if not isinstance(name, str) or len(name) > MAX_ICON_NAME_LENGTH:
        raise StructureError(
            f"{where}.name must be a string of at most {MAX_ICON_NAME_LENGTH} characters"
        )
    return {"src": src, "mode": mode, "color": color, "name": name}


def normalize_media_fields(content: dict) -> dict:
    """Validate a repeater's `image` / `icon` item values (ADR-0011). Image
    values are `""` or an https URL; icons are null or {src, mode, color, name}
    with the colour lowercased, extra keys dropped and an empty src → null."""
    if not isinstance(content, dict):
        return content
    media = {k: t for k, t in repeater_schema(content).items() if t in _MEDIA_TYPES}
    items = content.get("items")
    if not media or not isinstance(items, list):
        return content
    out = []
    for idx, item in enumerate(items):
        if isinstance(item, dict):
            item = dict(item)
            for key, ftype in media.items():
                if key in item:
                    where = f"items[{idx}].{key}"
                    if ftype == "image":
                        item[key] = _image_value(item[key], where)
                    else:
                        item[key] = _icon_value(item[key], where)
        out.append(item)
    return {**content, "items": out}
