"""Translation provider registry."""

from __future__ import annotations

import os

from .deepl import DeepLProvider
from .null import NullProvider
from .provider import TranslationProvider

_PROVIDERS = {
    "null": NullProvider,
    "deepl": DeepLProvider,
}


def get_provider(name: str | None = None) -> TranslationProvider:
    """Return the configured provider. Resolution: explicit `name` →
    env TRANSLATION_PROVIDER → "null". Raises ValueError for an unknown name."""
    key = (name or os.environ.get("TRANSLATION_PROVIDER") or "null").lower()
    try:
        return _PROVIDERS[key]()
    except KeyError as exc:
        raise ValueError(f"Unknown translation provider: {key!r}") from exc


__all__ = ["TranslationProvider", "NullProvider", "DeepLProvider", "get_provider"]
