"use client";

import { useEffect, useState } from "react";
import { Plus, Trash2 } from "lucide-react";
import { useQuery } from "@/hooks/useQuery";
import { ArcSpinner } from "@/components/ui/ArcSpinner";
import {
  dashboardInputCn,
  dashboardFieldLabelCn,
  dashboardSectionCardCn,
  dashboardErrorBannerCn,
  dashboardSuccessBannerCn,
} from "@/lib/styles";
import { getHours, putHours, createException, deleteException } from "./api";
import type { BookingHour, BookingException } from "./api";

interface Props {
  projectSlug: string;
}

const WEEKDAYS = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"];

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

/**
 * Weekly hours grid + closed-dates panel — business-level (resource_id null).
 * Save via PUT /hours (full replace). Exceptions via POST/DELETE /exceptions.
 */
export function HoursEditor({ projectSlug }: Props) {
  const hoursKey = `booking-hours:${projectSlug}`;

  const { data: raw, loading } = useQuery(hoursKey, () => getHours(projectSlug), {
    ttl: 60 * 1000,
  });

  const [rows, setRows] = useState<WeekdayRow[]>(() =>
    WEEKDAYS.map((_, i) => ({ weekday: i, intervals: [] }))
  );
  const [exceptions, setExceptions] = useState<BookingException[]>([]);
  const [saving, setSaving] = useState(false);
  const [hoursMsg, setHoursMsg] = useState<{ type: "ok" | "err"; text: string } | null>(null);

  // Exception form
  const [newDate, setNewDate] = useState("");
  const [addingException, setAddingException] = useState(false);
  const [excError, setExcError] = useState<string | null>(null);

  useEffect(() => {
    if (raw) {
      setRows(hoursToWeekdays(raw.hours ?? []));
      setExceptions(raw.exceptions ?? []);
    }
  }, [raw]);

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
          resource_id: null,
          weekday: r.weekday,
          start_time: iv.start_time,
          end_time: iv.end_time,
        }))
      );
      await putHours(projectSlug, { hours });
      setHoursMsg({ type: "ok", text: "Hours saved." });
    } catch (err) {
      setHoursMsg({
        type: "err",
        text: err instanceof Error ? err.message : "Save failed.",
      });
    } finally {
      setSaving(false);
    }
  }

  async function handleAddException() {
    if (!newDate.trim()) {
      setExcError("Date is required.");
      return;
    }
    setAddingException(true);
    setExcError(null);
    try {
      const exc = await createException(projectSlug, { date: newDate.trim(), is_closed: true });
      setExceptions((prev) => [...prev, exc]);
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
      setExceptions((prev) => prev.filter((e) => e.id !== id));
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
      {/* Weekly hours */}
      <div>
        <h2 className="mb-4 text-sm font-semibold text-zinc-700 dark:text-zinc-300">
          Weekly hours
        </h2>
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
                    <input
                      type="time"
                      value={iv.start_time}
                      onChange={(e) =>
                        updateInterval(row.weekday, idx, "start_time", e.target.value)
                      }
                      className={`${dashboardInputCn} w-32`}
                    />
                    <span className="text-xs text-zinc-400">to</span>
                    <input
                      type="time"
                      value={iv.end_time}
                      onChange={(e) => updateInterval(row.weekday, idx, "end_time", e.target.value)}
                      className={`${dashboardInputCn} w-32`}
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
          Closed dates
        </h2>

        <div className={`${dashboardSectionCardCn} p-4`}>
          <div className="flex items-end gap-3">
            <div className="flex-1">
              <label className={dashboardFieldLabelCn}>Date</label>
              <input
                type="date"
                value={newDate}
                onChange={(e) => {
                  setNewDate(e.target.value);
                  setExcError(null);
                }}
                className={dashboardInputCn}
              />
            </div>
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
          {excError && <p className="mt-1.5 text-xs text-red-600 dark:text-red-400">{excError}</p>}

          {exceptions.length === 0 && (
            <p className="mt-4 text-sm text-zinc-400 dark:text-zinc-500">No closed dates.</p>
          )}

          {exceptions.length > 0 && (
            <ul className="mt-4 space-y-1.5">
              {exceptions.map((exc) => (
                <li key={exc.id} className="flex items-center justify-between text-sm">
                  <span className="font-mono text-zinc-700 dark:text-zinc-300">{exc.date}</span>
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
