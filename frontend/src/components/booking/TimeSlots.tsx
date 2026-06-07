"use client";

import { ChevronLeft } from "lucide-react";
import { cn } from "@/lib/utils";
import { tw } from "@/components/booking/i18n";

interface TimeSlotsProps {
  dayLabel: string;
  slots: string[]; // UTC ISO
  loading: boolean;
  displayTz: string;
  tzOptions: string[];
  onTzChange: (tz: string) => void;
  onBack: () => void;
  onPick: (iso: string) => void;
  locale?: string;
}

function formatTime(iso: string, tz: string): string {
  return new Intl.DateTimeFormat(undefined, {
    hour: "2-digit",
    minute: "2-digit",
    timeZone: tz,
  }).format(new Date(iso));
}

export function TimeSlots({
  dayLabel,
  slots,
  loading,
  displayTz,
  tzOptions,
  onTzChange,
  onBack,
  onPick,
  locale = "en",
}: TimeSlotsProps) {
  return (
    <div>
      <button
        type="button"
        onClick={onBack}
        className="mb-3 inline-flex items-center gap-1 text-sm text-text-secondary outline-none transition-colors hover:text-accent focus-visible:text-accent"
      >
        <ChevronLeft className="h-4 w-4" /> {tw(locale, "back")}
      </button>
      <p className="font-display text-sm font-semibold text-text-primary">{dayLabel}</p>

      {/* Timezone — defaults to CET; the client can switch to their own. */}
      <div className="mb-3 mt-1 flex items-center gap-2 text-xs text-text-tertiary">
        <span>{tw(locale, "timesIn")}</span>
        <select
          value={displayTz}
          onChange={(e) => onTzChange(e.target.value)}
          aria-label="Display timezone"
          className="max-w-[210px] cursor-pointer rounded-md border border-border bg-surface/60 px-2 py-1 text-xs text-text-secondary outline-none transition-colors hover:border-accent/50 focus-visible:border-accent"
        >
          {tzOptions.map((z) => (
            <option key={z} value={z}>
              {z.replace(/_/g, " ")}
            </option>
          ))}
        </select>
      </div>

      {loading ? (
        <p className="py-8 text-center text-sm text-text-tertiary">{tw(locale, "loadingTimes")}</p>
      ) : slots.length === 0 ? (
        <p className="py-8 text-center text-sm text-text-tertiary">
          {tw(locale, "noTimesAvailable")}
        </p>
      ) : (
        // data-lenis-prevent: the marketing page uses Lenis smooth-scroll, which
        // otherwise swallows the wheel and stops this inner list from scrolling.
        <div data-lenis-prevent className="no-scrollbar max-h-56 space-y-2 overflow-y-auto pr-1">
          {slots.map((iso) => (
            <button
              key={iso}
              type="button"
              onClick={() => onPick(iso)}
              className={cn(
                "w-full rounded-[10px] border border-border bg-surface/40 px-4 py-3 text-sm font-medium text-text-primary outline-none transition-colors",
                "hover:border-accent/60 hover:bg-surface focus-visible:border-accent"
              )}
            >
              {formatTime(iso, displayTz)}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
