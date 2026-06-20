"use client";

import { useEffect } from "react";
import { useLocale } from "next-intl";
import { LazyMotion, domAnimation, MotionConfig } from "motion/react";
import { LoadingProvider } from "@/context/loading";
import { AuthProvider } from "@/context/auth";
import { ScrollToTopOnNavigate } from "@/components/nav/ScrollToTopOnNavigate";
import { RouteLoader } from "@/components/nav/RouteLoader";

export function MarketingProviders({ children }: { children: React.ReactNode }) {
  // Root <html lang> stays "en" statically; reflect the active marketing locale
  // for assistive tech on the client (hreflang covers SEO).
  const locale = useLocale();
  useEffect(() => {
    document.documentElement.lang = locale;
  }, [locale]);

  return (
    // NOTE: no `strict` — full `motion` components (LoadingScreen, PageTransition,
    // HeaderRightCluster) are used across the app and strict mode rejects them.
    <LazyMotion features={domAnimation}>
      <MotionConfig reducedMotion="user">
        <LoadingProvider>
          <AuthProvider>
            <ScrollToTopOnNavigate />
            <RouteLoader />
            {children}
          </AuthProvider>
        </LoadingProvider>
      </MotionConfig>
    </LazyMotion>
  );
}
