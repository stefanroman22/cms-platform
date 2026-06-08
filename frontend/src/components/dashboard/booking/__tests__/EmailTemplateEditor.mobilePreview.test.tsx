/**
 * Task 5 — Email preview mobile full-screen sheet.
 *
 * On mobile, tapping "Show preview" opens an AnimatePresence full-screen sheet
 * (role="dialog") rendering the preview, with a "Done" control to close it.
 * The desktop split-view preview column is unchanged.
 */

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, act } from "@testing-library/react";
import * as cache from "@/lib/cache";

// Stub the preview frame so we can detect when it renders without its
// debounced fetch/timer running.
vi.mock("../EmailPreviewFrame", () => ({
  EmailPreviewFrame: () => <div data-testid="email-preview-frame" />,
}));

vi.mock("../api", () => ({
  getEmailTemplate: vi.fn().mockResolvedValue({
    brand: { logo_url: null, accent_color: "#18181b", business_name: "Acme" },
    fields: [
      {
        key: "confirm_subject",
        label: "Subject",
        group: "confirmation",
        default: "Booked",
        value: "",
      },
    ],
  }),
  patchSettings: vi.fn().mockResolvedValue({}),
  uploadBookingLogo: vi.fn(),
}));

import { EmailTemplateEditor } from "../EmailTemplateEditor";

describe("EmailTemplateEditor mobile preview sheet", () => {
  beforeEach(() => cache.clearAll());
  afterEach(() => {
    vi.clearAllMocks();
    cache.clearAll();
  });

  it("opens a full-screen dialog sheet on Show preview and closes it on Done", async () => {
    const slug = "acme";
    render(<EmailTemplateEditor projectSlug={slug} />);

    // Wait for the draft to seed (Show preview toggle appears).
    const showBtn = await screen.findByRole("button", { name: /show preview/i });

    // No dialog before opening.
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();

    await act(async () => {
      fireEvent.click(showBtn);
      await Promise.resolve();
    });

    // A modal sheet with the preview is now visible.
    const dialog = screen.getByRole("dialog");
    expect(dialog).toBeInTheDocument();
    expect(dialog).toHaveAttribute("aria-modal", "true");

    // Close via the Done control.
    const doneBtn = screen.getByRole("button", { name: /done/i });
    await act(async () => {
      fireEvent.click(doneBtn);
      await Promise.resolve();
    });

    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("closes the sheet when the browser/OS Back button (popstate) fires", async () => {
    render(<EmailTemplateEditor projectSlug="acme" />);
    const showBtn = await screen.findByRole("button", { name: /show preview/i });

    await act(async () => {
      fireEvent.click(showBtn);
      await Promise.resolve();
    });
    expect(screen.getByRole("dialog")).toBeInTheDocument();

    // Simulate the OS/browser Back button. The full-screen opaque sheet MUST close —
    // otherwise it stays covering the dashboard (the reported black screen on mobile).
    await act(async () => {
      window.dispatchEvent(new PopStateEvent("popstate"));
      await Promise.resolve();
    });

    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });
});
