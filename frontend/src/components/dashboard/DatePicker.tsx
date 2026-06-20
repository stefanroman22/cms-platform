"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import { Calendar as CalendarIcon, ChevronLeft, ChevronRight, X } from "lucide-react";
import { dateKey, monthMatrix, MONTH_LABELS, WEEKDAY_LABELS } from "@/lib/bookingDates";
import { dashAccent } from "@/lib/dashboardTheme";
import { dashboardInputCn } from "@/lib/styles";

interface Props {
  /** YYYY-MM-DD, or "" for empty. */
  value: string;
  onChange: (value: string) => void;
  /** Earliest selectable day (YYYY-MM-DD), inclusive. */
  min?: string;
  placeholder?: string;
  /** Allow clearing back to "" (shows an X when a value is set). */
  clearable?: boolean;
  className?: string;
  ariaLabel?: string;
  disabled?: boolean;
}

const FADE = [0.16, 1, 0.3, 1] as const;
const POPOVER_W = 272; // px
const POPOVER_H = 320; // approx, for flip decision

function parseYmd(s: string): Date | null {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(s)) return null;
  const [y, m, d] = s.split("-").map(Number);
  const dt = new Date(y, m - 1, d);
  return Number.isNaN(dt.getTime()) ? null : dt;
}

function prettyLabel(s: string): string {
  const d = parseYmd(s);
  if (!d) return "";
  return new Intl.DateTimeFormat("en-GB", {
    weekday: "short",
    day: "numeric",
    month: "short",
    year: "numeric",
  }).format(d);
}

/**
 * Themed, animated date picker — a dashboard replacement for the native
 * `<input type="date">` popup. Trigger reuses `dashboardInputCn`; the calendar
 * popover is rendered in a portal with fixed positioning so it escapes the
 * `overflow-hidden` section cards, mirrors the marketing booking calendar's
 * month grid (gold accent on selected/today), and supports keyboard +
 * click-outside + Escape.
 */
export function DatePicker({
  value,
  onChange,
  min,
  placeholder = "Select a date",
  clearable = false,
  className = "",
  ariaLabel = "Choose date",
  disabled = false,
}: Props) {
  const reduced = useReducedMotion();
  const triggerRef = useRef<HTMLButtonElement>(null);
  const popRef = useRef<HTMLDivElement>(null);
  const [open, setOpen] = useState(false);
  const [pos, setPos] = useState<{ top: number; left: number } | null>(null);

  const selected = useMemo(() => parseYmd(value), [value]);
  const today = useMemo(() => {
    const d = new Date();
    d.setHours(0, 0, 0, 0);
    return d;
  }, []);
  const minDate = useMemo(() => (min ? parseYmd(min) : null), [min]);

  const [cursor, setCursor] = useState<Date>(() => selected ?? today);
  // Follow the selected date when `value` changes — React's "adjust state during
  // render" pattern (no setState-in-effect). `selected` is memoized on `value`,
  // so its identity only changes when the value does, so this can't loop.
  const [prevSelected, setPrevSelected] = useState(selected);
  if (selected && selected !== prevSelected) {
    setPrevSelected(selected);
    setCursor(selected);
  }

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

  // Move focus into the dialog on open (and back to the trigger on close) so
  // keyboard + screen-reader users land in the calendar and Escape works. The
  // didOpenRef guard prevents the close branch from stealing focus on mount.
  const didOpenRef = useRef(false);
  useEffect(() => {
    if (open && pos) {
      didOpenRef.current = true;
      popRef.current?.focus();
    } else if (!open && didOpenRef.current) {
      didOpenRef.current = false;
      triggerRef.current?.focus({ preventScroll: true });
    }
  }, [open, pos]);

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

  const weeks = useMemo(() => monthMatrix(cursor.getFullYear(), cursor.getMonth()), [cursor]);
  const todayKey = dateKey(today);
  const minKey = minDate ? dateKey(minDate) : null;

  function step(delta: number) {
    setCursor((c) => new Date(c.getFullYear(), c.getMonth() + delta, 1));
  }
  function pick(day: Date) {
    onChange(dateKey(day));
    setOpen(false);
  }

  return (
    <div className={`relative ${className}`}>
      <button
        ref={triggerRef}
        type="button"
        onClick={handleToggle}
        disabled={disabled}
        aria-haspopup="dialog"
        aria-expanded={open}
        aria-label={ariaLabel}
        className={`${dashboardInputCn} flex cursor-pointer items-center justify-between gap-2 text-left ${dashAccent.focusRing} disabled:cursor-not-allowed disabled:opacity-50`}
      >
        <span className={value ? "truncate" : "truncate text-zinc-400 dark:text-zinc-500"}>
          {value ? prettyLabel(value) : placeholder}
        </span>
        <span className="flex shrink-0 items-center gap-1">
          {clearable && value && !disabled && (
            <span
              role="button"
              tabIndex={0}
              aria-label="Clear date"
              onClick={(e) => {
                e.stopPropagation();
                onChange("");
              }}
              onKeyDown={(e) => {
                if (e.key === "Enter" || e.key === " ") {
                  e.preventDefault();
                  e.stopPropagation();
                  onChange("");
                }
              }}
              className="rounded p-0.5 text-zinc-400 hover:text-zinc-700 dark:hover:text-zinc-200"
            >
              <X className="h-3.5 w-3.5" />
            </span>
          )}
          <CalendarIcon className="h-4 w-4 text-zinc-400 dark:text-zinc-500" />
        </span>
      </button>

      {typeof document !== "undefined" &&
        createPortal(
          <AnimatePresence>
            {open && pos && (
              <motion.div
                ref={popRef}
                role="dialog"
                aria-modal="false"
                aria-label={ariaLabel}
                tabIndex={-1}
                initial={{ opacity: 0, y: -6 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -6 }}
                transition={{ duration: reduced ? 0 : 0.16, ease: "easeOut" }}
                style={{ position: "fixed", top: pos.top, left: pos.left, width: POPOVER_W }}
                className="z-[1000] rounded-xl border border-zinc-200 bg-white p-3 shadow-2xl outline-none dark:border-zinc-700 dark:bg-zinc-800"
              >
                {/* Month nav */}
                <div className="mb-2 flex items-center justify-between">
                  <button
                    type="button"
                    onClick={() => step(-1)}
                    aria-label="Previous month"
                    className={`rounded-lg border border-zinc-200 p-1.5 text-zinc-500 transition-colors hover:border-accent/50 hover:text-accent dark:border-zinc-700 dark:text-zinc-400 ${dashAccent.focusRing}`}
                  >
                    <ChevronLeft className="h-4 w-4" />
                  </button>
                  <p className="text-sm font-semibold text-zinc-900 dark:text-zinc-100">
                    {MONTH_LABELS[cursor.getMonth()]} {cursor.getFullYear()}
                  </p>
                  <button
                    type="button"
                    onClick={() => step(1)}
                    aria-label="Next month"
                    className={`rounded-lg border border-zinc-200 p-1.5 text-zinc-500 transition-colors hover:border-accent/50 hover:text-accent dark:border-zinc-700 dark:text-zinc-400 ${dashAccent.focusRing}`}
                  >
                    <ChevronRight className="h-4 w-4" />
                  </button>
                </div>

                {/* Weekday header */}
                <div className="grid grid-cols-7 gap-1 pb-1 text-center">
                  {WEEKDAY_LABELS.map((d) => (
                    <div
                      key={d}
                      className="text-[11px] font-medium text-zinc-400 dark:text-zinc-500"
                    >
                      {d}
                    </div>
                  ))}
                </div>

                {/* Days */}
                <motion.div
                  key={`grid-${cursor.getFullYear()}-${cursor.getMonth()}`}
                  initial={reduced ? false : { opacity: 0 }}
                  animate={{ opacity: 1 }}
                  transition={{ duration: 0.15, ease: FADE }}
                  className="grid grid-cols-7 gap-1 text-center"
                >
                  {weeks.flat().map((day) => {
                    const key = dateKey(day);
                    const inMonth = day.getMonth() === cursor.getMonth();
                    const isSelected = key === value;
                    const isToday = key === todayKey;
                    const disabledDay = minKey != null && key < minKey;
                    return (
                      <button
                        key={key}
                        type="button"
                        disabled={disabledDay}
                        aria-pressed={isSelected}
                        onClick={() => pick(day)}
                        className={`flex h-9 items-center justify-center rounded-lg text-sm tabular-nums outline-none transition-colors ${dashAccent.focusRing} ${
                          disabledDay
                            ? "cursor-not-allowed text-zinc-300 dark:text-zinc-700"
                            : isSelected
                              ? "cursor-pointer bg-accent font-semibold text-bg"
                              : `cursor-pointer ${
                                  inMonth
                                    ? "text-zinc-700 dark:text-zinc-200"
                                    : "text-zinc-400/60 dark:text-zinc-600"
                                } ${isToday ? "ring-1 ring-accent" : ""} hover:bg-accent/15 hover:text-accent`
                        }`}
                      >
                        {day.getDate()}
                      </button>
                    );
                  })}
                </motion.div>
              </motion.div>
            )}
          </AnimatePresence>,
          document.body
        )}
    </div>
  );
}
