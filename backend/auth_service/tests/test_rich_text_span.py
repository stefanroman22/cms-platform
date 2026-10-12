import pytest

from auth_service.services.rich_text import canonical_style, canonicalize


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("color: #1E5AA8", "color:#1e5aa8"),
        ("color:#abc", "color:#aabbcc"),
        ("color: rgb(30, 90, 168)", "color:#1e5aa8"),
        ('font-family: "Open Sans", Arial, sans-serif', "font-family:'Open Sans'"),
        ("font-size: 1.250em", "font-size:1.25em"),
        ("font-size: 2.0em; color: #000000", "color:#000000;font-size:2em"),
        ("font-size: 11pt", None),
        ("font-size: 9em", None),
        ("color: red", None),
        ("color: url(javascript:alert(1))", None),
        ("font-family: 'Bad;Name'", None),
        ("background: #fff; position: fixed", None),
        ("color:#111111;color:#222222", "color:#222222"),
    ],
)
def test_canonical_style(raw, expected):
    assert canonical_style(raw) == expected


def test_span_kept_in_inline_and_rich():
    v = '<span style="color: #1E5AA8; font-size: 1.5em">Hi</span> there'
    assert (
        canonicalize(v, "inline") == '<span style="color:#1e5aa8;font-size:1.5em">Hi</span> there'
    )
    assert (
        canonicalize(v, "rich")
        == '<p><span style="color:#1e5aa8;font-size:1.5em">Hi</span> there</p>'
    )


def test_span_without_valid_style_unwrapped():
    assert canonicalize('<span style="position:fixed">x</span>', "inline") == "x"
    assert canonicalize('<span class="a">x</span>', "inline") == "x"


def test_span_other_attributes_dropped():
    assert (
        canonicalize('<span style="color:#000" onclick="x()" class="c">x</span>', "inline")
        == '<span style="color:#000000">x</span>'
    )


@pytest.mark.parametrize("fmt", ["inline", "rich"])
def test_spans_count_toward_mark_depth(fmt):
    once = canonicalize('<span style="color:#000">' * 40 + "x" + "</span>" * 40, fmt)
    assert once.count("<span ") == 32
    assert canonicalize(once, fmt) == once


def test_span_idempotent_and_nested():
    v = '<strong><span style="font-family:\'Open Sans\'">a<span style="color:#fff">b</span></span></strong>'
    once = canonicalize(v, "rich")
    assert canonicalize(once, "rich") == once
