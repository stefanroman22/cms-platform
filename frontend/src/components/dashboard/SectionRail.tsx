"use client";

import { useRef } from "react";
import { motion, useReducedMotion } from "motion/react";
import type { SectionDef, SectionKey } from "./sectionConfig";

interface SectionRailProps {
  sections: SectionDef[];
  activeView: SectionKey;
  onSelect: (view: SectionKey) => void;
}

/**
 * Project-level section navigation: a horizontal segmented control on every
 * breakpoint (scrollable strip on narrow screens). The active item shows a
 * filled pill driven by a shared `layoutId` so it slides between items with
 * the same spring as the CMS underline (PageTabs). tablist semantics +
 * roving tabindex; all four arrow keys move selection.
 */
export function SectionRail({ sections, activeView, onSelect }: SectionRailProps) {
  const btnRefs = useRef<(HTMLButtonElement | null)[]>([]);
  const reduce = useReducedMotion();

  function onKeyDown(e: React.KeyboardEvent, index: number) {
    let next: number;
    if (e.key === "ArrowDown" || e.key === "ArrowRight") next = (index + 1) % sections.length;
    else if (e.key === "ArrowUp" || e.key === "ArrowLeft")
      next = (index - 1 + sections.length) % sections.length;
    else return;
    e.preventDefault();
    btnRefs.current[next]?.focus();
    // Automatic activation: arrowing also selects and swaps the panel.
    // Section panels are cheap/cached, so follow-focus activation is the
    // nicer UX here. Revisit if a section ever does real work on mount.
    onSelect(sections[next].key);
  }

  return (
    <nav
      role="tablist"
      aria-label="Project sections"
      aria-orientation="horizontal"
      className="no-scrollbar flex w-full items-center gap-1 overflow-x-auto overflow-y-hidden rounded-xl border border-zinc-200 bg-white p-1 shadow-sm dark:border-zinc-800 dark:bg-zinc-900 dark:shadow-none md:w-fit"
    >
      {sections.map((section, i) => {
        const isActive = section.key === activeView;
        const Icon = section.icon;
        return (
          <button
            key={section.key}
            ref={(el) => {
              btnRefs.current[i] = el;
            }}
            type="button"
            role="tab"
            id={`section-tab-${section.key}`}
            aria-controls={`section-panel-${section.key}`}
            aria-selected={isActive}
            tabIndex={isActive ? 0 : -1}
            onClick={() => onSelect(section.key)}
            onKeyDown={(e) => onKeyDown(e, i)}
            className="relative flex shrink-0 cursor-pointer items-center whitespace-nowrap rounded-lg px-3.5 py-2 text-sm font-medium outline-none transition-colors focus-visible:ring-2 focus-visible:ring-zinc-400/40"
          >
            {isActive && (
              <motion.span
                layoutId="section-rail-active"
                className="absolute inset-0 rounded-lg bg-zinc-900 shadow-sm dark:bg-zinc-700"
                transition={
                  reduce
                    ? { duration: 0 }
                    : { type: "spring", stiffness: 480, damping: 36, mass: 0.6 }
                }
              />
            )}
            <span
              className={
                "relative z-10 flex items-center gap-2.5 transition-colors duration-150 " +
                (isActive
                  ? "text-white"
                  : "text-zinc-500 hover:text-zinc-800 dark:text-zinc-400 dark:hover:text-zinc-200")
              }
            >
              <Icon aria-hidden="true" className="h-4 w-4 shrink-0" />
              {section.label}
              {section.adminOnly && (
                <span
                  className={
                    "ml-0.5 rounded-full px-1.5 py-px text-[10px] font-medium uppercase tracking-wide " +
                    (isActive
                      ? "bg-white/20 text-white/90"
                      : "bg-zinc-200/70 text-zinc-500 dark:bg-zinc-700/70 dark:text-zinc-400")
                  }
                >
                  admin
                </span>
              )}
            </span>
          </button>
        );
      })}
    </nav>
  );
}
