"use client";

import { motion } from "framer-motion";

interface PageTabsProps {
  pages: string[];
  activePage: string;
  onSelect: (page: string) => void;
}

/**
 * Horizontal tab bar for switching between CMS pages.
 *
 * Design: a single shared sliding underline driven by Framer's
 * `layoutId`. Selecting a tab moves the bar with a spring transition
 * — no per-tab border flicker, no layout shift, intentionally
 * minimal so the focus stays on the content.
 *
 * Pages are ordered as-received; the parent (`ServiceGrid`) puts
 * "General" last.
 */
export function PageTabs({ pages, activePage, onSelect }: PageTabsProps) {
  if (pages.length <= 1) return null;

  return (
    <div className="no-scrollbar mb-6 relative flex items-center gap-1 overflow-x-auto overflow-y-hidden border-b border-zinc-200 dark:border-zinc-800">
      {pages.map((page) => {
        const isActive = page === activePage;
        return (
          <button
            key={page}
            onClick={() => onSelect(page)}
            className="relative shrink-0 px-4 py-2.5 text-sm font-medium cursor-pointer outline-none focus-visible:ring-2 focus-visible:ring-zinc-400/40 focus-visible:rounded-md"
            aria-current={isActive ? "page" : undefined}
          >
            <span
              className={
                "transition-colors duration-150 " +
                (isActive
                  ? "text-zinc-900 dark:text-zinc-50"
                  : "text-zinc-500 hover:text-zinc-800 dark:text-zinc-400 dark:hover:text-zinc-200")
              }
            >
              {page}
            </span>
            {isActive && (
              <motion.span
                layoutId="page-tabs-underline"
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
