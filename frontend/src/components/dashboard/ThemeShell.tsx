"use client";

import { useTheme } from "@/context/theme";

export function ThemeShell({ children }: { children: React.ReactNode }) {
  const { theme } = useTheme();

  return (
    <div
      suppressHydrationWarning
      className={`flex h-screen overflow-hidden bg-zinc-50 dark:bg-zinc-950${theme === "dark" ? " dark" : ""}`}
    >
      {children}
    </div>
  );
}
