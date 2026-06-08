"use client";

import { LoadingProvider } from "@/context/loading";
import { AuthProvider } from "@/context/auth";
import { ScrollToTopOnNavigate } from "@/components/nav/ScrollToTopOnNavigate";

export function MarketingProviders({ children }: { children: React.ReactNode }) {
  return (
    <LoadingProvider>
      <AuthProvider>
        <ScrollToTopOnNavigate />
        {children}
      </AuthProvider>
    </LoadingProvider>
  );
}
