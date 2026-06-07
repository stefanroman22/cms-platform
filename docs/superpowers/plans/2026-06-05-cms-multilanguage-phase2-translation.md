# CMS Multi-Language — Phase 2 (Translation Engine + Auto-Translate) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make CMS content actually multilingual — author in the default locale, auto-translate into every other locale via DeepL on save, preserve manual per-locale overrides, and serve each locale (with per-leaf fallback to the default) over new public endpoints.

**Architecture:** Spec at [docs/superpowers/specs/2026-06-05-cms-multilanguage-design.md](../specs/2026-06-05-cms-multilanguage-design.md). This is **Phase 2 of 5**, built **on top of Phase 1** (branch `worktree-cms-multilanguage`). Phase 1 already shipped the per-locale schema, `segments_of()`+`src_hash()`, the `translation/` provider scaffold + `NullProvider`, `pick_locale_entry()`, locale-aware reads/writes, and per-locale-safe publish. Phase 2 adds: ICU-placeholder protection, the inverse `apply_segments()`, a `DeepLProvider`, a pure `sync_locale_draft()` translation step, the auto-translate/override logic inside `save_service`, and public per-locale read endpoints. No dashboard work yet (Phase 3) and no client wiring (Phase 4).

**Tech Stack:** Python 3.13 · FastAPI · supabase-py · DeepL Free API (`https://api-free.deepl.com/v2/translate`, key suffix `:fx`) via stdlib `urllib` (same as `publish.py`) · pytest with `mock_supabase`/`client`/`auth_as` fixtures.

---

## Conventions for this plan

- **Work location:** all Phase 2 work happens on branch **`worktree-cms-multilanguage`** in the worktree at **`.claude/worktrees/cms-multilanguage/`** (it has the Phase 1 code; `master`/`feat-*` do not). Commands below assume CWD is that worktree.
- **Run backend tests:** `cd backend && python -m pytest auth_service/tests/<file> -v` (venv active). Full suite: `make test-backend`.
- **Provider in tests:** leave `TRANSLATION_PROVIDER` unset → `NullProvider` (echoes source), so no test hits the network. `DeepLProvider` is unit-tested by mocking `urllib.request.urlopen`. Real DeepL is exercised only in the final gated smoke step.
- **Commits:** do NOT auto-commit (project convention). The `git commit` steps are prepared checkpoints — run them only when Stefan approves.
- **TDD:** failing test → see it fail → minimal implementation → see it pass.

## File structure (Phase 2)

**Create:**
- `backend/auth_service/translation/protect.py` — `protect()`/`restore()` ICU-placeholder masking (pure).
- `backend/auth_service/translation/deepl.py` — `DeepLProvider` (network; mocked in tests).
- `backend/auth_service/translation/sync.py` — `sync_locale_draft()` (pure; provider injected).
- `backend/auth_service/tests/test_translation_protect.py`
- `backend/auth_service/tests/test_deepl_provider.py`
- `backend/auth_service/tests/test_translation_sync.py`
- `backend/auth_service/tests/test_segments_apply.py`
- `backend/auth_service/tests/test_workspace_autotranslate.py`
- `backend/auth_service/tests/test_content_locale_endpoint.py`

**Modify:**
- `backend/auth_service/services/segments.py` — add `apply_segments()` (inverse) + `formats_of()`.
- `backend/auth_service/translation/__init__.py` — register `"deepl"` in `_PROVIDERS`.
- `backend/auth_service/routers/workspace.py` — `save_service` auto-translates on default edit and records overrides on non-default edit.
- `backend/auth_service/routers/content.py` — add `GET /content/{slug}/{locale}` and `/content/{slug}/{locale}/draft` with per-leaf default fallback; extract a shared content-map builder.

---

## Task 1: ICU placeholder protection (`protect.py`)

Machine translation must not mangle interpolation tokens like `{year}` or `{count}`. `protect()` masks them with private-use sentinels before translating; `restore()` puts them back.

**Files:**
- Create: `backend/auth_service/translation/protect.py`
- Test: `backend/auth_service/tests/test_translation_protect.py`

- [ ] **Step 1: Write the failing tests**

```python
# backend/auth_service/tests/test_translation_protect.py
from auth_service.translation.protect import protect, restore


def test_protect_masks_icu_placeholders():
    masked, tokens = protect("© {year} Acme. {count} items")
    assert "{year}" not in masked
    assert "{count}" not in masked
    assert len(tokens) == 2


def test_restore_is_exact_inverse():
    text = "Hello {name}, you have {count} messages"
    masked, tokens = protect(text)
    assert restore(masked, tokens) == text


def test_restore_after_surrounding_text_changes():
    # Simulate a translator that changed words around the (untouched) sentinels.
    masked, tokens = protect("© {year} Acme")
    # translator returns the sentinels intact but translates the rest
    translated = masked.replace("Acme", "Acme BV")
    out = restore(translated, tokens)
    assert "{year}" in out and "Acme BV" in out


def test_no_placeholders_is_passthrough():
    masked, tokens = protect("just text")
    assert masked == "just text"
    assert tokens == {}
    assert restore(masked, tokens) == "just text"
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd backend && python -m pytest auth_service/tests/test_translation_protect.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'auth_service.translation.protect'`.

- [ ] **Step 3: Implement `protect.py`**

```python
# backend/auth_service/translation/protect.py
"""Mask ICU/interpolation placeholders (e.g. {year}, {count}) before machine
translation so the engine cannot translate or drop them, then restore them
verbatim afterward. Uses Unicode private-use sentinels that translators leave
untouched. Pure — no I/O."""

from __future__ import annotations

import re

# Matches a single-brace placeholder with no nested braces: {year}, {count, plural, ...}
_PLACEHOLDER = re.compile(r"\{[^{}]*\}")
_OPEN = ""
_CLOSE = ""


def protect(text: str) -> tuple[str, dict[str, str]]:
    """Replace each placeholder with a sentinel token. Returns (masked_text,
    {sentinel: original_placeholder})."""
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
```

- [ ] **Step 4: Run to verify it passes**

Run: `cd backend && python -m pytest auth_service/tests/test_translation_protect.py -v`
Expected: PASS (4 passed).

- [ ] **Step 5: Commit**

```bash
git add backend/auth_service/translation/protect.py backend/auth_service/tests/test_translation_protect.py
git commit -m "feat(cms): ICU placeholder protect/restore for translation"
```

---

## Task 2: Inverse segment writer + format map (`segments.py`)

`segments_of()` flattens content → text. Phase 2 needs the inverse — write translated values back at their paths — plus a per-leaf format map (richtext = markdown) so the provider can be told what it's translating.

**Files:**
- Modify: `backend/auth_service/services/segments.py` (append two functions)
- Test: `backend/auth_service/tests/test_segments_apply.py`

- [ ] **Step 1: Write the failing tests**

```python
# backend/auth_service/tests/test_segments_apply.py
import copy

from auth_service.services.segments import apply_segments, formats_of, segments_of


def test_apply_round_trips_text_block():
    src = {"title": "Hi", "body": "Body"}
    out = apply_segments(copy.deepcopy(src), "text_block",
                         {"title": "Hallo", "body": "Tekst"})
    assert out == {"title": "Hallo", "body": "Tekst"}


def test_apply_key_value_by_path():
    src = {"entries": {"email": "a@b.com", "program": "Mon-Fri"}}
    out = apply_segments(copy.deepcopy(src), "key_value",
                         {"entries.program": "Ma-Vr"})
    assert out["entries"]["program"] == "Ma-Vr"
    assert out["entries"]["email"] == "a@b.com"  # untouched path preserved


def test_apply_repeater_by_item_id_and_tags():
    src = {
        "_schema": [{"key": "title", "type": "string"}, {"key": "tags", "type": "tags"}],
        "items": [{"_id": "x", "title": "Hosting", "tags": ["fast", "cheap"]}],
    }
    out = apply_segments(copy.deepcopy(src), "repeater", {
        "items.x.title": "Hosting NL",
        "items.x.tags.0": "snel",
    })
    assert out["items"][0]["title"] == "Hosting NL"
    assert out["items"][0]["tags"] == ["snel", "cheap"]  # only index 0 replaced


def test_apply_then_segments_is_identity_for_provided_paths():
    src = {"title": "A", "body": "B"}
    vals = {"title": "X", "body": "Y"}
    out = apply_segments(copy.deepcopy(src), "text_block", vals)
    assert segments_of("text_block", out) == vals


def test_formats_marks_richtext_as_markdown():
    fmts = formats_of("text_block", {"title": "T", "body": "B"})
    assert fmts == {"title": "text", "body": "markdown"}


def test_formats_repeater_richtext_field():
    content = {
        "_schema": [{"key": "name", "type": "string"}, {"key": "desc", "type": "richtext"}],
        "items": [{"_id": "x", "name": "N", "desc": "D"}],
    }
    fmts = formats_of("repeater", content)
    assert fmts["items.x.name"] == "text"
    assert fmts["items.x.desc"] == "markdown"
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd backend && python -m pytest auth_service/tests/test_segments_apply.py -v`
Expected: FAIL — `ImportError: cannot import name 'apply_segments'`.

- [ ] **Step 3: Append `apply_segments` + `formats_of` to `segments.py`**

Add to the end of `backend/auth_service/services/segments.py`:

```python
def apply_segments(content: dict, service_type: str, values: dict[str, str]) -> dict:
    """Write `values` (a {leaf_path: text} map, same paths as segments_of) back
    into `content` in place, then return it. Paths absent from `values` are left
    unchanged; non-translatable structure (URLs, numbers, _schema, item _ids) is
    never touched. Inverse of segments_of()."""
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
        schema = {
            field["key"]: field.get("type")
            for field in (content.get("_schema") or [])
            if isinstance(field, dict) and "key" in field
        }
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
                elif base in values:
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
        schema = {
            field["key"]: field.get("type")
            for field in (content.get("_schema") or [])
            if isinstance(field, dict) and "key" in field
        }
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
```

- [ ] **Step 4: Run to verify it passes**

Run: `cd backend && python -m pytest auth_service/tests/test_segments_apply.py auth_service/tests/test_segments.py -v`
Expected: PASS (Task 2's 6 tests + Phase 1's 9 still green).

- [ ] **Step 5: Commit**

```bash
git add backend/auth_service/services/segments.py backend/auth_service/tests/test_segments_apply.py
git commit -m "feat(cms): add apply_segments (inverse) + formats_of"
```

---

## Task 3: DeepL provider (`deepl.py`) + registry

**Files:**
- Create: `backend/auth_service/translation/deepl.py`
- Modify: `backend/auth_service/translation/__init__.py` (register `"deepl"`)
- Test: `backend/auth_service/tests/test_deepl_provider.py`

- [ ] **Step 1: Write the failing tests**

```python
# backend/auth_service/tests/test_deepl_provider.py
import json
from unittest.mock import MagicMock, patch

import pytest

from auth_service.translation import get_provider
from auth_service.translation.deepl import DeepLProvider


class _FakeResp:
    def __init__(self, payload):
        self._payload = json.dumps(payload).encode()

    def read(self):
        return self._payload

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def test_free_key_uses_free_endpoint():
    p = DeepLProvider(api_key="abc:fx")
    assert p.url.startswith("https://api-free.deepl.com")


def test_pro_key_uses_pro_endpoint():
    p = DeepLProvider(api_key="abc")
    assert p.url.startswith("https://api.deepl.com")


def test_missing_key_raises():
    with pytest.raises(RuntimeError):
        DeepLProvider(api_key="")


def test_translate_sends_batch_and_restores_placeholders():
    p = DeepLProvider(api_key="k:fx")
    captured = {}

    def _fake_urlopen(req):
        captured["body"] = json.loads(req.data.decode())
        # DeepL echoes the (masked) text with a word translated, sentinels intact
        return _FakeResp({"translations": [
            {"text": t.replace("Welcome", "Welkom")} for t in captured["body"]["text"]
        ]})

    with patch("auth_service.translation.deepl.urllib.request.urlopen", _fake_urlopen):
        out = p.translate(["Welcome © {year}"], source="en", target="nl", fmt="text")

    assert out == ["Welkom © {year}"]            # placeholder restored
    assert captured["body"]["target_lang"] == "NL"
    assert captured["body"]["source_lang"] == "EN"
    assert "{year}" not in captured["body"]["text"][0]  # masked on the wire


def test_translate_target_en_maps_to_en_gb():
    p = DeepLProvider(api_key="k:fx")
    with patch("auth_service.translation.deepl.urllib.request.urlopen",
               lambda req: _FakeResp({"translations": [{"text": "x"}]})):
        p.translate(["x"], source="nl", target="en", fmt="text")
    # No assertion error means it ran; explicit check below
    captured = {}

    def _cap(req):
        captured["b"] = json.loads(req.data.decode())
        return _FakeResp({"translations": [{"text": "x"}]})

    with patch("auth_service.translation.deepl.urllib.request.urlopen", _cap):
        p.translate(["x"], source="nl", target="en", fmt="text")
    assert captured["b"]["target_lang"] == "EN-GB"


def test_empty_input_returns_empty_without_network():
    p = DeepLProvider(api_key="k:fx")
    assert p.translate([], source="en", target="nl") == []


def test_registry_exposes_deepl():
    with patch.dict("os.environ", {"DEEPL_API_KEY": "k:fx"}):
        assert get_provider("deepl").name == "deepl"
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd backend && python -m pytest auth_service/tests/test_deepl_provider.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'auth_service.translation.deepl'`.

- [ ] **Step 3: Implement `deepl.py`**

```python
# backend/auth_service/translation/deepl.py
"""DeepL translation provider. Uses the Free API endpoint when the key ends in
':fx', else Pro. Masks ICU placeholders (protect/restore) and batches all texts
into one request. Network via stdlib urllib (consistent with publish.py)."""

from __future__ import annotations

import json
import os
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
        base = "https://api-free.deepl.com" if self.api_key.endswith(":fx") else "https://api.deepl.com"
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

        payload: dict = {
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
        with urllib.request.urlopen(req) as resp:
            result = json.loads(resp.read().decode())

        translations = [tr["text"] for tr in result.get("translations", [])]
        return [restore(t, tokens) for t, tokens in zip(translations, token_maps)]
```

- [ ] **Step 4: Register `"deepl"` in the registry**

In `backend/auth_service/translation/__init__.py`, replace the `_PROVIDERS` block:

```python
from .deepl import DeepLProvider
from .null import NullProvider
from .provider import TranslationProvider

_PROVIDERS = {
    "null": NullProvider,
    "deepl": DeepLProvider,
}
```

and add `"DeepLProvider"` to `__all__`:

```python
__all__ = ["TranslationProvider", "NullProvider", "DeepLProvider", "get_provider"]
```

- [ ] **Step 5: Run to verify it passes**

Run: `cd backend && python -m pytest auth_service/tests/test_deepl_provider.py auth_service/tests/test_translation_provider.py -v`
Expected: PASS (Task 3 tests + Phase 1's provider tests).

- [ ] **Step 6: Commit**

```bash
git add backend/auth_service/translation/deepl.py backend/auth_service/translation/__init__.py backend/auth_service/tests/test_deepl_provider.py
git commit -m "feat(cms): add DeepL translation provider (free/pro auto-detect)"
```

---

## Task 4: Pure translation step (`sync.py`)

`sync_locale_draft()` decides, for one service in one target locale, which leaves to re-translate (auto + source changed, or first-time) vs keep (manual override, or unchanged auto), calls the provider in fmt-grouped batches, and rebuilds the target draft mirroring the default's structure.

**Files:**
- Create: `backend/auth_service/translation/sync.py`
- Test: `backend/auth_service/tests/test_translation_sync.py`

- [ ] **Step 1: Write the failing tests**

```python
# backend/auth_service/tests/test_translation_sync.py
from auth_service.translation.null import NullProvider
from auth_service.translation.sync import sync_locale_draft


class _UpperProvider:
    """Fake engine: 'translates' by upper-casing, and counts calls/items."""
    name = "upper"

    def __init__(self):
        self.items = []

    def translate(self, texts, *, source, target, fmt="text"):
        self.items.extend(texts)
        return [t.upper() for t in texts]


def test_first_time_translates_all_auto_leaves():
    prov = _UpperProvider()
    content, meta = sync_locale_draft(
        "text_block",
        default_content={"title": "Hi", "body": "Yo"},
        prev_default_content={},
        target_content=None,
        target_meta={},
        provider=prov,
        source_locale="en", target_locale="nl",
    )
    assert content == {"title": "HI", "body": "YO"}
    assert meta == {}
    assert sorted(prov.items) == ["Hi", "Yo"]


def test_unchanged_auto_leaf_is_not_retranslated():
    prov = _UpperProvider()
    content, _ = sync_locale_draft(
        "text_block",
        default_content={"title": "Hi", "body": "NEW"},
        prev_default_content={"title": "Hi", "body": "OLD"},
        target_content={"title": "bestaande", "body": "OUD"},
        target_meta={},
        provider=prov,
        source_locale="en", target_locale="nl",
    )
    assert content["title"] == "bestaande"   # unchanged source → kept existing translation
    assert content["body"] == "NEW".upper()  # changed source → re-translated
    assert prov.items == ["NEW"]             # only the changed leaf hit the engine


def test_manual_override_is_preserved_and_not_translated():
    prov = _UpperProvider()
    content, meta = sync_locale_draft(
        "text_block",
        default_content={"title": "Hi", "body": "CHANGED"},
        prev_default_content={"title": "Hi", "body": "OLD"},
        target_content={"title": "T", "body": "mijn eigen tekst"},
        target_meta={"body": {"src_hash": "deadbeefdeadbeef"}},
        provider=prov,
        source_locale="en", target_locale="nl",
    )
    assert content["body"] == "mijn eigen tekst"     # manual kept despite source change
    assert "body" not in prov.items                  # engine never saw it
    assert meta == {"body": {"src_hash": "deadbeefdeadbeef"}}  # anchor preserved


def test_null_provider_mirrors_default_structure():
    content, _ = sync_locale_draft(
        "repeater",
        default_content={"_schema": [{"key": "t", "type": "string"}],
                         "items": [{"_id": "a", "t": "Hello"}]},
        prev_default_content={},
        target_content=None,
        target_meta={},
        provider=NullProvider(),
        source_locale="en", target_locale="nl",
    )
    assert content["items"][0]["_id"] == "a"      # structure preserved
    assert content["items"][0]["t"] == "Hello"    # NullProvider echoes
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd backend && python -m pytest auth_service/tests/test_translation_sync.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'auth_service.translation.sync'`.

- [ ] **Step 3: Implement `sync.py`**

```python
# backend/auth_service/translation/sync.py
"""Pure translation step for one service in one target locale.

Given the default-locale content (current + previous) and the target locale's
existing content + override metadata, decide per translatable leaf whether to
re-translate (auto + source changed, or never translated) or keep (manual
override, or unchanged auto), call the injected provider in fmt-grouped batches,
and rebuild the target draft mirroring the default's structure. No I/O."""

from __future__ import annotations

import copy

from ..services.segments import apply_segments, formats_of, segments_of
from .provider import TranslationProvider


def sync_locale_draft(
    service_type: str,
    default_content: dict,
    prev_default_content: dict | None,
    target_content: dict | None,
    target_meta: dict,
    provider: TranslationProvider,
    source_locale: str,
    target_locale: str,
) -> tuple[dict, dict]:
    """Return (new_target_draft, new_target_meta)."""
    src_segs = segments_of(service_type, default_content)
    prev_segs = segments_of(service_type, prev_default_content or {})
    tgt_segs = segments_of(service_type, target_content or {})
    fmts = formats_of(service_type, default_content)
    meta = target_meta or {}

    values: dict[str, str] = {}      # path -> final translated/kept text
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
    for fmt in ("text", "markdown", "html"):
        group = [p for p in to_translate if fmts.get(p, "text") == fmt]
        if not group:
            continue
        translated = provider.translate(
            [to_translate[p] for p in group],
            source=source_locale,
            target=target_locale,
            fmt=fmt,
        )
        for path, text in zip(group, translated):
            values[path] = text

    new_content = apply_segments(copy.deepcopy(default_content), service_type, values)
    return new_content, new_meta
```

- [ ] **Step 4: Run to verify it passes**

Run: `cd backend && python -m pytest auth_service/tests/test_translation_sync.py -v`
Expected: PASS (4 passed).

- [ ] **Step 5: Commit**

```bash
git add backend/auth_service/translation/sync.py backend/auth_service/tests/test_translation_sync.py
git commit -m "feat(cms): pure per-locale translation sync step"
```

---

## Task 5: Auto-translate + override capture in `save_service`

Wire the engine into saves: editing the default locale propagates to every other locale (re-translating changed/auto leaves, keeping manual ones); editing a non-default locale records the changed leaves as manual overrides anchored to the current source. Translation failures never fail the save.

**Files:**
- Modify: `backend/auth_service/routers/workspace.py` — imports + `save_service` (`:168-221`)
- Test: `backend/auth_service/tests/test_workspace_autotranslate.py`

- [ ] **Step 1: Write the failing tests**

```python
# backend/auth_service/tests/test_workspace_autotranslate.py
from unittest.mock import MagicMock


def _project(locales):
    return {
        "id": "project-demo", "slug": "demo", "name": "Demo",
        "default_locale": locales[0], "locales": locales,
        "github_repo": "https://github.com/test/demo",
        "repo_branch": "cms-preview", "production_branch": "master",
        "preview_url": "https://demo-dev.vercel.app", "production_url": "https://demo.vercel.app",
    }


def _patch_project(monkeypatch, locales):
    monkeypatch.setattr(
        "auth_service.routers.workspace.require_project_access",
        lambda slug, user: _project(locales),
    )


def _upserts(mock_supabase):
    return [c.args[0] for c in mock_supabase.upsert.call_args_list
            if isinstance(c.args[0], dict) and "project_service_id" in c.args[0]]


def test_editing_default_propagates_to_other_locales(
    mock_supabase, client, auth_as, client_user, monkeypatch
):
    auth_as(client_user)
    _patch_project(monkeypatch, ["en", "nl"])  # NullProvider (env unset) echoes
    mock_supabase.execute.side_effect = [
        # resolve service
        MagicMock(data={"id": "svc-1", "service_key": "hero", "label": "Hero",
                        "display_order": 1, "page_name": "General",
                        "service_type_slug": "text_block",
                        "service_types": {"name": "Text block", "icon": "Box", "schema": {}}}),
        # fetch existing rows for this service (none yet)
        MagicMock(data=[]),
        MagicMock(data=[{"id": "ce-en"}]),   # upsert en
        MagicMock(data=[{"id": "ce-nl"}]),   # upsert nl
        # get_service re-fetch
        MagicMock(data={"id": "svc-1", "service_key": "hero", "label": "Hero",
                        "display_order": 1, "page_name": "General",
                        "service_type_slug": "text_block",
                        "service_types": {"name": "Text block", "icon": "Box", "schema": {}},
                        "content_entries": [{"locale": "en", "draft_content": {"title": "Hi"},
                                             "published_content": None,
                                             "updated_at": "2026-06-05T10:00:00Z"}]}),
    ]

    res = client.put("/projects/demo/services/hero", json={"content": {"title": "Hi"}})
    assert res.status_code == 200

    ups = _upserts(mock_supabase)
    locales_written = {u["locale"] for u in ups}
    assert locales_written == {"en", "nl"}             # propagated to nl
    nl = next(u for u in ups if u["locale"] == "nl")
    assert nl["draft_content"] == {"title": "Hi"}      # NullProvider echo


def test_manual_override_survives_default_edit(
    mock_supabase, client, auth_as, client_user, monkeypatch
):
    auth_as(client_user)
    _patch_project(monkeypatch, ["en", "nl"])
    mock_supabase.execute.side_effect = [
        MagicMock(data={"id": "svc-1", "service_key": "hero", "label": "Hero",
                        "display_order": 1, "page_name": "General",
                        "service_type_slug": "text_block",
                        "service_types": {"name": "Text block", "icon": "Box", "schema": {}}}),
        # existing rows: en draft, nl with a MANUAL override on "title"
        MagicMock(data=[
            {"id": "ce-en", "locale": "en", "draft_content": {"title": "Old"},
             "published_content": None, "translation_meta": {}},
            {"id": "ce-nl", "locale": "nl", "draft_content": {"title": "mijn titel"},
             "published_content": None, "translation_meta": {"title": {"src_hash": "abc1230000000000"}}},
        ]),
        MagicMock(data=[{"id": "ce-en"}]),
        MagicMock(data=[{"id": "ce-nl"}]),
        MagicMock(data={"id": "svc-1", "service_key": "hero", "label": "Hero",
                        "display_order": 1, "page_name": "General",
                        "service_type_slug": "text_block",
                        "service_types": {"name": "Text block", "icon": "Box", "schema": {}},
                        "content_entries": [{"locale": "en", "draft_content": {"title": "New"},
                                             "published_content": None,
                                             "updated_at": "2026-06-05T10:00:00Z"}]}),
    ]

    res = client.put("/projects/demo/services/hero", json={"content": {"title": "New"}})
    assert res.status_code == 200

    nl = next(u for u in _upserts(mock_supabase) if u["locale"] == "nl")
    assert nl["draft_content"]["title"] == "mijn titel"        # override kept
    assert nl["translation_meta"] == {"title": {"src_hash": "abc1230000000000"}}


def test_editing_nondefault_locale_marks_changed_leaf_manual(
    mock_supabase, client, auth_as, client_user, monkeypatch
):
    auth_as(client_user)
    _patch_project(monkeypatch, ["en", "nl"])
    mock_supabase.execute.side_effect = [
        MagicMock(data={"id": "svc-1", "service_key": "hero", "label": "Hero",
                        "display_order": 1, "page_name": "General",
                        "service_type_slug": "text_block",
                        "service_types": {"name": "Text block", "icon": "Box", "schema": {}}}),
        # rows: en source + nl auto translation
        MagicMock(data=[
            {"id": "ce-en", "locale": "en", "draft_content": {"title": "Hi"},
             "published_content": None, "translation_meta": {}},
            {"id": "ce-nl", "locale": "nl", "draft_content": {"title": "Hoi"},
             "published_content": None, "translation_meta": {}},
        ]),
        MagicMock(data=[{"id": "ce-nl"}]),   # upsert nl
        MagicMock(data={"id": "svc-1", "service_key": "hero", "label": "Hero",
                        "display_order": 1, "page_name": "General",
                        "service_type_slug": "text_block",
                        "service_types": {"name": "Text block", "icon": "Box", "schema": {}},
                        "content_entries": [{"locale": "nl", "draft_content": {"title": "Hallo"},
                                             "published_content": None,
                                             "updated_at": "2026-06-05T10:00:00Z"}]}),
    ]

    res = client.put("/projects/demo/services/hero?locale=nl",
                     json={"content": {"title": "Hallo"}})  # user overrides nl title
    assert res.status_code == 200

    nl = next(u for u in _upserts(mock_supabase) if u["locale"] == "nl")
    assert "title" in nl["translation_meta"]               # marked manual
    assert "src_hash" in nl["translation_meta"]["title"]
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd backend && python -m pytest auth_service/tests/test_workspace_autotranslate.py -v`
Expected: FAIL — current `save_service` writes only the edited locale (no `nl` upsert; no `translation_meta`).

- [ ] **Step 3: Add imports to `workspace.py`**

After the existing `from ..services.content_locale import pick_locale_entry` line, add:

```python
from ..services.segments import segments_of, src_hash
from ..translation import get_provider
from ..translation.sync import sync_locale_draft
```

- [ ] **Step 4: Replace `save_service` (`workspace.py:168-221`)**

```python
@router.put("/projects/{project_slug}/services/{service_key}", response_model=ServiceDetailOut)
async def save_service(
    project_slug: str,
    service_key: str,
    body: ContentSaveRequest,
    request: Request,
    seed: bool = False,
    locale: str | None = None,
):
    user = await require_user(request)
    if seed and not user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="seed=true requires admin"
        )
    project = require_project_access(project_slug, user)
    default_locale = project.get("default_locale") or "en"
    locales = project.get("locales") or [default_locale]
    loc = locale or default_locale

    sb = get_supabase_admin()

    # Resolve the project_service (id + type)
    svc_result = (
        sb.table("project_services")
        .select(
            "id, service_key, label, display_order, page_name, service_type_slug, service_types(name, icon, schema)"
        )
        .eq("project_id", project["id"])
        .eq("service_key", service_key)
        .single()
        .execute()
    )
    if not svc_result.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Service not found")

    svc_id = svc_result.data["id"]
    service_type = svc_result.data["service_type_slug"]
    now = datetime.now(UTC).isoformat()

    # Load all existing per-locale rows for this service.
    rows = (
        sb.table("content_entries")
        .select("id, locale, draft_content, published_content, translation_meta")
        .eq("project_service_id", svc_id)
        .execute()
    )
    by_locale = {r["locale"]: r for r in (rows.data or [])}

    def _upsert(target_locale: str, content: dict, meta: dict | None) -> None:
        payload: dict = {
            "project_service_id": svc_id,
            "locale": target_locale,
            "draft_content": content,
            "updated_at": now,
            "updated_by": user.id,
        }
        if meta is not None:
            payload["translation_meta"] = meta
        if seed:
            payload["published_content"] = content
        sb.table("content_entries").upsert(
            payload, on_conflict="project_service_id,locale"
        ).execute()

    if loc == default_locale:
        prev_default = (by_locale.get(default_locale) or {}).get("draft_content") or {}
        _upsert(default_locale, body.content, None)
        # Propagate to every other locale. A translation failure for one locale
        # is logged and skipped — it never fails the default save.
        provider = get_provider()
        for target in locales:
            if target == default_locale:
                continue
            trow = by_locale.get(target) or {}
            try:
                new_content, new_meta = sync_locale_draft(
                    service_type,
                    body.content,
                    prev_default,
                    trow.get("draft_content"),
                    trow.get("translation_meta") or {},
                    provider,
                    default_locale,
                    target,
                )
                _upsert(target, new_content, new_meta)
            except Exception as exc:  # noqa: BLE001 — resilience: never fail the save
                logger.exception(
                    "auto-translate failed for %s/%s locale %s: %s",
                    project_slug, service_key, target, exc,
                )
    else:
        # Override edit on a non-default locale: any leaf whose value changed
        # versus the stored draft becomes a manual override, anchored to the
        # current default source hash.
        default_content = (by_locale.get(default_locale) or {}).get("draft_content") or {}
        prev_target = (by_locale.get(loc) or {}).get("draft_content") or {}
        prev_meta = dict((by_locale.get(loc) or {}).get("translation_meta") or {})
        new_segs = segments_of(service_type, body.content)
        prev_segs = segments_of(service_type, prev_target)
        src_segs = segments_of(service_type, default_content)
        for path, value in new_segs.items():
            if value != prev_segs.get(path):
                prev_meta[path] = {"src_hash": src_hash(src_segs.get(path, ""))}
        _upsert(loc, body.content, prev_meta)

    # Return fresh state for the edited locale
    return await get_service(project_slug, service_key, request, locale=loc)
```

- [ ] **Step 5: Run the new tests + the Phase 1 write tests**

Run: `cd backend && python -m pytest auth_service/tests/test_workspace_autotranslate.py auth_service/tests/test_workspace_save.py auth_service/tests/test_workspace_locale.py -v`
Expected: PASS. (Phase 1 `test_workspace_save.py` still passes: its faked project has no `locales`, so `locales == [default_locale]` and there is no propagation — the single default upsert is unchanged apart from gaining `translation_meta` only on the override branch, which those tests don't hit.)

- [ ] **Step 6: Commit**

```bash
git add backend/auth_service/routers/workspace.py backend/auth_service/tests/test_workspace_autotranslate.py
git commit -m "feat(cms): auto-translate on default save + override capture on locale save"
```

---

## Task 6: Public per-locale read endpoints

Add `GET /content/{slug}/{locale}` and `/content/{slug}/{locale}/draft`, each building content from the requested locale with **per-leaf fallback to the default locale** so a partially-translated site never renders blanks. Extract a shared builder to avoid duplicating the existing handlers.

**Files:**
- Modify: `backend/auth_service/routers/content.py` — imports, shared `_build_content_map`, refactor the two legacy handlers to use it, add the two new locale handlers (declared AFTER `/draft` and `/types` so those literals win route matching).
- Test: `backend/auth_service/tests/test_content_locale_endpoint.py`

- [ ] **Step 1: Write the failing tests**

```python
# backend/auth_service/tests/test_content_locale_endpoint.py
from unittest.mock import MagicMock


def _project():
    return {"id": "p1", "slug": "demo", "name": "Demo", "is_active": True,
            "default_locale": "en", "locales": ["en", "nl"], "preview_token": "tok"}


def _services_with_partial_nl():
    # hero is translated to nl; tagline only exists in en (nl must fall back)
    return [
        {"service_key": "hero", "label": "Hero", "display_order": 1,
         "service_type_slug": "text_block",
         "content_entries": [
             {"locale": "en", "published_content": {"title": "Hello", "body": "EN body"},
              "draft_content": None, "updated_at": "2026-06-05T10:00:00Z"},
             {"locale": "nl", "published_content": {"title": "Hallo", "body": "NL body"},
              "draft_content": None, "updated_at": "2026-06-05T10:00:00Z"},
         ]},
        {"service_key": "tagline", "label": "Tagline", "display_order": 2,
         "service_type_slug": "text_block",
         "content_entries": [
             {"locale": "en", "published_content": {"title": "Only EN"},
              "draft_content": None, "updated_at": "2026-06-05T10:00:00Z"},
         ]},
    ]


def test_locale_endpoint_returns_requested_locale(mock_supabase, client):
    mock_supabase.execute.side_effect = [
        MagicMock(data=_project()),
        MagicMock(data=_services_with_partial_nl()),
    ]
    res = client.get("/content/demo/nl")
    assert res.status_code == 200
    content = res.json()["content"]
    assert content["hero"]["title"] == "Hallo"          # nl translation
    assert content["tagline"]["title"] == "Only EN"     # per-leaf fallback to default


def test_locale_endpoint_rejects_unknown_locale(mock_supabase, client):
    mock_supabase.execute.return_value = MagicMock(data=_project())
    res = client.get("/content/demo/fr")  # fr not in project.locales
    assert res.status_code == 404


def test_legacy_endpoint_still_returns_default_locale(mock_supabase, client):
    mock_supabase.execute.side_effect = [
        MagicMock(data=_project()),
        MagicMock(data=_services_with_partial_nl()),
    ]
    res = client.get("/content/demo")
    assert res.status_code == 200
    assert res.json()["content"]["hero"]["title"] == "Hello"  # default = en


def test_locale_draft_requires_token(mock_supabase, client):
    mock_supabase.execute.return_value = MagicMock(data=_project())
    res = client.get("/content/demo/nl/draft")
    assert res.status_code == 401


def test_draft_literal_route_not_shadowed_by_locale(mock_supabase, client):
    # "/content/demo/draft" must hit the default-draft handler, not be read as locale="draft"
    mock_supabase.execute.return_value = MagicMock(data=_project())
    res = client.get("/content/demo/draft")  # no token
    assert res.status_code == 401  # draft handler's auth, not a 404 "unknown locale"
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd backend && python -m pytest auth_service/tests/test_content_locale_endpoint.py -v`
Expected: FAIL — `/content/demo/nl` 404s (no such route yet).

- [ ] **Step 3: Add the import + shared builder to `content.py`**

Add to the imports at the top (alongside `pick_locale_entry`):

```python
from ..services.segments import apply_segments, segments_of
```

Add this helper after `_normalise_published` (it builds one service's content for a locale, overlaying translated leaves on the default for per-leaf fallback):

```python
def _content_for_locale(svc: dict, locale: str, default_locale: str, *, draft: bool) -> tuple[dict | None, str | None]:
    """Return (content, updated_at) for one service in `locale`, or (None, None)
    to skip. Builds on the default-locale row and overlays the requested locale's
    translatable leaves so missing translations fall back to the default."""
    embedded = svc.get("content_entries")
    default_entry = pick_locale_entry(embedded, default_locale, default_locale)
    locale_entry = pick_locale_entry(embedded, locale, default_locale)

    def _raw(entry: dict | None) -> dict | None:
        if entry is None:
            return None
        if draft:
            d = entry.get("draft_content")
            return d if d is not None else entry.get("published_content")
        return entry.get("published_content")

    default_raw = _raw(default_entry)
    if default_raw is None:
        return None, None  # nothing published/drafted in the default → skip service

    service_type = svc["service_type_slug"]
    base = _normalise_published(service_type, default_raw)
    locale_raw = _raw(locale_entry) if locale_entry is not None else None
    if locale_raw is not None and locale_entry is not default_entry:
        overlay = segments_of(service_type, _normalise_published(service_type, locale_raw))
        base = apply_segments(json.loads(json.dumps(base)), service_type, overlay)

    updated_at = (locale_entry or default_entry or {}).get("updated_at")
    return base, updated_at


def _build_content_map(services: list, locale: str, default_locale: str, *, draft: bool):
    content_map: dict = {}
    last_updated: str | None = None
    for svc in services or []:
        if svc["service_type_slug"] in _PRIVATE_SERVICE_TYPES:
            continue
        content, updated_at = _content_for_locale(svc, locale, default_locale, draft=draft)
        if content is None:
            continue
        if updated_at and (last_updated is None or updated_at > last_updated):
            last_updated = updated_at
        content_map[svc["service_key"]] = {
            "_type": svc["service_type_slug"],
            "_label": svc.get("label") or svc["service_key"],
            **content,
        }
    return content_map, last_updated
```

- [ ] **Step 4: Add the two locale handlers to `content.py`**

Add these AFTER the existing `get_project_types` handler (so the literal `/{slug}/draft` and `/{slug}/types` routes are registered before `/{slug}/{locale}` and win matching):

```python
def _fetch_services(project_id: str):
    sb = get_supabase_admin()
    return (
        sb.table("project_services")
        .select(
            "service_key, label, display_order, service_type_slug, content_entries(locale, published_content, draft_content, updated_at)"
        )
        .eq("project_id", project_id)
        .order("display_order")
        .execute()
    )


@router.get("/{project_slug}/{locale}")
async def get_project_content_locale(project_slug: str, locale: str, request: Request):
    project = _resolve_project(project_slug)
    default_locale = project.get("default_locale") or "en"
    if locale not in (project.get("locales") or [default_locale]):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Locale not configured")

    services_result = _fetch_services(project["id"])
    content_map, last_updated = _build_content_map(
        services_result.data, locale, default_locale, draft=False
    )

    payload = {
        "project_slug": project["slug"],
        "project_name": project["name"],
        "locale": locale,
        "last_updated": last_updated,
        "content": content_map,
    }
    body_str = json.dumps(payload, sort_keys=True, default=str)
    etag = f'"{hashlib.sha256(body_str.encode()).hexdigest()[:16]}"'
    _cors, _cc = "Access-Control-Allow-Origin", "Cache-Control"
    if request.headers.get("If-None-Match") == etag:
        return Response(status_code=304, headers={_cc: "no-cache", "ETag": etag, _cors: "*"})
    headers = {_cc: "no-cache", "ETag": etag, _cors: "*"}
    if last_updated:
        headers["Last-Modified"] = last_updated
    return JSONResponse(content=payload, headers=headers)


@router.get("/{project_slug}/{locale}/draft")
async def get_project_draft_content_locale(project_slug: str, locale: str, request: Request):
    project = _resolve_project(project_slug)

    token_header = request.headers.get("X-CMS-Preview-Token")
    expected = project.get("preview_token")
    if not expected or not token_header or not hmac.compare_digest(token_header, expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or missing preview token"
        )

    default_locale = project.get("default_locale") or "en"
    if locale not in (project.get("locales") or [default_locale]):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Locale not configured")

    services_result = _fetch_services(project["id"])
    content_map, last_updated = _build_content_map(
        services_result.data, locale, default_locale, draft=True
    )

    payload = {
        "project_slug": project["slug"],
        "project_name": project["name"],
        "locale": locale,
        "last_updated": last_updated,
        "content": content_map,
    }
    return JSONResponse(
        content=payload,
        headers={"Cache-Control": "no-store", "Access-Control-Allow-Origin": "*"},
    )
```

> **Route-ordering note:** FastAPI matches routes in registration order. `get_project_draft_content` (`/{slug}/draft`) and `get_project_types` (`/{slug}/types`) are declared earlier in the file, so `/content/demo/draft` and `/content/demo/types` resolve to them, not to `/{slug}/{locale}`. The `test_draft_literal_route_not_shadowed_by_locale` test guards this. Do not move the new handlers above the literal ones.

- [ ] **Step 5: Run the new tests + the Phase 1 content tests**

Run: `cd backend && python -m pytest auth_service/tests/test_content_locale_endpoint.py auth_service/tests/test_content.py -v`
Expected: PASS (new endpoint tests + Phase 1's legacy-endpoint tests unchanged).

- [ ] **Step 6: Commit**

```bash
git add backend/auth_service/routers/content.py backend/auth_service/tests/test_content_locale_endpoint.py
git commit -m "feat(cms): public per-locale content endpoints with per-leaf default fallback"
```

---

## Task 7: Configuration + enablement

Translation is opt-in via env so existing single-locale projects are unaffected until configured.

**Files:** none (env/config only) — plus a doc note.

- [ ] **Step 1: Set backend env vars (Vercel `cms-backend-roman` + local `.env`)**

- `DEEPL_API_KEY` = a DeepL **Free** API key (ends in `:fx`).
- `TRANSLATION_PROVIDER` = `deepl`.

Per the project's Vercel split, these belong on the **backend** project (`cms-backend-roman`), not the frontend. With both unset, `get_provider()` returns `NullProvider` and saves simply echo the source into other locales (safe no-op behavior).

- [ ] **Step 2: Document the env vars**

Add a short "Multi-language / translation" subsection to `docs/DEVELOPMENT.md` (or the backend env section) listing `DEEPL_API_KEY` and `TRANSLATION_PROVIDER`, the free-tier cap (500k chars/month), and the `NullProvider` fallback behavior.

- [ ] **Step 3: Commit**

```bash
git add docs/DEVELOPMENT.md
git commit -m "docs(cms): document DeepL translation env vars"
```

---

## Final verification

- [ ] **Step 1: Run the entire backend suite**

Run: `make test-backend`
Expected: PASS — Phase 1 (233) + all Phase 2 tests, no regressions.

- [ ] **Step 2: Gated live DeepL smoke (requires a real key)**

With `DEEPL_API_KEY` exported, run a one-off from the worktree `backend/`:

```bash
python -c "from auth_service.translation import get_provider; print(get_provider('deepl').translate(['Welcome, © {year}'], source='en', target='nl', fmt='text'))"
```
Expected: a Dutch translation with `{year}` intact (e.g. `['Welkom, © {year}']`). Confirms key validity, endpoint selection, and placeholder protection end-to-end.

- [ ] **Step 3: Manual end-to-end on a 2-locale project (after Phase 1 is shipped)**

On a project with `locales = ['en','nl']`: save a `text_block` in `en` → confirm an `nl` `content_entries` row appears with translated draft; edit the `nl` value → confirm `translation_meta` records the override; edit the `en` source again → confirm the `nl` override is preserved (not overwritten). Publish → confirm `GET /content/{slug}/nl` serves the translated published content.

---

## Self-review (completed during authoring)

**Spec coverage (Phase 2 slice):** ✅ DeepL provider behind the pluggable interface → Task 3. ✅ ICU/markup protection → Task 1 (+ `fmt` grouping in Task 4). ✅ auto-translate on save, changed-only, manual preserved → Tasks 4–5. ✅ override capture + source-hash anchor (stale is derived at read time from `translation_meta` vs current `src_hash`) → Task 5. ✅ per-locale public endpoints with per-leaf default fallback → Task 6. ✅ provider config/enablement → Task 7. Per-locale **publish** flip already shipped in Phase 1 (publish-by-row-id). Deferred to Phase 3: dashboard locale switcher and the `translation_status` (auto/manual/needs-review) **read** surfacing for the editor UI — Phase 2 writes the `translation_meta` the dashboard will render.

**Placeholder scan:** ✅ no TBD/TODO; every code step is complete; every test step has real assertions; every run step states the expected outcome.

**Type/name consistency:** ✅ `segments_of`/`apply_segments`/`formats_of` share the identical leaf-path scheme (`items.<id>.<field>`, `entries.<k>`, `items.<id>.<tagfield>.<j>`). ✅ `TranslationProvider.translate(texts, *, source, target, fmt)` signature is the same in `provider.py`, `NullProvider`, `DeepLProvider`, and every call site (`sync_locale_draft`). ✅ `sync_locale_draft(service_type, default_content, prev_default_content, target_content, target_meta, provider, source_locale, target_locale)` arg order matches its call in `save_service`. ✅ `translation_meta` shape `{path: {"src_hash": ...}}` is written identically in `save_service` (override branch) and consumed in `sync_locale_draft` (manual branch). ✅ `get_provider()` reads env → returns `NullProvider` in tests (no network).
```
