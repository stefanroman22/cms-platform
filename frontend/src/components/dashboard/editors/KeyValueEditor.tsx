"use client";

import { useState } from "react";
import type { EditorProps } from "./index";
import { dashboardInputCn, dashboardFieldLabelCn, dashboardSectionCardCn } from "@/lib/styles";
import { Plus, Trash2 } from "lucide-react";
import { InfoTooltip } from "@/components/dashboard/InfoTooltip";
import {
  ContentField,
  convertValue,
  type FieldFormat,
} from "@/components/dashboard/rich-text/ContentField";

interface KVRow {
  key: string;
  value: string;
}

type Row = KVRow & { id: string; format: FieldFormat; initialFormat: FieldFormat };
let keySeq = 0;
const newKey = () => `k${Date.now().toString(36)}${(keySeq++).toString(36)}`;

function parseFormats(raw: unknown): Record<string, FieldFormat> {
  const out: Record<string, FieldFormat> = {};
  if (raw && typeof raw === "object" && !Array.isArray(raw)) {
    for (const [k, v] of Object.entries(raw as Record<string, unknown>)) {
      if (v === "plain" || v === "inline" || v === "rich") out[k] = v;
    }
  }
  return out;
}

function parseEntries(raw: unknown): KVRow[] {
  if (Array.isArray(raw)) return raw as KVRow[];
  if (raw && typeof raw === "object") {
    return Object.entries(raw as Record<string, string>).map(([key, value]) => ({ key, value }));
  }
  return [];
}

export function KeyValueEditor({
  initialContent,
  onChange,
  richText,
  canEditStructure,
}: EditorProps) {
  const [rows, setRows] = useState<Row[]>(() => {
    const parsed = parseEntries(initialContent.entries);
    const initialFormats = parseFormats(initialContent._formats);
    return (parsed.length > 0 ? parsed : [{ key: "", value: "" }]).map((r) => {
      const format = initialFormats[r.key.trim()] ?? "plain";
      return { ...r, id: newKey(), format, initialFormat: format };
    });
  });
  const hadFormats = "_formats" in initialContent;
  const showFormatSelect = !!richText && !!canEditStructure;

  const blankRow = (): Row => ({
    id: newKey(),
    key: "",
    value: "",
    format: "plain",
    initialFormat: "plain",
  });

  function emit(next: Row[]) {
    setRows(next);
    const entries: Record<string, string> = {};
    const formats: Record<string, FieldFormat> = {};
    for (const { key, value, format } of next) {
      const k = key.trim();
      if (k) {
        entries[k] = value;
        if (format !== "plain") formats[k] = format;
      }
    }
    if (richText || hadFormats) onChange({ entries, _formats: formats });
    else onChange({ entries });
  }

  function updateRow(index: number, field: "key" | "value", val: string) {
    emit(rows.map((r, i) => (i === index ? { ...r, [field]: val } : r)));
  }

  function changeFormat(index: number, to: FieldFormat) {
    emit(
      rows.map((r, i) =>
        i === index ? { ...r, value: convertValue(r.value, r.format, to), format: to } : r
      )
    );
  }

  function addRow() {
    emit([...rows, blankRow()]);
  }

  function removeRow(index: number) {
    const next = rows.filter((_, i) => i !== index);
    emit(next.length > 0 ? next : [blankRow()]);
  }

  // A non-admin's _formats is replaced server-side, so renaming a formatted entry would strand its HTML as plain.
  const keyLocked = (r: Row) => !!richText && !canEditStructure && r.initialFormat !== "plain";
  const LOCK_HINT = "Only an admin can rename formatted entries";

  return (
    <div className={dashboardSectionCardCn}>
      <div className="px-5 py-4 border-b border-zinc-100 dark:border-zinc-800">
        <p className="text-sm font-medium text-zinc-700 dark:text-zinc-300">Key-Value Entries</p>
        <p className="text-xs text-zinc-400 dark:text-zinc-500 mt-0.5">
          Arbitrary named fields accessible as{" "}
          <span className="font-mono">content.entries.&lt;key&gt;</span>.
        </p>
      </div>

      <div className="p-5 space-y-3">
        {/* Header row */}
        <div
          className={`grid ${richText ? (showFormatSelect ? "grid-cols-[1fr_2fr_auto_2rem]" : "grid-cols-[1fr_2fr_2rem]") : "grid-cols-[1fr_1fr_2rem]"} gap-2`}
        >
          <span className="flex items-center gap-1.5">
            <span className={dashboardFieldLabelCn} style={{ marginBottom: 0 }}>
              Key
            </span>
            <InfoTooltip
              hint="Make sure that for each key you enter the corresponding value"
              align="start"
              direction="down"
              wide
            />
          </span>
          <span className={dashboardFieldLabelCn} style={{ marginBottom: 0 }}>
            Value
          </span>
          {showFormatSelect && (
            <span className={dashboardFieldLabelCn} style={{ marginBottom: 0 }}>
              Format
            </span>
          )}
          <span />
        </div>

        {rows.map((row, i) => (
          <div
            key={row.id}
            className={`grid ${richText ? (showFormatSelect ? "grid-cols-[1fr_2fr_auto_2rem]" : "grid-cols-[1fr_2fr_2rem]") : "grid-cols-[1fr_1fr_2rem]"} gap-2 ${richText ? "items-start" : "items-center"}`}
          >
            <input
              type="text"
              value={row.key}
              onChange={(e) => updateRow(i, "key", e.target.value)}
              readOnly={keyLocked(row)}
              title={keyLocked(row) ? LOCK_HINT : undefined}
              placeholder="field_name"
              className={`${dashboardInputCn} font-mono text-xs`}
            />
            {richText ? (
              <ContentField
                format={row.format}
                label={row.key.trim() || "New entry value"}
                placeholder="value"
                value={row.value}
                onChange={(v) => updateRow(i, "value", v)}
              />
            ) : (
              <input
                type="text"
                value={row.value}
                onChange={(e) => updateRow(i, "value", e.target.value)}
                placeholder="value"
                className={dashboardInputCn}
              />
            )}
            {showFormatSelect && (
              <select
                aria-label={`Format of ${row.key || "new entry"}`}
                value={row.format}
                onChange={(e) => changeFormat(i, e.target.value as FieldFormat)}
                className={`${dashboardInputCn} w-auto text-xs cursor-pointer`}
              >
                <option value="plain">Plain</option>
                <option value="inline">Inline</option>
                <option value="rich">Rich</option>
              </select>
            )}
            <button
              type="button"
              onClick={() => removeRow(i)}
              className="flex items-center justify-center h-8 w-8 rounded-md text-zinc-400 hover:text-red-500 hover:bg-red-50 dark:hover:bg-red-950 transition-colors cursor-pointer"
              aria-label="Remove row"
            >
              <Trash2 className="h-3.5 w-3.5" />
            </button>
          </div>
        ))}

        <button
          type="button"
          onClick={addRow}
          className="flex items-center gap-1.5 text-xs font-medium text-zinc-500 hover:text-zinc-900 dark:text-zinc-400 dark:hover:text-zinc-100 transition-colors mt-2 cursor-pointer"
        >
          <Plus className="h-3.5 w-3.5" />
          Add row
        </button>
      </div>
    </div>
  );
}
