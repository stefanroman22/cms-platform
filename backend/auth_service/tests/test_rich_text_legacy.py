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


def test_legacy_to_html_never_raises_on_pua_sentinels():
    # Raw input containing the internal link-placeholder sentinels (U+E000/U+E001,
    # unassigned private-use code points) must not crash or corrupt output: no
    # real link exists, so a naive final substitution would IndexError on an
    # empty links list.
    sentinel = "0"
    assert legacy_to_html(sentinel, "inline") == "0"
    assert legacy_to_html(sentinel, "rich") == "<p>0</p>"
