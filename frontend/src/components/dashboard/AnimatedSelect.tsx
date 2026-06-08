"use client";

import { useEffect, useRef, useState } from "react";
import { ChevronDown, ChevronUp } from "lucide-react";
import { AnimatePresence, motion } from "framer-motion";
import { dashboardInputLgCn } from "@/lib/styles";

/**
 * Custom-styled select. Uses a button + absolutely positioned listbox so
 * the option list can animate in/out with framer-motion. Caller picks the
 * closed-state arrow direction via `initialChevron`; opening rotates it
 * 180°. Listbox flips above the button when there isn't enough room below.
 */
export function AnimatedSelect({
  value,
  onChange,
  options,
  ariaLabel,
  initialChevron = "down",
}: {
  value: string;
  onChange: (v: string) => void;
  options: readonly { value: string; label: string }[];
  ariaLabel: string;
  initialChevron?: "up" | "down";
}) {
  const [open, setOpen] = useState(false);
  const [openUp, setOpenUp] = useState(false);
  const wrapRef = useRef<HTMLDivElement>(null);
  const buttonRef = useRef<HTMLButtonElement>(null);

  function toggle() {
    if (!open && buttonRef.current) {
      const rect = buttonRef.current.getBoundingClientRect();
      const spaceBelow = window.innerHeight - rect.bottom;
      const approxListboxHeight = options.length * 40 + 16;
      setOpenUp(approxListboxHeight + 10 > spaceBelow);
    }
    setOpen((o) => !o);
  }

  useEffect(() => {
    if (!open) return;
    function onDocClick(e: MouseEvent) {
      if (wrapRef.current && !wrapRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    function onEsc(e: KeyboardEvent) {
      if (e.key === "Escape") setOpen(false);
    }
    document.addEventListener("mousedown", onDocClick);
    document.addEventListener("keydown", onEsc);
    return () => {
      document.removeEventListener("mousedown", onDocClick);
      document.removeEventListener("keydown", onEsc);
    };
  }, [open]);

  const current = options.find((o) => o.value === value) ?? options[0];

  return (
    <div ref={wrapRef} className="relative">
      <button
        ref={buttonRef}
        type="button"
        onClick={toggle}
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-label={ariaLabel}
        className={`${dashboardInputLgCn} flex cursor-pointer items-center justify-between text-left`}
      >
        <span className="truncate">{current?.label ?? ""}</span>
        {initialChevron === "up" ? (
          <ChevronUp
            className={`ml-2 h-4 w-4 shrink-0 text-zinc-400 transition-transform duration-200 ${
              open ? "rotate-180" : ""
            }`}
            aria-hidden="true"
          />
        ) : (
          <ChevronDown
            className={`ml-2 h-4 w-4 shrink-0 text-zinc-400 transition-transform duration-200 ${
              open ? "rotate-180" : ""
            }`}
            aria-hidden="true"
          />
        )}
      </button>

      <AnimatePresence>
        {open && (
          <motion.ul
            role="listbox"
            initial={{ opacity: 0, y: openUp ? 6 : -6 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: openUp ? 6 : -6 }}
            transition={{ duration: 0.18, ease: "easeOut" }}
            className={`absolute left-0 right-0 z-20 overflow-hidden rounded-lg border border-zinc-200 bg-white shadow-lg dark:border-zinc-700 dark:bg-zinc-800 ${
              openUp ? "bottom-full mb-2" : "top-full mt-2"
            }`}
          >
            {options.map((opt, i) => {
              const isSelected = opt.value === value;
              return (
                <motion.li
                  key={opt.value}
                  role="option"
                  aria-selected={isSelected}
                  initial={{ opacity: 0, x: -8 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ duration: 0.18, ease: "easeOut", delay: i * 0.03 }}
                  onClick={() => {
                    onChange(opt.value);
                    setOpen(false);
                  }}
                  className={`cursor-pointer px-3 py-2.5 text-sm transition-colors ${
                    isSelected
                      ? "bg-zinc-100 text-zinc-900 dark:bg-zinc-700 dark:text-zinc-100"
                      : "text-zinc-700 hover:bg-zinc-100 dark:text-zinc-300 dark:hover:bg-zinc-700"
                  }`}
                >
                  {opt.label}
                </motion.li>
              );
            })}
          </motion.ul>
        )}
      </AnimatePresence>
    </div>
  );
}
