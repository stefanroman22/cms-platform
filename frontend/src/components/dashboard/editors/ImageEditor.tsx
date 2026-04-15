"use client";

import { useState, useRef } from "react";
import type { EditorProps } from "./index";
import { dashboardInputCn, dashboardFieldLabelCn, dashboardSectionCardCn } from "@/lib/styles";
import { ImageIcon, Upload, X } from "lucide-react";
import { InfoTooltip } from "@/components/dashboard/InfoTooltip";

interface ImageEditorProps extends EditorProps {
    label?: string;
}

export function ImageEditor({ initialContent, onChange, onUpload, label = "Image" }: ImageEditorProps) {
    const [url, setUrl] = useState(String(initialContent.url ?? ""));
    const [alt, setAlt] = useState(String(initialContent.alt ?? ""));
    const [uploading, setUploading] = useState(false);
    const [uploadError, setUploadError] = useState("");
    const fileRef = useRef<HTMLInputElement>(null);

    function emit(next: { url: string; alt: string }) {
        onChange(next);
    }

    async function handleFile(file: File) {
        if (!onUpload) return;
        setUploading(true);
        setUploadError("");
        try {
            const uploaded = await onUpload(file);
            setUrl(uploaded);
            emit({ url: uploaded, alt });
        } catch (err) {
            setUploadError(err instanceof Error ? err.message : "Upload failed.");
        } finally {
            setUploading(false);
        }
    }

    const previewUrl = url.trim();

    return (
        <div className={`${dashboardSectionCardCn} divide-y divide-zinc-100 dark:divide-zinc-800`}>
            {/* Preview */}
            <div className="p-5">
                <label className={dashboardFieldLabelCn}>{label} preview</label>
                {previewUrl ? (
                    <div className="relative mt-1 overflow-hidden rounded-lg border border-zinc-200 dark:border-zinc-700 bg-zinc-50 dark:bg-zinc-800">
                        {/* eslint-disable-next-line @next/next/no-img-element */}
                        <img
                            src={previewUrl}
                            alt={alt || `${label} preview`}
                            className="max-h-64 w-full object-contain"
                        />
                        <button
                            type="button"
                            onClick={() => { setUrl(""); emit({ url: "", alt }); }}
                            className="absolute top-2 right-2 flex items-center justify-center h-7 w-7 rounded-full bg-white/90 dark:bg-zinc-900/90 text-zinc-600 dark:text-zinc-300 hover:text-red-500 shadow transition-colors cursor-pointer"
                            aria-label="Remove image"
                        >
                            <X className="h-3.5 w-3.5" />
                        </button>
                    </div>
                ) : (
                    <div className="mt-1 flex flex-col items-center justify-center gap-2 rounded-lg border border-dashed border-zinc-300 dark:border-zinc-700 bg-zinc-50 dark:bg-zinc-800 py-10">
                        <ImageIcon className="h-8 w-8 text-zinc-300 dark:text-zinc-600" />
                        <p className="text-xs text-zinc-400 dark:text-zinc-500">No image set</p>
                    </div>
                )}
            </div>

            {/* File upload */}
            <div className="p-5">
                <label className={dashboardFieldLabelCn}>Upload from device</label>
                <input
                    ref={fileRef}
                    type="file"
                    accept="image/*"
                    className="hidden"
                    onChange={(e) => { const f = e.target.files?.[0]; if (f) handleFile(f); }}
                />
                <button
                    type="button"
                    disabled={!onUpload || uploading}
                    onClick={() => fileRef.current?.click()}
                    className="flex items-center gap-2 rounded-lg border border-zinc-200 dark:border-zinc-700 px-4 py-2 text-sm text-zinc-600 dark:text-zinc-300 hover:bg-zinc-50 dark:hover:bg-zinc-800 disabled:opacity-40 disabled:cursor-not-allowed transition-colors cursor-pointer"
                >
                    <Upload className="h-4 w-4" />
                    {uploading ? "Uploading…" : "Choose file"}
                </button>
                {uploadError && (
                    <p className="mt-1.5 text-xs text-red-600 dark:text-red-400">{uploadError}</p>
                )}
            </div>

            {/* Alt text */}
            <div className="p-5">
                <span className="flex items-center gap-1.5 mb-1.5">
                    <label className={dashboardFieldLabelCn} style={{ marginBottom: 0 }}>Alt text</label>
                    <InfoTooltip hint="Describe the image briefly for screen readers and SEO. Example: 'Portrait photo of Laurian Duma'. Keep it concise." />
                </span>
                <input
                    type="text"
                    value={alt}
                    onChange={(e) => { setAlt(e.target.value); emit({ url, alt: e.target.value }); }}
                    placeholder="Describe the image for screen readers…"
                    className={dashboardInputCn}
                />
            </div>
        </div>
    );
}
