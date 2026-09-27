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
    [
        ("<p>x</p>", True),
        ("<BR/>", True),
        ('<a href="x">', True),
        ("a < b", False),
        ("5 * 3", False),
        ("<abbr>x</abbr>", False),
        ("Tom &amp; Jerry", False),
    ],
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
    assert (
        plain_text("<p>Tom &amp; <strong>Jerry</strong></p><p>2nd</p>", "rich") == "Tom & Jerry 2nd"
    )
    assert plain_text("a<br>b", "inline") == "a b"
    assert plain_text("<p>a</p><ul><li><p>b</p></li></ul>", "rich", keep_line_breaks=True) == "a\nb"
    assert plain_text("", "rich") == ""
    assert plain_text("raw <b>", "plain") == "raw <b>"
