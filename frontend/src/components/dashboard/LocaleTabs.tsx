"use client";

import { motion } from "framer-motion";

interface LocaleTabsProps {
  locales: string[];
  activeLocale: string;
  defaultLocale: string;
  onSelect: (locale: string) => void;
}

export function LocaleTabs({ locales, activeLocale, defaultLocale, onSelect }: LocaleTabsProps) {
  if (locales.length <= 1) return null;
  return (
    <div
      role="tablist"
      aria-label="Content language"
      className="mb-6 flex flex-wrap gap-1 border-b border-zinc-200 dark:border-zinc-800"
    >
      {locales.map((loc) => {
        const active = loc === activeLocale;
        return (
          <button
            key={loc}
            type="button"
            role="tab"
            aria-selected={active}
            onClick={() => onSelect(loc)}
            className={`relative cursor-pointer px-3 py-2 text-sm font-medium transition-colors ${
              active
                ? "text-zinc-900 dark:text-zinc-50"
                : "text-zinc-500 hover:text-zinc-800 dark:text-zinc-400 dark:hover:text-zinc-200"
            }`}
          >
            <span className="uppercase">{loc}</span>
            {loc === defaultLocale && (
              <span className="ml-1.5 rounded bg-zinc-100 px-1.5 py-0.5 text-[10px] font-normal text-zinc-500 dark:bg-zinc-800 dark:text-zinc-400">
                default
              </span>
            )}
            {active && (
              <motion.span
                layoutId="locale-tabs-underline"
                className="absolute inset-x-2 -bottom-px h-[2px] rounded-full bg-zinc-900 dark:bg-zinc-50"
                transition={{ type: "spring", stiffness: 480, damping: 36, mass: 0.6 }}
              />
            )}
          </button>
        );
      })}
    </div>
  );
}
