"""DeepL translation provider. Uses the Free API endpoint when the key ends in
':fx', else Pro. Masks ICU placeholders (protect/restore) and batches texts
into requests of at most 100 KiB. Network via stdlib urllib (consistent with
publish.py)."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

from .protect import protect, restore
from .provider import TextFormat

# Bare EN/PT are deprecated as DeepL *targets*; map to a regional variant.
_TARGET_OVERRIDE = {"en": "EN-GB", "pt": "PT-PT"}

# DeepL request-body budget: split masked texts into consecutive groups that each
# stay at or below this many bytes, so one giant rich-text leaf never blows up a
# single request. A single oversize text still forms its own (over-budget) group.
_MAX_REQUEST_BYTES = 100 * 1024


def _deepl_code(locale: str, *, is_target: bool) -> str:
    base = locale.split("-")[0].lower()
    if is_target and base in _TARGET_OVERRIDE:
        return _TARGET_OVERRIDE[base]
    return base.upper()


class DeepLProvider:
    name = "deepl"

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key if api_key is not None else os.environ.get("DEEPL_API_KEY", "")
        if not self.api_key:
            raise RuntimeError("DEEPL_API_KEY is not set")
        base = (
            "https://api-free.deepl.com"
            if self.api_key.endswith(":fx")
            else "https://api.deepl.com"
        )
        self.url = f"{base}/v2/translate"

    def translate(
        self, texts: list[str], *, source: str, target: str, fmt: TextFormat = "text"
    ) -> list[str]:
        if not texts:
            return []

        masked: list[str] = []
        token_maps: list[dict[str, str]] = []
        for text in texts:
            m, tokens = protect(text)
            masked.append(m)
            token_maps.append(tokens)

        translated: list[str] = []
        for group in _group_by_size(masked):
            translated.extend(self._post(group, source=source, target=target, fmt=fmt))
        return [restore(t, tokens) for t, tokens in zip(translated, token_maps, strict=True)]

    def _post(self, masked: list[str], *, source: str, target: str, fmt: TextFormat) -> list[str]:
        payload: dict[str, object] = {
            "text": masked,
            "target_lang": _deepl_code(target, is_target=True),
            "source_lang": _deepl_code(source, is_target=False),
        }
        if fmt == "html":
            payload["tag_handling"] = "html"

        req = urllib.request.Request(
            self.url,
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={
                "Authorization": f"DeepL-Auth-Key {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req) as resp:
                result = json.loads(resp.read().decode())
        except urllib.error.HTTPError as exc:
            body = exc.read().decode(errors="replace")
            raise RuntimeError(f"DeepL API error {exc.code}: {body}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"DeepL network error: {exc.reason}") from exc

        translations = [tr["text"] for tr in result.get("translations", [])]
        if len(translations) != len(masked):
            raise RuntimeError(
                f"DeepL returned {len(translations)} translations for {len(masked)} inputs"
            )
        return translations


def _group_by_size(texts: list[str]) -> list[list[str]]:
    """Split `texts` into consecutive groups whose JSON-encoded size stays at or
    below `_MAX_REQUEST_BYTES`. A single oversize text still forms its own group."""
    groups: list[list[str]] = []
    current: list[str] = []
    current_size = 0
    for text in texts:
        size = len(json.dumps(text, ensure_ascii=False).encode("utf-8")) + 1
        if current and current_size + size > _MAX_REQUEST_BYTES:
            groups.append(current)
            current = []
            current_size = 0
        current.append(text)
        current_size += size
    if current:
        groups.append(current)
    return groups
