import { describe, expect, it } from "vitest";
import { decodeEntities, parse } from "../src/parse";
import { safeHref } from "../src/href";
import { isHtml } from "../src/detect";

describe("decodeEntities", () => {
  it("decodes the basic and numeric entities exactly once", () => {
    expect(decodeEntities("&amp;amp; &lt; &gt; &quot; &#39; &apos; &nbsp; &#x1F600; &#65;")).toBe(
      "&amp; < > \" ' '   😀 A");
  });
  it("leaves unknown named entities literal", () => expect(decodeEntities("&bogus;")).toBe("&bogus;"));
  it("replaces invalid code points", () => expect(decodeEntities("&#xD800;&#0;")).toBe("��"));
});

describe("parse", () => {
  it("keeps a literal less-than", () => expect(parse("a < b").children).toEqual(["a < b"]));
  it("reads quoted attributes containing >", () => {
    const a = parse('<a href="https://x.ro/?q=a>b">t</a>').children[0];
    expect(a).toMatchObject({ tag: "a", href: "https://x.ro/?q=a>b" });
  });
  it("drops raw-text elements even when unclosed", () => expect(parse("x<script>alert(1)").children).toEqual(["x"]));
  it("never produces non-allow-listed tags", () => {
    const tags: string[] = [];
    const walk = (n: unknown) => {
      if (typeof n !== "string") {
        const e = n as { tag: string; children: unknown[] };
        tags.push(e.tag);
        e.children.forEach(walk);
      }
    };
    walk(parse('<div><img src=x onerror=1><iframe src=x></iframe><table><tr><td>a</td></tr></table><span>b</span></div>'));
    const allowed = ["#root", "p", "br", "hr", "strong", "em", "u", "s", "a", "ul", "ol", "li", "h2", "h3", "h4", "blockquote"];
    expect(tags.every((t) => allowed.includes(t))).toBe(true);
  });
});

describe("safeHref", () => {
  it.each([
    ["https://a.ro", "https://a.ro"], ["mailto:a@b.ro", "mailto:a@b.ro"], ["tel:+40", "tel:+40"],
    ["#x", "#x"], ["/p", "/p"], ["//e.com", null], ["/\\e.com", null], ["javascript:x", null],
    ["java\u0000script:x", null], [" JAVASCRIPT:x", null], ["data:x", null], ["", null], [null, null],
  ])("%s", (raw, expected) => expect(safeHref(raw as string | null)).toBe(expected));
});

describe("isHtml", () => {
  it.each([["<p>x</p>", true], ["<BR/>", true], ["a < b", false], ["<abbr>", false], ["Tom &amp; Jerry", false]])(
    "%s", (v, e) => expect(isHtml(v as string)).toBe(e));
});
