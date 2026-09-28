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
