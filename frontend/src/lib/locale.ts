export const LOCALES = ["en", "nl", "ro"] as const;
export type Locale = (typeof LOCALES)[number];
export const DEFAULT_LOCALE: Locale = "en";

/** Native language names, in display order. */
export const LOCALE_NAMES: Record<Locale, string> = {
  en: "English",
  nl: "Nederlands",
  ro: "Română",
};

// ISO-3166-1 alpha-2 country → preferred locale. ONLY the Netherlands gets Dutch
// and ONLY Romania gets Romanian; every other country falls back to English.
const COUNTRY_TO_LOCALE: Record<string, Locale> = {
  NL: "nl",
  RO: "ro",
};

export function resolveLocaleFromCountry(country: string | null | undefined): Locale {
  if (!country) return DEFAULT_LOCALE;
  return COUNTRY_TO_LOCALE[country.toUpperCase()] ?? DEFAULT_LOCALE;
}

export function isLocale(value: string | null | undefined): value is Locale {
  return !!value && (LOCALES as readonly string[]).includes(value);
}

/** "/nl/about" → "/about"; "/nl" → "/"; "/about" → "/about". */
export function stripLocale(pathname: string): string {
  const segments = pathname.split("/"); // ["", "nl", "about"]
  if (isLocale(segments[1])) {
    const rest = "/" + segments.slice(2).join("/");
    return rest === "/" ? "/" : rest.replace(/\/+$/, "");
  }
  return pathname;
}

export function hasLocalePrefix(pathname: string): boolean {
  return isLocale(pathname.split("/")[1]);
}

/**
 * Prefix an internal path with the locale, honoring `as-needed` (default locale
 * gets no prefix). For raw `<a href>` call sites that can't use the next-intl
 * `Link` (e.g. shared button primitives also used outside the i18n provider).
 */
export function localizePath(path: string, locale: Locale): string {
  if (locale === DEFAULT_LOCALE || !path.startsWith("/")) return path;
  return `/${locale}${path}`;
}
