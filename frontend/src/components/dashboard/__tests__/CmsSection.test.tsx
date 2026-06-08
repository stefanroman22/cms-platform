import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace: vi.fn() }),
  usePathname: () => "/dashboard/demo",
  useSearchParams: () => new URLSearchParams(),
}));

import { CmsSection } from "../CmsSection";

beforeEach(() => {
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
});
