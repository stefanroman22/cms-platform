import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import * as cache from "@/lib/cache";
import { DashboardSection } from "../DashboardSection";

const PROJECTS = [
  { id: "p1", name: "Demo Site", slug: "demo", website_url: "https://demo.example.com" },
  { id: "p2", name: "Bare Site", slug: "bare", website_url: null },
];

beforeEach(() => {
  cache.clearAll();
  global.fetch = vi.fn().mockResolvedValue({ ok: true, json: async () => PROJECTS });
});
afterEach(() => vi.restoreAllMocks());

describe("DashboardSection", () => {
  it("shows the coming-soon analytics frame with ghost KPI slots", async () => {
    render(<DashboardSection projectSlug="demo" isAdmin={false} onGoToCms={vi.fn()} />);
    expect(screen.getByText(/coming soon/i)).toBeInTheDocument();
    expect(screen.getByText(/website analytics/i)).toBeInTheDocument();
    expect(screen.getByText("Visitors")).toBeInTheDocument();
    expect(screen.getByText("Page views")).toBeInTheDocument();
    expect(screen.getByText("Avg. visit")).toBeInTheDocument();
    expect(screen.getByText("Top page")).toBeInTheDocument();
  });

  it("calls onGoToCms when the shortcut button is clicked", async () => {
    const onGoToCms = vi.fn();
    const user = userEvent.setup();
    render(<DashboardSection projectSlug="demo" isAdmin={false} onGoToCms={onGoToCms} />);
    await user.click(screen.getByRole("button", { name: /go to cms/i }));
    expect(onGoToCms).toHaveBeenCalledTimes(1);
  });

  it("shows the live website card linking to the project's website_url", async () => {
    render(<DashboardSection projectSlug="demo" isAdmin={false} onGoToCms={vi.fn()} />);
    await waitFor(() => {
      expect(screen.getByRole("link", { name: /live website/i })).toHaveAttribute(
        "href",
        "https://demo.example.com"
      );
    });
    expect(screen.getByText("demo.example.com")).toBeInTheDocument();
  });

  it("shows the not-connected fallback when the project has no website_url", async () => {
    render(<DashboardSection projectSlug="bare" isAdmin={false} onGoToCms={vi.fn()} />);
    await waitFor(() => {
      expect(screen.getByText(/no live website connected yet/i)).toBeInTheDocument();
    });
    expect(screen.queryByRole("link", { name: /live website/i })).not.toBeInTheDocument();
  });
});
