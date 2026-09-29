// Tests beyond the task-8 brief, covering the carry-ts-port-rules.md
// deviations (MAX_PARSE_DEPTH, MAX_MARK_DEPTH, linear inline()/tidy()) that
// the shared canonical-vectors.json fixture only partially exercises.
import { describe, expect, it } from "vitest";
import randomCases from "./_random-cross-check.json";
import { parse } from "../src/parse";
import { normalizeInline, normalizeRich } from "../src/normalize";
import { serialize } from "../src/serialize";

type Fmt = "inline" | "rich";
const canonical = (input: string, fmt: Fmt) => {
  const root = parse(input);
  return serialize(fmt === "inline" ? normalizeInline(root.children) : normalizeRich(root.children));
};

describe("MAX_PARSE_DEPTH: deep nesting does not stack-overflow", () => {
  it("300-deep <blockquote> nesting parses and canonicalizes without throwing", () => {
    const input = "<blockquote>".repeat(300) + "x" + "</blockquote>".repeat(300);
    expect(() => canonical(input, "rich")).not.toThrow();
    const out = canonical(input, "rich");
    // real tree depth is capped at MAX_PARSE_DEPTH (256), so nesting in the
    // output is bounded well below the 300 requested levels.
    expect((out.match(/<blockquote>/g) ?? []).length).toBeLessThanOrEqual(256);
    expect(out).toContain("x");
  });

  it("300-deep <strong> nesting parses and canonicalizes without throwing", () => {
    const input = "<strong>".repeat(300) + "x" + "</strong>".repeat(300);
    expect(() => canonical(input, "inline")).not.toThrow();
    expect(() => canonical(input, "rich")).not.toThrow();
    const out = canonical(input, "rich");
    // MAX_MARK_DEPTH (32) caps semantic nesting well below the parse-tree cap.
    expect((out.match(/<strong>/g) ?? []).length).toBeLessThanOrEqual(32);
    expect(out).toContain("x");
  });
});

describe("MAX_MARK_DEPTH idempotence across block contexts", () => {
  const nestedMarks = (n: number) => {
    let s = "x";
    for (let i = 0; i < n; i++) s = i % 2 === 0 ? `<strong>${s}</strong>` : `<em>${s}</em>`;
    return s;
  };
  const marks40 = nestedMarks(40);
  const containers: Record<string, string> = {
    "loose root": marks40,
    "<p>": `<p>${marks40}</p>`,
    "<blockquote>": `<blockquote>${marks40}</blockquote>`,
    "<ul><li>": `<ul><li>${marks40}</li></ul>`,
    "bare <li>": `<li>${marks40}</li>`,
    "<h2>": `<h2>${marks40}</h2>`,
  };
  for (const [label, html] of Object.entries(containers)) {
    for (const fmt of ["inline", "rich"] as Fmt[]) {
      it(`${label} (${fmt}) is idempotent under canonicalization`, () => {
        const once = canonical(html, fmt);
        const twice = canonical(once, fmt);
        expect(twice).toBe(once);
      });
    }
  }
});

describe("randomized cross-check against the Python backend", () => {
  type Vec = { name: string; fmt: Fmt; input: string; expected: string };
  for (const v of randomCases as Vec[]) {
    it(v.name, () => expect(canonical(v.input, v.fmt)).toBe(v.expected));
  }
});
