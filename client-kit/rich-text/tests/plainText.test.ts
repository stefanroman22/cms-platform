import { describe, expect, it } from "vitest";
import { plainText } from "../src/plainText";

describe("plainText", () => {
  it("strips markup and decodes entities", () =>
    expect(plainText("<p>Tom &amp; <strong>Jerry</strong></p><p>2nd</p>", { format: "rich" })).toBe("Tom & Jerry 2nd"));
  it("inline breaks become spaces", () => expect(plainText("a<br>b")).toBe("a b"));
  it("keeps line breaks when asked", () =>
    expect(plainText("<p>a</p><ul><li><p>b</p></li></ul>", { format: "rich", keepLineBreaks: true })).toBe("a\nb"));
  it("converts legacy rich markdown first", () => expect(plainText("**Hi** there", { format: "rich" })).toBe("Hi there"));
  it("handles empty and non-strings", () => {
    expect(plainText("")).toBe("");
    expect(plainText(undefined)).toBe("");
    expect(plainText(null)).toBe("");
  });
  it("nbsp becomes a normal space", () => expect(plainText("a&nbsp;b")).toBe("a b"));
});

describe("plainText matches backend plain_text (values verified via python -c)", () => {
  it("only leaf p/h2-h4 emit a boundary; ul/ol/li/blockquote just recurse (carry rule 6)", () =>
    expect(
      plainText("<h2>Title</h2><blockquote><p>Quoted</p><ul><li><p>a</p><p>b</p></li></ul></blockquote>", {
        format: "rich",
        keepLineBreaks: true,
      })
    ).toBe("Title\nQuoted\na\nb"));
  it("br/hr inside a list item become line breaks under keepLineBreaks, and a blank line from the container-then-hr gap survives", () =>
    expect(
      plainText("<ul><li><p>one<br>two</p></li></ul><hr><p>three</p>", { format: "rich", keepLineBreaks: true })
    ).toBe("one\ntwo\n\nthree"));
  it("without keepLineBreaks, every boundary collapses to a single space", () =>
    expect(plainText("<h3>Title</h3><ul><li><p>a</p></li><li><p>b</p></li></ul><p>c</p>", { format: "rich" })).toBe(
      "Title a b c"
    ));
  it("a Python-only whitespace char (\\x1c) collapses to a space like any other run", () =>
    expect(plainText("a\x1cb")).toBe("a b"));
  it("empty rich value with only whitespace/markup returns empty string", () =>
    expect(plainText("<p>   </p>", { format: "rich" })).toBe(""));
});
