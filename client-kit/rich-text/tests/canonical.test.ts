import { describe, expect, it } from "vitest";
import vectors from "../fixtures/canonical-vectors.json";
import { parse } from "../src/parse";
import { normalizeInline, normalizeRich } from "../src/normalize";
import { serialize } from "../src/serialize";

type Vec = { name: string; fmt: "inline" | "rich"; input: string; expected: string };

const canonical = (input: string, fmt: "inline" | "rich") => {
  const root = parse(input);
  return serialize(fmt === "inline" ? normalizeInline(root.children) : normalizeRich(root.children));
};

describe("canonical vectors (shared with backend)", () => {
  for (const v of vectors as Vec[]) {
    it(v.name, () => expect(canonical(v.input, v.fmt)).toBe(v.expected));
    it(`${v.name} (idempotent)`, () => {
      const once = canonical(v.input, v.fmt);
      expect(canonical(once, v.fmt)).toBe(once);
    });
  }
});
