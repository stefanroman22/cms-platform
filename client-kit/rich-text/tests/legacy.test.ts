import { describe, expect, it } from "vitest";
import vectors from "../fixtures/legacy-vectors.json";
import { legacyToHtml } from "../src/legacy";

type Vec = { name: string; fmt: "inline" | "rich"; input: string; expected: string };
describe("legacy vectors (shared with backend)", () => {
  for (const v of vectors as Vec[]) it(v.name, () => expect(legacyToHtml(v.input, v.fmt)).toBe(v.expected));
});

describe("legacyToHtml edge cases (verified against backend legacy_to_html)", () => {
  it("non-string input returns empty string", () => {
    // @ts-expect-error deliberately passing a non-string to mirror Python's `not isinstance(text, str)`
    expect(legacyToHtml(null, "rich")).toBe("");
    // @ts-expect-error same
    expect(legacyToHtml(undefined, "inline")).toBe("");
  });
  it("a Python-only whitespace char (\\x1c, file separator) still separates a heading marker from its text", () => {
    // Python's HEADING_RE `\s+` matches \x1c; so should the port (PY_WS), unlike JS's native \s.
    expect(legacyToHtml("##\x1cTitle", "rich")).toBe("<h2>Title</h2>");
  });
  it("a Python-only whitespace char (\\x1c) still separates a list marker from its item text", () => {
    expect(legacyToHtml("-\x1citem", "rich")).toBe("<ul><li><p>item</p></li></ul>");
  });
  it("U+FEFF (JS-only whitespace, not Python whitespace) is ordinary bold content, not a boundary", () => {
    // Python's \S (content boundary for **bold**) includes U+FEFF since Python's \s excludes it;
    // JS's native \s would incorrectly treat U+FEFF as whitespace and break the match.
    expect(legacyToHtml("**﻿bold﻿**", "rich")).toBe("<p><strong>﻿bold﻿</strong></p>");
  });
});
