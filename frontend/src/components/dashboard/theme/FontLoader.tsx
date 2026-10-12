import { googleFontsHref, themeCss, type CmsTheme } from "@/lib/cms-rich-text";

/** Loads a theme's fonts into the dashboard (Google stylesheets plus the
 *  @font-face rules for uploaded files) so font previews render. */
export function FontLoader({ theme }: { theme: CmsTheme | null }) {
  if (!theme) return null;
  const css = themeCss(theme);
  return (
    <>
      {theme.fonts.map((f) =>
        f.source === "google" ? (
          <link key={f.family} rel="stylesheet" href={googleFontsHref(f)} />
        ) : null
      )}
      {css ? <style>{css}</style> : null}
    </>
  );
}
