/**
 * Regression: saving the email template must NOT clear the shared
 * `booking-settings:` cache.
 *
 * That key drives BookingsSection's "enabled" gate (`if (!data?.enabled)`).
 * The editor previously did `cache.invalidate('booking-settings:…')` on save;
 * because `cache.invalidate` notifies subscribers with `null` and useQuery does
 * NOT refetch on that signal, the gate's data became null → the whole Bookings
 * section flipped to the "Enable bookings" screen after every save.
 */

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, act } from "@testing-library/react";
import * as cache from "@/lib/cache";

// Stub the preview frame (avoids its debounced fetch/timer in this test).
vi.mock("../EmailPreviewFrame", () => ({
  EmailPreviewFrame: () => null,
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
      {
        key: "manage_cta",
        label: "Manage",
        group: "shared",
        default: "Manage your booking",
        value: "",
      },
    ],
  }),
  patchSettings: vi.fn().mockResolvedValue({}),
  uploadBookingLogo: vi.fn(),
}));

import { EmailTemplateEditor } from "../EmailTemplateEditor";

describe("EmailTemplateEditor save — does not break the bookings gate", () => {
  beforeEach(() => cache.clearAll());
  afterEach(() => {
    vi.clearAllMocks();
    cache.clearAll();
  });

  it("keeps booking-settings.enabled intact after saving", async () => {
    const slug = "acme";
    // The section gate caches an enabled settings object under this key.
    cache.set(`booking-settings:${slug}`, { enabled: true, public_slug: slug });

    render(<EmailTemplateEditor projectSlug={slug} />);

    // Wait until the template loads and the draft seeds (Save button appears).
    const saveBtn = await screen.findByRole("button", { name: /save email settings/i });

    await act(async () => {
      fireEvent.click(saveBtn);
      await Promise.resolve();
      await Promise.resolve();
    });

    // The gate must still read enabled — the bug deleted this entry.
    expect(cache.get<{ enabled?: boolean }>(`booking-settings:${slug}`)?.enabled).toBe(true);
    // And the email-template cache is optimistically refreshed (not nulled).
    expect(cache.get(`email-template:${slug}`)).not.toBeNull();
  });
});
