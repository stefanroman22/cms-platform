import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor, fireEvent, act } from "@testing-library/react";
import * as cache from "@/lib/cache";

const { patchSettingsSpy, patchPolicySpy } = vi.hoisted(() => ({
  patchSettingsSpy: vi.fn(),
  patchPolicySpy: vi.fn(),
}));

vi.mock("../api", () => ({
  getPolicies: vi.fn(async () => ({
    policies: [
      {
        service_id: null,
        allow_reschedule: true,
        reschedule_window_hours: 24,
        max_reschedules: 2,
        allow_cancel: true,
        cancellation_window_hours: 24,
        policy_text: "",
      },
    ],
  })),
  patchPolicy: patchPolicySpy.mockResolvedValue({}),
  getSettings: vi.fn(async () => ({
    enabled: true,
    public_slug: "demo",
    reminders_enabled: true,
    reminder_offsets_min: [1440, 60],
  })),
  // PATCH returns the enabled-wrapped shape (the backend fix).
  patchSettings: patchSettingsSpy.mockResolvedValue({
    enabled: true,
    public_slug: "demo",
    reminders_enabled: true,
    reminder_offsets_min: [60],
  }),
}));

import { PoliciesForm } from "../PoliciesForm";

beforeEach(() => {
  cache.clearAll();
  patchSettingsSpy.mockClear();
  patchPolicySpy.mockClear();
  // Seed the shared gate cache the way BookingsSection would.
  cache.set("booking-settings:demo", { enabled: true, public_slug: "demo" });
});
afterEach(() => vi.restoreAllMocks());

describe("PoliciesForm reminders", () => {
  it("saves reminder offsets and keeps the shared settings cache `enabled`", async () => {
    render(<PoliciesForm projectSlug="demo" />);
    await waitFor(() => {
      expect(screen.getByText("Email reminders")).toBeInTheDocument();
    });
    // Uncheck "24 hours before" → offsets should become just [60].
    const checkboxes = screen.getAllByRole("checkbox");
    fireEvent.click(checkboxes[0]);

    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: /Save policy/i }));
    });

    expect(patchSettingsSpy).toHaveBeenCalledTimes(1);
    expect(patchSettingsSpy.mock.calls[0][1]).toEqual({
      reminders_enabled: true,
      reminder_offsets_min: [60],
    });
    // The shared gate cache must still carry enabled:true (no Enable-CTA flash).
    expect(cache.get<{ enabled: boolean }>("booking-settings:demo")?.enabled).toBe(true);
  });

  it("does NOT re-write reminder settings when only a policy field changed", async () => {
    render(<PoliciesForm projectSlug="demo" />);
    await waitFor(() => {
      expect(screen.getByText("Email reminders")).toBeInTheDocument();
    });
    // Change a policy-only field (max reschedules) and save; reminders untouched.
    fireEvent.change(screen.getByDisplayValue("2"), { target: { value: "3" } });
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: /Save policy/i }));
    });
    expect(patchPolicySpy).toHaveBeenCalledTimes(1);
    expect(patchSettingsSpy).not.toHaveBeenCalled(); // reminders unchanged → no settings write
  });
});
