// serialize.ts — editor HTML ⇄ stored CMS value (spec §6, §4.4).
import { isHtml, legacyToHtml } from "@/lib/cms-rich-text";

export type RichMode = "inline" | "rich";
const EMPTY_DOC = /^(?:<p>(?:\s|&nbsp;| |<br\s*\/?>)*<\/p>)*$/;

export function toStored(html: string, mode: RichMode): string {
  const trimmed = html.trim();
  if (EMPTY_DOC.test(trimmed)) return "";
  if (mode === "inline") {
    const m = /^<p>([\s\S]*)<\/p>$/.exec(trimmed);
    return (m ? m[1] : trimmed).replace(/^(?:<br\s*\/?>)+|(?:<br\s*\/?>)+$/g, "").trim();
  }
  return trimmed;
}

export function fromStored(value: unknown, mode: RichMode): string {
  const v = typeof value === "string" ? value : "";
  if (!v.trim()) return "";
  if (mode === "inline") return `<p>${v}</p>`; // inline values are HTML fragments — never legacy-converted here
  return isHtml(v) ? v : legacyToHtml(v, "rich");
}
