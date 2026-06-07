"use client";

import { useCallback } from "react";
import { useRouter, usePathname, useSearchParams } from "next/navigation";
import {
  DEFAULT_VIEW,
  isAccessibleView,
  type SectionCaps,
  type SectionKey,
} from "@/components/dashboard/sectionConfig";

/**
 * Active project section, persisted in the URL as `?view=`. Mirrors the
 * existing `?tab=` pattern in ServiceGrid so deep links like
 * `?view=cms&tab=Contact` round-trip. Non-admins requesting an admin-only
 * view (e.g. settings) fall back to the default.
 */
export function useProjectView(
  isAdmin: boolean,
  caps?: SectionCaps
): {
  activeView: SectionKey;
  setView: (view: SectionKey) => void;
} {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();

  const requested = searchParams.get("view");
  const activeView: SectionKey = isAccessibleView(requested, isAdmin, caps)
    ? requested
    : DEFAULT_VIEW;

  const setView = useCallback(
    (view: SectionKey) => {
      const params = new URLSearchParams(searchParams.toString());
      params.set("view", view);
      router.replace(`${pathname}?${params.toString()}`, { scroll: false });
    },
    [router, pathname, searchParams]
  );

  return { activeView, setView };
}
