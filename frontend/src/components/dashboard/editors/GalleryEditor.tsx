"use client";

import { useState, useRef } from "react";
import type { EditorProps } from "./index";
import { dashboardFieldLabelCn, dashboardInputCn, dashboardSectionCardCn } from "@/lib/styles";
import { Plus, Trash2, Upload, GripVertical } from "lucide-react";

export function GalleryEditor({ initialContent, onChange, onUpload }: EditorProps) {
    const [items, setItems] = useState<string[]>(() => {
        const raw = initialContent.items;
        return Array.isArray(raw) ? (raw as string[]) : [];
    });
    const [uploading, setUploading] = useState<number | null>(null);
    const [uploadError, setUploadError] = useState("");
    const fileRef = useRef<HTMLInputElement>(null);

    function emit(next: string[]) {
        setItems(next);
        onChange({ items: next });
    }

    function updateItem(index: number, value: string) {
        emit(items.map((item, i) => (i === index ? value : item)));
    }

    function removeItem(index: number) {
        emit(items.filter((_, i) => i !== index));
    }

    function addItem() {
        emit([...items, ""]);
    }

    async function handleFile(file: File) {
        if (!onUpload) return;
        setUploading(-1);
        setUploadError("");
        try {
            const uploaded = await onUpload(file);
            emit([...items, uploaded]);
        } catch (err) {
            setUploadError(err instanceof Error ? err.message : "Upload failed.");
        } finally {
            setUploading(null);
            if (fileRef.current) fileRef.current.value = "";
        }
    }

    return (
        <div className={`${dashboardSectionCardCn} divide-y divide-zinc-100 dark:divide-zinc-800`}>
            {/* Image list */}
            <div className="p-5 space-y-3">
                <label className={dashboardFieldLabelCn}>Gallery images ({items.length})</label>

                {items.length === 0 && (
                    <p className="text-xs text-zinc-400 dark:text-zinc-500">No images yet. Add a URL or upload a file.</p>
                )}

                {items.map((url, i) => (
                    <div key={i} className="flex items-center gap-2">
                        <GripVertical className="h-4 w-4 shrink-0 text-zinc-300 dark:text-zinc-600 cursor-grab" />
                        {url && (
                            // eslint-disable-next-line @next/next/no-img-element
                            <img
                                src={url}
                                alt={`Gallery item ${i + 1}`}
                                className="h-10 w-10 shrink-0 rounded-md border border-zinc-200 dark:border-zinc-700 object-cover"
                            />
                        )}
                        <input
                            type="url"
                            value={url}
                            onChange={(e) => updateItem(i, e.target.value)}
                            placeholder="https://…"
                            className={dashboardInputCn}
                        />
                        <button
                            type="button"
                            onClick={() => removeItem(i)}
                            className="flex items-center justify-center h-8 w-8 shrink-0 rounded-md text-zinc-400 hover:text-red-500 hover:bg-red-50 dark:hover:bg-red-950 transition-colors cursor-pointer"
                            aria-label="Remove image"
                        >
                            <Trash2 className="h-3.5 w-3.5" />
                        </button>
                    </div>
                ))}
            </div>

            {/* Actions */}
            <div className="px-5 py-4 flex items-center gap-4">
                <button
                    type="button"
                    onClick={addItem}
                    className="flex items-center gap-1.5 text-xs font-medium text-zinc-500 hover:text-zinc-900 dark:text-zinc-400 dark:hover:text-zinc-100 transition-colors cursor-pointer"
                >
                    <Plus className="h-3.5 w-3.5" />
                    Add URL
                </button>

                <input
                    ref={fileRef}
                    type="file"
                    accept="image/*"
                    className="hidden"
                    onChange={(e) => { const f = e.target.files?.[0]; if (f) handleFile(f); }}
                />
                <button
                    type="button"
                    disabled={!onUpload || uploading !== null}
                    onClick={() => fileRef.current?.click()}
                    className="flex items-center gap-1.5 text-xs font-medium text-zinc-500 hover:text-zinc-900 dark:text-zinc-400 dark:hover:text-zinc-100 disabled:opacity-40 disabled:cursor-not-allowed transition-colors cursor-pointer"
                >
                    <Upload className="h-3.5 w-3.5" />
                    {uploading !== null ? "Uploading…" : onUpload ? "Upload file" : "Upload (Phase 16)"}
                </button>

                {uploadError && (
                    <p className="text-xs text-red-600 dark:text-red-400">{uploadError}</p>
                )}
            </div>
        </div>
    );
}
