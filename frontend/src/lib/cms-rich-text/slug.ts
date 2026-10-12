// Vendored from CMS client-kit/rich-text v1.2.0 — do not edit; re-sync instead.
// URL-safe slugs for repeater `slug` fields: a 1:1 port of the backend's
// services/slug.py, pinned by fixtures/slug-vectors.json. Sites can compare
// slugify(param) with a stored slug to match URLs tolerantly.

export const MAX_SLUG_LENGTH = 96;

// Letters NFKD does not decompose into an ASCII base letter.
const SPECIAL: Record<string, string> = {
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
};
const MARK_RE = /\p{M}/u;
const NON_ASCII_RE = /[^\x00-\x7f]/g;
const NON_ALNUM_RE = /[^a-z0-9]+/g;

/** `"Reparații și întreținere"` → `"reparatii-si-intretinere"`. Non-Latin text gives `""`. */
export function slugify(text: string): string {
  if (typeof text !== "string") return "";
  let mapped = "";
  for (const ch of text.normalize("NFKD")) {
    if (MARK_RE.test(ch)) continue;
    mapped += SPECIAL[ch] ?? ch;
  }
  const slug = mapped
    .replace(NON_ASCII_RE, "")
    .toLowerCase()
    .replace(NON_ALNUM_RE, "-")
    .replace(/^-+|-+$/g, "");
  return slug.slice(0, MAX_SLUG_LENGTH).replace(/-+$/, "");
}
