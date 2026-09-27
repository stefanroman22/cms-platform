// frontend/src/components/dashboard/seo/SeoSection.test.tsx
import { render, screen } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { SeoSection } from "./SeoSection";

describe("SeoSection", () => {
  it("shows the static coming-soon panel", () => {
    render(<SeoSection />);
    expect(screen.getByText(/work in progress/i)).toBeInTheDocument();
    expect(screen.getByText(/coming soon/i)).toBeInTheDocument();
  });

  it("makes no backend calls", () => {
    const fetchSpy = vi.fn();
    global.fetch = fetchSpy;
    render(<SeoSection />);
    expect(fetchSpy).not.toHaveBeenCalled();
  });
});
