/**
 * Remembers the last project the user opened so /dashboard can land them
 * straight back on it next visit. Plain localStorage (survives sessions),
 * versioned key following the `booking.overview.v1.*` convention.
 */
const STORAGE_KEY = "dashboard.lastProject.v1";

export function getLastProjectSlug(): string | null {
  if (typeof window === "undefined") return null;
  try {
    return window.localStorage.getItem(STORAGE_KEY);
  } catch {
    return null;
  }
}

export function setLastProjectSlug(slug: string): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(STORAGE_KEY, slug);
  } catch {
    // Storage unavailable (private mode / quota) — remembering is best-effort.
  }
}
