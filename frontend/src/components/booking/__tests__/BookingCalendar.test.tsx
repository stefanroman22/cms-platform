import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, waitFor, screen } from "@testing-library/react";
import { BookingCalendar } from "../BookingCalendar";

/** Build a fetch mock with configurable service + resource fixtures. */
function mockFetch(opts?: { services?: unknown[]; resources?: unknown[] }) {
  const services = opts?.services ?? [];
  const resources = opts?.resources ?? [];
  return vi.fn((url: string | URL | Request) => {
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
    if (u.includes("/resources")) {
      return Promise.resolve({ ok: true, json: async () => ({ resources }) });
    }
    if (u.includes("/services")) {
      return Promise.resolve({ ok: true, json: async () => ({ services }) });
    }
    return Promise.resolve({ ok: true, json: async () => ({ days: [] }) });
  }) as unknown as typeof fetch;
}

beforeEach(() => {
  global.fetch = mockFetch();
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

describe("BookingCalendar barber step", () => {
  it("renders a barber step with the eligible barbers + a No preference option", async () => {
    global.fetch = mockFetch({
      services: [{ id: "s1", name: "Cut", duration_min: 30 }],
      resources: [
        { id: "r1", name: "Alex", type: "staff" },
        { id: "r2", name: "Sam", type: "staff" },
      ],
    });
    render(<BookingCalendar slug="acme" />);
    // Single service is auto-skipped; with 2 barbers the barber step shows.
    expect(await screen.findByText("Select a staff member")).toBeTruthy();
    expect(screen.getByText("Alex")).toBeTruthy();
    expect(screen.getByText("Sam")).toBeTruthy();
    expect(screen.getByText("No preference")).toBeTruthy();
  });

  it("auto-skips the barber step when only one barber is eligible", async () => {
    global.fetch = mockFetch({
      services: [{ id: "s1", name: "Cut", duration_min: 30 }],
      resources: [{ id: "r1", name: "Alex", type: "staff" }],
    });
    const { container } = render(<BookingCalendar slug="acme" />);
    // Goes straight to the date step (month grid) — no barber prompt.
    await waitFor(() => {
      expect(container.querySelector("[data-booking-root]")).toBeTruthy();
    });
    await waitFor(() => {
      // The single barber is selected silently and availability is requested
      // with its resource_id.
      const calls = (global.fetch as unknown as { mock: { calls: unknown[][] } }).mock.calls.map(
        (c) => String(c[0])
      );
      expect(calls.some((u) => u.includes("/availability") && u.includes("resource_id=r1"))).toBe(
        true
      );
    });
    expect(screen.queryByText("Select a staff member")).toBeNull();
  });
});
