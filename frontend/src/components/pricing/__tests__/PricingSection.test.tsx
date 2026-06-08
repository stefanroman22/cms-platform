import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { PricingSection } from "../PricingSection";

// jsdom lacks IntersectionObserver (Reveal `inView`) and matchMedia
// (useReducedMotion) — stub both so the section mounts.
if (typeof globalThis.IntersectionObserver === "undefined") {
  (globalThis as unknown as Record<string, unknown>).IntersectionObserver = class {
    observe() {}
    unobserve() {}
    disconnect() {}
  };
}
if (typeof window !== "undefined" && !window.matchMedia) {
  window.matchMedia = ((query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addEventListener() {},
    removeEventListener() {},
    addListener() {},
    removeListener() {},
    dispatchEvent() {
      return false;
    },
  })) as typeof window.matchMedia;
}

describe("PricingSection feature tooltips", () => {
  it("shows the full tooltip text on click, portaled out of the clipping card", async () => {
    const user = userEvent.setup();
    render(<PricingSection />);

    // "24/7 maintenance" is a feature whose tooltip overflowed the card edge.
    await user.click(screen.getByRole("button", { name: "24/7 maintenance" }));

    const tip = await screen.findByRole("tooltip");
    expect(tip).toHaveTextContent("We keep your automations running around the clock.");

    // Portaled to <body>, so it is NOT nested inside the overflow-hidden section.
    expect(tip.closest("section")).toBeNull();
    // Positioned fixed (escapes any clipping ancestor).
    expect(tip).toHaveStyle({ position: "fixed" });
  });
});
