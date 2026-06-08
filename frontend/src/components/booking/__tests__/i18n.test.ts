import { describe, it, expect } from "vitest";
import { tw, STRINGS } from "../i18n";

describe("tw", () => {
  it("returns the English string for a known key", () => {
    expect(tw("en", "schedule")).toBe(STRINGS.en.schedule);
  });

  it("falls back to English for an unknown locale", () => {
    expect(tw("xx", "schedule")).toBe(STRINGS.en.schedule);
  });

  it("falls back to English when locale is empty string", () => {
    expect(tw("", "back")).toBe(STRINGS.en.back);
  });

  it("covers all keys defined in STRINGS.en", () => {
    const keys = Object.keys(STRINGS.en) as Array<keyof (typeof STRINGS)["en"]>;
    for (const key of keys) {
      expect(tw("en", key)).toBe(STRINGS.en[key]);
    }
  });
});
