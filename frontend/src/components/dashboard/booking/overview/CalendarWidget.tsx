"use client";

import { useMemo, useState } from "react";
import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import { CalendarOff, ChevronLeft, ChevronRight } from "lucide-react";
import { monthMatrix, MONTH_LABELS, WEEKDAY_LABELS } from "@/lib/bookingDates";
import { dashAccent } from "@/lib/dashboardTheme";
import type { BookingAppointment, BookingHour, BookingResource, BookingService } from "../api";
import { StaffAvatar } from "../StaffAvatar";
import type { CalendarView } from "./prefsStore";

interface Props {
  appointments: BookingAppointment[];
  services: BookingService[];
  /** Active staff — drives the day-view columns + avatars. */
  staff?: BookingResource[];
  /** "all" | resource_id — when a single staff is scoped, the day view shows one column. */
  scope?: string;
  /** Working hours (business default + per-staff). Drives the day-view time window:
   *  business schedule for "all", the selected staff's schedule when one is scoped. */
  hours?: BookingHour[];
  timezone: string | null;
  onSelectAppointment: (a: BookingAppointment) => void;
  /** Controlled view (persisted by the parent). When omitted, the widget owns its own state. */
  view?: CalendarView;
  onViewChange?: (v: CalendarView) => void;
  /** Initial view when uncontrolled. Day-first by request. */
  defaultView?: CalendarView;
}

const FADE = [0.16, 1, 0.3, 1] as const;

// Fallback event palette when a service has no explicit color (mirrors the
// by-service chart palette so the two widgets read as one system).
const EVENT_PALETTE = ["#10b981", "#3b82f6", "#8b5cf6", "#f59e0b", "#ef4444", "#06b6d4", "#84cc16"];

// Day timeline geometry.
const HOUR_PX = 56; // height of one hour row
const DEFAULT_START_HOUR = 8;
const DEFAULT_END_HOUR = 20;

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

/** "HH:MM" → fractional hour, floored or ceiled to a whole hour. */
function timeToHour(t: string, mode: "floor" | "ceil"): number | null {
  const m = /^(\d{1,2}):(\d{2})/.exec(t);
  if (!m) return null;
  const h = Number(m[1]) + Number(m[2]) / 60;
  return mode === "floor" ? Math.floor(h) : Math.ceil(h);
}

/** The working-hours rows that define the day-view window for a given scope + weekday.
 *  - "all" → the business-default rows (resource_id null).
 *  - a single staff → that staff's own rows; but if they have NO personal hours at
 *    all, inherit the business default (mirrors the per-staff schedule model, where
 *    a staff with no hours of their own follows the business hours). */
function scheduleRowsFor(hours: BookingHour[], scope: string, weekday: number): BookingHour[] {
  const sameDay = hours.filter((h) => h.weekday === weekday);
  if (scope === "all") return sameDay.filter((h) => h.resource_id == null);
  const hasOwnHours = hours.some((h) => h.resource_id === scope);
  return hasOwnHours
    ? sameDay.filter((h) => h.resource_id === scope)
    : sameDay.filter((h) => h.resource_id == null);
}

/** Minutes-from-midnight of a UTC instant rendered in the tenant timezone. */
function minutesInTz(utc: string, tz: string): number {
  try {
    const parts = new Intl.DateTimeFormat("en-GB", {
      timeZone: tz,
      hour: "2-digit",
      minute: "2-digit",
      hour12: false,
    }).formatToParts(new Date(utc));
    const h = Number(parts.find((p) => p.type === "hour")?.value ?? "0") % 24;
    const m = Number(parts.find((p) => p.type === "minute")?.value ?? "0");
    return h * 60 + m;
  } catch {
    return 0;
  }
}

export function CalendarWidget({
  appointments,
  services,
  staff = [],
  scope = "all",
  hours = [],
  timezone,
  onSelectAppointment,
  view: controlledView,
  onViewChange,
  defaultView = "day",
}: Props) {
  const tz = timezone ?? "UTC";
  const reduced = useReducedMotion();

  const [internalView, setInternalView] = useState<CalendarView>(defaultView);
  const view = controlledView ?? internalView;
  function setView(v: CalendarView) {
    onViewChange?.(v);
    if (controlledView === undefined) setInternalView(v);
  }

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
    <div className="rounded-xl border border-zinc-200 bg-white p-3 sm:p-4 dark:border-zinc-800 dark:bg-zinc-900">
      {/* Toolbar */}
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <div className="flex min-w-0 items-center gap-1.5">
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
          <p className="ml-1 truncate text-sm font-semibold text-zinc-900 dark:text-zinc-100">
            {heading}
          </p>
        </div>

        {/* View segmented control — day-first. */}
        <div
          role="group"
          aria-label="Calendar view"
          className="inline-flex rounded-lg border border-zinc-200 bg-zinc-50 p-0.5 dark:border-zinc-700 dark:bg-zinc-800/50"
        >
          {(["day", "week", "month"] as CalendarView[]).map((v) => {
            const active = view === v;
            return (
              <button
                key={v}
                type="button"
                aria-pressed={active}
                onClick={() => setView(v)}
                className={`relative cursor-pointer rounded-md px-3 py-1 text-xs font-medium capitalize transition-colors ${dashAccent.focusRing} ${
                  active
                    ? "text-zinc-900 dark:text-zinc-100"
                    : "text-zinc-500 hover:text-zinc-700 dark:text-zinc-400 dark:hover:text-zinc-200"
                }`}
              >
                {active && (
                  <motion.span
                    layoutId="calendar-view-pill"
                    className="absolute inset-0 rounded-md bg-white shadow-sm dark:bg-zinc-700"
                    transition={
                      reduced
                        ? { duration: 0 }
                        : { type: "spring", stiffness: 480, damping: 36, mass: 0.6 }
                    }
                  />
                )}
                <span className="relative z-10">{v}</span>
              </button>
            );
          })}
        </div>
      </div>

      {/* Body — crossfade on view / period change. */}
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
              <DayTimeline
                cursor={cursor}
                todayKey={todayKey}
                tz={tz}
                staff={staff}
                scope={scope}
                hours={hours}
                events={byDay.get(localDayKey(cursor)) ?? []}
                colorFor={colorFor}
                onSelectAppointment={onSelectAppointment}
                reduced={!!reduced}
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

// ── Day timeline (Fresha-style: staff columns × hour rows) ────────────────────

interface DayTimelineProps {
  cursor: Date;
  todayKey: string;
  tz: string;
  staff: BookingResource[];
  scope: string;
  hours: BookingHour[];
  events: BookingAppointment[];
  colorFor: (a: BookingAppointment) => string;
  onSelectAppointment: (a: BookingAppointment) => void;
  reduced: boolean;
}

function DayTimeline({
  cursor,
  todayKey,
  tz,
  staff,
  scope,
  hours,
  events,
  colorFor,
  onSelectAppointment,
  reduced,
}: DayTimelineProps) {
  // Columns = scoped staff (one when a single member is selected). If the tenant
  // has no resources, fall back to a single "All bookings" column.
  const columns = useMemo(() => {
    const active = staff.filter((s) => s.is_active !== false);
    const scoped = scope !== "all" ? active.filter((s) => s.id === scope) : active;
    if (scoped.length > 0)
      return scoped.map((s) => ({ id: s.id, name: s.name, image_url: s.image_url }));
    return [{ id: "__all__", name: "All bookings", image_url: null as string | null }];
  }, [staff, scope]);

  // Bucket the day's events into their column (by resource_id; unmatched → first column).
  const byColumn = useMemo(() => {
    const map = new Map<string, BookingAppointment[]>();
    columns.forEach((c) => map.set(c.id, []));
    for (const a of events) {
      const colId =
        columns.length === 1
          ? columns[0].id
          : a.resource_id && map.has(a.resource_id)
            ? a.resource_id
            : columns[0].id;
      map.get(colId)!.push(a);
    }
    return map;
  }, [events, columns]);

  // Time window: driven by the relevant working schedule (business hours when
  // "all" staff are shown; the selected staff's hours when one is scoped), then
  // expanded to fit any appointments so nothing is ever clipped.
  const { startHour, endHour, closed } = useMemo(() => {
    const rows = scheduleRowsFor(hours, scope, cursor.getDay());
    let lo: number | null = null;
    let hi: number | null = null;
    for (const r of rows) {
      const s = timeToHour(r.start_time, "floor");
      const e = timeToHour(r.end_time, "ceil");
      if (s != null) lo = lo == null ? s : Math.min(lo, s);
      if (e != null) hi = hi == null ? e : Math.max(hi, e);
    }
    for (const a of events) {
      const s = Math.floor(minutesInTz(a.start_utc, tz) / 60);
      const e = Math.ceil(minutesInTz(a.end_utc, tz) / 60);
      lo = lo == null ? s : Math.min(lo, s);
      hi = hi == null ? e : Math.max(hi, e);
    }
    // Closed: the schedule (which IS loaded — hours non-empty) has no hours for
    // this weekday, and there are no bookings to show. Don't invent a default
    // window — surface that the day is closed, matching the Hours tab.
    if (rows.length === 0 && hours.length > 0 && events.length === 0) {
      return { startHour: DEFAULT_START_HOUR, endHour: DEFAULT_END_HOUR, closed: true };
    }
    if (lo == null || hi == null) {
      lo = DEFAULT_START_HOUR;
      hi = DEFAULT_END_HOUR;
    }
    lo = Math.max(0, lo);
    hi = Math.min(24, hi);
    if (hi - lo < 6) hi = Math.min(24, lo + 6); // keep a readable minimum span
    return { startHour: lo, endHour: hi, closed: false };
  }, [hours, scope, cursor, events, tz]);

  const hourCount = endHour - startHour;
  const bodyHeight = hourCount * HOUR_PX;
  const isToday = localDayKey(cursor) === todayKey;

  // "Now" line position (only when viewing today and within window).
  const nowTop = useMemo(() => {
    if (!isToday) return null;
    const m = minutesInTz(new Date().toISOString(), tz);
    if (m < startHour * 60 || m > endHour * 60) return null;
    return ((m - startHour * 60) / 60) * HOUR_PX;
  }, [isToday, tz, startHour, endHour]);

  const hourLabels = Array.from({ length: hourCount + 1 }, (_, i) => startHour + i);

  // Closed day → mirror the Hours tab (no working hours) instead of an invented
  // default grid. Appointments on a closed day are never hidden (closed is false
  // when events exist), so this only shows when there's genuinely nothing.
  if (closed) {
    const weekday = new Intl.DateTimeFormat("en-GB", { weekday: "long" }).format(cursor);
    return (
      <div
        data-testid="calendar-day-view"
        className="flex flex-col items-center justify-center gap-2 rounded-xl border border-dashed border-zinc-200 px-6 py-14 text-center dark:border-zinc-800"
      >
        <CalendarOff className="h-6 w-6 text-zinc-300 dark:text-zinc-600" aria-hidden="true" />
        <p className="text-sm font-medium text-zinc-500 dark:text-zinc-400">Closed on {weekday}s</p>
        <p className="max-w-xs text-xs text-zinc-400 dark:text-zinc-500">
          {scope === "all"
            ? "No business working hours are set for this day."
            : "This staff member isn’t working this day."}
        </p>
      </div>
    );
  }

  return (
    <div data-testid="calendar-day-view" className="overflow-x-auto">
      <div className="flex min-w-fit">
        {/* Time gutter */}
        <div className="sticky left-0 z-10 w-12 shrink-0 bg-white dark:bg-zinc-900">
          <div className="h-12" aria-hidden="true" /> {/* aligns with column headers */}
          <div className="relative" style={{ height: bodyHeight }}>
            {hourLabels.slice(0, -1).map((h, i) => (
              <div
                key={h}
                className="absolute right-1.5 -translate-y-1/2 text-[10px] tabular-nums text-zinc-400 dark:text-zinc-500"
                style={{ top: i * HOUR_PX }}
              >
                {String(h).padStart(2, "0")}:00
              </div>
            ))}
          </div>
        </div>

        {/* Staff columns */}
        <div className="flex flex-1">
          {columns.map((col) => {
            const colEvents = byColumn.get(col.id) ?? [];
            return (
              <div
                key={col.id}
                className="min-w-[clamp(150px,72vw,260px)] flex-1 border-l border-zinc-100 first:border-l-0 dark:border-zinc-800/70"
              >
                {/* Column header — centered when there's only one staff column,
                    so the lone avatar + name sit in the middle of the timeline. */}
                <div
                  className={`flex h-12 items-center gap-2 px-2 ${
                    columns.length === 1 ? "justify-center" : ""
                  }`}
                >
                  {col.id !== "__all__" && (
                    <StaffAvatar src={col.image_url} name={col.name} size={28} />
                  )}
                  <span className="truncate text-sm font-medium text-zinc-700 dark:text-zinc-200">
                    {col.name}
                  </span>
                </div>

                {/* Column body */}
                <div className="relative" style={{ height: bodyHeight }}>
                  {/* Hour gridlines */}
                  {hourLabels.slice(0, -1).map((h, i) => (
                    <div
                      key={h}
                      className="absolute inset-x-0 border-t border-zinc-100 dark:border-zinc-800/70"
                      style={{ top: i * HOUR_PX }}
                      aria-hidden="true"
                    />
                  ))}

                  {/* Now line */}
                  {nowTop !== null && (
                    <div
                      className="pointer-events-none absolute inset-x-0 z-20 flex items-center"
                      style={{ top: nowTop }}
                      aria-hidden="true"
                    >
                      <span className="h-1.5 w-1.5 -ml-0.5 rounded-full bg-accent" />
                      <span className="h-px flex-1 bg-accent/60" />
                    </div>
                  )}

                  {/* Appointment blocks */}
                  {colEvents.map((a, i) => {
                    const startMin = minutesInTz(a.start_utc, tz);
                    const endMin = Math.max(startMin + 15, minutesInTz(a.end_utc, tz));
                    const top = ((startMin - startHour * 60) / 60) * HOUR_PX;
                    // 28px == a 30-min slot at HOUR_PX=56 — the floor that lets a
                    // short booking still show BOTH the name and the time · service
                    // line (with the tight py-0.5/leading-tight below) WITHOUT a
                    // 30-min block overflowing into the next back-to-back one.
                    const height = Math.max(28, ((endMin - startMin) / 60) * HOUR_PX);
                    const color = colorFor(a);
                    const secondary = a.service_name
                      ? `${timeLabel(a.start_utc, tz)} · ${a.service_name}`
                      : timeLabel(a.start_utc, tz);
                    return (
                      <motion.button
                        key={a.id}
                        type="button"
                        onClick={() => onSelectAppointment(a)}
                        initial={reduced ? false : { opacity: 0, y: 4 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{
                          duration: 0.2,
                          delay: reduced ? 0 : Math.min(i * 0.03, 0.2),
                          ease: FADE,
                        }}
                        title={`${timeLabel(a.start_utc, tz)} · ${a.customer_name ?? "Booking"}${a.service_name ? ` · ${a.service_name}` : ""}`}
                        className="group absolute inset-x-1 z-10 flex cursor-pointer flex-col overflow-hidden rounded-md px-2 py-0.5 text-left leading-tight transition-shadow hover:shadow-md"
                        style={{
                          top,
                          height,
                          backgroundColor: `${color}26`, // ~15% tint
                          borderLeft: `3px solid ${color}`,
                        }}
                      >
                        <span className="truncate text-[11px] font-semibold leading-tight text-zinc-800 dark:text-zinc-100">
                          {a.customer_name ?? "Booking"}
                        </span>
                        <span className="truncate text-[10px] leading-tight text-zinc-500 dark:text-zinc-400">
                          {secondary}
                        </span>
                      </motion.button>
                    );
                  })}

                  {colEvents.length === 0 && columns.length === 1 && (
                    <p className="absolute inset-0 flex items-center justify-center text-sm text-zinc-400 dark:text-zinc-500">
                      No bookings on this day.
                    </p>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
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
