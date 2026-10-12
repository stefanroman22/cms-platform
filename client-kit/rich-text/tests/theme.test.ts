import { describe, expect, it } from "vitest";
import {
  contrastRatio, fontStack, googleFontsHref, readIcon, readTheme, recommendIconColors, themeCss,
  type CmsTheme,
} from "../src/theme";

describe("googleFontsHref", () => {
  it("italic", () => {
    expect(googleFontsHref({ family: "Open Sans", weights: [700, 400, 400], italic: true })).toBe(
      "https://fonts.googleapis.com/css2?family=Open+Sans:ital,wght@0,400;0,700;1,400;1,700&display=swap");
  });
  it("non-italic", () => {
    expect(googleFontsHref({ family: "Open Sans", weights: [400, 700], italic: false })).toBe(
      "https://fonts.googleapis.com/css2?family=Open+Sans:wght@400;700&display=swap");
  });
  it("empty weights", () => {
    expect(googleFontsHref({ family: "Lora", weights: [], italic: false })).toBe(
      "https://fonts.googleapis.com/css2?family=Lora&display=swap");
  });
});

describe("fontStack", () => {
  it("quotes the family with default and custom fallback", () => {
    expect(fontStack("Lora")).toBe("'Lora', system-ui, sans-serif");
    expect(fontStack("Lora", "serif")).toBe("'Lora', serif");
  });
  it("drops a family that fails FONT_FAMILY_RE and keeps only the fallback", () => {
    expect(fontStack("a';}body{x:y")).toBe("system-ui, sans-serif");
    expect(fontStack("", "serif")).toBe("serif");
  });
});

const theme = (over: Partial<CmsTheme> = {}): CmsTheme => ({
  colors: [], surfaces: [], fonts: [], body_font: "", heading_font: "", ...over,
});

describe("themeCss", () => {
  const up = (url: string) => ({
    family: "Brand", source: "upload" as const, files: [{ url, weight: 400, style: "normal" as const }],
  });
  it("emits @font-face for uploads and vars only for present fonts", () => {
    const css = themeCss(theme({ fonts: [up("https://x.co/a.woff2")], body_font: "Brand", heading_font: "Missing" }));
    expect(css).toContain("@font-face");
    expect(css).toContain('format("woff2")');
    expect(css).toContain('url("https://x.co/a.woff2")');
    expect(css).toContain("--cms-font-body:'Brand', system-ui, sans-serif");
    expect(css).not.toContain("--cms-font-heading");
  });
  it("skips http and injection attempts", () => {
    for (const u of [
      "http://x.co/a.woff2", 'https://x.co/a")}body{x:y.woff2', "https://x.co/a b.woff2", "https://x.co/a(1).woff2",
      "https://x.co/a</style>.woff2", "https://x.co/<a>.woff2",
    ]) {
      expect(themeCss(theme({ fonts: [up(u)] }))).not.toContain("@font-face");
    }
  });
  it("skips a font whose family fails FONT_FAMILY_RE (no @font-face, no variable)", () => {
    const bad = "x';}</style><script>";
    const css = themeCss(theme({
      fonts: [{ ...up("https://x.co/a.woff2"), family: bad }, { family: bad, source: "system" }],
      body_font: bad, heading_font: bad,
    }));
    expect(css).toBe("");
  });
});

describe("readTheme", () => {
  it("returns null for undefined", () => expect(readTheme(undefined)).toBeNull());
  it("drops invalid entries", () => {
    const t = readTheme({
      colors: [{ name: "bad", value: "red" }, { name: "ok", value: "#112233" }],
      surfaces: [],
      fonts: [{ family: "Bad;Font", source: "system" }, { family: "Arial", source: "system" }],
      body_font: "Arial", heading_font: "",
    });
    expect(t?.colors).toEqual([{ name: "ok", value: "#112233" }]);
    expect(t?.fonts).toEqual([{ family: "Arial", source: "system" }]);
  });
  it("returns null when nothing is usable", () => {
    expect(readTheme({ colors: [{ name: "x", value: "red" }], fonts: [], surfaces: [] })).toBeNull();
  });
});

describe("contrast", () => {
  it("black/white is 21", () => expect(contrastRatio("#ffffff", "#000000")).toBe(21));
  it("recommendIconColors sorts ok first and flags low contrast", () => {
    const t = theme({
      colors: [{ name: "cyan", value: "#49d4fc" }, { name: "white", value: "#ffffff" }],
      surfaces: [{ name: "blue", value: "#3a70a9" }],
    });
    const r = recommendIconColors(t, "blue");
    expect(r.map((x) => x.color.name)).toEqual(["white", "cyan"]);
    expect(r[0].ok).toBe(true);
    expect(r[1].ok).toBe(false);
    expect(r[1].ratio.toFixed(2)).toBe("2.97");
  });
  it("unknown surface name falls back to all surfaces; no surfaces gives 21", () => {
    const t = theme({ colors: [{ name: "cyan", value: "#49d4fc" }], surfaces: [{ name: "blue", value: "#3a70a9" }] });
    expect(recommendIconColors(t, "nope")[0].ratio.toFixed(2)).toBe("2.97");
    expect(recommendIconColors(theme({ colors: t.colors }))[0].ratio).toBe(21);
  });
});

describe("readIcon", () => {
  it("requires an https src", () => {
    expect(readIcon({ src: "http://x/a.svg", mode: "tint", color: "", name: "a" })).toBeNull();
    expect(readIcon(null)).toBeNull();
    expect(readIcon({ src: "https://x/a.svg", mode: "tint", color: "#fff000", name: "a" })).toEqual(
      { src: "https://x/a.svg", mode: "tint", color: "#fff000", name: "a" });
  });
});
