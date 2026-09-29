import { describe, expect, it } from "vitest";
import { normalizeLinkInput } from "../linkInput";

describe("normalizeLinkInput", () => {
  it.each([
    ["https://a.ro/x", "https://a.ro/x"],
    ["example.com", "https://example.com"],
    ["www.example.com/p?q=1", "https://www.example.com/p?q=1"],
    ["name@firm.ro", "mailto:name@firm.ro"],
    ["+40 721 000 000", "tel:+40721000000"],
    ["/contact", "/contact"],
    ["#services", "#services"],
    ["mailto:a@b.ro", "mailto:a@b.ro"],
    ["javascript:alert(1)", null],
    ["//evil.com", null],
    ["", null],
    ["just words", null],
  ])("%s", (raw, expected) => expect(normalizeLinkInput(raw)).toBe(expected));
});
