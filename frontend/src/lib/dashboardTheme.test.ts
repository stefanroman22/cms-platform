import { describe, it, expect } from "vitest";
import { dashAccent } from "./dashboardTheme";

describe("dashboard accent primitives", () => {
  it("exposes accent class constants", () => {
    expect(dashAccent.focusRing).toContain("ring-accent");
    expect(dashAccent.tabUnderline).toContain("bg-accent");
    expect(dashAccent.ctaPrimary).toContain("bg-accent");
    expect(dashAccent.kpiHighlight).toContain("text-accent");
  });
});
