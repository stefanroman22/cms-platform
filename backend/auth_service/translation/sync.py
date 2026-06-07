"""Pure translation step for one service in one target locale.

Given the default-locale content (current + previous) and the target locale's
existing content + override metadata, decide per translatable leaf whether to
re-translate (auto + source changed, or never translated) or keep (manual
override, or unchanged auto), call the injected provider in fmt-grouped batches,
and rebuild the target draft mirroring the default's structure. No I/O."""

from __future__ import annotations

import copy
from typing import get_args

from ..services.segments import apply_segments, formats_of, segments_of
from .provider import TextFormat, TranslationProvider

# The translation formats to batch by, derived from the provider's TextFormat.
_FORMATS = get_args(TextFormat)  # ("text", "markdown", "html")


def sync_locale_draft(
    service_type: str,
    default_content: dict,
    prev_default_content: dict | None,
    target_content: dict | None,
    target_meta: dict | None,
    provider: TranslationProvider,
    source_locale: str,
    target_locale: str,
) -> tuple[dict, dict]:
    """Return (new_target_draft, new_target_meta) for one service in one locale.

    Args:
        default_content: current default-locale content (source of truth for structure + text).
        prev_default_content: the previous default-locale content; used to detect which
            source leaves changed. Pass None or {} on the first sync (everything counts as new).
        target_content: the target locale's existing content, or None if not yet translated.
        target_meta: map of manually-overridden leaf paths -> {"src_hash": ...}; None/absent
            means every leaf is auto-managed.

    A leaf listed in target_meta is kept verbatim from target_content and never translated;
    if target_content lacks that leaf (a bootstrap case), the default-locale source text is
    used as a placeholder. Unchanged auto leaves keep their existing translation; changed or
    never-translated auto leaves are re-translated. The rebuilt draft mirrors default_content's
    structure (non-translatable fields are copied from the default)."""
    src_segs = segments_of(service_type, default_content)
    prev_segs = segments_of(service_type, prev_default_content or {})
    tgt_segs = segments_of(service_type, target_content or {})
    fmts = formats_of(service_type, default_content)
    meta = target_meta or {}

    values: dict[str, str] = {}  # path -> final translated/kept text
    to_translate: dict[str, str] = {}  # path -> source text needing the engine
    new_meta: dict[str, dict] = {}

    for path, source_text in src_segs.items():
        if path in meta:
            # Manual override — keep the target's value, keep its source anchor.
            values[path] = tgt_segs.get(path, source_text)
            new_meta[path] = meta[path]
            continue
        source_changed = source_text != prev_segs.get(path)
        if source_changed or path not in tgt_segs:
            to_translate[path] = source_text
        else:
            values[path] = tgt_segs[path]  # unchanged auto — keep existing translation

    # Batch by format so the engine is told what markup to preserve.
    for fmt in _FORMATS:
        group = [p for p in to_translate if fmts.get(p, "text") == fmt]
        if not group:
            continue
        translated = provider.translate(
            [to_translate[p] for p in group],
            source=source_locale,
            target=target_locale,
            fmt=fmt,
        )
        for path, text in zip(group, translated, strict=True):
            values[path] = text

    new_content = apply_segments(copy.deepcopy(default_content), service_type, values)
    return new_content, new_meta
