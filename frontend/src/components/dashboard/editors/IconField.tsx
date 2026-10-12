"use client";

import dynamic from "next/dynamic";
import { useEffect, useRef, useState } from "react";
import { Shapes, Upload, X } from "lucide-react";
import { CmsIcon, recommendIconColors, type CmsIconValue } from "@/lib/cms-rich-text";
import { useProjectTheme } from "@/components/dashboard/theme/ProjectThemeContext";

const IconPicker = dynamic(() => import("./IconPicker").then((m) => m.IconPicker), {
  ssr: false,
  loading: () => <p className="text-xs text-zinc-400 dark:text-zinc-500">Loading icons…</p>,
});

const btnCn =
  "flex items-center gap-1.5 rounded-lg border border-zinc-200 dark:border-zinc-700 px-3 py-1.5 text-xs text-zinc-600 dark:text-zinc-300 hover:bg-zinc-50 dark:hover:bg-zinc-800 disabled:opacity-40 disabled:cursor-not-allowed transition-colors cursor-pointer";
const toggleCn = (on: boolean) =>
  `rounded-md px-2.5 py-1 text-xs font-medium transition-colors cursor-pointer disabled:opacity-40 disabled:cursor-not-allowed ${
    on
      ? "bg-zinc-900 text-white dark:bg-zinc-100 dark:text-zinc-900"
      : "text-zinc-600 hover:bg-zinc-100 dark:text-zinc-300 dark:hover:bg-zinc-800"
  }`;
const pressedRingCn =
  "ring-2 ring-zinc-900 ring-offset-1 dark:ring-zinc-100 dark:ring-offset-zinc-900";

const isSvg = (src: string) => src.split(/[?#]/)[0].toLowerCase().endsWith(".svg");
/** Lucide's PascalCase → kebab file names ("ArrowUpRight" → "arrow-up-right",
 *  "Building2" → "building-2", "Grid3x3" → "grid-3x3"). */
const kebab = (name: string) =>
  name
    .replace(/([a-z0-9])([A-Z])/g, "$1-$2")
    .replace(/(?<=[a-zA-Z]{2})(?=\d)/g, "-")
    .toLowerCase();

/** A repeater `icon` field (ADR-0011): pick from the Lucide set or upload an
 *  SVG/PNG; SVGs can be recoloured with the theme's contrast-checked colours. */
export function IconField({
  value,
  onChange,
  onUpload,
  surface,
}: {
  value: CmsIconValue | null;
  onChange: (icon: CmsIconValue | null) => void;
  onUpload?: (file: File) => Promise<string>;
  surface?: string;
}) {
  const { theme } = useProjectTheme();
  const [pickerOpen, setPickerOpen] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState("");
  const fileRef = useRef<HTMLInputElement>(null);
  const chooseRef = useRef<HTMLButtonElement>(null);
  // Set when a pick closes the picker; Choose icon is disabled during the
  // upload, so focus goes back to it once it is enabled again.
  const refocusChooseRef = useRef(false);
  useEffect(() => {
    if (!refocusChooseRef.current || pickerOpen || uploading) return;
    refocusChooseRef.current = false;
    chooseRef.current?.focus();
  }, [pickerOpen, uploading]);

  const svg = !!value && isSvg(value.src);
  const mode = svg ? value.mode : "original";
  const color = value?.color ?? "";
  const recommendations = theme ? recommendIconColors(theme, surface) : [];

  async function upload(file: File, toIcon: (src: string) => CmsIconValue) {
    if (!onUpload) return;
    setUploading(true);
    setUploadError("");
    try {
      onChange(toIcon(await onUpload(file)));
    } catch (err) {
      setUploadError(err instanceof Error ? err.message : "Upload failed.");
    } finally {
      setUploading(false);
    }
  }

  function handlePick(markup: string, name: string) {
    setPickerOpen(false);
    refocusChooseRef.current = true;
    const slug = kebab(name);
    const withNs = markup.includes("xmlns=")
      ? markup
      : markup.replace("<svg", '<svg xmlns="http://www.w3.org/2000/svg"');
    const file = new File([withNs], `${slug}.svg`, { type: "image/svg+xml" });
    upload(file, (src) => ({ src, mode: "tint", color, name: `lucide:${slug}` }));
  }

  function handleFile(file: File) {
    const fileIsSvg = file.type === "image/svg+xml" || /\.svg$/i.test(file.name);
    upload(file, (src) => ({
      src,
      mode: fileIsSvg ? "tint" : "original",
      color,
      name: file.name.slice(0, 64),
    }));
  }

  const set = (patch: Partial<CmsIconValue>) => value && onChange({ ...value, ...patch });

  return (
    <div
      className="space-y-3"
      onKeyDown={(e) => {
        if (e.key === "Escape" && pickerOpen) {
          e.preventDefault();
          setPickerOpen(false);
          chooseRef.current?.focus();
        }
      }}
    >
      <div className="flex items-center gap-3">
        <div className="flex h-16 w-16 shrink-0 items-center justify-center rounded-lg border border-zinc-200 bg-zinc-50 text-zinc-700 dark:border-zinc-700 dark:bg-zinc-800 dark:text-zinc-200">
          {value ? (
            <CmsIcon icon={value} size={40} label={value.name || "Icon"} />
          ) : (
            <span className="text-xs text-zinc-400 dark:text-zinc-500">No icon</span>
          )}
        </div>
        <input
          ref={fileRef}
          type="file"
          accept="image/svg+xml,image/png,image/webp"
          className="hidden"
          onChange={(e) => {
            const f = e.target.files?.[0];
            if (f) handleFile(f);
            e.target.value = "";
          }}
        />
        <div className="flex flex-wrap gap-2">
          <button
            ref={chooseRef}
            type="button"
            disabled={!onUpload || uploading}
            aria-expanded={pickerOpen}
            onClick={() => setPickerOpen((o) => !o)}
            className={btnCn}
          >
            <Shapes className="h-3.5 w-3.5" />
            Choose icon
          </button>
          <button
            type="button"
            disabled={!onUpload || uploading}
            onClick={() => fileRef.current?.click()}
            className={btnCn}
          >
            <Upload className="h-3.5 w-3.5" />
            {uploading ? "Uploading…" : "Upload SVG/PNG"}
          </button>
          {value && (
            <button
              type="button"
              onClick={() => onChange(null)}
              className={`${btnCn} hover:text-red-500`}
            >
              <X className="h-3.5 w-3.5" />
              Remove
            </button>
          )}
        </div>
      </div>
      {uploadError && <p className="text-xs text-red-600 dark:text-red-400">{uploadError}</p>}

      {pickerOpen && (
        <div className="rounded-lg border border-zinc-200 p-3 dark:border-zinc-700">
          <IconPicker onPick={handlePick} />
        </div>
      )}

      {value && (
        <div
          role="group"
          aria-label="Icon colours"
          className="inline-flex gap-0.5 rounded-lg border border-zinc-200 p-0.5 dark:border-zinc-700"
        >
          <button
            type="button"
            disabled={!svg}
            aria-pressed={mode === "tint"}
            onClick={() => set({ mode: "tint" })}
            className={toggleCn(mode === "tint")}
          >
            Recolour
          </button>
          <button
            type="button"
            aria-pressed={mode === "original"}
            onClick={() => set({ mode: "original" })}
            className={toggleCn(mode === "original")}
          >
            Original colours
          </button>
        </div>
      )}

      {value && mode === "tint" && (
        <div className="flex flex-wrap items-center gap-2">
          <button
            type="button"
            aria-pressed={color === ""}
            onClick={() => set({ color: "" })}
            className={`${btnCn} ${color === "" ? pressedRingCn : ""}`}
          >
            Site default
          </button>
          {recommendations.map(({ color: c, ok, ratio }) => {
            const pressed = color.toLowerCase() === c.value;
            return (
              <button
                key={`${c.name}${c.value}`}
                type="button"
                aria-pressed={pressed}
                title={`${c.name} (${c.value}) · contrast ${ratio.toFixed(1)}:1`}
                onClick={() => set({ color: c.value })}
                className={`${btnCn} ${pressed ? pressedRingCn : ""}`}
              >
                <span
                  aria-hidden
                  className="h-4 w-4 rounded-full border border-zinc-200 dark:border-zinc-700"
                  style={{ backgroundColor: c.value }}
                />
                {c.name}
                {ok ? (
                  <>
                    <span aria-hidden className="text-emerald-600 dark:text-emerald-400">
                      ✓
                    </span>
                    <span className="sr-only">good contrast</span>
                  </>
                ) : (
                  <span className="text-zinc-400 dark:text-zinc-500">low contrast</span>
                )}
              </button>
            );
          })}
          <label className="flex cursor-pointer items-center gap-1.5 text-xs text-zinc-600 dark:text-zinc-300">
            Custom
            {/* Neutral placeholder, not black: re-picking the shown value fires no change. */}
            <input
              type="color"
              aria-label="Custom colour"
              value={color || "#777777"}
              onChange={(e) => set({ color: e.target.value })}
              className="h-6 w-8 cursor-pointer rounded border border-zinc-200 bg-transparent dark:border-zinc-700"
            />
          </label>
        </div>
      )}
    </div>
  );
}
