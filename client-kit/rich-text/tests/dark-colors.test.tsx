import { describe, expect, it } from "vitest";
import { renderToString } from "react-dom/server";
import { CmsIcon } from "../src/CmsIcon";
import { RichText } from "../src/RichText";
import { splitRichWords } from "../src/splitRichWords";
import { DARK_SURFACE, colorCss, contrastRatio, readableOn } from "../src/theme";

describe("readableOn", () => {
  it("keeps a colour that already reaches 4.5:1 on the dark surface", () => {
    expect(readableOn("#49d4fc")).toBe("#49d4fc");
    expect(readableOn("#ffffff")).toBe("#ffffff");
  });
  it("lightens a dark blue just enough to reach 4.5:1 (itgs body text #2861e6)", () => {
    const out = readableOn("#2861e6");
    expect(out).not.toBe("#2861e6");
    expect(contrastRatio(out, DARK_SURFACE)).toBeGreaterThanOrEqual(4.5);
    expect(contrastRatio(out, DARK_SURFACE)).toBeLessThan(4.7); // the smallest step, not white
    // Still a blue: blue stays the strongest channel.
    const [r, g, b] = [1, 3, 5].map((i) => parseInt(out.slice(i, i + 2), 16));
    expect(b).toBeGreaterThan(r);
    expect(b).toBeGreaterThan(g);
  });
  it("is readable on every darker surface too", () => {
    const out = readableOn("#2861e6");
    for (const s of ["#0b1322", "#13233f", "#111827", "#000000"]) {
      expect(contrastRatio(out, s)).toBeGreaterThanOrEqual(4.5);
    }
  });
  it("darkens toward black on a light surface", () => {
    const out = readableOn("#ffd54f", "#ffffff");
    expect(contrastRatio(out, "#ffffff")).toBeGreaterThanOrEqual(4.5);
    expect(parseInt(out.slice(1, 3), 16)).toBeLessThan(0xff);
  });
  it("honours a custom ratio", () =>
    expect(contrastRatio(readableOn("#2861e6", DARK_SURFACE, 7), DARK_SURFACE)).toBeGreaterThanOrEqual(7));
  it("returns invalid input unchanged", () => {
    expect(readableOn("red")).toBe("red");
    expect(readableOn("#123")).toBe("#123");
    expect(readableOn("#2861e6", "nope")).toBe("#2861e6");
  });
});

describe("colorCss", () => {
  it("keeps the stored colour as the light value and carries the dark variant", () => {
    expect(colorCss("color", "#2861e6")).toEqual({
      "--cms-color-dark": readableOn("#2861e6"),
      color: "var(--cms-color, #2861e6)",
    });
  });
  it("a readable colour has itself as the dark variant", () =>
    expect(colorCss("backgroundColor", "#49d4fc")).toEqual({
      "--cms-color-dark": "#49d4fc",
      backgroundColor: "var(--cms-color, #49d4fc)",
    }));
});

describe("dark variants in rendered markup", () => {
  const dark = readableOn("#2861e6");
  it("RichText styled span", () => {
    const html = renderToString(<RichText value={'<span style="color:#2861e6">x</span>'} format="inline" />);
    expect(html).toContain(`--cms-color-dark:${dark}`);
    expect(html).toContain("color:var(--cms-color, #2861e6)");
  });
  it("splitRichWords styled span", () => {
    const [w] = splitRichWords('<span style="color:#2861e6">x</span>');
    expect(renderToString(<>{w.node}</>)).toContain(`--cms-color-dark:${dark}`);
  });
  it("tinted icon with a colour", () => {
    const html = renderToString(
      <CmsIcon icon={{ src: "https://x.co/i.svg", mode: "tint", color: "#2861e6", name: "i" }} />);
    expect(html).toContain(`--cms-color-dark:${dark}`);
    expect(html).toContain("background-color:var(--cms-color, #2861e6)");
  });
  it("tinted icon without a colour follows the text colour", () =>
    expect(renderToString(<CmsIcon icon={{ src: "https://x.co/i.svg", mode: "tint", color: "", name: "i" }} />))
      .toContain("background-color:currentColor"));
});
