"use client";

import { useState } from "react";
import type { EditorProps } from "./index";
import { dashboardInputCn, dashboardFieldLabelCn, dashboardSectionCardCn } from "@/lib/styles";
import { Plus, Trash2 } from "lucide-react";
import { InfoTooltip } from "@/components/dashboard/InfoTooltip";

interface KVRow {
    key: string;
    value: string;
}

function parseEntries(raw: unknown): KVRow[] {
    if (Array.isArray(raw)) return raw as KVRow[];
    if (raw && typeof raw === "object") {
        return Object.entries(raw as Record<string, string>).map(([key, value]) => ({ key, value }));
    }
    return [];
}

export function KeyValueEditor({ initialContent, onChange }: EditorProps) {
    const [rows, setRows] = useState<KVRow[]>(() => {
        const parsed = parseEntries(initialContent.entries);
        return parsed.length > 0 ? parsed : [{ key: "", value: "" }];
    });

    function emit(next: KVRow[]) {
        setRows(next);
        onChange({ entries: next });
    }

    function updateRow(index: number, field: "key" | "value", val: string) {
        const next = rows.map((r, i) => (i === index ? { ...r, [field]: val } : r));
        emit(next);
    }

    function addRow() {
        emit([...rows, { key: "", value: "" }]);
    }

    function removeRow(index: number) {
        const next = rows.filter((_, i) => i !== index);
        emit(next.length > 0 ? next : [{ key: "", value: "" }]);
    }

    return (
        <div className={dashboardSectionCardCn}>
            <div className="px-5 py-4 border-b border-zinc-100 dark:border-zinc-800">
                <p className="text-sm font-medium text-zinc-700 dark:text-zinc-300">Key-Value Entries</p>
                <p className="text-xs text-zinc-400 dark:text-zinc-500 mt-0.5">
                    Arbitrary named fields accessible as <span className="font-mono">content.entries[n].key</span>.
                </p>
            </div>

            <div className="p-5 space-y-3">
                {/* Header row */}
                <div className="grid grid-cols-[1fr_1fr_2rem] gap-2">
                    <span className="flex items-center gap-1.5">
                        <span className={dashboardFieldLabelCn} style={{ marginBottom: 0 }}>Key</span>
                        <InfoTooltip hint="Make sure that for each key you enter the corresponding value" align="start" direction="down" wide />
                    </span>
                    <span className={dashboardFieldLabelCn} style={{ marginBottom: 0 }}>Value</span>
                    <span />
                </div>

                {rows.map((row, i) => (
                    <div key={i} className="grid grid-cols-[1fr_1fr_2rem] gap-2 items-center">
                        <input
                            type="text"
                            value={row.key}
                            onChange={(e) => updateRow(i, "key", e.target.value)}
                            placeholder="field_name"
                            className={`${dashboardInputCn} font-mono text-xs`}
                        />
                        <input
                            type="text"
                            value={row.value}
                            onChange={(e) => updateRow(i, "value", e.target.value)}
                            placeholder="value"
                            className={dashboardInputCn}
                        />
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
