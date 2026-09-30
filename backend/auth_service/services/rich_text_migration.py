"""One-time rich-text migration planner (spec §8). Pure: rows in → updates / SQL out.

The CLI (backend/scripts/migrate_rich_text.py) loads rows, prints the plan and
writes ONE atomic DO block (every row update guarded by its updated_at, plus the
version flip). Atomicity matters: re-converting an already-migrated inline value
would double-escape it, so a project is never left half-migrated."""

from __future__ import annotations

import copy
import json
import re
import secrets
from dataclasses import dataclass, field

from .rich_text import FORMATS, normalize_content
from .segments import repeater_schema, segments_of, src_hash

REPEATER_TYPES = frozenset({"string", "inline", "richtext", "url", "tags"})
_UUID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
_TS_RE = re.compile(r"^[0-9T:\-+.Z ]{10,40}$")


@dataclass
class MigrationConfig:
    repeaters: dict[str, dict[str, str]] = field(default_factory=dict)
    key_values: dict[str, dict[str, str]] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, raw: dict) -> MigrationConfig:
        cfg = cls(dict(raw.get("repeaters") or {}), dict(raw.get("key_values") or {}))
        for svc, fields in cfg.repeaters.items():
            for key, typ in fields.items():
                if typ not in REPEATER_TYPES:
                    raise ValueError(f"repeaters.{svc}.{key}: invalid type {typ!r}")
        for svc, entries in cfg.key_values.items():
            for key, fmt in entries.items():
                if fmt not in FORMATS:
                    raise ValueError(f"key_values.{svc}.{key}: invalid format {fmt!r}")
        return cfg


@dataclass
class RowUpdate:
    row_id: str
    service_key: str
    locale: str
    updated_at: str | None
    draft_content: dict | None
    published_content: dict | None
    translation_meta: dict | None
    diffs: list[tuple[str, str, str]] = field(default_factory=list)


def unknown_config_refs(services: list[dict], cfg: MigrationConfig) -> list[str]:
    by_key = {s["service_key"]: s for s in services}
    problems: list[str] = []
    for svc, fields in cfg.repeaters.items():
        s = by_key.get(svc)
        if not s or s["service_type_slug"] != "repeater":
            problems.append(f"repeaters.{svc}: no such repeater service")
            continue
        known: set[str] = set()
        for row in s.get("content_entries") or []:
            for blob in (row.get("draft_content"), row.get("published_content")):
                known |= set(repeater_schema(blob or {}).keys())
        problems += [f"repeaters.{svc}.{k}: no such field" for k in fields if k not in known]
    for svc, entries in cfg.key_values.items():
        s = by_key.get(svc)
        if not s or s["service_type_slug"] != "key_value":
            problems.append(f"key_values.{svc}: no such key_value service")
            continue
        known = set()
        for row in s.get("content_entries") or []:
            for blob in (row.get("draft_content"), row.get("published_content")):
                known |= set(_entries_dict((blob or {}).get("entries")).keys())
        problems += [f"key_values.{svc}.{k}: no such entry" for k in entries if k not in known]
    return problems


def _entries_dict(entries: object) -> dict:
    """Mirror of routers/content.py::_normalise_published's key_value flattening."""
    if isinstance(entries, dict):
        return entries
    if isinstance(entries, list):
        flattened: dict = {}
        for item in entries:
            if not isinstance(item, dict):
                continue
            key = item.get("key")
            if not isinstance(key, str) or not key.strip():
                continue
            flattened[key.strip()] = item.get("value")
        return flattened
    return {}


def _restructure(stype: str, key: str, content: object, cfg: MigrationConfig) -> object:
    if not isinstance(content, dict):
        return content
    c = copy.deepcopy(content)
    if stype == "repeater" and key in cfg.repeaters and isinstance(c.get("_schema"), list):
        types = cfg.repeaters[key]
        c["_schema"] = [
            {**f, "type": types.get(f.get("key"), f.get("type"))} if isinstance(f, dict) else f
            for f in c["_schema"]
        ]
    if stype == "key_value":
        if key in cfg.key_values:
            if "entries" in c:
                c["entries"] = _entries_dict(c["entries"])
            c["_formats"] = {**(c.get("_formats") or {}), **cfg.key_values[key]}
    return c


def _convert(stype: str, key: str, content: object, cfg: MigrationConfig) -> object:
    c = _restructure(stype, key, content, cfg)
    if not isinstance(c, dict) or not c:
        return c
    return normalize_content(stype, c, legacy=True, enforce_limit=False)


def _rehash(stype: str, meta: dict, old_default: dict, new_default: dict) -> dict:
    old_src = segments_of(stype, old_default)
    new_src = segments_of(stype, new_default)
    out: dict = {}
    for path, anchor in (meta or {}).items():
        if (
            isinstance(anchor, dict)
            and anchor.get("src_hash") == src_hash(old_src.get(path, ""))
            and path in new_src
        ):
            out[path] = {**anchor, "src_hash": src_hash(new_src[path])}
        else:
            out[path] = anchor  # already stale (or orphaned) stays that way
    return out


def _diffs(stype: str, before: object, after: object) -> list[tuple[str, str, str]]:
    b = segments_of(stype, before if isinstance(before, dict) else {})
    a = segments_of(stype, after if isinstance(after, dict) else {})
    out = [(p, b.get(p, ""), a.get(p, "")) for p in sorted(set(a) | set(b)) if a.get(p) != b.get(p)]
    for meta_key in ("_schema", "_formats"):
        bv = before.get(meta_key) if isinstance(before, dict) else None
        av = after.get(meta_key) if isinstance(after, dict) else None
        if bv != av:
            out.append(
                (meta_key, json.dumps(bv, ensure_ascii=False), json.dumps(av, ensure_ascii=False))
            )
    return out


def plan_project_migration(
    services: list[dict], cfg: MigrationConfig, default_locale: str
) -> list[RowUpdate]:
    updates: list[RowUpdate] = []
    for svc in services:
        stype, key = svc["service_type_slug"], svc["service_key"]
        rows = svc.get("content_entries") or []
        drow = next((r for r in rows if r["locale"] == default_locale), {}) or {}
        d_old = drow.get("draft_content")
        if d_old is None:
            d_old = drow.get("published_content") or {}
        d_new = _convert(stype, key, d_old, cfg)
        for row in rows:
            old_draft, old_pub = row.get("draft_content"), row.get("published_content")
            new_draft = _convert(stype, key, old_draft, cfg) if old_draft is not None else None
            new_pub = _convert(stype, key, old_pub, cfg) if old_pub is not None else None
            meta = row.get("translation_meta") or {}
            new_meta = (
                meta if row["locale"] == default_locale else _rehash(stype, meta, d_old, d_new)
            )
            if new_draft == old_draft and new_pub == old_pub and new_meta == meta:
                continue
            updates.append(
                RowUpdate(
                    row_id=row["id"],
                    service_key=key,
                    locale=row["locale"],
                    updated_at=row.get("updated_at"),
                    draft_content=new_draft if new_draft != old_draft else None,
                    published_content=new_pub if new_pub != old_pub else None,
                    translation_meta=new_meta if new_meta != meta else None,
                    diffs=_diffs(
                        stype,
                        old_draft if old_draft is not None else old_pub,
                        new_draft if new_draft is not None else new_pub,
                    ),
                )
            )
    return updates


def _check_id(value: str) -> str:
    if not isinstance(value, str) or not _UUID_RE.match(value):
        raise ValueError(f"refusing to interpolate non-uuid id {value!r}")
    return value


def _lit(obj: object, tag: str) -> str:
    if obj is None:
        return "null"
    s = json.dumps(obj, ensure_ascii=False)
    if f"${tag}$" in s or f"$mig_{tag}$" in s or f"$rst_{tag}$" in s:
        raise ValueError("dollar-quote collision; re-run")
    return f"${tag}${s}${tag}$::jsonb"


def migration_sql(project_id: str, updates: list[RowUpdate]) -> str:
    pid = _check_id(project_id)
    tag = "j" + secrets.token_hex(6)
    lines = [
        f"do $mig_{tag}$",
        "begin",
        f"  if exists (select 1 from projects where id = '{pid}' and rich_text_version <> 0) then",
        "    raise exception 'rich-text migration: project is not at version 0';",
        "  end if;",
    ]
    for u in updates:
        rid = _check_id(u.row_id)
        sets = ["updated_at = now()"]
        if u.draft_content is not None:
            sets.append(f"draft_content = {_lit(u.draft_content, tag)}")
        if u.published_content is not None:
            sets.append(f"published_content = {_lit(u.published_content, tag)}")
        if u.translation_meta is not None:
            sets.append(f"translation_meta = {_lit(u.translation_meta, tag)}")
        if u.updated_at is None:
            guard = "updated_at is null"
        else:
            if not _TS_RE.match(u.updated_at):
                raise ValueError(f"bad updated_at {u.updated_at!r}")
            guard = f"updated_at = '{u.updated_at}'::timestamptz"
        lines.append(
            f"  update content_entries set {', '.join(sets)} where id = '{rid}' and {guard};"
        )
        lines.append(
            f"  if not found then raise exception 'rich-text migration conflict on row {rid} "
            f"(edited since planning) — re-plan and apply again'; end if;"
        )
    lines += [
        f"  update projects set rich_text_version = 1, updated_at = now() where id = '{pid}';",
        "  if not found then raise exception 'rich-text migration: project not found'; end if;",
        "end",
        f"$mig_{tag}$;",
    ]
    return "\n".join(lines) + "\n"


def restore_sql(project_id: str, rows: list[dict]) -> str:
    pid = _check_id(project_id)
    tag = "j" + secrets.token_hex(6)
    lines = [f"do $rst_{tag}$", "begin"]
    for r in rows:
        rid = _check_id(r["id"])
        lines.append(
            f"  update content_entries set draft_content = {_lit(r.get('draft_content'), tag)}, "
            f"published_content = {_lit(r.get('published_content'), tag)}, "
            f"translation_meta = {_lit(r.get('translation_meta') or {}, tag)}, updated_at = now() "
            f"where id = '{rid}';"
        )
        lines.append(
            f"  if not found then raise exception 'rich-text restore: row {rid} not found'; end if;"
        )
    lines += [
        f"  update projects set rich_text_version = 0, updated_at = now() where id = '{pid}';",
        "  if not found then raise exception 'rich-text restore: project not found'; end if;",
        "end",
        f"$rst_{tag}$;",
    ]
    return "\n".join(lines) + "\n"
