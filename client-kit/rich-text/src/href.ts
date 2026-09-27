const CTRL = /[\x00-\x1f\x7f]/g;
export const MAX_HREF_LENGTH = 2048;
/** Cleaned href when its scheme is allowed, else null (default deny). Mirrors backend safe_href. */
export function safeHref(raw?: string | null): string | null {
  if (!raw) return null;
  const v = raw.replace(CTRL, "").trim();
  if (!v || v.length > MAX_HREF_LENGTH) return null;
  const probe = v.replace(/ /g, "").toLowerCase();
  if (/^(https?:\/\/|mailto:|tel:)/.test(probe)) return v;
  if (v.startsWith("#")) return v;
  if (v.startsWith("/") && !v.startsWith("//") && !v.startsWith("/\\")) return v;
  return null;
}
