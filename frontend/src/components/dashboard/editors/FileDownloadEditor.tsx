"use client";

import { useState, useRef } from "react";
import type { EditorProps } from "./index";
import { dashboardInputCn, dashboardFieldLabelCn, dashboardSectionCardCn } from "@/lib/styles";
import { Upload, FileIcon } from "lucide-react";

export function FileDownloadEditor({ initialContent, onChange, onUpload }: EditorProps) {
    const [url, setUrl] = useState(String(initialContent.url ?? ""));
    const [filename, setFilename] = useState(String(initialContent.filename ?? ""));
    const [uploading, setUploading] = useState(false);
    const [uploadError, setUploadError] = useState("");
    const fileRef = useRef<HTMLInputElement>(null);

    function emit(next: { url: string; filename: string }) {
        onChange(next);
    }

    async function handleFile(file: File) {
        if (!onUpload) return;
        setUploading(true);
        setUploadError("");
        try {
            const uploaded = await onUpload(file);
            setUrl(uploaded);
            if (!filename) setFilename(file.name);
            emit({ url: uploaded, filename: filename || file.name });
        } catch (err) {
            setUploadError(err instanceof Error ? err.message : "Upload failed.");
        } finally {
            setUploading(false);
        }
    }

    return (
        <div className={`${dashboardSectionCardCn} divide-y divide-zinc-100 dark:divide-zinc-800`}>
            {/* Current file preview */}
            {url && (
                <div className="p-5">
                    <label className={dashboardFieldLabelCn}>Current file</label>
                    <a
                        href={url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="mt-1 flex items-center gap-2 rounded-lg border border-zinc-200 dark:border-zinc-700 px-4 py-3 text-sm text-zinc-700 dark:text-zinc-300 hover:bg-zinc-50 dark:hover:bg-zinc-800 transition-colors"
                    >
                        <FileIcon className="h-4 w-4 shrink-0 text-zinc-400" />
                        <span className="truncate">{filename || url}</span>
                    </a>
                </div>
            )}

            {/* File URL */}
            <div className="p-5">
                <label className={dashboardFieldLabelCn}>File URL</label>
                <input
                    type="url"
                    value={url}
                    onChange={(e) => { setUrl(e.target.value); emit({ url: e.target.value, filename }); }}
                    placeholder="https://…"
                    className={dashboardInputCn}
                />
            </div>

            {/* Upload */}
            <div className="p-5">
                <label className={dashboardFieldLabelCn}>Upload file</label>
                <input
                    ref={fileRef}
                    type="file"
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
                    {uploading ? "Uploading…" : onUpload ? "Choose file" : "Upload (Phase 16)"}
                </button>
                {uploadError && (
                    <p className="mt-1.5 text-xs text-red-600 dark:text-red-400">{uploadError}</p>
                )}
            </div>

            {/* Display filename */}
            <div className="p-5">
                <label className={dashboardFieldLabelCn}>Display filename</label>
                <p className="text-xs text-zinc-400 dark:text-zinc-500 mb-2">
                    Shown to visitors as the download link label. Defaults to the URL filename.
                </p>
                <input
                    type="text"
                    value={filename}
                    onChange={(e) => { setFilename(e.target.value); emit({ url, filename: e.target.value }); }}
                    placeholder="e.g. Menu 2026.pdf"
                    className={dashboardInputCn}
                />
            </div>
        </div>
    );
}
