import { describe, it, expect } from "vitest";
import { STAT_VIEWS, STAT_VIEWS_BY_ID } from "./widgetRegistry";
import { DEFAULT_STAT_VIEW } from "./prefsStore";

describe("overview stat-view registry", () => {
  it("the default stat view is registered", () => {
    expect(STAT_VIEWS_BY_ID[DEFAULT_STAT_VIEW]).toBeTruthy();
  });

  it("does not expose calendar or peak-times as stat views", () => {
    const ids = new Set(STAT_VIEWS.map((v) => v.id));
    // Calendar is always-on (not a selectable view); peak times was removed.
    expect(ids.has("calendar")).toBe(false);
    expect(ids.has("peakTimes")).toBe(false);
  });

  it("offers overview, breakdown and trend", () => {
    const ids = new Set(STAT_VIEWS.map((v) => v.id));
    expect(ids.has("overview")).toBe(true);
    expect(ids.has("breakdown")).toBe(true);
    expect(ids.has("trend")).toBe(true);
  });

  it("every view has a title and a render function", () => {
    for (const v of STAT_VIEWS) {
      expect(typeof v.title).toBe("string");
      expect(v.title.length).toBeGreaterThan(0);
      expect(typeof v.render).toBe("function");
    }
  });

  it("by-staff is gated by an availability predicate", () => {
    const staffView = STAT_VIEWS_BY_ID["byStaff"];
    expect(staffView).toBeTruthy();
    expect(typeof staffView.available).toBe("function");
  });
});
