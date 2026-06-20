"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import { Clock } from "lucide-react";
import { dashAccent } from "@/lib/dashboardTheme";
import { dashboardInputCn } from "@/lib/styles";

interface Props {
  /** "HH:MM" (24h), or "" for empty. */
  value: string;
  onChange: (value: string) => void;
  /** Option granularity in minutes (default 15). */
  step?: number;
  placeholder?: string;
  className?: string;
  ariaLabel?: string;
  disabled?: boolean;
}

const POPOVER_W = 128; // px
const POPOVER_H = 288; // approx, for the flip decision

function pad(n: number): string {
  return String(n).padStart(2, "0");
}

/** Normalise an incoming value to "HH:MM" — tolerates the backend's `time`
 *  serialization "HH:MM:SS" and non-zero-padded hours, like the native input did. */
function toHHMM(v: string): string {
  const m = /^(\d{1,2}):(\d{2})/.exec(v);
  return m ? `${pad(Number(m[1]))}:${m[2]}` : "";
}

/** Build the option list (00:00 → 23:(60-step)), inserting `value` if it's
 *  off-grid so an existing odd time stays selectable. */
function buildOptions(step: number, value: string): string[] {
  const out: string[] = [];
  for (let m = 0; m < 24 * 60; m += step) out.push(`${pad(Math.floor(m / 60))}:${pad(m % 60)}`);
  if (/^\d{2}:\d{2}$/.test(value) && !out.includes(value)) {
    out.push(value);
    out.sort();
  }
  return out;
}

/**
 * Themed, animated time picker — a dashboard replacement for the native
 * `<input type="time">` popup. Trigger reuses `dashboardInputCn`; the popover is
 * a portal-rendered, flip-aware scrollable list (24h, gold accent on the
 * selected slot) that mirrors the DatePicker's motion + dismissal behaviour.
 */
export function TimePicker({
  value,
  onChange,
  step = 15,
  placeholder = "--:--",
  className = "",
  ariaLabel = "Choose time",
  disabled = false,
}: Props) {
  const reduced = useReducedMotion();
  const triggerRef = useRef<HTMLButtonElement>(null);
  const popRef = useRef<HTMLDivElement>(null);
  const selectedRef = useRef<HTMLButtonElement>(null);
  const [open, setOpen] = useState(false);
  const [pos, setPos] = useState<{ top: number; left: number } | null>(null);

  const v = toHHMM(value); // "HH:MM" for display, option-matching, and selection
  const options = useMemo(() => buildOptions(step, v), [step, v]);

  const reposition = useCallback(() => {
    const el = triggerRef.current;
    if (!el) return;
    const r = el.getBoundingClientRect();
    const spaceBelow = window.innerHeight - r.bottom;
    const openUp = POPOVER_H > spaceBelow && r.top > spaceBelow;
    const left = Math.min(Math.max(8, r.left), window.innerWidth - POPOVER_W - 8);
    const top = openUp ? r.top - POPOVER_H - 6 : r.bottom + 6;
    setPos({ top, left });
  }, []);

  function handleToggle() {
    if (disabled) return;
    if (!open) reposition();
    setOpen((o) => !o);
  }

  // On open, move focus to the selected slot (so arrow keys traverse from it) and
  // scroll it into view; restore the trigger on a real close. didOpenRef guards
  // the close branch from firing on mount.
  const didOpenRef = useRef(false);
  useEffect(() => {
    if (open && pos) {
      didOpenRef.current = true;
      (selectedRef.current ?? popRef.current)?.focus();
      selectedRef.current?.scrollIntoView({ block: "center" });
    } else if (!open && didOpenRef.current) {
      didOpenRef.current = false;
      triggerRef.current?.focus({ preventScroll: true });
    }
  }, [open, pos]);

  // Listbox keyboard traversal (Up/Down/Home/End) over the option buttons, so the
  // role="listbox" contract is honoured for keyboard + screen-reader users.
  function onListKeyDown(e: React.KeyboardEvent) {
    if (!["ArrowDown", "ArrowUp", "Home", "End"].includes(e.key)) return;
    const opts = Array.from(
      popRef.current?.querySelectorAll<HTMLButtonElement>('[role="option"]') ?? []
    );
    if (opts.length === 0) return;
    e.preventDefault();
    const idx = opts.indexOf(document.activeElement as HTMLButtonElement);
    const next =
      e.key === "Home"
        ? opts[0]
        : e.key === "End"
          ? opts[opts.length - 1]
          : e.key === "ArrowDown"
            ? (opts[idx + 1] ?? opts[0])
            : (opts[idx - 1] ?? opts[opts.length - 1]);
    next.focus();
  }

  // Reposition on scroll/resize; dismiss on outside click + Escape.
  useEffect(() => {
    if (!open) return;
    function onDown(e: MouseEvent) {
      const t = e.target as Node;
      if (
        triggerRef.current &&
        !triggerRef.current.contains(t) &&
        popRef.current &&
        !popRef.current.contains(t)
      ) {
        setOpen(false);
      }
    }
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") setOpen(false);
    }
    document.addEventListener("mousedown", onDown);
    document.addEventListener("keydown", onKey);
    window.addEventListener("scroll", reposition, true);
    window.addEventListener("resize", reposition);
    return () => {
      document.removeEventListener("mousedown", onDown);
      document.removeEventListener("keydown", onKey);
      window.removeEventListener("scroll", reposition, true);
      window.removeEventListener("resize", reposition);
    };
  }, [open, reposition]);

  function pick(t: string) {
    onChange(t);
    setOpen(false);
  }

  return (
    <div className={`relative ${className}`}>
      <button
        ref={triggerRef}
        type="button"
        onClick={handleToggle}
        disabled={disabled}
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-label={ariaLabel}
        className={`${dashboardInputCn} flex cursor-pointer items-center justify-between gap-2 text-left ${dashAccent.focusRing} disabled:cursor-not-allowed disabled:opacity-50`}
      >
        <span className={v ? "tabular-nums" : "text-zinc-400 dark:text-zinc-500"}>
          {v || placeholder}
        </span>
        <Clock className="h-4 w-4 shrink-0 text-zinc-400 dark:text-zinc-500" />
      </button>

      {typeof document !== "undefined" &&
        createPortal(
          <AnimatePresence>
            {open && pos && (
              <motion.div
                ref={popRef}
                role="listbox"
                aria-label={ariaLabel}
                tabIndex={-1}
                onKeyDown={onListKeyDown}
                initial={{ opacity: 0, y: -6 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -6 }}
                transition={{ duration: reduced ? 0 : 0.16, ease: "easeOut" }}
                style={{ position: "fixed", top: pos.top, left: pos.left, width: POPOVER_W }}
                className="z-[1000] max-h-72 overflow-y-auto rounded-xl border border-zinc-200 bg-white p-1 shadow-2xl outline-none dark:border-zinc-700 dark:bg-zinc-800"
              >
                {options.map((t) => {
                  const isSelected = t === v;
                  return (
                    <button
                      key={t}
                      ref={isSelected ? selectedRef : undefined}
                      type="button"
                      role="option"
                      aria-selected={isSelected}
                      onClick={() => pick(t)}
                      className={`block w-full rounded-md px-3 py-1.5 text-center text-sm tabular-nums outline-none transition-colors ${dashAccent.focusRing} ${
                        isSelected
                          ? "cursor-pointer bg-accent font-semibold text-bg"
                          : "cursor-pointer text-zinc-700 hover:bg-accent/15 hover:text-accent dark:text-zinc-200"
                      }`}
                    >
                      {t}
                    </button>
                  );
                })}
              </motion.div>
            )}
          </AnimatePresence>,
          document.body
        )}
    </div>
  );
}
