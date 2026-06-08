/**
 * Task 3C — Resources tab relabeled to "Staff" (key unchanged).
 * Task 6 — the tab strip hides its scrollbar (no-scrollbar) on mobile.
 */

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen } from "@testing-library/react";
import * as cache from "@/lib/cache";

vi.mock("../api", () => ({
  getSettings: vi.fn().mockResolvedValue({ enabled: true, public_slug: "acme" }),
  enableBookings: vi.fn(),
}));

// Stub the heavy tab panels so the shell renders cheaply.
vi.mock("../BookingSettingsForm", () => ({ BookingSettingsForm: () => null }));
vi.mock("../ServicesManager", () => ({ ServicesManager: () => null }));
vi.mock("../ResourcesManager", () => ({ ResourcesManager: () => null }));
vi.mock("../HoursEditor", () => ({ HoursEditor: () => null }));
vi.mock("../PoliciesForm", () => ({ PoliciesForm: () => null }));
vi.mock("../AppointmentsManager", () => ({ AppointmentsManager: () => null }));
vi.mock("../OverviewPanel", () => ({ OverviewPanel: () => null }));
vi.mock("../EmailTemplateEditor", () => ({ EmailTemplateEditor: () => null }));

import { BookingsSection } from "../BookingsSection";

describe("BookingsSection tabs", () => {
  beforeEach(() => cache.clearAll());
  afterEach(() => {
    vi.clearAllMocks();
    cache.clearAll();
  });

  it("labels the resources tab 'Staff' and not 'Resources'", async () => {
    render(<BookingsSection projectSlug="acme" isAdmin />);
    expect(await screen.findByRole("button", { name: /^staff$/i })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /^resources$/i })).not.toBeInTheDocument();
  });

  it("hides the scrollbar on the tab strip", async () => {
    render(<BookingsSection projectSlug="acme" isAdmin />);
    const nav = await screen.findByRole("navigation", { name: /booking configuration tabs/i });
    expect(nav.className).toContain("no-scrollbar");
  });
});
