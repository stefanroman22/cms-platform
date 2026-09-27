"""Differential test: a seeded random tag-soup corpus, generated from and run
through the kit itself (client-kit/rich-text/tests/_generate-fuzz-vectors.test.ts,
seed 20260927, committed at client-kit/rich-text/fixtures/fuzz-vectors.json),
replayed against the backend. Exists because rich_text._parse is a
from-scratch Python port of client-kit/rich-text/src/parse.ts (fix round 3):
the ~70 hand-written shared vectors in canonical-vectors.json pin specific
named cases, but a random corpus catches unanticipated interactions between
fragments (comments butting up against tags, nested/mismatched close tags,
self-closing edge cases, etc.) that no one thought to write a named vector
for.

Compared against `_parse` + the same `_inline`/`_blocks`/`_serialize` steps
`canonicalize()` uses, NOT against `canonicalize()` itself — matching how
the kit's own shared-fixture test helper works (client-kit/rich-text/tests/
canonical.test.ts's `canonical()`: parse -> normalize -> serialize, no
legacy-content layer). `is_html`/legacy-content routing is a separate,
orthogonal, pre-existing backend-only feature that parse.ts has no
equivalent of at all (a value with no tag `is_html` recognises is legacy
content per ADR-0010 regardless of whether `_parse` would have handled it
fine) — every other fixture and report in this task series hits the same
distinction for individual named vectors (each solved there by prefixing a
recognised tag so `canonicalize()` takes the same code path being tested);
doing that per-fragment for a 2000-case *generated* corpus isn't practical,
so this test compares the two parse pipelines directly instead, and
`test_fuzz_corpus_canonicalize_and_plain_text_do_not_crash` below separately
covers the real `canonicalize()`/`plain_text()` entry points for robustness
(not byte parity, since the legacy layer makes that the wrong comparison).

To regenerate the corpus after changing the generator's FRAGMENTS/COUNT/SEED:
    cd client-kit/rich-text && GENERATE_FUZZ_VECTORS=1 npx vitest run tests/_generate-fuzz-vectors.test.ts
"""

import json
import re
from html import unescape
from pathlib import Path

import pytest

from auth_service.services.rich_text import (
    _blocks,
    _inline,
    _parse,
    _serialize,
    _trim_edges,
    _trim_empty_edges,
    canonicalize,
    plain_text,
)

_REPO = Path(__file__).resolve().parents[3]
_FUZZ_VECTORS = json.loads(
    (_REPO / "client-kit" / "rich-text" / "fixtures" / "fuzz-vectors.json").read_text("utf-8")
)


def _kit_equivalent_canonical(value: str, fmt: str) -> str:
    """Mirrors client-kit/rich-text/tests/canonical.test.ts's `canonical()`
    helper exactly: parse -> normalize -> serialize, with no legacy-content
    routing (canonicalize()'s `is_html` branch has no equivalent in the
    kit's own comparison helper either)."""
    root = _parse(value)
    if fmt == "inline":
        return _serialize(_trim_edges(_inline(root.children)))
    return _serialize(_trim_empty_edges(_blocks(root.children, 0)))


# The kit's decodeEntities only recognises amp/lt/gt/quot/apos/nbsp (always
# semicolon-terminated) plus numeric refs; Python's html.unescape (used by
# rich_text._parse, per an explicit controller ruling for better
# DeepL-output fidelity) recognises the full HTML5 named-entity table,
# *including* the legacy subset HTML5 allows without a trailing `;` (e.g.
# "&notanentity" — html.unescape greedily matches the legacy "&not" -> "¬"
# prefix and leaves "anentity"; the kit's regex requires ";" so never
# touches it at all). This is an accepted, already-logged pre-existing gap
# (not something fix round 3 introduces or is expected to close) — see
# _parse's docstring. Rather than re-deriving which of HTML5's ~100+ legacy
# semicolon-optional names might appear in a random fragment, a case is
# "comparable" iff the kit's own decode rule and Python's html.unescape
# actually agree on this specific input — computed directly, not guessed at
# with a regex over the safe set.
_KIT_ENTITY_RE = re.compile(r"&(#[xX][0-9a-fA-F]+|#[0-9]+|[a-zA-Z][a-zA-Z0-9]*);")
_KIT_NAMED_ENTITIES = {"amp": "&", "lt": "<", "gt": ">", "quot": '"', "apos": "'", "nbsp": "\xa0"}


def _kit_decode_entities(value: str) -> str:
    """Python port of client-kit/rich-text/src/parse.ts's decodeEntities,
    used only to classify fuzz-corpus divergence, not by canonicalize()."""

    def repl(m: re.Match) -> str:
        e = m.group(1)
        if e[0] == "#":
            try:
                cp = int(e[2:], 16) if e[1] in "xX" else int(e[1:])
            except ValueError:
                return m.group(0)
            if 0 < cp <= 0x10FFFF and not (0xD800 <= cp <= 0xDFFF):
                return chr(cp)
            return "�"
        return _KIT_NAMED_ENTITIES.get(e, m.group(0))

    return _KIT_ENTITY_RE.sub(repl, value)


def _entity_decoding_diverges(value: str) -> bool:
    return unescape(value) != _kit_decode_entities(value)


_COMPARABLE = [v for v in _FUZZ_VECTORS if not _entity_decoding_diverges(v["input"])]
_UNSAFE_ENTITY = [v for v in _FUZZ_VECTORS if _entity_decoding_diverges(v["input"])]


@pytest.mark.parametrize("vec", _COMPARABLE, ids=[f"{v['i']}-{v['fmt']}" for v in _COMPARABLE])
def test_fuzz_corpus_matches_kit(vec):
    assert _kit_equivalent_canonical(vec["input"], vec["fmt"]) == vec["expected"]


@pytest.mark.parametrize("vec", _FUZZ_VECTORS, ids=[f"{v['i']}-{v['fmt']}" for v in _FUZZ_VECTORS])
def test_fuzz_corpus_canonicalize_and_plain_text_do_not_crash(vec):
    # The real public entry points, over the whole corpus including the
    # entity-divergent cases (byte parity isn't meaningful for those, but
    # they must still not raise). Also exercises is_html/legacy routing,
    # which _kit_equivalent_canonical above deliberately bypasses.
    canonicalize(vec["input"], vec["fmt"], enforce_limit=False)
    plain_text(vec["input"], vec["fmt"])


def test_fuzz_corpus_has_expected_size():
    # If this fails, the committed fixture and this test's understanding of
    # it (COUNT in the generator) have drifted — regenerate or investigate,
    # don't just bump the number.
    assert len(_FUZZ_VECTORS) == 2000


def test_fuzz_corpus_entity_filter_is_exercised():
    # Sanity check on the filter itself, not the corpus: fails loudly if the
    # divergence check above stops matching anything (e.g. from a typo)
    # rather than silently comparing zero cases, or if it over-matches
    # everything.
    assert 0 < len(_UNSAFE_ENTITY) < len(_FUZZ_VECTORS)
