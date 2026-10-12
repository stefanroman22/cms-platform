import { describe, expect, it } from "vitest";
import { fromStored, toStored } from "../serialize";

describe("toStored", () => {
  it.each([
    ["<p></p>", "rich", ""],
    ["<p></p><p><br></p>", "rich", ""],
    ["<p>&nbsp;</p>", "rich", ""],
    ["<p>a</p><p></p><p>b</p>", "rich", "<p>a</p><p></p><p>b</p>"],
    ["<p></p>", "inline", ""],
    ["<p>A &amp; <strong>B</strong></p>", "inline", "A &amp; <strong>B</strong>"],
    ["<p><br>x<br></p>", "inline", "x"],
    ["<p>a<br><br>b</p>", "inline", "a<br><br>b"],
  ])("%s (%s)", (html, mode, expected) =>
    expect(toStored(html, mode as "inline" | "rich")).toBe(expected)
  );

  it("canonicalizes: only href survives on a pasted <a> (target/rel/class/title stripped)", () => {
    expect(
      toStored(
        '<p><a href="https://x.ro" target="_blank" rel="noopener" class="c" title="t">x</a></p>',
        "rich"
      )
    ).toBe('<p><a href="https://x.ro">x</a></p>');
  });

  it("canonicalizes TipTap's styled spans (rgb, quoted family, spaced declarations)", () => {
    expect(
      toStored(
        '<p><span style="color: rgb(30, 90, 168); font-family: &quot;Open Sans&quot;; font-size: 1.25em">x</span></p>',
        "rich"
      )
    ).toBe(
      "<p><span style=\"color:#1e5aa8;font-family:'Open Sans';font-size:1.25em\">x</span></p>"
    );
    expect(toStored("<p><span style=\"font-family: 'Lora'\">x</span> y</p>", "inline")).toBe(
      "<span style=\"font-family:'Lora'\">x</span> y"
    );
  });

  it("canonicalizes inline mode the same way", () => {
    expect(
      toStored('<p><a href="https://x.ro" target="_blank" rel="noopener">x</a></p>', "inline")
    ).toBe('<a href="https://x.ro">x</a>');
  });
});

describe("fromStored", () => {
  it("wraps inline values in one paragraph", () =>
    expect(fromStored("A &amp; B", "inline")).toBe("<p>A &amp; B</p>"));
  it("passes rich HTML through", () => expect(fromStored("<p>x</p>", "rich")).toBe("<p>x</p>"));
  it("converts tag-free rich (legacy markdown)", () =>
    expect(fromStored("**x**", "rich")).toBe("<p><strong>x</strong></p>"));
  it("treats non-strings and blanks as empty", () => {
    expect(fromStored(undefined, "rich")).toBe("");
    expect(fromStored("  ", "inline")).toBe("");
  });
});
