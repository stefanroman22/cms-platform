"use client";

import { LoadingProvider } from "@/context/loading";
import { AuthProvider } from "@/context/auth";

export function MarketingProviders({ children }: { children: React.ReactNode }) {
  return (
    <LoadingProvider>
      <AuthProvider>{children}</AuthProvider>
    </LoadingProvider>
  );
}
