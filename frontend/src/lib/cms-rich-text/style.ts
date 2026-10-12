// Vendored from CMS client-kit/rich-text v1.1.0 — do not edit; re-sync instead.
// span[style] (ADR-0011): the only declarations a styled span keeps.
// 1:1 port of backend services/rich_text.canonical_style. Explicit ASCII
// classes (no \s, \d or /i, whose Unicode behaviour differs between Python and
// JS) so both ports agree on every input.
import type { CSSProperties } from "react";
import { pyStrip } from "./whitespace";

export const STYLE_RE =
  /(?:^|[ \t\n\f\r])[sS][tT][yY][lL][eE][ \t\n\f\r]*=[ \t\n\f\r]*(?:"([^"]*)"|'([^']*)'|([^ \t\n\f\r"'=<>`]+))/;
const HEX_RE = /^#([0-9a-fA-F]{3}|[0-9a-fA-F]{6})$/;
const RGB_RE =
  /^rgb\([ \t\r\n\f]*([0-9]{1,3})[ \t\r\n\f]*,[ \t\r\n\f]*([0-9]{1,3})[ \t\r\n\f]*,[ \t\r\n\f]*([0-9]{1,3})[ \t\r\n\f]*\)$/i;
const FONT_FAMILY_RE = /^[A-Za-z0-9][A-Za-z0-9 \-]{0,63}$/;
const FONT_SIZE_RE = /^([0-9]{1,2}(?:\.[0-9]{1,3})?)em$/i;
const WS = /[ \t\r\n\f]+/g;

function styleColor(v: string): string | null {
  const hex = HEX_RE.exec(v);
  if (hex) {
    const h = hex[1].toLowerCase();
    return "#" + (h.length === 3 ? [...h].map((c) => c + c).join("") : h);
  }
  const rgb = RGB_RE.exec(v);
  if (rgb) {
    const parts = [rgb[1], rgb[2], rgb[3]].map(Number);
    if (parts.every((c) => c <= 255)) return "#" + parts.map((c) => c.toString(16).padStart(2, "0")).join("");
  }
  return null;
}

function styleFontFamily(v: string): string | null {
  let name = pyStrip(v.split(",")[0]);
  if (name.length >= 2 && name[0] === name[name.length - 1] && (name[0] === "'" || name[0] === '"')) {
    name = pyStrip(name.slice(1, -1));
  }
  name = name.replace(WS, " ");
  return FONT_FAMILY_RE.test(name) ? `'${name}'` : null;
}

function styleFontSize(v: string): string | null {
  const m = FONT_SIZE_RE.exec(v);
  if (!m) return null;
  const size = Number(m[1]);
  if (!(size >= 0.5 && size <= 4)) return null;
  return size.toFixed(3).replace(/0+$/, "").replace(/\.$/, "") + "em";
}

// Canonical declaration order (ADR-0011): color, font-family, font-size.
const STYLE_PROPS: Record<string, (v: string) => string | null> = {
  color: styleColor,
  "font-family": styleFontFamily,
  "font-size": styleFontSize,
};

/** Canonical span declarations, or null if none is valid. Every other property, and any invalid
 *  value, is dropped; a later valid declaration of the same property wins (an invalid one is ignored). */
export function canonicalStyle(raw: string): string | null {
  const kept: Record<string, string> = {};
  for (const decl of raw.split(";")) {
    const colon = decl.indexOf(":");
    if (colon === -1) continue;
    const prop = pyStrip(decl.slice(0, colon)).toLowerCase();
    const check = Object.prototype.hasOwnProperty.call(STYLE_PROPS, prop) ? STYLE_PROPS[prop] : undefined;
    const canon = check ? check(pyStrip(decl.slice(colon + 1))) : null;
    if (canon !== null) kept[prop] = canon;
  }
  const out = Object.keys(STYLE_PROPS).filter((p) => p in kept).map((p) => `${p}:${kept[p]}`).join(";");
  return out || null;
}

/** The declarations of a span style (canonicalised first), e.g. for a renderer or editor toolbar. */
export function parseStyle(canonical: string): { color?: string; fontFamily?: string; fontSize?: string } {
  const out: { color?: string; fontFamily?: string; fontSize?: string } = {};
  for (const decl of (canonicalStyle(canonical) ?? "").split(";")) {
    const colon = decl.indexOf(":");
    if (colon === -1) continue;
    const prop = decl.slice(0, colon);
    const value = decl.slice(colon + 1);
    if (prop === "color") out.color = value;
    else if (prop === "font-family") out.fontFamily = value.slice(1, -1);
    else if (prop === "font-size") out.fontSize = value;
  }
  return out;
}

/** React style for a span: the family falls back to the site's body font. */
export function styleCss(style: string | null | undefined): CSSProperties {
  const s = parseStyle(style ?? "");
  const css: CSSProperties = {};
  if (s.color) css.color = s.color;
  if (s.fontFamily) css.fontFamily = `'${s.fontFamily}', var(--cms-font-body, sans-serif)`;
  if (s.fontSize) css.fontSize = s.fontSize;
  return css;
}
