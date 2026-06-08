"""DeepL translation provider. Uses the Free API endpoint when the key ends in
':fx', else Pro. Masks ICU placeholders (protect/restore) and batches all texts
into one request. Network via stdlib urllib (consistent with publish.py)."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

from .protect import protect, restore
from .provider import TextFormat

# Bare EN/PT are deprecated as DeepL *targets*; map to a regional variant.
_TARGET_OVERRIDE = {"en": "EN-GB", "pt": "PT-PT"}


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

        payload: dict[str, object] = {
            "text": masked,
            "target_lang": _deepl_code(target, is_target=True),
            "source_lang": _deepl_code(source, is_target=False),
        }
        if fmt == "html":
            payload["tag_handling"] = "html"

        req = urllib.request.Request(
            self.url,
            data=json.dumps(payload).encode(),
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
        if len(translations) != len(texts):
            raise RuntimeError(
                f"DeepL returned {len(translations)} translations for {len(texts)} inputs"
            )
        return [restore(t, tokens) for t, tokens in zip(translations, token_maps, strict=False)]
