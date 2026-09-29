// Vendored from CMS client-kit/rich-text v1.0.0 — do not edit; re-sync instead.
// Python's `str.strip()` (no args) trims by `str.isspace()`, whose character
// set differs from JS's `String.prototype.trim()`: JS treats U+FEFF (BOM /
// zero-width no-break space) as whitespace, Python does not; Python treats
// \x1c-\x1f (file/group/record/unit separators) and \x85 (NEL) as
// whitespace, JS does not. Every backend call to `.strip()`/`.lstrip()`/
// `.rstrip()` *without arguments* (rich_text.py's _has_content, _drop_edge,
// _ends_with_br, _inline's push, _list, safe_href) must use this exact set
// instead of JS's built-in trim. Places where the backend calls
// `strip(" ")`/`lstrip(" ")`/`rstrip(" ")` with an explicit space argument
// stay on ASCII-space-only regexes (unaffected by this module).
// Exported so other modules can build their own `[${PY_WS}]` character classes
// wherever the Python source uses bare `\s`/`\S` inside a compiled regex —
// Python's Unicode `\s` (e.g. rich_text_legacy.py's HEADING_RE, plain_text's
// `re.sub(r"\s+", " ", ...)`) and JS's native `\s` disagree at the edges (JS
// treats U+FEFF as whitespace, Python doesn't; Python treats \x1c-\x1f and
// U+0085 as whitespace, JS doesn't), so JS's built-in \s cannot be reused.
export const PY_WS = "\\t\\n\\v\\f\\r\\x1c-\\x1f \\x85\\xa0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000";
const PY_STRIP_RE = new RegExp(`^[${PY_WS}]+|[${PY_WS}]+$`, "g");

/** Mirrors Python's `str.strip()` (no-argument form) exactly. */
export function pyStrip(s: string): string {
  return s.replace(PY_STRIP_RE, "");
}
