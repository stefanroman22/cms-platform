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
        # open-tag prefix" check) computed in linear time — not something
        # parse-aware that would hide a real tag sitting after a
        # quote-swallowed tag-open like this one.
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
    # Originally (fix round 1): stdlib html.parser rescans from every
    # unterminated `<` (check_for_whole_start_tag/parse_endtag re-derive the
    # tag boundary from scratch each time), making these inputs O(n^2) —
    # ~10-90s locally, well within the raw 200 KB input cap and reachable by
    # any authenticated editor via the save endpoint. Fix round 3 replaced
    # html.parser entirely with a direct linear port of the kit's tokenizer
    # (rich_text._parse), which visits every position once by construction —
    # kept as a regression guard. 5s (not 1-2s) because the quadratic
    # regressions this originally guarded against took 10-90s, so 5s still
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
    # Fix round 1 finding, kept as a regression guard after fix round 3
    # replaced html.parser with rich_text._parse (a direct port of the
    # kit's tokenizer): a pathological run tucked inside an unterminated
    # comment / <! / <? / script-style raw-text construct (e.g. "<!--" +
    # "<b" * 50000) must not blow up canonicalize/plain_text/is_html. The
    # kit never emits anything for a construct that can't find its
    # terminator, and _parse's single scan loop visits every position once
    # by construction, so this stays linear structurally, not by a
    # special-cased guard.
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


def test_marked_section_does_not_crash():
    # Fix round 2 finding A, kept as a regression guard: a *terminated*
    # `<![` + unknown keyword (an HTML5 "marked section", e.g.
    # `<![CDATA[...]]>` or a bogus one like `<![x>`) used to be left for
    # stdlib html.parser to parse itself, and `_markupbase.parse_marked_
    # section` raises AssertionError on an unrecognised keyword — an
    # unhandled 500 on save, reachable by any authenticated editor. Fix
    # round 3 replaced html.parser entirely with rich_text._parse (a direct
    # port of the kit's tokenizer, which has no concept of "marked
    # sections" at all — a `<!` construct just ends at the first bare `>`,
    # same as the kit), so there is no `_markupbase` call left to crash.
    assert canonicalize("<p>x</p><![x>", "rich") == "<p>x</p>"
    # `<![if !IE]>x<![endif]>` contains no tag name is_html recognises (its
    # curated list is p/br/strong/.../span — "if"/"endif" aren't in it, and
    # weren't before any of these fixes either), so canonicalize() routes it
    # through the pre-existing, unrelated legacy-content converter rather
    # than _parse; it therefore does not byte-match the kit's bare parse()
    # output here (a pre-existing gap, not something any of these fixes
    # changes or is meant to close — see the fix-round-2/3 reports). The one
    # property being tested here is what these fixes do guarantee: no
    # crash.
    canonicalize("<![if !IE]>x<![endif]>", "rich")


@pytest.mark.parametrize(
    "raw",
    [
        pytest.param("<p>x</p>" + "<![CDATA[x>" * 20_000, id="cdata-repeat"),
        pytest.param(
            "<p>x</p>" + "<![CDATA[x>" * 20_000 + "<script>", id="cdata-repeat-then-script"
        ),
        pytest.param("<p>x</p>" + "<![CDATA[x>" * 20_000 + "<!--", id="cdata-repeat-then-comment"),
    ],
)
def test_marked_section_repeat_is_not_quadratic(raw):
    # Fix round 2 finding B, kept as a regression guard: html.parser's own
    # `_markupbase` marked-section scanning was near-quadratic on many
    # `<![...]>`-shaped constructs in a row (~2.8-5.1s for ~220 KB, growing
    # faster than linearly, near/over budget on a serverless function) even
    # when none of them individually crashed. Fix round 3 removed
    # html.parser (and `_markupbase`) from this file entirely, so there is
    # nothing left to go near-quadratic here.
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


@pytest.mark.parametrize(
    "raw",
    [
        pytest.param("<p>x</p>" + "<<?>b" * 40_000, id="pi-join-repeat-40000"),
        pytest.param("<<!>b" * 40_000, id="bang-join-repeat-40000"),
        pytest.param("<<!---->b" * 20_000, id="comment-join-repeat-20000"),
    ],
)
def test_splicing_adjacent_constructs_is_not_quadratic(raw):
    # Fix round 3 finding B: fix round 2's approach — leave a *terminated*
    # comment/decl/PI's surrounding text in place and splice only the
    # construct itself out of the returned string — joins the text before
    # and after the splice. For a single splice that's harmless, but for
    # thousands of them in a row (e.g. "<<?>b" * 40000, where each "<?>"
    # splice joins the "<" before it to the "b" after it) it reopens the
    # same shape of O(n^2) DoS fix round 1 closed: `_HTML_OPEN_RE`/is_html
    # and canonicalize/plain_text end up re-scanning ever-growing joined
    # text. Fix round 3's rewrite (rich_text._parse, a direct port of the
    # kit's tokenizer) never splices at all — it decides what each
    # character contributes to the output during one linear pass, the same
    # way the kit does, so no join can ever happen.
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


def test_splicing_adjacent_constructs_near_raw_input_cap_is_not_quadratic():
    # Fix round 3 finding B: the same payload shape as
    # test_splicing_adjacent_constructs_is_not_quadratic, sized to land just
    # under the raw-input cap (4 * MAX_LENGTH["rich"] = 200_000 chars) so
    # RichTextTooLong is raised only *after* canonicalize has already fully
    # parsed and serialized the value (enforce_limit checks the *output*
    # length against MAX_LENGTH, after parsing) — the slow path, if it were
    # still quadratic, would still have to run to completion first.
    raw = "<p>x</p>" + "<<?>b" * 39_990
    start = time.perf_counter()
    with pytest.raises(RichTextTooLong):
        canonicalize(raw, "rich", enforce_limit=True)
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
