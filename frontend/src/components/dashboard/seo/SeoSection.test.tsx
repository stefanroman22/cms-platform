// frontend/src/components/dashboard/seo/SeoSection.test.tsx
import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { SeoSection } from "./SeoSection";

beforeEach(() => {
  // URL-aware mock: the overview endpoint returns the scores object, every
  // list endpoint (plan/history/articles/competitors) returns its empty shape.
  global.fetch = vi.fn().mockImplementation((url: string) => {
    const json = url.includes("/seo/overview")
      ? {
          enabled: true,
          blog_route: null,
          last_run_at: null,
          seo_score: 82,
          geo_score: 71,
          local_score: 64,
          last_status: "completed",
          locales: ["en"],
        }
      : url.includes("/seo/history")
        ? { runs: [], changes: [] }
        : [];
    return Promise.resolve({ ok: true, json: async () => json });
  });
});

describe("SeoSection", () => {
  it("renders the tab strip", async () => {
    render(<SeoSection projectSlug="acme" isAdmin />);
    expect(screen.getByRole("button", { name: /overview/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /plan/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /competitors/i })).toBeInTheDocument();
  });

  it("switches to the Plan tab on click", async () => {
    render(<SeoSection projectSlug="acme" isAdmin />);
    fireEvent.click(screen.getByRole("button", { name: /plan/i }));
    expect(await screen.findByText(/no plan items yet/i)).toBeInTheDocument();
  });

  it("shows a coming-soon message (no tabs) for non-admin clients", () => {
    render(<SeoSection projectSlug="acme" isAdmin={false} />);
    expect(screen.getByText(/work in progress/i)).toBeInTheDocument();
    expect(screen.getByText(/coming soon/i)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /overview/i })).not.toBeInTheDocument();
  });
});
