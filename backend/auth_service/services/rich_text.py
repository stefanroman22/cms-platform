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
_TAG_NAME_RE = re.compile(r"[a-zA-Z][a-zA-Z0-9:-]*")


class RichTextTooLong(ValueError):
    """The canonical value exceeds MAX_LENGTH for its format."""

    def __init__(self, length: int, limit: int) -> None:
        super().__init__(f"{length} > {limit}")
        self.length = length
        self.limit = limit


def _escape_tail_for_reparse(tail: str) -> str:
    """Re-encode an unterminated tag-open (and everything after it) so
    HTMLParser treats it as one literal text run instead of repeatedly
    rescanning an incomplete tag construct.

    Only `<` and `>` are escaped; any `&...;` already in the tail (e.g.
    `&amp;`) is left untouched so HTMLParser's own entity decoding — which
    already runs on every ordinary text node via convert_charrefs and is
    the thing client-kit/rich-text/src/parse.ts's decodeEntities is kept in
    parity with — decodes it exactly as it would for any other text node.
    Escaping `<`/`>` guarantees no raw `<` remains in the tail, so
    HTMLParser's fast path (`rawdata.find('<', i)`) hands the whole
    remainder to a single `handle_data` call instead of re-deriving the tag
    boundary from `i` on every subsequent `<`."""
    return tail.replace("<", "&lt;").replace(">", "&gt;")


def _guard_unterminated(value: str) -> str:
    """Linear pre-pass mirroring client-kit/rich-text/src/parse.ts's tag
    tokenizer loop char-for-char, so HTMLParser and `is_html` only ever see
    what the kit itself would treat as real markup or text.

    Two things happen here, both because the kit's tokenizer never hands a
    comment / `<!` / `<?` construct to anything else, and never hands an
    unterminated tag-open to anything else either — it decides their fate
    itself, inline, in this one pass:

    1. Every comment (`<!--...-->`), and every other `<!...>` / `<?...>`
       construct (declarations, processing instructions, and anything HTML5
       would call a "marked section" like `<![CDATA[...]]>` or a bogus
       comment like `<![x>`) — TERMINATED or not — is removed from the
       output entirely. The kit finds the end of a comment by searching for
       a literal `-->`, and the end of any other `<!`/`<?` construct by
       searching for the *first* bare `>` (no quote-tracking, no nested
       `]]>` awareness — a `<![CDATA[<script>...` construct ends at the `>`
       of that `<script>`, same as the kit), and in both cases emits no text
       for what it found either way. Left in the string for stdlib
       html.parser instead, these constructs are not simply inert: `<![` +
       an unrecognised keyword raises `AssertionError` inside
       `_markupbase.parse_marked_section` (an unhandled 500 on save), and
       many repeats of a `<![...]>`-shaped run is itself near-quadratic in
       `_markupbase`'s own marked-section scanning. Splicing them out here
       means HTMLParser never parses a marked section at all, closing both
       the crash and the slowdown, and makes the backend match the kit's
       (much simpler) "first bare `>` ends it" rule instead of trying to
       out-implement `_markupbase`.
    2. A `<` that opens a tag (an ASCII letter, or `/` + ASCII letter,
       follows it) with no closing `>` outside quotes anywhere in the rest
       of the input has that `<` and everything after it re-encoded as
       literal text. A script/style open tag with no closing tag keeps just
       the open tag and drops everything after it. Both are truncations,
       not removals — the kit does emit content for these (see
       `_escape_tail_for_reparse`), it just never finds a `>` to end them
       properly.

    stdlib html.parser rescans from every unterminated `<` (check_for_whole_
    start_tag re-derives the tag boundary from `i` on each call, and its
    fallback on failure advances `i` by only one `<` at a time), and
    `is_html`'s tag-prefix regex has the same shape of problem if fed a
    string that still contains a dangling construct — both making inputs
    like `"<b" * 50000` (~10-90s), `"<a a" * 25000`, or any of the above
    prefixed onto such a run, quadratic: a serverless-function DoS reachable
    by any authenticated editor via the save endpoint, within the 200 KB
    raw-input cap. This walk visits every position at most once (O(n)) and
    never rescans. When every tag-open in `value` is already terminated and
    `value` contains no comment/`<!`/`<?` construct at all, `value` is
    returned unchanged (verbatim, not just equal — no piece is copied)."""
    n = len(value)
    lower = value.lower()
    i = 0
    # `pieces` accumulates the parts of `value` that survive (kept spans
    # between removed comments/decls/PIs); `copy_from` is the start of the
    # next not-yet-flushed span. Left empty/0 for the overwhelmingly common
    # case of no comment/decl/PI in `value`, so that case returns `value`
    # itself with no copying at all.
    pieces: list[str] = []
    copy_from = 0

    def truncate_at(pos: int) -> str:
        if not pieces:
            return value[:pos]
        pieces.append(value[copy_from:pos])
        return "".join(pieces)

    while i < n:
        lt = value.find("<", i)
        if lt == -1:
            return value if not pieces else "".join(pieces) + value[copy_from:]
        if value.startswith("<!--", lt):
            end = value.find("-->", lt + 4)
            if end == -1:
                # No closing "-->" anywhere: the kit drops the comment and
                # everything after it (it never emits text for it), so
                # truncate here instead of leaving the rest of the input
                # (which may itself be a pathological run) for HTMLParser or
                # is_html to rescan.
                return truncate_at(lt)
            # Terminated: splice the whole comment out (see point 1 above)
            # and keep scanning from right after it.
            pieces.append(value[copy_from:lt])
            copy_from = end + 3
            i = copy_from
            continue
        c1 = value[lt + 1] if lt + 1 < n else ""
        if c1 == "!" or c1 == "?":
            end = value.find(">", lt)
            if end == -1:
                # Same reasoning as the unterminated-comment case above.
                return truncate_at(lt)
            # Terminated: splice the whole `<!...>`/`<?...>` construct out
            # (see point 1 above), ending at the first bare `>` exactly like
            # the kit — not at any `]]>` or other marked-section-specific
            # terminator — and keep scanning from right after it.
            pieces.append(value[copy_from:lt])
            copy_from = end + 1
            i = copy_from
            continue
        c2 = value[lt + 2] if lt + 2 < n else ""
        is_tag_start = c1 in _ASCII_LETTERS or (c1 == "/" and c2 in _ASCII_LETTERS)
        if not is_tag_start:
            i = lt + 1
            continue

        # Scan forward once, char by char, tracking quote state, to find the
        # first `>` outside quotes — that's the tag's end. No backtracking,
        # so this is O(remaining input) for this one `<`, not repeated per
        # `<` the way html.parser's own fallback (and _HTML_OPEN_RE) are.
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
            # is literal text. Rewrite it and stop — never rescans the same
            # span again.
            tail = _escape_tail_for_reparse(value[lt:])
            if not pieces:
                return value[:lt] + tail
            pieces.append(value[copy_from:lt])
            pieces.append(tail)
            return "".join(pieces)

        is_close = c1 == "/"
        name_match = _TAG_NAME_RE.match(value, lt + 2 if is_close else lt + 1)
        tag = name_match.group().lower() if name_match else ""
        self_closing = value[tag_end - 1] == "/"
        i = tag_end + 1
        if not is_close and tag in _RAW_TEXT and not self_closing:
            end_tag = lower.find(f"</{tag}", i)
            gt = value.find(">", end_tag) if end_tag != -1 else -1
            if end_tag == -1 or gt == -1:
                # No closing tag (or its own `>` never arrives): the kit
                # never emits text for raw-text content regardless, so keep
                # the open tag itself (it contributes nothing either way)
                # and drop everything after it — same reasoning as the
                # comment/decl case: don't leave a possibly-pathological
                # tail for anything downstream to rescan.
                return truncate_at(i)
            i = gt + 1
    return value if not pieces else "".join(pieces) + value[copy_from:]


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
        # Flat parse-tree depth safety net (no exemptions): only exists to keep the
        # recursive semantic transform below (_inline/_blocks) within Python's
        # recursion limit for any input, regardless of tag mix. The much smaller,
        # semantically meaningful cap on canonical output is MAX_MARK_DEPTH, applied
        # separately inside _inline.
        if len(self._stack) - 1 >= MAX_PARSE_DEPTH:
            return  # depth cap reached: unwrap like an unknown element
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
    b.feed(_guard_unterminated(value))
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
