/**
 * H2 — per-field text colour overrides.
 *
 * Colour-capable fields (color: true) render a <input type="color"> next to the
 * text input; subjects (color: false) do not. Changing the picker stores the hex
 * in the same email_copy dict under `${key}__color` and persists it on Save.
 */

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, act } from "@testing-library/react";
import * as cache from "@/lib/cache";
import { patchSettings } from "../api";

// Stub the preview frame (avoids its debounced fetch/timer here).
vi.mock("../EmailPreviewFrame", () => ({
  EmailPreviewFrame: () => null,
}));

vi.mock("../api", () => ({
  getEmailTemplate: vi.fn().mockResolvedValue({
    brand: { logo_url: null, accent_color: "#18181b", business_name: "Acme" },
    fields: [
      {
        key: "confirmed_heading",
        label: "Heading",
        group: "confirmation",
        default: "You're booked, {name}.",
        value: "",
        color: true,
        color_value: "",
      },
      {
        key: "confirm_subject",
        label: "Subject",
        group: "confirmation",
        default: "Booked",
        value: "",
        color: false,
        color_value: "",
      },
    ],
  }),
  patchSettings: vi.fn().mockResolvedValue({}),
  uploadBookingLogo: vi.fn(),
}));

import { EmailTemplateEditor } from "../EmailTemplateEditor";

describe("EmailTemplateEditor per-field colour", () => {
  beforeEach(() => cache.clearAll());
  afterEach(() => {
    vi.clearAllMocks();
    cache.clearAll();
  });

  it("shows a colour picker for colour-capable fields only and saves the hex under {key}__color", async () => {
    render(<EmailTemplateEditor projectSlug="acme" />);
    await screen.findByRole("button", { name: /save email settings/i });

    // Heading (color:true) has a colour input; Subject (color:false) does not.
    const headingColor = screen.getByLabelText(/heading text color/i) as HTMLInputElement;
    expect(headingColor).toBeInTheDocument();
    expect(screen.queryByLabelText(/subject text color/i)).not.toBeInTheDocument();

    // Pick a colour.
    await act(async () => {
      fireEvent.input(headingColor, { target: { value: "#ff8800" } });
    });

    // Save → patchSettings receives the colour under the derived key.
    const saveBtn = screen.getByRole("button", { name: /save email settings/i });
    await act(async () => {
      fireEvent.click(saveBtn);
      await Promise.resolve();
      await Promise.resolve();
    });

    const body = (patchSettings as unknown as { mock: { calls: unknown[][] } }).mock
      .calls[0][1] as {
      email_copy?: Record<string, string>;
    };
    expect(body.email_copy?.["confirmed_heading__color"]).toBe("#ff8800");
  });
});
