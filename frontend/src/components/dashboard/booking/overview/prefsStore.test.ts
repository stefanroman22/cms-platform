import { describe, it, expect, beforeEach } from "vitest";
import { createOverviewPrefs, DEFAULT_STAT_VIEW, DEFAULT_SCOPE } from "./prefsStore";

beforeEach(() => localStorage.clear());

describe("overview prefs store", () => {
  it("returns defaults when empty", () => {
    const s = createOverviewPrefs("proj-1");
    expect(s.getStatView()).toBe(DEFAULT_STAT_VIEW);
    expect(s.getScope()).toBe(DEFAULT_SCOPE);
  });

  it("default stat view is the KPI overview", () => {
    expect(DEFAULT_STAT_VIEW).toBe("overview");
  });

  it("persists stat view and scope", () => {
    const s = createOverviewPrefs("proj-1");
    s.setScope("staff-7");
    s.setStatView("trend");
    const s2 = createOverviewPrefs("proj-1");
    expect(s2.getScope()).toBe("staff-7");
    expect(s2.getStatView()).toBe("trend");
  });

  it("survives corrupt storage", () => {
    localStorage.setItem("booking.overview.v1.proj-1", "not json");
    expect(createOverviewPrefs("proj-1").getStatView()).toBe(DEFAULT_STAT_VIEW);
    expect(createOverviewPrefs("proj-1").getScope()).toBe("all");
  });

  it("scopes storage per project key", () => {
    createOverviewPrefs("proj-1").setScope("staff-7");
    expect(createOverviewPrefs("proj-2").getScope()).toBe("all");
  });

  it("setting one key does not clobber the other", () => {
    const s = createOverviewPrefs("proj-1");
    s.setStatView("breakdown");
    s.setScope("staff-3");
    const s2 = createOverviewPrefs("proj-1");
    expect(s2.getStatView()).toBe("breakdown");
    expect(s2.getScope()).toBe("staff-3");
  });
});
