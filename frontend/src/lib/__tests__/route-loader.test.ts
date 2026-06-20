import { describe, it, expect } from "vitest";
import { shouldTriggerRouteLoad } from "../route-loader";

const ORIGIN = "https://roman-technologies.dev";
const at = (href: string | null, currentPath = "/") =>
  shouldTriggerRouteLoad({ href, currentOrigin: ORIGIN, currentPath });

describe("shouldTriggerRouteLoad", () => {
  it("triggers for an internal route to a different path", () => {
    expect(at("/about")).toBe(true);
  });
  it("does not trigger for a same-page hash link", () => {
    expect(at("/#contact", "/")).toBe(false);
    expect(at("#contact", "/")).toBe(false);
  });
  it("triggers for a different path even with a hash", () => {
    expect(at("/about#team", "/")).toBe(true);
  });
  it("does not trigger for external links", () => {
    expect(at("https://example.com/x")).toBe(false);
  });
  it("ignores mailto/tel and empty href", () => {
    expect(at("mailto:a@b.com")).toBe(false);
    expect(at("tel:+311234")).toBe(false);
    expect(at(null)).toBe(false);
  });
});
