"use client";

import { useEffect, useState } from "react";
import { Clock } from "lucide-react";
import { motion } from "framer-motion";
import { fadeUp, staggerFast } from "@/lib/animations";
import type { Lead } from "../types";
import { EditableSectionShell } from "./EditableSectionShell";
import { useLeadPatch } from "../hooks/useLeadPatch";

interface Props {
  lead: Lead;
  onPatched: (lead: Lead) => void;
}

const DAYS = [
  "Monday",
  "Tuesday",
  "Wednesday",
  "Thursday",
  "Friday",
  "Saturday",
  "Sunday",
] as const;
type Day = (typeof DAYS)[number];

function emptyDraft(hours: Record<string, string> | null): Record<Day, string> {
  return Object.fromEntries(DAYS.map((d) => [d, hours?.[d] ?? ""])) as Record<Day, string>;
}

function draftToServerMap(draft: Record<Day, string>): Record<string, string> {
  const out: Record<string, string> = {};
  for (const d of DAYS) if (draft[d].trim() !== "") out[d] = draft[d].trim();
  return out;
}

function mapsEqual(a: Record<string, string>, b: Record<string, string>): boolean {
  const ak = Object.keys(a).sort();
  const bk = Object.keys(b).sort();
  if (ak.length !== bk.length) return false;
  return ak.every((k, i) => k === bk[i] && a[k] === b[k]);
}

export function OpeningHoursSection({ lead, onPatched }: Props) {
  const { patch, saving, error, clearError } = useLeadPatch(lead.id, onPatched);
  const [draft, setDraft] = useState<Record<Day, string>>(() => emptyDraft(lead.opening_hours));

  useEffect(() => {
    setDraft(emptyDraft(lead.opening_hours));
    clearError();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [lead.id, lead.opening_hours]);

  async function handleSave() {
    const next = draftToServerMap(draft);
    const curr = (lead.opening_hours ?? {}) as Record<string, string>;
    if (mapsEqual(next, curr)) return;
    await patch({ opening_hours: next });
  }

  function handleCancel() {
    setDraft(emptyDraft(lead.opening_hours));
    clearError();
  }

  const readView = (
    <motion.div
      variants={staggerFast}
      initial="hidden"
      animate="visible"
      className="rounded-lg border border-zinc-200 dark:border-zinc-800 bg-zinc-50 dark:bg-zinc-900 divide-y divide-zinc-200 dark:divide-zinc-800"
    >
      {DAYS.map((day) => {
        const v = lead.opening_hours?.[day] ?? "___";
        const placeholder = v === "___";
        return (
          <motion.div
            key={day}
            variants={fadeUp}
            className="flex items-center justify-between px-3 py-2 text-sm"
          >
            <span className="text-zinc-600 dark:text-zinc-400 font-medium">{day}</span>
            <span
              className={
                placeholder
                  ? "text-zinc-400 dark:text-zinc-600 font-mono italic"
                  : "text-zinc-900 dark:text-zinc-100 tabular-nums"
              }
            >
              {v}
            </span>
          </motion.div>
        );
      })}
    </motion.div>
  );

  const editView = (
    <div className="rounded-lg border border-zinc-200 dark:border-zinc-800 bg-zinc-50 dark:bg-zinc-900 divide-y divide-zinc-200 dark:divide-zinc-800">
      {DAYS.map((day) => (
        <div key={day} className="flex items-center gap-2 px-3 py-1.5">
          <span className="w-20 text-xs text-zinc-600 dark:text-zinc-400 font-medium shrink-0">
            {day}
          </span>
          <input
            type="text"
            aria-label={`${day} hours`}
            value={draft[day]}
            onChange={(e) => setDraft((d) => ({ ...d, [day]: e.target.value }))}
            placeholder="9–17, Closed, Open 24 hours…"
            className="flex-1 rounded-md border border-zinc-200 dark:border-zinc-700 bg-white dark:bg-zinc-950 px-2 py-1 text-xs text-zinc-900 dark:text-zinc-100 focus:outline-none focus:ring-2 focus:ring-zinc-400 dark:focus:ring-zinc-600"
          />
          <button
            type="button"
            aria-label={`Mark ${day} closed`}
            onClick={() => setDraft((d) => ({ ...d, [day]: "Closed" }))}
            className="text-[10px] px-1.5 py-0.5 rounded text-zinc-500 dark:text-zinc-400 hover:bg-zinc-200 dark:hover:bg-zinc-800 cursor-pointer transition-colors"
          >
            Closed
          </button>
        </div>
      ))}
    </div>
  );

  return (
    <div className="mt-5">
      <div className="text-xs uppercase tracking-wider text-zinc-500 dark:text-zinc-400 font-semibold mb-2 flex items-center gap-1.5">
        <Clock className="h-3.5 w-3.5" />
      </div>
      <EditableSectionShell
        id="opening_hours"
        title="Opening hours"
        readView={readView}
        editView={editView}
        onSave={handleSave}
        onCancel={handleCancel}
        saving={saving}
        error={error}
        canSave
      />
    </div>
  );
}
