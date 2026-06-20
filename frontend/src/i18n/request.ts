import { getRequestConfig } from "next-intl/server";
import { hasLocale } from "next-intl";
import { routing } from "./routing";

async function load(locale: string): Promise<Record<string, unknown>> {
  return (await import(`../../messages/${locale}.json`)).default;
}

// Deep-merge `override` over `base`; arrays and primitives in override win wholesale.
function mergeDeep(
  base: Record<string, unknown>,
  override: Record<string, unknown>
): Record<string, unknown> {
  const out: Record<string, unknown> = { ...base };
  for (const key of Object.keys(override ?? {})) {
    const b = base?.[key];
    const o = override[key];
    out[key] =
      b && o && typeof b === "object" && typeof o === "object" && !Array.isArray(o)
        ? mergeDeep(b as Record<string, unknown>, o as Record<string, unknown>)
        : o;
  }
  return out;
}

export default getRequestConfig(async ({ requestLocale }) => {
  const requested = await requestLocale;
  const locale = hasLocale(routing.locales, requested) ? requested : routing.defaultLocale;
  const en = await load(routing.defaultLocale);
  const messages = locale === routing.defaultLocale ? en : mergeDeep(en, await load(locale));
  return { locale, messages };
});
