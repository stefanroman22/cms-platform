import { afterEach, describe, expect, it } from "vitest";
import { cleanup, render } from "@testing-library/react";
import { ThemeStyles } from "../src/ThemeStyles";
import { googleFontsHref, themeCss, type CmsTheme } from "../src/theme";

const theme = (over: Partial<CmsTheme> = {}): CmsTheme => ({
  colors: [], surfaces: [], fonts: [], body_font: "", heading_font: "", ...over,
});
const OPEN_SANS = { family: "Open Sans", source: "google" as const, weights: [400, 700], italic: false };
const LORA = { family: "Lora", source: "google" as const, weights: [], italic: true };
const BRAND = {
  family: "Brand", source: "upload" as const,
  files: [{ url: "https://x.co/brand.woff2", weight: 400, style: "normal" as const }],
};

// React 19 hoists <link> into <head> and keeps it there after unmount, so query
// the whole document and empty <head> between tests.
const links = (rel: string) => Array.from(document.querySelectorAll<HTMLLinkElement>(`link[rel="${rel}"]`));

afterEach(() => {
  cleanup();
  document.head.innerHTML = "";
});

describe("ThemeStyles", () => {
  it("renders nothing for a null theme", () => {
    const { container } = render(<ThemeStyles theme={null} />);
    expect(container.innerHTML).toBe("");
    expect(document.querySelectorAll("link")).toHaveLength(0);
  });

  it("emits the preconnects and one stylesheet per Google font", () => {
    render(<ThemeStyles theme={theme({ fonts: [OPEN_SANS, BRAND, LORA] })} />);
    expect(links("preconnect").map((l) => l.getAttribute("href"))).toEqual([
      "https://fonts.googleapis.com", "https://fonts.gstatic.com",
    ]);
    expect(links("stylesheet").map((l) => l.getAttribute("href"))).toEqual([
      googleFontsHref(OPEN_SANS), googleFontsHref(LORA),
    ]);
  });

  it("emits no Google preconnect without a Google font", () => {
    render(<ThemeStyles theme={theme({ fonts: [BRAND, { family: "Arial", source: "system" }] })} />);
    expect(links("preconnect")).toHaveLength(0);
    expect(links("stylesheet")).toHaveLength(0);
  });

  it("writes the theme CSS into a <style>", () => {
    const t = theme({ fonts: [BRAND, OPEN_SANS], body_font: "Brand", heading_font: "Open Sans" });
    render(<ThemeStyles theme={t} />);
    const style = document.querySelector("style");
    expect(style?.textContent).toBe(themeCss(t));
    expect(style?.textContent).toContain("@font-face{font-family:'Brand'");
    expect(style?.textContent).toContain(":root{--cms-font-body:'Brand', system-ui, sans-serif;--cms-font-heading:'Open Sans', system-ui, sans-serif}");
  });
});
