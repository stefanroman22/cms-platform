import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import * as cache from "@/lib/cache";

let mockSearch = "";
const { replaceSpy, pushSpy } = vi.hoisted(() => ({ replaceSpy: vi.fn(), pushSpy: vi.fn() }));
vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace: replaceSpy, push: pushSpy }),
  usePathname: () => "/dashboard/demo",
  useSearchParams: () => new URLSearchParams(mockSearch),
}));

import { CmsSection } from "../CmsSection";

const HERO_DETAIL = {
  id: "s1",
  service_key: "hero",
  label: "Hero Banner",
  service_type_slug: "unknown_type",
  service_type_name: "Hero",
  service_type_icon: "image",
  schema: {},
  content: {},
  last_updated: null,
};

beforeEach(() => {
  mockSearch = "";
  replaceSpy.mockClear();
  pushSpy.mockClear();
  cache.clearAll();
  global.fetch = vi.fn().mockResolvedValue({ ok: true, json: async () => [] });
});
afterEach(() => vi.restoreAllMocks());

describe("CmsSection", () => {
  it("renders the empty-state when there are no services", async () => {
    render(<CmsSection projectSlug="demo" isAdmin={false} />);
    await waitFor(() => {
      expect(screen.getByText(/no services configured yet/i)).toBeInTheDocument();
    });
  });

  it("renders the inline editor instead of the grid when ?service= is set", async () => {
    mockSearch = "view=cms&service=hero";
    global.fetch = vi.fn().mockResolvedValue({ ok: true, json: async () => HERO_DETAIL });

    render(<CmsSection projectSlug="demo" isAdmin={false} />);

    expect(screen.getByRole("button", { name: /back to content list/i })).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.getByRole("heading", { name: /hero banner/i })).toBeInTheDocument();
    });
    expect(screen.queryByText(/no services configured yet/i)).not.toBeInTheDocument();
  });

  it("back to content strips service+locale but keeps view+tab, replacing the history entry", async () => {
    mockSearch = "view=cms&tab=Home&service=hero&locale=nl";
    global.fetch = vi.fn().mockResolvedValue({ ok: true, json: async () => HERO_DETAIL });
    const user = userEvent.setup();

    render(<CmsSection projectSlug="demo" isAdmin={false} />);
    await user.click(screen.getByRole("button", { name: /back to content list/i }));

    expect(replaceSpy).toHaveBeenCalledWith("/dashboard/demo?view=cms&tab=Home", {
      scroll: false,
    });
    expect(pushSpy).not.toHaveBeenCalled();
  });
});
