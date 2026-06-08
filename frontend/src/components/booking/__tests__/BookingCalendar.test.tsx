import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, waitFor } from "@testing-library/react";
import { BookingCalendar } from "../BookingCalendar";

beforeEach(() => {
  global.fetch = vi.fn((url: string | URL | Request) => {
    const u = typeof url === "string" ? url : url.toString();
    if (u.includes("/config")) {
      return Promise.resolve({
        ok: true,
        json: async () => ({
          public_slug: "acme",
          business_name: "Acme",
          logo_url: null,
          primary_color: "#123456",
          accent_color: "#000000",
          widget_color: "#abcdef",
          locale: "en",
        }),
      });
    }
    if (u.includes("/services")) {
      return Promise.resolve({ ok: true, json: async () => ({ services: [] }) });
    }
    return Promise.resolve({ ok: true, json: async () => ({ days: [] }) });
  }) as unknown as typeof fetch;
});
afterEach(() => vi.restoreAllMocks());

describe("BookingCalendar theming", () => {
  it("drives the widget accent from widget_color, independent of the email accent_color", async () => {
    const { container } = render(<BookingCalendar slug="acme" />);
    await waitFor(() => {
      const root = container.querySelector("[data-booking-root]") as HTMLElement;
      expect(root).toBeTruthy();
      // Widget uses widget_color (#abcdef), NOT the email accent_color (#000000).
      expect(root.style.getPropertyValue("--color-accent")).toBe("#abcdef");
    });
  });
});
