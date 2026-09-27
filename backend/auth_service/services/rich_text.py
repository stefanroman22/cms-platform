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
