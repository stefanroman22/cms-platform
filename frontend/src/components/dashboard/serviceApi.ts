import * as cache from "@/lib/cache";
import type { FieldFormat } from "@/components/dashboard/rich-text/ContentField";

/** Dashboard detail payload for one service in one locale (`ServiceDetailOut`). */
export interface ServiceDetail {
  id: string;
  service_key: string;
  label: string | null;
  service_type_slug: string;
  service_type_name: string;
  service_type_icon: string;
  schema: Record<string, unknown>;
  content: Record<string, unknown>;
  last_updated: string | null;
  locale?: string;
  default_locale?: string;
  locales?: string[];
  translation_status?: Record<string, string> | null;
  rich_text_version?: number;
  field_formats?: Record<string, FieldFormat>;
  can_edit_structure?: boolean;
}

// Cache keys shared by the editor, the service cards and the locale tabs, so a
// hover prefetch lands exactly where the editor will look for it.
export const serviceDetailKey = (projectSlug: string, serviceKey: string, locale?: string) =>
  `service:${projectSlug}:${serviceKey}:${locale || "default"}`;
export const serviceDetailPrefix = (projectSlug: string, serviceKey: string) =>
  `service:${projectSlug}:${serviceKey}:`;
export const servicesListKey = (projectSlug: string) => `services:${projectSlug}`;
export const projectStatusKey = (projectSlug: string) => `status:${projectSlug}`;

export function fetchServiceDetail(
  projectSlug: string,
  serviceKey: string,
  locale?: string
): Promise<ServiceDetail> {
  const q = locale ? `?locale=${encodeURIComponent(locale)}` : "";
  return fetch(`/api/projects/${projectSlug}/services/${serviceKey}${q}`, {
    credentials: "include",
    cache: "no-store",
  }).then((r) => {
    if (!r.ok) throw new Error("Failed to load service.");
    return r.json();
  });
}

export async function saveServiceContent(
  projectSlug: string,
  serviceKey: string,
  content: Record<string, unknown>,
  locale?: string
): Promise<ServiceDetail> {
  const q = locale ? `?locale=${encodeURIComponent(locale)}` : "";
  const r = await fetch(`/api/projects/${projectSlug}/services/${serviceKey}${q}`, {
    method: "PUT",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ content }),
  });
  if (!r.ok) {
    const b = await r.json().catch(() => ({}));
    const d = b.detail;
    throw new Error(
      Array.isArray(d)
        ? d.map((x) => x?.msg ?? String(x)).join("; ")
        : typeof d === "string"
          ? d
          : "Save failed"
    );
  }
  return r.json();
}

/** Warm the cache on hover/focus so opening the service is instant. */
export function prefetchServiceDetail(projectSlug: string, serviceKey: string, locale?: string) {
  cache.prefetch(serviceDetailKey(projectSlug, serviceKey, locale), () =>
    fetchServiceDetail(projectSlug, serviceKey, locale)
  );
}
