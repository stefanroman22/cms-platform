# CMS Rich Text Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Every prose field in the CMS gets a rich-text editor (bold, italic, underline, strike, links, lists, headings, quotes, dividers, line breaks, blank lines — no colours). Each client site renders it through a vendored kit and themes formatting with CSS variables. Rolled out safely to all four live sites and baked into the agents that build future sites.

**Architecture:** Values of `inline`/`rich` fields are stored as canonical, allow-listed HTML produced only by the backend (`services/rich_text.py`). A per-project gate `projects.rich_text_version` (0 = legacy, 1 = rich) keeps every live site on today's behaviour until its site ships the kit and its data is migrated atomically. A zero-dependency TypeScript client kit (`client-kit/rich-text/`) ports the same parser and canonical transform, pinned to the backend by two shared JSON fixture files. The kit renders React elements (never `innerHTML`) and exposes a `--cms-rich-*` CSS-variable theme contract.

**Tech Stack:** FastAPI + Python 3.13 (`html.parser`, pytest), Supabase Postgres, Next.js 16 dashboard with TipTap v3 + vitest, a React ≥18 client kit (vitest + jsdom), and four client sites (two Next 16, two Vite).

**Spec:** `docs/superpowers/specs/2026-09-27-cms-rich-text-design.md` — read it before any task. Its §4 (content model), §4.4 (the double-escaping rule) and §7 (kit) are normative.

## Global Constraints

- Repo root: `c:\Users\stefa\.gemini\antigravity\scratch\CMS - websites`. Work on branch `feat/rich-text` (already created from `origin/dev`). Never push to `main` of the CMS repo; production changes only via the "Promote dev → main" workflow.
- Commit messages are one plain line. **Never add `Co-Authored-By` or any AI attribution** (user rule; overrides any harness guidance). Never use `git commit --no-verify`.
- One Supabase DB (`xeluydwpgiddbamysgyu`) serves every environment. Backend tests that reach Supabase must use the `mock_supabase` fixture. Tests never call DeepL (conftest forces `TRANSLATION_PROVIDER=null`).
- Never edit an applied migration file; add a new one.
- Dashboard animation imports come from `motion/react`, never `framer-motion` (lint-enforced).
- Formats: `plain` | `inline` | `rich`. Inline tags: `strong em u s a br`. Rich tags: inline plus `p ul ol li h2 h3 h4 blockquote hr`. The only attribute is `a[href]`.
- Allowed hrefs: `http://`, `https://`, `mailto:`, `tel:`, `#…`, `/…` (not `//…`, not `/\…`), max 2 048 chars, after removing ASCII control chars.
- Limits (serialized canonical HTML length): inline 2 000, rich 50 000. Rejected saves return 422 with detail `Field <path> is too long (<n> > <limit> characters)`.
- **Double-escaping rule:** `inline` values are always parsed as HTML fragments (save path, dashboard, kit). Legacy inline conversion (escape + `\n`→`<br>`) happens only in the one-time migration of a version-0 project. `rich` values without any tag are legacy and are converted (Markdown-lite).
- Repeater field types: `string`(plain) · `inline` · `richtext`(rich) · `url`(plain, untranslated) · `tags`(plain). Key-value per-entry formats live in `content._formats`, default `plain`.
- `_schema` (repeater) and `_formats` (key_value) are structural: non-admin saves always keep the stored values; admin saves may change them, and an admin payload that omits them keeps the stored ones.
- Theme variables (the site contract): `--cms-rich-strong`, `--cms-rich-strong-weight`, `--cms-rich-em`, `--cms-rich-underline`, `--cms-rich-link`, `--cms-rich-link-hover`, `--cms-rich-link-decoration`, `--cms-rich-heading`, `--cms-rich-heading-font`, `--cms-rich-heading-weight`, `--cms-rich-marker`, `--cms-rich-quote-border`, `--cms-rich-quote-text`, `--cms-rich-rule`, `--cms-rich-gap`, `--cms-rich-list-indent`.
- Kit files vendored into a site or into the dashboard are never edited in place; re-sync with the kit's script.
- `make ci` is the test gate; run it at the task checkpoints named below and before any push.
- Windows host: use Git Bash syntax in Bash tool calls; the backend venv is activated with `source backend/venv/Scripts/activate`.

## Review Focus

1. **Reordering or removing repeater items / key-value rows that hold rich fields**: the formatted text must move and disappear with its own item, not stay in the old slot. Pinned by the stable-key tests in Task 13.
2. **A field containing only Enter presses or spaces**: it must store `""` (not `<p></p>`), and sites must render nothing. Pinned in Task 2 (canonical vectors), Task 10 (kit renders null) and Task 12 (serialize).
3. **Pasting from Google Docs** (outer `<b style="font-weight:normal">` wrapper, bold via `<span style="font-weight:700">`, coloured spans): only the truly bold text is bold, and no colours or fonts survive. Pinned in Task 12.
4. **A title with a link, rendered inside an already-clickable card**: no nested `<a>` (invalid HTML, hydration error). Pinned by the `links={false}` test in Task 10 and the usage rule in Tasks 17–20.
5. **`&`, `<`, quotes, emoji and `{placeholders}` through save → translate → render**: they must display exactly once, with no `&amp;amp;` and no lost characters. Pinned by idempotence vectors (Task 2), the translation re-canonicalisation test (Task 6) and the kit entity-decoding test (Task 8).

---

## File Structure

**Backend** (`backend/auth_service/`):
- `services/rich_text.py` — NEW. Formats, `is_html`, `safe_href`, the HTML→tree builder, canonical transform, serializer, `canonicalize`, `plain_text`, `format_of`, `field_formats`, `normalize_content`, errors.
- `services/rich_text_legacy.py` — NEW. `legacy_to_html` (Markdown-lite / plain → canonical HTML).
- `services/content_structure.py` — NEW. `apply_structure_rules` (the `_schema`/`_formats` policy) plus validation.
- `services/rich_text_migration.py` — NEW. Pure migration planner and SQL emitter.
- `services/segments.py` — MODIFY. `inline` field type; `formats_of(..., rich_text_version)`; public `repeater_schema`.
- `translation/sync.py`, `translation/deepl.py` — MODIFY. Version-aware formats, re-canonicalisation, request chunking.
- `routers/workspace.py`, `routers/deps.py`, `routers/content.py`, `models/schemas.py` — MODIFY.
- `tests/test_rich_text_*.py`, `tests/test_content_structure.py`, `tests/test_deepl_chunking.py` — NEW.
- `backend/scripts/migrate_rich_text.py` — NEW CLI. `backend/scripts/.rich-text-work/` — gitignored.
- `backend/migrations/2026_09_27_rich_text.sql` — NEW.

**Client kit** (`client-kit/rich-text/`): `package.json`, `tsconfig.json`, `vitest.config.ts`, `src/{parse,href,detect,normalize,serialize,legacy,plainText,RichText,splitRichWords,index}.ts(x)`, `src/cms-rich.css`, `fixtures/{canonical,legacy}-vectors.json`, `scripts/sync-rich-text-kit.mjs`, `tests/*.test.ts(x)`, `README.md`.

**Dashboard** (`frontend/src/`):
- `lib/cms-rich-text/` — vendored kit (generated by the sync script; never hand-edited).
- `components/dashboard/rich-text/{extensions.ts,serialize.ts,linkInput.ts,RichTextEditor.tsx,Toolbar.tsx,LinkPopover.tsx,ContentField.tsx}` + `__tests__/`.
- `components/dashboard/editors/{index.ts,TextBlockEditor.tsx,RepeaterEditor.tsx,KeyValueEditor.tsx}`, `components/dashboard/ServiceEditor.tsx` — MODIFY.

**Docs:** `docs/decisions/0010-rich-text-content.md` — NEW.

---

### Task 1: Database migration and ADR

**Files:**
- Create: `backend/migrations/2026_09_27_rich_text.sql`
- Create: `docs/decisions/0010-rich-text-content.md`
- Modify: `.gitignore` (add `backend/scripts/.rich-text-work/`)

**Interfaces:**
- Produces: column `projects.rich_text_version smallint not null` (existing rows 0, default for new rows 1); `service_types` row `text_block` whose `schema.fields.title.type = "inline"`.

- [ ] **Step 1: Write the migration**

```sql
-- 2026-09-27 rich text (ADR-0010). Additive: old code ignores the column.
-- Existing projects start at 0 (legacy behaviour) and are flipped to 1 one at a
-- time by backend/scripts/migrate_rich_text.py after their site ships the kit.
-- Projects created after this migration default to 1.
alter table projects add column if not exists rich_text_version smallint not null default 0;
alter table projects alter column rich_text_version set default 1;
alter table projects drop constraint if exists projects_rich_text_version_check;
alter table projects add constraint projects_rich_text_version_check check (rich_text_version in (0, 1));

update service_types
   set schema = jsonb_set(schema, '{fields,title,type}', '"inline"')
 where slug = 'text_block';
```

- [ ] **Step 2: Apply it to the shared DB (controller does this, not a subagent)**

Run with the Supabase MCP `apply_migration` (project `xeluydwpgiddbamysgyu`, name `2026_09_27_rich_text`) using the file contents. Then verify:

```sql
select slug, rich_text_version from projects order by slug;
select schema->'fields'->'title' from service_types where slug='text_block';
```
Expected: every existing project shows `0`; the title field type is `"inline"`.

- [ ] **Step 3: Write ADR 0010**

Create `docs/decisions/0010-rich-text-content.md`, following the structure of `docs/decisions/0008-*.md` (read it first for the headings). Content:
- **Status:** Accepted, 2026-09-27.
- **Context:** the Markdown half-convention, no sanitisation, DeepL mangling Markdown, sites not rendering HTML, ADR-0006's payload contract.
- **Decision:** the three formats with their tag sets; canonical HTML produced only by `services/rich_text.py`; the per-project `rich_text_version` gate; `_schema`/`_formats` as structural metadata; the client kit plus the `--cms-rich-*` theme contract; translation as `fmt="html"` with re-canonicalisation; the one-time atomic migration.
- **Do not:** store attributes other than `a[href]`; add colour/font/size marks; render CMS HTML with `dangerouslySetInnerHTML` on sites; run legacy inline conversion outside the migration; flip a project to version 1 before its site ships the kit; let a non-admin save change `_schema`/`_formats`.

- [ ] **Step 4: Gitignore the migration work dir**

Append to `.gitignore`:
```
# rich-text migration SQL + backups (contain client content)
backend/scripts/.rich-text-work/
```

- [ ] **Step 5: Commit**

```bash
git add backend/migrations/2026_09_27_rich_text.sql docs/decisions/0010-rich-text-content.md .gitignore
git commit -m "feat(db): rich_text_version gate and ADR-0010"
```

---

### Task 2: Backend canonical HTML (`services/rich_text.py`)

**Files:**
- Create: `backend/auth_service/services/rich_text.py`
- Create: `client-kit/rich-text/fixtures/canonical-vectors.json`
- Test: `backend/auth_service/tests/test_rich_text_canonical.py`

**Interfaces:**
- Produces (used by Tasks 3–7, 15):
  - `Format = Literal["plain","inline","rich"]`, `FORMATS`, `MAX_LENGTH`
  - `is_html(value: str) -> bool`, `safe_href(raw: str | None) -> str | None`
  - `escape_text(s: str) -> str`, `escape_attr(s: str) -> str`
  - `canonicalize(value, fmt, *, legacy=False, enforce_limit=True) -> str`
  - `plain_text(value, fmt="inline", *, keep_line_breaks=False) -> str`
  - `class RichTextTooLong(ValueError)` with `.length` and `.limit`
- Consumes (lazy import inside `canonicalize` and `plain_text`): `rich_text_legacy.legacy_to_html(text, fmt)` from Task 3. Until Task 3 lands, a tag-free rich value raises `ModuleNotFoundError`; this task's tests don't exercise that path.

- [ ] **Step 1: Create the shared canonical fixture**

`client-kit/rich-text/fixtures/canonical-vectors.json` (the TypeScript kit asserts the same file in Task 8):

```json
[
  {"name": "tiptap paragraph", "fmt": "rich", "input": "<p>Hello <strong>world</strong></p>", "expected": "<p>Hello <strong>world</strong></p>"},
  {"name": "synonyms", "fmt": "rich", "input": "<p><b>B</b> <i>I</i> <strike>S</strike> <del>D</del> <ins>U</ins></p>", "expected": "<p><strong>B</strong> <em>I</em> <s>S</s> <s>D</s> <u>U</u></p>"},
  {"name": "attributes stripped", "fmt": "rich", "input": "<p class=\"x\" style=\"color:red\"><strong style=\"color:red\">x</strong></p>", "expected": "<p><strong>x</strong></p>"},
  {"name": "script dropped with content", "fmt": "rich", "input": "<p>a<script>alert(1)</script>b</p>", "expected": "<p>ab</p>"},
  {"name": "style dropped with content", "fmt": "rich", "input": "<style>p{color:red}</style><p>x</p>", "expected": "<p>x</p>"},
  {"name": "svg dropped with content", "fmt": "rich", "input": "<p>a<svg><script>x</script><text>t</text></svg>b</p>", "expected": "<p>ab</p>"},
  {"name": "img dropped", "fmt": "rich", "input": "<p>a<img src=x onerror=alert(1)>b</p>", "expected": "<p>ab</p>"},
  {"name": "comment dropped", "fmt": "rich", "input": "<p>a<!-- x -->b</p>", "expected": "<p>ab</p>"},
  {"name": "javascript href unwrapped", "fmt": "rich", "input": "<p><a href=\"javascript:alert(1)\">x</a></p>", "expected": "<p>x</p>"},
  {"name": "entity-obfuscated scheme", "fmt": "rich", "input": "<p><a href=\"jav&#x61;script:alert(1)\">x</a></p>", "expected": "<p>x</p>"},
  {"name": "tab-split scheme", "fmt": "rich", "input": "<p><a href=\" java\tscript:alert(1)\">x</a></p>", "expected": "<p>x</p>"},
  {"name": "data url", "fmt": "rich", "input": "<p><a href=\"data:text/html,x\">x</a></p>", "expected": "<p>x</p>"},
  {"name": "protocol-relative", "fmt": "rich", "input": "<p><a href=\"//evil.com\">x</a></p>", "expected": "<p>x</p>"},
  {"name": "safe link keeps only href", "fmt": "rich", "input": "<p><a href=\"https://x.com/a?b=1&amp;c=2\" target=\"_blank\" rel=\"noopener\">x</a></p>", "expected": "<p><a href=\"https://x.com/a?b=1&amp;c=2\">x</a></p>"},
  {"name": "mailto tel hash relative", "fmt": "rich", "input": "<p><a href=\"mailto:a@b.ro\">m</a> <a href=\"tel:+40700\">t</a> <a href=\"#top\">h</a> <a href=\"/contact\">r</a></p>", "expected": "<p><a href=\"mailto:a@b.ro\">m</a> <a href=\"tel:+40700\">t</a> <a href=\"#top\">h</a> <a href=\"/contact\">r</a></p>"},
  {"name": "nested links unwrap inner", "fmt": "rich", "input": "<a href=\"https://a.com\">x <a href=\"https://b.com\">y</a></a>", "expected": "<p><a href=\"https://a.com\">x y</a></p>"},
  {"name": "loose inline wrapped", "fmt": "rich", "input": "Hello <strong>x</strong>", "expected": "<p>Hello <strong>x</strong></p>"},
  {"name": "span unwrapped", "fmt": "rich", "input": "<p><span style=\"font-weight:700\">x</span></p>", "expected": "<p>x</p>"},
  {"name": "only empty paragraphs", "fmt": "rich", "input": "<p></p><p><br></p>", "expected": ""},
  {"name": "interior empty paragraph kept", "fmt": "rich", "input": "<p></p><p>a</p><p></p><p>b</p><p></p>", "expected": "<p>a</p><p></p><p>b</p>"},
  {"name": "heading levels clamped", "fmt": "rich", "input": "<h1>A</h1><h5>B</h5>", "expected": "<h2>A</h2><h4>B</h4>"},
  {"name": "empty heading dropped", "fmt": "rich", "input": "<h2> </h2><p>x</p>", "expected": "<p>x</p>"},
  {"name": "divs become paragraphs", "fmt": "rich", "input": "<div>a</div><div>b</div>", "expected": "<p>a</p><p>b</p>"},
  {"name": "nested div split", "fmt": "rich", "input": "<div><div>a</div>b</div>", "expected": "<p>a</p><p>b</p>"},
  {"name": "tiptap nested list", "fmt": "rich", "input": "<ul><li><p>a</p><ul><li><p>b</p></li></ul></li></ul>", "expected": "<ul><li><p>a</p><ul><li><p>b</p></li></ul></li></ul>"},
  {"name": "loose li text wrapped", "fmt": "rich", "input": "<ul><li>a</li><li>b</li></ul>", "expected": "<ul><li><p>a</p></li><li><p>b</p></li></ul>"},
  {"name": "empty li removed", "fmt": "rich", "input": "<ul><li><p></p></li><li><p>x</p></li></ul>", "expected": "<ul><li><p>x</p></li></ul>"},
  {"name": "list depth 5 flattened", "fmt": "rich", "input": "<ul><li><p>1</p><ul><li><p>2</p><ul><li><p>3</p><ul><li><p>4</p><ul><li><p>5</p></li></ul></li></ul></li></ul></li></ul></li></ul>", "expected": "<ul><li><p>1</p><ul><li><p>2</p><ul><li><p>3</p><ul><li><p>4</p><p>5</p></li></ul></li></ul></li></ul></li></ul>"},
  {"name": "nested blockquote flattened", "fmt": "rich", "input": "<blockquote><blockquote><p>x</p></blockquote></blockquote>", "expected": "<blockquote><p>x</p></blockquote>"},
  {"name": "hr kept", "fmt": "rich", "input": "<p>a</p><hr/><p>b</p>", "expected": "<p>a</p><hr><p>b</p>"},
  {"name": "unclosed mark", "fmt": "rich", "input": "<p><strong>a</p><p>b</p>", "expected": "<p><strong>a</strong></p><p>b</p>"},
  {"name": "whitespace collapse", "fmt": "rich", "input": "<p>a \n  b</p>", "expected": "<p>a b</p>"},
  {"name": "nbsp preserved", "fmt": "rich", "input": "<p>a&nbsp;b</p>", "expected": "<p>a&nbsp;b</p>"},
  {"name": "entities decoded once", "fmt": "rich", "input": "<p>Tom &amp; Jerry &lt;3 \"q\" 😀 {name}</p>", "expected": "<p>Tom &amp; Jerry &lt;3 \"q\" 😀 {name}</p>"},
  {"name": "empty marks dropped", "fmt": "rich", "input": "<p><strong></strong>x<em> </em></p>", "expected": "<p>x</p>"},
  {"name": "br edges trimmed", "fmt": "rich", "input": "<p><br>a<br></p>", "expected": "<p>a</p>"},
  {"name": "inline flattens paragraphs", "fmt": "inline", "input": "<p>a</p><p>b</p>", "expected": "a<br>b"},
  {"name": "inline flattens lists", "fmt": "inline", "input": "<ul><li><p>a</p></li><li><p>b</p></li></ul>", "expected": "a<br>b"},
  {"name": "inline keeps marks", "fmt": "inline", "input": "Our <strong>IT</strong> &amp; <em>cloud</em>", "expected": "Our <strong>IT</strong> &amp; <em>cloud</em>"},
  {"name": "inline tag-free text", "fmt": "inline", "input": "Tom & Jerry", "expected": "Tom &amp; Jerry"},
  {"name": "inline canonical is stable", "fmt": "inline", "input": "Tom &amp; Jerry", "expected": "Tom &amp; Jerry"},
  {"name": "inline lone less-than", "fmt": "inline", "input": "a < b", "expected": "a &lt; b"},
  {"name": "inline user line breaks kept", "fmt": "inline", "input": "a<br><br>b", "expected": "a<br><br>b"},
  {"name": "inline only breaks", "fmt": "inline", "input": "<br><br>", "expected": ""},
  {"name": "inline whitespace only", "fmt": "inline", "input": "   ", "expected": ""},
  {"name": "inline headings flattened", "fmt": "inline", "input": "<h2>Title</h2>", "expected": "Title"},
  {"name": "inline hr becomes break", "fmt": "inline", "input": "a<hr>b", "expected": "a<br>b"}
]
```

- [ ] **Step 2: Write the failing tests**

`backend/auth_service/tests/test_rich_text_canonical.py`:

```python
import json
from pathlib import Path

import pytest

from auth_service.services.rich_text import (
    MAX_LENGTH,
    RichTextTooLong,
    canonicalize,
    is_html,
    plain_text,
    safe_href,
)

_REPO = Path(__file__).resolve().parents[3]
_VECTORS = json.loads(
    (_REPO / "client-kit" / "rich-text" / "fixtures" / "canonical-vectors.json").read_text("utf-8")
)


@pytest.mark.parametrize("vec", _VECTORS, ids=[v["name"] for v in _VECTORS])
def test_canonical_vectors(vec):
    assert canonicalize(vec["input"], vec["fmt"]) == vec["expected"]


@pytest.mark.parametrize("vec", _VECTORS, ids=[v["name"] for v in _VECTORS])
def test_canonicalize_is_idempotent(vec):
    once = canonicalize(vec["input"], vec["fmt"])
    assert canonicalize(once, vec["fmt"]) == once


def test_plain_format_is_untouched():
    assert canonicalize("<b>not html here</b> & raw", "plain") == "<b>not html here</b> & raw"


@pytest.mark.parametrize(
    "value,expected",
    [("<p>x</p>", True), ("<BR/>", True), ('<a href="x">', True), ("a < b", False),
     ("5 * 3", False), ("<abbr>x</abbr>", False), ("Tom &amp; Jerry", False)],
)
def test_is_html(value, expected):
    assert is_html(value) is expected


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("https://a.ro/x", "https://a.ro/x"),
        ("  https://a.ro  ", "https://a.ro"),
        ("mailto:a@b.ro", "mailto:a@b.ro"),
        ("tel:+40700", "tel:+40700"),
        ("#top", "#top"),
        ("/contact", "/contact"),
        ("//evil.com", None),
        ("/\\evil.com", None),
        ("javascript:alert(1)", None),
        ("java\x00script:alert(1)", None),
        ("JAVASCRIPT:alert(1)", None),
        ("data:text/html,x", None),
        ("vbscript:x", None),
        ("ftp://x", None),
        ("", None),
        (None, None),
        ("https://a.ro/" + "x" * 3000, None),
    ],
)
def test_safe_href(raw, expected):
    assert safe_href(raw) == expected


def test_inline_limit_enforced():
    with pytest.raises(RichTextTooLong) as exc:
        canonicalize("a" * (MAX_LENGTH["inline"] + 1), "inline")
    assert exc.value.limit == MAX_LENGTH["inline"]
    assert exc.value.length == MAX_LENGTH["inline"] + 1


def test_rich_limit_enforced_and_can_be_disabled():
    big = "<p>" + "a" * MAX_LENGTH["rich"] + "</p>"
    with pytest.raises(RichTextTooLong):
        canonicalize(big, "rich")
    assert canonicalize(big, "rich", enforce_limit=False) == big


def test_plain_text_strips_markup_and_decodes():
    assert plain_text("<p>Tom &amp; <strong>Jerry</strong></p><p>2nd</p>", "rich") == "Tom & Jerry 2nd"
    assert plain_text("a<br>b", "inline") == "a b"
    assert plain_text("<p>a</p><ul><li><p>b</p></li></ul>", "rich", keep_line_breaks=True) == "a\nb"
    assert plain_text("", "rich") == ""
    assert plain_text("raw <b>", "plain") == "raw <b>"
```

- [ ] **Step 3: Run to confirm failure**

Run: `cd backend && source venv/Scripts/activate && python -m pytest auth_service/tests/test_rich_text_canonical.py -q`
Expected: collection error `ModuleNotFoundError: auth_service.services.rich_text`.

- [ ] **Step 4: Implement `services/rich_text.py`**

```python
"""Rich-text content model (ADR-0010): field formats and canonical HTML.

`inline` / `rich` CMS leaves are stored as canonical HTML produced by
`canonicalize`. The backend is the only writer (ADR-0002), so every value a
client site renders has passed through here. The TypeScript client kit
(client-kit/rich-text) ports this exact transform; both are pinned by
client-kit/rich-text/fixtures/canonical-vectors.json. Pure — no I/O."""

from __future__ import annotations

import re
from html.parser import HTMLParser
from typing import Literal

Format = Literal["plain", "inline", "rich"]
FORMATS: tuple[str, ...] = ("plain", "inline", "rich")

MARK_TAGS = frozenset({"strong", "em", "u", "s"})
INLINE_TAGS = MARK_TAGS | {"a", "br"}
HEADING_TAGS = frozenset({"h2", "h3", "h4"})
BLOCK_TAGS = frozenset({"p", "ul", "ol", "li", "blockquote", "hr"}) | HEADING_TAGS
RICH_TAGS = INLINE_TAGS | BLOCK_TAGS

MAX_LENGTH: dict[str, int] = {"inline": 2_000, "rich": 50_000}
MAX_LIST_DEPTH = 4
MAX_HREF_LENGTH = 2_048

_SYNONYMS = {
    "b": "strong", "i": "em", "strike": "s", "del": "s", "ins": "u",
    "h1": "h2", "h5": "h4", "h6": "h4", "div": "p",
}
_DROP_WITH_CONTENT = frozenset({
    "script", "style", "iframe", "object", "svg", "math", "template", "noscript", "head",
    "title", "textarea", "select", "button", "canvas", "audio", "video", "picture",
})
_HTML_RE = re.compile(
    r"<(?:p|br|strong|em|u|s|a|ul|ol|li|h[1-6]|blockquote|hr|b|i|div|span)\b[^>]*>", re.I
)
_WS_RE = re.compile(r"[ \t\r\n\f]+")
_CTRL_RE = re.compile(r"[\x00-\x1f\x7f]")


class RichTextTooLong(ValueError):
    """The canonical value exceeds MAX_LENGTH for its format."""

    def __init__(self, length: int, limit: int) -> None:
        super().__init__(f"{length} > {limit}")
        self.length = length
        self.limit = limit


def is_html(value: str) -> bool:
    """True when `value` contains at least one recognised HTML tag."""
    return bool(_HTML_RE.search(value))


def safe_href(raw: str | None) -> str | None:
    """Return a cleaned href if its scheme is allowed, else None (default deny)."""
    if not raw:
        return None
    v = _CTRL_RE.sub("", raw).strip()
    if not v or len(v) > MAX_HREF_LENGTH:
        return None
    probe = v.replace(" ", "").lower()
    if probe.startswith(("http://", "https://", "mailto:", "tel:")):
        return v
    if v.startswith("#"):
        return v
    if v.startswith("/") and not v.startswith(("//", "/\\")):
        return v
    return None


def escape_text(s: str) -> str:
    return (
        s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace("\xa0", "&nbsp;")
    )


def escape_attr(s: str) -> str:
    return escape_text(s).replace('"', "&quot;")


# ── Tree ──────────────────────────────────────────────────────────────────────


class _Node:
    __slots__ = ("tag", "href", "children")

    def __init__(self, tag: str, href: str | None = None, children: list | None = None) -> None:
        self.tag = tag
        self.href = href
        self.children: list[_Node | str] = children if children is not None else []


def _br() -> _Node:
    return _Node("br")


class _Builder(HTMLParser):
    """Tag-soup tolerant builder that keeps only allow-listed elements.

    Unknown elements are unwrapped (their text flows into the parent);
    _DROP_WITH_CONTENT elements vanish with everything inside them."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.root = _Node("#root")
        self._stack: list[_Node] = [self.root]
        self._skip = 0

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        if tag in _DROP_WITH_CONTENT:
            self._skip += 1
            return
        if self._skip:
            return
        tag = _SYNONYMS.get(tag, tag)
        if tag in ("br", "hr"):
            self._stack[-1].children.append(_Node(tag))
            return
        if tag not in RICH_TAGS:
            return
        href = None
        if tag == "a":
            href = next((v for k, v in attrs if k.lower() == "href"), None)
        node = _Node(tag, href)
        self._stack[-1].children.append(node)
        self._stack.append(node)

    def handle_startendtag(self, tag, attrs):
        if tag.lower() in _DROP_WITH_CONTENT:
            return
        self.handle_starttag(tag, attrs)
        self.handle_endtag(tag)

    def handle_endtag(self, tag):
        tag = tag.lower()
        if tag in _DROP_WITH_CONTENT:
            if self._skip:
                self._skip -= 1
            return
        if self._skip:
            return
        tag = _SYNONYMS.get(tag, tag)
        if tag not in RICH_TAGS or tag in ("br", "hr"):
            return
        for i in range(len(self._stack) - 1, 0, -1):
            if self._stack[i].tag == tag:
                del self._stack[i:]
                return

    def handle_data(self, data):
        if self._skip or not data:
            return
        kids = self._stack[-1].children
        if kids and isinstance(kids[-1], str):
            kids[-1] += data
        else:
            kids.append(data)


def _parse(value: str) -> _Node:
    b = _Builder()
    b.feed(value)
    b.close()
    return b.root


# ── Canonical transform (mirrored 1:1 by client-kit/rich-text/src/normalize.ts) ──


def _has_content(nodes: list) -> bool:
    for n in nodes:
        if isinstance(n, str):
            if n.strip():
                return True
        elif n.tag != "br":
            return True
    return False


def _ends_with_br(nodes: list) -> bool:
    for n in reversed(nodes):
        if isinstance(n, str):
            if not n.strip():
                continue
            return False
        return n.tag == "br"
    return False


def _inline(nodes: list, in_link: bool = False) -> list:
    out: list = []
    for n in nodes:
        if isinstance(n, str):
            out.append(_WS_RE.sub(" ", n))
            continue
        tag = n.tag
        if tag == "br":
            out.append(_br())
        elif tag in MARK_TAGS:
            kids = _inline(n.children, in_link)
            if _has_content(kids):
                out.append(_Node(tag, children=kids))
        elif tag == "a":
            kids = _inline(n.children, True)
            href = None if in_link else safe_href(n.href)
            if href and _has_content(kids):
                out.append(_Node("a", href, kids))
            else:
                out.extend(kids)
        else:  # a block element inside an inline context: flatten, separated by <br>
            kids = [] if tag == "hr" else _inline(n.children, in_link)
            if tag == "hr" or _has_content(kids):
                if _has_content(out) and not _ends_with_br(out):
                    out.append(_br())
                out.extend(kids)
                if not _ends_with_br(out):
                    out.append(_br())
    return out


def _tidy(nodes: list) -> list:
    res: list = []
    for n in nodes:
        if isinstance(n, str):
            s = n
            last = res[-1] if res else None
            if isinstance(last, _Node) and last.tag == "br":
                s = s.lstrip(" ")
            if not s:
                continue
            if isinstance(last, str):
                res[-1] = _WS_RE.sub(" ", last + s)
                continue
            res.append(s)
        else:
            if n.tag == "br" and res and isinstance(res[-1], str):
                t = res[-1].rstrip(" ")
                if t:
                    res[-1] = t
                else:
                    res.pop()
            res.append(n)
    return res


def _drop_edge(n) -> bool:
    return (not n.strip()) if isinstance(n, str) else n.tag == "br"


def _trim_edges(nodes: list) -> list:
    res = _tidy(nodes)
    while res and _drop_edge(res[0]):
        res.pop(0)
    while res and _drop_edge(res[-1]):
        res.pop()
    if res and isinstance(res[0], str):
        res[0] = res[0].lstrip(" ")
    if res and isinstance(res[-1], str):
        res[-1] = res[-1].rstrip(" ")
    return res


def _is_empty_p(n: _Node) -> bool:
    return n.tag == "p" and not _has_content(n.children)


def _trim_empty_edges(blocks: list[_Node]) -> list[_Node]:
    s, e = 0, len(blocks)
    while s < e and _is_empty_p(blocks[s]):
        s += 1
    while e > s and _is_empty_p(blocks[e - 1]):
        e -= 1
    return blocks[s:e]


def _paragraph_nodes(children: list, depth: int) -> list[_Node]:
    if any(isinstance(c, _Node) and c.tag in BLOCK_TAGS for c in children):
        return _blocks(children, depth)
    return [_Node("p", children=_trim_edges(_inline(children)))]


def _blocks(nodes: list, depth: int) -> list[_Node]:
    out: list[_Node] = []
    pending: list = []

    def flush() -> None:
        if pending:
            kids = _trim_edges(_inline(pending))
            if _has_content(kids):
                out.append(_Node("p", children=kids))
            pending.clear()

    for n in nodes:
        if isinstance(n, str) or n.tag in INLINE_TAGS:
            pending.append(n)
            continue
        flush()
        tag = n.tag
        if tag == "p":
            out.extend(_paragraph_nodes(n.children, depth))
        elif tag in HEADING_TAGS:
            kids = _trim_edges(_inline(n.children))
            if _has_content(kids):
                out.append(_Node(tag, children=kids))
        elif tag == "hr":
            out.append(_Node("hr"))
        elif tag in ("ul", "ol"):
            out.extend(_list(n, depth + 1))
        elif tag == "li":
            out.extend(_list(_Node("ul", children=[n]), depth + 1))
        elif tag == "blockquote":
            inner: list[_Node] = []
            for b in _trim_empty_edges(_blocks(n.children, depth)):
                inner.extend(b.children if b.tag == "blockquote" else [b])
            if inner:
                out.append(_Node("blockquote", children=inner))
    flush()
    return out


def _li(children: list, depth: int) -> _Node:
    kept: list[_Node] = []
    for b in _blocks(children, depth):
        if b.tag in ("p", "ul", "ol"):
            kept.append(b)
        elif b.tag in HEADING_TAGS:
            kept.append(_Node("p", children=b.children))
        elif b.tag == "blockquote":
            kept.extend(x for x in b.children if x.tag in ("p", "ul", "ol"))
    if not kept or kept[0].tag != "p":
        kept.insert(0, _Node("p"))
    return _Node("li", children=kept)


def _li_has_content(item: _Node) -> bool:
    return any(
        c.tag in ("ul", "ol") or (c.tag == "p" and _has_content(c.children)) for c in item.children
    )


def _list(node: _Node, depth: int) -> list[_Node]:
    items: list[_Node] = []
    for c in node.children:
        if isinstance(c, str):
            if c.strip():
                items.append(_li([c], depth))
            continue
        if c.tag == "li":
            items.append(_li(c.children, depth))
        elif c.tag in ("ul", "ol") and items:
            items[-1].children.extend(_list(c, depth + 1))
        else:
            items.append(_li([c], depth))
    items = [i for i in items if _li_has_content(i)]
    if not items:
        return []
    if depth > MAX_LIST_DEPTH:
        flat: list[_Node] = []
        for i in items:
            flat.extend(i.children)
        return flat
    return [_Node(node.tag, children=items)]


def _serialize(nodes: list) -> str:
    parts: list[str] = []
    buf: list[str] = []

    def flush() -> None:
        if buf:
            parts.append(escape_text(_WS_RE.sub(" ", "".join(buf))))
            buf.clear()

    for n in nodes:
        if isinstance(n, str):
            buf.append(n)
            continue
        flush()
        if n.tag in ("br", "hr"):
            parts.append(f"<{n.tag}>")
        elif n.tag == "a":
            parts.append(f'<a href="{escape_attr(n.href or "")}">{_serialize(n.children)}</a>')
        else:
            parts.append(f"<{n.tag}>{_serialize(n.children)}</{n.tag}>")
    flush()
    return "".join(parts)


def canonicalize(
    value: str, fmt: Format, *, legacy: bool = False, enforce_limit: bool = True
) -> str:
    """Return the canonical stored form of an inline/rich value.

    `plain` values are returned untouched. `legacy=True` (migration only) treats a
    tag-free value as pre-rich-text content. Tag-free `rich` values are always
    legacy. Tag-free `inline` values are HTML fragments (spec §4.4)."""
    if fmt == "plain" or not isinstance(value, str):
        return value
    if not value.strip():
        return ""
    if not is_html(value) and (legacy or fmt == "rich"):
        from .rich_text_legacy import legacy_to_html

        value = legacy_to_html(value, fmt)
    root = _parse(value)
    if fmt == "inline":
        out = _serialize(_trim_edges(_inline(root.children)))
    else:
        out = _serialize(_trim_empty_edges(_blocks(root.children, 0)))
    limit = MAX_LENGTH[fmt]
    if enforce_limit and len(out) > limit:
        raise RichTextTooLong(len(out), limit)
    return out


def plain_text(value: str, fmt: Format = "inline", *, keep_line_breaks: bool = False) -> str:
    """Text content of a stored value, for meta tags, emails, keys and logs."""
    if not isinstance(value, str) or not value:
        return ""
    if fmt == "plain":
        return value
    if fmt == "rich" and not is_html(value):
        from .rich_text_legacy import legacy_to_html

        value = legacy_to_html(value, "rich")
    parts: list[str] = []

    def walk(nodes: list) -> None:
        for n in nodes:
            if isinstance(n, str):
                parts.append(n)
            elif n.tag in ("br", "hr"):
                parts.append("\n")
            elif n.tag in BLOCK_TAGS:
                parts.append("\n")
                walk(n.children)
                parts.append("\n")
            else:
                walk(n.children)

    walk(_parse(value).children)
    text = "".join(parts)
    if keep_line_breaks:
        lines = [re.sub(r"\s+", " ", ln).strip() for ln in text.split("\n")]
        kept: list[str] = []
        for ln in lines:
            if ln or (kept and kept[-1]):
                kept.append(ln)
        return "\n".join(kept).strip()
    return re.sub(r"\s+", " ", text).strip()
```

- [ ] **Step 5: Run the tests**

Run: `python -m pytest auth_service/tests/test_rich_text_canonical.py -q`
Expected: all pass. If a vector fails, fix the implementation, not the vector. The only exception is a vector that contradicts spec §4.3; in that case fix the vector **and** say so in your report, because the TS kit asserts the same file.

- [ ] **Step 6: Commit**

```bash
git add backend/auth_service/services/rich_text.py backend/auth_service/tests/test_rich_text_canonical.py client-kit/rich-text/fixtures/canonical-vectors.json
git commit -m "feat(backend): canonical rich-text HTML sanitiser"
```

---

### Task 3: Legacy converter (`services/rich_text_legacy.py`)

**Files:**
- Create: `backend/auth_service/services/rich_text_legacy.py`
- Create: `client-kit/rich-text/fixtures/legacy-vectors.json`
- Test: `backend/auth_service/tests/test_rich_text_legacy.py`

**Interfaces:**
- Consumes: `safe_href`, `escape_text`, `escape_attr`, `canonicalize` from Task 2.
- Produces: `legacy_to_html(text: str, fmt: str) -> str`. Output is already canonical, and the TS port in Task 9 reproduces it exactly.

- [ ] **Step 1: Create the shared legacy fixture**

`client-kit/rich-text/fixtures/legacy-vectors.json`:

```json
[
  {"name": "paragraphs and soft breaks", "fmt": "rich", "input": "First line\nsecond line\n\nNext para", "expected": "<p>First line<br>second line</p><p>Next para</p>"},
  {"name": "marks", "fmt": "rich", "input": "Some **bold** and *italic* and _also_ ~~gone~~ and __strong__", "expected": "<p>Some <strong>bold</strong> and <em>italic</em> and <em>also</em> <s>gone</s> and <strong>strong</strong></p>"},
  {"name": "heading and bullets", "fmt": "rich", "input": "## Services\n- Repairs\n- Installs", "expected": "<h2>Services</h2><ul><li><p>Repairs</p></li><li><p>Installs</p></li></ul>"},
  {"name": "h1 h3 h4 h6", "fmt": "rich", "input": "# A\n### B\n#### C\n###### D", "expected": "<h2>A</h2><h3>B</h3><h4>C</h4><h4>D</h4>"},
  {"name": "ordered list", "fmt": "rich", "input": "1. One\n2) Two", "expected": "<ol><li><p>One</p></li><li><p>Two</p></li></ol>"},
  {"name": "intro then list", "fmt": "rich", "input": "Intro:\n- a\n* b\n+ c", "expected": "<p>Intro:</p><ul><li><p>a</p></li><li><p>b</p></li><li><p>c</p></li></ul>"},
  {"name": "list continuation", "fmt": "rich", "input": "- a\ncontinued\n- b", "expected": "<ul><li><p>a<br>continued</p></li><li><p>b</p></li></ul>"},
  {"name": "link with underscores", "fmt": "rich", "input": "See [our site](https://example.com/a_b_c) now", "expected": "<p>See <a href=\"https://example.com/a_b_c\">our site</a> now</p>"},
  {"name": "unsafe link becomes text", "fmt": "rich", "input": "Click [x](javascript:void)", "expected": "<p>Click x</p>"},
  {"name": "bold link", "fmt": "rich", "input": "**[Call us](tel:+40700000000)**", "expected": "<p><strong><a href=\"tel:+40700000000\">Call us</a></strong></p>"},
  {"name": "escaping", "fmt": "rich", "input": "Tom & Jerry <3 \"quotes\" {name}", "expected": "<p>Tom &amp; Jerry &lt;3 \"quotes\" {name}</p>"},
  {"name": "quote", "fmt": "rich", "input": "> Quoted\n> text", "expected": "<blockquote><p>Quoted<br>text</p></blockquote>"},
  {"name": "empty quote dropped", "fmt": "rich", "input": ">\n\nx", "expected": "<p>x</p>"},
  {"name": "hr", "fmt": "rich", "input": "Above\n\n---\n\nBelow", "expected": "<p>Above</p><hr><p>Below</p>"},
  {"name": "star math is literal", "fmt": "rich", "input": "5 * 3 * 2 = 30", "expected": "<p>5 * 3 * 2 = 30</p>"},
  {"name": "snake case is literal", "fmt": "rich", "input": "use my_var_name here", "expected": "<p>use my_var_name here</p>"},
  {"name": "whitespace runs", "fmt": "rich", "input": "  a    b  \n\n\n\n  c ", "expected": "<p>a b</p><p>c</p>"},
  {"name": "nbsp becomes space", "fmt": "rich", "input": "a\u00a0b", "expected": "<p>a b</p>"},
  {"name": "crlf", "fmt": "rich", "input": "a\r\nb\r\n\r\nc", "expected": "<p>a<br>b</p><p>c</p>"},
  {"name": "blank rich", "fmt": "rich", "input": "   \n  ", "expected": ""},
  {"name": "inline escapes", "fmt": "inline", "input": "Soluții IT & Cloud <3", "expected": "Soluții IT &amp; Cloud &lt;3"},
  {"name": "inline newlines", "fmt": "inline", "input": "Line one\nLine two\n\nLine four", "expected": "Line one<br>Line two<br><br>Line four"},
  {"name": "inline no markdown", "fmt": "inline", "input": "**not bold** *nor this*", "expected": "**not bold** *nor this*"},
  {"name": "inline trims blank edges", "fmt": "inline", "input": "\n  padded  \n\n", "expected": "padded"},
  {"name": "inline blank", "fmt": "inline", "input": " \n ", "expected": ""}
]
```

- [ ] **Step 2: Write the failing tests**

`backend/auth_service/tests/test_rich_text_legacy.py`:

```python
import json
from pathlib import Path

import pytest

from auth_service.services.rich_text import canonicalize
from auth_service.services.rich_text_legacy import legacy_to_html

_REPO = Path(__file__).resolve().parents[3]
_VECTORS = json.loads(
    (_REPO / "client-kit" / "rich-text" / "fixtures" / "legacy-vectors.json").read_text("utf-8")
)


@pytest.mark.parametrize("vec", _VECTORS, ids=[v["name"] for v in _VECTORS])
def test_legacy_vectors(vec):
    assert legacy_to_html(vec["input"], vec["fmt"]) == vec["expected"]


@pytest.mark.parametrize("vec", _VECTORS, ids=[v["name"] for v in _VECTORS])
def test_legacy_output_is_already_canonical(vec):
    out = legacy_to_html(vec["input"], vec["fmt"])
    assert canonicalize(out, vec["fmt"]) == out


def test_canonicalize_legacy_flag_converts_tag_free_inline():
    assert canonicalize("a & b\nc", "inline", legacy=True) == "a &amp; b<br>c"


def test_canonicalize_without_legacy_treats_inline_as_html():
    # A canonical inline value must never be escaped twice (spec §4.4).
    assert canonicalize("a &amp; b", "inline") == "a &amp; b"


def test_tag_free_rich_is_always_legacy():
    assert canonicalize("**x**", "rich") == "<p><strong>x</strong></p>"
```

- [ ] **Step 3: Run to confirm failure**

Run: `python -m pytest auth_service/tests/test_rich_text_legacy.py -q`
Expected: `ModuleNotFoundError: auth_service.services.rich_text_legacy`.

- [ ] **Step 4: Implement `services/rich_text_legacy.py`**

```python
"""Legacy (pre-rich-text) text → canonical HTML (spec §4.4).

Rich: the Markdown-lite subset CMS content used before ADR-0010. Inline: plain
text (escape + line breaks, no Markdown). Output is already canonical. Mirrored
exactly by client-kit/rich-text/src/legacy.ts; both are pinned by
client-kit/rich-text/fixtures/legacy-vectors.json — change them together."""

from __future__ import annotations

import re

from .rich_text import escape_attr, escape_text, safe_href

_WS_RE = re.compile(r"[ \t\r\n\f]+")
_W = "0-9A-Za-z\u00c0-\u024f"  # explicit word class so Python and JS agree
_LINK_RE = re.compile(r"\[([^\]\n]+)\]\(([^)\s]+)\)")
_BOLD_RE = re.compile(r"\*\*(?=\S)(.+?)(?<=\S)\*\*|__(?=\S)(.+?)(?<=\S)__")
_STRIKE_RE = re.compile(r"~~(?=\S)(.+?)(?<=\S)~~")
_EM_RE = re.compile(
    rf"(?<![{_W}*])\*(?=\S)(.+?)(?<=\S)\*(?![{_W}*])|(?<![{_W}_])_(?=\S)(.+?)(?<=\S)_(?![{_W}_])"
)
_PH_RE = re.compile("\ue000(\\d+)\ue001")
_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)$")
_HR_RE = re.compile(r"^(?:-{3,}|\*{3,}|_{3,})$")
_UL_RE = re.compile(r"^[-*+]\s+(.+)$")
_OL_RE = re.compile(r"^\d{1,9}[.)]\s+(.+)$")
_QUOTE_RE = re.compile(r"^>\s?(.*)$")
_BLANK_SPLIT_RE = re.compile(r"\n[ \t]*\n")


def _clean(line: str) -> str:
    return _WS_RE.sub(" ", line).strip()


def _inline_md(line: str) -> str:
    links: list[str] = []

    def keep(m: re.Match) -> str:
        href = safe_href(m.group(2))
        label = escape_text(m.group(1))
        links.append(f'<a href="{escape_attr(href)}">{label}</a>' if href else label)
        return f"\ue000{len(links) - 1}\ue001"

    s = _LINK_RE.sub(keep, line)
    s = escape_text(s)
    s = _BOLD_RE.sub(lambda m: f"<strong>{m.group(1) or m.group(2)}</strong>", s)
    s = _STRIKE_RE.sub(lambda m: f"<s>{m.group(1)}</s>", s)
    s = _EM_RE.sub(lambda m: f"<em>{m.group(1) or m.group(2)}</em>", s)
    return _PH_RE.sub(lambda m: links[int(m.group(1))], s)


def _flush(kind: str | None, groups: list[list[str]], out: list[str]) -> None:
    if kind is None or not groups:
        return
    if kind in ("p", "quote"):
        lines = [g for g in groups[0] if g]
        if not lines:
            return
        body = "<br>".join(lines)
        out.append(f"<p>{body}</p>" if kind == "p" else f"<blockquote><p>{body}</p></blockquote>")
        return
    items = "".join("<li><p>" + "<br>".join(g) + "</p></li>" for g in groups if g)
    if items:
        out.append(f"<{kind}>{items}</{kind}>")


def _rich(text: str) -> str:
    out: list[str] = []
    for raw_block in _BLANK_SPLIT_RE.split(text):
        kind: str | None = None
        groups: list[list[str]] = []
        for raw_line in raw_block.split("\n"):
            line = _clean(raw_line)
            if not line:
                continue
            if _HR_RE.match(line):
                _flush(kind, groups, out)
                kind, groups = None, []
                out.append("<hr>")
                continue
            h = _HEADING_RE.match(line)
            if h:
                _flush(kind, groups, out)
                kind, groups = None, []
                content = _inline_md(h.group(2))
                level = {1: 2, 2: 2, 3: 3}.get(len(h.group(1)), 4)
                if content:
                    out.append(f"<h{level}>{content}</h{level}>")
                continue
            ul, ol = _UL_RE.match(line), _OL_RE.match(line)
            m, k = (ul, "ul") if ul else (ol, "ol")
            if m:
                if kind != k:
                    _flush(kind, groups, out)
                    kind, groups = k, []
                groups.append([_inline_md(m.group(1))])
                continue
            q = _QUOTE_RE.match(line)
            if q:
                if kind != "quote":
                    _flush(kind, groups, out)
                    kind, groups = "quote", [[]]
                groups[0].append(_inline_md(_clean(q.group(1))))
                continue
            if kind in ("ul", "ol"):
                groups[-1].append(_inline_md(line))
                continue
            if kind != "p":
                _flush(kind, groups, out)
                kind, groups = "p", [[]]
            groups[0].append(_inline_md(line))
        _flush(kind, groups, out)
    return "".join(out)


def _inline(text: str) -> str:
    lines = [_clean(ln) for ln in text.split("\n")]
    while lines and not lines[0]:
        lines.pop(0)
    while lines and not lines[-1]:
        lines.pop()
    return "<br>".join(escape_text(ln) for ln in lines)


def legacy_to_html(text: str, fmt: str) -> str:
    """Convert pre-rich-text content to canonical HTML for `fmt` ("inline"|"rich")."""
    if not isinstance(text, str):
        return ""
    t = text.replace("\r\n", "\n").replace("\r", "\n").replace("\u00a0", " ")
    if not t.strip():
        return ""
    return _rich(t) if fmt == "rich" else _inline(t)
```

- [ ] **Step 5: Run both rich-text test files**

Run: `python -m pytest auth_service/tests/test_rich_text_legacy.py auth_service/tests/test_rich_text_canonical.py -q`
Expected: all pass. The same fixture rule as Task 2 Step 5 applies.

- [ ] **Step 6: Commit**

```bash
git add backend/auth_service/services/rich_text_legacy.py backend/auth_service/tests/test_rich_text_legacy.py client-kit/rich-text/fixtures/legacy-vectors.json
git commit -m "feat(backend): legacy Markdown-lite to rich-text HTML converter"
```

---

### Task 4: Format model — `format_of`, `field_formats`, `normalize_content`, segments

**Files:**
- Modify: `backend/auth_service/services/rich_text.py` (append)
- Modify: `backend/auth_service/services/segments.py`
- Test: `backend/auth_service/tests/test_rich_text_formats.py`

**Interfaces:**
- Consumes: `canonicalize`, `RichTextTooLong` (Task 2); `segments_of`, `apply_segments` (existing).
- Produces:
  - `format_of(service_type: str, path: str, content: dict) -> Format`
  - `field_formats(service_type: str, content: dict) -> dict[str, str]` (spec §5.7 shape)
  - `normalize_content(service_type, content, *, legacy=False, enforce_limit=True) -> dict` (returns a new dict)
  - `class RichTextFieldError(ValueError)` with `.path`, `.length`, `.limit`
  - `segments.repeater_schema(content) -> dict[str, str | None]` (public rename of `_repeater_schema`; keep the old name as an alias)
  - `segments.formats_of(service_type, content, rich_text_version: int = 0) -> dict[str, str]`

- [ ] **Step 1: Write the failing tests**

`backend/auth_service/tests/test_rich_text_formats.py`:

```python
import pytest

from auth_service.services.rich_text import (
    RichTextFieldError,
    field_formats,
    format_of,
    normalize_content,
)
from auth_service.services.segments import formats_of, segments_of

REPEATER = {
    "_schema": [
        {"key": "title", "label": "Title", "type": "inline"},
        {"key": "body", "label": "Body", "type": "richtext"},
        {"key": "name", "label": "Name", "type": "string"},
        {"key": "link", "label": "Link", "type": "url"},
        {"key": "tags", "label": "Tags", "type": "tags"},
    ],
    "items": [
        {"_id": "i1", "title": "A & B", "body": "**x**", "name": "N & M", "link": "https://a.ro", "tags": ["t"]},
    ],
}
KV = {"entries": {"phone": "+40 7", "about": "We & you", "bio": "<p>x</p>"}, "_formats": {"about": "inline", "bio": "rich", "bad": "weird"}}


def test_format_of_text_block():
    assert format_of("text_block", "title", {}) == "inline"
    assert format_of("text_block", "body", {}) == "rich"


def test_format_of_repeater_by_schema_type():
    assert format_of("repeater", "items.i1.title", REPEATER) == "inline"
    assert format_of("repeater", "items.i1.body", REPEATER) == "rich"
    assert format_of("repeater", "items.i1.name", REPEATER) == "plain"
    assert format_of("repeater", "items.i1.tags.0", REPEATER) == "plain"
    assert format_of("repeater", "items.i1.missing", REPEATER) == "plain"


def test_format_of_key_value_defaults_to_plain_and_ignores_invalid():
    assert format_of("key_value", "entries.phone", KV) == "plain"
    assert format_of("key_value", "entries.about", KV) == "inline"
    assert format_of("key_value", "entries.bio", KV) == "rich"
    assert format_of("key_value", "entries.bad", {"_formats": {"bad": "weird"}}) == "plain"


def test_format_of_other_types_plain():
    assert format_of("image", "alt", {}) == "plain"
    assert format_of("file_download", "filename", {}) == "plain"


def test_field_formats_shapes():
    assert field_formats("text_block", {}) == {"title": "inline", "body": "rich"}
    assert field_formats("repeater", REPEATER) == {
        "title": "inline", "body": "rich", "name": "plain", "link": "plain", "tags": "plain",
    }
    assert field_formats("key_value", KV) == {
        "phone": "plain", "about": "inline", "bio": "rich", "*": "plain",
    }
    assert field_formats("image", {}) == {"alt": "plain"}
    assert field_formats("file_download", {}) == {"filename": "plain"}
    assert field_formats("gallery", {}) == {}


def test_normalize_content_touches_only_inline_and_rich_leaves():
    out = normalize_content("repeater", REPEATER)
    item = out["items"][0]
    assert item["title"] == "A &amp; B"
    assert item["body"] == "<p><strong>x</strong></p>"  # tag-free rich → legacy
    assert item["name"] == "N & M"  # plain untouched
    assert item["link"] == "https://a.ro"
    assert item["tags"] == ["t"]
    assert out["_schema"] == REPEATER["_schema"]
    assert REPEATER["items"][0]["title"] == "A & B"  # input not mutated


def test_normalize_content_key_value():
    out = normalize_content("key_value", KV)
    assert out["entries"] == {"phone": "+40 7", "about": "We &amp; you", "bio": "<p>x</p>"}


def test_normalize_content_legacy_flag_for_inline():
    out = normalize_content("text_block", {"title": "a\nb", "body": ""}, legacy=True)
    assert out == {"title": "a<br>b", "body": ""}


def test_normalize_content_reports_path_on_limit():
    with pytest.raises(RichTextFieldError) as exc:
        normalize_content("text_block", {"title": "x" * 2001})
    assert exc.value.path == "title"
    assert exc.value.limit == 2000


def test_segments_include_inline_repeater_fields():
    segs = segments_of("repeater", REPEATER)
    assert "items.i1.title" in segs


def test_formats_of_versions():
    legacy = formats_of("repeater", REPEATER)
    assert legacy["items.i1.body"] == "markdown"
    assert legacy["items.i1.title"] == "text"
    v1 = formats_of("repeater", REPEATER, rich_text_version=1)
    assert v1["items.i1.body"] == "html"
    assert v1["items.i1.title"] == "html"
    assert v1["items.i1.name"] == "text"
    assert v1["items.i1.tags.0"] == "text"
    assert formats_of("text_block", {"title": "t", "body": "b"}, rich_text_version=1) == {
        "title": "html", "body": "html",
    }
```

- [ ] **Step 2: Run to confirm failure**

Run: `python -m pytest auth_service/tests/test_rich_text_formats.py -q`
Expected: `ImportError` (`format_of` is not defined).

- [ ] **Step 3: Update `services/segments.py`**

- Change line 17 to: `_TRANSLATABLE_FIELD_TYPES = {"string", "inline", "richtext", "tags"}`.
- Rename `_repeater_schema` to `repeater_schema`, update the three internal call sites, and add `_repeater_schema = repeater_schema  # backwards-compatible alias` directly below the function.
- Replace `formats_of` with a version-aware wrapper that keeps the current body as `_legacy_formats_of`:

```python
def formats_of(
    service_type: str, content: dict, rich_text_version: int = 0
) -> dict[str, str]:
    """Return {leaf_path: fmt} mirroring segments_of's paths.

    Version ≥ 1 (ADR-0010): inline/rich leaves are "html", everything else "text".
    Version 0: the pre-rich-text behaviour (richtext leaves "markdown")."""
    if rich_text_version >= 1:
        from .rich_text import format_of

        return {
            path: ("html" if format_of(service_type, path, content) in ("inline", "rich") else "text")
            for path in segments_of(service_type, content)
        }
    return _legacy_formats_of(service_type, content)


def _legacy_formats_of(service_type: str, content: dict) -> dict[str, str]:
    # (the previous body of formats_of, unchanged)
```

- [ ] **Step 4: Append the format model to `services/rich_text.py`**

```python
# ── Field formats (spec §4.2) ────────────────────────────────────────────────

_REPEATER_TYPE_FORMAT: dict[str | None, str] = {
    "string": "plain", "inline": "inline", "richtext": "rich", "url": "plain", "tags": "plain",
}
_FIXED_FORMATS: dict[str, dict[str, str]] = {
    "text_block": {"title": "inline", "body": "rich"},
    "image": {"alt": "plain"},
    "floor_plan": {"alt": "plain"},
    "file_download": {"filename": "plain"},
}


class RichTextFieldError(ValueError):
    """A leaf exceeded its format's length limit; carries the leaf path."""

    def __init__(self, path: str, length: int, limit: int) -> None:
        super().__init__(f"Field {path} is too long ({length} > {limit} characters)")
        self.path = path
        self.length = length
        self.limit = limit


def _kv_formats(content: dict) -> dict[str, str]:
    raw = content.get("_formats") if isinstance(content, dict) else None
    if not isinstance(raw, dict):
        return {}
    return {k: v for k, v in raw.items() if isinstance(k, str) and v in FORMATS}


def format_of(service_type: str, path: str, content: dict) -> Format:
    """Format of one leaf path as produced by segments.segments_of."""
    fixed = _FIXED_FORMATS.get(service_type)
    if fixed is not None:
        return fixed.get(path, "plain")  # type: ignore[return-value]
    if service_type == "key_value" and path.startswith("entries."):
        return _kv_formats(content).get(path[len("entries."):], "plain")  # type: ignore[return-value]
    if service_type == "repeater" and path.startswith("items."):
        from .segments import repeater_schema

        parts = path.split(".")
        if len(parts) != 3:  # tags leaves: items.<id>.<key>.<j>
            return "plain"
        return _REPEATER_TYPE_FORMAT.get(repeater_schema(content).get(parts[2]), "plain")  # type: ignore[return-value]
    return "plain"


def field_formats(service_type: str, content: dict) -> dict[str, str]:
    """Per-field (not per-item) formats for the dashboard (spec §5.7)."""
    fixed = _FIXED_FORMATS.get(service_type)
    if fixed is not None:
        return dict(fixed)
    if service_type == "repeater":
        from .segments import repeater_schema

        return {
            key: _REPEATER_TYPE_FORMAT.get(ftype, "plain")
            for key, ftype in repeater_schema(content if isinstance(content, dict) else {}).items()
        }
    if service_type == "key_value":
        content = content if isinstance(content, dict) else {}
        fmts = _kv_formats(content)
        entries = content.get("entries")
        keys = list(entries.keys()) if isinstance(entries, dict) else []
        out = {k: fmts.get(k, "plain") for k in keys}
        out.update({k: v for k, v in fmts.items() if k not in out})
        out["*"] = "plain"
        return out
    return {}


def normalize_content(
    service_type: str, content: dict, *, legacy: bool = False, enforce_limit: bool = True
) -> dict:
    """Return a copy of `content` with every inline/rich leaf canonicalised."""
    import copy

    from .segments import apply_segments, segments_of

    if not isinstance(content, dict):
        return content
    values: dict[str, str] = {}
    for path, value in segments_of(service_type, content).items():
        fmt = format_of(service_type, path, content)
        if fmt == "plain":
            continue
        try:
            values[path] = canonicalize(value, fmt, legacy=legacy, enforce_limit=enforce_limit)
        except RichTextTooLong as exc:
            raise RichTextFieldError(path, exc.length, exc.limit) from exc
    return apply_segments(copy.deepcopy(content), service_type, values)
```

- [ ] **Step 5: Run the new tests and the existing segment/translation tests**

Run: `python -m pytest auth_service/tests/test_rich_text_formats.py auth_service/tests/test_segments.py auth_service/tests/test_segments_apply.py auth_service/tests/test_translation_sync.py -q`
Expected: all pass. `test_formats_marks_richtext_as_markdown` must still pass, because version 0 is unchanged.

- [ ] **Step 6: Commit**

```bash
git add backend/auth_service/services/rich_text.py backend/auth_service/services/segments.py backend/auth_service/tests/test_rich_text_formats.py
git commit -m "feat(backend): rich-text field format model and content normaliser"
```

---

### Task 5: Save path, structure policy, service detail, admin fields

**Files:**
- Create: `backend/auth_service/services/content_structure.py`
- Modify: `backend/auth_service/routers/deps.py:27` (project select)
- Modify: `backend/auth_service/routers/workspace.py` (`get_service`, `save_service`, `add_service`)
- Modify: `backend/auth_service/models/schemas.py` (`ServiceDetailOut`, `RepeaterItemField`, `ServiceCreateRequest`, `AdminProjectPatchIn`)
- Test: `backend/auth_service/tests/test_content_structure.py`, `backend/auth_service/tests/test_rich_text_save.py`

**Interfaces:**
- Consumes: `normalize_content`, `RichTextFieldError`, `field_formats`, `FORMATS` (Task 4).
- Produces:
  - `content_structure.apply_structure_rules(service_type: str, content: dict, *, is_admin: bool, stored: tuple) -> dict` (raises `StructureError`)
  - `content_structure.VALID_REPEATER_TYPES`
  - `ServiceDetailOut.rich_text_version: int`, `.can_edit_structure: bool`, `.field_formats: dict[str, str] | None`
  - `ServiceCreateRequest.formats: dict[str, Literal["plain","inline","rich"]] | None`
  - `AdminProjectPatchIn.rich_text_version: int | None` (0 or 1)
  - The project dict from `require_project_access` includes `rich_text_version`.

- [ ] **Step 1: Write the failing structure-policy tests**

`backend/auth_service/tests/test_content_structure.py`:

```python
import pytest

from auth_service.services.content_structure import StructureError, apply_structure_rules

STORED_SCHEMA = [{"key": "t", "label": "T", "type": "string"}]
NEW_SCHEMA = [{"key": "t", "label": "T", "type": "inline"}]


def test_client_cannot_change_repeater_schema():
    out = apply_structure_rules(
        "repeater", {"_schema": NEW_SCHEMA, "items": []}, is_admin=False,
        stored=({"_schema": STORED_SCHEMA, "items": []},),
    )
    assert out["_schema"] == STORED_SCHEMA


def test_admin_can_change_repeater_schema():
    out = apply_structure_rules(
        "repeater", {"_schema": NEW_SCHEMA, "items": []}, is_admin=True,
        stored=({"_schema": STORED_SCHEMA},),
    )
    assert out["_schema"] == NEW_SCHEMA


def test_missing_schema_is_grafted_for_everyone():
    for admin in (True, False):
        out = apply_structure_rules(
            "repeater", {"items": []}, is_admin=admin, stored=(None, {"_schema": STORED_SCHEMA})
        )
        assert out["_schema"] == STORED_SCHEMA


def test_admin_invalid_repeater_type_rejected():
    with pytest.raises(StructureError):
        apply_structure_rules(
            "repeater", {"_schema": [{"key": "t", "label": "T", "type": "html"}], "items": []},
            is_admin=True, stored=(),
        )


def test_client_cannot_change_formats_and_cannot_inject_them():
    out = apply_structure_rules(
        "key_value", {"entries": {"a": "x"}, "_formats": {"a": "rich"}}, is_admin=False,
        stored=({"entries": {"a": "x"}, "_formats": {"a": "inline"}},),
    )
    assert out["_formats"] == {"a": "inline"}
    out2 = apply_structure_rules(
        "key_value", {"entries": {"a": "x"}, "_formats": {"a": "rich"}}, is_admin=False, stored=({},)
    )
    assert "_formats" not in out2


def test_admin_payload_without_formats_keeps_stored():
    out = apply_structure_rules(
        "key_value", {"entries": {"a": "x"}}, is_admin=True, stored=({"_formats": {"a": "rich"}},)
    )
    assert out["_formats"] == {"a": "rich"}


def test_admin_formats_validated_and_pruned_to_entries():
    out = apply_structure_rules(
        "key_value", {"entries": {"a": "x"}, "_formats": {"a": "rich", "gone": "inline"}},
        is_admin=True, stored=(),
    )
    assert out["_formats"] == {"a": "rich"}
    with pytest.raises(StructureError):
        apply_structure_rules(
            "key_value", {"entries": {"a": "x"}, "_formats": {"a": "bold"}}, is_admin=True, stored=()
        )


def test_other_types_untouched():
    c = {"title": "x"}
    assert apply_structure_rules("text_block", c, is_admin=False, stored=()) is c
```

- [ ] **Step 2: Implement `services/content_structure.py`**

```python
"""Structural metadata policy for CMS content (ADR-0010).

`_schema` (repeater field definitions) and `_formats` (key_value per-entry
formats) decide how fields are edited and rendered, so only admins/agents may
change them. A client save always keeps the stored values; any payload that
omits them keeps the stored ones (the connector's items-only seed PUT)."""

from __future__ import annotations

from .rich_text import FORMATS

VALID_REPEATER_TYPES = frozenset({"string", "inline", "richtext", "url", "tags"})


class StructureError(ValueError):
    """Invalid admin-supplied structure (→ HTTP 422)."""


def _first(stored: tuple, key: str, kind: type):
    for blob in stored:
        if isinstance(blob, dict):
            val = blob.get(key)
            if isinstance(val, kind) and val:
                return val
    return None


def _validate_schema(schema: object) -> None:
    if schema is None:
        return
    if not isinstance(schema, list):
        raise StructureError("_schema must be a list")
    for field in schema:
        if not isinstance(field, dict) or not isinstance(field.get("key"), str):
            raise StructureError("_schema entries need a string 'key'")
        if field.get("type") not in VALID_REPEATER_TYPES:
            raise StructureError(
                f"_schema field '{field.get('key')}' has invalid type {field.get('type')!r}; "
                f"allowed: {', '.join(sorted(VALID_REPEATER_TYPES))}"
            )


def _validate_formats(formats: object) -> None:
    if not isinstance(formats, dict):
        raise StructureError("_formats must be an object")
    for key, fmt in formats.items():
        if fmt not in FORMATS:
            raise StructureError(f"_formats['{key}'] must be one of {', '.join(FORMATS)}")


def apply_structure_rules(
    service_type: str, content: dict, *, is_admin: bool, stored: tuple
) -> dict:
    if not isinstance(content, dict):
        return content
    if service_type == "repeater":
        stored_schema = _first(stored, "_schema", list)
        incoming = content.get("_schema")
        has_incoming = isinstance(incoming, list) and bool(incoming)
        if (not is_admin or not has_incoming) and stored_schema is not None:
            return {**content, "_schema": stored_schema}
        if is_admin and has_incoming:
            _validate_schema(incoming)
        return content
    if service_type == "key_value":
        stored_formats = _first(stored, "_formats", dict)
        if not is_admin or "_formats" not in content:
            if stored_formats is not None:
                return {**content, "_formats": stored_formats}
            return {k: v for k, v in content.items() if k != "_formats"}
        incoming = content.get("_formats") or {}
        _validate_formats(incoming)
        entries = content.get("entries")
        keys = set(entries.keys()) if isinstance(entries, dict) else set()
        return {**content, "_formats": {k: v for k, v in incoming.items() if k in keys}}
    return content
```

Run: `python -m pytest auth_service/tests/test_content_structure.py -q` → all pass.

- [ ] **Step 3: Write the failing save-path tests**

`backend/auth_service/tests/test_rich_text_save.py`. It reuses the side-effect ordering from `test_workspace_save.py::test_put_service_writes_to_draft_content_only` (svc row → locale rows → upsert → re-fetch) and patches `require_project_access` to add `rich_text_version`:

```python
from unittest.mock import MagicMock

import pytest

from auth_service.models.schemas import UserOut

SVC_TEXT = {
    "id": "svc-1", "service_key": "hero", "label": "Hero", "display_order": 1,
    "page_name": "General", "service_type_slug": "text_block",
    "service_types": {"name": "Text block", "icon": "Box", "schema": {}},
}


def _project(version):
    def fake(slug, user):
        return {"id": f"project-{slug}", "slug": slug, "default_locale": "en",
                "locales": ["en"], "rich_text_version": version}
    return fake


def _refetch(content):
    return MagicMock(data={**SVC_TEXT, "content_entries": {
        "draft_content": content, "published_content": {}, "updated_at": "2026-09-27T10:00:00Z"}})


def _content_upserts(mock_supabase):
    return [c.args[0] for c in mock_supabase.upsert.call_args_list
            if isinstance(c.args[0], dict) and "project_service_id" in c.args[0]]


@pytest.fixture
def client_as(auth_as, monkeypatch, client_user):
    def _set(version, user=None):
        auth_as(user or client_user)
        monkeypatch.setattr("auth_service.routers.workspace.require_project_access", _project(version))
    return _set


def test_version0_saves_values_verbatim(mock_supabase, client, client_as):
    client_as(0)
    mock_supabase.execute.side_effect = [MagicMock(data=SVC_TEXT), MagicMock(data=[]),
                                         MagicMock(data=[{}]), _refetch({})]
    res = client.put("/projects/demo/services/hero",
                     json={"content": {"title": "A & B", "body": "**x**"}})
    assert res.status_code == 200
    assert _content_upserts(mock_supabase)[0]["draft_content"] == {"title": "A & B", "body": "**x**"}


def test_version1_canonicalises_inline_and_rich(mock_supabase, client, client_as):
    client_as(1)
    mock_supabase.execute.side_effect = [MagicMock(data=SVC_TEXT), MagicMock(data=[]),
                                         MagicMock(data=[{}]), _refetch({})]
    res = client.put("/projects/demo/services/hero", json={"content": {
        "title": "A & <b>B</b>", "body": '<p onclick="x">Hi<script>alert(1)</script></p><p></p>'}})
    assert res.status_code == 200
    assert _content_upserts(mock_supabase)[0]["draft_content"] == {
        "title": "A &amp; <strong>B</strong>", "body": "<p>Hi</p>"}


def test_version1_too_long_is_422_with_path(mock_supabase, client, client_as):
    client_as(1)
    mock_supabase.execute.side_effect = [MagicMock(data=SVC_TEXT), MagicMock(data=[])]
    res = client.put("/projects/demo/services/hero", json={"content": {"title": "x" * 2001}})
    assert res.status_code == 422
    assert res.json()["detail"] == "Field title is too long (2001 > 2000 characters)"
    assert _content_upserts(mock_supabase) == []


def test_client_cannot_change_key_value_formats(mock_supabase, client, client_as):
    client_as(1)
    svc_kv = {**SVC_TEXT, "service_type_slug": "key_value"}
    stored = {"entries": {"about": "x"}, "_formats": {"about": "inline"}}
    mock_supabase.execute.side_effect = [
        MagicMock(data=svc_kv),
        MagicMock(data=[{"id": "r1", "locale": "en", "draft_content": stored,
                         "published_content": stored, "translation_meta": {}}]),
        MagicMock(data=[{}]), _refetch(stored)]
    res = client.put("/projects/demo/services/hero", json={"content": {
        "entries": {"about": "<p>y</p>"}, "_formats": {"about": "rich"}}})
    assert res.status_code == 200
    draft = _content_upserts(mock_supabase)[0]["draft_content"]
    assert draft["_formats"] == {"about": "inline"}
    assert draft["entries"]["about"] == "y"  # canonicalised as inline, block unwrapped


def test_admin_invalid_formats_is_422(mock_supabase, client, client_as, admin_user):
    client_as(1, admin_user)
    svc_kv = {**SVC_TEXT, "service_type_slug": "key_value"}
    mock_supabase.execute.side_effect = [MagicMock(data=svc_kv), MagicMock(data=[])]
    res = client.put("/projects/demo/services/hero",
                     json={"content": {"entries": {"a": "x"}, "_formats": {"a": "bold"}}})
    assert res.status_code == 422


def test_get_service_exposes_formats_version_and_structure_flag(mock_supabase, client, client_as):
    client_as(1)
    mock_supabase.execute.return_value = _refetch({"title": "t"})
    body = client.get("/projects/demo/services/hero").json()
    assert body["rich_text_version"] == 1
    assert body["field_formats"] == {"title": "inline", "body": "rich"}
    assert body["can_edit_structure"] is False
```

If the `admin_user` fixture's `is_admin` flag isn't `True`, check `tests/conftest.py` and use the fixture that is.

- [ ] **Step 4: Implement the save/read changes**

1. `routers/deps.py` project select: append `, rich_text_version` to the column list.
2. `models/schemas.py`:
   - `ServiceDetailOut`: add `rich_text_version: int = 0`, `can_edit_structure: bool = False`, `field_formats: dict[str, str] | None = None`.
   - `RepeaterItemField.type`: update the comment to `# "string" | "inline" | "richtext" | "url" | "tags"`.
   - `ServiceCreateRequest`: add `formats: dict[str, Literal["plain", "inline", "rich"]] | None = None  # key_value per-entry formats`. Import `Literal` if needed.
   - `AdminProjectPatchIn`: add `rich_text_version: int | None = Field(default=None, ge=0, le=1)`.
3. `routers/workspace.py`:
   - Imports: `from ..services.content_structure import StructureError, VALID_REPEATER_TYPES, apply_structure_rules` and `from ..services.rich_text import RichTextFieldError, field_formats, normalize_content`.
   - `get_service`: after `flat["translation_status"] = …`, add:
     ```python
     flat["rich_text_version"] = int(project.get("rich_text_version") or 0)
     flat["can_edit_structure"] = bool(getattr(user, "is_admin", False))
     flat["field_formats"] = field_formats(result.data["service_type_slug"], flat.get("content") or {})
     ```
   - `save_service`: replace the whole `content_in = body.content` / `if service_type == "repeater": … _grafted_repeater_content(...)` block with:
     ```python
     version = int(project.get("rich_text_version") or 0)
     d = by_locale.get(default_locale) or {}
     t = by_locale.get(loc) or {}
     try:
         content_in = apply_structure_rules(
             service_type,
             body.content,
             is_admin=bool(getattr(user, "is_admin", False)),
             stored=(d.get("draft_content"), d.get("published_content"),
                     t.get("draft_content"), t.get("published_content")),
         )
         if version >= 1:
             content_in = normalize_content(service_type, content_in)
     except StructureError as exc:
         raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
     except RichTextFieldError as exc:
         raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
     ```
     Keep `_repeater_schema_of` / `_grafted_repeater_content` only if other code or tests still import them (grep). If they don't, delete them — this change orphans them.
   - In the same function, pass `rich_text_version=version` to the `sync_locale_draft(...)` call. The parameter itself lands in Task 6; until then, leave this one call-site change for Task 6 and mention it in your report.
   - `add_service`:
     - Replace `valid_field_types = {"string", "richtext", "url", "tags"}` with `valid_field_types = VALID_REPEATER_TYPES`.
     - After the repeater seeding block, add: when `body.service_type_slug == "key_value" and body.formats`, fetch the new service id the same way the repeater branch does, then insert a default-locale row with `{"entries": {}, "_formats": body.formats}` as both draft and published.
4. Run `python -m pytest auth_service/tests/test_rich_text_save.py auth_service/tests/test_content_structure.py auth_service/tests/test_workspace_save.py auth_service/tests/test_repeater_schema_preserved.py auth_service/tests/test_service_create_validation.py -q`.

    Expected: all pass. If a pre-existing test asserts that a **non-admin** can change `_schema`, it encodes the old policy. Update that test to the ADR-0010 policy, and say so in your report.

- [ ] **Step 5: Full backend suite**

Run: `cd .. && make test-backend`
Expected: green.

- [ ] **Step 6: Commit**

```bash
git add backend/auth_service
git commit -m "feat(backend): rich-text save path, structure policy and service detail formats"
```

---

### Task 6: Translation — version-aware formats, re-canonicalisation, DeepL chunking

**Files:**
- Modify: `backend/auth_service/translation/sync.py`
- Modify: `backend/auth_service/translation/deepl.py`
- Modify: `backend/auth_service/routers/workspace.py` (three `sync_locale_draft` calls)
- Test: `backend/auth_service/tests/test_translation_sync.py` (add cases), `backend/auth_service/tests/test_deepl_chunking.py`

**Interfaces:**
- Consumes: `formats_of(..., rich_text_version)` and `format_of` (Task 4); `canonicalize` (Task 2).
- Produces: `sync_locale_draft(..., rich_text_version: int = 0)` as a keyword-only trailing parameter; `DeepLProvider` splits requests larger than 100 KiB.

- [ ] **Step 1: Add the failing sync tests**

Append to `test_translation_sync.py`. `_UpperProvider` already exists in that file; reuse it. The HTML-producing fake below is new:

```python
class _HtmlSoupProvider:
    """Returns translations with junk markup, like a misbehaving engine."""

    name = "soup"

    def __init__(self):
        self.calls = []

    def translate(self, texts, *, source, target, fmt="text"):
        self.calls.append(fmt)
        return [t.replace("<strong>", '<strong style="color:red"><span>') .replace("</strong>", "</span></strong>") + "<script>x</script>" if fmt == "html" else t.upper() for t in texts]


def test_v1_translates_rich_leaves_as_html_and_recanonicalises():
    p = _HtmlSoupProvider()
    new, meta = sync_locale_draft(
        "text_block", {"title": "A &amp; <strong>B</strong>", "body": "<p>x</p>"}, None, None, None,
        p, "en", "de", rich_text_version=1,
    )
    assert p.calls == ["html"]
    assert new["title"] == "A &amp; <strong>B</strong>"
    assert new["body"] == "<p>x</p>"


def test_v0_behaviour_unchanged():
    p = _UpperProvider()
    new, _ = sync_locale_draft("text_block", {"title": "a", "body": "b"}, None, None, None, p, "en", "de")
    assert new == {"title": "A", "body": "B"}


def test_v1_overlong_translation_is_kept_not_raised():
    class Longer:
        name = "long"

        def translate(self, texts, *, source, target, fmt="text"):
            return [t + ("x" * 3000) for t in texts]

    new, _ = sync_locale_draft("text_block", {"title": "t"}, None, None, None, Longer(), "en", "de", rich_text_version=1)
    assert len(new["title"]) > 2000
```

If `_UpperProvider` records calls under a different attribute name, adapt `p.calls` to it.

- [ ] **Step 2: Implement in `translation/sync.py`**

- Add a keyword-only parameter `*, rich_text_version: int = 0` after `target_locale`.
- `fmts = formats_of(service_type, default_content, rich_text_version)`.
- In the batch loop, after `translated = provider.translate(...)`, write:
  ```python
  for path, text in zip(group, translated, strict=True):
      if fmt == "html":
          text = canonicalize(text, format_of(service_type, path, default_content), enforce_limit=False)
      values[path] = text
  ```
  Import `canonicalize, format_of` from `..services.rich_text`.
- Update the docstring: "Version ≥ 1: inline/rich leaves are translated as HTML and the engine output is re-canonicalised."

- [ ] **Step 3: Pass the version at every call site**

In `routers/workspace.py`:
- `save_service` → `rich_text_version=version`.
- `set_project_locales` → `rich_text_version=int(project.get("rich_text_version") or 0)`.
- `retranslate_service` → the same expression.

Run: `grep -n "sync_locale_draft(" backend/auth_service/routers/workspace.py` and confirm each of the three calls passes it.

- [ ] **Step 4: Write the failing DeepL chunking test**

`backend/auth_service/tests/test_deepl_chunking.py`:

```python
import json
from unittest.mock import MagicMock, patch

from auth_service.translation.deepl import DeepLProvider


def _fake_urlopen(sent):
    def _open(req):
        body = json.loads(req.data.decode())
        sent.append(len(req.data))
        resp = MagicMock()
        resp.__enter__.return_value.read.return_value = json.dumps(
            {"translations": [{"text": f"T:{t}"} for t in body["text"]]}
        ).encode()
        return resp
    return _open


def test_large_batches_are_split_and_order_preserved():
    texts = [f"<p>{i}:" + ("é" * 30_000) + "</p>" for i in range(8)]  # ~480 KB total
    sent = []
    with patch("auth_service.translation.deepl.urllib.request.urlopen", side_effect=_fake_urlopen(sent)):
        out = DeepLProvider(api_key="k:fx").translate(texts, source="en", target="de", fmt="html")
    assert out == [f"T:{t}" for t in texts]
    assert len(sent) > 1
    assert all(size <= 110 * 1024 for size in sent)


def test_small_batch_is_one_request():
    sent = []
    with patch("auth_service.translation.deepl.urllib.request.urlopen", side_effect=_fake_urlopen(sent)):
        DeepLProvider(api_key="k:fx").translate(["a", "b"], source="en", target="de")
    assert len(sent) == 1
```

- [ ] **Step 5: Implement chunking in `translation/deepl.py`**

- Add `_MAX_REQUEST_BYTES = 100 * 1024`.
- Move the request/response code into `def _post(self, masked: list[str], *, source: str, target: str, fmt: TextFormat) -> list[str]`. It builds the payload exactly as today, encodes the body with `json.dumps(payload, ensure_ascii=False).encode("utf-8")`, and keeps the count check per request.
- In `translate`, split the masked texts into consecutive index groups whose sum of `len(json.dumps(t, ensure_ascii=False).encode("utf-8")) + 1` stays ≤ `_MAX_REQUEST_BYTES`. A single oversize text forms its own group. Call `_post` per group, concatenate the results in order, then `restore()` each with its token map.
- Update the module docstring's "batches all texts into one request" to "batches texts into requests of at most 100 KiB".

- [ ] **Step 6: Run the translation tests and the full backend suite**

Run: `python -m pytest auth_service/tests/test_translation_sync.py auth_service/tests/test_deepl_chunking.py auth_service/tests/test_deepl_provider.py auth_service/tests/test_workspace_autotranslate.py -q && cd .. && make test-backend`
Expected: green.

- [ ] **Step 7: Commit**

```bash
git add backend/auth_service
git commit -m "feat(backend): translate rich text as HTML, re-sanitise output, chunk DeepL requests"
```

---

### Task 7: Public content endpoints expose `rich_text_version`

**Files:**
- Modify: `backend/auth_service/routers/content.py`
- Test: `backend/auth_service/tests/test_content.py` (add cases)

**Interfaces:**
- Produces: a top-level `"rich_text_version": int` in the responses of `GET /content/{slug}`, `/content/{slug}/draft`, `/content/{slug}/{locale}` and `/content/{slug}/{locale}/draft`. The `/types` `.d.ts` output declares it.

- [ ] **Step 1: Write the failing tests**

Add to `test_content.py`, following that file's existing mocking of the project row and services. Two cases:
- (a) A project row with `"rich_text_version": 1` → `res.json()["rich_text_version"] == 1` for `/content/demo`.
- (b) A project row without the key → `0`.

Add the same assertion to one locale-endpoint test.

- [ ] **Step 2: Implement**

- Add `rich_text_version` to the project select at `content.py:34`.
- Add `"rich_text_version": int(project.get("rich_text_version") or 0),` to all four `payload = {` dicts, directly after `"project_slug"`.
- If the ETag is derived from anything narrower than the full payload (read the ETag code), make sure it also varies with `rich_text_version`. The migration bumps `updated_at` on every touched row anyway.
- In `get_project_types`, add the line `"  rich_text_version: number;",` next to `last_updated`. Also add a comment line above the content map type: `"  // inline/rich fields are sanitised HTML strings — render with the CMS rich-text kit (ADR-0010)"`.

- [ ] **Step 3: Audit other readers of CMS text (spec §5.11)**

Run: `grep -rn "draft_content\|published_content" backend/auth_service --include=*.py | grep -v tests/`. For every reader outside `content.py`, `workspace.py`, `publish.py`, `segments.py`, `rich_text*.py` and `translation/`, check whether it puts a text leaf into an email, a notification, a log line or any other non-HTML output. Each such use must go through `plain_text(value, fmt)`; for email HTML, wrap it in `html.escape(plain_text(...))`. As of 2026-09-27 the only other reader, `forms.py`, reads only `email_config.destination_email`, which is plain. Record the audit result (file:line → verdict) in your report, even if nothing needed changing.

- [ ] **Step 4: Run**

Run: `python -m pytest auth_service/tests/test_content.py -q && cd .. && make test-backend`
Expected: green.

- [ ] **Step 5: Commit**

```bash
git add backend/auth_service
git commit -m "feat(content): expose rich_text_version to client sites"
```

---

### Task 8: Client kit — package, parser, canonical transform, serializer

**Files:**
- Create: `client-kit/rich-text/package.json`, `tsconfig.json`, `vitest.config.ts`
- Create: `client-kit/rich-text/src/parse.ts`, `src/href.ts`, `src/detect.ts`, `src/normalize.ts`, `src/serialize.ts`
- Test: `client-kit/rich-text/tests/canonical.test.ts`, `tests/parse.test.ts`

**Interfaces:**
- Consumes: `fixtures/canonical-vectors.json` (Task 2). The TS port must reproduce it exactly.
- Produces (used by Tasks 9–13):
  - `type RichNode = string | RichElement`; `interface RichElement { tag: string; href?: string | null; children: RichNode[] }`
  - `MARK_TAGS`, `INLINE_TAGS`, `HEADING_TAGS`, `BLOCK_TAGS` (`Set<string>`)
  - `parse(html: string): RichElement` (root tag `"#root"`)
  - `decodeEntities(s: string): string`
  - `safeHref(raw?: string | null): string | null`, `MAX_HREF_LENGTH`
  - `isHtml(value: string): boolean`
  - `normalizeInline(nodes: RichNode[]): RichNode[]`, `normalizeRich(nodes: RichNode[]): RichElement[]`
  - `serialize(nodes: RichNode[]): string`, `escapeText`, `escapeAttr`

- [ ] **Step 1: Package scaffolding**

`client-kit/rich-text/package.json`:
```json
{
  "name": "@cms/rich-text-kit",
  "version": "1.0.0",
  "private": true,
  "type": "module",
  "description": "Vendored rich-text renderer for CMS client sites (ADR-0010). Zero runtime deps besides React.",
  "scripts": { "test": "vitest run", "typecheck": "tsc --noEmit" },
  "peerDependencies": { "react": ">=18" },
  "devDependencies": {
    "@testing-library/react": "^16.1.0",
    "@types/react": "^19.0.0",
    "@types/react-dom": "^19.0.0",
    "jsdom": "^25.0.0",
    "react": "^19.2.0",
    "react-dom": "^19.2.0",
    "typescript": "^5.6.0",
    "vitest": "^4.1.4"
  }
}
```
`tsconfig.json`:
```json
{"compilerOptions": {"target": "ES2022", "module": "ESNext", "moduleResolution": "bundler", "jsx": "react-jsx", "strict": true, "noEmit": true, "resolveJsonModule": true, "esModuleInterop": true, "skipLibCheck": true, "lib": ["ES2022", "DOM"]}, "include": ["src", "tests"]}
```
`vitest.config.ts`:
```ts
import { defineConfig } from "vitest/config";
export default defineConfig({ test: { environment: "jsdom", include: ["tests/**/*.test.ts?(x)"] } });
```
Run `cd client-kit/rich-text && npm install`, then commit the generated `package-lock.json`.

- [ ] **Step 2: Write the failing tests**

`tests/canonical.test.ts`:
```ts
import { describe, expect, it } from "vitest";
import vectors from "../fixtures/canonical-vectors.json";
import { parse } from "../src/parse";
import { normalizeInline, normalizeRich } from "../src/normalize";
import { serialize } from "../src/serialize";

type Vec = { name: string; fmt: "inline" | "rich"; input: string; expected: string };

const canonical = (input: string, fmt: "inline" | "rich") => {
  const root = parse(input);
  return serialize(fmt === "inline" ? normalizeInline(root.children) : normalizeRich(root.children));
};

describe("canonical vectors (shared with backend)", () => {
  for (const v of vectors as Vec[]) {
    it(v.name, () => expect(canonical(v.input, v.fmt)).toBe(v.expected));
    it(`${v.name} (idempotent)`, () => {
      const once = canonical(v.input, v.fmt);
      expect(canonical(once, v.fmt)).toBe(once);
    });
  }
});
```
`tests/parse.test.ts`:
```ts
import { describe, expect, it } from "vitest";
import { decodeEntities, parse } from "../src/parse";
import { safeHref } from "../src/href";
import { isHtml } from "../src/detect";

describe("decodeEntities", () => {
  it("decodes the basic and numeric entities exactly once", () => {
    expect(decodeEntities("&amp;amp; &lt; &gt; &quot; &#39; &apos; &nbsp; &#x1F600; &#65;")).toBe(
      "&amp; < > \" ' '   😀 A");
  });
  it("leaves unknown named entities literal", () => expect(decodeEntities("&bogus;")).toBe("&bogus;"));
  it("replaces invalid code points", () => expect(decodeEntities("&#xD800;&#0;")).toBe("��"));
});

describe("parse", () => {
  it("keeps a literal less-than", () => expect(parse("a < b").children).toEqual(["a < b"]));
  it("reads quoted attributes containing >", () => {
    const a = parse('<a href="https://x.ro/?q=a>b">t</a>').children[0];
    expect(a).toMatchObject({ tag: "a", href: "https://x.ro/?q=a>b" });
  });
  it("drops raw-text elements even when unclosed", () => expect(parse("x<script>alert(1)").children).toEqual(["x"]));
  it("never produces non-allow-listed tags", () => {
    const tags: string[] = [];
    const walk = (n: unknown) => {
      if (typeof n !== "string") {
        const e = n as { tag: string; children: unknown[] };
        tags.push(e.tag);
        e.children.forEach(walk);
      }
    };
    walk(parse('<div><img src=x onerror=1><iframe src=x></iframe><table><tr><td>a</td></tr></table><span>b</span></div>'));
    const allowed = ["#root", "p", "br", "hr", "strong", "em", "u", "s", "a", "ul", "ol", "li", "h2", "h3", "h4", "blockquote"];
    expect(tags.every((t) => allowed.includes(t))).toBe(true);
  });
});

describe("safeHref", () => {
  it.each([
    ["https://a.ro", "https://a.ro"], ["mailto:a@b.ro", "mailto:a@b.ro"], ["tel:+40", "tel:+40"],
    ["#x", "#x"], ["/p", "/p"], ["//e.com", null], ["/\\e.com", null], ["javascript:x", null],
    ["java\u0000script:x", null], [" JAVASCRIPT:x", null], ["data:x", null], ["", null], [null, null],
  ])("%s", (raw, expected) => expect(safeHref(raw as string | null)).toBe(expected));
});

describe("isHtml", () => {
  it.each([["<p>x</p>", true], ["<BR/>", true], ["a < b", false], ["<abbr>", false], ["Tom &amp; Jerry", false]])(
    "%s", (v, e) => expect(isHtml(v as string)).toBe(e));
});
```
Run `npx vitest run` → fails (modules missing).

- [ ] **Step 3: Implement `src/detect.ts` and `src/href.ts`**

```ts
// src/detect.ts
const HTML_RE = /<(?:p|br|strong|em|u|s|a|ul|ol|li|h[1-6]|blockquote|hr|b|i|div|span)\b[^>]*>/i;
/** True when `value` contains at least one recognised HTML tag (spec §4.4). */
export function isHtml(value: string): boolean {
  return HTML_RE.test(value);
}
```
```ts
// src/href.ts
const CTRL = /[\x00-\x1f\x7f]/g;
export const MAX_HREF_LENGTH = 2048;
/** Cleaned href when its scheme is allowed, else null (default deny). Mirrors backend safe_href. */
export function safeHref(raw?: string | null): string | null {
  if (!raw) return null;
  const v = raw.replace(CTRL, "").trim();
  if (!v || v.length > MAX_HREF_LENGTH) return null;
  const probe = v.replace(/ /g, "").toLowerCase();
  if (/^(https?:\/\/|mailto:|tel:)/.test(probe)) return v;
  if (v.startsWith("#")) return v;
  if (v.startsWith("/") && !v.startsWith("//") && !v.startsWith("/\\")) return v;
  return null;
}
```

- [ ] **Step 4: Implement `src/parse.ts`**

```ts
export type RichNode = string | RichElement;
export interface RichElement {
  tag: string;
  href?: string | null;
  children: RichNode[];
}

export const MARK_TAGS = new Set(["strong", "em", "u", "s"]);
export const INLINE_TAGS = new Set(["strong", "em", "u", "s", "a", "br"]);
export const HEADING_TAGS = new Set(["h2", "h3", "h4"]);
export const BLOCK_TAGS = new Set(["p", "ul", "ol", "li", "blockquote", "hr", "h2", "h3", "h4"]);
const RICH_TAGS = new Set([...INLINE_TAGS, ...BLOCK_TAGS]);

const SYNONYMS: Record<string, string> = {
  b: "strong", i: "em", strike: "s", del: "s", ins: "u", h1: "h2", h5: "h4", h6: "h4", div: "p",
};
const DROP_WITH_CONTENT = new Set([
  "script", "style", "iframe", "object", "svg", "math", "template", "noscript", "head",
  "title", "textarea", "select", "button", "canvas", "audio", "video", "picture",
]);
/** Elements whose content is text, not markup (the backend HTMLParser's CDATA mode). */
const RAW_TEXT = new Set(["script", "style"]);
const TAG_RE = /<(\/?)([a-zA-Z][a-zA-Z0-9:-]*)((?:[^>"']|"[^"]*"|'[^']*')*?)(\/?)>/y;
const HREF_RE = /(?:^|\s)href\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s"'=<>`]+))/i;
const NAMED: Record<string, string> = { amp: "&", lt: "<", gt: ">", quot: '"', apos: "'", nbsp: " " };

export function decodeEntities(s: string): string {
  return s.replace(/&(#[xX][0-9a-fA-F]+|#[0-9]+|[a-zA-Z][a-zA-Z0-9]*);/g, (m, e: string) => {
    if (e[0] === "#") {
      const cp = e[1] === "x" || e[1] === "X" ? parseInt(e.slice(2), 16) : parseInt(e.slice(1), 10);
      const ok = cp > 0 && cp <= 0x10ffff && !(cp >= 0xd800 && cp <= 0xdfff);
      return ok ? String.fromCodePoint(cp) : "�";
    }
    return NAMED[e] ?? m;
  });
}

/** Tag-soup tolerant parser keeping only allow-listed elements. Mirrors backend _Builder. */
export function parse(html: string): RichElement {
  const root: RichElement = { tag: "#root", children: [] };
  const stack: RichElement[] = [root];
  const lower = html.toLowerCase();
  const n = html.length;
  let skip = 0;
  let i = 0;

  const text = (t: string) => {
    if (skip || !t) return;
    const kids = stack[stack.length - 1].children;
    const last = kids[kids.length - 1];
    if (typeof last === "string") kids[kids.length - 1] = last + t;
    else kids.push(t);
  };
  const open = (raw: string, attrs: string) => {
    if (DROP_WITH_CONTENT.has(raw)) { skip++; return; }
    if (skip) return;
    const tag = SYNONYMS[raw] ?? raw;
    if (tag === "br" || tag === "hr") { stack[stack.length - 1].children.push({ tag, children: [] }); return; }
    if (!RICH_TAGS.has(tag)) return;
    let node: RichElement;
    if (tag === "a") {
      const h = HREF_RE.exec(attrs);
      node = { tag, href: h ? decodeEntities(h[1] ?? h[2] ?? h[3] ?? "") : null, children: [] };
    } else {
      node = { tag, children: [] };
    }
    stack[stack.length - 1].children.push(node);
    stack.push(node);
  };
  const close = (raw: string) => {
    if (DROP_WITH_CONTENT.has(raw)) { if (skip) skip--; return; }
    if (skip) return;
    const tag = SYNONYMS[raw] ?? raw;
    if (!RICH_TAGS.has(tag) || tag === "br" || tag === "hr") return;
    for (let k = stack.length - 1; k > 0; k--) {
      if (stack[k].tag === tag) { stack.length = k; return; }
    }
  };

  while (i < n) {
    const lt = html.indexOf("<", i);
    if (lt === -1) { text(decodeEntities(html.slice(i))); break; }
    if (lt > i) text(decodeEntities(html.slice(i, lt)));
    if (html.startsWith("<!--", lt)) { const end = html.indexOf("-->", lt + 4); i = end === -1 ? n : end + 3; continue; }
    if (html[lt + 1] === "!" || html[lt + 1] === "?") { const end = html.indexOf(">", lt); i = end === -1 ? n : end + 1; continue; }
    TAG_RE.lastIndex = lt;
    const m = TAG_RE.exec(html);
    if (!m) { text("<"); i = lt + 1; continue; }
    i = TAG_RE.lastIndex;
    const tag = m[2].toLowerCase();
    const selfClosing = m[4] === "/";
    if (m[1] === "/") { close(tag); continue; }
    if (RAW_TEXT.has(tag) && !selfClosing) {
      const endTag = lower.indexOf(`</${tag}`, i);
      if (endTag === -1) i = n;
      else { const gt = html.indexOf(">", endTag); i = gt === -1 ? n : gt + 1; }
      continue;
    }
    if (selfClosing) { if (!DROP_WITH_CONTENT.has(tag)) { open(tag, m[3]); close(tag); } continue; }
    open(tag, m[3]);
  }
  return root;
}
```

- [ ] **Step 5: Implement `src/normalize.ts` and `src/serialize.ts`**

These are line-for-line ports of `_inline`, `_tidy`, `_trim_edges`, `_blocks`, `_paragraph_nodes`, `_li`, `_list`, `_trim_empty_edges` and `_serialize` in `backend/auth_service/services/rich_text.py`. Keep that file open while writing them.

```ts
// src/normalize.ts — 1:1 port of the canonical transform in backend services/rich_text.py.
import { BLOCK_TAGS, HEADING_TAGS, INLINE_TAGS, MARK_TAGS, type RichElement, type RichNode } from "./parse";
import { safeHref } from "./href";

export const MAX_LIST_DEPTH = 4;
const WS = /[ \t\r\n\f]+/g;
const isEl = (n: RichNode | undefined): n is RichElement => n !== undefined && typeof n !== "string";
const br = (): RichElement => ({ tag: "br", children: [] });
const el = (tag: string, children: RichNode[] = []): RichElement => ({ tag, children });

export function hasContent(nodes: RichNode[]): boolean {
  return nodes.some((n) => (typeof n === "string" ? n.trim() !== "" : n.tag !== "br"));
}
function endsWithBr(nodes: RichNode[]): boolean {
  for (let k = nodes.length - 1; k >= 0; k--) {
    const n = nodes[k];
    if (typeof n === "string") {
      if (n.trim() === "") continue;
      return false;
    }
    return n.tag === "br";
  }
  return false;
}
function inline(nodes: RichNode[], inLink = false): RichNode[] {
  const out: RichNode[] = [];
  for (const n of nodes) {
    if (typeof n === "string") { out.push(n.replace(WS, " ")); continue; }
    const tag = n.tag;
    if (tag === "br") out.push(br());
    else if (MARK_TAGS.has(tag)) {
      const kids = inline(n.children, inLink);
      if (hasContent(kids)) out.push(el(tag, kids));
    } else if (tag === "a") {
      const kids = inline(n.children, true);
      const href = inLink ? null : safeHref(n.href);
      if (href && hasContent(kids)) out.push({ tag: "a", href, children: kids });
      else out.push(...kids);
    } else {
      const kids = tag === "hr" ? [] : inline(n.children, inLink);
      if (tag === "hr" || hasContent(kids)) {
        if (hasContent(out) && !endsWithBr(out)) out.push(br());
        out.push(...kids);
        if (!endsWithBr(out)) out.push(br());
      }
    }
  }
  return out;
}
function tidy(nodes: RichNode[]): RichNode[] {
  const res: RichNode[] = [];
  for (const n of nodes) {
    const last = res[res.length - 1];
    if (typeof n === "string") {
      let s = n;
      if (isEl(last) && last.tag === "br") s = s.replace(/^ +/, "");
      if (!s) continue;
      if (typeof last === "string") { res[res.length - 1] = (last + s).replace(WS, " "); continue; }
      res.push(s);
    } else {
      if (n.tag === "br" && typeof last === "string") {
        const t = last.replace(/ +$/, "");
        if (t) res[res.length - 1] = t;
        else res.pop();
      }
      res.push(n);
    }
  }
  return res;
}
const dropEdge = (n: RichNode) => (typeof n === "string" ? n.trim() === "" : n.tag === "br");
function trimEdges(nodes: RichNode[]): RichNode[] {
  const res = tidy(nodes);
  while (res.length && dropEdge(res[0])) res.shift();
  while (res.length && dropEdge(res[res.length - 1])) res.pop();
  if (typeof res[0] === "string") res[0] = res[0].replace(/^ +/, "");
  const l = res.length - 1;
  if (l >= 0 && typeof res[l] === "string") res[l] = (res[l] as string).replace(/ +$/, "");
  return res;
}
const isEmptyP = (n: RichElement) => n.tag === "p" && !hasContent(n.children);
function trimEmptyEdges(bs: RichElement[]): RichElement[] {
  let s = 0;
  let e = bs.length;
  while (s < e && isEmptyP(bs[s])) s++;
  while (e > s && isEmptyP(bs[e - 1])) e--;
  return bs.slice(s, e);
}
function paragraphNodes(children: RichNode[], depth: number): RichElement[] {
  if (children.some((c) => isEl(c) && BLOCK_TAGS.has(c.tag))) return blocks(children, depth);
  return [el("p", trimEdges(inline(children)))];
}
function blocks(nodes: RichNode[], depth: number): RichElement[] {
  const out: RichElement[] = [];
  let pending: RichNode[] = [];
  const flush = () => {
    if (pending.length) {
      const kids = trimEdges(inline(pending));
      if (hasContent(kids)) out.push(el("p", kids));
      pending = [];
    }
  };
  for (const n of nodes) {
    if (typeof n === "string" || INLINE_TAGS.has(n.tag)) { pending.push(n); continue; }
    flush();
    const tag = n.tag;
    if (tag === "p") out.push(...paragraphNodes(n.children, depth));
    else if (HEADING_TAGS.has(tag)) {
      const kids = trimEdges(inline(n.children));
      if (hasContent(kids)) out.push(el(tag, kids));
    } else if (tag === "hr") out.push(el("hr"));
    else if (tag === "ul" || tag === "ol") out.push(...list(n, depth + 1));
    else if (tag === "li") out.push(...list(el("ul", [n]), depth + 1));
    else if (tag === "blockquote") {
      const inner: RichElement[] = [];
      for (const b of trimEmptyEdges(blocks(n.children, depth))) {
        inner.push(...(b.tag === "blockquote" ? (b.children as RichElement[]) : [b]));
      }
      if (inner.length) out.push(el("blockquote", inner));
    }
  }
  flush();
  return out;
}
function li(children: RichNode[], depth: number): RichElement {
  const kept: RichElement[] = [];
  for (const b of blocks(children, depth)) {
    if (b.tag === "p" || b.tag === "ul" || b.tag === "ol") kept.push(b);
    else if (HEADING_TAGS.has(b.tag)) kept.push(el("p", b.children));
    else if (b.tag === "blockquote") {
      kept.push(...(b.children as RichElement[]).filter((x) => x.tag === "p" || x.tag === "ul" || x.tag === "ol"));
    }
  }
  if (!kept.length || kept[0].tag !== "p") kept.unshift(el("p"));
  return el("li", kept);
}
const liHasContent = (item: RichElement) =>
  item.children.some((c) => isEl(c) && (c.tag === "ul" || c.tag === "ol" || (c.tag === "p" && hasContent(c.children))));
function list(node: RichElement, depth: number): RichElement[] {
  let items: RichElement[] = [];
  for (const c of node.children) {
    if (typeof c === "string") { if (c.trim()) items.push(li([c], depth)); continue; }
    if (c.tag === "li") items.push(li(c.children, depth));
    else if ((c.tag === "ul" || c.tag === "ol") && items.length) items[items.length - 1].children.push(...list(c, depth + 1));
    else items.push(li([c], depth));
  }
  items = items.filter(liHasContent);
  if (!items.length) return [];
  if (depth > MAX_LIST_DEPTH) return items.flatMap((x) => x.children as RichElement[]);
  return [el(node.tag, items)];
}

export function normalizeInline(nodes: RichNode[]): RichNode[] {
  return trimEdges(inline(nodes));
}
export function normalizeRich(nodes: RichNode[]): RichElement[] {
  return trimEmptyEdges(blocks(nodes, 0));
}
```
```ts
// src/serialize.ts
import type { RichNode } from "./parse";

const WS = /[ \t\r\n\f]+/g;
export const escapeText = (s: string) =>
  s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/ /g, "&nbsp;");
export const escapeAttr = (s: string) => escapeText(s).replace(/"/g, "&quot;");

/** Canonical HTML string of a normalized tree (mirrors backend _serialize). */
export function serialize(nodes: RichNode[]): string {
  let out = "";
  let buf = "";
  const flush = () => {
    if (buf) { out += escapeText(buf.replace(WS, " ")); buf = ""; }
  };
  for (const n of nodes) {
    if (typeof n === "string") { buf += n; continue; }
    flush();
    if (n.tag === "br" || n.tag === "hr") out += `<${n.tag}>`;
    else if (n.tag === "a") out += `<a href="${escapeAttr(n.href ?? "")}">${serialize(n.children)}</a>`;
    else out += `<${n.tag}>${serialize(n.children)}</${n.tag}>`;
  }
  flush();
  return out;
}
```

- [ ] **Step 6: Run the kit tests**

Run: `cd client-kit/rich-text && npx vitest run && npx tsc --noEmit`
Expected: every canonical vector passes and TS compiles. If a vector fails only in TS, the port diverges from Python — fix the port. Never edit the fixture to suit TS.

- [ ] **Step 7: Commit**

```bash
git add client-kit/rich-text
git commit -m "feat(kit): rich-text parser and canonical transform (TS port)"
```

---

### Task 9: Client kit — legacy converter and `plainText`

**Files:**
- Create: `client-kit/rich-text/src/legacy.ts`, `src/plainText.ts`
- Test: `client-kit/rich-text/tests/legacy.test.ts`, `tests/plainText.test.ts`

**Interfaces:**
- Consumes: `fixtures/legacy-vectors.json` (Task 3), plus `escapeText`, `escapeAttr`, `safeHref`, `isHtml`, `parse` and `BLOCK_TAGS` (Task 8).
- Produces:
  - `legacyToHtml(text: string, fmt: "inline" | "rich"): string`
  - `plainText(value, opts?: { format?: "inline" | "rich"; keepLineBreaks?: boolean }): string`
  - `interface PlainTextOptions`

- [ ] **Step 1: Write the failing tests**

`tests/legacy.test.ts`:
```ts
import { describe, expect, it } from "vitest";
import vectors from "../fixtures/legacy-vectors.json";
import { legacyToHtml } from "../src/legacy";

type Vec = { name: string; fmt: "inline" | "rich"; input: string; expected: string };
describe("legacy vectors (shared with backend)", () => {
  for (const v of vectors as Vec[]) it(v.name, () => expect(legacyToHtml(v.input, v.fmt)).toBe(v.expected));
});
```
`tests/plainText.test.ts`:
```ts
import { describe, expect, it } from "vitest";
import { plainText } from "../src/plainText";

describe("plainText", () => {
  it("strips markup and decodes entities", () =>
    expect(plainText("<p>Tom &amp; <strong>Jerry</strong></p><p>2nd</p>", { format: "rich" })).toBe("Tom & Jerry 2nd"));
  it("inline breaks become spaces", () => expect(plainText("a<br>b")).toBe("a b"));
  it("keeps line breaks when asked", () =>
    expect(plainText("<p>a</p><ul><li><p>b</p></li></ul>", { format: "rich", keepLineBreaks: true })).toBe("a\nb"));
  it("converts legacy rich markdown first", () => expect(plainText("**Hi** there", { format: "rich" })).toBe("Hi there"));
  it("handles empty and non-strings", () => {
    expect(plainText("")).toBe("");
    expect(plainText(undefined)).toBe("");
    expect(plainText(null)).toBe("");
  });
  it("nbsp becomes a normal space", () => expect(plainText("a&nbsp;b")).toBe("a b"));
});
```

- [ ] **Step 2: Implement `src/legacy.ts`**

This is a line-for-line port of `backend/auth_service/services/rich_text_legacy.py`. Keep that file open while porting.

```ts
// Legacy (pre-rich-text) text → canonical HTML. 1:1 port of backend services/rich_text_legacy.py;
// both are pinned by fixtures/legacy-vectors.json — change them together.
import { escapeAttr, escapeText } from "./serialize";
import { safeHref } from "./href";

const WS = /[ \t\r\n\f]+/g;
const W = "0-9A-Za-z\\u00C0-\\u024F";
const LINK_RE = /\[([^\]\n]+)\]\(([^)\s]+)\)/g;
const BOLD_RE = /\*\*(?=\S)(.+?)(?<=\S)\*\*|__(?=\S)(.+?)(?<=\S)__/g;
const STRIKE_RE = /~~(?=\S)(.+?)(?<=\S)~~/g;
const EM_RE = new RegExp(
  `(?<![${W}*])\\*(?=\\S)(.+?)(?<=\\S)\\*(?![${W}*])|(?<![${W}_])_(?=\\S)(.+?)(?<=\\S)_(?![${W}_])`, "g");
const PH_RE = /(\d+)/g;
const HEADING_RE = /^(#{1,6})\s+(.*)$/;
const HR_RE = /^(?:-{3,}|\*{3,}|_{3,})$/;
const UL_RE = /^[-*+]\s+(.+)$/;
const OL_RE = /^\d{1,9}[.)]\s+(.+)$/;
const QUOTE_RE = /^>\s?(.*)$/;
const BLANK_SPLIT_RE = /\n[ \t]*\n/;

const clean = (line: string) => line.replace(WS, " ").trim();

function inlineMd(line: string): string {
  const links: string[] = [];
  let s = line.replace(LINK_RE, (_m, label: string, url: string) => {
    const href = safeHref(url);
    links.push(href ? `<a href="${escapeAttr(href)}">${escapeText(label)}</a>` : escapeText(label));
    return `${links.length - 1}`;
  });
  s = escapeText(s);
  s = s.replace(BOLD_RE, (_m, a?: string, b?: string) => `<strong>${a || b}</strong>`);
  s = s.replace(STRIKE_RE, (_m, a: string) => `<s>${a}</s>`);
  s = s.replace(EM_RE, (_m, a?: string, b?: string) => `<em>${a || b}</em>`);
  return s.replace(PH_RE, (_m, k: string) => links[Number(k)]);
}

type Kind = "p" | "quote" | "ul" | "ol" | null;
function flush(kind: Kind, groups: string[][], out: string[]): void {
  if (kind === null || !groups.length) return;
  if (kind === "p" || kind === "quote") {
    const lines = groups[0].filter(Boolean);
    if (!lines.length) return;
    const body = lines.join("<br>");
    out.push(kind === "p" ? `<p>${body}</p>` : `<blockquote><p>${body}</p></blockquote>`);
    return;
  }
  const items = groups.filter((g) => g.length).map((g) => `<li><p>${g.join("<br>")}</p></li>`).join("");
  if (items) out.push(`<${kind}>${items}</${kind}>`);
}

function rich(text: string): string {
  const out: string[] = [];
  for (const rawBlock of text.split(BLANK_SPLIT_RE)) {
    let kind: Kind = null;
    let groups: string[][] = [];
    for (const rawLine of rawBlock.split("\n")) {
      const line = clean(rawLine);
      if (!line) continue;
      if (HR_RE.test(line)) {
        flush(kind, groups, out);
        kind = null;
        groups = [];
        out.push("<hr>");
        continue;
      }
      const h = HEADING_RE.exec(line);
      if (h) {
        flush(kind, groups, out);
        kind = null;
        groups = [];
        const content = inlineMd(h[2]);
        const level = ({ 1: 2, 2: 2, 3: 3 } as Record<number, number>)[h[1].length] ?? 4;
        if (content) out.push(`<h${level}>${content}</h${level}>`);
        continue;
      }
      const ul = UL_RE.exec(line);
      const ol = ul ? null : OL_RE.exec(line);
      const m = ul ?? ol;
      if (m) {
        const k: Kind = ul ? "ul" : "ol";
        if (kind !== k) { flush(kind, groups, out); kind = k; groups = []; }
        groups.push([inlineMd(m[1])]);
        continue;
      }
      const q = QUOTE_RE.exec(line);
      if (q) {
        if (kind !== "quote") { flush(kind, groups, out); kind = "quote"; groups = [[]]; }
        groups[0].push(inlineMd(clean(q[1])));
        continue;
      }
      if (kind === "ul" || kind === "ol") { groups[groups.length - 1].push(inlineMd(line)); continue; }
      if (kind !== "p") { flush(kind, groups, out); kind = "p"; groups = [[]]; }
      groups[0].push(inlineMd(line));
    }
    flush(kind, groups, out);
  }
  return out.join("");
}

function inlinePlain(text: string): string {
  const lines = text.split("\n").map(clean);
  while (lines.length && !lines[0]) lines.shift();
  while (lines.length && !lines[lines.length - 1]) lines.pop();
  return lines.map(escapeText).join("<br>");
}

/** Pre-rich-text content → canonical HTML. Rich = Markdown-lite; inline = plain text (migration only). */
export function legacyToHtml(text: string, fmt: "inline" | "rich"): string {
  if (typeof text !== "string") return "";
  const t = text.replace(/\r\n/g, "\n").replace(/\r/g, "\n").replace(/ /g, " ");
  if (!t.trim()) return "";
  return fmt === "rich" ? rich(t) : inlinePlain(t);
}
```

- [ ] **Step 3: Implement `src/plainText.ts`**

```ts
import { BLOCK_TAGS, parse, type RichNode } from "./parse";
import { isHtml } from "./detect";
import { legacyToHtml } from "./legacy";

export interface PlainTextOptions { format?: "inline" | "rich"; keepLineBreaks?: boolean }

/** Text content of a CMS value — for meta tags, JSON-LD, alt/aria, React keys, search, tel:/mailto:. */
export function plainText(value: string | null | undefined, opts: PlainTextOptions = {}): string {
  if (typeof value !== "string" || !value) return "";
  const format = opts.format ?? "inline";
  const html = format === "rich" && !isHtml(value) ? legacyToHtml(value, "rich") : value;
  const parts: string[] = [];
  const walk = (nodes: RichNode[]) => {
    for (const n of nodes) {
      if (typeof n === "string") parts.push(n);
      else if (n.tag === "br" || n.tag === "hr") parts.push("\n");
      else if (BLOCK_TAGS.has(n.tag)) { parts.push("\n"); walk(n.children); parts.push("\n"); }
      else walk(n.children);
    }
  };
  walk(parse(html).children);
  const text = parts.join("");
  if (opts.keepLineBreaks) {
    const kept: string[] = [];
    for (const raw of text.split("\n")) {
      const l = raw.replace(/\s+/g, " ").trim();
      if (l || (kept.length && kept[kept.length - 1])) kept.push(l);
    }
    return kept.join("\n").trim();
  }
  return text.replace(/\s+/g, " ").trim();
}
```

- [ ] **Step 4: Run and commit**

Run: `npx vitest run && npx tsc --noEmit` → green.

```bash
git add client-kit/rich-text
git commit -m "feat(kit): legacy converter and plainText"
```

---

### Task 10: Client kit — `<RichText>`, `splitRichWords`, theme CSS

**Files:**
- Create: `client-kit/rich-text/src/RichText.tsx`, `src/splitRichWords.tsx`, `src/cms-rich.css`, `src/index.ts`
- Test: `client-kit/rich-text/tests/RichText.test.tsx`, `tests/splitRichWords.test.tsx`, `tests/version.test.ts`

**Interfaces:**
- Consumes: Tasks 8–9.
- Produces (the public API sites import from `index.ts`):
  - `RichText(props: RichTextProps)`, with `RichTextProps = { value?: string | null; format?: "inline" | "rich"; as?: ElementType; className?: string; id?: string; headingOffset?: number; links?: boolean; linkTarget?: "auto" | "self" | "blank"; renderLink?: (p: RenderLinkProps) => ReactNode }`
  - `richTree(value, format) → RichNode[]`
  - `splitRichWords(value, format?) → RichWord[]`, with `RichWord = { key: string; text: string; node: ReactNode; breakBefore: boolean }`
  - `RichWords({ value, format?, renderWord, as?, className? })`
  - `RICH_TEXT_KIT_VERSION`

- [ ] **Step 1: Write the failing tests**

`tests/RichText.test.tsx`:
```tsx
import { describe, expect, it } from "vitest";
import { render } from "@testing-library/react";
import { renderToString } from "react-dom/server";
import type { ReactElement } from "react";
import { RichText } from "../src/RichText";

const html = (ui: ReactElement) => render(ui).container.innerHTML;

describe("RichText", () => {
  it("renders semantic elements inside .cms-rich", () => {
    expect(html(<RichText value="<p>Hi <strong>there</strong></p><ul><li><p>a</p></li></ul>" />)).toBe(
      '<div class="cms-rich"><p>Hi <strong>there</strong></p><ul><li><p>a</p></li></ul></div>');
  });
  it("inline format renders a span wrapper", () => {
    expect(html(<RichText value="A &amp; <em>B</em>" format="inline" />)).toBe(
      '<span class="cms-rich cms-rich--inline">A &amp; <em>B</em></span>');
  });
  it("renders nothing for empty, whitespace or empty-paragraph values", () => {
    for (const v of ["", "   ", "<p></p>", "<p><br></p>", null, undefined]) {
      expect(render(<RichText value={v} />).container.innerHTML).toBe("");
    }
  });
  it("renders legacy markdown rich values", () => {
    expect(html(<RichText value={"**Bold** text\n\n- one"} />)).toBe(
      '<div class="cms-rich"><p><strong>Bold</strong> text</p><ul><li><p>one</p></li></ul></div>');
  });
  it("decodes entities exactly once", () => {
    expect(render(<RichText value="Tom &amp;amp; Jerry" format="inline" />).container.textContent).toBe("Tom &amp; Jerry");
  });
  it("never renders scripts, handlers or javascript: links", () => {
    const out = html(<RichText value={'<p onclick="x()">a<script>alert(1)</script><img src=x onerror=y><a href="javascript:z()">l</a></p>'} />);
    expect(out).toBe('<div class="cms-rich"><p>al</p></div>');
  });
  it("external links open in a new tab, internal and mailto ones don't", () => {
    const out = html(<RichText value={'<p><a href="https://x.ro">e</a> <a href="/c">i</a> <a href="mailto:a@b.ro">m</a></p>'} />);
    expect(out).toContain('<a href="https://x.ro" target="_blank" rel="noopener noreferrer">e</a>');
    expect(out).toContain('<a href="/c">i</a>');
    expect(out).toContain('<a href="mailto:a@b.ro">m</a>');
  });
  it("links={false} renders no anchors (safe inside clickable cards)", () => {
    expect(html(<RichText value={'<a href="https://x.ro">t</a>'} format="inline" links={false} />)).toBe(
      '<span class="cms-rich cms-rich--inline"><span class="cms-rich-link">t</span></span>');
  });
  it("renderLink is used for internal links", () => {
    const out = html(<RichText value={'<a href="/about">t</a>'} format="inline"
      renderLink={({ href, children }) => <a data-router="" href={href}>{children}</a>} />);
    expect(out).toContain('<a data-router="" href="/about">t</a>');
  });
  it("headingOffset shifts levels and clamps at h6", () => {
    expect(html(<RichText value="<h2>a</h2><h4>b</h4>" headingOffset={1} />)).toBe('<div class="cms-rich"><h3>a</h3><h5>b</h5></div>');
    expect(html(<RichText value="<h4>b</h4>" headingOffset={5} />)).toBe('<div class="cms-rich"><h6>b</h6></div>');
  });
  it("keeps interior empty paragraphs", () => {
    expect(html(<RichText value="<p>a</p><p></p><p>b</p>" />)).toBe('<div class="cms-rich"><p>a</p><p></p><p>b</p></div>');
  });
  it("server render is deterministic (no hydration mismatch)", () => {
    const v = '<p>a<br>b &amp; <a href="https://x.ro">c</a></p><ol><li><p>x</p></li></ol>';
    expect(renderToString(<RichText value={v} />)).toBe(renderToString(<RichText value={v} />));
  });
  it("accepts className, id and as", () => {
    expect(html(<RichText value="<p>x</p>" as="section" className="prose" id="s" />)).toBe(
      '<section class="cms-rich prose" id="s"><p>x</p></section>');
  });
});
```
`tests/splitRichWords.test.tsx`:
```tsx
import { describe, expect, it } from "vitest";
import { render } from "@testing-library/react";
import { RichWords, splitRichWords } from "../src/splitRichWords";

describe("splitRichWords", () => {
  it("splits into words that keep their marks", () => {
    const words = splitRichWords("IT <strong>solutions for</strong> you");
    expect(words.map((w) => w.text)).toEqual(["IT", "solutions", "for", "you"]);
    const { container } = render(<>{words.map((w) => <span key={w.key}>{w.node}</span>)}</>);
    expect(container.innerHTML).toBe(
      "<span>IT</span><span><strong>solutions</strong></span><span><strong>for</strong></span><span>you</span>");
  });
  it("glues a word split across a mark boundary", () => {
    expect(splitRichWords("wo<strong>rd</strong> next").map((w) => w.text)).toEqual(["word", "next"]);
  });
  it("marks words after a line break", () => {
    expect(splitRichWords("a<br>b").map((x) => [x.text, x.breakBefore])).toEqual([["a", false], ["b", true]]);
  });
  it("empty value gives no words", () => expect(splitRichWords("")).toEqual([]));
  it("RichWords renders spaces and breaks between words", () => {
    const { container } = render(<RichWords value="a b<br>c" renderWord={(w) => <i>{w.node}</i>} />);
    expect(container.innerHTML).toBe('<span class="cms-rich cms-rich--inline"><i>a</i> <i>b</i><br><i>c</i></span>');
  });
});
```
`tests/version.test.ts`:
```ts
import { expect, it } from "vitest";
import pkg from "../package.json";
import { RICH_TEXT_KIT_VERSION } from "../src/index";
it("kit version constant matches package.json", () => expect(RICH_TEXT_KIT_VERSION).toBe(pkg.version));
```

- [ ] **Step 2: Implement `src/RichText.tsx`**

```tsx
import { Fragment, createElement, type ElementType, type ReactNode } from "react";
import { isHtml } from "./detect";
import { legacyToHtml } from "./legacy";
import { normalizeInline, normalizeRich } from "./normalize";
import { parse, type RichElement, type RichNode } from "./parse";

export type RichFormat = "inline" | "rich";
export type LinkTarget = "auto" | "self" | "blank";
export interface RenderLinkProps { href: string; external: boolean; children: ReactNode }

export interface RichTextProps {
  value?: string | null;
  format?: RichFormat;
  as?: ElementType;
  className?: string;
  id?: string;
  /** Shift h2–h4 by this many levels (e.g. 1 inside cards). Clamped to h1–h6. */
  headingOffset?: number;
  /** false renders links as <span class="cms-rich-link"> — use inside already-clickable elements. */
  links?: boolean;
  linkTarget?: LinkTarget;
  /** Render internal (/path, #hash) links with the site's router link. */
  renderLink?: (props: RenderLinkProps) => ReactNode;
}

/** Normalized node tree for a CMS value (spec §4.4: inline = HTML fragment; tag-free rich = legacy). */
export function richTree(value: string | null | undefined, format: RichFormat = "rich"): RichNode[] {
  if (typeof value !== "string" || !value.trim()) return [];
  const src = format === "rich" && !isHtml(value) ? legacyToHtml(value, "rich") : value;
  const root = parse(src);
  return format === "inline" ? normalizeInline(root.children) : normalizeRich(root.children);
}

interface Ctx { headingOffset: number; links: boolean; linkTarget: LinkTarget; renderLink?: RichTextProps["renderLink"] }
const EXTERNAL = /^https?:\/\//i;

export function renderRichNodes(nodes: RichNode[], ctx: Ctx): ReactNode[] {
  return nodes.map((n, i) => renderNode(n, i, ctx));
}

function renderAnchor(n: RichElement, key: number, kids: ReactNode[], ctx: Ctx): ReactNode {
  const href = n.href ?? "";
  const external = EXTERNAL.test(href);
  if (!ctx.links) return <span key={key} className="cms-rich-link">{kids}</span>;
  if (ctx.renderLink && !external && (href.startsWith("/") || href.startsWith("#"))) {
    return <Fragment key={key}>{ctx.renderLink({ href, external, children: kids })}</Fragment>;
  }
  const blank = ctx.linkTarget === "blank" || (ctx.linkTarget === "auto" && external);
  return blank ? (
    <a key={key} href={href} target="_blank" rel="noopener noreferrer">{kids}</a>
  ) : (
    <a key={key} href={href}>{kids}</a>
  );
}

function renderNode(n: RichNode, key: number, ctx: Ctx): ReactNode {
  if (typeof n === "string") return n;
  const kids = renderRichNodes(n.children, ctx);
  switch (n.tag) {
    case "br": return <br key={key} />;
    case "hr": return <hr key={key} />;
    case "a": return renderAnchor(n, key, kids, ctx);
    case "h2":
    case "h3":
    case "h4": {
      const level = Math.min(6, Math.max(1, Number(n.tag[1]) + ctx.headingOffset));
      return createElement(`h${level}`, { key }, ...kids);
    }
    default:
      return createElement(n.tag, { key }, ...kids);
  }
}

/** Renders a CMS inline/rich value safely (no innerHTML) as semantic elements themed by --cms-rich-* vars.
 *  Uses no hooks, so it works as a Next.js Server Component and in client components. */
export function RichText({
  value, format = "rich", as, className, id, headingOffset = 0, links = true, linkTarget = "auto", renderLink,
}: RichTextProps) {
  const nodes = richTree(value, format);
  if (!nodes.length) return null;
  const Tag: ElementType = as ?? (format === "inline" ? "span" : "div");
  const cls = ["cms-rich", format === "inline" ? "cms-rich--inline" : "", className ?? ""].filter(Boolean).join(" ");
  return <Tag className={cls} id={id}>{renderRichNodes(nodes, { headingOffset, links, linkTarget, renderLink })}</Tag>;
}
```

- [ ] **Step 3: Implement `src/splitRichWords.tsx`**

```tsx
import { Fragment, createElement, type ElementType, type ReactNode } from "react";
import { isHtml } from "./detect";
import { legacyToHtml } from "./legacy";
import { normalizeInline } from "./normalize";
import { parse, type RichNode } from "./parse";
import type { RichFormat } from "./RichText";

export interface RichWord { key: string; text: string; node: ReactNode; breakBefore: boolean }
type Mark = { tag: string; href?: string | null };
const EXTERNAL = /^https?:\/\//i;

function wrap(text: string, marks: Mark[]): ReactNode {
  let node: ReactNode = text;
  for (let k = marks.length - 1; k >= 0; k--) {
    const m = marks[k];
    if (m.tag === "a") {
      const href = m.href ?? "";
      node = EXTERNAL.test(href)
        ? createElement("a", { href, target: "_blank", rel: "noopener noreferrer" }, node)
        : createElement("a", { href }, node);
    } else {
      node = createElement(m.tag, null, node);
    }
  }
  return node;
}

/** Word tokens of a CMS value with their formatting, for per-word animations. Always flattened to inline. */
export function splitRichWords(value: string | null | undefined, format: RichFormat = "inline"): RichWord[] {
  if (typeof value !== "string" || !value.trim()) return [];
  const html = format === "rich" && !isHtml(value) ? legacyToHtml(value, "rich") : value;
  const nodes = normalizeInline(parse(html).children);
  const words: RichWord[] = [];
  let pendingBreak = false;
  let glue = false; // the previous text ended mid-word
  const walk = (list: RichNode[], marks: Mark[]) => {
    for (const n of list) {
      if (typeof n === "string") {
        n.split(/(\s+)/).forEach((piece, idx) => {
          if (!piece) return;
          if (/^\s+$/.test(piece)) { glue = false; return; }
          const node = wrap(piece, marks);
          const last = words[words.length - 1];
          if (glue && idx === 0 && last && !pendingBreak) {
            last.text += piece;
            last.node = createElement(Fragment, null, last.node, node);
          } else {
            words.push({ key: `w${words.length}`, text: piece, node, breakBefore: pendingBreak });
            pendingBreak = false;
          }
          glue = true;
        });
      } else if (n.tag === "br") {
        pendingBreak = true;
        glue = false;
      } else {
        walk(n.children, [...marks, { tag: n.tag, href: n.href }]);
      }
    }
  };
  walk(nodes, []);
  return words;
}

export interface RichWordsProps {
  value?: string | null;
  format?: RichFormat;
  renderWord: (word: RichWord, index: number) => ReactNode;
  as?: ElementType;
  className?: string;
}

export function RichWords({ value, format = "inline", renderWord, as, className }: RichWordsProps) {
  const words = splitRichWords(value, format);
  if (!words.length) return null;
  const Tag: ElementType = as ?? "span";
  const cls = ["cms-rich", "cms-rich--inline", className ?? ""].filter(Boolean).join(" ");
  return (
    <Tag className={cls}>
      {words.map((w, i) => (
        <Fragment key={w.key}>
          {w.breakBefore ? <br /> : i > 0 ? " " : null}
          {renderWord(w, i)}
        </Fragment>
      ))}
    </Tag>
  );
}
```

- [ ] **Step 4: Create `src/cms-rich.css`**

```css
/* CMS rich text base styles (ADR-0010). Theme ONLY through the --cms-rich-* variables:
   define them on :root, on your dark-theme selector and on every inverted surface.
   Selectors are ".cms-rich <el>" (0,1,1) so Tailwind preflight (v3/v4) can't strip bullets;
   no rule targets the wrapper itself, so classes you pass to <RichText> always apply. */
.cms-rich > * + *,
.cms-rich li > * + * { margin-top: var(--cms-rich-gap, 0.75em); }
.cms-rich p, .cms-rich ul, .cms-rich ol, .cms-rich blockquote,
.cms-rich h2, .cms-rich h3, .cms-rich h4, .cms-rich h5, .cms-rich h6, .cms-rich hr { margin-bottom: 0; }
.cms-rich > :first-child { margin-top: 0; }
.cms-rich p:empty::before { content: "\200b"; }
.cms-rich strong { color: var(--cms-rich-strong, inherit); font-weight: var(--cms-rich-strong-weight, 700); }
.cms-rich em { color: var(--cms-rich-em, inherit); font-style: italic; }
.cms-rich u { text-decoration-line: underline; text-decoration-color: var(--cms-rich-underline, currentColor); text-underline-offset: 0.15em; }
.cms-rich s { text-decoration-line: line-through; }
.cms-rich a, .cms-rich .cms-rich-link {
  color: var(--cms-rich-link, currentColor);
  text-decoration: var(--cms-rich-link-decoration, underline);
  text-underline-offset: 0.18em;
}
.cms-rich a:hover { color: var(--cms-rich-link-hover, var(--cms-rich-link, currentColor)); }
.cms-rich a:focus-visible { outline: 2px solid currentColor; outline-offset: 2px; border-radius: 2px; }
.cms-rich h2, .cms-rich h3, .cms-rich h4, .cms-rich h5, .cms-rich h6 {
  color: var(--cms-rich-heading, inherit);
  font-family: var(--cms-rich-heading-font, inherit);
  font-weight: var(--cms-rich-heading-weight, 700);
  line-height: 1.25;
}
.cms-rich h2 { font-size: 1.35em; }
.cms-rich h3 { font-size: 1.2em; }
.cms-rich h4, .cms-rich h5, .cms-rich h6 { font-size: 1.05em; }
.cms-rich ul, .cms-rich ol { padding-left: var(--cms-rich-list-indent, 1.4em); }
.cms-rich ul { list-style: disc; }
.cms-rich ul ul { list-style: circle; }
.cms-rich ol { list-style: decimal; }
.cms-rich li + li { margin-top: 0.35em; }
.cms-rich li::marker { color: var(--cms-rich-marker, currentColor); }
.cms-rich blockquote {
  border-left: 3px solid var(--cms-rich-quote-border, currentColor);
  padding-left: 1em;
  color: var(--cms-rich-quote-text, inherit);
  font-style: italic;
}
.cms-rich hr { border: 0; border-top: 1px solid var(--cms-rich-rule, currentColor); opacity: 0.4; }
```

- [ ] **Step 5: Create `src/index.ts`**

```ts
export const RICH_TEXT_KIT_VERSION = "1.0.0";
export { parse, decodeEntities, MARK_TAGS, INLINE_TAGS, HEADING_TAGS, BLOCK_TAGS, type RichNode, type RichElement } from "./parse";
export { safeHref, MAX_HREF_LENGTH } from "./href";
export { isHtml } from "./detect";
export { normalizeInline, normalizeRich, MAX_LIST_DEPTH } from "./normalize";
export { serialize, escapeText, escapeAttr } from "./serialize";
export { legacyToHtml } from "./legacy";
export { plainText, type PlainTextOptions } from "./plainText";
export { RichText, richTree, renderRichNodes, type RichTextProps, type RichFormat, type LinkTarget, type RenderLinkProps } from "./RichText";
export { splitRichWords, RichWords, type RichWord, type RichWordsProps } from "./splitRichWords";
```

- [ ] **Step 6: Run and commit**

Run: `npx vitest run && npx tsc --noEmit` → green.

```bash
git add client-kit/rich-text
git commit -m "feat(kit): RichText renderer, per-word splitting and theme CSS"
```

---

### Task 11: Kit distribution — sync script, README, Makefile, dashboard vendoring

**Files:**
- Create: `client-kit/rich-text/scripts/sync-rich-text-kit.mjs`, `client-kit/rich-text/README.md`
- Create (generated by the script): `frontend/src/lib/cms-rich-text/*`
- Modify: `Makefile`, `frontend/.prettierignore` (create if missing), `frontend/eslint.config.mjs`, and the lint-staged / pre-commit config if either would reformat vendored files.

**Interfaces:**
- Produces:
  - `node client-kit/rich-text/scripts/sync-rich-text-kit.mjs <target-dir> [--check]`
  - `make test-kit`, `make kit-sync`, `make kit-sync-check` (the last runs inside `make ci`)
  - The dashboard imports the kit from `@/lib/cms-rich-text`.

- [ ] **Step 1: Write the sync script**

```js
#!/usr/bin/env node
// Vendors the rich-text kit into a site or the dashboard (ADR-0010).
// Usage: node sync-rich-text-kit.mjs <target-dir> [--check]
import { existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const kitRoot = join(dirname(fileURLToPath(import.meta.url)), "..");
const { version } = JSON.parse(readFileSync(join(kitRoot, "package.json"), "utf8"));
const FILES = [
  "parse.ts", "href.ts", "detect.ts", "normalize.ts", "serialize.ts", "legacy.ts",
  "plainText.ts", "RichText.tsx", "splitRichWords.tsx", "index.ts", "cms-rich.css",
];
const [target, flag] = process.argv.slice(2);
if (!target) {
  console.error("usage: sync-rich-text-kit.mjs <target-dir> [--check]");
  process.exit(2);
}
const lf = (s) => s.replace(/\r\n/g, "\n");
const header = (f) =>
  f.endsWith(".css")
    ? `/* Vendored from CMS client-kit/rich-text v${version} — do not edit; re-sync instead. */\n`
    : `// Vendored from CMS client-kit/rich-text v${version} — do not edit; re-sync instead.\n`;
const drift = [];
for (const f of FILES) {
  const want = header(f) + lf(readFileSync(join(kitRoot, "src", f), "utf8"));
  const dest = join(target, f);
  if (flag === "--check") {
    if (!existsSync(dest) || lf(readFileSync(dest, "utf8")) !== want) drift.push(f);
  } else {
    mkdirSync(target, { recursive: true });
    writeFileSync(dest, want);
  }
}
const versionFile = join(target, "VERSION");
if (flag === "--check") {
  if (!existsSync(versionFile) || readFileSync(versionFile, "utf8").trim() !== version) drift.push("VERSION");
  if (drift.length) {
    console.error(`rich-text kit drift in ${target}: ${drift.join(", ")} — run the sync script`);
    process.exit(1);
  }
  console.log(`rich-text kit v${version} in sync: ${target}`);
} else {
  writeFileSync(versionFile, `${version}\n`);
  console.log(`synced rich-text kit v${version} -> ${target}`);
}
```

- [ ] **Step 2: Makefile targets**

Add these, following the existing `## help` comment style:
```make
KIT_DIR := client-kit/rich-text
KIT_DASHBOARD_DIR := frontend/src/lib/cms-rich-text

test-kit: ## Run the rich-text client kit tests
	cd $(KIT_DIR) && npm test && npx tsc --noEmit

kit-sync: ## Vendor the rich-text kit into the dashboard
	node $(KIT_DIR)/scripts/sync-rich-text-kit.mjs $(KIT_DASHBOARD_DIR)

kit-sync-check: ## Fail if the dashboard's vendored kit is out of date
	node $(KIT_DIR)/scripts/sync-rich-text-kit.mjs $(KIT_DASHBOARD_DIR) --check
```
- Add `cd $(KIT_DIR) && npm ci` to `install`.
- Change `test:` to `test: test-backend test-agent test-frontend test-kit`.
- Change `ci:` to `ci: lint test kit-sync-check docs-check`.
- Declare the new targets `.PHONY` if the Makefile does that for the others.

- [ ] **Step 3: Vendor into the dashboard and keep formatters away from it**

Run `make kit-sync`. Then:
- Add `src/lib/cms-rich-text/` to `frontend/.prettierignore`.
- Add `"src/lib/cms-rich-text/**"` to the ignore list in `frontend/eslint.config.mjs`. Use its existing `ignores` entry, or add `{ ignores: [...] }` as the first config object.
- Check `.pre-commit-config.yaml` and the `lint-staged` config in `frontend/package.json`: vendored files must not be reformatted on commit, so exclude the path there as well if needed.

Run `make kit-sync-check` → it must report in sync. Run `cd frontend && npx tsc --noEmit` → the vendored kit compiles under the dashboard's tsconfig. If it doesn't, fix the **kit source** and re-sync; never edit the vendored copy.

- [ ] **Step 4: Write `client-kit/rich-text/README.md`**

Sections (write real prose and code, not stubs):
1. **What it is** — link ADR-0010; zero runtime deps besides React; never uses `innerHTML`.
2. **Install into a site** — `node <cms-repo>/client-kit/rich-text/scripts/sync-rich-text-kit.mjs <site>/src/lib/cms-rich-text`; import `cms-rich.css` once (Next: in the root layout; Vite: in `main.tsx`); re-sync on kit upgrades (see the `VERSION` file).
3. **Field-usage rules** (a table):

   | Use | How |
   |---|---|
   | Display prose | `<RichText value={x} format="rich|inline" />` |
   | Meta tags, JSON-LD, `alt`/`aria-label`, React keys, search, `tel:`/`mailto:`, `Number()` | `plainText(x)` |
   | Per-word animations | `splitRichWords` / `<RichWords>` |
   | Inside a clickable card | `links={false}` |
   | Internal links | `renderLink` with the site router |
   | Headings inside cards | `headingOffset={1}` |

4. **next-intl sites** — CMS values merged into messages are read with `t.raw("key")` and rendered with `<RichText>`. Never call `t()` on an inline/rich value (tags throw in ICU). Metadata uses `plainText(t.raw(...))`.
5. **Theme recipe** — the variable table from spec §7, a worked example, and the contrast rule (accent colours only where they reach 4.5:1 against that surface). Example:

   ```css
   :root { --cms-rich-strong: var(--ink); --cms-rich-link: var(--brand); --cms-rich-marker: var(--brand); }
   [data-theme="dark"] { --cms-rich-strong: #fff; --cms-rich-link: var(--accent-cyan); }
   .hero, .section-dark { --cms-rich-strong: var(--accent-cyan); }
   ```

6. **Formats** — plain / inline / rich, and what each editor can produce.
7. **Testing a site** — a checklist: bold, link, list, heading, blank line and `&`, in each locale and each theme; no literal tags; no console or hydration errors.

- [ ] **Step 5: Run the gate**

Run: `make test-kit && make kit-sync-check && cd frontend && npx tsc --noEmit && npm run lint`
Expected: green.

- [ ] **Step 6: Commit**

```bash
git add client-kit Makefile frontend/src/lib/cms-rich-text frontend/.prettierignore frontend/eslint.config.mjs
git commit -m "feat(kit): sync script, README, make targets, vendor kit into dashboard"
```
Also stage `.pre-commit-config.yaml` / `frontend/package.json` if you changed them.

---

### Task 12: Dashboard rich-text editor component

**Files:**
- Modify: `frontend/package.json` (add explicit deps `@tiptap/core`, `@tiptap/extension-document`, `@tiptap/extensions`, all at `^3.23.5`, matching `@tiptap/starter-kit`)
- Create: `frontend/src/components/dashboard/rich-text/extensions.ts`, `serialize.ts`, `linkInput.ts`, `RichTextEditor.tsx`, `Toolbar.tsx`, `LinkPopover.tsx`
- Test: `frontend/src/components/dashboard/rich-text/__tests__/serialize.test.ts`, `linkInput.test.ts`, `RichTextEditor.test.tsx`

**Interfaces:**
- Consumes: `@/lib/cms-rich-text` (`isHtml`, `legacyToHtml`, `safeHref`, `parse`, `normalizeInline`, `serialize`) from Task 11.
- Produces (used by Task 13):
  - `type RichMode = "inline" | "rich"`
  - `toStored(html: string, mode: RichMode): string`, `fromStored(value: unknown, mode: RichMode): string`
  - `normalizeLinkInput(raw: string): string | null`
  - `RICH_LIMITS: Record<RichMode, number>` = `{ inline: 2000, rich: 50000 }`
  - `RichTextEditor(props: { value: string; onChange(v: string): void; mode: RichMode; label: string; placeholder?: string; disabled?: boolean; id?: string; onReady?(editor: Editor): void })`

- [ ] **Step 1: Add the explicit TipTap deps**

Run: `cd frontend && npm install @tiptap/core@^3.23.5 @tiptap/extension-document@^3.23.5 @tiptap/extensions@^3.23.5`
Confirm `npm ls @tiptap/core` shows a single version.

- [ ] **Step 2: Write the failing unit tests**

`__tests__/serialize.test.ts`:
```ts
import { describe, expect, it } from "vitest";
import { fromStored, toStored } from "../serialize";

describe("toStored", () => {
  it.each([
    ["<p></p>", "rich", ""], ["<p></p><p><br></p>", "rich", ""], ["<p>&nbsp;</p>", "rich", ""],
    ["<p>a</p><p></p><p>b</p>", "rich", "<p>a</p><p></p><p>b</p>"],
    ["<p></p>", "inline", ""], ["<p>A &amp; <strong>B</strong></p>", "inline", "A &amp; <strong>B</strong>"],
    ["<p><br>x<br></p>", "inline", "x"], ["<p>a<br><br>b</p>", "inline", "a<br><br>b"],
  ])("%s (%s)", (html, mode, expected) => expect(toStored(html, mode as "inline" | "rich")).toBe(expected));
});

describe("fromStored", () => {
  it("wraps inline values in one paragraph", () => expect(fromStored("A &amp; B", "inline")).toBe("<p>A &amp; B</p>"));
  it("passes rich HTML through", () => expect(fromStored("<p>x</p>", "rich")).toBe("<p>x</p>"));
  it("converts tag-free rich (legacy markdown)", () => expect(fromStored("**x**", "rich")).toBe("<p><strong>x</strong></p>"));
  it("treats non-strings and blanks as empty", () => {
    expect(fromStored(undefined, "rich")).toBe("");
    expect(fromStored("  ", "inline")).toBe("");
  });
});
```
`__tests__/linkInput.test.ts`:
```ts
import { describe, expect, it } from "vitest";
import { normalizeLinkInput } from "../linkInput";

describe("normalizeLinkInput", () => {
  it.each([
    ["https://a.ro/x", "https://a.ro/x"], ["example.com", "https://example.com"],
    ["www.example.com/p?q=1", "https://www.example.com/p?q=1"], ["name@firm.ro", "mailto:name@firm.ro"],
    ["+40 721 000 000", "tel:+40721000000"], ["/contact", "/contact"], ["#services", "#services"],
    ["mailto:a@b.ro", "mailto:a@b.ro"], ["javascript:alert(1)", null], ["//evil.com", null], ["", null], ["just words", null],
  ])("%s", (raw, expected) => expect(normalizeLinkInput(raw)).toBe(expected));
});
```

- [ ] **Step 3: Implement `serialize.ts` and `linkInput.ts`**

```ts
// serialize.ts — editor HTML ⇄ stored CMS value (spec §6, §4.4).
import { isHtml, legacyToHtml } from "@/lib/cms-rich-text";

export type RichMode = "inline" | "rich";
const EMPTY_DOC = /^(?:<p>(?:\s|&nbsp;|\u00a0|<br\s*\/?>)*<\/p>)*$/;

export function toStored(html: string, mode: RichMode): string {
  const trimmed = html.trim();
  if (EMPTY_DOC.test(trimmed)) return "";
  if (mode === "inline") {
    const m = /^<p>([\s\S]*)<\/p>$/.exec(trimmed);
    return (m ? m[1] : trimmed).replace(/^(?:<br\s*\/?>)+|(?:<br\s*\/?>)+$/g, "").trim();
  }
  return trimmed;
}

export function fromStored(value: unknown, mode: RichMode): string {
  const v = typeof value === "string" ? value : "";
  if (!v.trim()) return "";
  if (mode === "inline") return `<p>${v}</p>`; // inline values are HTML fragments — never legacy-converted here
  return isHtml(v) ? v : legacyToHtml(v, "rich");
}
```
```ts
// linkInput.ts — what a client types in the link box → a safe href, or null.
import { safeHref } from "@/lib/cms-rich-text";

export function normalizeLinkInput(raw: string): string | null {
  const v = raw.trim();
  if (!v) return null;
  if (/^(https?:\/\/|mailto:|tel:)/i.test(v) || v.startsWith("#") || v.startsWith("/")) return safeHref(v);
  if (/^[^\s@/]+@[^\s@/]+\.[^\s@/]+$/.test(v)) return safeHref(`mailto:${v}`);
  if (/^\+?[\d\s().-]{6,}$/.test(v)) return safeHref(`tel:${v.replace(/[\s().-]/g, "")}`);
  if (/^[\w-]+(\.[\w-]+)+([/?#]\S*)?$/.test(v)) return safeHref(`https://${v}`);
  return null;
}
```
Run the two unit tests → green.

- [ ] **Step 4: Implement `extensions.ts`**

```ts
import { Extension } from "@tiptap/core";
import Document from "@tiptap/extension-document";
import StarterKit from "@tiptap/starter-kit";
import { Placeholder } from "@tiptap/extensions";
import { safeHref } from "@/lib/cms-rich-text";

// Colours, fonts, sizes and highlights are intentionally NOT loaded (ADR-0010): pasted
// styling vanishes while style-based bold/italic (Google Docs) is still recognised.
const link = {
  openOnClick: false,
  autolink: true,
  linkOnPaste: true,
  defaultProtocol: "https",
  protocols: ["mailto", "tel"],
  HTMLAttributes: { target: null, rel: null },
  isAllowedUri: (url: string) => safeHref(url) !== null,
};

export function richExtensions(placeholder = "") {
  return [
    StarterKit.configure({ heading: { levels: [2, 3, 4] }, code: false, codeBlock: false, link }),
    Placeholder.configure({ placeholder }),
  ];
}

/** Single-paragraph document: titles and short fields. Enter inserts a line break. */
const InlineDocument = Document.extend({ content: "paragraph" });
const InlineEnter = Extension.create({
  name: "inlineEnter",
  priority: 1000,
  addKeyboardShortcuts() {
    return { Enter: () => this.editor.commands.setHardBreak() };
  },
});

export function inlineExtensions(placeholder = "") {
  return [
    StarterKit.configure({
      document: false, heading: false, bulletList: false, orderedList: false, listItem: false,
      listKeymap: false, blockquote: false, horizontalRule: false, code: false, codeBlock: false,
      trailingNode: false, link,
    }),
    InlineDocument,
    InlineEnter,
    Placeholder.configure({ placeholder }),
  ];
}
```
If a `StarterKit.configure` key is rejected by the installed v3 typings, check `node_modules/@tiptap/starter-kit/dist/index.d.ts` for the exact option names and use those. Say so in your report.

- [ ] **Step 5: Implement `LinkPopover.tsx`**

```tsx
"use client";

import { useEffect, useId, useRef, useState } from "react";
import type { Editor } from "@tiptap/react";
import { dashboardFieldLabelCn, dashboardInputCn, dashboardPrimaryBtnCn } from "@/lib/styles";
import { normalizeLinkInput } from "./linkInput";

export function LinkPopover({ editor, onClose }: { editor: Editor; onClose: () => void }) {
  const initial = (editor.getAttributes("link").href as string | undefined) ?? "";
  const [value, setValue] = useState(initial);
  const [error, setError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const boxRef = useRef<HTMLDivElement>(null);
  const id = useId();

  useEffect(() => {
    inputRef.current?.focus();
    inputRef.current?.select();
    const onDown = (e: MouseEvent) => {
      if (boxRef.current && !boxRef.current.contains(e.target as Node)) onClose();
    };
    document.addEventListener("mousedown", onDown);
    return () => document.removeEventListener("mousedown", onDown);
  }, [onClose]);

  function apply() {
    const href = normalizeLinkInput(value);
    if (!href) {
      setError("Enter a web address, email address, phone number, /page or #section.");
      return;
    }
    const { empty } = editor.state.selection;
    if (empty && !editor.isActive("link")) {
      editor.chain().focus()
        .insertContent({ type: "text", text: value.trim(), marks: [{ type: "link", attrs: { href } }] })
        .unsetMark("link").run();
    } else {
      editor.chain().focus().extendMarkRange("link").setLink({ href }).run();
    }
    onClose();
  }

  function remove() {
    editor.chain().focus().extendMarkRange("link").unsetLink().run();
    onClose();
  }

  return (
    <div
      ref={boxRef}
      role="dialog"
      aria-label="Edit link"
      className="absolute left-1.5 top-full z-20 mt-1 w-80 rounded-lg border border-zinc-200 bg-white p-3 shadow-lg dark:border-zinc-700 dark:bg-zinc-900"
      onKeyDown={(e) => {
        if (e.key === "Escape") { e.preventDefault(); onClose(); editor.commands.focus(); }
      }}
    >
      <label htmlFor={id} className={dashboardFieldLabelCn}>Link address</label>
      <input
        ref={inputRef}
        id={id}
        value={value}
        onChange={(e) => { setValue(e.target.value); setError(null); }}
        onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); apply(); } }}
        placeholder="https://…, name@email.com, +40…, /contact"
        aria-invalid={error ? true : undefined}
        aria-describedby={error ? `${id}-err` : undefined}
        className={dashboardInputCn}
      />
      {error && <p id={`${id}-err`} role="alert" className="mt-1.5 text-xs text-red-600 dark:text-red-400">{error}</p>}
      <div className="mt-3 flex justify-end gap-2">
        {initial && (
          <button type="button" onClick={remove} className="cursor-pointer rounded-md px-3 py-1.5 text-xs font-medium text-red-600 hover:bg-red-50 dark:hover:bg-red-950">
            Remove link
          </button>
        )}
        <button type="button" onClick={onClose} className="cursor-pointer rounded-md px-3 py-1.5 text-xs font-medium text-zinc-600 hover:bg-zinc-100 dark:text-zinc-300 dark:hover:bg-zinc-800">
          Cancel
        </button>
        <button type="button" onClick={apply} className={dashboardPrimaryBtnCn}>Apply</button>
      </div>
    </div>
  );
}
```
If `dashboardPrimaryBtnCn` is named differently in `@/lib/styles`, use the actual export.

- [ ] **Step 6: Implement `Toolbar.tsx`**

```tsx
"use client";

import { useRef, type KeyboardEvent, type ReactNode } from "react";
import { useEditorState, type Editor } from "@tiptap/react";
import {
  Bold, Italic, Link2, List, ListOrdered, Minus, Quote, Redo2, RemoveFormatting,
  Strikethrough, Underline, Undo2, Unlink,
} from "lucide-react";
import { LinkPopover } from "./LinkPopover";
import type { RichMode } from "./serialize";

type BlockStyle = "p" | "h2" | "h3" | "h4";

function Btn({ label, shortcut, active, disabled, onClick, children }: {
  label: string; shortcut?: string; active?: boolean; disabled?: boolean; onClick: () => void; children: ReactNode;
}) {
  return (
    <button
      type="button"
      aria-label={label}
      title={shortcut ? `${label} (${shortcut})` : label}
      aria-pressed={active === undefined ? undefined : active}
      disabled={disabled}
      onMouseDown={(e) => e.preventDefault()}
      onClick={onClick}
      className={`inline-flex h-7 w-7 cursor-pointer items-center justify-center rounded transition-colors disabled:cursor-not-allowed disabled:opacity-30 ${
        active
          ? "bg-zinc-900 text-white dark:bg-zinc-100 dark:text-zinc-900"
          : "text-zinc-600 hover:bg-zinc-100 dark:text-zinc-300 dark:hover:bg-zinc-800"
      }`}
    >
      {children}
    </button>
  );
}

const Sep = () => <span aria-hidden className="mx-1 h-4 w-px bg-zinc-200 dark:bg-zinc-700" />;
const ic = "h-3.5 w-3.5";

export function Toolbar({ editor, mode, linkOpen, setLinkOpen }: {
  editor: Editor | null; mode: RichMode; linkOpen: boolean; setLinkOpen: (open: boolean) => void;
}) {
  const barRef = useRef<HTMLDivElement>(null);
  const s = useEditorState({
    editor,
    selector: ({ editor: e }) =>
      e
        ? {
            bold: e.isActive("bold"), italic: e.isActive("italic"), underline: e.isActive("underline"),
            strike: e.isActive("strike"), bullet: e.isActive("bulletList"), ordered: e.isActive("orderedList"),
            quote: e.isActive("blockquote"), link: e.isActive("link"),
            block: (e.isActive("heading", { level: 2 }) ? "h2" : e.isActive("heading", { level: 3 }) ? "h3"
              : e.isActive("heading", { level: 4 }) ? "h4" : "p") as BlockStyle,
            canUndo: e.can().undo(), canRedo: e.can().redo(),
          }
        : null,
  });

  if (!editor || !s) return <div className="h-9 border-b border-zinc-200 dark:border-zinc-700" aria-hidden />;
  const chain = () => editor.chain().focus();

  const onKeyDown = (ev: KeyboardEvent<HTMLDivElement>) => {
    if (ev.key !== "ArrowRight" && ev.key !== "ArrowLeft") return;
    const items = Array.from(barRef.current?.querySelectorAll<HTMLElement>("button:not(:disabled), select") ?? []);
    const idx = items.indexOf(document.activeElement as HTMLElement);
    if (idx === -1) return;
    ev.preventDefault();
    items[(idx + (ev.key === "ArrowRight" ? 1 : items.length - 1)) % items.length]?.focus();
  };

  return (
    <div
      ref={barRef}
      role="toolbar"
      aria-label="Formatting"
      onKeyDown={onKeyDown}
      className="sticky top-0 z-10 flex flex-wrap items-center gap-0.5 rounded-t-lg border-b border-zinc-200 bg-white px-1.5 py-1 dark:border-zinc-700 dark:bg-zinc-900"
    >
      <Btn label="Undo" shortcut="Ctrl+Z" disabled={!s.canUndo} onClick={() => chain().undo().run()}><Undo2 className={ic} /></Btn>
      <Btn label="Redo" shortcut="Ctrl+Shift+Z" disabled={!s.canRedo} onClick={() => chain().redo().run()}><Redo2 className={ic} /></Btn>
      <Sep />
      {mode === "rich" && (
        <>
          <select
            aria-label="Text style"
            value={s.block}
            onChange={(e) => {
              const v = e.target.value as BlockStyle;
              if (v === "p") chain().setParagraph().run();
              else chain().setHeading({ level: Number(v[1]) as 2 | 3 | 4 }).run();
            }}
            className="h-7 cursor-pointer rounded border border-zinc-200 bg-transparent px-1.5 text-xs text-zinc-700 dark:border-zinc-700 dark:text-zinc-200"
          >
            <option value="p">Paragraph</option>
            <option value="h2">Heading 2</option>
            <option value="h3">Heading 3</option>
            <option value="h4">Heading 4</option>
          </select>
          <Sep />
        </>
      )}
      <Btn label="Bold" shortcut="Ctrl+B" active={s.bold} onClick={() => chain().toggleBold().run()}><Bold className={ic} /></Btn>
      <Btn label="Italic" shortcut="Ctrl+I" active={s.italic} onClick={() => chain().toggleItalic().run()}><Italic className={ic} /></Btn>
      <Btn label="Underline" shortcut="Ctrl+U" active={s.underline} onClick={() => chain().toggleUnderline().run()}><Underline className={ic} /></Btn>
      <Btn label="Strikethrough" shortcut="Ctrl+Shift+S" active={s.strike} onClick={() => chain().toggleStrike().run()}><Strikethrough className={ic} /></Btn>
      {mode === "rich" && (
        <>
          <Sep />
          <Btn label="Bullet list" shortcut="Ctrl+Shift+8" active={s.bullet} onClick={() => chain().toggleBulletList().run()}><List className={ic} /></Btn>
          <Btn label="Numbered list" shortcut="Ctrl+Shift+7" active={s.ordered} onClick={() => chain().toggleOrderedList().run()}><ListOrdered className={ic} /></Btn>
          <Btn label="Quote" shortcut="Ctrl+Shift+B" active={s.quote} onClick={() => chain().toggleBlockquote().run()}><Quote className={ic} /></Btn>
          <Btn label="Divider" onClick={() => chain().setHorizontalRule().run()}><Minus className={ic} /></Btn>
        </>
      )}
      <Sep />
      <Btn label="Link" shortcut="Ctrl+K" active={s.link} onClick={() => setLinkOpen(true)}><Link2 className={ic} /></Btn>
      <Btn label="Remove link" disabled={!s.link} onClick={() => chain().extendMarkRange("link").unsetLink().run()}><Unlink className={ic} /></Btn>
      <Btn label="Clear formatting" onClick={() => chain().unsetAllMarks().clearNodes().run()}><RemoveFormatting className={ic} /></Btn>
      {linkOpen && <LinkPopover editor={editor} onClose={() => setLinkOpen(false)} />}
    </div>
  );
}
```

- [ ] **Step 7: Implement `RichTextEditor.tsx`**

```tsx
"use client";

import { useEffect, useId, useRef, useState } from "react";
import { EditorContent, useEditor, type Editor } from "@tiptap/react";
import { normalizeInline, parse, serialize } from "@/lib/cms-rich-text";
import { inlineExtensions, richExtensions } from "./extensions";
import { fromStored, toStored, type RichMode } from "./serialize";
import { Toolbar } from "./Toolbar";

export const RICH_LIMITS: Record<RichMode, number> = { inline: 2000, rich: 50000 };

export interface RichTextEditorProps {
  value: string;
  onChange: (value: string) => void;
  mode: RichMode;
  /** Accessible name of the editing area. */
  label: string;
  placeholder?: string;
  disabled?: boolean;
  id?: string;
  /** Test/advanced hook: receives the TipTap editor once created. */
  onReady?: (editor: Editor) => void;
}

/** Inline paste: an inline document holds one paragraph, so flatten blocks to <br>. */
const inlinePaste = (html: string) => `<p>${serialize(normalizeInline(parse(html).children))}</p>`;

export function RichTextEditor({ value, onChange, mode, label, placeholder, disabled, id, onReady }: RichTextEditorProps) {
  const autoId = useId();
  const onChangeRef = useRef(onChange);
  onChangeRef.current = onChange;
  const [length, setLength] = useState(() => value.length);
  const [linkOpen, setLinkOpen] = useState(false);

  const editor = useEditor({
    extensions: mode === "inline" ? inlineExtensions(placeholder) : richExtensions(placeholder),
    content: fromStored(value, mode),
    editable: !disabled,
    immediatelyRender: false,
    editorProps: {
      attributes: {
        role: "textbox",
        "aria-multiline": mode === "rich" ? "true" : "false",
        "aria-label": label,
        id: id ?? autoId,
        class: `prose prose-sm prose-zinc dark:prose-invert max-w-none px-3 py-2 focus:outline-none ${
          mode === "rich" ? "min-h-[10rem]" : "min-h-[2.25rem]"
        }`,
      },
      transformPastedHTML: mode === "inline" ? inlinePaste : undefined,
      handleKeyDown: (_view, event) => {
        if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k") {
          event.preventDefault();
          setLinkOpen(true);
          return true;
        }
        return false;
      },
    },
    onUpdate: ({ editor: e }) => {
      const stored = toStored(e.getHTML(), mode);
      setLength(stored.length);
      onChangeRef.current(stored);
    },
  });

  useEffect(() => { if (editor) onReady?.(editor); }, [editor, onReady]);
  useEffect(() => { editor?.setEditable(!disabled); }, [editor, disabled]);

  const limit = RICH_LIMITS[mode];
  const over = length > limit;
  return (
    <div
      data-mode={mode}
      className={`relative rounded-lg border bg-white transition-colors focus-within:ring-2 focus-within:ring-zinc-900/10 dark:bg-zinc-950 dark:focus-within:ring-zinc-100/10 ${
        over ? "border-red-400 dark:border-red-500" : "border-zinc-200 dark:border-zinc-700"
      }`}
    >
      <Toolbar editor={editor} mode={mode} linkOpen={linkOpen} setLinkOpen={setLinkOpen} />
      <EditorContent editor={editor} />
      {length >= limit * 0.8 && (
        <p aria-live="polite" className={`px-3 pb-1.5 text-right text-[11px] ${over ? "text-red-600 dark:text-red-400" : "text-zinc-400"}`}>
          {length.toLocaleString()} / {limit.toLocaleString()} characters incl. formatting
          {over && " — too long, the save will be rejected"}
        </p>
      )}
    </div>
  );
}
```
Add `.ProseMirror p.is-editor-empty:first-child::before { content: attr(data-placeholder); float: left; height: 0; pointer-events: none; color: rgb(161 161 170); }` to `frontend/src/app/globals.css`, unless a placeholder style already exists there.

- [ ] **Step 8: Write the component tests**

`__tests__/RichTextEditor.test.tsx`:
```tsx
import { beforeAll, describe, expect, it, vi } from "vitest";
import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { Editor } from "@tiptap/react";
import { RichTextEditor } from "../RichTextEditor";

beforeAll(() => {
  // ProseMirror layout APIs jsdom lacks.
  Range.prototype.getBoundingClientRect = () => ({ x: 0, y: 0, width: 0, height: 0, top: 0, left: 0, right: 0, bottom: 0, toJSON: () => ({}) }) as DOMRect;
  Range.prototype.getClientRects = () => ({ length: 0, item: () => null, [Symbol.iterator]: [][Symbol.iterator] }) as unknown as DOMRectList;
  document.elementFromPoint = () => null;
});

async function setup(props: Partial<Parameters<typeof RichTextEditor>[0]> = {}) {
  let editor: Editor | undefined;
  const onChange = vi.fn();
  render(<RichTextEditor value="" onChange={onChange} mode="rich" label="Body" onReady={(e) => { editor = e; }} {...props} />);
  await waitFor(() => expect(editor).toBeDefined());
  return { editor: editor!, onChange };
}

describe("RichTextEditor", () => {
  it("loads stored HTML and exposes an accessible textbox", async () => {
    await setup({ value: "<p>Hello <strong>x</strong></p>" });
    const box = screen.getByRole("textbox", { name: "Body" });
    expect(box.innerHTML).toContain("<strong>x</strong>");
  });

  it("bold button toggles bold and emits stored HTML", async () => {
    const { editor, onChange } = await setup({ value: "<p>word</p>" });
    act(() => { editor.commands.selectAll(); });
    await userEvent.click(screen.getByRole("button", { name: "Bold" }));
    expect(onChange).toHaveBeenLastCalledWith("<p><strong>word</strong></p>");
    await waitFor(() => expect(screen.getByRole("button", { name: "Bold" })).toHaveAttribute("aria-pressed", "true"));
  });

  it("emptying the editor stores an empty string", async () => {
    const { editor, onChange } = await setup({ value: "<p>x</p>" });
    act(() => { editor.commands.clearContent(true); });
    expect(onChange).toHaveBeenLastCalledWith("");
  });

  it("inline mode: no lists/headings in the toolbar and Enter inserts a line break", async () => {
    const { editor, onChange } = await setup({ mode: "inline", value: "a", label: "Title" });
    expect(screen.queryByRole("button", { name: "Bullet list" })).toBeNull();
    expect(screen.queryByLabelText("Text style")).toBeNull();
    act(() => { editor.commands.focus("end"); editor.commands.keyboardShortcut("Enter"); editor.commands.insertContent("b"); });
    expect(onChange).toHaveBeenLastCalledWith("a<br>b");
  });

  it("Google Docs paste keeps real bold, drops the wrapper bold and colours", async () => {
    const { editor, onChange } = await setup();
    act(() => {
      editor.view.pasteHTML('<meta charset="utf-8"><b style="font-weight:normal;" id="docs-internal-guid-1"><span style="font-weight:700;color:#ff0000">Bold</span><span style="font-weight:400;color:#00ff00"> plain</span></b>');
    });
    expect(onChange).toHaveBeenLastCalledWith("<p><strong>Bold</strong> plain</p>");
  });

  it("inline paste of several paragraphs becomes line breaks", async () => {
    const { editor, onChange } = await setup({ mode: "inline", label: "Title" });
    act(() => { editor.view.pasteHTML("<p>one</p><ul><li>two</li></ul>"); });
    expect(onChange).toHaveBeenLastCalledWith("one<br>two");
  });

  it("link popover validates and applies", async () => {
    const { editor, onChange } = await setup({ value: "<p>site</p>" });
    act(() => { editor.commands.selectAll(); });
    await userEvent.click(screen.getByRole("button", { name: "Link" }));
    const input = screen.getByLabelText("Link address");
    await userEvent.type(input, "javascript:alert(1){enter}");
    expect(screen.getByRole("alert")).toBeInTheDocument();
    await userEvent.clear(input);
    await userEvent.type(input, "example.com{enter}");
    expect(onChange).toHaveBeenLastCalledWith('<p><a href="https://example.com">site</a></p>');
  });

  it("shows the counter near the limit", async () => {
    await setup({ mode: "inline", value: "x".repeat(1700), label: "Title" });
    expect(await screen.findByText(/1,700 \/ 2,000/)).toBeInTheDocument();
  });
});
```
If `editor.commands.keyboardShortcut` doesn't trigger the custom Enter handler in jsdom, replace that line with `editor.commands.setHardBreak()`. Keep an assertion that the inline document never contains more than one `<p>` (`editor.getHTML().match(/<p>/g)?.length === 1`). If `editor.view.pasteHTML` is unavailable in the installed prosemirror-view, dispatch a `paste` event whose `clipboardData.getData("text/html")` returns the HTML instead. The assertions are the contract; the mechanics may be adapted.

- [ ] **Step 9: Run and commit**

Run: `cd frontend && npx vitest run src/components/dashboard/rich-text && npx tsc --noEmit && npm run lint`
Expected: green.

```bash
git add frontend/package.json frontend/package-lock.json frontend/src/components/dashboard/rich-text frontend/src/app/globals.css
git commit -m "feat(dashboard): TipTap rich-text editor with toolbar and link popover"
```

---

### Task 13: Wire the editor into every content editor

**Files:**
- Create: `frontend/src/components/dashboard/rich-text/ContentField.tsx`
- Modify: `frontend/src/components/dashboard/editors/index.ts`, `TextBlockEditor.tsx`, `RepeaterEditor.tsx`, `KeyValueEditor.tsx`
- Modify: `frontend/src/components/dashboard/ServiceEditor.tsx` (`ServiceDetail` type + props passed to the editor)
- Test: `frontend/src/components/dashboard/editors/__tests__/TextBlockEditor.test.tsx`, `RepeaterEditor.test.tsx`, `KeyValueEditor.test.tsx`

**Interfaces:**
- Consumes: `RichTextEditor`, `RichMode` (Task 12); `plainText`, `escapeText` (kit); from the service detail (Task 5): `rich_text_version`, `field_formats`, `can_edit_structure`.
- Produces:
  - `type FieldFormat = "plain" | "inline" | "rich"`
  - `ContentField({ format, value, onChange, label, placeholder?, inputType? })`
  - `EditorProps` gains `richText?: boolean`, `fieldFormats?: Record<string, FieldFormat>`, `canEditStructure?: boolean`
  - `convertValue(value: string, from: FieldFormat, to: FieldFormat): string`

- [ ] **Step 1: Implement `ContentField.tsx`**

```tsx
"use client";

import { escapeText, plainText } from "@/lib/cms-rich-text";
import { dashboardInputCn } from "@/lib/styles";
import { RichTextEditor } from "./RichTextEditor";

export type FieldFormat = "plain" | "inline" | "rich";

export function ContentField({ format, value, onChange, label, placeholder, inputType = "text" }: {
  format: FieldFormat; value: string; onChange: (v: string) => void; label: string; placeholder?: string;
  inputType?: "text" | "url" | "email" | "tel";
}) {
  if (format === "plain") {
    return (
      <input type={inputType} value={value} aria-label={label} placeholder={placeholder}
        onChange={(e) => onChange(e.target.value)} className={dashboardInputCn} />
    );
  }
  return <RichTextEditor mode={format} value={value} onChange={onChange} label={label} placeholder={placeholder} />;
}

/** Convert a value when an admin changes a field's format, so nothing is lost or double-escaped. */
export function convertValue(value: string, from: FieldFormat, to: FieldFormat): string {
  if (from === to || !value) return value;
  if (to === "plain") return plainText(value, { format: from === "rich" ? "rich" : "inline", keepLineBreaks: from === "rich" });
  if (from === "plain") {
    const escaped = value.split("\n").map(escapeText);
    return to === "inline" ? escaped.join("<br>") : `<p>${escaped.join("<br>")}</p>`;
  }
  if (to === "rich") return `<p>${value}</p>`; // inline → rich: one paragraph
  return plainText(value, { format: "rich", keepLineBreaks: true }).split("\n").map(escapeText).join("<br>"); // rich → inline
}
```

- [ ] **Step 2: Extend `EditorProps` and pass the props from `ServiceEditor`**

In `editors/index.ts`:
```ts
import type { FieldFormat } from "@/components/dashboard/rich-text/ContentField";
export interface EditorProps {
  initialContent: Record<string, unknown>;
  onChange: (content: Record<string, unknown>) => void;
  onUpload?: (file: File) => Promise<string>;
  /** Project has rich text enabled (rich_text_version ≥ 1). */
  richText?: boolean;
  /** Per-field formats from the service detail (spec §5.7). */
  fieldFormats?: Record<string, FieldFormat>;
  /** Caller is an admin and may change field formats. */
  canEditStructure?: boolean;
}
```
In `ServiceEditor.tsx`:
- Add `rich_text_version?: number; field_formats?: Record<string, FieldFormat>; can_edit_structure?: boolean;` to the `ServiceDetail` type.
- Pass `richText={(service.rich_text_version ?? 0) >= 1} fieldFormats={service.field_formats ?? {}} canEditStructure={!!service.can_edit_structure}` to the `EditorComponent`.
- Change the editor element's `key` to include `service.last_updated`. After a save or re-translate refresh, the uncontrolled editors must remount with the canonical stored value. Put this key on the editor element only, **not** on the `AnimatePresence` child, so saving doesn't replay the enter animation.

- [ ] **Step 3: `TextBlockEditor` — rich path behind the flag**

Keep the existing JSX as the `!richText` branch, byte-for-byte. Add the rich branch:
```tsx
if (richText) {
  return (
    <div className={`${dashboardSectionCardCn} divide-y divide-zinc-100 dark:divide-zinc-800`}>
      <div className="p-5">
        <span className={dashboardFieldLabelCn}>Title</span>
        <ContentField format={fieldFormats?.title ?? "inline"} value={title} label="Title"
          placeholder="Enter section title…" onChange={(v) => { setTitle(v); emit({ title: v, body }); }} />
      </div>
      <div className="p-5">
        <span className={dashboardFieldLabelCn}>Body</span>
        <ContentField format={fieldFormats?.body ?? "rich"} value={body} label="Body"
          placeholder="Write content here…" onChange={(v) => { setBody(v); emit({ title, body: v }); }} />
      </div>
    </div>
  );
}
```

- [ ] **Step 4: `RepeaterEditor` — `inline` type, rich fields, stable keys**

- `SchemaField.type` gains `"inline"`.
- Replace `useState<ItemRecord[]>` with rows that carry a stable key:
  ```ts
  type Row = { key: string; item: ItemRecord };
  let keySeq = 0;
  const newKey = () => `r${Date.now().toString(36)}${(keySeq++).toString(36)}`;
  const toRows = (items: ItemRecord[]): Row[] =>
    items.map((item) => ({ key: typeof item._id === "string" && item._id ? item._id : newKey(), item }));
  ```
- `addItem` / `removeItem` / `moveItem` / `updateField` operate on rows, and `emit` sends `rows.map((r) => r.item)`. Render with `key={row.key}`.
- `FieldInput` rich branch, used when `richText`:
  ```tsx
  if (richText && field.type !== "tags") {
    const format: FieldFormat = field.type === "inline" ? "inline" : field.type === "richtext" ? "rich" : "plain";
    return <ContentField format={format} value={typeof value === "string" ? value : ""} label={field.label}
      inputType={field.type === "url" ? "url" : "text"} onChange={onChange} />;
  }
  ```
  The legacy branch (`!richText`) stays exactly as today; there, `inline` falls through to the plain `<input>`. Hide the "Supports Markdown" tooltip when `richText`.

- [ ] **Step 5: `KeyValueEditor` — per-entry formats, `_formats` round-trip, admin select**

- Rows become `{ id: string; key: string; value: string }`, using the same `newKey()` idea as Step 4.
- Add `const [formats, setFormats] = useState<Record<string, FieldFormat>>(() => parseFormats(initialContent._formats))`. `parseFormats` keeps only entries whose value is `plain`, `inline` or `rich`.
- `const hadFormats = "_formats" in initialContent`.
- `emit(nextRows, nextFormats = formats)` builds `entries` as today, then prunes `nextFormats` to keys present in `entries`. It calls `onChange({ entries, _formats: pruned })` whenever `richText || hadFormats`; otherwise it calls `onChange({ entries })` exactly as today.
- Renaming a key moves its format (`nextFormats[newKey] = nextFormats[oldKey]; delete nextFormats[oldKey]`). Deleting a row drops its format.
- Value cell when `richText`: `<ContentField format={formats[row.key.trim()] ?? "plain"} label={row.key.trim() || "New entry value"} … />`. The accessible label is the entry key, and the tests below query by it.
- When `richText && canEditStructure`, add a narrow `<select aria-label={`Format of ${row.key || "new entry"}`}>` column with options Plain / Inline / Rich. On change it calls `convertValue(row.value, old, new)`, updates both the row value and `formats`, and emits.
- The grid becomes `grid-cols-[1fr_2fr_auto_2rem]` when the select shows, otherwise `grid-cols-[1fr_2fr_2rem]`. Rich rows are taller, so align items to the top.

- [ ] **Step 6: Tests**

`TextBlockEditor.test.tsx`:
```tsx
import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { TextBlockEditor } from "../TextBlockEditor";

vi.mock("@/components/dashboard/rich-text/RichTextEditor", () => ({
  RichTextEditor: ({ label, value, mode }: { label: string; value: string; mode: string }) =>
    <div role="textbox" aria-label={label} data-mode={mode}>{value}</div>,
}));

describe("TextBlockEditor", () => {
  it("version 0 keeps the legacy input and textarea", () => {
    render(<TextBlockEditor initialContent={{ title: "t", body: "b" }} onChange={() => {}} />);
    expect(screen.getByDisplayValue("t").tagName).toBe("INPUT");
    expect(screen.getByDisplayValue("b").tagName).toBe("TEXTAREA");
  });
  it("version 1 renders inline title and rich body editors", () => {
    render(<TextBlockEditor initialContent={{ title: "t", body: "<p>b</p>" }} onChange={() => {}} richText
      fieldFormats={{ title: "inline", body: "rich" }} />);
    expect(screen.getByRole("textbox", { name: "Title" })).toHaveAttribute("data-mode", "inline");
    expect(screen.getByRole("textbox", { name: "Body" })).toHaveAttribute("data-mode", "rich");
  });
});
```
`RepeaterEditor.test.tsx` (the stateful mock mimics TipTap owning its state, which is exactly what exposes index keys):
```tsx
import { useState } from "react";
import { describe, expect, it, vi } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { RepeaterEditor } from "../RepeaterEditor";

vi.mock("@/components/dashboard/rich-text/RichTextEditor", () => ({
  RichTextEditor: ({ value, label }: { value: string; label: string }) => {
    const [held] = useState(value); // uncontrolled, like TipTap
    return <div data-testid="rte" aria-label={label}>{held}</div>;
  },
}));

const content = {
  _schema: [{ key: "body", label: "Body", type: "richtext" }],
  items: [{ body: "<p>first</p>" }, { body: "<p>second</p>" }],
};

describe("RepeaterEditor rich fields", () => {
  it("formatted text moves with its item", async () => {
    render(<RepeaterEditor initialContent={content} onChange={() => {}} richText />);
    await userEvent.click(screen.getAllByRole("button", { name: "Move down" })[0]);
    expect(screen.getAllByTestId("rte").map((n) => n.textContent)).toEqual(["<p>second</p>", "<p>first</p>"]);
  });
  it("removing an item removes its text, not the last one", async () => {
    render(<RepeaterEditor initialContent={content} onChange={() => {}} richText />);
    await userEvent.click(screen.getAllByRole("button", { name: "Remove item" })[0]);
    expect(screen.getAllByTestId("rte").map((n) => n.textContent)).toEqual(["<p>second</p>"]);
  });
  it("emits items without internal keys", async () => {
    const onChange = vi.fn();
    render(<RepeaterEditor initialContent={content} onChange={onChange} richText />);
    await userEvent.click(screen.getAllByRole("button", { name: "Move down" })[0]);
    expect(onChange).toHaveBeenLastCalledWith({ _schema: content._schema, items: [{ body: "<p>second</p>" }, { body: "<p>first</p>" }] });
  });
});
```
`KeyValueEditor.test.tsx`:
```tsx
import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { KeyValueEditor } from "../KeyValueEditor";
import { convertValue } from "@/components/dashboard/rich-text/ContentField";

vi.mock("@/components/dashboard/rich-text/RichTextEditor", () => ({
  RichTextEditor: ({ label, mode }: { label: string; mode: string }) => <div role="textbox" aria-label={label} data-mode={mode} />,
}));

const initial = { entries: { phone: "+40 7", about: "We &amp; you" }, _formats: { about: "inline" } };

describe("KeyValueEditor", () => {
  it("keeps _formats when rows are edited", async () => {
    const onChange = vi.fn();
    render(<KeyValueEditor initialContent={initial} onChange={onChange} richText />);
    await userEvent.type(screen.getByDisplayValue("+40 7"), "0");
    expect(onChange).toHaveBeenLastCalledWith({ entries: { phone: "+40 70", about: "We &amp; you" }, _formats: { about: "inline" } });
  });
  it("renders the inline editor for inline entries and inputs for plain ones", () => {
    render(<KeyValueEditor initialContent={initial} onChange={() => {}} richText />);
    expect(screen.getByRole("textbox", { name: "about" })).toHaveAttribute("data-mode", "inline");
    expect(screen.getByDisplayValue("+40 7").tagName).toBe("INPUT");
  });
  it("non-admins get no format select; admins do", () => {
    const { rerender } = render(<KeyValueEditor initialContent={initial} onChange={() => {}} richText />);
    expect(screen.queryByLabelText("Format of phone")).toBeNull();
    rerender(<KeyValueEditor initialContent={initial} onChange={() => {}} richText canEditStructure />);
    expect(screen.getByLabelText("Format of phone")).toBeInTheDocument();
  });
  it("deleting a row drops its format", async () => {
    const onChange = vi.fn();
    render(<KeyValueEditor initialContent={initial} onChange={onChange} richText />);
    await userEvent.click(screen.getAllByRole("button", { name: "Remove row" })[1]);
    expect(onChange).toHaveBeenLastCalledWith({ entries: { phone: "+40 7" }, _formats: {} });
  });
});

describe("convertValue", () => {
  it.each([
    ["A & B", "plain", "inline", "A &amp; B"],
    ["a\nb", "plain", "rich", "<p>a<br>b</p>"],
    ["A &amp; <strong>B</strong>", "inline", "plain", "A & B"],
    ["A <em>B</em>", "inline", "rich", "<p>A <em>B</em></p>"],
    ["<p>a</p><p>b &amp; c</p>", "rich", "inline", "a<br>b &amp; c"],
  ])("%s %s→%s", (v, f, t, e) => expect(convertValue(v, f as never, t as never)).toBe(e));
});
```
Legacy regression: the existing dashboard tests (`CmsSection.test.tsx` etc.) must still pass unchanged.

- [ ] **Step 7: Run and commit**

Run: `cd frontend && npx vitest run && npx tsc --noEmit && npm run lint`
Expected: green.

```bash
git add frontend/src/components/dashboard
git commit -m "feat(dashboard): rich-text fields in text block, repeater and key-value editors"
```

---

### Task 14: ServiceEditor hardening (unsaved work, errors)

**Files:**
- Modify: `frontend/src/components/dashboard/ServiceEditor.tsx`
- Test: `frontend/src/components/dashboard/__tests__/ServiceEditor.test.tsx` (new; copy the mocking setup from `CmsSection.test.tsx`)

**Interfaces:**
- Consumes: the existing `isDirty`, `setLocale`, `handleRetranslate` and `saveContent`.
- Produces: no new exports (behaviour only).

- [ ] **Step 1: Write the failing tests**

Copy the `vi.hoisted` + `vi.mock("next/navigation")` + `global.fetch` setup from `CmsSection.test.tsx`. Render `ServiceEditor` with a two-locale text_block detail at `rich_text_version: 0`, so the legacy textarea is easy to type in. Then:
1. After typing in the body textarea, a `beforeunload` event dispatched on `window` has `defaultPrevented === true`. Before typing, it doesn't.
2. With a dirty draft and `window.confirm` mocked to return `false`, clicking the other locale tab does **not** change the locale: no `router.replace`/`push` with `?locale=`, and the draft text is still present. With `confirm` returning `true`, it switches.
3. The same confirmation guards "Re-translate from …" when dirty.
4. When the save PUT responds `422 {"detail": "Field title is too long (2001 > 2000 characters)"}`, that exact text appears in the error banner. A pydantic-style `{"detail":[{"msg":"x"},{"msg":"y"}]}` shows `x; y`.

- [ ] **Step 2: Implement**

```tsx
// beforeunload guard while dirty
useEffect(() => {
  if (!isDirty) return;
  const onBeforeUnload = (e: BeforeUnloadEvent) => { e.preventDefault(); e.returnValue = ""; };
  window.addEventListener("beforeunload", onBeforeUnload);
  return () => window.removeEventListener("beforeunload", onBeforeUnload);
}, [isDirty]);

const confirmDiscard = () =>
  !isDirty || window.confirm("You have unsaved changes. Discard them?");
```
- Call `if (!confirmDiscard()) return;` at the top of `setLocale` (before it touches the URL) and of `handleRetranslate`.
- In `saveContent`'s error path, normalise `detail`: `Array.isArray(d) ? d.map((x) => x?.msg ?? String(x)).join("; ") : typeof d === "string" ? d : "Save failed"`.

- [ ] **Step 3: Run and commit**

Run: `cd frontend && npx vitest run && npx tsc --noEmit && npm run lint`
Expected: green.

```bash
git add frontend/src/components/dashboard
git commit -m "fix(dashboard): guard unsaved edits on unload, locale switch and re-translate; show save errors"
```

---

### Task 15: Data migration planner and CLI

**Files:**
- Create: `backend/auth_service/services/rich_text_migration.py`
- Create: `backend/scripts/migrate_rich_text.py`
- Test: `backend/auth_service/tests/test_rich_text_migration.py`

**Interfaces:**
- Consumes: `normalize_content`, `FORMATS` (Task 4); `segments_of`, `src_hash` (segments).
- Produces:
  - `MigrationConfig.from_dict(raw: dict) -> MigrationConfig` (raises `ValueError` on invalid types)
  - `unknown_config_refs(services: list[dict], cfg: MigrationConfig) -> list[str]`
  - `plan_project_migration(services: list[dict], cfg: MigrationConfig, default_locale: str) -> list[RowUpdate]`
  - `migration_sql(project_id: str, updates: list[RowUpdate]) -> str` (atomic `DO` block that sets version 1)
  - `restore_sql(project_id: str, rows: list[dict]) -> str` (atomic, sets version 0)
  - `RowUpdate` dataclass fields: `row_id, service_key, locale, updated_at, draft_content, published_content, translation_meta, diffs`
  - Each `services` item is shaped `{"service_key","service_type_slug","content_entries":[{"id","locale","draft_content","published_content","translation_meta","updated_at"}]}`.

- [ ] **Step 1: Write the failing tests**

`backend/auth_service/tests/test_rich_text_migration.py`:
```python
import pytest

from auth_service.services.rich_text_migration import (
    MigrationConfig,
    migration_sql,
    plan_project_migration,
    restore_sql,
    unknown_config_refs,
)
from auth_service.services.segments import src_hash

PID = "860792c9-24f7-43fc-97de-107a31ea7307"
R_EN, R_DE, R_KV, R_RP = (f"00000000-0000-0000-0000-00000000000{i}" for i in range(1, 5))


def _services():
    tb_en = {"title": "IT & Cloud", "body": "**Fast** repairs\n\n- a\n- b"}
    tb_de = {"title": "IT & Cloud DE", "body": "**Schnell**"}
    return [
        {"service_key": "hero", "service_type_slug": "text_block", "content_entries": [
            {"id": R_EN, "locale": "en", "draft_content": tb_en, "published_content": tb_en,
             "translation_meta": {}, "updated_at": "2026-09-27T10:00:00+00:00"},
            {"id": R_DE, "locale": "de", "draft_content": tb_de, "published_content": tb_de,
             "translation_meta": {"title": {"src_hash": src_hash("IT & Cloud")},
                                  "body": {"src_hash": "stale0000000000"}},
             "updated_at": "2026-09-27T10:00:01+00:00"},
        ]},
        {"service_key": "contact_info", "service_type_slug": "key_value", "content_entries": [
            {"id": R_KV, "locale": "en",
             "draft_content": {"entries": [{"key": "phone", "value": "+40 7"}, {"key": "about", "value": "We & you"}]},
             "published_content": {"entries": {"phone": "+40 7", "about": "We & you"}},
             "translation_meta": {}, "updated_at": None},
        ]},
        {"service_key": "features", "service_type_slug": "repeater", "content_entries": [
            {"id": R_RP, "locale": "en",
             "draft_content": {"_schema": [{"key": "title", "label": "T", "type": "string"},
                                           {"key": "desc", "label": "D", "type": "richtext"}],
                               "items": [{"_id": "i1", "title": "A & B", "desc": "*x*"}]},
             "published_content": {}, "translation_meta": {}, "updated_at": "2026-09-27T10:00:02+00:00"},
        ]},
    ]


CFG = MigrationConfig.from_dict({"repeaters": {"features": {"title": "inline"}},
                                 "key_values": {"contact_info": {"about": "inline"}}})


def _by_id(updates):
    return {u.row_id: u for u in updates}


def test_text_block_converted_in_draft_and_published():
    u = _by_id(plan_project_migration(_services(), CFG, "en"))[R_EN]
    expected = {"title": "IT &amp; Cloud", "body": "<p><strong>Fast</strong> repairs</p><ul><li><p>a</p></li><li><p>b</p></li></ul>"}
    assert u.draft_content == expected
    assert u.published_content == expected


def test_manual_override_hash_follows_converted_source_but_stale_stays_stale():
    u = _by_id(plan_project_migration(_services(), CFG, "en"))[R_DE]
    assert u.translation_meta["title"] == {"src_hash": src_hash("IT &amp; Cloud")}
    assert u.translation_meta["body"] == {"src_hash": "stale0000000000"}


def test_key_value_formats_applied_legacy_list_flattened_plain_untouched():
    u = _by_id(plan_project_migration(_services(), CFG, "en"))[R_KV]
    assert u.draft_content == {"entries": {"phone": "+40 7", "about": "We &amp; you"}, "_formats": {"about": "inline"}}
    assert u.published_content["entries"]["phone"] == "+40 7"


def test_repeater_schema_retyped_and_fields_converted():
    u = _by_id(plan_project_migration(_services(), CFG, "en"))[R_RP]
    assert u.draft_content["_schema"][0]["type"] == "inline"
    assert u.draft_content["items"][0] == {"_id": "i1", "title": "A &amp; B", "desc": "<p><em>x</em></p>"}
    assert u.published_content is None or u.published_content == {}


def test_unknown_refs_reported():
    cfg = MigrationConfig.from_dict({"repeaters": {"features": {"nope": "inline"}, "ghost": {"x": "inline"}},
                                     "key_values": {"contact_info": {"zzz": "rich"}}})
    refs = unknown_config_refs(_services(), cfg)
    assert any("ghost" in r for r in refs) and any("nope" in r for r in refs) and any("zzz" in r for r in refs)


def test_invalid_config_type_rejected():
    with pytest.raises(ValueError):
        MigrationConfig.from_dict({"repeaters": {"features": {"title": "html"}}})


def test_sql_is_one_atomic_block_with_guards_and_version_flip():
    sql = migration_sql(PID, plan_project_migration(_services(), CFG, "en"))
    assert sql.strip().startswith("do $") and sql.count("do $") == 1
    assert "rich_text_version <> 0" in sql
    assert f"id = '{R_EN}' and updated_at = '2026-09-27T10:00:00+00:00'::timestamptz" in sql
    assert f"id = '{R_KV}' and updated_at is null" in sql
    assert "if not found then raise exception" in sql
    assert f"update projects set rich_text_version = 1" in sql


def test_sql_rejects_bad_ids():
    bad = plan_project_migration(_services(), CFG, "en")
    bad[0].row_id = "x'; drop table projects; --"
    with pytest.raises(ValueError):
        migration_sql(PID, bad)


def test_restore_sql_sets_version_back():
    sql = restore_sql(PID, [{"id": R_EN, "draft_content": {"title": "x"}, "published_content": {},
                             "translation_meta": {}}])
    assert "rich_text_version = 0" in sql and f"id = '{R_EN}'" in sql
```

- [ ] **Step 2: Implement `services/rich_text_migration.py`**

```python
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
    def from_dict(cls, raw: dict) -> "MigrationConfig":
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
    if isinstance(entries, dict):
        return entries
    if isinstance(entries, list):
        return {
            e["key"]: e.get("value", "")
            for e in entries
            if isinstance(e, dict) and isinstance(e.get("key"), str) and e["key"].strip()
        }
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
        if "entries" in c:
            c["entries"] = _entries_dict(c["entries"])
        if key in cfg.key_values:
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
            out.append((meta_key, json.dumps(bv, ensure_ascii=False), json.dumps(av, ensure_ascii=False)))
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
            new_meta = meta if row["locale"] == default_locale else _rehash(stype, meta, d_old, d_new)
            if new_draft == old_draft and new_pub == old_pub and new_meta == meta:
                continue
            updates.append(RowUpdate(
                row_id=row["id"], service_key=key, locale=row["locale"], updated_at=row.get("updated_at"),
                draft_content=new_draft if new_draft != old_draft else None,
                published_content=new_pub if new_pub != old_pub else None,
                translation_meta=new_meta if new_meta != meta else None,
                diffs=_diffs(stype, old_draft if old_draft is not None else old_pub,
                             new_draft if new_draft is not None else new_pub),
            ))
    return updates


def _check_id(value: str) -> str:
    if not isinstance(value, str) or not _UUID_RE.match(value):
        raise ValueError(f"refusing to interpolate non-uuid id {value!r}")
    return value


def _lit(obj: object, tag: str) -> str:
    s = json.dumps(obj, ensure_ascii=False)
    if f"${tag}$" in s:
        raise ValueError("dollar-quote collision; re-run")
    return f"${tag}${s}${tag}$::jsonb"


def migration_sql(project_id: str, updates: list[RowUpdate]) -> str:
    pid = _check_id(project_id)
    tag = "j" + secrets.token_hex(6)
    lines = [
        f"do $mig_{tag}$",
        "begin",
        f"  if (select rich_text_version from projects where id = '{pid}') <> 0 then",
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
        lines.append(f"  update content_entries set {', '.join(sets)} where id = '{rid}' and {guard};")
        lines.append(
            f"  if not found then raise exception 'rich-text migration conflict on row {rid} "
            f"(edited since planning) — re-plan and apply again'; end if;"
        )
    lines += [
        f"  update projects set rich_text_version = 1, updated_at = now() where id = '{pid}';",
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
            f"published_content = {_lit(r.get('published_content') or {}, tag)}, "
            f"translation_meta = {_lit(r.get('translation_meta') or {}, tag)}, updated_at = now() "
            f"where id = '{rid}';"
        )
    lines += [
        f"  update projects set rich_text_version = 0, updated_at = now() where id = '{pid}';",
        "end",
        f"$rst_{tag}$;",
    ]
    return "\n".join(lines) + "\n"
```
The `draft_content` column is nullable, so `_lit(None)` renders `null::jsonb` — valid.

- [ ] **Step 3: Implement the CLI `backend/scripts/migrate_rich_text.py`**

```python
"""Rich-text migration for ONE version-0 project (spec §8, ADR-0010).

  python scripts/migrate_rich_text.py --project <slug> --formats <config.json>            # dry run
  python scripts/migrate_rich_text.py --project <slug> --formats <config.json> --emit-sql # + SQL + backup
  python scripts/migrate_rich_text.py --restore <backup.json> --emit-sql                  # rollback SQL

Apply the emitted SQL with the Supabase MCP execute_sql (or scripts/apply_supabase_migration.py).
Output goes to backend/scripts/.rich-text-work/ (gitignored: contains client content)."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))
WORK = BACKEND / "scripts" / ".rich-text-work"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--project")
    ap.add_argument("--formats", help="JSON config: {repeaters:{svc:{field:type}}, key_values:{svc:{key:fmt}}}")
    ap.add_argument("--emit-sql", action="store_true")
    ap.add_argument("--restore", help="backup JSON written by a previous --emit-sql")
    args = ap.parse_args()

    from dotenv import load_dotenv

    load_dotenv(BACKEND / ".env")
    from auth_service.services.rich_text_migration import (  # noqa: E402
        MigrationConfig, migration_sql, plan_project_migration, restore_sql, unknown_config_refs,
    )

    WORK.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")

    if args.restore:
        backup = json.loads(Path(args.restore).read_text("utf-8"))
        out = WORK / f"{backup['slug']}-{stamp}.restore.sql"
        out.write_text(restore_sql(backup["project_id"], backup["rows"]), "utf-8")
        print(f"restore SQL → {out}")
        return 0

    if not args.project:
        ap.error("--project is required")
    sb = _supabase()
    proj = (sb.table("projects").select("id, slug, default_locale, rich_text_version")
            .eq("slug", args.project).single().execute().data)
    if int(proj.get("rich_text_version") or 0) >= 1:
        print(f"{args.project}: already migrated (rich_text_version=1) — nothing to do")
        return 0
    services = (sb.table("project_services")
                .select("service_key, service_type_slug, content_entries(id, locale, draft_content, "
                        "published_content, translation_meta, updated_at)")
                .eq("project_id", proj["id"]).execute().data) or []
    cfg = MigrationConfig.from_dict(json.loads(Path(args.formats).read_text("utf-8")) if args.formats else {})
    problems = unknown_config_refs(services, cfg)
    if problems:
        print("config references things that don't exist:\n  " + "\n  ".join(problems), file=sys.stderr)
        return 1
    updates = plan_project_migration(services, cfg, proj.get("default_locale") or "en")
    for u in updates:
        print(f"\n[{u.service_key} / {u.locale}] row {u.row_id}")
        for path, before, after in u.diffs:
            print(f"  {path}\n    - {before!r}\n    + {after!r}")
    print(f"\n{len(updates)} row(s) to update in {args.project}")
    if not args.emit_sql:
        print("dry run — re-run with --emit-sql to write the atomic SQL + backup")
        return 0
    touched = {u.row_id for u in updates}
    rows = [dict(r, service_key=s["service_key"]) for s in services
            for r in (s.get("content_entries") or []) if r["id"] in touched]
    backup = WORK / f"{args.project}-{stamp}.backup.json"
    backup.write_text(json.dumps({"project_id": proj["id"], "slug": args.project, "created_at": stamp,
                                  "rows": rows}, ensure_ascii=False, indent=1), "utf-8")
    sql = WORK / f"{args.project}-{stamp}.sql"
    sql.write_text(migration_sql(proj["id"], updates), "utf-8")
    print(f"backup → {backup}\nSQL    → {sql}\nApply the SQL with Supabase MCP execute_sql.")
    return 0


def _supabase():
    # Use the same admin client factory the backend uses (see auth_service routers' get_supabase_admin import).
    from auth_service.supabase_client import get_supabase_admin  # adjust to the real module path

    return get_supabase_admin()


if __name__ == "__main__":
    raise SystemExit(main())
```
Before running, find the real module path of `get_supabase_admin` (`grep -rn "def get_supabase_admin" backend/auth_service`) and fix the import in `_supabase()`. Also confirm `python-dotenv` is in `backend/requirements*.txt`. If it isn't, load `.env` with a small manual `KEY=VALUE` parser instead of adding a dependency.

- [ ] **Step 4: Run tests, dry-run against a real project, and commit**

Run: `python -m pytest auth_service/tests/test_rich_text_migration.py -q && cd .. && make test-backend`

Then do a read-only smoke run. The dry run writes nothing to the DB:
`cd backend && source venv/Scripts/activate && python scripts/migrate_rich_text.py --project e2e-test-project`
Expected: it prints a plan and "dry run", with no errors.

```bash
git add backend/auth_service/services/rich_text_migration.py backend/auth_service/tests/test_rich_text_migration.py backend/scripts/migrate_rich_text.py
git commit -m "feat(backend): atomic rich-text data migration planner and CLI"
```

---

### Task 16: Ship the CMS (controller-run, operational)

**Files:**
- Modify: `e2e/` specs that type into the text_block body `textarea` (find them with `grep -rn "textarea" e2e/tests`) — they must also work with a TipTap `role="textbox"`.
- Modify: `docs/` files invalidated by this change (grep for "Markdown supported", "richtext" and "react-markdown" under `docs/`; fix or delete in the same commit).

- [ ] **Step 1: Full gate**

Run: `make ci`
Expected: green (lint, backend, agent, frontend, kit, kit-sync-check, docs-check). Fix anything red before continuing.

- [ ] **Step 2: E2E selector update**

- For specs that edit a text_block: when the project is at `rich_text_version` 1, target `page.getByRole("textbox", { name: "Body" })`. Use `.click()` + `keyboard.type()` instead of `.fill()`, because TipTap is a contenteditable.
- Keep the textarea path working for version-0 projects.

Commit: `git commit -am "test(e2e): drive the rich-text editor"`.

- [ ] **Step 3: Whole-branch review before merge**

Dispatch the final whole-branch code reviewer (per subagent-driven-development) over `origin/dev..feat/rich-text`. Fix confirmed findings, then run `make ci` again.

- [ ] **Step 4: Merge to dev and push**

```bash
git fetch origin && git checkout dev && git pull --ff-only origin dev
git merge --no-ff feat/rich-text -m "Merge feat/rich-text: CMS rich text (ADR-0010)"
git push origin dev
git checkout feat/rich-text
```
If the push fails with 403 as the wrong GitHub user, run `gh auth switch -u stefanroman22 && gh auth setup-git` and retry.

- [ ] **Step 5: Verify the dev preview**

- Use the Vercel MCP (`list_deployments` for `cms-backend-roman` and `roman-technologies`, target preview) to confirm both dev deploys reached READY. Use `get_deployment` build logs on failure.
- Hit the dev backend: `GET <dev-backend>/content/e2e-test-project` must contain `"rich_text_version"`.
- Migrate `e2e-test-project` (config `{}`) through Task 15's CLI (`--emit-sql`), apply the SQL with MCP `execute_sql`, and confirm `select rich_text_version from projects where slug='e2e-test-project'` is `1`.
- If `e2e/.env.local` exists, run `cd e2e && npm test` against the dev preview (`PLAYWRIGHT_DEPLOYED_STATE` per the e2e README). If the credentials aren't available, record the manual dashboard checks for Stefan in the final report: format text in a text_block, save, reload, publish.

- [ ] **Step 6: Promote dev → main**

Run: `gh workflow list` to find the "Promote dev → main" workflow, then `gh workflow run "<name>" --ref dev` and `gh run watch`.
Expected: success. Verify prod: `curl -s https://cms-backend-roman.vercel.app/content/it-global-services | grep -o '"rich_text_version":[0-9]'` → `"rich_text_version":0` (the sites aren't migrated yet).

---

## Site rollout tasks (17–20) — shared procedure

Each site task follows this procedure exactly. The site-specific notes in each task list the known render sites, which came from exploring every client repo on 2026-09-27. **Re-verify them in the code**: the notes are a starting map, not a substitute for reading.

**R1. Prepare.** `cd <site repo>`, `git fetch`, check out the preview branch (`cms-preview`), fast-forward it to the production branch if it lags (`git merge --ff-only origin/<prod>`), and confirm a clean tree. Never build while a dev server of the same repo is running.

**R2. Vendor the kit.** `node "c:/Users/stefa/.gemini/antigravity/scratch/CMS - websites/client-kit/rich-text/scripts/sync-rich-text-kit.mjs" <site>/src/lib/cms-rich-text` (Next sites without `src/`: `lib/cms-rich-text`). Import `cms-rich.css` once (Next: root layout; Vite: `main.tsx`). Exclude the vendored folder from the site's formatter/linter if they would rewrite it.

**R3. Theme.** Define the `--cms-rich-*` variables in the site's global CSS from its existing palette: on `:root` (or the default theme), the dark-theme selector (if any), and every inverted surface (hero, dark sections, footer, header). Rules:
- Bold: text colour plus weight by default. Use an accent **only** where its contrast against that surface is ≥ 4.5:1. Compute it with
  `node -e "const L=h=>{const c=h.match(/\w\w/g).map(x=>parseInt(x,16)/255).map(v=>v<=.03928?v/12.92:((v+.055)/1.055)**2.4);return .2126*c[0]+.7152*c[1]+.0722*c[2]};const[a,b]=process.argv.slice(1).map(L);console.log(((Math.max(a,b)+.05)/(Math.min(a,b)+.05)).toFixed(2))" 49d4fc 142845`.
- Links: the brand/link colour already used by the site, with hover.
- Markers: brand or accent, subtle. Quote border: accent. Rule: muted.

**R4. Wire every CMS text render site** (spec §9 rules; README "Field-usage rules"):
- Display prose → `<RichText value={x} format="inline|rich" />`. **Rich values must not sit inside `<p>`, `<h*>` or `<span>`**, because block elements inside `<p>` cause invalid HTML and hydration errors. Replace the wrapper with `<RichText as="div" className={oldClasses} …>`. Inline values may sit inside `<p>`/`<h*>` (they render a `<span>`).
- Metadata, JSON-LD, `alt`/`aria-*`, React keys, search/filter, `href`/`tel:`/`mailto:` building, `Number()`, `.split()` for logic → `plainText(x)` (use `{ format: "rich" }` for rich values).
- Per-word animations and "last N words accented" logic → `splitRichWords` / `<RichWords>`.
- Values inside an element that is already a link/button → `links={false}`.
- Internal links → `renderLink` with the site's router `Link`.
- Fields that stay `plain` (URLs, phones, emails, slugs, hours, numbers, alt text) are untouched.

**R5. Formats config.** Write `<site>/cms-rich-text.formats.json` (commit it — it documents the site's contract):
`{"repeaters": {"<svc>": {"<field>": "inline"|"richtext"|"string"}}, "key_values": {"<svc>": {"<entry>": "plain"|"inline"|"rich"}}}`.
- Classify every repeater `string` field and every key_value entry from how the site uses it after R4. Prose you wired to `<RichText format="inline">` → `inline`; multi-sentence body copy wired to `format="rich"` → `richtext`/`rich`; machine values → leave out (they stay plain).
- text_block title/body need no config (always inline/rich).
- Read the current `_schema` / entries straight from the DB (Supabase MCP `execute_sql` on `content_entries` joined to `project_services` for the project) so the config uses real keys.
- **Every field made rich/inline in the config must have all its render sites wired in R4.** Otherwise a converted value would show `&amp;` or tags on the live site.

**R6. Verify on legacy data (still version 0).** Run the site's build and lint. Run it locally, then use Playwright (MCP) on the pages that render CMS text. Checks:
- No console errors or hydration warnings.
- Pages look the same as production: compare screenshots of the hero and one content section against the live production URL.
- Metadata is unchanged (`document.title`, `meta[name=description]`).
- Legacy Markdown fields (where they exist) now render real `<strong>`/lists instead of literal `**`.

**R7. Ship the code.** Commit (one plain line, no attribution), then:
- Push the preview branch. Wait for the Vercel preview (Vercel MCP `list_deployments` for the site project) and repeat the R6 checks on the preview URL.
- Push the **same commit** to the production branch (`git push origin cms-preview:<prod>`). Wait for the production deploy and re-check production.

The site is now safe for both data forms.

**R8. Migrate the data.** From the CMS repo (`backend/`):
- `python scripts/migrate_rich_text.py --project <slug> --formats <site>/cms-rich-text.formats.json` (dry run). Read every diff: plain values must be untouched, and nothing may be double-escaped.
- Re-run with `--emit-sql`, and apply the SQL file's contents with Supabase MCP `execute_sql`.
- Confirm `rich_text_version = 1`.
- Keep the backup JSON path in your report.

**R9. Verify on migrated data** (local, preview and production, every locale, light and dark):
- Formatted fields render correctly and the theme colours apply.
- Compute the style of a `strong` inside `.cms-rich` on a light surface and on a dark surface with Playwright `browser_evaluate` (`getComputedStyle(el).color`) and compare against the variables you set.
- Metadata and JSON-LD are plain.
- `tel:`/`mailto:` links are intact.
- No literal tags or `&amp;`, and no console errors.

**R10. Real formatted edit (draft only, then restore).** Pick one rich field and one inline field.
- Save the current `draft_content` value.
- Set a test value (`<p>Test <strong>bold</strong> <em>italic</em> <u>under</u> <a href="https://example.com">link</a></p><ul><li><p>one</p></li></ul><p></p><p>after blank line</p>` for rich; `Test <strong>bold</strong> &amp; more` for inline) via `execute_sql` `jsonb_set` on **draft_content only**.
- Verify on the preview deployment and locally (both read drafts). Bullets must be visible, the blank line must keep its height, and the external link must open in a new tab.
- Restore the exact saved draft value. Published content (production) is never touched.

**R11. Report.** Files changed, formats config, backup path, deployment URLs checked, screenshots taken, and any render site you intentionally left plain (with the reason).

---

### Task 17: it-global-services (Next 16 + next-intl, Tailwind v4, `data-theme` dark mode)

Repo: `c:\Users\stefa\.gemini\antigravity\scratch\George Site - parinti\it-global-services`. Branches: `cms-preview` → `main`. Vercel project `it-global-services` (prod URL `https://it-global-services.vercel.app`). Locales: ro (default, unprefixed), en, hu, de, fr, it. `.env.local` reads the **draft** endpoint.

**Before starting:** a `next dev` process from an earlier session may still be serving port 3007 for this repo. Stop it first (`netstat -ano | grep :3007` → `taskkill //PID <pid> //F`).

Known render sites (re-verify):
- CMS client: `src/lib/cms.ts` (`textBlock`, `image`, `keyValue`, `repeater`, `contactInfo`, `keyFeatures`, `servicesCatalog`); mapping in `src/data/services.ts` `toService()`.
- `src/app/[locale]/page.tsx:45-65`: `general_tagline` title split into base + last-2-words accent → use `splitRichWords`, take the accent from the last two tokens, pass tokens to `Hero`.
- `src/components/sections/Hero.tsx`: per-word animated spans (~line 69–93) → render `RichWord.node` inside each `motion.span`; accent in `text-[#49d4fc]`; `home_hero_subhead` in a `motion.p` → `format="inline"` (or rich with the `motion.div` wrapper).
- `ServicesGrid.tsx`, `WhyChooseUs.tsx`, `CtaBand.tsx`, `ServiceCard.tsx` (card is a link → `links={false}`), `ServicePageContent.tsx` (`fullDescription` in a `<p>` → rich as div; `features[]` stay tags/plain), `PageBanner.tsx`, `about/AboutPageContent.tsx` (`RichBody` hand-parser → replace with `<RichText format="rich">` and delete `RichBody`), `contact/ContactPageContent.tsx`, `ContactForm.tsx`.
- `SectionMarquee.tsx` (whitespace-nowrap marquee of feature titles → inline, `links={false}`, key via `plainText`).
- `Footer.tsx` `footer_description` → inline/rich; `Header.tsx` / `Footer.tsx` / `MobileMenu.tsx` brand wordmark split + SRL regex → operate on `plainText(brandName)`.
- Non-display: `layout.tsx:45-70,118-135` (title, OG, JSON-LD) → `plainText`. Banner titles/subtitles in `generateMetadata` and `services/[slug]/page.tsx:78-79` → `plainText`. `contactFields.ts` → keep plain. React keys from titles → `plainText`.

Theme (from `src/app/globals.css`):
- Light surfaces use `--ink`.
- The header/hero/footer bars are navy (`--header-bg` `#2a5088` light / `#142845` dark), where the cyan accent `#49d4fc` is the natural emphasis colour. Check its contrast on both navies with the R3 script.
- Dark theme: `[data-theme="dark"]`.

Formats guidance:
- `key_features.title` inline, `key_features.description` inline or rich (it renders in a `<p>`).
- `services_catalog.title` inline; `short_description` inline; `full_description` rich (if already `richtext`, leave it).
- `slug` / `animation` / `features` stay as they are.
- `contact_info` entries all plain.

Follow R1–R11.

### Task 18: laurian-duma-portfolio (Vite 8 SPA, Tailwind v3, always dark)

Repo: `c:\Users\stefa\.gemini\antigravity\scratch\Laurian Duma - Portofolio Website`. Branches: `cms-preview` → **`master`**. Vercel project `laurian-duma-portfolio`. Single locale (en).

Known render sites (re-verify):
- CMS client `src/lib/cms.ts` (`useCMSContent`, `getService`, `withFallback`, `entriesToRecord`); types `src/lib/cms.types.ts` (regenerate with `npm run cms:sync-types` after the backend deploy so `rich_text_version` appears).
- `src/views/AboutView.tsx`: cv name/title (inline); `summary` in a `<p>` → rich as div; email/github/linkedin stay plain (hrefs); skills entries: keys are codes (plain), values are labels (inline).
- `ExperienceView.tsx`: period, role, company (inline); `bullets[]` stay `tags`/plain, and each is also a React key.
- `HobbiesView.tsx`: icon emoji plain; name inline (uppercase styling still applies); description inline or rich.
- `ProjectsView.tsx`: name inline (also `aria-label` → `plainText`); description rich; `tags[]` plain; repo/url plain.
- `ContactView.tsx`: all plain.

Theme: `tailwind.config.js` palette (primary `#86adff`, tertiary `#69fd5d`, surfaces dark). Set the variables on `:root` in `src/index.css`: strong = on-surface text colour (or primary if ≥ 4.5:1), link = primary, marker = tertiary.

Tests: Vitest exists. Add `tests/components/RichTextUsage.test.tsx`, rendering `AboutView` with a mocked CMS payload containing formatted `summary`, and assert a `<strong>` renders inside `.cms-rich`.

Follow R1–R11. In R7 push `cms-preview`, then `git push origin cms-preview:master`.

### Task 19: akris (Vite 6 SPA, Tailwind v3 via CDN, react-markdown)

Repo: `c:\Users\stefa\.gemini\antigravity\scratch\Akris-main` (remote `akris-website`). Branches: `cms-preview` → `main`. Vercel project `akris-website`. Single locale (en).

Known render sites (re-verify):
- CMS hooks in `getData/getCmsContent.tsx` and `hooks/*.tsx`.
- `components/Markdown.tsx` (react-markdown + remark-breaks; strong in `text-primary`) is used by `pages/NewsDetail.tsx` and `pages/OATK.tsx` → replace with `<RichText format="rich" as="div" className="prose prose-invert">` and delete `Markdown.tsx`. Remove `react-markdown` and `remark-breaks` from `package.json` once unused. The kit renders legacy Markdown until the migration, so there is no gap.
- `Hero.tsx`: `hero.heading`/`description` go to `FadeInText`, which does `text.split(" ")` → rewrite `components/FadeInText.tsx` to use `splitRichWords` (keep its motion behaviour).
- `BoardMembers.tsx`:
  - `member.function` is compared to `'Chair'` → keep plain or compare `plainText(...)`.
  - `quote` → inline (italic `<p>`).
  - Name and major → inline.
  - Category name.
- `pages/News.tsx`: title (also img `alt` and search filter → `plainText`); `NewsDetail.tsx` title.
- `pages/History.tsx`, `AboutAkris.tsx`, `About.tsx` (`trainingDays` split on commas → plain), `RegistrationForm.tsx`.
- Settings coerced with `Number()` stay plain.

Theme: the CDN Tailwind config in `index.html` (`primary #36e27b`, dark backgrounds). Put the variables in the site's CSS entry (create `src/cms-theme.css` if there's no global CSS) on `:root`: strong = `#36e27b` if ≥ 4.5:1 on the dark background (the old `Markdown.tsx` used `text-primary` for strong, so keep that look); link = primary; marker = primary.

Tests: none exist. Rely on build + Playwright.

Follow R1–R11.

### Task 20: samir-kapsalon (Next 16 + next-intl ICU messages)

Repo: `c:\Users\stefa\.gemini\antigravity\scratch\samir-kapsalon`. Branches: `cms-preview` → `main`. The local checkout is `feat/booking-fresha-layout`, whose HEAD equals `origin/cms-preview`. Create or refresh a local `cms-preview` tracking branch in R1. Vercel project `samir-kapsalon`. Locales nl (default), en.

**This is the riskiest site.** `lib/cms-content.ts` `withCmsContent()` deep-merges CMS values into next-intl messages, and components read them with `t("…")`, which parses ICU. A plain `t()` on a value containing tags throws ("didn't resolve to a string… use t.rich"), and an inline value like `We &amp; you` would print `&amp;`. Rules:
- For every CMS key you convert (R5), change **every** consumer to `t.raw("key")`, then `<RichText>` (display) or `plainText(...)` (metadata, alt, keys, hrefs). Grep for every `t("ns.key")`/`t('key')` usage of those keys, including `generateMetadata`.
- Values already read via `t.raw()` (`diensten.groups`/`notes`, `team.members`, `reviews.items`, `servicesTeaser.items`, `galleryTeaser.alts`) just need `<RichText>`/`plainText` at render.
- Keys you do not convert stay on `t()` exactly as today.
- `lib/cms-content.ts` passes values through untouched. Make sure nothing there escapes or splits converted values.

Known render sites (re-verify):
- `components/sections/Hero.tsx:27-35` (title lines in `<em class="hero-em">` → inline inside the `em`)
- `AboutStrip.tsx`, `TrustBand.tsx`, `ServicesTeaser.tsx`, `Reviews.tsx` (`r.text` in a `<blockquote>` → rich as div inside the blockquote or inline; `r.author` is a key → `plainText`)
- `LocationStrip.tsx`, `BookingStrip.tsx`, `GalleryTeaser.tsx`, `InstagramStrip.tsx`, `MapCard.tsx`, `chrome/Footer.tsx`
- `app/[locale]/diensten/page.tsx`, `team/page.tsx`, `contact/page.tsx`, `galerij/page.tsx`, `PageHeader.tsx`, `BookingForm.tsx:690`

Non-display uses (keep plain / `plainText`):
- `metaTitle`/`metaDescription`
- All `*Alt` values
- Contact `phone` (normalised to E.164), `instagram`, `address` (comma-split), `maps_url`
- Hours `open`/`close` (sliced)
- The crumbs `aria-label`
- React keys from names/titles

Theme: `app/globals.css` oklch tokens (`--foreground`, `--accent`, `.hero-em`, `.eyebrow`). The dark block exists but isn't user-toggled. Define the variables on `:root`, plus dark sections if any.

Tests: Playwright e2e (`tests/e2e/site.spec.ts`, `next start` on port 3100). Run it in R6 and R9 and extend it with one formatted-text assertion (a `.cms-rich strong` exists on the home page after R10's draft edit — or keep that assertion manual if it would need the draft).

Follow R1–R11.

---

### Task 21: CMS Connector agent update

**Files** (all in the CMS repo):
- Modify: `agents/CMS Connector - Website/prompts.py` (service shapes table ~L27-40, field types ~L40, manifest `item_schema` ~L154)
- Modify: `agents/CMS Connector - Website/scan.py` (`_repeater_seed_content` ~L557-569 and the create/seed calls ~L616-694)
- Modify: `agents/CMS Connector - Website/AGENTS.md` (glossary ~L160, "Generated client website contracts" ~L100-126)
- Modify: `agents/CMS Connector - Website/phases/2-scan.md`, `phases/4-integration.md` (§4.1.6), `phases/5-testing.md` (5i)
- Modify: `agents/CMS Connector - Website/LEARNINGS.md` (append only)
- Modify: `.claude/skills/cms-connector-website/SKILL.md` (untracked — commit with `git add -f`)
- Test: `agents/CMS Connector - Website/tests/` (add cases)

**Interfaces:**
- Consumes: backend create/seed API (Task 5), which now accepts repeater type `inline` and a key_value `formats` map on create; kit README (Task 11).
- Produces: new client sites are provisioned at `rich_text_version` 1 (DB default) with correct formats, seeded with canonical HTML, and wired to the kit.

- [ ] **Step 1: Scan prompt and docs**

In `prompts.py`, update the shapes table to:
```
| text_block | { title?: InlineHtml, body?: RichHtml } |
| key_value  | { entries: Record<string,string>, _formats?: Record<string,"plain"|"inline"|"rich"> } |
| repeater   | { _schema: [{key,label,type}], items: object[] } |
Repeater field types: `string` (plain), `inline` (bold/italic/underline/strike/link/line breaks), `richtext` (full: paragraphs, headings h2–h4, lists, quotes, dividers), `url`, `tags`.
```
Add a classification rule block:
- Prose the client should be able to format → `inline` (titles, labels, short lines) or `richtext` (bodies, descriptions, bios, anything that could hold a list).
- Machine values stay `string`/`url`/plain: URLs, emails, phone numbers, addresses parsed by code, hours, prices used as numbers, slugs, alt text, anything feeding `href`/`tel:`/`mailto:`/`Number()`/regex.
- Key-value entries get `_formats` the same way (default `plain`).
- Source rich text (Markdown, Portable Text, HTML in the old site) is emitted as **canonical HTML** in the seed (allowed tags only), never Markdown.

Mirror the same in `phases/2-scan.md` (report must list each field's format) and in the `AGENTS.md` glossary. Add "field formats" to the contracts section, with a link to ADR-0010 and the kit README.

- [ ] **Step 2: Provisioning code (`scan.py`)**

- Pass key_value `formats` on the create call (from the manifest's per-entry formats).
- Include `_formats` in the key_value seed payloads, the same way `_repeater_seed_content` grafts `_schema`.
- Accept `inline` in any local type validation.
- Add tests in `agents/CMS Connector - Website/tests/`:
  - A manifest with `inline`/`richtext` fields and key_value formats produces create payloads with `item_schema` types and `formats`.
  - Seed payloads carry `_formats` and HTML values.

  Follow the existing test style there. Run `make test-agent`.

- [ ] **Step 3: Integration phase (§4.1.6)**

Add a numbered point "Rich text (ADR-0010)":
- Vendor the kit (sync command); import `cms-rich.css`.
- Define `--cms-rich-*` on every surface (the R3 rules).
- Render rules (the R4 table), including the next-intl `t.raw` rule for message-merged content and the no-rich-in-`<p>` rule.
- Write `cms-rich-text.formats.json` for the record.
- New projects are already at `rich_text_version` 1, so no migration is needed.

- [ ] **Step 4: Testing phase (5i)**

Extend the probe:
- For one inline and one rich field, write a formatted probe (`<strong>`, a link, a list for rich) to the draft.
- Assert on preview/localhost that `.cms-rich strong`, `.cms-rich a[href]` and `.cms-rich li` exist, and that no literal `<strong>` / `&lt;` / `**` text is visible.
- Assert the computed colour of `strong` equals the site's `--cms-rich-strong` on that surface.
- Then restore, as 5i already does.

- [ ] **Step 5: LEARNINGS + SKILL.md**

Append to `LEARNINGS.md` under "Phase 2" and "Phase 4" (format `- 2026-09-27: <rule>. Triggered by: CMS rich text rollout (ADR-0010).`):
1. Rich text is canonical HTML with field formats, rendered by the kit. This supersedes the 2026-06-17 Markdown + react-markdown rule for new work.
2. Never `t()` a rich/inline value; use `t.raw` + `<RichText>`.
3. Never put a rich value inside `<p>`.

Update `SKILL.md` to reference the kit README and the new 5i assertions.

- [ ] **Step 6: Commit**

```bash
git add "agents/CMS Connector - Website"
git add -f .claude/skills/cms-connector-website/SKILL.md
git commit -m "feat(agents): connector provisions field formats, seeds HTML, wires the rich-text kit"
```

---

### Task 22: Website Builder agent and generation skills

**Files:**
- Modify: `agents/Website Builder/phases/3-scaffold.md`, `phases/4-implement.md`, `phases/8-verify.md`, `AGENTS.md` (hard constraints + skills table)
- Modify: `agents/Website Builder/learnings-template/frontend-patterns.md` (§4 TextReveal), `learnings-template/conventions.md`, `agents/Website Builder/LEARNINGS.md`
- Modify: `.claude/skills/vite-react-scaffolding/SKILL.md`, `.claude/skills/i18n-setup/SKILL.md`, `.claude/skills/design-handoff/SKILL.md` (untracked → `git add -f`)

- [ ] **Step 1: Scaffold and implement phases**

- `3-scaffold.md`:
  - Add a step: vendor the kit into `src/lib/cms-rich-text/` and import `cms-rich.css` in `src/main.tsx`.
  - Define the `--cms-rich-*` variables in `src/index.css` from the design tokens (`tokens.richText` from design-handoff, else derived by the R3 contrast rule), for every surface the design has.
- `4-implement.md`: add the render rules (R4 table) and "CMS prose is rendered with `<RichText>`, never `dangerouslySetInnerHTML`, never inside `<p>`".
- `AGENTS.md`: add both as hard constraints.

- [ ] **Step 2: Verify gates (`8-verify.md`)**

- REQUIRE grep: `cms-rich-text` import present; `--cms-rich-strong` defined in CSS.
- FAIL grep: `dangerouslySetInnerHTML` outside the JSON-LD script; `react-markdown`.
- Add a Playwright check: a `.cms-rich` element renders with the themed `strong` colour.

- [ ] **Step 3: Patterns and learnings**

- `frontend-patterns.md` §4: the TextReveal pattern must use `splitRichWords` (show the adapted snippet).
- `conventions.md`: add `### CMS — rich text via the kit` (Rationale / Established 2026-09-27 / Source ADR-0010).
- `LEARNINGS.md`: a new top entry in its format.

- [ ] **Step 4: Skills**

- `vite-react-scaffolding`: add `lib/cms-rich-text/` and the css import to the folder tree. The kit has no deps, so no `manualChunks` change is needed; say so explicitly.
- `i18n-setup`: CMS rich values that flow through react-i18next are read as raw strings and rendered with `<RichText>`. Don't interpolate them into other translations.
- `design-handoff`: add a `tokens.richText` slot to the manifest schema: `{ strong, em, link, linkHover, marker, heading, quoteBorder, rule }` per surface (`light`, `dark`, `inverted`), plus the contrast rule.

- [ ] **Step 5: Docs check and commit**

Run: `make docs-check` → green.

```bash
git add "agents/Website Builder"
git add -f .claude/skills/vite-react-scaffolding/SKILL.md .claude/skills/i18n-setup/SKILL.md .claude/skills/design-handoff/SKILL.md
git commit -m "feat(agents): website builder scaffolds the rich-text kit and theme variables"
```

---

### Task 23: Final review, second promote, cleanup (controller)

- [ ] **Step 1: Cross-check the live system**

- For each of the 4 projects: `select slug, rich_text_version from projects` → 1.
- `GET /content/<slug>` returns `"rich_text_version":1`.
- Production site home page: no console errors.
- The dashboard's service detail for one project returns `field_formats`.

- [ ] **Step 2: Whole-branch review of agent/skill changes**

Dispatch a reviewer over the Task 21–22 diff for consistency with ADR-0010 and the kit README.

- [ ] **Step 3: Cleanup per CLAUDE.md**

- Delete `docs/superpowers/specs/2026-09-27-cms-rich-text-design.md` and `docs/superpowers/plans/2026-09-27-cms-rich-text.md`. ADR-0010 and the kit README are the lasting docs.
- Commit on `feat/rich-text`, merge to `dev`, push, `make ci`, then promote dev → main again.

- [ ] **Step 4: Memory + report**

Update the project memory (a new file for the rich-text system with an index line; mark the old Markdown-convention notes as superseded). Report to Stefan:
- What shipped.
- Per-site formats and verification evidence.
- Backup files.
- Anything left for him to check by hand (e.g. dashboard E2E if credentials weren't available).
