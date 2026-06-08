import { describe, it, expect, vi } from "vitest";
import { createBookingClient } from "./index";
import { BOOKING_CONTRACT_VERSION } from "./contract";

const cfg = { apiBase: "https://api.example.com/booking", slug: "acme" };

describe("booking-client", () => {
  it("rejects an incomplete payload before sending", async () => {
    const fetchMock = vi.fn();
    const c = createBookingClient({ ...cfg, fetch: fetchMock });
    await expect(
      c.createBooking({
        service_id: "s1",
        start_utc: "2026-07-01T10:00:00Z",
        customer: { name: "", email: "bad" },
      } as never)
    ).rejects.toThrow(/name|email/i);
    expect(fetchMock).not.toHaveBeenCalled(); // never hits the network when invalid
  });

  it("normalizes and routes a valid payload to the right slug", async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: async () => ({ id: "b1" }) });
    const c = createBookingClient({ ...cfg, fetch: fetchMock });
    const res = await c.createBooking({
      service_id: "s1",
      start_utc: "2026-07-01T10:00:00Z",
      customer: { name: " Jane ", email: "jane@x.com" },
    });
    expect(res.id).toBe("b1");
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("https://api.example.com/booking/acme");
    expect(JSON.parse(init.body).customer.name).toBe("Jane"); // trimmed/normalized
  });

  it("rejects a missing service_id without sending", async () => {
    const fetchMock = vi.fn();
    const c = createBookingClient({ ...cfg, fetch: fetchMock });
    await expect(
      c.createBooking({
        start_utc: "2026-07-01T10:00:00Z",
        customer: { name: "Jane", email: "jane@x.com" },
      } as never)
    ).rejects.toThrow(/service_id/i);
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("rejects a non-ISO start_utc without sending", async () => {
    const fetchMock = vi.fn();
    const c = createBookingClient({ ...cfg, fetch: fetchMock });
    await expect(
      c.createBooking({
        service_id: "s1",
        start_utc: "not-a-date",
        customer: { name: "Jane", email: "jane@x.com" },
      } as never)
    ).rejects.toThrow(/start_utc/i);
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("surfaces backend errors with the field message", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: false,
      status: 422,
      json: async () => ({
        detail: { field: "customer.email", message: "customer.email is invalid" },
      }),
    });
    const c = createBookingClient({ ...cfg, fetch: fetchMock });
    await expect(
      c.createBooking({
        service_id: "s1",
        start_utc: "2026-07-01T10:00:00Z",
        customer: { name: "Jane", email: "jane@x.com" },
      })
    ).rejects.toThrow(/customer\.email/);
  });

  it("getConfig / getServices / getAvailability route to the slug", async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: async () => ({}) });
    const c = createBookingClient({ ...cfg, fetch: fetchMock });
    await c.getConfig();
    await c.getServices();
    await c.getAvailability("s1", "2026-07-01", "2026-07-31");
    const urls = fetchMock.mock.calls.map((args) => args[0] as string);
    expect(urls[0]).toBe("https://api.example.com/booking/acme/config");
    expect(urls[1]).toBe("https://api.example.com/booking/acme/services");
    expect(urls[2]).toBe(
      "https://api.example.com/booking/acme/availability?service_id=s1&from=2026-07-01&to=2026-07-31"
    );
  });

  it("trims a trailing slash on apiBase", async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: async () => ({ id: "b1" }) });
    const c = createBookingClient({
      apiBase: "https://api.example.com/booking/",
      slug: "acme",
      fetch: fetchMock,
    });
    await c.createBooking({
      service_id: "s1",
      start_utc: "2026-07-01T10:00:00Z",
      customer: { name: "Jane", email: "jane@x.com" },
    });
    expect(fetchMock.mock.calls[0][0]).toBe("https://api.example.com/booking/acme");
  });

  it("exposes the contract version", () => {
    expect(BOOKING_CONTRACT_VERSION).toMatch(/^\d+\.\d+\.\d+$/);
  });
});
