"use client";

import { AnimatePresence, m } from "motion/react";
import { ChevronLeft, ChevronRight } from "lucide-react";
import { cn } from "@/lib/utils";
import { dateKey, monthMatrix, MONTH_LABELS, WEEKDAY_LABELS } from "@/lib/bookingDates";
import { tw } from "@/components/booking/i18n";

const FADE = [0.16, 1, 0.3, 1] as const;

interface MonthGridProps {
  viewYear: number;
  viewMonth: number; // 0-11
  bookableDays: Set<string>; // YYYY-MM-DD
  loading: boolean;
  /** False when the viewed month is the current month (can't page into the past). */
  canGoPrev: boolean;
  onPrevMonth: () => void;
  onNextMonth: () => void;
  onSelectDay: (d: Date) => void;
  locale?: string;
}

export function MonthGrid({
  viewYear,
  viewMonth,
  bookableDays,
  loading,
  canGoPrev,
  onPrevMonth,
  onNextMonth,
  onSelectDay,
  locale = "en",
}: MonthGridProps) {
  const weeks = monthMatrix(viewYear, viewMonth);
  return (
    <div>
      <div className="mb-4 flex items-center justify-between">
        <button
          type="button"
          onClick={onPrevMonth}
          disabled={!canGoPrev}
          aria-label={tw(locale, "prevMonth")}
          className={cn(
            "rounded-lg border border-border p-1.5 outline-none transition-colors",
            canGoPrev
              ? "text-text-secondary hover:border-accent/50 hover:text-accent focus-visible:border-accent"
              : "cursor-not-allowed text-text-tertiary/30"
          )}
        >
          <ChevronLeft className="h-4 w-4" />
        </button>
        <p className="font-display text-sm font-semibold text-text-primary">
          {MONTH_LABELS[viewMonth]} {viewYear}
        </p>
        <button
          type="button"
          onClick={onNextMonth}
          aria-label={tw(locale, "nextMonth")}
          className="rounded-lg border border-border p-1.5 text-text-secondary outline-none transition-colors hover:border-accent/50 hover:text-accent focus-visible:border-accent"
        >
          <ChevronRight className="h-4 w-4" />
        </button>
      </div>

      {/* Fade between months. mode="wait" + fixed 6-row grid → no layout jump. */}
      <AnimatePresence mode="wait" initial={false}>
        <m.div
          key={`${viewYear}-${viewMonth}`}
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.2, ease: FADE }}
          className="grid grid-cols-7 gap-1 text-center"
        >
          {WEEKDAY_LABELS.map((d) => (
            <div key={d} className="pb-2 text-xs font-medium text-text-tertiary">
              {d}
            </div>
          ))}
          {weeks.flat().map((day) => {
            const key = dateKey(day);
            const inMonth = day.getMonth() === viewMonth;
            const bookable = inMonth && bookableDays.has(key);
            return (
              <button
                key={key}
                type="button"
                disabled={!bookable || loading}
                onClick={() => onSelectDay(day)}
                className={cn(
                  "flex h-10 items-center justify-center rounded-lg text-sm outline-none transition-colors",
                  !inMonth && "text-text-tertiary/30",
                  inMonth && !bookable && "text-text-tertiary/50",
                  bookable &&
                    "text-text-primary hover:bg-accent hover:text-bg focus-visible:bg-accent focus-visible:text-bg"
                )}
              >
                {day.getDate()}
              </button>
            );
          })}
        </m.div>
      </AnimatePresence>

      {loading && (
        <m.p
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          className="mt-3 text-center text-xs text-text-tertiary"
        >
          {tw(locale, "loadingAvailability")}
        </m.p>
      )}
    </div>
  );
}
