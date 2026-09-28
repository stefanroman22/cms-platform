// serialize.ts — editor HTML ⇄ stored CMS value (spec §6, §4.4).
import {
  isHtml,
  legacyToHtml,
  normalizeRich,
  normalizeInline,
  parse,
  serialize as kitSerialize,
} from "@/lib/cms-rich-text";

export type RichMode = "inline" | "rich";
const EMPTY_DOC = /^(?:<p>(?:\s|&nbsp;| |<br\s*\/?>)*<\/p>)*$/;

// Re-parses the editor's raw getHTML() output through the vendored kit's
// allow-list parser + canonical normalizer before storing. This is what
// strips attributes TipTap's Link mark can carry through a paste (target,
// rel, class, title — none of which the kit's parser ever recognizes on
// <a>, only href) and guarantees the stored value, and the character count
// measured from it, exactly match what the backend would canonicalize it to.
export function toStored(html: string, mode: RichMode): string {
  const trimmed = html.trim();
  if (EMPTY_DOC.test(trimmed)) return "";
  if (mode === "inline") {
    const m = /^<p>([\s\S]*)<\/p>$/.exec(trimmed);
    const inner = m ? m[1] : trimmed;
    return kitSerialize(normalizeInline(parse(inner).children));
  }
  return kitSerialize(normalizeRich(parse(trimmed).children));
}

export function fromStored(value: unknown, mode: RichMode): string {
  const v = typeof value === "string" ? value : "";
  if (!v.trim()) return "";
  if (mode === "inline") return `<p>${v}</p>`; // inline values are HTML fragments — never legacy-converted here
  return isHtml(v) ? v : legacyToHtml(v, "rich");
}
