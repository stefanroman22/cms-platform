/**
 * Task 3B — Booking settings: widget accent color removed from the dashboard.
 *
 * The "Widget accent color" field is gone (widget styling is owned by the
 * client/connector now). The rest of the settings form still renders and the
 * PATCH payload no longer carries widget_color.
 */

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, act } from "@testing-library/react";
import * as cache from "@/lib/cache";

const patchSettings = vi.fn().mockResolvedValue({ enabled: true });

vi.mock("../api", () => ({
  getSettings: vi.fn().mockResolvedValue({
    enabled: true,
    business_name: "Acme",
    timezone: "Europe/Berlin",
    locale: "en",
    public_slug: "acme",
    widget_color: "#c9a961",
  }),
  patchSettings: (...args: unknown[]) => patchSettings(...args),
}));

import { BookingSettingsForm } from "../BookingSettingsForm";

describe("BookingSettingsForm widget color removal", () => {
  beforeEach(() => cache.clearAll());
  afterEach(() => {
    vi.clearAllMocks();
    cache.clearAll();
  });

  it("does not render the Widget accent color field but keeps other settings", async () => {
    render(<BookingSettingsForm projectSlug="acme" />);

    // Business name still renders once the draft seeds.
    expect(await screen.findByDisplayValue("Acme")).toBeInTheDocument();

    // The widget accent color block is gone.
    expect(screen.queryByText(/widget accent color/i)).not.toBeInTheDocument();
    expect(screen.queryByLabelText(/pick widget accent color/i)).not.toBeInTheDocument();

    // Other fields remain.
    expect(screen.getByText(/public booking link/i)).toBeInTheDocument();
  });

  it("does not send widget_color in the PATCH payload", async () => {
    render(<BookingSettingsForm projectSlug="acme" />);
    await screen.findByDisplayValue("Acme");

    const saveBtn = screen.getByRole("button", { name: /save settings/i });
    await act(async () => {
      fireEvent.click(saveBtn);
      await Promise.resolve();
    });

    expect(patchSettings).toHaveBeenCalled();
    const body = patchSettings.mock.calls[0][1] as Record<string, unknown>;
    expect(body).not.toHaveProperty("widget_color");
  });
});
