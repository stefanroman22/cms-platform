"use client";

/**
 * Dashboard shell. The `dark` class lives on <html> (set by the boot
 * script in `app/layout.tsx` and kept in sync by `context/theme.tsx`),
 * so this component no longer needs to apply it conditionally —
 * Tailwind's `dark:` utilities key on the html-level class via the
 * `@custom-variant dark` rule in `globals.css`.
 */
export function ThemeShell({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex h-screen overflow-hidden bg-zinc-50 dark:bg-zinc-950">{children}</div>
  );
}
