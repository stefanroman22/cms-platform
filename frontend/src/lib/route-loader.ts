/**
 * Decides whether an anchor click should trigger the full-screen route loader.
 * Pure + framework-free so it is unit-testable. Returns true only for a real
 * client-side navigation to a DIFFERENT pathname on the same origin.
 */
export function shouldTriggerRouteLoad({
  href,
  currentOrigin,
  currentPath,
}: {
  href: string | null | undefined;
  currentOrigin: string;
  currentPath: string;
}): boolean {
  if (!href) return false;
  if (/^(mailto:|tel:|#)/i.test(href)) return false;
  let url: URL;
  try {
    url = new URL(href, currentOrigin);
  } catch {
    return false;
  }
  if (url.origin !== currentOrigin) return false; // external
  if (!/^https?:$/.test(url.protocol)) return false;
  if (url.pathname === currentPath) return false; // same page (pure hash)
  return true;
}
