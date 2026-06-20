import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import * as cache from "@/lib/cache";

vi.mock("next/navigation", () => ({
  usePathname: () => "/dashboard/demo",
}));
vi.mock("@/context/user", () => ({
  useUser: () => ({ user: { id: "u1", is_admin: false } }),
}));
vi.mock("@/context/loading", () => ({
  useLoading: () => ({ show: vi.fn() }),
}));
vi.mock("@/lib/auth", () => ({ logout: vi.fn() }));
vi.mock("@/context/auth", () => ({ broadcastLogout: vi.fn() }));

import { SidebarPanel } from "../SidebarPanel";

const PROJECTS = [
  { id: "p1", name: "Demo Site", slug: "demo" },
  { id: "p2", name: "Other Site", slug: "other" },
];

beforeEach(() => {
  cache.clearAll();
  global.fetch = vi.fn().mockResolvedValue({ ok: true, json: async () => PROJECTS });
});
afterEach(() => vi.restoreAllMocks());

describe("SidebarPanel", () => {
  it("renders the Projects chapter with one dotted list item per project", async () => {
    render(<SidebarPanel />);
    expect(screen.getByText("Projects")).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.getByRole("link", { name: /demo site/i })).toBeInTheDocument();
      expect(screen.getByRole("link", { name: /other site/i })).toBeInTheDocument();
    });
  });

  it("marks the project matching the current route as current", async () => {
    render(<SidebarPanel />);
    await waitFor(() => {
      expect(screen.getByRole("link", { name: /demo site/i })).toHaveAttribute(
        "aria-current",
        "page"
      );
    });
    expect(screen.getByRole("link", { name: /other site/i })).not.toHaveAttribute("aria-current");
  });

  it("links each project to its workspace route", async () => {
    render(<SidebarPanel />);
    await waitFor(() => {
      expect(screen.getByRole("link", { name: /other site/i })).toHaveAttribute(
        "href",
        "/dashboard/other"
      );
    });
  });

  it("shows an empty message when the user has no projects", async () => {
    (global.fetch as ReturnType<typeof vi.fn>).mockResolvedValue({
      ok: true,
      json: async () => [],
    });
    render(<SidebarPanel />);
    await waitFor(() => {
      expect(screen.getByText(/no projects yet/i)).toBeInTheDocument();
    });
  });

  it("shows an error with a retry instead of 'no projects' when the fetch fails", async () => {
    (global.fetch as ReturnType<typeof vi.fn>).mockResolvedValue({
      ok: false,
      json: async () => ({}),
    });
    render(<SidebarPanel />);
    await waitFor(() => {
      expect(screen.getByText(/couldn.t load projects/i)).toBeInTheDocument();
    });
    expect(screen.getByRole("button", { name: /retry/i })).toBeInTheDocument();
    expect(screen.queryByText(/no projects yet/i)).not.toBeInTheDocument();
  });
});
