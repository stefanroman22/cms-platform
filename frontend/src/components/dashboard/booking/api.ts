/**
 * Typed fetch helpers for the booking-admin endpoints.
 * All requests hit `/api/projects/${slug}/bookings/...` with
 * `credentials: "include"` and throw `Error(detail)` on non-ok.
 */

// ── Types ────────────────────────────────────────────────────────────────────

export interface BookingSettings {
  enabled: boolean;
  tenant_id?: string;
  timezone?: string;
  locale?: string;
  business_name?: string;
  logo_url?: string;
  primary_color?: string;
  accent_color?: string;
  widget_color?: string;
  email_from_name?: string;
  owner_notification_email?: string;
  meeting_url?: string;
  slot_granularity_min?: number;
  reminders_enabled?: boolean;
  reminder_offsets_min?: number[];
  calendar_provider?: string;
  public_slug?: string;
}

export interface BookingService {
  id: string;
  tenant_id?: string;
  name: string;
  description?: string;
  color?: string;
  duration_min: number;
  buffer_before_min?: number;
  buffer_after_min?: number;
  lead_time_min?: number;
  max_advance_days?: number;
  is_active?: boolean;
  sort_order?: number;
  resource_ids: string[];
}

export interface BookingResource {
  id: string;
  tenant_id?: string;
  name: string;
  type?: string;
  capacity?: number;
  is_active?: boolean;
  sort_order?: number;
}

export interface BookingHour {
  id?: string;
  tenant_id?: string;
  resource_id?: string | null;
  weekday: number; // 0=Sun .. 6=Sat
  start_time: string; // "HH:MM"
  end_time: string;
}

export interface BookingException {
  id: string;
  tenant_id?: string;
  resource_id?: string | null;
  date: string; // "YYYY-MM-DD"
  is_closed?: boolean;
  start_time?: string | null;
  end_time?: string | null;
}

export interface BookingPolicy {
  id?: string;
  tenant_id?: string;
  service_id?: string | null;
  allow_reschedule?: boolean;
  reschedule_window_hours?: number;
  max_reschedules?: number;
  allow_cancel?: boolean;
  cancellation_window_hours?: number;
  policy_text?: string;
}

// ── Email template ────────────────────────────────────────────────────────────

export interface EmailTemplateField {
  key: string;
  label: string;
  group: "shared" | "confirmation" | "reschedule" | "cancellation" | "reminder";
  default: string;
  value: string;
}

export interface EmailTemplateBrand {
  logo_url?: string | null;
  accent_color?: string | null;
  business_name?: string | null;
}

export interface EmailTemplateData {
  brand: EmailTemplateBrand;
  fields: EmailTemplateField[];
}

export interface EmailDraft {
  logo_url?: string;
  accent_color?: string;
  business_name?: string;
  email_copy?: Record<string, string>;
}

// ── Request body shapes (match backend Pydantic models exactly) ───────────────

export type SettingsPatch = Partial<Omit<BookingSettings, "enabled" | "tenant_id">> & {
  email_copy?: Record<string, string>;
};

export interface ServiceIn {
  name: string;
  description?: string;
  color?: string;
  duration_min: number;
  buffer_before_min?: number;
  buffer_after_min?: number;
  lead_time_min?: number;
  max_advance_days?: number;
  is_active?: boolean;
  sort_order?: number;
  resource_ids: string[];
}

export interface ResourceIn {
  name: string;
  type?: string;
  capacity?: number;
  is_active?: boolean;
  sort_order?: number;
}

export interface HoursRow {
  resource_id?: string | null;
  weekday: number;
  start_time: string;
  end_time: string;
}

export interface HoursReplace {
  hours: HoursRow[];
}

export interface ExceptionIn {
  resource_id?: string | null;
  date: string;
  is_closed?: boolean;
  start_time?: string | null;
  end_time?: string | null;
}

export interface PolicyPatch {
  service_id?: string | null;
  allow_reschedule?: boolean;
  reschedule_window_hours?: number;
  max_reschedules?: number;
  allow_cancel?: boolean;
  cancellation_window_hours?: number;
  policy_text?: string;
}

// ── Helpers ──────────────────────────────────────────────────────────────────

async function throwOnError(r: Response): Promise<void> {
  if (!r.ok) {
    const body = (await r.json().catch(() => ({}))) as { detail?: string };
    throw new Error(body.detail ?? `Request failed (${r.status})`);
  }
}

// ── Settings ─────────────────────────────────────────────────────────────────

export async function getSettings(slug: string): Promise<BookingSettings> {
  const r = await fetch(`/api/projects/${slug}/bookings/settings`, {
    credentials: "include",
  });
  await throwOnError(r);
  return r.json();
}

export async function enableBookings(slug: string): Promise<BookingSettings> {
  const r = await fetch(`/api/projects/${slug}/bookings/enable`, {
    method: "POST",
    credentials: "include",
  });
  await throwOnError(r);
  return r.json();
}

export async function patchSettings(slug: string, body: SettingsPatch): Promise<BookingSettings> {
  const r = await fetch(`/api/projects/${slug}/bookings/settings`, {
    method: "PATCH",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  await throwOnError(r);
  return r.json();
}

// ── Services ─────────────────────────────────────────────────────────────────

export async function listServices(slug: string): Promise<{ services: BookingService[] }> {
  const r = await fetch(`/api/projects/${slug}/bookings/services`, {
    credentials: "include",
  });
  await throwOnError(r);
  return r.json();
}

export async function createService(slug: string, body: ServiceIn): Promise<BookingService> {
  const r = await fetch(`/api/projects/${slug}/bookings/services`, {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  await throwOnError(r);
  return r.json();
}

export async function patchService(
  slug: string,
  id: string,
  body: ServiceIn
): Promise<BookingService> {
  const r = await fetch(`/api/projects/${slug}/bookings/services/${id}`, {
    method: "PATCH",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  await throwOnError(r);
  return r.json();
}

export async function deleteService(slug: string, id: string): Promise<void> {
  const r = await fetch(`/api/projects/${slug}/bookings/services/${id}`, {
    method: "DELETE",
    credentials: "include",
  });
  await throwOnError(r);
}

// ── Resources ────────────────────────────────────────────────────────────────

export async function listResources(slug: string): Promise<{ resources: BookingResource[] }> {
  const r = await fetch(`/api/projects/${slug}/bookings/resources`, {
    credentials: "include",
  });
  await throwOnError(r);
  return r.json();
}

export async function createResource(slug: string, body: ResourceIn): Promise<BookingResource> {
  const r = await fetch(`/api/projects/${slug}/bookings/resources`, {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  await throwOnError(r);
  return r.json();
}

export async function patchResource(
  slug: string,
  id: string,
  body: ResourceIn
): Promise<BookingResource> {
  const r = await fetch(`/api/projects/${slug}/bookings/resources/${id}`, {
    method: "PATCH",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  await throwOnError(r);
  return r.json();
}

export async function deleteResource(slug: string, id: string): Promise<void> {
  const r = await fetch(`/api/projects/${slug}/bookings/resources/${id}`, {
    method: "DELETE",
    credentials: "include",
  });
  await throwOnError(r);
}

// ── Hours & Exceptions ───────────────────────────────────────────────────────

export async function getHours(
  slug: string
): Promise<{ hours: BookingHour[]; exceptions: BookingException[] }> {
  const r = await fetch(`/api/projects/${slug}/bookings/hours`, {
    credentials: "include",
  });
  await throwOnError(r);
  return r.json();
}

export async function putHours(
  slug: string,
  body: HoursReplace
): Promise<{ hours: BookingHour[] }> {
  const r = await fetch(`/api/projects/${slug}/bookings/hours`, {
    method: "PUT",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  await throwOnError(r);
  return r.json();
}

export async function createException(slug: string, body: ExceptionIn): Promise<BookingException> {
  const r = await fetch(`/api/projects/${slug}/bookings/exceptions`, {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  await throwOnError(r);
  return r.json();
}

export async function deleteException(slug: string, id: string): Promise<void> {
  const r = await fetch(`/api/projects/${slug}/bookings/exceptions/${id}`, {
    method: "DELETE",
    credentials: "include",
  });
  await throwOnError(r);
}

// ── Appointments ─────────────────────────────────────────────────────────────

export interface BookingAppointment {
  id: string;
  status: "confirmed" | "cancelled" | "no_show" | "completed" | string;
  start_utc: string;
  end_utc: string;
  reschedule_count: number;
  notes?: string | null;
  source?: string | null;
  service_id: string;
  resource_id?: string | null;
  customer_id?: string | null;
  customer_name?: string | null;
  customer_email?: string | null;
  customer_phone?: string | null;
  customer_timezone?: string | null;
  service_name?: string | null;
  resource_name?: string | null;
}

export interface AvailabilitySlot {
  start_utc: string;
  end_utc: string;
  resource_id?: string | null;
}

export interface AvailabilityDay {
  date: string; // "YYYY-MM-DD"
  slots: AvailabilitySlot[];
}

export interface AvailabilityResponse {
  days: AvailabilityDay[];
  slots?: AvailabilitySlot[];
}

export interface AppointmentFilters {
  status?: string;
  service_id?: string;
  resource_id?: string;
  from?: string;
  to?: string;
}

export interface AppointmentCustomerIn {
  name: string;
  email: string;
  phone?: string;
  tz?: string;
}

export interface AppointmentCreateIn {
  service_id: string;
  resource_id?: string;
  start_utc: string;
  customer: AppointmentCustomerIn;
  note?: string;
}

export interface AppointmentActionIn {
  action: "cancel" | "reschedule" | "no_show" | "complete";
  start_utc?: string;
  reason?: string;
}

// ── Policies ─────────────────────────────────────────────────────────────────

export async function getPolicies(slug: string): Promise<{ policies: BookingPolicy[] }> {
  const r = await fetch(`/api/projects/${slug}/bookings/policies`, {
    credentials: "include",
  });
  await throwOnError(r);
  return r.json();
}

export async function patchPolicy(slug: string, body: PolicyPatch): Promise<BookingPolicy> {
  const r = await fetch(`/api/projects/${slug}/bookings/policies`, {
    method: "PATCH",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  await throwOnError(r);
  return r.json();
}

// ── Appointment management ────────────────────────────────────────────────────

export async function listAppointments(
  slug: string,
  filters: AppointmentFilters = {}
): Promise<{ appointments: BookingAppointment[] }> {
  const params = new URLSearchParams();
  if (filters.status) params.set("status", filters.status);
  if (filters.service_id) params.set("service_id", filters.service_id);
  if (filters.resource_id) params.set("resource_id", filters.resource_id);
  if (filters.from) params.set("from", filters.from);
  if (filters.to) params.set("to", filters.to);
  const qs = params.toString();
  const r = await fetch(`/api/projects/${slug}/bookings/appointments${qs ? `?${qs}` : ""}`, {
    credentials: "include",
  });
  await throwOnError(r);
  return r.json();
}

export async function createAppointment(
  slug: string,
  body: AppointmentCreateIn
): Promise<BookingAppointment> {
  const r = await fetch(`/api/projects/${slug}/bookings/appointments`, {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  await throwOnError(r);
  return r.json();
}

export async function actOnAppointment(
  slug: string,
  id: string,
  body: AppointmentActionIn
): Promise<BookingAppointment> {
  const r = await fetch(`/api/projects/${slug}/bookings/appointments/${id}`, {
    method: "PATCH",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  await throwOnError(r);
  return r.json();
}

export async function getAvailability(
  slug: string,
  serviceId: string,
  from: string,
  to: string
): Promise<AvailabilityResponse> {
  const params = new URLSearchParams({ service_id: serviceId, from, to });
  const r = await fetch(`/api/projects/${slug}/bookings/availability?${params.toString()}`, {
    credentials: "include",
  });
  await throwOnError(r);
  return r.json();
}

// ── Stats ─────────────────────────────────────────────────────────────────────

export interface BookingStatsKpis {
  total: number;
  upcoming: number;
  today: number;
  this_week: number;
  avg_per_day: number;
}

export interface BookingStatsByDay {
  date: string;
  count: number;
}

export interface BookingStatsByService {
  service: string;
  count: number;
}

export interface BookingStatsByStatus {
  status: string;
  count: number;
}

export interface BookingStatsHeatmapCell {
  weekday: number; // 0=Mon..6=Sun
  hour: number;
  count: number;
}

export interface BookingStats {
  kpis: BookingStatsKpis;
  cancellation_rate: number;
  no_show_rate: number;
  by_day: BookingStatsByDay[];
  by_service: BookingStatsByService[];
  by_status: BookingStatsByStatus[];
  heatmap: BookingStatsHeatmapCell[];
}

export async function getStats(slug: string, from?: string, to?: string): Promise<BookingStats> {
  const params = new URLSearchParams();
  if (from) params.set("from", from);
  if (to) params.set("to", to);
  const qs = params.toString();
  const r = await fetch(`/api/projects/${slug}/bookings/stats${qs ? `?${qs}` : ""}`, {
    credentials: "include",
  });
  await throwOnError(r);
  return r.json();
}

// ── Email template ────────────────────────────────────────────────────────────

export async function getEmailTemplate(slug: string): Promise<EmailTemplateData> {
  const r = await fetch(`/api/projects/${slug}/bookings/email-template`, {
    credentials: "include",
  });
  await throwOnError(r);
  return r.json();
}

export async function previewEmail(
  slug: string,
  emailCase: string,
  draft: EmailDraft
): Promise<{ html: string }> {
  const r = await fetch(`/api/projects/${slug}/bookings/email-preview`, {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ case: emailCase, draft }),
  });
  await throwOnError(r);
  return r.json();
}

export async function uploadBookingLogo(slug: string, file: File): Promise<{ url: string }> {
  const form = new FormData();
  form.append("file", file);
  const r = await fetch(`/api/projects/${slug}/bookings/logo`, {
    method: "POST",
    credentials: "include",
    body: form,
    // No Content-Type header — let the browser set multipart boundary
  });
  await throwOnError(r);
  return r.json();
}
