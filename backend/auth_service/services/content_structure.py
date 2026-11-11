"""Structural metadata policy for CMS content (ADR-0010).

`_schema` (repeater field definitions) and `_formats` (key_value per-entry
formats) decide how fields are edited and rendered, so only admins/agents may
change them. A client save always keeps the stored values; any payload that
omits them keeps the stored ones (the connector's items-only seed PUT).

ADR-0011 adds the same rule for media size hints: `_schema` field `hint` /
`surface` ride along with `_schema`, and an image service's `_hint` is kept
like `_formats`.

ADR-0013 adds the option field types (`toggle`, `select`, `color`): their
`options` / `default` ride along with `_schema` the same way, and an `options`
service keeps its stored `_schema` like a repeater."""

from __future__ import annotations

import re

from .rich_text import FORMATS
from .segments import repeater_schema
from .slug import slugify
from .theme import normalize_hex

VALID_REPEATER_TYPES = frozenset(
    {
        "string",
        "inline",
        "richtext",
        "url",
        "tags",
        "slug",
        "image",
        "icon",
        "toggle",
        "select",
        "color",
    }
)
_MEDIA_TYPES = frozenset({"image", "icon"})
OPTION_TYPES = frozenset({"toggle", "select", "color"})
MIN_SELECT_OPTIONS, MAX_SELECT_OPTIONS = 2, 24
MAX_OPTION_LABEL_LENGTH = 80
_OPTION_VALUE_RE = re.compile(r"[a-z0-9][a-z0-9_-]{0,39}")
# An options service's `_schema` (ADR-0013).
MAX_OPTIONS_FIELDS = 40
MAX_OPTIONS_FIELD_LABEL_LENGTH = 120
_OPTIONS_KEY_RE = re.compile(r"[a-z0-9_]{1,40}")
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
        options, default = field.get("options"), field.get("default")
        if (options is not None or default is not None) and field["type"] not in OPTION_TYPES:
            raise StructureError(
                f"_schema field '{field['key']}': options and default are only allowed on "
                "toggle, select and color fields"
            )
        if field["type"] in OPTION_TYPES:
            _validate_option_field(field)


def _validate_option_field(field: dict) -> None:
    where = f"_schema field '{field['key']}'"
    ftype, options, default = field["type"], field.get("options"), field.get("default")
    if ftype == "select":
        if not isinstance(options, list) or not (
            MIN_SELECT_OPTIONS <= len(options) <= MAX_SELECT_OPTIONS
        ):
            raise StructureError(
                f"{where} options must be a list of {MIN_SELECT_OPTIONS} to "
                f"{MAX_SELECT_OPTIONS} {{value, label}} objects"
            )
        values: set[str] = set()
        for idx, opt in enumerate(options):
            if not isinstance(opt, dict) or set(opt) != {"value", "label"}:
                raise StructureError(f"{where} options[{idx}] must be {{value, label}}")
            value, label = opt["value"], opt["label"]
            if not isinstance(value, str) or not _OPTION_VALUE_RE.fullmatch(value):
                raise StructureError(
                    f"{where} options[{idx}].value must be 1 to 40 lowercase letters, digits, "
                    "'-' or '_', starting with a letter or digit"
                )
            if value in values:
                raise StructureError(f"{where} options[{idx}].value {value!r} is a duplicate")
            values.add(value)
            if not isinstance(label, str) or not 1 <= len(label) <= MAX_OPTION_LABEL_LENGTH:
                raise StructureError(
                    f"{where} options[{idx}].label must be a string of 1 to "
                    f"{MAX_OPTION_LABEL_LENGTH} characters"
                )
        if default is not None and (not isinstance(default, str) or default not in values):
            raise StructureError(f"{where} default must be one of the option values")
        return
    if options is not None:
        raise StructureError(f"{where}: options are only allowed on select fields")
    if ftype == "toggle":
        if default is not None and not isinstance(default, bool):
            raise StructureError(f"{where} default must be true or false")
    elif default is not None and default != "" and normalize_hex(default) is None:
        raise StructureError(f"{where} default must be a hex colour or empty")


def validate_options_schema(schema: object) -> None:
    """Validate an options service's `_schema` (ADR-0013): 1 to 40 option-type
    fields with unique `^[a-z0-9_]{1,40}$` keys and 1-to-120-character labels."""
    if not isinstance(schema, list) or not 1 <= len(schema) <= MAX_OPTIONS_FIELDS:
        raise StructureError(f"_schema must be a list of 1 to {MAX_OPTIONS_FIELDS} fields")
    keys: set[str] = set()
    for field in schema:
        if not isinstance(field, dict) or not isinstance(field.get("key"), str):
            raise StructureError("_schema entries need a string 'key'")
        key = field["key"]
        if not _OPTIONS_KEY_RE.fullmatch(key):
            raise StructureError(
                f"_schema field {key!r}: key must be 1 to 40 lowercase letters, digits or '_'"
            )
        if key in keys:
            raise StructureError(f"_schema field '{key}' is a duplicate key")
        keys.add(key)
        label = field.get("label")
        if not isinstance(label, str) or not 1 <= len(label) <= MAX_OPTIONS_FIELD_LABEL_LENGTH:
            raise StructureError(
                f"_schema field '{key}' label must be a string of 1 to "
                f"{MAX_OPTIONS_FIELD_LABEL_LENGTH} characters"
            )
        if field.get("type") not in OPTION_TYPES:
            raise StructureError(
                f"_schema field '{key}' has invalid type {field.get('type')!r}; "
                f"allowed: {', '.join(sorted(OPTION_TYPES))}"
            )
    _validate_schema(schema)


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
    if service_type in ("repeater", "options"):
        stored_schema = _first(stored, "_schema", list)
        incoming = content.get("_schema")
        has_incoming = isinstance(incoming, list) and bool(incoming)
        if not is_admin or not has_incoming:
            if stored_schema is not None:
                return {**content, "_schema": stored_schema}
            return {k: v for k, v in content.items() if k != "_schema"}
        if service_type == "options":
            validate_options_schema(incoming)
        else:
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


def normalize_slug_fields(content: dict) -> dict:
    """Store every repeater item's `slug` field value slugified (URL-safe in
    every locale); an empty value or null stays/becomes `""`, a number is kept
    as its text, and any other non-string is rejected."""
    if not isinstance(content, dict):
        return content
    slug_keys = [k for k, t in repeater_schema(content).items() if t == "slug"]
    items = content.get("items")
    if not slug_keys or not isinstance(items, list):
        return content
    out = []
    for idx, item in enumerate(items):
        if isinstance(item, dict):
            item = dict(item)
            for key in slug_keys:
                if key in item:
                    item[key] = _slug_value(item[key], f"items[{idx}].{key}")
        out.append(item)
    return {**content, "items": out}


def _slug_value(value: object, where: str) -> str:
    if value is None:
        return ""
    if isinstance(value, int | float) and not isinstance(value, bool):
        value = str(value)
    if not isinstance(value, str):
        raise StructureError(f"{where} must be a string")
    return slugify(value)


def _option_fields(schema: object) -> dict[str, dict]:
    """{key: field definition} of a `_schema`'s option-type fields; malformed
    entries are skipped."""
    if not isinstance(schema, list):
        return {}
    return {
        field["key"]: field
        for field in schema
        if isinstance(field, dict)
        and isinstance(field.get("key"), str)
        and field.get("type") in OPTION_TYPES
    }


def _option_value(field: dict, value: object, where: str) -> bool | str:
    """A toggle is a real bool; a select is `""` or one of its option values; a
    colour is `""` or a hex colour, stored as lowercase `#rrggbb`."""
    ftype = field["type"]
    if ftype == "toggle":
        if not isinstance(value, bool):
            raise StructureError(f"{where} must be true or false")
        return value
    if ftype == "select":
        options = field.get("options")
        options = options if isinstance(options, list) else []
        allowed = [opt.get("value") for opt in options if isinstance(opt, dict)]
        if value != "" and (not isinstance(value, str) or value not in allowed):
            raise StructureError(f"{where} must be one of the field's option values or empty")
        return value
    if value == "":
        return value
    color = normalize_hex(value)
    if color is None:
        raise StructureError(f"{where} must be a hex colour or empty")
    return color


def _option_default(field: dict) -> bool | str:
    """The field's `default`, else false / `""`. A stored default that is not
    valid (never written by a validated save) falls back the same way."""
    fallback = False if field["type"] == "toggle" else ""
    default = field.get("default")
    if default is None:
        return fallback
    try:
        return _option_value(field, default, "default")
    except StructureError:
        return fallback


def normalize_option_fields(content: dict) -> dict:
    """Validate a repeater's `toggle` / `select` / `color` item values
    (ADR-0013). A key an item lacks stays missing (the site uses its default)."""
    if not isinstance(content, dict):
        return content
    fields = _option_fields(content.get("_schema"))
    items = content.get("items")
    if not fields or not isinstance(items, list):
        return content
    out = []
    for idx, item in enumerate(items):
        if isinstance(item, dict):
            item = dict(item)
            for key, field in fields.items():
                if key in item:
                    item[key] = _option_value(field, item[key], f"items[{idx}].{key}")
        out.append(item)
    return {**content, "items": out}


def normalize_options(content: dict) -> dict:
    """Rebuild an options service's content (ADR-0013) as exactly
    `{_schema, values}`, with one value per schema key: a valid incoming value
    (normalised), else the field's default, else false / `""`. An invalid value
    is a StructureError; unknown keys are dropped. No `_schema` → `{values: {}}`."""
    if not isinstance(content, dict):
        return content
    schema = content.get("_schema")
    if not isinstance(schema, list) or not schema:
        return {"values": {}}
    incoming = content.get("values")
    if not isinstance(incoming, dict):
        incoming = {}
    values: dict[str, bool | str] = {}
    for key, field in _option_fields(schema).items():
        if key in incoming:
            values[key] = _option_value(field, incoming[key], f"values.{key}")
        else:
            values[key] = _option_default(field)
    return {"_schema": schema, "values": values}
