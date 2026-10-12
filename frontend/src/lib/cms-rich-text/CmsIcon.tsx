// Vendored from CMS client-kit/rich-text v1.2.0 — do not edit; re-sync instead.
import type { ReactNode } from "react";
import type { CmsIconValue } from "./theme";

export interface CmsIconProps {
  icon: CmsIconValue | null; size?: number | string; className?: string; label?: string; fallback?: ReactNode;
}

const UNSAFE_SRC_RE = /["'()\\\s]/;

export function CmsIcon({ icon, size = "1em", className, label, fallback }: CmsIconProps): ReactNode {
  if (!icon || UNSAFE_SRC_RE.test(icon.src)) return fallback ?? null;
  const isSvg = icon.src.split(/[?#]/)[0].toLowerCase().endsWith(".svg");
  if (icon.mode === "original" || !isSvg) {
    // width/height attributes take pixels only; a CSS length ("1em") goes through style.
    const dims = typeof size === "number" ? { width: size, height: size } : { style: { width: size, height: size } };
    return <img src={icon.src} alt={label ?? ""} {...dims} className={className} loading="lazy" decoding="async" />;
  }
  const url = `url("${icon.src}")`;
  return (
    <span
      role={label ? "img" : undefined}
      aria-label={label}
      aria-hidden={label ? undefined : true}
      className={["cms-icon", className].filter(Boolean).join(" ")}
      style={{
        display: "inline-block", width: size, height: size, backgroundColor: icon.color || "currentColor",
        WebkitMaskImage: url, maskImage: url, WebkitMaskRepeat: "no-repeat", maskRepeat: "no-repeat",
        WebkitMaskPosition: "center", maskPosition: "center", WebkitMaskSize: "contain", maskSize: "contain",
      }}
    />
  );
}
