// Vendored from CMS client-kit/rich-text v1.0.0 — do not edit; re-sync instead.
// Legacy (pre-rich-text) text → canonical HTML. 1:1 port of backend services/rich_text_legacy.py;
// both are pinned by fixtures/legacy-vectors.json — change them together.
import { escapeAttr, escapeText } from "./serialize";
import { safeHref } from "./href";
import { pyStrip, PY_WS } from "./whitespace";

// One Python `\s` char / one Python `\S` char, for use inside a JS character
// class wherever the Python source uses bare `\s`/`\S` in a compiled regex —
// see whitespace.ts's PY_WS comment for why JS's native \s can't be reused.
const S = PY_WS;
const NOT_S = `^${PY_WS}`;

const WS = /[ \t\r\n\f]+/g;
const W = "0-9A-Za-z\\u00C0-\\u024F";
const LINK_RE = new RegExp(`\\[([^\\]\\n]+)\\]\\(([^)${S}]+)\\)`, "g");
// `s` (dotAll): Python's `.` matches any char except `\n` (incl. U+2028/U+2029
// LINE/PARAGRAPH SEPARATOR); JS's `.` without `s` also excludes U+2028/U+2029
// (they're JS line terminators too). Every input to these regexes is already
// a single line (split on "\n" upstream, in `rich()`/`inlineMd()`), so `.`
// only ever needs to exclude "\n" itself here — `s` makes it behave exactly
// like Python's `.` for that already-single-line input. Fix round 1 finding.
const BOLD_RE = new RegExp(
  `\\*\\*(?=[${NOT_S}])(.+?)(?<=[${NOT_S}])\\*\\*|__(?=[${NOT_S}])(.+?)(?<=[${NOT_S}])__`, "gs");
const STRIKE_RE = new RegExp(`~~(?=[${NOT_S}])(.+?)(?<=[${NOT_S}])~~`, "gs");
const EM_RE = new RegExp(
  `(?<![${W}*])\\*(?=[${NOT_S}])(.+?)(?<=[${NOT_S}])\\*(?![${W}*])|(?<![${W}_])_(?=[${NOT_S}])(.+?)(?<=[${NOT_S}])_(?![${W}_])`,
  "gs");
// The placeholder index is wrapped in U+E000/U+E001 (private-use sentinels) so
// it can never collide with an ordinary digit run elsewhere in the text (e.g.
// "5 * 3 * 2 = 30"); legacyToHtml() strips any pre-existing U+E000/U+E001 from
// raw input up front for the same reason (carry rule 7).
const PH_RE = /(\d+)/g;
const HEADING_RE = new RegExp(`^(#{1,6})[${S}]+(.*)$`, "s");
const HR_RE = /^(?:-{3,}|\*{3,}|_{3,})$/;
const UL_RE = new RegExp(`^[-*+][${S}]+(.+)$`, "s");
const OL_RE = new RegExp(`^\\d{1,9}[.)][${S}]+(.+)$`, "s");
const QUOTE_RE = new RegExp(`^>[${S}]?(.*)$`, "s");
const BLANK_SPLIT_RE = /\n[ \t]*\n/;

const clean = (line: string) => pyStrip(line.replace(WS, " "));

function inlineMd(line: string): string {
  const links: string[] = [];
  let s = line.replace(LINK_RE, (_m, label: string, url: string) => {
    const href = safeHref(url);
    links.push(href ? `<a href="${escapeAttr(href)}">${escapeText(label)}</a>` : escapeText(label));
    return `${links.length - 1}`;
  });
  s = escapeText(s);
  s = s.replace(BOLD_RE, (_m, a?: string, b?: string) => `<strong>${a || b}</strong>`);
  s = s.replace(STRIKE_RE, (_m, a: string) => `<s>${a}</s>`);
  s = s.replace(EM_RE, (_m, a?: string, b?: string) => `<em>${a || b}</em>`);
  return s.replace(PH_RE, (_m, k: string) => links[Number(k)]);
}

type Kind = "p" | "quote" | "ul" | "ol" | null;
function flush(kind: Kind, groups: string[][], out: string[]): void {
  if (kind === null || !groups.length) return;
  if (kind === "p" || kind === "quote") {
    const lines = groups[0].filter(Boolean);
    if (!lines.length) return;
    const body = lines.join("<br>");
    out.push(kind === "p" ? `<p>${body}</p>` : `<blockquote><p>${body}</p></blockquote>`);
    return;
  }
  const items = groups.filter((g) => g.length).map((g) => `<li><p>${g.join("<br>")}</p></li>`).join("");
  if (items) out.push(`<${kind}>${items}</${kind}>`);
}

function rich(text: string): string {
  const out: string[] = [];
  for (const rawBlock of text.split(BLANK_SPLIT_RE)) {
    let kind: Kind = null;
    let groups: string[][] = [];
    for (const rawLine of rawBlock.split("\n")) {
      const line = clean(rawLine);
      if (!line) continue;
      if (HR_RE.test(line)) {
        flush(kind, groups, out);
        kind = null;
        groups = [];
        out.push("<hr>");
        continue;
      }
      const h = HEADING_RE.exec(line);
      if (h) {
        flush(kind, groups, out);
        kind = null;
        groups = [];
        const content = inlineMd(h[2]);
        const level = ({ 1: 2, 2: 2, 3: 3 } as Record<number, number>)[h[1].length] ?? 4;
        if (content) out.push(`<h${level}>${content}</h${level}>`);
        continue;
      }
      const ul = UL_RE.exec(line);
      const ol = ul ? null : OL_RE.exec(line);
      const m = ul ?? ol;
      if (m) {
        const k: Kind = ul ? "ul" : "ol";
        if (kind !== k) { flush(kind, groups, out); kind = k; groups = []; }
        groups.push([inlineMd(m[1])]);
        continue;
      }
      const q = QUOTE_RE.exec(line);
      if (q) {
        if (kind !== "quote") { flush(kind, groups, out); kind = "quote"; groups = [[]]; }
        groups[0].push(inlineMd(clean(q[1])));
        continue;
      }
      if (kind === "ul" || kind === "ol") { groups[groups.length - 1].push(inlineMd(line)); continue; }
      if (kind !== "p") { flush(kind, groups, out); kind = "p"; groups = [[]]; }
      groups[0].push(inlineMd(line));
    }
    flush(kind, groups, out);
  }
  return out.join("");
}

function inlinePlain(text: string): string {
  const lines = text.split("\n").map(clean);
  while (lines.length && !lines[0]) lines.shift();
  while (lines.length && !lines[lines.length - 1]) lines.pop();
  return lines.map(escapeText).join("<br>");
}

/** Pre-rich-text content → canonical HTML. Rich = Markdown-lite; inline = plain text (migration only). */
export function legacyToHtml(text: string, fmt: "inline" | "rich"): string {
  if (typeof text !== "string") return "";
  let t = text.replace(/\r\n/g, "\n").replace(/\r/g, "\n").replace(/\xa0/g, " ");
  // Strip the private-use sentinels inlineMd() uses internally to protect
  // already-built <a> tags from the bold/italic/strike passes. Without this,
  // raw input containing these unassigned PUA code points could collide with
  // a real placeholder once PH_RE.replace runs over the whole string.
  t = t.replace(/[]/g, "");
  if (!pyStrip(t)) return "";
  return fmt === "rich" ? rich(t) : inlinePlain(t);
}
