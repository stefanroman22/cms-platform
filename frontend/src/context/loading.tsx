"use client";

import { createContext, useContext, useState, useCallback } from "react";
import dynamic from "next/dynamic";

/**
 * LoadingScreen is dynamic-imported with `ssr: false`. Two reasons:
 *   1. It's never visible on cold load — the overlay only shows when
 *      a transition explicitly calls `show()`. Loading its module +
 *      framer-motion + arc CSS upfront wastes bandwidth.
 *   2. The overlay's framer animation has no business running during
 *      SSR HTML generation.
 */
const LoadingScreen = dynamic(
  () => import("@/components/ui/LoadingScreen").then((m) => ({ default: m.LoadingScreen })),
  { ssr: false }
);

interface LoadingContextValue {
  show: () => void;
  hide: () => void;
}

const LoadingContext = createContext<LoadingContextValue>({
  show: () => {},
  hide: () => {},
});

export function LoadingProvider({ children }: { children: React.ReactNode }) {
  const [isVisible, setIsVisible] = useState(false);

  const show = useCallback(() => setIsVisible(true), []);
  const hide = useCallback(() => setIsVisible(false), []);

  return (
    <LoadingContext.Provider value={{ show, hide }}>
      {/* Only render the overlay once we actually want it visible — keeps
          the dynamic chunk out of the network waterfall on cold load. */}
      {isVisible && <LoadingScreen isVisible={isVisible} />}
      {children}
    </LoadingContext.Provider>
  );
}

export function useLoading() {
  return useContext(LoadingContext);
}
