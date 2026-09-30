"""Rich-text content model (ADR-0010): field formats and canonical HTML.

`inline` / `rich` CMS leaves are stored as canonical HTML produced by
`canonicalize`. The backend is the only writer (ADR-0002), so every value a
client site renders has passed through here. The TypeScript client kit
(client-kit/rich-text) ports this exact transform; both are pinned by
client-kit/rich-text/fixtures/canonical-vectors.json. Pure — no I/O."""

from __future__ import annotations

import re
from html import unescape
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
MAX_PARSE_DEPTH = 256
MAX_MARK_DEPTH = 32

_SYNONYMS = {
    "b": "strong",
    "i": "em",
    "strike": "s",
    "del": "s",
    "ins": "u",
    "h1": "h2",
    "h5": "h4",
    "h6": "h4",
    "div": "p",
}
_DROP_WITH_CONTENT = frozenset(
    {
        "script",
        "style",
        "iframe",
        "object",
        "svg",
        "math",
        "template",
        "noscript",
        "head",
        "title",
        "textarea",
        "select",
        "button",
        "canvas",
        "audio",
        "video",
        "picture",
    }
)
_HTML_OPEN_RE = re.compile(
    r"<(?:p|br|strong|em|u|s|a|ul|ol|li|h[1-6]|blockquote|hr|b|i|div|span)\b", re.I
)
_WS_RE = re.compile(r"[ \t\r\n\f]+")
_CTRL_RE = re.compile(r"[\x00-\x1f\x7f]")
_ASCII_LETTERS = frozenset("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ")
_RAW_TEXT = frozenset({"script", "style"})
# Mirrors client-kit/rich-text/src/parse.ts's TAG_RE exactly (sticky `y` flag
# there ~= matching with Python's pos/endpos here): group 1 is the `/` of a
# close tag, group 2 the tag name, group 3 the raw attrs text, group 4 a
# trailing `/` for a self-closing tag.
_TAG_RE = re.compile(r"<(/?)([a-zA-Z][a-zA-Z0-9:-]*)((?:[^>\"']|\"[^\"]*\"|'[^']*')*?)(/?)>")
# Mirrors parse.ts's HREF_RE exactly.
_HREF_RE = re.compile(r"(?:^|\s)href\s*=\s*(?:\"([^\"]*)\"|'([^']*)'|([^\s\"'=<>`]+))", re.I)


class RichTextTooLong(ValueError):
    """The canonical value exceeds MAX_LENGTH for its format."""

    def __init__(self, length: int, limit: int) -> None:
        super().__init__(f"{length} > {limit}")
        self.length = length
        self.limit = limit


def is_html(value: str) -> bool:
    """True when `value` contains at least one recognised HTML tag.

    Originally `<(?:p|br|...)\\b[^>]*>` (re.I) searched over the raw value.
    That `[^>]*>` tail always succeeds from a match of the opening `<tag\\b`
    part iff *some* `>` occurs anywhere later in the string — the run of
    non-`>` characters just stretches to reach it, whatever it is — so the
    original True/False answer is exactly "does some recognised open-tag
    prefix start before the *last* `>` in the whole string". Checking it
    that way is O(n) and gives the identical answer for every input,
    including the ones the old regex got right only by backtracking
    catastrophically: `_HTML_OPEN_RE` has no unbounded/nested quantifiers (a
    small fixed alternation plus a word boundary), so a plain `.search()`
    over it can't blow up the way `[^>]*` does on an unterminated tag-open
    run like `"<b" * 50000`."""
    gt = value.rfind(">")
    if gt == -1:
        return False
    return _HTML_OPEN_RE.search(value, 0, gt) is not None


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


def _parse(value: str) -> _Node:  # one function by design, see below
    """Tag-soup tolerant tokenizer + tree builder: a direct, line-for-line
    port of client-kit/rich-text/src/parse.ts's `parse()`, not a wrapper
    around stdlib `html.parser`. Three rounds of trying to make html.parser
    behave (a linear guard pre-pass to neutralise unterminated tags, then to
    also neutralise comments/declarations/marked sections it can crash or go
    near-quadratic on) kept surfacing new html.parser-only pathologies —
    patching around a general-purpose HTML5 parser's own edge cases wasn't
    converging. The kit already has an exact, linear, tag-soup-tolerant
    tokenizer purpose-built for this exact allow-listed tag set; this is
    that same algorithm, so there is exactly one specification for what
    "the canonical parse of this input" means, not two that have to be kept
    in sync by construction of very different control flow. Everything
    below one function for the same reason parse.ts is one function: `text`/
    `open_tag`/`close_tag` and the tokenizer loop all close over the same
    `stack`/`skip` parse state, which is the state a single html.parser
    instance held as attributes before.

    Kept identical to parse.ts: the RICH_TAGS allow-list, `_SYNONYMS`,
    `_DROP_WITH_CONTENT` skip-counting, `_RAW_TEXT` (script/style) raw-text
    skipping, `MAX_PARSE_DEPTH` (br/hr always appended before any depth
    check; any other tag beyond the cap is unwrapped like an unknown
    element), and end-tag pop-to-nearest-matching-ancestor. Comments,
    `<!...>`/`<?...>` constructs (including anything HTML5 would call a
    "marked section", e.g. `<![CDATA[...]]>`) and unterminated tag-opens are
    handled by the same scan loop as ordinary tags — there is no separate
    guard pre-pass or removal step, because nothing here is ever handed to
    a general-purpose parser that could misinterpret it: text runs, once
    identified as text, are appended straight to the tree.

    Deliberate difference from parse.ts, per an explicit controller ruling:
    entities (in text runs and in `href` values) are decoded with Python's
    `html.unescape` (the full HTML5 named-entity table) rather than a port
    of the kit's small `decodeEntities` (amp/lt/gt/quot/apos/nbsp only) —
    better fidelity for DeepL-translated output. Canonical output only ever
    re-escapes `&amp; &lt; &gt; &nbsp; &quot;` (see `escape_text`/
    `escape_attr`), so this cannot change what a *stored* canonical value
    looks like for anything already expressible in those five escapes;
    it only affects entities outside that set on *raw, not-yet-canonical*
    input (e.g. `&copy;` decodes to `©` here but is left as literal text by
    the kit) — an accepted, already-logged minor, not new to this port."""
    root = _Node("#root")
    stack: list[_Node] = [root]
    lower = value.lower()
    n = len(value)
    skip = 0
    i = 0

    def text(t: str) -> None:
        nonlocal skip
        if skip or not t:
            return
        kids = stack[-1].children
        if kids and isinstance(kids[-1], str):
            kids[-1] = kids[-1] + t
        else:
            kids.append(t)

    def open_tag(raw: str, attrs: str) -> None:
        nonlocal skip
        if raw in _DROP_WITH_CONTENT:
            skip += 1
            return
        if skip:
            return
        tag = _SYNONYMS.get(raw, raw)
        if tag in ("br", "hr"):
            stack[-1].children.append(_Node(tag))
            return
        if tag not in RICH_TAGS:
            return
        # Flat parse-tree depth safety net (no exemptions): only exists to keep
        # the recursive semantic transform below (_inline/_blocks) within
        # Python's recursion limit for any input, regardless of tag mix. The
        # much smaller, semantically meaningful cap on canonical output is
        # MAX_MARK_DEPTH, applied separately inside _inline.
        if len(stack) - 1 >= MAX_PARSE_DEPTH:
            return  # depth cap reached: unwrap like an unknown element
        href = None
        if tag == "a":
            m = _HREF_RE.search(attrs)
            if m:
                raw_href = m.group(1)
                if raw_href is None:
                    raw_href = m.group(2)
                if raw_href is None:
                    raw_href = m.group(3)
                href = unescape(raw_href if raw_href is not None else "")
        node = _Node(tag, href)
        stack[-1].children.append(node)
        stack.append(node)

    def close_tag(raw: str) -> None:
        nonlocal skip
        if raw in _DROP_WITH_CONTENT:
            if skip:
                skip -= 1
            return
        if skip:
            return
        tag = _SYNONYMS.get(raw, raw)
        if tag not in RICH_TAGS or tag in ("br", "hr"):
            return
        for k in range(len(stack) - 1, 0, -1):
            if stack[k].tag == tag:
                del stack[k:]
                return

    while i < n:
        lt = value.find("<", i)
        if lt == -1:
            text(unescape(value[i:]))
            break
        if lt > i:
            text(unescape(value[i:lt]))
        if value.startswith("<!--", lt):
            end = value.find("-->", lt + 4)
            i = n if end == -1 else end + 3
            continue
        c1 = value[lt + 1] if lt + 1 < n else ""
        if c1 == "!" or c1 == "?":
            end = value.find(">", lt)
            i = n if end == -1 else end + 1
            continue

        # A `<` only begins a tag when followed by an ASCII letter (open tag)
        # or `/` + ASCII letter (close tag); anything else is literal text.
        c2 = value[lt + 2] if lt + 2 < n else ""
        is_tag_start = c1 in _ASCII_LETTERS or (c1 == "/" and c2 in _ASCII_LETTERS)
        if not is_tag_start:
            text("<")
            i = lt + 1
            continue

        # Scan forward once, char by char, tracking quote state, to find the
        # first `>` outside quotes — that's the tag's end. No backtracking,
        # so this is O(remaining input) for this one `<`, not repeated per
        # `<`.
        j = lt + 1
        quote = ""
        tag_end = -1
        while j < n:
            ch = value[j]
            if quote:
                if ch == quote:
                    quote = ""
            elif ch == '"' or ch == "'":
                quote = ch
            elif ch == ">":
                tag_end = j
                break
            j += 1
        if tag_end == -1:
            # No terminating `>` anywhere in the rest of the input (or an
            # unclosed quote swallowed it): this `<` and everything after it
            # is literal text. Emit it and stop — never rescans the same
            # span again.
            text(unescape(value[lt:]))
            break

        m = _TAG_RE.match(value, lt, tag_end + 1)
        if not m:
            text(unescape(value[lt : tag_end + 1]))
            i = tag_end + 1
            continue
        i = tag_end + 1
        tag = m.group(2).lower()
        self_closing = m.group(4) == "/"
        if m.group(1) == "/":
            close_tag(tag)
            continue
        if tag in _RAW_TEXT and not self_closing:
            end_tag = lower.find(f"</{tag}", i)
            if end_tag == -1:
                i = n
            else:
                gt = value.find(">", end_tag)
                i = n if gt == -1 else gt + 1
            continue
        if self_closing:
            if tag not in _DROP_WITH_CONTENT:
                open_tag(tag, m.group(3))
                close_tag(tag)
            continue
        open_tag(tag, m.group(3))
    return root


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


def _inline(nodes: list, in_link: bool = False, mark_depth: int = 0) -> list:
    """`mark_depth` counts the strong/em/u/s/a elements enclosing the current
    position (independent of any block wrapper): beyond MAX_MARK_DEPTH, a
    mark/link is unwrapped rather than nested further (its children are
    processed at the same depth). This is deliberately decoupled from block
    structure (p/li/ul/blockquote) so that re-parsing a canonical value never
    sees a different mark budget than the first parse did — the property
    canonicalize's idempotence test relies on."""
    out: list = []
    # Running state mirroring _has_content(out)/_ends_with_br(out), updated as
    # items are pushed, so the block-inside-inline branch below never rescans
    # the whole (potentially large) accumulator.
    has_content = False
    ends_with_br = False

    def push(item: _Node | str) -> None:
        nonlocal has_content, ends_with_br
        out.append(item)
        if isinstance(item, str):
            if item.strip():
                has_content = True
                ends_with_br = False
            # whitespace-only strings leave has_content/ends_with_br unchanged,
            # matching _has_content/_ends_with_br's skip-trailing-whitespace rule
        else:
            if item.tag != "br":
                has_content = True
            ends_with_br = item.tag == "br"

    for n in nodes:
        if isinstance(n, str):
            push(_WS_RE.sub(" ", n))
            continue
        tag = n.tag
        if tag == "br":
            push(_br())
        elif tag in MARK_TAGS:
            if mark_depth >= MAX_MARK_DEPTH:
                for item in _inline(n.children, in_link, mark_depth):
                    push(item)
                continue
            kids = _inline(n.children, in_link, mark_depth + 1)
            if _has_content(kids):
                push(_Node(tag, children=kids))
        elif tag == "a":
            if mark_depth >= MAX_MARK_DEPTH:
                for item in _inline(n.children, True, mark_depth):
                    push(item)
                continue
            kids = _inline(n.children, True, mark_depth + 1)
            href = None if in_link else safe_href(n.href)
            if href and _has_content(kids):
                push(_Node("a", href, kids))
            else:
                for item in kids:
                    push(item)
        else:  # a block element inside an inline context: flatten, separated by <br>
            kids = [] if tag == "hr" else _inline(n.children, in_link, mark_depth)
            if tag == "hr" or _has_content(kids):
                if has_content and not ends_with_br:
                    push(_br())
                for item in kids:
                    push(item)
                if not ends_with_br:
                    push(_br())
    return out


def _tidy(nodes: list) -> list:
    res: list = []
    buf: list[str] = []

    def flush() -> None:
        if not buf:
            return
        s = _WS_RE.sub(" ", "".join(buf))
        buf.clear()
        last = res[-1] if res else None
        if isinstance(last, _Node) and last.tag == "br":
            s = s.lstrip(" ")
        if s:
            res.append(s)

    for n in nodes:
        if isinstance(n, str):
            buf.append(n)
            continue
        flush()
        if n.tag == "br" and res and isinstance(res[-1], str):
            t = res[-1].rstrip(" ")
            if t:
                res[-1] = t
            else:
                res.pop()
        res.append(n)
    flush()
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
    if enforce_limit and len(value) > 4 * MAX_LENGTH[fmt]:
        raise RichTextTooLong(len(value), MAX_LENGTH[fmt])
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
            elif n.tag == "p" or n.tag in HEADING_TAGS:
                walk(n.children)
                parts.append("\n")
            else:  # ul, ol, li, blockquote — containers with no boundary of their own
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


# ── Field formats (spec §4.2) ────────────────────────────────────────────────

_REPEATER_TYPE_FORMAT: dict[str | None, str] = {
    "string": "plain",
    "inline": "inline",
    "richtext": "rich",
    "url": "plain",
    "tags": "plain",
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
        return _kv_formats(content).get(path[len("entries.") :], "plain")  # type: ignore[return-value]
    if service_type == "repeater" and path.startswith("items."):
        from .segments import repeater_schema

        # Item ids are client-supplied and may contain dots, so take the field
        # key from the right. Tags leaves (items.<id>.<key>.<j>) end in an index,
        # which is never a schema key, so they resolve to plain.
        key = path.rsplit(".", 1)[-1]
        return _REPEATER_TYPE_FORMAT.get(repeater_schema(content).get(key), "plain")  # type: ignore[return-value]
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
