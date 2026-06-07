"""Provider interface for machine translation. Implementations preserve ICU
placeholders (e.g. {year}) and any markup indicated by `fmt`, and return a list
whose order matches the input."""

from __future__ import annotations

from typing import Literal, Protocol, runtime_checkable

TextFormat = Literal["text", "markdown", "html"]


@runtime_checkable
class TranslationProvider(Protocol):
    name: str

    def translate(
        self, texts: list[str], *, source: str, target: str, fmt: TextFormat = "text"
    ) -> list[str]: ...
