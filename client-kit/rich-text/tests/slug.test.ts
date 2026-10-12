import { describe, expect, it } from "vitest";
import vectors from "../fixtures/slug-vectors.json";
import { MAX_SLUG_LENGTH, slugify } from "../src/index";

type Vec = { name: string; input: string; expected: string };
describe("slug vectors (shared with backend)", () => {
  for (const v of vectors as Vec[]) it(v.name, () => expect(slugify(v.input)).toBe(v.expected));
});

describe("slugify", () => {
  it("is idempotent and bounded", () => {
    for (const v of vectors as Vec[]) {
      const out = slugify(v.input);
      expect(slugify(out)).toBe(out);
      expect(out.length).toBeLessThanOrEqual(MAX_SLUG_LENGTH);
    }
  });
  it("returns an empty string for non-string input, like the backend", () => {
    // @ts-expect-error deliberately passing a non-string to mirror Python's `not isinstance(text, str)`
    expect(slugify(null)).toBe("");
    // @ts-expect-error same
    expect(slugify(3)).toBe("");
  });
});
