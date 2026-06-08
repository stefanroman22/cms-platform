"""Translatable-segment model for CMS content.

Flattens a service's content blob into a flat map of {leaf_path: text} for the
leaves that are human-readable and worth translating, driven by service type and
(for repeaters) the per-item field schema. URLs, emails, numbers and image
sources are never translated.

Used by the multilingual pipeline to (a) auto-translate the default locale into
others and (b) track which leaves a client manually overrode. Pure — no I/O.
"""

from __future__ import annotations

import hashlib

# Repeater field types whose values are translatable text.
_TRANSLATABLE_FIELD_TYPES = {"string", "richtext", "tags"}


def _repeater_schema(content: dict) -> dict[str, str | None]:
    """Map of {field key: field type} from a repeater content blob's _schema."""
    return {
        field["key"]: field.get("type")
        for field in (content.get("_schema") or [])
        if isinstance(field, dict) and "key" in field
    }


def src_hash(text: str) -> str:
    """Stable 16-hex-char fingerprint of a source string, used to detect when a
    default-locale source changed since a translation/override was anchored."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def segments_of(service_type: str, content: dict) -> dict[str, str]:
    """Return {leaf_path: text} for the translatable leaves of one service.

    Leaf paths are dot-delimited and stable: e.g. "title", "entries.email",
    "items.<id>.short_description", "items.<id>.features.0". Repeater items are
    keyed by their stable "_id" when present, else by positional index.
    """
    if not isinstance(content, dict):
        return {}

    out: dict[str, str] = {}

    if service_type == "text_block":
        for key in ("title", "body"):
            val = content.get(key)
            if isinstance(val, str) and val:
                out[key] = val

    elif service_type in ("image", "floor_plan"):
        val = content.get("alt")
        if isinstance(val, str) and val:
            out["alt"] = val

    elif service_type == "file_download":
        val = content.get("filename")
        if isinstance(val, str) and val:
            out["filename"] = val

    elif service_type == "key_value":
        entries = content.get("entries")
        if isinstance(entries, dict):
            for key, val in entries.items():
                if isinstance(val, str) and val:
                    out[f"entries.{key}"] = val

    elif service_type == "repeater":
        schema = _repeater_schema(content)
        for idx, item in enumerate(content.get("items") or []):
            if not isinstance(item, dict):
                continue
            item_id = item.get("_id") or str(idx)
            for key, ftype in schema.items():
                if ftype not in _TRANSLATABLE_FIELD_TYPES:
                    continue
                val = item.get(key)
                if ftype == "tags" and isinstance(val, list):
                    for j, tag in enumerate(val):
                        if isinstance(tag, str) and tag:
                            out[f"items.{item_id}.{key}.{j}"] = tag
                elif isinstance(val, str) and val:
                    out[f"items.{item_id}.{key}"] = val

    # gallery (URLs), video (URLs), email_config (private): no translatable text.
    return out


def apply_segments(content: dict, service_type: str, values: dict[str, str]) -> dict:
    """Write `values` (a {leaf_path: text} map, same paths as segments_of) back
    into `content` in place, then return it. Paths absent from `values` are left
    unchanged; non-translatable structure (URLs, numbers, _schema, item _ids) is
    never touched. Paths present in `values` but absent from `content` (including
    out-of-range tag indices) are silently ignored. Inverse of segments_of()."""
    if not isinstance(content, dict):
        return content

    if service_type == "text_block":
        for key in ("title", "body"):
            if key in values:
                content[key] = values[key]

    elif service_type in ("image", "floor_plan"):
        if "alt" in values:
            content["alt"] = values["alt"]

    elif service_type == "file_download":
        if "filename" in values:
            content["filename"] = values["filename"]

    elif service_type == "key_value":
        entries = content.get("entries")
        if isinstance(entries, dict):
            for key in list(entries.keys()):
                path = f"entries.{key}"
                if path in values:
                    entries[key] = values[path]

    elif service_type == "repeater":
        schema = _repeater_schema(content)
        for idx, item in enumerate(content.get("items") or []):
            if not isinstance(item, dict):
                continue
            item_id = item.get("_id") or str(idx)
            for key, ftype in schema.items():
                if ftype not in _TRANSLATABLE_FIELD_TYPES:
                    continue
                base = f"items.{item_id}.{key}"
                val = item.get(key)
                if ftype == "tags" and isinstance(val, list):
                    for j in range(len(val)):
                        path = f"{base}.{j}"
                        if path in values:
                            val[j] = values[path]
                elif base in values and key in item:  # only overwrite, never insert
                    item[key] = values[base]

    return content


def formats_of(service_type: str, content: dict) -> dict[str, str]:
    """Return {leaf_path: fmt} mirroring segments_of's paths, where fmt is
    'markdown' for richtext leaves (text_block.body, repeater richtext fields)
    and 'text' otherwise. Lets the translator know what markup to preserve."""
    fmts: dict[str, str] = {}
    if not isinstance(content, dict):
        return fmts

    if service_type == "text_block":
        if isinstance(content.get("title"), str) and content["title"]:
            fmts["title"] = "text"
        if isinstance(content.get("body"), str) and content["body"]:
            fmts["body"] = "markdown"

    elif service_type in ("image", "floor_plan"):
        if isinstance(content.get("alt"), str) and content["alt"]:
            fmts["alt"] = "text"

    elif service_type == "file_download":
        if isinstance(content.get("filename"), str) and content["filename"]:
            fmts["filename"] = "text"

    elif service_type == "key_value":
        entries = content.get("entries")
        if isinstance(entries, dict):
            for key, val in entries.items():
                if isinstance(val, str) and val:
                    fmts[f"entries.{key}"] = "text"

    elif service_type == "repeater":
        schema = _repeater_schema(content)
        for idx, item in enumerate(content.get("items") or []):
            if not isinstance(item, dict):
                continue
            item_id = item.get("_id") or str(idx)
            for key, ftype in schema.items():
                if ftype not in _TRANSLATABLE_FIELD_TYPES:
                    continue
                base = f"items.{item_id}.{key}"
                val = item.get(key)
                if ftype == "tags" and isinstance(val, list):
                    for j, tag in enumerate(val):
                        if isinstance(tag, str) and tag:
                            fmts[f"{base}.{j}"] = "text"
                elif isinstance(val, str) and val:
                    fmts[base] = "markdown" if ftype == "richtext" else "text"

    return fmts
