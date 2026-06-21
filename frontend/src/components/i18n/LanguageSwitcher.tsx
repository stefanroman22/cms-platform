"use client";

import { useEffect, useRef, useState, useTransition } from "react";
import { useLocale, useTranslations } from "next-intl";
import { AnimatePresence, m } from "motion/react";
import { Globe, Check, ChevronDown } from "lucide-react";
import { usePathname, useRouter } from "@/i18n/navigation";
import { LOCALES, LOCALE_NAMES, type Locale } from "@/lib/locale";

type Variant = "nav" | "drawer" | "footer";

export function LanguageSwitcher({ variant = "nav" }: { variant?: Variant }) {
  const active = useLocale() as Locale;
  const t = useTranslations("languageSwitcher");
  const pathname = usePathname();
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [, startTransition] = useTransition();
  const ref = useRef<HTMLDivElement>(null);

  function select(next: Locale) {
    setOpen(false);
    if (next === active) return;
    // Persist the explicit choice (localStorage mirror; the NEXT_LOCALE cookie is
    // the server-side source of truth that survives reloads + drives SSR).
    try {
      localStorage.setItem("preferred-locale", next);
    } catch {
      /* ignore */
    }
    startTransition(() => router.replace(pathname, { locale: next }));
  }

  useEffect(() => {
    if (!open) return;
    const onClick = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false);
    document.addEventListener("mousedown", onClick);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onClick);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- close the menu when the route changes
    setOpen(false);
  }, [pathname]);

  // ── Drawer: inline segmented pills (always visible inside the menu) ───────
  if (variant === "drawer") {
    return (
      <div className="flex flex-col gap-2">
        <p className="px-1 text-xs font-semibold uppercase tracking-widest text-zinc-600">
          {t("label")}
        </p>
        <div className="flex gap-1.5">
          {LOCALES.map((l) => (
            <button
              key={l}
              type="button"
              onClick={() => select(l)}
              aria-current={l === active}
              className={`flex-1 rounded-lg border px-3 py-2 text-sm font-medium transition-colors cursor-pointer ${
                l === active
                  ? "border-accent/40 bg-accent/10 text-accent"
                  : "border-white/[0.08] text-zinc-400 hover:text-white"
              }`}
            >
              {LOCALE_NAMES[l]}
            </button>
          ))}
        </div>
      </div>
    );
  }

  // ── Nav + footer: trigger button + popover ───────────────────────────────
  const upward = variant === "footer";
  return (
    <div ref={ref} className="relative">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-haspopup="menu"
        aria-expanded={open}
        aria-label={t("ariaLabel")}
        className="flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-sm font-medium text-zinc-400 transition-colors hover:text-white cursor-pointer"
      >
        <Globe className="h-4 w-4" />
        <span className="uppercase">{active}</span>
        {/* Arrow points toward the menu's opening direction once open: the nav
            menu opens downward (up at rest → down on open); the footer menu
            opens upward (down at rest → up on open). */}
        <ChevronDown
          className={`h-3.5 w-3.5 transition-transform ${
            (upward ? open : !open) ? "rotate-180" : ""
          }`}
        />
      </button>

      <AnimatePresence>
        {open && (
          <m.ul
            role="menu"
            initial={{ opacity: 0, scale: 0.96, y: upward ? 6 : -6 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.96, y: upward ? 6 : -6 }}
            transition={{ duration: 0.16, ease: "easeOut" }}
            className={`absolute right-0 z-50 min-w-[10rem] overflow-hidden rounded-xl border border-white/[0.08] bg-zinc-950/95 p-1 shadow-xl backdrop-blur ${
              upward ? "bottom-full mb-2" : "top-full mt-2"
            }`}
          >
            {LOCALES.map((l) => (
              <li key={l} role="none">
                <button
                  type="button"
                  role="menuitemradio"
                  aria-checked={l === active}
                  onClick={() => select(l)}
                  className={`flex w-full items-center justify-between gap-3 rounded-lg px-3 py-2 text-sm transition-colors cursor-pointer ${
                    l === active ? "text-accent" : "text-zinc-300 hover:bg-white/5 hover:text-white"
                  }`}
                >
                  {LOCALE_NAMES[l]}
                  {l === active && <Check className="h-4 w-4" />}
                </button>
              </li>
            ))}
          </m.ul>
        )}
      </AnimatePresence>
    </div>
  );
}
