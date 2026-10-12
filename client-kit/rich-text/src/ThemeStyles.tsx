import type { LinkHTMLAttributes } from "react";
import { googleFontsHref, themeCss, type CmsTheme } from "./theme";

// React 19 hoists <link precedence>; older @types/react reject the prop, so it goes through a typed spread.
const precedence = { precedence: "default" } as LinkHTMLAttributes<HTMLLinkElement>;

export function ThemeStyles({ theme }: { theme: CmsTheme | null }) {
  if (!theme) return null;
  const css = themeCss(theme);
  const google = theme.fonts.some((f) => f.source === "google");
  return (
    <>
      {google ? <link rel="preconnect" href="https://fonts.googleapis.com" /> : null}
      {google ? <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="" /> : null}
      {theme.fonts.map((f) =>
        f.source === "google" ? <link key={f.family} rel="stylesheet" href={googleFontsHref(f)} {...precedence} /> : null,
      )}
      {css ? <style>{css}</style> : null}
    </>
  );
}
