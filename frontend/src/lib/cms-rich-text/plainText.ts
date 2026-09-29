// Vendored from CMS client-kit/rich-text v1.0.0 — do not edit; re-sync instead.
// Text content of a stored value, for meta tags, JSON-LD, alt/aria, React keys,
// search, tel:/mailto:. 1:1 port of backend services/rich_text.plain_text
// (rich_text.py lines ~633-666), restricted to the "inline"/"rich" formats the
// kit renders (the backend's "plain" passthrough branch has no client-kit use).
import { HEADING_TAGS, parse, type RichNode } from "./parse";
import { isHtml } from "./detect";
import { legacyToHtml } from "./legacy";
import { pyStrip, PY_WS } from "./whitespace";

// Mirrors Python's `re.sub(r"\s+", " ", ...)`: PY_WS (not JS's native \s) is
// the char class that agrees with Python's Unicode \s — see whitespace.ts.
const PY_WS_RUN_RE = new RegExp(`[${PY_WS}]+`, "g");

export interface PlainTextOptions { format?: "inline" | "rich"; keepLineBreaks?: boolean }

/** Text content of a CMS value — for meta tags, JSON-LD, alt/aria, React keys, search, tel:/mailto:. */
export function plainText(value: string | null | undefined, opts: PlainTextOptions = {}): string {
  if (typeof value !== "string" || !value) return "";
  const format = opts.format ?? "inline";
  const html = format === "rich" && !isHtml(value) ? legacyToHtml(value, "rich") : value;
  const parts: string[] = [];
  // Only leaf blocks (p, h2-h4) emit a trailing "\n"; containers (ul/ol/li/
  // blockquote) just recurse; br/hr emit "\n" (carry rule 6 — mirrors the
  // backend's corrected plain_text, not the doubled-separator plan snippet).
  const walk = (nodes: RichNode[]) => {
    for (const n of nodes) {
      if (typeof n === "string") { parts.push(n); continue; }
      if (n.tag === "br" || n.tag === "hr") { parts.push("\n"); }
      else if (n.tag === "p" || HEADING_TAGS.has(n.tag)) { walk(n.children); parts.push("\n"); }
      else { walk(n.children); }
    }
  };
  walk(parse(html).children);
  const text = parts.join("");
  if (opts.keepLineBreaks) {
    const kept: string[] = [];
    for (const raw of text.split("\n")) {
      const l = pyStrip(raw.replace(PY_WS_RUN_RE, " "));
      if (l || (kept.length && kept[kept.length - 1])) kept.push(l);
    }
    return pyStrip(kept.join("\n"));
  }
  return pyStrip(text.replace(PY_WS_RUN_RE, " "));
}
