"use client";

import { useState } from "react";

/** Served from `public/booking/`. Every staff member always has an avatar —
 *  this neutral silhouette stands in when none is uploaded. */
export const DEFAULT_STAFF_AVATAR = "/booking/default-staff-avatar.svg";

interface Props {
  src?: string | null;
  name?: string | null;
  /** Rendered diameter in px. */
  size?: number;
  className?: string;
}

/**
 * Circular staff avatar with a guaranteed image: uses the uploaded `src`, and
 * falls back to the default silhouette both when `src` is empty and when the
 * image fails to load (a stale/broken URL never leaves a blank hole).
 */
export function StaffAvatar({ src, name, size = 36, className = "" }: Props) {
  const [errored, setErrored] = useState(false);
  const url = src && !errored ? src : DEFAULT_STAFF_AVATAR;
  return (
    // eslint-disable-next-line @next/next/no-img-element -- arbitrary uploaded/external URLs; no next/image domain config
    <img
      src={url}
      alt={name ? `${name}'s avatar` : "Staff avatar"}
      width={size}
      height={size}
      style={{ width: size, height: size }}
      onError={() => setErrored(true)}
      className={`shrink-0 rounded-full bg-zinc-100 object-cover ring-1 ring-zinc-200 dark:bg-zinc-800 dark:ring-zinc-700 ${className}`}
    />
  );
}
