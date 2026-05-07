"use client";

import { createContext, useContext, useEffect, useState } from "react";

type Theme = "light" | "dark";

interface ThemeContextValue {
  theme: Theme;
  toggleTheme: () => void;
  setTheme: (t: Theme) => void;
}

const DEFAULT_THEME: Theme = "dark";
export const THEME_STORAGE_KEY = "dashboard-theme";

const ThemeContext = createContext<ThemeContextValue>({
  theme: DEFAULT_THEME,
  toggleTheme: () => {},
  setTheme: () => {},
});

/**
 * Read the persisted theme.
 *
 * On SSR (no document), returns the default. On the client we read
 * `documentElement.dataset.theme` because the inline boot script in
 * `app/layout.tsx` runs BEFORE React hydrates and sets that attribute
 * from localStorage. Reading the dataset (not localStorage directly)
 * means SSR + hydration agree — no flash.
 */
function readBootTheme(): Theme {
  if (typeof document === "undefined") return DEFAULT_THEME;
  const t = document.documentElement.dataset.theme;
  return t === "light" || t === "dark" ? t : DEFAULT_THEME;
}

function persistTheme(t: Theme) {
  try {
    window.localStorage.setItem(THEME_STORAGE_KEY, t);
  } catch {
    /* private mode / disabled — fine, falls back to default next visit */
  }
  document.documentElement.dataset.theme = t;
  document.documentElement.classList.toggle("dark", t === "dark");
}

export function ThemeProvider({ children }: { children: React.ReactNode }) {
  // SSR: always DEFAULT_THEME so the server-rendered HTML matches the
  // <html data-theme="dark"> the inline boot script will set on the
  // client. After hydration, the effect below reconciles state with
  // whatever the boot script discovered in localStorage.
  const [theme, setThemeState] = useState<Theme>(DEFAULT_THEME);

  // Reconcile after mount — if localStorage held "light", bring state
  // in line. Cheap noop if already matching.
  useEffect(() => {
    const boot = readBootTheme();
    if (boot !== theme) setThemeState(boot);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Whenever theme changes (toggle or programmatic), persist + apply
  // the class. The inline script does the same on first paint; this
  // covers every subsequent change.
  useEffect(() => {
    if (typeof document === "undefined") return;
    persistTheme(theme);
  }, [theme]);

  function toggleTheme() {
    setThemeState((prev) => (prev === "dark" ? "light" : "dark"));
  }

  function setTheme(t: Theme) {
    setThemeState(t);
  }

  return (
    <ThemeContext.Provider value={{ theme, toggleTheme, setTheme }}>
      {children}
    </ThemeContext.Provider>
  );
}

export function useTheme(): ThemeContextValue {
  return useContext(ThemeContext);
}
