import json
import time
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
    [
        ("<p>x</p>", True),
        ("<BR/>", True),
        ('<a href="x">', True),
        ("a < b", False),
        ("5 * 3", False),
        ("<abbr>x</abbr>", False),
        ("Tom &amp; Jerry", False),
        # Fix round 1 finding: is_html must keep the exact original truth
        # value (a naive, quote-unaware "does some > follow a recognised
        # open-tag prefix" check) computed in linear time — NOT run
        # _guard_unterminated first, which would hide a real tag sitting
        # after a quote-swallowed tag-open like this one.
        ('x<y "a <b>bold</b>', True),
    ],
)
def test_is_html(value, expected):
    assert is_html(value) is expected


def test_is_html_unterminated_comment_with_pathological_tail_is_not_quadratic():
    start = time.perf_counter()
    is_html("<!--" + "<b" * 50_000)
    elapsed = time.perf_counter() - start
    assert elapsed < 5.0


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
    assert (
        plain_text("<p>Tom &amp; <strong>Jerry</strong></p><p>2nd</p>", "rich") == "Tom & Jerry 2nd"
    )
    assert plain_text("a<br>b", "inline") == "a b"
    assert plain_text("<p>a</p><ul><li><p>b</p></li></ul>", "rich", keep_line_breaks=True) == "a\nb"
    assert plain_text("", "rich") == ""
    assert plain_text("raw <b>", "plain") == "raw <b>"


def test_deeply_nested_marks_do_not_recurse_without_bound():
    big = "<strong>" * 5000 + "x" + "</strong>" * 5000
    canonicalize(big, "rich", enforce_limit=False)


def test_deeply_nested_blockquotes_do_not_recurse_without_bound():
    big = "<blockquote>" * 5000 + "x" + "</blockquote>" * 5000
    canonicalize(big, "rich", enforce_limit=False)


def test_many_adjacent_unwrapped_links_are_not_quadratic():
    # No href -> safe_href denies it -> the <a> unwraps to plain text, merging
    # thousands of adjacent text fragments in _tidy. This must stay linear.
    big = "<a>x</a>" * 40_000  # ~320 KB
    start = time.perf_counter()
    canonicalize(big, "rich", enforce_limit=False)
    elapsed = time.perf_counter() - start
    assert elapsed < 5.0


@pytest.mark.parametrize(
    "raw",
    [
        pytest.param("<b" * 50_000, id="b-repeat-50000"),
        pytest.param("<a a" * 25_000, id="a-a-repeat-25000"),
        pytest.param("<b" * 50_000 + '">', id="b-repeat-50000-plus-quote-gt"),
        pytest.param("</b" * 50_000, id="close-b-repeat-50000"),
    ],
)
def test_unterminated_tag_open_is_not_quadratic(raw):
    # Stdlib html.parser rescans from every unterminated `<` (check_for_whole_
    # start_tag/parse_endtag re-derive the tag boundary from scratch each
    # time), making these inputs O(n^2) — ~10-90s locally, well within the raw
    # 200 KB input cap and reachable by any authenticated editor via the save
    # endpoint. The linear _guard_unterminated pre-pass must keep both
    # canonicalize and plain_text well under the budget. 5s (not 1-2s) because
    # the quadratic regressions this guards against took 10-90s, so 5s still
    # catches them without flaking under load.
    start = time.perf_counter()
    canonicalize(raw, "rich", enforce_limit=False)
    elapsed = time.perf_counter() - start
    assert elapsed < 5.0

    start = time.perf_counter()
    plain_text(raw, "rich")
    elapsed = time.perf_counter() - start
    assert elapsed < 5.0


@pytest.mark.parametrize(
    "raw",
    [
        pytest.param("<!--" + "<b" * 50_000, id="unterminated-comment-then-b-repeat"),
        pytest.param("<!x" + "<b" * 50_000, id="unterminated-bang-decl-then-b-repeat"),
        pytest.param("<?x" + "<b" * 50_000, id="unterminated-pi-then-b-repeat"),
        pytest.param("<script>" + "<b" * 50_000, id="unterminated-script-then-b-repeat"),
        pytest.param("<style>" + "<b" * 50_000, id="unterminated-style-then-b-repeat"),
        pytest.param("<p>x</p><!--" + "<b" * 50_000, id="real-tag-then-unterminated-comment"),
        pytest.param("<!-->" + "<b" * 50_000, id="stray-gt-does-not-close-comment"),
    ],
)
def test_unterminated_comment_decl_and_raw_text_are_not_quadratic(raw):
    # Fix round 1 finding: _guard_unterminated originally left an unterminated
    # comment / <! / <? / script-style raw-text construct's *dangling tail*
    # in `value` unchanged (only `i` was advanced to `n`, ending the scan
    # loop without truncating what it returns) — so a pathological run tucked
    # inside one of these constructs (e.g. "<!--" + "<b" * 50000) still
    # reached html.parser's own rescanning fallback and _HTML_OPEN_RE
    # untouched, reopening the same O(n^2) DoS this guard exists to close.
    # The kit never emits anything for these once they can't find their
    # terminator, so the guard now truncates the same way (see its
    # docstring), and canonicalize/plain_text/is_html must all stay linear.
    start = time.perf_counter()
    is_html(raw)
    elapsed = time.perf_counter() - start
    assert elapsed < 5.0

    start = time.perf_counter()
    canonicalize(raw, "rich", enforce_limit=False)
    elapsed = time.perf_counter() - start
    assert elapsed < 5.0

    start = time.perf_counter()
    plain_text(raw, "rich")
    elapsed = time.perf_counter() - start
    assert elapsed < 5.0


def test_raw_input_cap_rejects_before_parsing():
    with pytest.raises(RichTextTooLong) as exc:
        canonicalize("a" * (4 * MAX_LENGTH["inline"] + 1), "inline")
    assert exc.value.limit == MAX_LENGTH["inline"]
    assert exc.value.length == 4 * MAX_LENGTH["inline"] + 1


def test_many_repeated_hr_in_heading_is_not_quadratic():
    # Every <hr> re-evaluates the block-inside-inline branch of _inline; before
    # the fix this rescanned the whole accumulator (_has_content/_ends_with_br)
    # on every iteration.
    big = "<h2>" + "<hr> " * 39_990  # ~200 KB, under the raw-input cap
    start = time.perf_counter()
    canonicalize(big, "rich", enforce_limit=True)
    elapsed = time.perf_counter() - start
    assert elapsed < 5.0


def _deep(tag: str, n: int, inner: str = "x") -> str:
    return f"<{tag}>" * n + inner + f"</{tag}>" * n


def _nested_lists(depth: int, marks: str) -> str:
    html = marks
    for _ in range(depth):
        html = f"<ul><li>{html}</li></ul>"
    return html


_CONTAINERS = {
    "p": "<p>{marks}</p>",
    "blockquote": "<blockquote>{marks}</blockquote>",
    "ul_li": "<ul><li>{marks}</li></ul>",
    "bare_li": "<li>{marks}</li>",
    "ol_li_blockquote": "<ol><li><blockquote>{marks}</blockquote></li></ol>",
    "h2": "<h2>{marks}</h2>",
    "loose_root": "{marks}",
}


@pytest.mark.parametrize("mark_tag", ["strong", "em"])
@pytest.mark.parametrize("container", list(_CONTAINERS))
@pytest.mark.parametrize("fmt", ["rich", "inline"])
def test_deep_marks_idempotent_in_every_container_shape(fmt, container, mark_tag):
    html = _CONTAINERS[container].format(marks=_deep(mark_tag, 40))
    once = canonicalize(html, fmt)
    twice = canonicalize(once, fmt)
    assert once == twice


@pytest.mark.parametrize("mark_tag", ["strong", "em"])
@pytest.mark.parametrize("list_depth", [1, 2, 3, 4])
@pytest.mark.parametrize("fmt", ["rich", "inline"])
def test_deep_marks_idempotent_in_nested_lists_without_p(fmt, list_depth, mark_tag):
    html = _nested_lists(list_depth, _deep(mark_tag, 40))
    once = canonicalize(html, fmt)
    twice = canonicalize(once, fmt)
    assert once == twice
