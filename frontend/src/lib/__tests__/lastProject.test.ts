import { describe, it, expect, beforeEach } from "vitest";
import { getLastProjectSlug, setLastProjectSlug } from "../lastProject";

beforeEach(() => {
  window.localStorage.clear();
});

describe("lastProject", () => {
  it("returns null when nothing has been stored", () => {
    expect(getLastProjectSlug()).toBeNull();
  });

  it("round-trips the stored slug", () => {
    setLastProjectSlug("demo");
    expect(getLastProjectSlug()).toBe("demo");
  });

  it("overwrites the previous slug", () => {
    setLastProjectSlug("demo");
    setLastProjectSlug("other");
    expect(getLastProjectSlug()).toBe("other");
  });
});
