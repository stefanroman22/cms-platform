"use client";

import { useState, useRef } from "react";
import type { EditorProps } from "./index";
import { dashboardInputCn, dashboardFieldLabelCn, dashboardSectionCardCn } from "@/lib/styles";
import { Upload } from "lucide-react";

function getEmbedUrl(url: string): string | null {
  try {
    const u = new URL(url);
    // YouTube
    if (u.hostname.includes("youtube.com")) {
      const id = u.searchParams.get("v");
      return id ? `https://www.youtube.com/embed/${id}` : null;
    }
    if (u.hostname === "youtu.be") {
      const id = u.pathname.slice(1);
      return id ? `https://www.youtube.com/embed/${id}` : null;
    }
    // Vimeo
    if (u.hostname.includes("vimeo.com")) {
      const id = u.pathname.split("/").filter(Boolean).pop();
      return id ? `https://player.vimeo.com/video/${id}` : null;
    }
  } catch {
    /* ignore invalid URL */
  }
  return null;
}

export function VideoEditor({ initialContent, onChange, onUpload }: EditorProps) {
  const [url, setUrl] = useState(String(initialContent.url ?? ""));
  const [poster, setPoster] = useState(String(initialContent.poster ?? ""));
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState("");
  const fileRef = useRef<HTMLInputElement>(null);

  function emit(next: { url: string; poster: string }) {
    onChange(next);
  }

  async function handleFile(file: File) {
    if (!onUpload) return;
    setUploading(true);
    setUploadError("");
    try {
      const uploaded = await onUpload(file);
      setUrl(uploaded);
      emit({ url: uploaded, poster });
    } catch (err) {
      setUploadError(err instanceof Error ? err.message : "Upload failed.");
    } finally {
      setUploading(false);
    }
  }

  const embedUrl = getEmbedUrl(url);

  return (
    <div className={`${dashboardSectionCardCn} divide-y divide-zinc-100 dark:divide-zinc-800`}>
      {/* Preview */}
      {embedUrl && (
        <div className="p-5">
          <label className={dashboardFieldLabelCn}>Preview</label>
          <div className="mt-1 aspect-video w-full overflow-hidden rounded-lg border border-zinc-200 dark:border-zinc-700">
            <iframe
              src={embedUrl}
              allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
              allowFullScreen
              className="h-full w-full"
              title="Video preview"
            />
          </div>
        </div>
      )}

      {/* Video URL */}
      <div className="p-5">
        <label className={dashboardFieldLabelCn}>Video URL</label>
        <p className="text-xs text-zinc-400 dark:text-zinc-500 mb-2">
          YouTube, Vimeo, or direct video link (MP4 / WebM).
        </p>
        <input
          type="url"
          value={url}
          onChange={(e) => {
            setUrl(e.target.value);
            emit({ url: e.target.value, poster });
          }}
          placeholder="https://youtube.com/watch?v=…"
          className={dashboardInputCn}
        />
      </div>

      {/* Upload */}
      <div className="p-5">
        <label className={dashboardFieldLabelCn}>Upload video file</label>
        <input
          ref={fileRef}
          type="file"
          accept="video/*"
          className="hidden"
          onChange={(e) => {
            const f = e.target.files?.[0];
            if (f) handleFile(f);
          }}
        />
        <button
          type="button"
          disabled={!onUpload || uploading}
          onClick={() => fileRef.current?.click()}
          className="flex items-center gap-2 rounded-lg border border-zinc-200 dark:border-zinc-700 px-4 py-2 text-sm text-zinc-600 dark:text-zinc-300 hover:bg-zinc-50 dark:hover:bg-zinc-800 disabled:opacity-40 disabled:cursor-not-allowed transition-colors cursor-pointer"
        >
          <Upload className="h-4 w-4" />
          {uploading ? "Uploading…" : onUpload ? "Choose video file" : "Upload (Phase 16)"}
        </button>
        {uploadError && (
          <p className="mt-1.5 text-xs text-red-600 dark:text-red-400">{uploadError}</p>
        )}
      </div>

      {/* Poster */}
      <div className="p-5">
        <label className={dashboardFieldLabelCn}>Poster image URL (optional)</label>
        <p className="text-xs text-zinc-400 dark:text-zinc-500 mb-2">
          Shown before the video plays. Leave empty to use the video thumbnail.
        </p>
        <input
          type="url"
          value={poster}
          onChange={(e) => {
            setPoster(e.target.value);
            emit({ url, poster: e.target.value });
          }}
          placeholder="https://…"
          className={dashboardInputCn}
        />
      </div>
    </div>
  );
}
