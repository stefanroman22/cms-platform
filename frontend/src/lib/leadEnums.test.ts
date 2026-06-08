import { describe, it, expect } from "vitest";
import { LEAD_TYPE_LABEL, LEAD_TYPE_BADGE_CN } from "./leadEnums";

describe("product (lead_type) labels", () => {
  it("uses the approved product wording", () => {
    expect(LEAD_TYPE_LABEL.website).toBe("Website");
    expect(LEAD_TYPE_LABEL.automation).toBe("AI Workflow");
    expect(LEAD_TYPE_LABEL.both).toBe("Website + AI Workflow");
  });
  it("has a badge class for every product value", () => {
    (Object.keys(LEAD_TYPE_LABEL) as (keyof typeof LEAD_TYPE_LABEL)[]).forEach((k) => {
      expect(LEAD_TYPE_BADGE_CN[k]).toBeTruthy();
    });
  });
});
