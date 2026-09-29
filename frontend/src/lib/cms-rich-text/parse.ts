// Vendored from CMS client-kit/rich-text v1.0.0 — do not edit; re-sync instead.
export type RichNode = string | RichElement;
export interface RichElement {
  tag: string;
  href?: string | null;
  children: RichNode[];
}

export const MARK_TAGS = new Set(["strong", "em", "u", "s"]);
export const INLINE_TAGS = new Set(["strong", "em", "u", "s", "a", "br"]);
export const HEADING_TAGS = new Set(["h2", "h3", "h4"]);
export const BLOCK_TAGS = new Set(["p", "ul", "ol", "li", "blockquote", "hr", "h2", "h3", "h4"]);
const RICH_TAGS = new Set([...INLINE_TAGS, ...BLOCK_TAGS]);

// Flat parse-tree depth safety net (no exemptions): only exists to keep the
// recursive semantic transform in normalize.ts (inline/blocks) within a safe
// recursion depth for any input, regardless of tag mix. Mirrors backend
// _Builder.handle_starttag's MAX_PARSE_DEPTH check.
const MAX_PARSE_DEPTH = 256;

const SYNONYMS: Record<string, string> = {
  b: "strong", i: "em", strike: "s", del: "s", ins: "u", h1: "h2", h5: "h4", h6: "h4", div: "p",
};
const DROP_WITH_CONTENT = new Set([
  "script", "style", "iframe", "object", "svg", "math", "template", "noscript", "head",
  "title", "textarea", "select", "button", "canvas", "audio", "video", "picture",
]);
/** Elements whose content is text, not markup (the backend HTMLParser's CDATA mode). */
const RAW_TEXT = new Set(["script", "style"]);
const TAG_RE = /<(\/?)([a-zA-Z][a-zA-Z0-9:-]*)((?:[^>"']|"[^"]*"|'[^']*')*?)(\/?)>/y;
const HREF_RE = /(?:^|\s)href\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s"'=<>`]+))/i;
const LETTER_RE = /[a-zA-Z]/;
// nbsp decodes to U+00A0 (a real non-breaking space), not a regular space —
// mirrors Python's html.parser/html.unescape, and matches escapeText in
// serialize.ts which only re-escapes U+00A0 back to &nbsp;.
const NAMED: Record<string, string> = { amp: "&", lt: "<", gt: ">", quot: '"', apos: "'", nbsp: " " };

export function decodeEntities(s: string): string {
  return s.replace(/&(#[xX][0-9a-fA-F]+|#[0-9]+|[a-zA-Z][a-zA-Z0-9]*);/g, (m, e: string) => {
    if (e[0] === "#") {
      const cp = e[1] === "x" || e[1] === "X" ? parseInt(e.slice(2), 16) : parseInt(e.slice(1), 10);
      const ok = cp > 0 && cp <= 0x10ffff && !(cp >= 0xd800 && cp <= 0xdfff);
      return ok ? String.fromCodePoint(cp) : "�";
    }
    return NAMED[e] ?? m;
  });
}

/** Tag-soup tolerant parser keeping only allow-listed elements. Mirrors backend _Builder. */
export function parse(html: string): RichElement {
  const root: RichElement = { tag: "#root", children: [] };
  const stack: RichElement[] = [root];
  const lower = html.toLowerCase();
  const n = html.length;
  let skip = 0;
  let i = 0;

  const text = (t: string) => {
    if (skip || !t) return;
    const kids = stack[stack.length - 1].children;
    const last = kids[kids.length - 1];
    if (typeof last === "string") kids[kids.length - 1] = last + t;
    else kids.push(t);
  };
  const open = (raw: string, attrs: string) => {
    if (DROP_WITH_CONTENT.has(raw)) { skip++; return; }
    if (skip) return;
    const tag = SYNONYMS[raw] ?? raw;
    if (tag === "br" || tag === "hr") { stack[stack.length - 1].children.push({ tag, children: [] }); return; }
    if (!RICH_TAGS.has(tag)) return;
    if (stack.length - 1 >= MAX_PARSE_DEPTH) return; // depth cap reached: unwrap like an unknown element
    let node: RichElement;
    if (tag === "a") {
      const h = HREF_RE.exec(attrs);
      node = { tag, href: h ? decodeEntities(h[1] ?? h[2] ?? h[3] ?? "") : null, children: [] };
    } else {
      node = { tag, children: [] };
    }
    stack[stack.length - 1].children.push(node);
    stack.push(node);
  };
  const close = (raw: string) => {
    if (DROP_WITH_CONTENT.has(raw)) { if (skip) skip--; return; }
    if (skip) return;
    const tag = SYNONYMS[raw] ?? raw;
    if (!RICH_TAGS.has(tag) || tag === "br" || tag === "hr") return;
    for (let k = stack.length - 1; k > 0; k--) {
      if (stack[k].tag === tag) { stack.length = k; return; }
    }
  };

  while (i < n) {
    const lt = html.indexOf("<", i);
    if (lt === -1) { text(decodeEntities(html.slice(i))); break; }
    if (lt > i) text(decodeEntities(html.slice(i, lt)));
    if (html.startsWith("<!--", lt)) { const end = html.indexOf("-->", lt + 4); i = end === -1 ? n : end + 3; continue; }
    if (html[lt + 1] === "!" || html[lt + 1] === "?") { const end = html.indexOf(">", lt); i = end === -1 ? n : end + 1; continue; }

    // A `<` only begins a tag when followed by an ASCII letter (open tag) or
    // `/` + ASCII letter (close tag); anything else is literal text. This
    // O(1) check avoids ever invoking the tag regex on a `<` that can't
    // possibly start a tag (e.g. "a < b").
    const c1 = html[lt + 1];
    const isTagStart =
      (c1 !== undefined && LETTER_RE.test(c1)) ||
      (c1 === "/" && html[lt + 2] !== undefined && LETTER_RE.test(html[lt + 2]));
    if (!isTagStart) { text("<"); i = lt + 1; continue; }

    // Scan forward once, char by char, tracking quote state, to find the
    // first `>` outside quotes — that's the tag's end. No backtracking, so
    // this is O(remaining input) for this one `<`, not repeated per `<`.
    let j = lt + 1;
    let quote = "";
    let tagEnd = -1;
    while (j < n) {
      const ch = html[j];
      if (quote) {
        if (ch === quote) quote = "";
      } else if (ch === '"' || ch === "'") {
        quote = ch;
      } else if (ch === ">") {
        tagEnd = j;
        break;
      }
      j++;
    }
    if (tagEnd === -1) {
      // No terminating `>` anywhere in the rest of the input (or an unclosed
      // quote swallowed it): this `<` and everything after it is literal
      // text. Emit it and stop — never rescans the same span again.
      text(decodeEntities(html.slice(lt)));
      break;
    }

    const tagText = html.slice(lt, tagEnd + 1);
    TAG_RE.lastIndex = 0;
    const m = TAG_RE.exec(tagText);
    if (!m) { text(decodeEntities(tagText)); i = tagEnd + 1; continue; }
    i = tagEnd + 1;
    const tag = m[2].toLowerCase();
    const selfClosing = m[4] === "/";
    if (m[1] === "/") { close(tag); continue; }
    if (RAW_TEXT.has(tag) && !selfClosing) {
      const endTag = lower.indexOf(`</${tag}`, i);
      if (endTag === -1) i = n;
      else { const gt = html.indexOf(">", endTag); i = gt === -1 ? n : gt + 1; }
      continue;
    }
    if (selfClosing) { if (!DROP_WITH_CONTENT.has(tag)) { open(tag, m[3]); close(tag); } continue; }
    open(tag, m[3]);
  }
  return root;
}
