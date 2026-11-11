// Vendored from CMS client-kit/rich-text v1.3.1 — do not edit; re-sync instead.
export interface ThemeColor { name: string; value: string }
export type ThemeFont =
  | { family: string; source: "google"; weights: number[]; italic: boolean }
  | { family: string; source: "upload"; files: { url: string; weight: number; style: "normal" | "italic" }[] }
  | { family: string; source: "system" };
export interface CmsTheme {
  colors: ThemeColor[]; surfaces: ThemeColor[]; fonts: ThemeFont[];
  body_font: string; heading_font: string;
}
export interface CmsIconValue { src: string; mode: "tint" | "original"; color: string; name: string }

export const FONT_FAMILY_RE = /^[A-Za-z0-9][A-Za-z0-9 \-]{0,63}$/;
const HEX_RE = /^#[0-9a-fA-F]{6}$/;
const UNSAFE_URL_RE = /["'()\\\s<>]/;

const isObj = (v: unknown): v is Record<string, unknown> => typeof v === "object" && v !== null && !Array.isArray(v);
const safeUrl = (u: unknown): u is string => typeof u === "string" && u.startsWith("https://") && !UNSAFE_URL_RE.test(u);

function readColors(raw: unknown): ThemeColor[] {
  if (!Array.isArray(raw)) return [];
  const out: ThemeColor[] = [];
  for (const c of raw) {
    if (isObj(c) && typeof c.name === "string" && typeof c.value === "string" && HEX_RE.test(c.value)) {
      out.push({ name: c.name, value: c.value.toLowerCase() });
    }
  }
  return out;
}

function readFont(f: unknown): ThemeFont | null {
  if (!isObj(f) || typeof f.family !== "string" || !FONT_FAMILY_RE.test(f.family)) return null;
  if (f.source === "system") return { family: f.family, source: "system" };
  if (f.source === "google") {
    const weights = Array.isArray(f.weights)
      ? f.weights.filter((w): w is number => typeof w === "number" && Number.isInteger(w) && w >= 1 && w <= 1000)
      : [];
    return { family: f.family, source: "google", weights, italic: f.italic === true };
  }
  if (f.source === "upload") {
    const files: { url: string; weight: number; style: "normal" | "italic" }[] = [];
    if (Array.isArray(f.files)) {
      for (const x of f.files) {
        if (isObj(x) && safeUrl(x.url) && typeof x.weight === "number" && Number.isFinite(x.weight)) {
          files.push({ url: x.url, weight: x.weight, style: x.style === "italic" ? "italic" : "normal" });
        }
      }
    }
    return { family: f.family, source: "upload", files };
  }
  return null;
}

export function readTheme(raw: unknown): CmsTheme | null {
  if (!isObj(raw)) return null;
  const colors = readColors(raw.colors);
  const surfaces = readColors(raw.surfaces);
  const fonts: ThemeFont[] = [];
  if (Array.isArray(raw.fonts)) {
    for (const f of raw.fonts) {
      const font = readFont(f);
      if (font) fonts.push(font);
    }
  }
  if (!colors.length && !surfaces.length && !fonts.length) return null;
  return {
    colors, surfaces, fonts,
    body_font: typeof raw.body_font === "string" ? raw.body_font : "",
    heading_font: typeof raw.heading_font === "string" ? raw.heading_font : "",
  };
}

export function googleFontsHref(font: { family: string; weights: number[]; italic: boolean }): string {
  const family = font.family.replace(/ /g, "+");
  const weights = [...new Set(font.weights)].sort((a, b) => a - b);
  let spec = `family=${family}`;
  if (weights.length) {
    spec += font.italic
      ? `:ital,wght@${[0, 1].flatMap((i) => weights.map((w) => `${i},${w}`)).join(";")}`
      : `:wght@${weights.join(";")}`;
  }
  return `https://fonts.googleapis.com/css2?${spec}&display=swap`;
}

// A theme can reach these without readTheme(), so the family is re-checked before it goes into CSS.
export function fontStack(family: string, fallback = "system-ui, sans-serif"): string {
  return FONT_FAMILY_RE.test(family) ? `'${family}', ${fallback}` : fallback;
}

const FORMATS: Record<string, string> = { woff2: "woff2", woff: "woff", ttf: "truetype", otf: "opentype" };
const fontFormat = (url: string): string | null => {
  const ext = url.split(/[?#]/)[0].split(".").pop()?.toLowerCase() ?? "";
  return FORMATS[ext] ?? null;
};

export function themeCss(theme: CmsTheme): string {
  let css = "";
  for (const f of theme.fonts) {
    if (f.source !== "upload" || !FONT_FAMILY_RE.test(f.family)) continue;
    for (const file of f.files) {
      const format = fontFormat(file.url);
      if (!format || !safeUrl(file.url)) continue;
      css += `@font-face{font-family:'${f.family}';font-style:${file.style};font-weight:${file.weight};font-display:swap;src:url("${file.url}") format("${format}")}`;
    }
  }
  const has = (name: string) => FONT_FAMILY_RE.test(name) && theme.fonts.some((f) => f.family === name);
  const vars: string[] = [];
  if (has(theme.body_font)) vars.push(`--cms-font-body:${fontStack(theme.body_font)}`);
  if (has(theme.heading_font)) vars.push(`--cms-font-heading:${fontStack(theme.heading_font)}`);
  if (vars.length) css += `:root{${vars.join(";")}}`;
  return css;
}

export function relativeLuminance(hex: string): number {
  const [r, g, b] = [1, 3, 5].map((i) => {
    const v = parseInt(hex.slice(i, i + 2), 16) / 255;
    return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4;
  });
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}

export function contrastRatio(a: string, b: string): number {
  const x = relativeLuminance(a);
  const y = relativeLuminance(b);
  return (Math.max(x, y) + 0.05) / (Math.min(x, y) + 0.05);
}

/** A typical dark-theme card (Tailwind gray-800). A colour made readable on it stays readable on every darker surface. */
export const DARK_SURFACE = "#1f2937";

/** `color` moved toward white (dark `surface`) or black (light one) just far enough to reach `ratio`
 *  against it; unchanged when it already does, or when either is not a #rrggbb colour. */
export function readableOn(color: string, surface: string = DARK_SURFACE, ratio = 4.5): string {
  if (!HEX_RE.test(color) || !HEX_RE.test(surface) || contrastRatio(color, surface) >= ratio) return color;
  const target = contrastRatio("#ffffff", surface) >= contrastRatio("#000000", surface) ? 255 : 0;
  const rgb = [1, 3, 5].map((i) => parseInt(color.slice(i, i + 2), 16));
  const mix = (t: number) => "#" + rgb.map((c) => Math.round(c + (target - c) * t).toString(16).padStart(2, "0")).join("");
  let lo = 0;
  let hi = 1;
  for (let i = 0; i < 12; i++) {
    const mid = (lo + hi) / 2;
    if (contrastRatio(mix(mid), surface) >= ratio) hi = mid;
    else lo = mid;
  }
  return mix(hi);
}

/** Inline style for a client-chosen colour (ADR-0011): `prop` is the stored colour, and
 *  `--cms-color-dark` its readable variant, which cms-rich.css switches to on dark themes. */
export function colorCss(prop: "color" | "backgroundColor", color: string): Record<string, string> {
  return { "--cms-color-dark": readableOn(color), [prop]: `var(--cms-color, ${color})` };
}

export function recommendIconColors(
  theme: CmsTheme, surfaceName?: string,
): { color: ThemeColor; ok: boolean; ratio: number }[] {
  const named = surfaceName
    ? theme.surfaces.filter((s) => s.name.toLowerCase() === surfaceName.toLowerCase())
    : [];
  const surfaces = named.length ? named : theme.surfaces;
  return theme.colors
    .map((color) => {
      const ratio = surfaces.length ? Math.min(...surfaces.map((s) => contrastRatio(color.value, s.value))) : 21;
      return { color, ok: ratio >= 3, ratio };
    })
    .sort((a, b) => Number(b.ok) - Number(a.ok) || b.ratio - a.ratio);
}

/** `raw` lowercased when it is a #rrggbb colour, else "". */
export function readColorHex(raw: unknown): string {
  return typeof raw === "string" && HEX_RE.test(raw) ? raw.toLowerCase() : "";
}

export function readIcon(raw: unknown): CmsIconValue | null {
  if (!isObj(raw) || typeof raw.src !== "string" || !raw.src.startsWith("https://")) return null;
  return {
    src: raw.src,
    mode: raw.mode === "original" ? "original" : "tint",
    color: typeof raw.color === "string" ? raw.color : "",
    name: typeof raw.name === "string" ? raw.name : "",
  };
}
