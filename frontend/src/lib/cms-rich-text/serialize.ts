// Vendored from CMS client-kit/rich-text v1.0.0 — do not edit; re-sync instead.
import type { RichNode } from "./parse";

const WS = /[ \t\r\n\f]+/g;
// Mirrors backend escape_text: only the literal U+00A0 non-breaking space is
// re-escaped to &nbsp; — ordinary spaces stay literal spaces.
export const escapeText = (s: string) =>
  s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/ /g, "&nbsp;");
export const escapeAttr = (s: string) => escapeText(s).replace(/"/g, "&quot;");

/** Canonical HTML string of a normalized tree (mirrors backend _serialize). */
export function serialize(nodes: RichNode[]): string {
  let out = "";
  let buf = "";
  const flush = () => {
    if (buf) { out += escapeText(buf.replace(WS, " ")); buf = ""; }
  };
  for (const n of nodes) {
    if (typeof n === "string") { buf += n; continue; }
    flush();
    if (n.tag === "br" || n.tag === "hr") out += `<${n.tag}>`;
    else if (n.tag === "a") out += `<a href="${escapeAttr(n.href ?? "")}">${serialize(n.children)}</a>`;
    else out += `<${n.tag}>${serialize(n.children)}</${n.tag}>`;
  }
  flush();
  return out;
}
