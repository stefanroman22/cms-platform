import { describe, it, expect } from "vitest";
import {
  PROJECT_SECTIONS,
  DEFAULT_VIEW,
  visibleSections,
  isAccessibleView,
} from "../sectionConfig";

describe("sectionConfig", () => {
  it("defines the five sections in order", () => {
    expect(PROJECT_SECTIONS.map((s) => s.key)).toEqual([
      "dashboard",
      "cms",
      "autofix",
      "bookings",
      "settings",
    ]);
  });

  it("default view is dashboard", () => {
    expect(DEFAULT_VIEW).toBe("dashboard");
  });

  it("hides admin-only sections from non-admins", () => {
    // Without bookingEnabled cap, non-admins see dashboard/cms/autofix only
    expect(visibleSections(false).map((s) => s.key)).toEqual(["dashboard", "cms", "autofix"]);
    // Admins always see all sections including bookings and settings
    expect(visibleSections(true).map((s) => s.key)).toEqual([
      "dashboard",
      "cms",
      "autofix",
      "bookings",
      "settings",
    ]);
  });

  it("shows bookings to non-admins when bookingEnabled cap is true", () => {
    expect(visibleSections(false, { bookingEnabled: true }).map((s) => s.key)).toEqual([
      "dashboard",
      "cms",
      "autofix",
      "bookings",
    ]);
  });

  it("validates views against admin visibility", () => {
    expect(isAccessibleView("cms", false)).toBe(true);
    expect(isAccessibleView("settings", false)).toBe(false);
    expect(isAccessibleView("settings", true)).toBe(true);
    expect(isAccessibleView("bookings", false)).toBe(false);
    expect(isAccessibleView("bookings", false, { bookingEnabled: true })).toBe(true);
    expect(isAccessibleView("bookings", true)).toBe(true);
    expect(isAccessibleView("bogus", true)).toBe(false);
    expect(isAccessibleView(null, true)).toBe(false);
  });
});
