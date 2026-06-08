/**
 * @roman/booking-client — a tiny, framework-agnostic adapter a client website's
 * booking form calls. It owns CORRECTNESS (validate + normalize the payload
 * against the versioned contract before sending) and TARGETING (route to the
 * right slug/endpoint), so a custom-styled client form can never post an
 * incomplete payload or hit the wrong tenant.
 *
 * IMPORTANT: zero React/DOM imports. `fetch` is injectable so the SDK is
 * unit-testable and host-agnostic. This file is copied verbatim into client
 * website repos by the CMS connector; the client owns 100% of the UI, the SDK
 * owns correctness + targeting. No styling here.
 */

import { BOOKING_CONTRACT_VERSION, type BookingPayload, validateAndNormalize } from "./contract";

export { BOOKING_CONTRACT_VERSION, type BookingPayload };

type FetchLike = (
  input: string,
  init?: {
    method?: string;
    headers?: Record<string, string>;
    body?: string;
  }
) => Promise<{ ok: boolean; status?: number; json: () => Promise<unknown> }>;

export interface BookingClientConfig {
  /** Base URL of the booking API, e.g. "https://api.example.com/booking". */
  apiBase: string;
  /** Tenant public slug — the routing target. */
  slug: string;
  /** Injectable fetch (defaults to the global `fetch`). */
  fetch?: FetchLike;
}

export interface CreateBookingResult {
  [key: string]: unknown;
}

export interface BookingClient {
  createBooking: (payload: BookingPayload) => Promise<CreateBookingResult>;
  getConfig: () => Promise<unknown>;
  getServices: () => Promise<unknown>;
  getAvailability: (serviceId: string, from: string, to: string) => Promise<unknown>;
  readonly contractVersion: string;
}

/** Extract a human-readable message from a backend error body. */
function errorMessage(status: number | undefined, body: unknown): string {
  if (body && typeof body === "object") {
    const detail = (body as { detail?: unknown }).detail;
    if (detail && typeof detail === "object") {
      const d = detail as { field?: unknown; message?: unknown };
      if (typeof d.message === "string") {
        return typeof d.field === "string" ? `${d.field}: ${d.message}` : d.message;
      }
    }
    if (typeof detail === "string") return detail;
  }
  return `Booking request failed${status ? ` (${status})` : ""}`;
}

export function createBookingClient(config: BookingClientConfig): BookingClient {
  const fetchFn: FetchLike =
    config.fetch ?? ((globalThis as { fetch?: FetchLike }).fetch as FetchLike);
  if (typeof fetchFn !== "function") {
    throw new Error("booking-client: no fetch implementation available");
  }
  const base = config.apiBase.replace(/\/+$/, "");
  const slug = config.slug;
  const target = `${base}/${slug}`;

  async function getJson(url: string): Promise<unknown> {
    const res = await fetchFn(url, { method: "GET" });
    if (!res.ok) {
      throw new Error(errorMessage(res.status, await res.json().catch(() => null)));
    }
    return res.json();
  }

  return {
    contractVersion: BOOKING_CONTRACT_VERSION,

    async createBooking(payload: BookingPayload): Promise<CreateBookingResult> {
      // Validate + normalize BEFORE any network call — a bad payload never
      // reaches the backend.
      const normalized = validateAndNormalize(payload);
      const res = await fetchFn(target, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify(normalized),
      });
      const body = await res.json().catch(() => null);
      if (!res.ok) {
        throw new Error(errorMessage(res.status, body));
      }
      return (body ?? {}) as CreateBookingResult;
    },

    getConfig() {
      return getJson(`${target}/config`);
    },

    getServices() {
      return getJson(`${target}/services`);
    },

    getAvailability(serviceId: string, from: string, to: string) {
      const qs = `service_id=${encodeURIComponent(serviceId)}&from=${encodeURIComponent(
        from
      )}&to=${encodeURIComponent(to)}`;
      return getJson(`${target}/availability?${qs}`);
    },
  };
}
