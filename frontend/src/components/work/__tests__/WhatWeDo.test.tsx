import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { LazyMotion, domAnimation } from "motion/react";
import { WhatWeDo } from "../WhatWeDo";

// jsdom does not ship IntersectionObserver — provide a no-op stub so Reveal
// (whileInView) mounts without throwing.
if (typeof globalThis.IntersectionObserver === "undefined") {
  (globalThis as unknown as Record<string, unknown>).IntersectionObserver = class {
    observe() {}
    unobserve() {}
    disconnect() {}
  };
}

describe("WhatWeDo", () => {
  it("renders all four services in the split layout", () => {
    // split layout has no own LazyMotion; provide one (WorkSection does in prod).
    render(
      <LazyMotion features={domAnimation}>
        <WhatWeDo layout="split" />
      </LazyMotion>
    );
    expect(screen.getByRole("heading", { name: /what do we do/i })).toBeInTheDocument();
    expect(screen.getByText("We build AI agents")).toBeInTheDocument();
    expect(screen.getByText("We develop websites")).toBeInTheDocument();
    expect(screen.getByText("We build software applications")).toBeInTheDocument();
    expect(screen.getByText("We create automation workflows with AI")).toBeInTheDocument();
  });

  it("renders the heading and all four services in the full layout", () => {
    render(<WhatWeDo layout="full" />);
    expect(screen.getByRole("heading", { name: /what do we do/i })).toBeInTheDocument();
    expect(screen.getByText("We build AI agents")).toBeInTheDocument();
    expect(screen.getByText("We create automation workflows with AI")).toBeInTheDocument();
  });
});
