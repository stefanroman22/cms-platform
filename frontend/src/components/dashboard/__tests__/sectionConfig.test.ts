import { describe, it, expect } from "vitest";
import {
  PROJECT_SECTIONS,
  DEFAULT_VIEW,
  visibleSections,
  isAccessibleView,
} from "../sectionConfig";

describe("sectionConfig", () => {
  it("defines the four sections in order", () => {
    expect(PROJECT_SECTIONS.map((s) => s.key)).toEqual(["dashboard", "cms", "autofix", "settings"]);
  });

  it("default view is dashboard", () => {
    expect(DEFAULT_VIEW).toBe("dashboard");
  });

  it("hides admin-only sections from non-admins", () => {
    expect(visibleSections(false).map((s) => s.key)).toEqual(["dashboard", "cms", "autofix"]);
    expect(visibleSections(true).map((s) => s.key)).toEqual([
      "dashboard",
      "cms",
      "autofix",
      "settings",
    ]);
  });

  it("validates views against admin visibility", () => {
    expect(isAccessibleView("cms", false)).toBe(true);
    expect(isAccessibleView("settings", false)).toBe(false);
    expect(isAccessibleView("settings", true)).toBe(true);
    expect(isAccessibleView("bogus", true)).toBe(false);
    expect(isAccessibleView(null, true)).toBe(false);
  });
});
