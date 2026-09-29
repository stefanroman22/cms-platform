// Vendored from CMS client-kit/rich-text v1.0.0 — do not edit; re-sync instead.
// Mirrors backend rich_text.is_html exactly (see its docstring): the original
// `<(?:p|...)\b[^>]*>` backtracks quadratically on an unterminated tag-open run
// like "<b" * 50000, because the `[^>]*>` tail always succeeds from a match of
// the opening prefix iff *some* `>` occurs anywhere later in the string. So the
// original true/false answer is exactly "does some recognised open-tag prefix
// start before the *last* `>` in the whole string" — checking it that way is
// O(n) and gives the identical answer for every input, since HTML_OPEN_RE has
// no unbounded/nested quantifiers (a small fixed alternation plus a word
// boundary) and can't blow up the way `[^>]*` does.
const HTML_OPEN_RE = /<(?:p|br|strong|em|u|s|a|ul|ol|li|h[1-6]|blockquote|hr|b|i|div|span)\b/i;

/** True when `value` contains at least one recognised HTML tag (spec §4.4). */
export function isHtml(value: string): boolean {
  const gt = value.lastIndexOf(">");
  if (gt === -1) return false;
  const m = HTML_OPEN_RE.exec(value);
  return m !== null && m.index < gt;
}
