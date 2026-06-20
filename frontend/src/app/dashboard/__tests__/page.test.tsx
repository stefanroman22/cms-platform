import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import * as cache from "@/lib/cache";

const { replaceSpy } = vi.hoisted(() => ({ replaceSpy: vi.fn() }));
vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace: replaceSpy }),
}));

import DashboardIndexPage from "../page";

const PROJECTS = [
  { id: "p1", name: "Alpha", slug: "alpha" },
  { id: "p2", name: "Beta", slug: "beta" },
];

beforeEach(() => {
  replaceSpy.mockClear();
  cache.clearAll();
  window.localStorage.clear();
  global.fetch = vi.fn().mockResolvedValue({ ok: true, json: async () => PROJECTS });
});
afterEach(() => vi.restoreAllMocks());

describe("DashboardIndexPage (overview removed — redirect decision)", () => {
  it("redirects to the stored last-visited project", async () => {
    window.localStorage.setItem("dashboard.lastProject.v1", "beta");
    render(<DashboardIndexPage />);
    await waitFor(() => {
      expect(replaceSpy).toHaveBeenCalledWith("/dashboard/beta");
    });
  });

  it("falls back to the first project when the stored slug no longer exists", async () => {
    window.localStorage.setItem("dashboard.lastProject.v1", "gone");
    render(<DashboardIndexPage />);
    await waitFor(() => {
      expect(replaceSpy).toHaveBeenCalledWith("/dashboard/alpha");
    });
  });

  it("defaults to the first project when nothing is stored", async () => {
    render(<DashboardIndexPage />);
    await waitFor(() => {
      expect(replaceSpy).toHaveBeenCalledWith("/dashboard/alpha");
    });
  });

  it("shows the empty state and does not redirect when the user has no projects", async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: true, json: async () => [] });
    render(<DashboardIndexPage />);
    await waitFor(() => {
      expect(screen.getByText(/no projects yet/i)).toBeInTheDocument();
    });
    expect(replaceSpy).not.toHaveBeenCalled();
  });
});
