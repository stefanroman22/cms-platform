"use client";

import { useContext, useState, type ReactNode } from "react";
import { LayoutRouterContext } from "next/dist/shared/lib/app-router-context.shared-runtime";

/**
 * Freezes the App Router layout context for its subtree.
 *
 * AnimatePresence keeps an exiting page mounted while it fades out. Without this
 * freeze, App Router would immediately swap that subtree to the NEW route's
 * content, so the "outgoing" page would already show the incoming content as it
 * fades — a flicker, not a clean cross-fade. Snapshotting the context on first
 * render pins the exiting page to what it was rendering.
 *
 * This relies on a Next internal context; it is the standard, widely-used way to
 * get true exit animations in the App Router. Verified present on Next 16.2.5.
 */
export function FrozenRouter({ children }: { children: ReactNode }) {
  const context = useContext(LayoutRouterContext);
  // Snapshot the layout context once, on mount, and never update it — the
  // useState initializer captures the first-render value — so this subtree keeps
  // rendering the route it had even after navigation swaps the live context.
  const [frozen] = useState(context);

  // No context (shouldn't happen inside a layout) — render children untouched.
  if (!frozen) return <>{children}</>;

  return <LayoutRouterContext.Provider value={frozen}>{children}</LayoutRouterContext.Provider>;
}
