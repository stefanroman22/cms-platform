"use client";

import { useState, useCallback } from "react";
import type { EditorProps } from "./index";
import { dashboardInputCn, dashboardFieldLabelCn, dashboardSectionCardCn } from "@/lib/styles";
import { Plus, Trash2, ChevronUp, ChevronDown } from "lucide-react";
import { InfoTooltip } from "@/components/dashboard/InfoTooltip";

interface SchemaField {
    key: string;
    label: string;
    type: "string" | "richtext" | "url" | "tags";
}

type ItemRecord = Record<string, unknown>;

function parseSchema(raw: unknown): SchemaField[] {
    if (Array.isArray(raw)) return raw as SchemaField[];
    return [];
}

function parseItems(raw: unknown): ItemRecord[] {
    if (Array.isArray(raw)) return raw as ItemRecord[];
    return [];
}

/** Tags field: comma-separated string ↔ string[] */
function tagsToString(val: unknown): string {
    if (Array.isArray(val)) return (val as string[]).join(", ");
    if (typeof val === "string") return val;
    return "";
}

function stringToTags(val: string): string[] {
    return val.split(",").map((s) => s.trim()).filter(Boolean);
}

function FieldInput({
    field,
    value,
    onChange,
}: {
    field: SchemaField;
    value: unknown;
    onChange: (val: unknown) => void;
}) {
    if (field.type === "tags") {
        return (
            <input
                type="text"
                value={tagsToString(value)}
                onChange={(e) => onChange(stringToTags(e.target.value))}
                placeholder="Comma-separated values"
                className={dashboardInputCn}
            />
        );
    }
    if (field.type === "richtext") {
        return (
            <textarea
                value={typeof value === "string" ? value : ""}
                onChange={(e) => onChange(e.target.value)}
                rows={3}
                className={`${dashboardInputCn} resize-y`}
            />
        );
    }
    // string | url
    return (
        <input
            type={field.type === "url" ? "url" : "text"}
            value={typeof value === "string" ? value : ""}
            onChange={(e) => onChange(e.target.value)}
            className={dashboardInputCn}
        />
    );
}

export function RepeaterEditor({ initialContent, onChange }: EditorProps) {
    const schema = parseSchema(initialContent._schema);
    const [items, setItems] = useState<ItemRecord[]>(() => parseItems(initialContent.items));

    const emit = useCallback(
        (next: ItemRecord[]) => {
            setItems(next);
            onChange({ _schema: schema, items: next });
        },
        [schema, onChange]
    );

    function addItem() {
        const blank: ItemRecord = {};
        schema.forEach((f) => {
            blank[f.key] = f.type === "tags" ? [] : "";
        });
        emit([...items, blank]);
    }

    function removeItem(index: number) {
        emit(items.filter((_, i) => i !== index));
    }

    function moveItem(index: number, direction: "up" | "down") {
        const next = [...items];
        const swap = direction === "up" ? index - 1 : index + 1;
        if (swap < 0 || swap >= next.length) return;
        [next[index], next[swap]] = [next[swap], next[index]];
        emit(next);
    }

    function updateField(itemIndex: number, fieldKey: string, val: unknown) {
        const next = items.map((item, i) =>
            i === itemIndex ? { ...item, [fieldKey]: val } : item
        );
        emit(next);
    }

    if (schema.length === 0) {
        return (
            <div className={dashboardSectionCardCn}>
                <div className="p-5">
                    <p className="text-sm text-zinc-500 dark:text-zinc-400">
                        This repeater has no field schema defined. Re-create the service with an{" "}
                        <span className="font-mono">item_schema</span>.
                    </p>
                </div>
            </div>
        );
    }

    return (
        <div className="space-y-4">
            {items.map((item, itemIndex) => (
                <div key={itemIndex} className={dashboardSectionCardCn}>
                    {/* Item header */}
                    <div className="flex items-center justify-between px-5 py-3 border-b border-zinc-100 dark:border-zinc-800">
                        <p className="text-sm font-medium text-zinc-700 dark:text-zinc-300">
                            Item {itemIndex + 1}
                        </p>
                        <div className="flex items-center gap-1">
                            <button
                                type="button"
                                onClick={() => moveItem(itemIndex, "up")}
                                disabled={itemIndex === 0}
                                className="flex items-center justify-center h-7 w-7 rounded text-zinc-400 hover:text-zinc-700 dark:hover:text-zinc-200 disabled:opacity-30 disabled:cursor-not-allowed cursor-pointer transition-colors"
                                aria-label="Move up"
                            >
                                <ChevronUp className="h-4 w-4" />
                            </button>
                            <button
                                type="button"
                                onClick={() => moveItem(itemIndex, "down")}
                                disabled={itemIndex === items.length - 1}
                                className="flex items-center justify-center h-7 w-7 rounded text-zinc-400 hover:text-zinc-700 dark:hover:text-zinc-200 disabled:opacity-30 disabled:cursor-not-allowed cursor-pointer transition-colors"
                                aria-label="Move down"
                            >
                                <ChevronDown className="h-4 w-4" />
                            </button>
                            <button
                                type="button"
                                onClick={() => removeItem(itemIndex)}
                                className="flex items-center justify-center h-7 w-7 rounded text-zinc-400 hover:text-red-500 hover:bg-red-50 dark:hover:bg-red-950 transition-colors cursor-pointer"
                                aria-label="Remove item"
                            >
                                <Trash2 className="h-3.5 w-3.5" />
                            </button>
                        </div>
                    </div>

                    {/* Item fields */}
                    <div className="p-5 space-y-4">
                        {schema.map((field) => (
                            <div key={field.key}>
                                <span className="flex items-center gap-1.5 mb-1.5">
                                    <label className={dashboardFieldLabelCn} style={{ marginBottom: 0 }}>
                                        {field.label}
                                        <span className="ml-1.5 font-mono text-[10px] text-zinc-400 dark:text-zinc-500 normal-case">
                                            ({field.type})
                                        </span>
                                    </label>
                                    {field.type === "url" && (
                                        <InfoTooltip hint="Enter a full URL starting with https://, e.g. https://github.com/username" />
                                    )}
                                    {field.type === "tags" && (
                                        <InfoTooltip hint="Enter values separated by commas. Example: React, TypeScript, Node.js" />
                                    )}
                                    {field.type === "richtext" && (
                                        <InfoTooltip hint="Supports Markdown formatting: **bold**, *italic*, [link](url), - bullet" />
                                    )}
                                </span>
                                <FieldInput
                                    field={field}
                                    value={item[field.key]}
                                    onChange={(val) => updateField(itemIndex, field.key, val)}
                                />
                            </div>
                        ))}
                    </div>
                </div>
            ))}

            <button
                type="button"
                onClick={addItem}
                className="flex items-center gap-2 rounded-lg border border-dashed border-zinc-300 dark:border-zinc-700 px-4 py-3 text-sm text-zinc-500 dark:text-zinc-400 hover:border-zinc-400 dark:hover:border-zinc-500 hover:text-zinc-700 dark:hover:text-zinc-200 transition-colors w-full justify-center cursor-pointer"
            >
                <Plus className="h-4 w-4" />
                Add item
            </button>
        </div>
    );
}
