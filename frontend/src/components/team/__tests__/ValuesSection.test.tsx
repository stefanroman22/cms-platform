// jsdom does not ship IntersectionObserver — provide a no-op stub so Reveal
// (whileInView) mounts without throwing.
if (typeof globalThis.IntersectionObserver === "undefined") {
  (globalThis as unknown as Record<string, unknown>).IntersectionObserver = class {
    observe() {}
    unobserve() {}
    disconnect() {}
  };
}

import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { ValuesSection } from "../ValuesSection";

describe("ValuesSection", () => {
  it("renders all four values with their descriptions", () => {
    render(<ValuesSection />);
    expect(screen.getByText("Client comes first")).toBeInTheDocument();
    expect(screen.getByText("Teamwork")).toBeInTheDocument();
    expect(screen.getByText("Ownership")).toBeInTheDocument();
    expect(screen.getByText("Transparency")).toBeInTheDocument();
    expect(screen.getByText(/start from your goals/i)).toBeInTheDocument();
  });
});
