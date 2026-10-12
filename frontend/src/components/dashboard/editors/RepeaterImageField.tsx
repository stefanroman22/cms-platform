"use client";

import { useRef, useState } from "react";
import { ImageIcon, Upload, X } from "lucide-react";
import { ImageHint, measureImage, type ImageSize } from "./ImageHint";

const btnCn =
  "flex items-center gap-1.5 rounded-lg border border-zinc-200 dark:border-zinc-700 px-3 py-1.5 text-xs text-zinc-600 dark:text-zinc-300 hover:bg-zinc-50 dark:hover:bg-zinc-800 disabled:opacity-40 disabled:cursor-not-allowed transition-colors cursor-pointer";

/** A repeater `image` field (ADR-0011): the value is a URL string, "" for none. */
export function RepeaterImageField({
  value,
  onChange,
  onUpload,
  hint,
}: {
  value: string;
  onChange: (url: string) => void;
  onUpload?: (file: File) => Promise<string>;
  hint?: ImageSize;
}) {
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState("");
  const [measured, setMeasured] = useState<ImageSize>();
  const [bytes, setBytes] = useState<number>();
  const fileRef = useRef<HTMLInputElement>(null);

  async function handleFile(file: File) {
    if (!onUpload) return;
    setUploading(true);
    setUploadError("");
    try {
      setMeasured(undefined);
      const measuring = measureImage(file);
      const uploaded = await onUpload(file);
      setBytes(file.size);
      onChange(uploaded);
      measuring.then((size) => setMeasured(size ?? undefined));
    } catch (err) {
      setUploadError(err instanceof Error ? err.message : "Upload failed.");
    } finally {
      setUploading(false);
    }
  }

  return (
    <div>
      <div className="flex items-center gap-3">
        <div className="flex h-16 w-24 shrink-0 items-center justify-center overflow-hidden rounded-lg border border-zinc-200 dark:border-zinc-700 bg-zinc-50 dark:bg-zinc-800">
          {value ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img src={value} alt="" className="h-full w-full object-contain" />
          ) : (
            <ImageIcon className="h-6 w-6 text-zinc-300 dark:text-zinc-600" />
          )}
        </div>
        <input
          ref={fileRef}
          type="file"
          accept="image/*"
          className="hidden"
          onChange={(e) => {
            const f = e.target.files?.[0];
            if (f) handleFile(f);
            e.target.value = "";
          }}
        />
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            disabled={!onUpload || uploading}
            onClick={() => fileRef.current?.click()}
            className={btnCn}
          >
            <Upload className="h-3.5 w-3.5" />
            {uploading ? "Uploading…" : value ? "Replace" : "Choose image"}
          </button>
          {value && (
            <button
              type="button"
              onClick={() => onChange("")}
              className={`${btnCn} hover:text-red-500`}
            >
              <X className="h-3.5 w-3.5" />
              Remove
            </button>
          )}
        </div>
      </div>
      {uploadError && (
        <p className="mt-1.5 text-xs text-red-600 dark:text-red-400">{uploadError}</p>
      )}
      <ImageHint
        hint={hint}
        measured={value ? measured : undefined}
        bytes={value ? bytes : undefined}
      />
    </div>
  );
}
