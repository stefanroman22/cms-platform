// linkInput.ts — what a client types in the link box → a safe href, or null.
import { safeHref } from "@/lib/cms-rich-text";

export function normalizeLinkInput(raw: string): string | null {
  const v = raw.trim();
  if (!v) return null;
  if (/^(https?:\/\/|mailto:|tel:)/i.test(v) || v.startsWith("#") || v.startsWith("/"))
    return safeHref(v);
  if (/^[^\s@/]+@[^\s@/]+\.[^\s@/]+$/.test(v)) return safeHref(`mailto:${v}`);
  if (/^\+?[\d\s().-]{6,}$/.test(v)) return safeHref(`tel:${v.replace(/[\s().-]/g, "")}`);
  if (/^[\w-]+(\.[\w-]+)+([/?#]\S*)?$/.test(v)) return safeHref(`https://${v}`);
  return null;
}
