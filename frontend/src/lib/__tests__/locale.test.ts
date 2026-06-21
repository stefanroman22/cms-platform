import { describe, it, expect } from "vitest";
import {
  resolveLocaleFromCountry,
  stripLocale,
  hasLocalePrefix,
  isLocale,
  localizePath,
  DEFAULT_LOCALE,
} from "@/lib/locale";

describe("resolveLocaleFromCountry", () => {
  it("maps NL→nl, RO→ro", () => {
    expect(resolveLocaleFromCountry("NL")).toBe("nl");
    expect(resolveLocaleFromCountry("RO")).toBe("ro");
  });
  it("maps only NL→nl and RO→ro; every other country → English", () => {
    expect(resolveLocaleFromCountry("BE")).toBe("en");
    expect(resolveLocaleFromCountry("MD")).toBe("en");
    expect(resolveLocaleFromCountry("DE")).toBe("en");
    expect(resolveLocaleFromCountry("GB")).toBe("en");
  });
  it("is case-insensitive", () => {
    expect(resolveLocaleFromCountry("nl")).toBe("nl");
  });
  it("falls back to English for unknown/empty", () => {
    expect(resolveLocaleFromCountry("US")).toBe(DEFAULT_LOCALE);
    expect(resolveLocaleFromCountry(null)).toBe("en");
    expect(resolveLocaleFromCountry(undefined)).toBe("en");
    expect(resolveLocaleFromCountry("")).toBe("en");
  });
});

describe("stripLocale", () => {
  it("removes a leading locale segment", () => {
    expect(stripLocale("/nl/about")).toBe("/about");
    expect(stripLocale("/ro/team")).toBe("/team");
  });
  it("returns / for a bare locale root", () => {
    expect(stripLocale("/nl")).toBe("/");
  });
  it("leaves unprefixed paths untouched", () => {
    expect(stripLocale("/about")).toBe("/about");
    expect(stripLocale("/")).toBe("/");
  });
});

describe("localizePath", () => {
  it("prefixes non-default locales", () => {
    expect(localizePath("/contact", "nl")).toBe("/nl/contact");
    expect(localizePath("/contact", "ro")).toBe("/ro/contact");
  });
  it("leaves the default locale unprefixed (as-needed)", () => {
    expect(localizePath("/contact", "en")).toBe("/contact");
  });
  it("leaves non-internal hrefs untouched", () => {
    expect(localizePath("https://x.com", "ro")).toBe("https://x.com");
    expect(localizePath("#pricing", "nl")).toBe("#pricing");
  });
});

describe("hasLocalePrefix / isLocale", () => {
  it("detects a locale prefix", () => {
    expect(hasLocalePrefix("/nl/about")).toBe(true);
    expect(hasLocalePrefix("/about")).toBe(false);
    expect(hasLocalePrefix("/")).toBe(false);
  });
  it("isLocale guards membership", () => {
    expect(isLocale("ro")).toBe(true);
    expect(isLocale("de")).toBe(false);
    expect(isLocale(null)).toBe(false);
  });
});
