import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor, fireEvent, act } from "@testing-library/react";
import * as cache from "@/lib/cache";

const { patchPolicySpy } = vi.hoisted(() => ({
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
}));

import { PoliciesForm } from "../PoliciesForm";

beforeEach(() => {
  cache.clearAll();
  patchPolicySpy.mockClear();
});
afterEach(() => vi.restoreAllMocks());

describe("PoliciesForm", () => {
  it("saves the tenant-default policy", async () => {
    render(<PoliciesForm projectSlug="demo" />);
    await waitFor(() => {
      expect(screen.getByDisplayValue("2")).toBeInTheDocument();
    });
    fireEvent.change(screen.getByDisplayValue("2"), { target: { value: "3" } });
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: /Save policy/i }));
    });
    expect(patchPolicySpy).toHaveBeenCalledTimes(1);
    expect(patchPolicySpy.mock.calls[0][1]).toMatchObject({
      service_id: null,
      max_reschedules: 3,
    });
  });
});
