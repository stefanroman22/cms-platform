import { routing } from "./routing";
import type { Locale } from "@/lib/locale";

const BASE = "https://roman-technologies.dev";

/** `path` is the locale-less canonical path, e.g. "/" or "/about". */
export function buildAlternates(path: string, locale: Locale) {
  const url = (l: string) =>
    l === routing.defaultLocale ? `${BASE}${path}` : `${BASE}/${l}${path === "/" ? "" : path}`;

  const languages: Record<string, string> = {};
  for (const l of routing.locales) languages[l] = url(l);
  languages["x-default"] = url(routing.defaultLocale);

  return { canonical: url(locale), languages };
}
