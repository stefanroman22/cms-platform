"""URL-safe slugs for repeater `slug` fields.

Mirrored 1:1 by client-kit/rich-text/src/slug.ts; both are pinned by
client-kit/rich-text/fixtures/slug-vectors.json."""

from __future__ import annotations

import re
import unicodedata

MAX_SLUG_LENGTH = 96

# Letters NFKD does not decompose into an ASCII base letter.
_SPECIAL = {
    "ß": "ss",
    "ẞ": "ss",
    "æ": "ae",
    "Æ": "ae",
    "ø": "o",
    "Ø": "o",
    "đ": "d",
    "Đ": "d",
    "ł": "l",
    "Ł": "l",
    "ı": "i",
    "œ": "oe",
    "Œ": "oe",
}
_NON_ALNUM_RE = re.compile(r"[^a-z0-9]+")


def slugify(text: object) -> str:
    """`"Reparații și întreținere"` → `"reparatii-si-intretinere"`. Non-Latin
    text, and anything that is not a string, gives `""`."""
    if not isinstance(text, str):
        return ""
    decomposed = unicodedata.normalize("NFKD", text)
    no_marks = "".join(ch for ch in decomposed if not unicodedata.category(ch).startswith("M"))
    mapped = "".join(_SPECIAL.get(ch, ch) for ch in no_marks)
    # ASCII letters/digits stay; any other letter or number (a script with no
    # transliteration, e.g. 東) is dropped; everything else (dashes, NBSP, ·, &,
    # emoji…) becomes a separator instead of silently joining two words.
    kept = []
    for ch in mapped:
        if ch.isascii() and ch.isalnum():
            kept.append(ch)
        elif unicodedata.category(ch)[0] not in "LN":
            kept.append("-")
    slug = _NON_ALNUM_RE.sub("-", "".join(kept).lower()).strip("-")
    return slug[:MAX_SLUG_LENGTH].rstrip("-")
