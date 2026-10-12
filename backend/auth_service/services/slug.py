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
    ascii_text = mapped.encode("ascii", "ignore").decode("ascii").lower()
    slug = _NON_ALNUM_RE.sub("-", ascii_text).strip("-")
    return slug[:MAX_SLUG_LENGTH].rstrip("-")
