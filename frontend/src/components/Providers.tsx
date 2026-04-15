"use client";

import { LoadingProvider } from "@/context/loading";
import { AuthProvider } from "@/context/auth";

export function Providers({ children }: { children: React.ReactNode }) {
  return (
    <LoadingProvider>
      <AuthProvider>{children}</AuthProvider>
    </LoadingProvider>
  );
}
