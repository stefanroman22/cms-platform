"""Mask ICU/interpolation placeholders (e.g. {year}, {count}) before machine
translation so the engine cannot translate or drop them, then restore them
verbatim afterward. Uses Unicode private-use sentinels that translators leave
untouched. Pure — no I/O."""

from __future__ import annotations

import re

# Matches flat placeholders only (no nested braces): {year}, {name}, {count}.
# ICU plural/select constructs with inner braces — {count, plural, one {x} other {y}} —
# are NOT fully masked (only their leaf nodes are). Don't pass ICU plural strings here
# until a recursive matcher is added; CMS content uses flat placeholders only.
_PLACEHOLDER = re.compile(r"\{[^{}]*\}")
_OPEN = ""
_CLOSE = ""


def protect(text: str) -> tuple[str, dict[str, str]]:
    """Replace each placeholder with a sentinel token. Repeated identical
    placeholders each get a distinct sentinel, preserving positional identity.
    Returns (masked_text, {sentinel: original_placeholder})."""
    tokens: dict[str, str] = {}

    def _sub(match: re.Match) -> str:
        sentinel = f"{_OPEN}{len(tokens)}{_CLOSE}"
        tokens[sentinel] = match.group(0)
        return sentinel

    return _PLACEHOLDER.sub(_sub, text), tokens


def restore(text: str, tokens: dict[str, str]) -> str:
    """Inverse of protect(): swap each sentinel back to its placeholder."""
    for sentinel, original in tokens.items():
        text = text.replace(sentinel, original)
    return text
