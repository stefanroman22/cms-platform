"""No-op provider: echoes source text unchanged. Used for manual-only projects
and as the safe default before a real engine (DeepL, added in Phase 2) is
configured — lets the whole pipeline run with no external dependency."""

from __future__ import annotations

from .provider import TextFormat


class NullProvider:
    name = "null"

    def translate(
        self, texts: list[str], *, source: str, target: str, fmt: TextFormat = "text"
    ) -> list[str]:
        return list(texts)
