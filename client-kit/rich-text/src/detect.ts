const HTML_RE = /<(?:p|br|strong|em|u|s|a|ul|ol|li|h[1-6]|blockquote|hr|b|i|div|span)\b[^>]*>/i;
/** True when `value` contains at least one recognised HTML tag (spec §4.4). */
export function isHtml(value: string): boolean {
  return HTML_RE.test(value);
}
