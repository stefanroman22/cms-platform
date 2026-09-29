// Fix round 1 (code review findings):
// 1. Whitespace set parity with Python's str.strip() (no-arg form) — JS
//    String.prototype.trim() disagrees with Python's str.isspace() on U+FEFF
//    (JS: whitespace: Python: not) and \x1c-\x1f / \x85 (Python: whitespace,
//    JS: not). See src/whitespace.ts's pyStrip().
// 2. The tag tokenizer in src/parse.ts used to backtrack the tag regex from
//    every failing `<`, making "<b".repeat(50000)-style input quadratic.
import { describe, expect, it } from "vitest";
import { parse } from "../src/parse";
import { normalizeInline, normalizeRich } from "../src/normalize";
import { serialize } from "../src/serialize";
import { safeHref } from "../src/href";

type Fmt = "inline" | "rich";
const canonical = (input: string, fmt: Fmt) => {
  const root = parse(input);
  return serialize(fmt === "inline" ? normalizeInline(root.children) : normalizeRich(root.children));
};

describe("whitespace parity with Python str.strip() (no-arg form)", () => {
  // Each case below was run against the real backend
  // (backend/auth_service/services/rich_text.py) to confirm the expected
  // value; see task-8-report.md's fix-round-1 section for the commands and
  // raw output. The three canonical-transform cases are also pinned in the
  // shared fixture (client-kit/rich-text/fixtures/canonical-vectors.json:
  // "BOM paragraph is not empty", "BOM inside mark is not empty", "BOM
  // inline edge is not trimmed") and are exercised there via
  // canonical.test.ts; they're repeated here by name for direct traceability
  // to this fix.
  it("a lone U+FEFF paragraph is not empty (Python does not treat U+FEFF as whitespace)", () => {
    expect(canonical("<p>﻿</p><p>y</p>", "rich")).toBe("<p>﻿</p><p>y</p>");
  });
  it("a lone U+FEFF mark is not empty", () => {
    expect(canonical("<p><strong>﻿</strong>x</p>", "rich")).toBe("<p><strong>﻿</strong>x</p>");
  });
  it("a leading U+FEFF is not trimmed as an inline edge", () => {
    expect(canonical("﻿<br>y", "inline")).toBe("﻿<br>y");
  });

  it("safeHref: a leading U+FEFF is NOT stripped (Python: null)", () => {
    expect(safeHref("﻿https://a.ro")).toBe(null);
  });
  it("safeHref: a leading U+0085 (NEL) IS stripped (Python: safe)", () => {
    expect(safeHref("\x85https://a.ro")).toBe("https://a.ro");
  });
});

describe("MAX_PARSE_DEPTH-adjacent: tag tokenizer stays O(n), no backtracking blowup", () => {
  const withinBudget = (fn: () => void, budgetMs = 1000) => {
    const start = performance.now();
    fn();
    const elapsed = performance.now() - start;
    expect(elapsed).toBeLessThan(budgetMs);
  };

  it('"<b".repeat(50000) completes fast and yields text only', () => {
    const input = "<b".repeat(50000);
    let root: ReturnType<typeof parse> | undefined;
    withinBudget(() => { root = parse(input); });
    expect(root!.children.every((c) => typeof c === "string")).toBe(true);
  });

  it('"<a a".repeat(25000) completes fast and yields text only', () => {
    const input = "<a a".repeat(25000);
    let root: ReturnType<typeof parse> | undefined;
    withinBudget(() => { root = parse(input); });
    expect(root!.children.every((c) => typeof c === "string")).toBe(true);
  });

  it('("<b".repeat(50000) + \'">\') completes fast and yields text only', () => {
    const input = "<b".repeat(50000) + '">';
    let root: ReturnType<typeof parse> | undefined;
    withinBudget(() => { root = parse(input); });
    expect(root!.children.every((c) => typeof c === "string")).toBe(true);
  });

  it('"a <b" (no space before b) keeps the literal tag-soup as text', () => {
    expect(parse("a <b").children).toEqual(["a <b"]);
  });

  it("existing vectors still parse well-formed tags correctly (quoted > inside href)", () => {
    const a = parse('<a href="https://x.ro/?q=a>b">t</a>').children[0];
    expect(a).toMatchObject({ tag: "a", href: "https://x.ro/?q=a>b" });
  });
});
