"""Legacy (pre-rich-text) text → canonical HTML (spec §4.4).

Rich: the Markdown-lite subset CMS content used before ADR-0010. Inline: plain
text (escape + line breaks, no Markdown). Output is already canonical. Mirrored
exactly by client-kit/rich-text/src/legacy.ts; both are pinned by
client-kit/rich-text/fixtures/legacy-vectors.json — change them together."""

from __future__ import annotations

import re

from .rich_text import escape_attr, escape_text, safe_href

_WS_RE = re.compile(r"[ \t\r\n\f]+")
_W = "0-9A-Za-zÀ-ɏ"  # explicit word class so Python and JS agree
_LINK_RE = re.compile(r"\[([^\]\n]+)\]\(([^)\s]+)\)")
_BOLD_RE = re.compile(r"\*\*(?=\S)(.+?)(?<=\S)\*\*|__(?=\S)(.+?)(?<=\S)__")
_STRIKE_RE = re.compile(r"~~(?=\S)(.+?)(?<=\S)~~")
_EM_RE = re.compile(
    rf"(?<![{_W}*])\*(?=\S)(.+?)(?<=\S)\*(?![{_W}*])|(?<![{_W}_])_(?=\S)(.+?)(?<=\S)_(?![{_W}_])"
)
_PH_RE = re.compile("(\\d+)")
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
        return f"{len(links) - 1}"

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
    t = text.replace("\r\n", "\n").replace("\r", "\n").replace(" ", " ")
    # Strip the private-use sentinels _inline_md() uses internally to protect
    # already-built <a> tags from the bold/italic/strike passes. Without this,
    # raw input containing these unassigned PUA code points could collide with
    # a real placeholder (IndexError on a bare sentinel, or a real link's HTML
    # silently duplicated onto unrelated text) once _PH_RE.sub runs over the
    # whole string.
    t = t.replace("", "").replace("", "")
    if not t.strip():
        return ""
    return _rich(t) if fmt == "rich" else _inline(t)
