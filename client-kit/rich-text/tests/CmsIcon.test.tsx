import { describe, expect, it } from "vitest";
import { render } from "@testing-library/react";
import { CmsIcon } from "../src/CmsIcon";
import type { CmsIconValue } from "../src/theme";

const icon = (over: Partial<CmsIconValue> = {}): CmsIconValue => ({
  src: "https://x.co/i.svg", mode: "tint", color: "", name: "i", ...over,
});
const root = (ui: React.ReactElement) => render(ui).container;

describe("CmsIcon", () => {
  it("tint svg renders masked span with currentColor when no colour", () => {
    const el = root(<CmsIcon icon={icon()} size={24} label="Phone" />).firstElementChild as HTMLElement;
    expect(el.tagName).toBe("SPAN");
    expect(el.getAttribute("role")).toBe("img");
    expect(el.getAttribute("aria-label")).toBe("Phone");
    expect(el.className).toContain("cms-icon");
    expect(el.style.backgroundColor).toBe("currentcolor");
    expect(el.style.maskImage || el.style.webkitMaskImage).toContain("https://x.co/i.svg");
  });
  it("uses the given colour and aria-hidden without label", () => {
    const el = root(<CmsIcon icon={icon({ color: "#112233" })} />).firstElementChild as HTMLElement;
    expect(el.style.backgroundColor).toBe("rgb(17, 34, 51)");
    expect(el.getAttribute("aria-hidden")).toBe("true");
    expect(el.getAttribute("role")).toBeNull();
  });
  it("original mode renders img", () => {
    const el = root(<CmsIcon icon={icon({ mode: "original" })} size={16} />).firstElementChild!;
    expect(el.tagName).toBe("IMG");
    expect(el.getAttribute("loading")).toBe("lazy");
    expect(el.getAttribute("alt")).toBe("");
  });
  it("non-svg src renders img", () => {
    expect(root(<CmsIcon icon={icon({ src: "https://x.co/i.png?v=1" })} />).firstElementChild!.tagName).toBe("IMG");
  });
  it("img takes a numeric size as width/height attributes", () => {
    const el = root(<CmsIcon icon={icon({ mode: "original" })} size={16} />).firstElementChild as HTMLImageElement;
    expect(el.getAttribute("width")).toBe("16");
    expect(el.getAttribute("height")).toBe("16");
    expect(el.style.width).toBe("");
  });
  it("img takes a string size (and the 1em default) as CSS, never as an attribute", () => {
    for (const [size, css] of [[undefined, "1em"], ["2rem", "2rem"]] as const) {
      const el = root(<CmsIcon icon={icon({ mode: "original" })} size={size} />).firstElementChild as HTMLImageElement;
      expect(el.hasAttribute("width")).toBe(false);
      expect(el.hasAttribute("height")).toBe(false);
      expect(el.style.width).toBe(css);
      expect(el.style.height).toBe(css);
    }
  });
  it("svg with a query string still tints", () => {
    expect(root(<CmsIcon icon={icon({ src: "https://x.co/i.svg?v=1" })} />).firstElementChild!.tagName).toBe("SPAN");
  });
  it("unsafe src and null render the fallback", () => {
    expect(root(<CmsIcon icon={icon({ src: 'https://x.co/a")x.svg' })} fallback={<b>fb</b>} />).innerHTML).toBe("<b>fb</b>");
    expect(root(<CmsIcon icon={null} fallback={<b>fb</b>} />).innerHTML).toBe("<b>fb</b>");
    expect(root(<CmsIcon icon={null} />).innerHTML).toBe("");
  });
});
