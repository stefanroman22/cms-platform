"use client";

import { useEffect, useMemo, useState } from "react";
import { Plus, Trash2, Users } from "lucide-react";
import { useQuery } from "@/hooks/useQuery";
import { ArcSpinner } from "@/components/ui/ArcSpinner";
import {
  dashboardInputCn,
  dashboardFieldLabelCn,
  dashboardSectionCardCn,
  dashboardErrorBannerCn,
  dashboardSuccessBannerCn,
} from "@/lib/styles";
import * as cache from "@/lib/cache";
import { getHours, putHours, createException, deleteException, listResources } from "./api";
import type { BookingHour, BookingException, BookingResource } from "./api";
import { createOverviewPrefs } from "./overview/prefsStore";
import { DatePicker } from "@/components/dashboard/DatePicker";
import { TimePicker } from "@/components/dashboard/TimePicker";

interface Props {
  projectSlug: string;
}

const WEEKDAYS = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"];

// "" = business-wide default (resource_id null); otherwise a staff resource_id.
const BUSINESS = "";

type Interval = { start_time: string; end_time: string };
type WeekdayRow = { weekday: number; intervals: Interval[] };

function hoursToWeekdays(hours: BookingHour[]): WeekdayRow[] {
  const map = new Map<number, Interval[]>();
  for (const h of hours) {
    if (!map.has(h.weekday)) map.set(h.weekday, []);
    map.get(h.weekday)!.push({ start_time: h.start_time, end_time: h.end_time });
  }
  return WEEKDAYS.map((_, i) => ({ weekday: i, intervals: map.get(i) ?? [] }));
}

/** Rows belonging to a scope: the business default ("") matches null resource_id;
 * a staff scope matches that resource_id exactly. */
function inScope<T extends { resource_id?: string | null }>(rows: T[], scope: string): T[] {
  return rows.filter((r) => (scope === BUSINESS ? r.resource_id == null : r.resource_id === scope));
}

/**
 * Weekly hours grid + closed-dates panel, scoped per staff member.
 *
 * A barber edits THEIR OWN calendar by picking themselves in the scope switcher;
 * "Business default" edits the fallback hours used by any staff with no own rows.
 * Saving one scope never wipes another (the backend PUT /hours is scope-aware).
 * The chosen scope is persisted in localStorage (shared with the Overview), so a
 * barber opening the dashboard on their own device lands on their own calendar.
 */
export function HoursEditor({ projectSlug }: Props) {
  const prefs = useMemo(() => createOverviewPrefs(projectSlug), [projectSlug]);
  // Map the shared viewing scope ("all" | resource_id) onto the editable scope
  // ("" business-default | resource_id).
  const [scope, setScope] = useState<string>(() => {
    const s = prefs.getScope();
    return s === "all" ? BUSINESS : s;
  });

  const hoursKey = `booking-hours:${projectSlug}`;
  const { data: raw, loading } = useQuery(hoursKey, () => getHours(projectSlug), {
    ttl: 60 * 1000,
  });
  const { data: resData } = useQuery(`booking-resources:${projectSlug}`, () =>
    listResources(projectSlug)
  );
  const staff: BookingResource[] = (resData?.resources ?? []).filter((r) => r.is_active !== false);

  // All rows for the tenant (every scope); the visible grid is derived per scope.
  const [allHours, setAllHours] = useState<BookingHour[]>([]);
  const [allExceptions, setAllExceptions] = useState<BookingException[]>([]);
  const [rows, setRows] = useState<WeekdayRow[]>(() =>
    WEEKDAYS.map((_, i) => ({ weekday: i, intervals: [] }))
  );
  const [saving, setSaving] = useState(false);
  const [hoursMsg, setHoursMsg] = useState<{ type: "ok" | "err"; text: string } | null>(null);
  // True when a staff member has no personal hours yet, so the grid is showing
  // the (read-derived) business default as a starting point.
  const [inherited, setInherited] = useState(false);

  const [newDate, setNewDate] = useState("");
  const [excMode, setExcMode] = useState<"all_day" | "custom">("all_day");
  const [excStart, setExcStart] = useState("09:00");
  const [excEnd, setExcEnd] = useState("13:00");
  const [addingException, setAddingException] = useState(false);
  const [excError, setExcError] = useState<string | null>(null);

  useEffect(() => {
    if (raw) {
      setAllHours(raw.hours ?? []);
      setAllExceptions(raw.exceptions ?? []);
    }
  }, [raw]);

  // Re-derive the weekly grid whenever the scope or the underlying rows change.
  // A staff member with no personal hours inherits the business default: we show
  // those hours as the starting point WITHOUT persisting anything, so the backend
  // fallback (this staff is bookable on business hours) stays intact until the
  // owner explicitly edits & saves their own schedule.
  useEffect(() => {
    const own = inScope(allHours, scope);
    if (scope !== BUSINESS && own.length === 0) {
      setRows(hoursToWeekdays(inScope(allHours, BUSINESS)));
      setInherited(true);
    } else {
      setRows(hoursToWeekdays(own));
      setInherited(false);
    }
    setHoursMsg(null);
  }, [allHours, scope]);

  const scopeExceptions = inScope(allExceptions, scope);

  function changeScope(next: string) {
    setScope(next);
    prefs.setScope(next === BUSINESS ? "all" : next);
  }

  function addInterval(weekday: number) {
    setRows((prev) =>
      prev.map((r) =>
        r.weekday === weekday
          ? { ...r, intervals: [...r.intervals, { start_time: "09:00", end_time: "17:00" }] }
          : r
      )
    );
  }

  function removeInterval(weekday: number, idx: number) {
    setRows((prev) =>
      prev.map((r) =>
        r.weekday === weekday ? { ...r, intervals: r.intervals.filter((_, i) => i !== idx) } : r
      )
    );
  }

  function updateInterval(weekday: number, idx: number, field: keyof Interval, value: string) {
    setRows((prev) =>
      prev.map((r) =>
        r.weekday === weekday
          ? {
              ...r,
              intervals: r.intervals.map((iv, i) => (i === idx ? { ...iv, [field]: value } : iv)),
            }
          : r
      )
    );
  }

  async function handleSaveHours() {
    setSaving(true);
    setHoursMsg(null);
    try {
      const hours = rows.flatMap((r) =>
        r.intervals.map((iv) => ({
          weekday: r.weekday,
          start_time: iv.start_time,
          end_time: iv.end_time,
        }))
      );
      const res = await putHours(projectSlug, { resource_id: scope || null, hours });
      // Server returns ALL scopes' rows — refresh the master list.
      setAllHours(res.hours ?? []);
      // Write through the shared `booking-hours:${slug}` cache so the Overview
      // day-window reflects this edit on its next mount (preserve exceptions —
      // putHours returns hours only).
      cache.set(hoursKey, { hours: res.hours ?? [], exceptions: allExceptions });
      setHoursMsg({ type: "ok", text: "Hours saved." });
    } catch (err) {
      setHoursMsg({ type: "err", text: err instanceof Error ? err.message : "Save failed." });
    } finally {
      setSaving(false);
    }
  }

  async function handleAddException() {
    if (!newDate.trim()) {
      setExcError("Date is required.");
      return;
    }
    if (excMode === "custom" && excStart >= excEnd) {
      setExcError("Closing time must be after the opening time.");
      return;
    }
    setAddingException(true);
    setExcError(null);
    try {
      // all_day  => fully closed (is_closed=true).
      // custom   => open ONLY during [start,end] for that date; everything else
      //             that day is closed. This is the backend's day-override and is
      //             what actually constrains the public scheduler.
      const body =
        excMode === "all_day"
          ? { date: newDate.trim(), is_closed: true, resource_id: scope || null }
          : {
              date: newDate.trim(),
              is_closed: false,
              start_time: excStart,
              end_time: excEnd,
              resource_id: scope || null,
            };
      const exc = await createException(projectSlug, body);
      setAllExceptions((prev) => [...prev, exc]);
      setNewDate("");
    } catch (err) {
      setExcError(err instanceof Error ? err.message : "Failed to add closed date.");
    } finally {
      setAddingException(false);
    }
  }

  async function handleDeleteException(id: string) {
    try {
      await deleteException(projectSlug, id);
      setAllExceptions((prev) => prev.filter((e) => e.id !== id));
    } catch {
      // silently ignore — user can retry
    }
  }

  if (loading) {
    return (
      <div className="flex items-center gap-3 rounded-xl border border-zinc-200 bg-white/40 px-6 py-8 text-sm text-zinc-500 dark:border-zinc-800 dark:bg-zinc-900/40 dark:text-zinc-400">
        <ArcSpinner size={20} />
        Loading hours…
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Scope switcher — whose calendar are we editing? */}
      {staff.length > 0 && (
        <div className={`${dashboardSectionCardCn} flex flex-wrap items-center gap-3 p-4`}>
          <span className="inline-flex items-center gap-1.5 text-sm font-medium text-zinc-700 dark:text-zinc-300">
            <Users className="h-4 w-4 text-zinc-400" aria-hidden="true" />
            Editing calendar for
          </span>
          <select
            value={scope}
            onChange={(e) => changeScope(e.target.value)}
            className={`${dashboardInputCn} max-w-xs`}
            aria-label="Staff calendar to edit"
          >
            <option value={BUSINESS}>Business default (all staff)</option>
            {staff.map((s) => (
              <option key={s.id} value={s.id}>
                {s.name}
              </option>
            ))}
          </select>
          <p className="w-full text-xs text-zinc-400 dark:text-zinc-500">
            {scope === BUSINESS
              ? "Fallback hours used by any staff member who has no personal hours set."
              : "Personal hours for this staff member — they override the business default."}
          </p>
        </div>
      )}

      {/* Weekly hours */}
      <div>
        <h2 className="mb-4 text-sm font-semibold text-zinc-700 dark:text-zinc-300">
          Weekly hours
        </h2>
        {inherited && (
          <p className="mb-3 rounded-lg border border-accent/30 bg-accent/10 px-3 py-2 text-xs text-zinc-600 dark:text-zinc-300">
            Showing the <span className="font-medium">business default</span> — this staff member
            has no personal hours yet. Edit and save to give them their own schedule; the business
            hours stay unchanged.
          </p>
        )}
        <div className={`${dashboardSectionCardCn} divide-y divide-zinc-100 dark:divide-zinc-800`}>
          {rows.map((row) => (
            <div key={row.weekday} className="px-4 py-3">
              <div className="flex items-center justify-between">
                <span className="w-24 text-sm font-medium text-zinc-700 dark:text-zinc-300">
                  {WEEKDAYS[row.weekday]}
                </span>
                <button
                  type="button"
                  onClick={() => addInterval(row.weekday)}
                  className="inline-flex cursor-pointer items-center gap-1 rounded-md border border-zinc-200 px-2 py-1 text-xs text-zinc-500 transition-colors hover:border-zinc-300 hover:text-zinc-700 dark:border-zinc-700 dark:text-zinc-400 dark:hover:border-zinc-600 dark:hover:text-zinc-200"
                >
                  <Plus className="h-3 w-3" />
                  Add
                </button>
              </div>
              {row.intervals.length === 0 && (
                <p className="mt-1 text-xs text-zinc-400 dark:text-zinc-500">Closed</p>
              )}
              <div className="mt-2 space-y-2">
                {row.intervals.map((iv, idx) => (
                  <div key={idx} className="flex items-center gap-2">
                    <TimePicker
                      value={iv.start_time}
                      onChange={(v) => updateInterval(row.weekday, idx, "start_time", v)}
                      ariaLabel="Opens at"
                      className="w-28"
                    />
                    <span className="text-xs text-zinc-400">to</span>
                    <TimePicker
                      value={iv.end_time}
                      onChange={(v) => updateInterval(row.weekday, idx, "end_time", v)}
                      ariaLabel="Closes at"
                      className="w-28"
                    />
                    <button
                      type="button"
                      onClick={() => removeInterval(row.weekday, idx)}
                      aria-label="Remove interval"
                      className="inline-flex cursor-pointer items-center justify-center rounded-md p-1 text-zinc-400 transition-colors hover:bg-red-50 hover:text-red-500 dark:hover:bg-red-950/30 dark:hover:text-red-400"
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </button>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>

        {hoursMsg && (
          <div
            className={`mt-3 ${hoursMsg.type === "ok" ? dashboardSuccessBannerCn : dashboardErrorBannerCn}`}
          >
            {hoursMsg.text}
          </div>
        )}

        <div className="mt-4 flex justify-end">
          <button
            type="button"
            onClick={() => {
              handleSaveHours().catch(() => {});
            }}
            disabled={saving}
            className="cursor-pointer rounded-lg bg-zinc-900 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-zinc-700 disabled:cursor-not-allowed disabled:opacity-40 dark:bg-zinc-700 dark:hover:bg-zinc-600"
          >
            {saving ? "Saving…" : "Save hours"}
          </button>
        </div>
      </div>

      {/* Closed dates / exceptions */}
      <div>
        <h2 className="mb-4 text-sm font-semibold text-zinc-700 dark:text-zinc-300">
          {scope === BUSINESS ? "Closed dates" : "Holidays / time off"}
        </h2>

        <div className={`${dashboardSectionCardCn} p-4`}>
          {/* All-day vs custom-hours toggle */}
          <div
            role="group"
            aria-label="Closure type"
            className="mb-3 inline-flex rounded-lg border border-zinc-200 bg-zinc-50 p-0.5 dark:border-zinc-700 dark:bg-zinc-800/50"
          >
            {(
              [
                ["all_day", "Closed all day"],
                ["custom", "Custom hours"],
              ] as const
            ).map(([mode, label]) => {
              const active = excMode === mode;
              return (
                <button
                  key={mode}
                  type="button"
                  aria-pressed={active}
                  onClick={() => {
                    setExcMode(mode);
                    setExcError(null);
                  }}
                  className={`cursor-pointer rounded-md px-3 py-1 text-xs font-medium transition-colors ${
                    active
                      ? "bg-white text-zinc-900 shadow-sm dark:bg-zinc-700 dark:text-zinc-100"
                      : "text-zinc-500 hover:text-zinc-700 dark:text-zinc-400 dark:hover:text-zinc-200"
                  }`}
                >
                  {label}
                </button>
              );
            })}
          </div>

          <div className="flex flex-wrap items-end gap-3">
            <div className="min-w-[10rem] flex-1">
              <label className={dashboardFieldLabelCn}>Date</label>
              <DatePicker
                value={newDate}
                onChange={(v) => {
                  setNewDate(v);
                  setExcError(null);
                }}
                ariaLabel="Closed date"
              />
            </div>
            {excMode === "custom" && (
              <>
                <div>
                  <label className={dashboardFieldLabelCn}>Open from</label>
                  <TimePicker
                    value={excStart}
                    onChange={(v) => {
                      setExcStart(v);
                      setExcError(null);
                    }}
                    ariaLabel="Open from"
                    className="w-28"
                  />
                </div>
                <div>
                  <label className={dashboardFieldLabelCn}>Open until</label>
                  <TimePicker
                    value={excEnd}
                    onChange={(v) => {
                      setExcEnd(v);
                      setExcError(null);
                    }}
                    ariaLabel="Open until"
                    className="w-28"
                  />
                </div>
              </>
            )}
            <button
              type="button"
              onClick={() => {
                handleAddException().catch(() => {});
              }}
              disabled={addingException}
              className="inline-flex cursor-pointer items-center gap-1.5 rounded-lg bg-zinc-900 px-3 py-2 text-sm font-medium text-white transition-colors hover:bg-zinc-700 disabled:cursor-not-allowed disabled:opacity-40 dark:bg-zinc-700 dark:hover:bg-zinc-600"
            >
              <Plus className="h-4 w-4" />
              Add
            </button>
          </div>
          <p className="mt-1.5 text-xs text-zinc-400 dark:text-zinc-500">
            {excMode === "all_day"
              ? `Fully closed that day${scope === BUSINESS ? " for the whole business" : " for this staff member"}.`
              : "Open only during these hours that day — the rest of the day is closed to bookings."}
          </p>
          {excError && <p className="mt-1.5 text-xs text-red-600 dark:text-red-400">{excError}</p>}

          {scopeExceptions.length === 0 && (
            <p className="mt-4 text-sm text-zinc-400 dark:text-zinc-500">
              {scope === BUSINESS ? "No closed dates." : "No holidays for this staff member."}
            </p>
          )}

          {scopeExceptions.length > 0 && (
            <ul className="mt-4 space-y-1.5">
              {scopeExceptions.map((exc) => (
                <li key={exc.id} className="flex items-center justify-between gap-3 text-sm">
                  <span className="flex flex-wrap items-center gap-2">
                    <span className="font-mono text-zinc-700 dark:text-zinc-300">{exc.date}</span>
                    <span className="rounded-full bg-zinc-100 px-2 py-0.5 text-[11px] font-medium text-zinc-500 dark:bg-zinc-800 dark:text-zinc-400">
                      {exc.is_closed === false && exc.start_time && exc.end_time
                        ? `Open ${exc.start_time.slice(0, 5)}–${exc.end_time.slice(0, 5)}`
                        : "Closed all day"}
                    </span>
                  </span>
                  <button
                    type="button"
                    onClick={() => handleDeleteException(exc.id)}
                    aria-label={`Remove closed date ${exc.date}`}
                    className="inline-flex cursor-pointer items-center gap-1 text-xs text-zinc-400 transition-colors hover:text-red-500 dark:text-zinc-500 dark:hover:text-red-400"
                  >
                    <Trash2 className="h-3 w-3" />
                    Remove
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </div>
  );
}
