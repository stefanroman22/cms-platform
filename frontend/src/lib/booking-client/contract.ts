/**
 * Versioned create-booking contract — the single source of truth a client
 * booking form is validated against before any network call.
 *
 * IMPORTANT: this file is FRAMEWORK-AGNOSTIC (zero React/DOM imports) and is
 * copied verbatim into client website repos by the CMS connector. It mirrors the
 * backend constant in `backend/auth_service/models/booking_contract.py`; keep the
 * version + required field set in lockstep. Bump the version on any
 * non-backward-compatible change.
 */

export const BOOKING_CONTRACT_VERSION = "1.0.0";

/** A normalized booking payload as posted to `POST {apiBase}/{slug}`. */
export interface BookingPayload {
  service_id: string;
  resource_id?: string;
  start_utc: string;
  note?: string;
  customer: {
    name: string;
    email: string;
    phone?: string;
    locale?: string;
    tz?: string;
  };
  /** Honeypot — leave empty; bots fill it. */
  website?: string;
}

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

/** A non-empty, parseable ISO-8601 datetime check (no Date side effects). */
function isIsoDateTime(value: unknown): boolean {
  if (typeof value !== "string" || value.trim() === "") return false;
  const t = Date.parse(value);
  return !Number.isNaN(t);
}

/**
 * Validate + normalize a candidate payload against the contract. Returns the
 * normalized payload on success, or throws an Error naming every bad field.
 * Strings are trimmed; optional fields default to empty.
 */
export function validateAndNormalize(input: unknown): BookingPayload {
  const errors: string[] = [];
  const p = (input ?? {}) as Record<string, unknown>;
  const customerRaw = (p.customer ?? {}) as Record<string, unknown>;

  const service_id = typeof p.service_id === "string" ? p.service_id.trim() : "";
  if (!service_id) errors.push("service_id is required");

  const start_utc = typeof p.start_utc === "string" ? p.start_utc.trim() : "";
  if (!start_utc) {
    errors.push("start_utc is required");
  } else if (!isIsoDateTime(start_utc)) {
    errors.push("start_utc must be an ISO-8601 datetime");
  }

  const name = typeof customerRaw.name === "string" ? customerRaw.name.trim() : "";
  if (!name) errors.push("customer.name is required");

  const email = typeof customerRaw.email === "string" ? customerRaw.email.trim() : "";
  if (!email) {
    errors.push("customer.email is required");
  } else if (!EMAIL_RE.test(email)) {
    errors.push("customer.email is invalid");
  }

  if (errors.length > 0) {
    throw new Error(`Invalid booking payload: ${errors.join("; ")}`);
  }

  const str = (v: unknown): string => (typeof v === "string" ? v.trim() : "");
  return {
    service_id,
    resource_id: str(p.resource_id),
    start_utc,
    note: str(p.note),
    customer: {
      name,
      email,
      phone: str(customerRaw.phone),
      locale: str(customerRaw.locale),
      tz: str(customerRaw.tz),
    },
    website: str(p.website),
  };
}
