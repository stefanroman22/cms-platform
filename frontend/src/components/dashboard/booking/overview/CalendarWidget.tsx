"use client";

import { useMemo, useState } from "react";
import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import { ChevronLeft, ChevronRight } from "lucide-react";
import { monthMatrix, MONTH_LABELS, WEEKDAY_LABELS } from "@/lib/bookingDates";
import { dashAccent } from "@/lib/dashboardTheme";
import type { BookingAppointment, BookingService } from "../api";

type View = "month" | "week" | "day";

interface Props {
  appointments: BookingAppointment[];
  services: BookingService[];
  timezone: string | null;
  onSelectAppointment: (a: BookingAppointment) => void;
}

const FADE = [0.16, 1, 0.3, 1] as const;

// Fallback event palette when a service has no explicit color (mirrors the
// by-service chart palette so the two widgets read as one system).
const EVENT_PALETTE = ["#10b981", "#3b82f6", "#8b5cf6", "#f59e0b", "#ef4444", "#06b6d4", "#84cc16"];

/** YYYY-MM-DD for a UTC instant rendered in the tenant timezone (en-CA → ISO). */
function tzDayKey(utc: string, tz: string): string {
  try {
    return new Intl.DateTimeFormat("en-CA", {
      timeZone: tz,
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
    }).format(new Date(utc));
  } catch {
    return utc.slice(0, 10);
  }
}

/** Same key for a local Date already representing a calendar day. */
function localDayKey(d: Date): string {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

function timeLabel(utc: string, tz: string): string {
  try {
    return new Intl.DateTimeFormat("en-GB", {
      timeZone: tz,
      hour: "2-digit",
      minute: "2-digit",
    }).format(new Date(utc));
  } catch {
    return "";
  }
}

export function CalendarWidget({ appointments, services, timezone, onSelectAppointment }: Props) {
  const tz = timezone ?? "UTC";
  const reduced = useReducedMotion();
  const [view, setView] = useState<View>("month");

  // "today" expressed in the tenant timezone, plus the cursor day for week/day.
  const todayKey = useMemo(() => tzDayKey(new Date().toISOString(), tz), [tz]);
  const [cursor, setCursor] = useState<Date>(() => {
    const [y, m, d] = todayKey.split("-").map(Number);
    return new Date(y, m - 1, d);
  });

  // service_id → color (explicit, else a stable palette slot).
  const serviceColor = useMemo(() => {
    const map = new Map<string, string>();
    services.forEach((s, i) => {
      map.set(s.id, s.color || EVENT_PALETTE[i % EVENT_PALETTE.length]);
    });
    return map;
  }, [services]);

  // Bucket appointments by their tenant-timezone day. Cancelled bookings are
  // omitted from the calendar — they clutter the day cells and the owner cares about
  // what's actually happening (cancellations still count in the stats/KPIs).
  const byDay = useMemo(() => {
    const map = new Map<string, BookingAppointment[]>();
    for (const a of appointments) {
      if (a.status === "cancelled") continue;
      const key = tzDayKey(a.start_utc, tz);
      const bucket = map.get(key);
      if (bucket) bucket.push(a);
      else map.set(key, [a]);
    }
    // sort each day chronologically
    for (const list of map.values()) {
      list.sort((x, y) => x.start_utc.localeCompare(y.start_utc));
    }
    return map;
  }, [appointments, tz]);

  function colorFor(a: BookingAppointment): string {
    return serviceColor.get(a.service_id) ?? EVENT_PALETTE[0];
  }

  function eventLabel(a: BookingAppointment): string {
    const who = a.customer_name || "Booking";
    return `${timeLabel(a.start_utc, tz)} ${who}`.trim();
  }

  // ── Navigation ──────────────────────────────────────────────────────────────
  function step(dir: -1 | 1) {
    setCursor((c) => {
      const next = new Date(c);
      if (view === "month") next.setMonth(c.getMonth() + dir);
      else if (view === "week") next.setDate(c.getDate() + 7 * dir);
      else next.setDate(c.getDate() + dir);
      return next;
    });
  }

  const heading = useMemo(() => {
    if (view === "day") {
      return new Intl.DateTimeFormat("en-GB", {
        weekday: "short",
        day: "numeric",
        month: "long",
        year: "numeric",
      }).format(cursor);
    }
    if (view === "week") {
      const start = startOfWeek(cursor);
      const end = new Date(start);
      end.setDate(start.getDate() + 6);
      const fmt = (d: Date) =>
        new Intl.DateTimeFormat("en-GB", { day: "numeric", month: "short" }).format(d);
      return `${fmt(start)} – ${fmt(end)} ${end.getFullYear()}`;
    }
    return `${MONTH_LABELS[cursor.getMonth()]} ${cursor.getFullYear()}`;
  }, [view, cursor]);

  return (
    <div className="rounded-xl border border-zinc-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-900">
      {/* Toolbar */}
      <div className="mb-4 flex items-center justify-between gap-3">
        <div className="flex items-center gap-1.5">
          <button
            type="button"
            onClick={() => step(-1)}
            aria-label="Previous"
            className={`rounded-lg border border-zinc-200 p-1.5 text-zinc-500 transition-colors hover:border-accent/50 hover:text-accent dark:border-zinc-700 dark:text-zinc-400 ${dashAccent.focusRing}`}
          >
            <ChevronLeft className="h-4 w-4" />
          </button>
          <button
            type="button"
            onClick={() => step(1)}
            aria-label="Next"
            className={`rounded-lg border border-zinc-200 p-1.5 text-zinc-500 transition-colors hover:border-accent/50 hover:text-accent dark:border-zinc-700 dark:text-zinc-400 ${dashAccent.focusRing}`}
          >
            <ChevronRight className="h-4 w-4" />
          </button>
          <p className="ml-1 text-sm font-semibold text-zinc-900 dark:text-zinc-100">{heading}</p>
        </div>

        {/* View segmented control */}
        <div
          role="group"
          aria-label="Calendar view"
          className="inline-flex rounded-lg border border-zinc-200 bg-zinc-50 p-0.5 dark:border-zinc-700 dark:bg-zinc-800/50"
        >
          {(["month", "week", "day"] as View[]).map((v) => {
            const active = view === v;
            return (
              <button
                key={v}
                type="button"
                aria-pressed={active}
                onClick={() => setView(v)}
                className={`cursor-pointer rounded-md px-3 py-1 text-xs font-medium capitalize transition-colors ${dashAccent.focusRing} ${
                  active
                    ? "bg-white text-zinc-900 shadow-sm dark:bg-zinc-700 dark:text-zinc-100"
                    : "text-zinc-500 hover:text-zinc-700 dark:text-zinc-400 dark:hover:text-zinc-200"
                }`}
              >
                {v}
              </button>
            );
          })}
        </div>
      </div>

      {/* Body — crossfade on view / period change. Default (sync) mode mounts the
          incoming view immediately so it's interactive without waiting on the exit.
          The exiting child is absolutely positioned over this relative wrapper. */}
      <div className="relative">
        <AnimatePresence initial={false}>
          <motion.div
            key={`${view}-${localDayKey(cursor)}`}
            initial={reduced ? false : { opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={reduced ? undefined : { opacity: 0, position: "absolute", inset: 0 }}
            transition={{ duration: 0.18, ease: FADE }}
          >
            {view === "month" && (
              <MonthView
                cursor={cursor}
                todayKey={todayKey}
                byDay={byDay}
                colorFor={colorFor}
                eventLabel={eventLabel}
                onSelectAppointment={onSelectAppointment}
              />
            )}
            {view === "week" && (
              <WeekView
                cursor={cursor}
                todayKey={todayKey}
                byDay={byDay}
                colorFor={colorFor}
                eventLabel={eventLabel}
                onSelectAppointment={onSelectAppointment}
              />
            )}
            {view === "day" && (
              <DayView
                cursor={cursor}
                todayKey={todayKey}
                byDay={byDay}
                colorFor={colorFor}
                eventLabel={eventLabel}
                onSelectAppointment={onSelectAppointment}
              />
            )}
          </motion.div>
        </AnimatePresence>
      </div>
    </div>
  );
}

// ── Shared sub-pieces ───────────────────────────────────────────────────────

interface ViewProps {
  cursor: Date;
  todayKey: string;
  byDay: Map<string, BookingAppointment[]>;
  colorFor: (a: BookingAppointment) => string;
  eventLabel: (a: BookingAppointment) => string;
  onSelectAppointment: (a: BookingAppointment) => void;
}

function startOfWeek(d: Date): Date {
  const out = new Date(d);
  const offset = (out.getDay() + 6) % 7; // Mon-first
  out.setDate(out.getDate() - offset);
  out.setHours(0, 0, 0, 0);
  return out;
}

function EventChip({
  appt,
  color,
  label,
  onSelect,
}: {
  appt: BookingAppointment;
  color: string;
  label: string;
  onSelect: (a: BookingAppointment) => void;
}) {
  return (
    <button
      type="button"
      onClick={() => onSelect(appt)}
      title={label}
      className="flex w-full cursor-pointer items-center gap-1 rounded px-1 py-0.5 text-left text-[10px] leading-tight text-zinc-700 transition-colors hover:bg-zinc-100 dark:text-zinc-300 dark:hover:bg-zinc-800"
    >
      <span
        className="inline-block h-1.5 w-1.5 shrink-0 rounded-full"
        style={{ backgroundColor: color }}
        aria-hidden="true"
      />
      <span className="truncate">{label}</span>
    </button>
  );
}

// ── Month ───────────────────────────────────────────────────────────────────

function MonthView({
  cursor,
  todayKey,
  byDay,
  colorFor,
  eventLabel,
  onSelectAppointment,
}: ViewProps) {
  const weeks = monthMatrix(cursor.getFullYear(), cursor.getMonth());
  return (
    <div>
      <div className="grid grid-cols-7 gap-1 pb-1 text-center">
        {WEEKDAY_LABELS.map((d) => (
          <div key={d} className="text-[11px] font-medium text-zinc-400 dark:text-zinc-500">
            {d}
          </div>
        ))}
      </div>
      <div className="grid grid-cols-7 gap-1">
        {weeks.flat().map((day) => {
          const key = localDayKey(day);
          const inMonth = day.getMonth() === cursor.getMonth();
          const isToday = key === todayKey;
          const events = byDay.get(key) ?? [];
          return (
            <div
              key={key}
              data-testid={isToday ? "calendar-today" : undefined}
              className={`min-h-[68px] rounded-lg border p-1 ${
                isToday
                  ? `border-transparent ${dashAccent.todayMarker}`
                  : "border-zinc-100 dark:border-zinc-800/60"
              } ${inMonth ? "" : "opacity-40"}`}
            >
              <div
                className={`mb-0.5 text-right text-[11px] tabular-nums ${
                  isToday ? "font-semibold" : "text-zinc-400 dark:text-zinc-500"
                }`}
              >
                {day.getDate()}
              </div>
              <div className="space-y-0.5">
                {events.slice(0, 3).map((a) => (
                  <EventChip
                    key={a.id}
                    appt={a}
                    color={colorFor(a)}
                    label={eventLabel(a)}
                    onSelect={onSelectAppointment}
                  />
                ))}
                {events.length > 3 && (
                  <span className="block px-1 text-[10px] text-zinc-400 dark:text-zinc-500">
                    +{events.length - 3} more
                  </span>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ── Week ────────────────────────────────────────────────────────────────────

function WeekView({
  cursor,
  todayKey,
  byDay,
  colorFor,
  eventLabel,
  onSelectAppointment,
}: ViewProps) {
  const start = startOfWeek(cursor);
  const days = Array.from({ length: 7 }, (_, i) => {
    const d = new Date(start);
    d.setDate(start.getDate() + i);
    return d;
  });
  return (
    <div data-testid="calendar-week-view" className="grid grid-cols-7 gap-1">
      {days.map((day) => {
        const key = localDayKey(day);
        const isToday = key === todayKey;
        const events = byDay.get(key) ?? [];
        return (
          <div
            key={key}
            className={`min-h-[160px] rounded-lg border p-1.5 ${
              isToday
                ? `border-transparent ${dashAccent.todayMarker}`
                : "border-zinc-100 dark:border-zinc-800/60"
            }`}
          >
            <div className="mb-1 text-center">
              <div className="text-[10px] uppercase text-zinc-400 dark:text-zinc-500">
                {WEEKDAY_LABELS[(day.getDay() + 6) % 7]}
              </div>
              <div
                className={`text-sm tabular-nums ${isToday ? "font-semibold" : "text-zinc-700 dark:text-zinc-300"}`}
              >
                {day.getDate()}
              </div>
            </div>
            <div className="space-y-0.5">
              {events.map((a) => (
                <EventChip
                  key={a.id}
                  appt={a}
                  color={colorFor(a)}
                  label={eventLabel(a)}
                  onSelect={onSelectAppointment}
                />
              ))}
            </div>
          </div>
        );
      })}
    </div>
  );
}

// ── Day ─────────────────────────────────────────────────────────────────────

function DayView({
  cursor,
  todayKey,
  byDay,
  colorFor,
  eventLabel,
  onSelectAppointment,
}: ViewProps) {
  const key = localDayKey(cursor);
  const isToday = key === todayKey;
  const events = byDay.get(key) ?? [];
  return (
    <div data-testid="calendar-day-view">
      <div
        className={`rounded-lg border p-3 ${
          isToday
            ? `border-transparent ${dashAccent.todayMarker}`
            : "border-zinc-100 dark:border-zinc-800/60"
        }`}
      >
        {events.length === 0 ? (
          <p className="py-8 text-center text-sm text-zinc-400 dark:text-zinc-500">
            No bookings on this day.
          </p>
        ) : (
          <ul className="space-y-1.5">
            {events.map((a) => (
              <li key={a.id}>
                <button
                  type="button"
                  onClick={() => onSelectAppointment(a)}
                  className="flex w-full cursor-pointer items-center gap-2 rounded-lg px-2 py-2 text-left transition-colors hover:bg-zinc-50 dark:hover:bg-zinc-800/60"
                >
                  <span
                    className="inline-block h-2.5 w-2.5 shrink-0 rounded-full"
                    style={{ backgroundColor: colorFor(a) }}
                    aria-hidden="true"
                  />
                  <span className="text-sm text-zinc-800 dark:text-zinc-200">{eventLabel(a)}</span>
                  {a.service_name && (
                    <span className="ml-auto text-xs text-zinc-400 dark:text-zinc-500">
                      {a.service_name}
                    </span>
                  )}
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
