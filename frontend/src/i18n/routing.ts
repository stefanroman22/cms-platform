import { defineRouting } from "next-intl/routing";
import { LOCALES, DEFAULT_LOCALE } from "@/lib/locale";

export const routing = defineRouting({
  locales: LOCALES,
  defaultLocale: DEFAULT_LOCALE,
  localePrefix: "as-needed",
  // Persist the language choice for a year. Without an explicit maxAge, next-intl
  // writes a SESSION cookie on every served page, which overwrites the persistent
  // cookie the middleware sets — so the choice was lost on browser close and the
  // next visit fell back to the geo default instead of the remembered language.
  localeCookie: {
    maxAge: 60 * 60 * 24 * 365,
  },
});
