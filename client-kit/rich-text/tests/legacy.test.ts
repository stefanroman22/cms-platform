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
    const bom = String.fromCharCode(0xfeff);
    expect(legacyToHtml(`**${bom}bold${bom}**`, "rich")).toBe(`<p><strong>${bom}bold${bom}</strong></p>`);
  });

  // Fix round 1 finding: JS `.` (without the `s`/dotAll flag) excludes the
  // LINE SEPARATOR and PARAGRAPH SEPARATOR code points, but Python's `.`
  // matches them (Python only excludes the newline). Since `clean()` only
  // splits raw text on the newline character, a line can still contain one
  // of these separators reaching BOLD/STRIKE/EM/HEADING/UL/OL/QUOTE_RE's
  // `.`-based capture groups. Without the `s` flag, these regexes fail to
  // match at all on such a line, so e.g. a heading marker followed by text
  // containing that separator fell through to being treated as an ordinary
  // paragraph instead of a heading. Built via fromCodePoint (not a literal
  // escape) so the separator can't be mistaken for an ordinary line break by
  // anything re-splitting this source file on line terminators. All four
  // cases also appear as vectors in the shared fixture.
  const LINE_SEP = String.fromCodePoint(0x2028);
  const PARA_SEP = String.fromCodePoint(0x2029);
  it("a line-separator code point inside heading/bold/quote/list text does not break the match (matches backend)", () => {
    expect(legacyToHtml(`## A${LINE_SEP}B`, "rich")).toBe(`<h2>A${LINE_SEP}B</h2>`);
    expect(legacyToHtml(`**a${LINE_SEP}b**`, "rich")).toBe(`<p><strong>a${LINE_SEP}b</strong></p>`);
    expect(legacyToHtml(`>x${LINE_SEP}y`, "rich")).toBe(`<blockquote><p>x${LINE_SEP}y</p></blockquote>`);
    expect(legacyToHtml(`- a${LINE_SEP}b`, "rich")).toBe(`<ul><li><p>a${LINE_SEP}b</p></li></ul>`);
  });
  it("a paragraph-separator code point behaves the same way as the line separator for the same regexes", () => {
    expect(legacyToHtml(`## A${PARA_SEP}B`, "rich")).toBe(`<h2>A${PARA_SEP}B</h2>`);
    expect(legacyToHtml(`*a${PARA_SEP}b*`, "rich")).toBe(`<p><em>a${PARA_SEP}b</em></p>`);
  });
});
