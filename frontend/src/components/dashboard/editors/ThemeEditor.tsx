"use client";

import { useId, useRef, useState } from "react";
import type { EditorProps } from "./index";
import { dashboardInputCn, dashboardFieldLabelCn, dashboardSectionCardCn } from "@/lib/styles";
import { Plus, Trash2, Upload } from "lucide-react";
import {
  FONT_FAMILY_RE,
  fontStack,
  googleFontsHref,
  readTheme,
  type CmsTheme,
  type ThemeColor,
  type ThemeFont,
} from "@/lib/cms-rich-text";
import { FONT_CATALOG } from "@/components/dashboard/theme/fontCatalog";
import { FontLoader } from "@/components/dashboard/theme/FontLoader";

// Caps mirror backend services/theme.py.
const MAX_COLORS = 24;
const MAX_SURFACES = 8;
const MAX_FONTS = 12;
const MAX_FONT_FILES = 8;
const SAMPLE = "The quick brown fox · Aa Ăă Șș Țț";
const PICK_WEIGHTS = [300, 400, 500, 600, 700, 800];
const FILE_WEIGHTS = [100, 200, 300, 400, 500, 600, 700, 800, 900];
const SOURCE_LABEL: Record<ThemeFont["source"], string> = {
  google: "Google",
  upload: "Uploaded",
  system: "System",
};
const FAMILY_HINT = "Font names may use letters, digits, spaces and hyphens (max 64 characters).";

const secondaryBtnCn =
  "flex shrink-0 items-center gap-1.5 rounded-lg border border-zinc-200 px-3 py-2 text-sm text-zinc-600 transition-colors hover:bg-zinc-50 disabled:cursor-not-allowed disabled:opacity-40 cursor-pointer dark:border-zinc-700 dark:text-zinc-300 dark:hover:bg-zinc-800";
const removeBtnCn =
  "flex h-8 w-8 shrink-0 items-center justify-center rounded-lg text-zinc-400 transition-colors hover:bg-red-50 hover:text-red-500 cursor-pointer dark:hover:bg-red-950";

interface ColorRow extends ThemeColor {
  id: string;
  /** What the hex box shows; `value` keeps the last valid colour. */
  text: string;
}

interface ThemeState {
  colors: ColorRow[];
  surfaces: ColorRow[];
  fonts: ThemeFont[];
  body_font: string;
  heading_font: string;
}

let rowSeq = 0;
const toRows = (list: ThemeColor[]): ColorRow[] =>
  list.map((c) => ({ ...c, id: `c${rowSeq++}`, text: c.value }));

/** `#abc` / `#AABBCC` / `aabbcc` → `#aabbcc`; null when not a hex colour. */
function normalizeHex(raw: string): string | null {
  const m = /^#?([0-9a-f]{3}|[0-9a-f]{6})$/i.exec(raw.trim());
  if (!m) return null;
  const h = m[1].toLowerCase();
  return `#${h.length === 3 ? [...h].map((c) => c + c).join("") : h}`;
}

function toTheme(s: ThemeState): CmsTheme {
  const plain = (rows: ColorRow[]) => rows.map(({ name, value }) => ({ name, value }));
  return {
    colors: plain(s.colors),
    surfaces: plain(s.surfaces),
    fonts: s.fonts,
    body_font: s.body_font,
    heading_font: s.heading_font,
  };
}

async function googleFontExists(font: { family: string; weights: number[]; italic: boolean }) {
  try {
    return (await fetch(googleFontsHref(font), { mode: "cors" })).ok;
  } catch {
    return false;
  }
}

function fontDetail(f: ThemeFont): string {
  if (f.source === "google") {
    const w = f.weights.length ? f.weights.join(", ") : "default weight";
    return f.italic ? `${w} · italic` : w;
  }
  if (f.source === "upload") return `${f.files.length} file${f.files.length === 1 ? "" : "s"}`;
  return "Installed on visitors' devices";
}

export function ThemeEditor({ initialContent, onChange, onUpload }: EditorProps) {
  const [state, setState] = useState<ThemeState>(() => {
    const t = readTheme(initialContent);
    return {
      colors: toRows(t?.colors ?? []),
      surfaces: toRows(t?.surfaces ?? []),
      fonts: t?.fonts ?? [],
      body_font: t?.body_font ?? "",
      heading_font: t?.heading_font ?? "",
    };
  });
  // Async font adds build on the latest state, not the render they started in.
  const stateRef = useRef(state);

  const [fontError, setFontError] = useState("");
  const [googleFamily, setGoogleFamily] = useState("");
  const [weights, setWeights] = useState<number[]>([400, 700]);
  const [italic, setItalic] = useState(false);
  const [probing, setProbing] = useState(false);
  const [uploadFamily, setUploadFamily] = useState("");
  const [uploadWeight, setUploadWeight] = useState(400);
  const [uploadStyle, setUploadStyle] = useState<"normal" | "italic">("normal");
  const [uploading, setUploading] = useState(false);
  const [systemFamily, setSystemFamily] = useState("");
  const fileRef = useRef<HTMLInputElement>(null);
  const catalogId = useId();

  function update(next: ThemeState, emit = true) {
    stateRef.current = next;
    setState(next);
    if (emit) onChange({ ...toTheme(next) });
  }

  const findFont = (family: string) =>
    stateRef.current.fonts.find((f) => f.family.toLowerCase() === family.toLowerCase());

  function familyError(family: string): string {
    if (!FONT_FAMILY_RE.test(family)) return FAMILY_HINT;
    if (findFont(family)) return `${family} is already in the theme.`;
    if (stateRef.current.fonts.length >= MAX_FONTS)
      return `A theme holds at most ${MAX_FONTS} fonts.`;
    return "";
  }

  function addFont(font: ThemeFont) {
    const s = stateRef.current;
    update({ ...s, fonts: [...s.fonts, font] });
  }

  function removeFont(family: string) {
    const s = stateRef.current;
    update({
      ...s,
      fonts: s.fonts.filter((f) => f.family !== family),
      body_font: s.body_font === family ? "" : s.body_font,
      heading_font: s.heading_font === family ? "" : s.heading_font,
    });
  }

  async function addGoogleFont() {
    const family = googleFamily.trim();
    const err = familyError(family);
    setFontError(err);
    if (err) return;
    const picked = [...weights].sort((a, b) => a - b);
    // Not every family has every weight (or any weight axis): retry narrower.
    const attempts = [picked, [400], []].filter(
      (w, i, all) => all.findIndex((x) => x.join() === w.join()) === i
    );
    setProbing(true);
    try {
      for (const w of attempts) {
        const font = {
          family,
          source: "google" as const,
          weights: w,
          italic: w.length ? italic : false,
        };
        if (await googleFontExists(font)) {
          addFont(font);
          setGoogleFamily("");
          return;
        }
      }
      setFontError(`Google Fonts has no family called ${family}`);
    } finally {
      setProbing(false);
    }
  }

  async function uploadFont(file: File) {
    // Clear the input on every path so choosing the same file again fires onChange.
    const resetInput = () => {
      if (fileRef.current) fileRef.current.value = "";
    };
    if (!onUpload) return resetInput();
    const family = uploadFamily.trim();
    const existing = findFont(family);
    let err = "";
    if (!FONT_FAMILY_RE.test(family)) err = FAMILY_HINT;
    else if (existing && existing.source !== "upload")
      err = `${existing.family} is already in the theme.`;
    else if (existing?.source === "upload" && existing.files.length >= MAX_FONT_FILES)
      err = `A font holds at most ${MAX_FONT_FILES} files.`;
    else if (!existing && stateRef.current.fonts.length >= MAX_FONTS)
      err = `A theme holds at most ${MAX_FONTS} fonts.`;
    setFontError(err);
    if (err) return resetInput();
    setUploading(true);
    try {
      const url = await onUpload(file);
      const entry = { url, weight: uploadWeight, style: uploadStyle };
      const s = stateRef.current;
      const current = findFont(family);
      const fonts: ThemeFont[] =
        current?.source === "upload"
          ? s.fonts.map((f) =>
              f === current ? { ...current, files: [...current.files, entry] } : f
            )
          : [...s.fonts, { family, source: "upload", files: [entry] }];
      update({ ...s, fonts });
    } catch (e) {
      setFontError(e instanceof Error ? e.message : "Upload failed.");
    } finally {
      setUploading(false);
      resetInput();
    }
  }

  function addSystemFont() {
    const family = systemFamily.trim();
    const err = familyError(family);
    setFontError(err);
    if (err) return;
    addFont({ family, source: "system" });
    setSystemFamily("");
  }

  const theme = toTheme(state);

  return (
    <div className="space-y-6">
      <FontLoader theme={theme} />

      {/* Fonts */}
      <div className={dashboardSectionCardCn}>
        <div className="border-b border-zinc-100 px-5 py-4 dark:border-zinc-800">
          <p className="text-sm font-medium text-zinc-700 dark:text-zinc-300">Fonts</p>
          <p className="mt-0.5 text-xs text-zinc-400 dark:text-zinc-500">
            Fonts your site can use. Pick which one is used for body text and headings below.
          </p>
        </div>

        <div className="divide-y divide-zinc-100 dark:divide-zinc-800">
          {state.fonts.length === 0 ? (
            <p className="px-5 py-4 text-sm text-zinc-400 dark:text-zinc-500">No fonts yet.</p>
          ) : (
            state.fonts.map((f) => (
              <div key={f.family} className="flex items-center gap-3 px-5 py-3">
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="text-sm font-medium text-zinc-800 dark:text-zinc-100">
                      {f.family}
                    </span>
                    <span className="rounded bg-zinc-100 px-1.5 py-0.5 text-[10px] font-medium text-zinc-600 dark:bg-zinc-800 dark:text-zinc-300">
                      {SOURCE_LABEL[f.source]}
                    </span>
                    <span className="text-xs text-zinc-400 dark:text-zinc-500">
                      {fontDetail(f)}
                    </span>
                  </div>
                  <p
                    className="mt-1 truncate text-lg text-zinc-700 dark:text-zinc-200"
                    style={{ fontFamily: fontStack(f.family) }}
                  >
                    {SAMPLE}
                  </p>
                </div>
                <button
                  type="button"
                  onClick={() => removeFont(f.family)}
                  aria-label={`Remove ${f.family}`}
                  className={removeBtnCn}
                >
                  <Trash2 className="h-4 w-4" />
                </button>
              </div>
            ))
          )}

          {/* Usage */}
          <div className="grid gap-4 px-5 py-4 sm:grid-cols-2">
            {(
              [
                ["body_font", "Body font"],
                ["heading_font", "Heading font"],
              ] as const
            ).map(([field, label]) => (
              <div key={field}>
                <label htmlFor={`${catalogId}-${field}`} className={dashboardFieldLabelCn}>
                  {label}
                </label>
                <select
                  id={`${catalogId}-${field}`}
                  value={state[field]}
                  onChange={(e) => update({ ...stateRef.current, [field]: e.target.value })}
                  className={dashboardInputCn}
                >
                  <option value="">Site default</option>
                  {state.fonts.map((f) => (
                    <option key={f.family} value={f.family}>
                      {f.family}
                    </option>
                  ))}
                </select>
              </div>
            ))}
          </div>

          {/* Add a Google font */}
          <div className="space-y-3 px-5 py-4">
            <label htmlFor={`${catalogId}-google`} className={dashboardFieldLabelCn}>
              Add Google font
            </label>
            <div className="flex gap-2">
              <input
                id={`${catalogId}-google`}
                type="text"
                list={`${catalogId}-catalog`}
                aria-label="Google font family"
                value={googleFamily}
                onChange={(e) => setGoogleFamily(e.target.value)}
                placeholder="e.g. Open Sans"
                className={dashboardInputCn}
              />
              <datalist id={`${catalogId}-catalog`}>
                {FONT_CATALOG.map((f) => (
                  <option key={f.family} value={f.family} label={f.category} />
                ))}
              </datalist>
              <button
                type="button"
                onClick={addGoogleFont}
                disabled={probing || !googleFamily.trim()}
                aria-label="Add Google font"
                className={secondaryBtnCn}
              >
                <Plus className="h-4 w-4" />
                {probing ? "Checking…" : "Add"}
              </button>
            </div>
            <div className="flex flex-wrap items-center gap-x-4 gap-y-2 text-xs text-zinc-600 dark:text-zinc-300">
              {PICK_WEIGHTS.map((w) => (
                <label key={w} className="flex cursor-pointer items-center gap-1.5">
                  <input
                    type="checkbox"
                    checked={weights.includes(w)}
                    onChange={(e) =>
                      setWeights((prev) =>
                        e.target.checked ? [...prev, w] : prev.filter((x) => x !== w)
                      )
                    }
                  />
                  {w}
                </label>
              ))}
              <label className="flex cursor-pointer items-center gap-1.5">
                <input
                  type="checkbox"
                  checked={italic}
                  onChange={(e) => setItalic(e.target.checked)}
                />
                Italic
              </label>
            </div>
          </div>

          {/* Upload a font */}
          {onUpload && (
            <div className="space-y-3 px-5 py-4">
              <p className={dashboardFieldLabelCn}>Upload font</p>
              <div className="grid gap-2 sm:grid-cols-[1fr_auto_auto_auto]">
                <input
                  type="text"
                  aria-label="Uploaded font family"
                  value={uploadFamily}
                  onChange={(e) => setUploadFamily(e.target.value)}
                  placeholder="Family name, e.g. Brand Sans"
                  className={dashboardInputCn}
                />
                <select
                  aria-label="Font file weight"
                  value={uploadWeight}
                  onChange={(e) => setUploadWeight(Number(e.target.value))}
                  className={dashboardInputCn}
                >
                  {FILE_WEIGHTS.map((w) => (
                    <option key={w} value={w}>
                      {w}
                    </option>
                  ))}
                </select>
                <select
                  aria-label="Font file style"
                  value={uploadStyle}
                  onChange={(e) => setUploadStyle(e.target.value as "normal" | "italic")}
                  className={dashboardInputCn}
                >
                  <option value="normal">Normal</option>
                  <option value="italic">Italic</option>
                </select>
                <input
                  ref={fileRef}
                  type="file"
                  aria-label="Font file"
                  accept=".woff2,.woff,.ttf,.otf"
                  className="hidden"
                  onChange={(e) => {
                    const f = e.target.files?.[0];
                    if (f) uploadFont(f);
                  }}
                />
                <button
                  type="button"
                  disabled={uploading}
                  onClick={() => fileRef.current?.click()}
                  className={secondaryBtnCn}
                >
                  <Upload className="h-4 w-4" />
                  {uploading ? "Uploading…" : "Choose file"}
                </button>
              </div>
              <p className="text-xs text-zinc-400 dark:text-zinc-500">
                .woff2, .woff, .ttf or .otf. Upload one file per weight and style; files with the
                same family name are grouped into one font.
              </p>
            </div>
          )}

          {/* System font */}
          <div className="space-y-3 px-5 py-4">
            <label htmlFor={`${catalogId}-system`} className={dashboardFieldLabelCn}>
              System font
            </label>
            <div className="flex gap-2">
              <input
                id={`${catalogId}-system`}
                type="text"
                aria-label="System font family"
                value={systemFamily}
                onChange={(e) => setSystemFamily(e.target.value)}
                placeholder="e.g. Georgia"
                className={dashboardInputCn}
              />
              <button
                type="button"
                onClick={addSystemFont}
                disabled={!systemFamily.trim()}
                aria-label="Add system font"
                className={secondaryBtnCn}
              >
                <Plus className="h-4 w-4" />
                Add
              </button>
            </div>
          </div>

          {fontError && (
            <p role="alert" className="px-5 py-3 text-xs text-red-600 dark:text-red-400">
              {fontError}
            </p>
          )}
        </div>
      </div>

      <ColorCard
        title="Colours"
        help="Brand colours offered when styling text and icons."
        noun="Colour"
        fallback="#000000"
        max={MAX_COLORS}
        rows={state.colors}
        onRows={(colors, emit) => update({ ...stateRef.current, colors }, emit)}
      />
      <ColorCard
        title="Surfaces"
        help="Backgrounds your site uses (page, cards, header). Used to check that icon and text colours stay visible."
        noun="Surface"
        fallback="#ffffff"
        max={MAX_SURFACES}
        rows={state.surfaces}
        onRows={(surfaces, emit) => update({ ...stateRef.current, surfaces }, emit)}
      />
    </div>
  );
}

function ColorCard({
  title,
  help,
  noun,
  fallback,
  max,
  rows,
  onRows,
}: {
  title: string;
  help: string;
  noun: string;
  fallback: string;
  max: number;
  rows: ColorRow[];
  /** `emit` is false while the hex box holds an invalid colour. */
  onRows: (rows: ColorRow[], emit: boolean) => void;
}) {
  const patch = (i: number, p: Partial<ColorRow>, emit = true) =>
    onRows(
      rows.map((r, j) => (j === i ? { ...r, ...p } : r)),
      emit
    );

  return (
    <div className={dashboardSectionCardCn}>
      <div className="border-b border-zinc-100 px-5 py-4 dark:border-zinc-800">
        <p className="text-sm font-medium text-zinc-700 dark:text-zinc-300">{title}</p>
        <p className="mt-0.5 text-xs text-zinc-400 dark:text-zinc-500">{help}</p>
      </div>
      <div className="space-y-3 p-5">
        {rows.map((r, i) => (
          <div key={r.id} className="flex items-center gap-2">
            <input
              type="text"
              aria-label={`${noun} ${i + 1} name`}
              value={r.name}
              maxLength={40}
              onChange={(e) => patch(i, { name: e.target.value })}
              placeholder="Name"
              className={dashboardInputCn}
            />
            <input
              type="color"
              value={r.value}
              onChange={(e) => patch(i, { value: e.target.value, text: e.target.value })}
              className="h-8 w-10 shrink-0 cursor-pointer rounded border border-zinc-200 bg-transparent p-0.5 dark:border-zinc-700"
              aria-label={`Pick ${noun.toLowerCase()} ${i + 1}`}
            />
            <input
              type="text"
              aria-label={`${noun} ${i + 1} hex`}
              value={r.text}
              onChange={(e) => {
                const hex = normalizeHex(e.target.value);
                if (hex) patch(i, { value: hex, text: e.target.value });
                else patch(i, { text: e.target.value }, false);
              }}
              onBlur={() => {
                if (!normalizeHex(r.text)) patch(i, { text: r.value }, false);
              }}
              placeholder={fallback}
              className={`${dashboardInputCn} w-32 shrink-0 font-mono`}
            />
            <button
              type="button"
              onClick={() =>
                onRows(
                  rows.filter((_, j) => j !== i),
                  true
                )
              }
              aria-label={`Remove ${noun.toLowerCase()} ${i + 1}`}
              className={removeBtnCn}
            >
              <Trash2 className="h-4 w-4" />
            </button>
          </div>
        ))}
        <button
          type="button"
          disabled={rows.length >= max}
          onClick={() =>
            onRows(
              [
                ...rows,
                {
                  id: `c${rowSeq++}`,
                  name: `${noun} ${rows.length + 1}`,
                  value: fallback,
                  text: fallback,
                },
              ],
              true
            )
          }
          className={secondaryBtnCn}
        >
          <Plus className="h-4 w-4" />
          Add {noun.toLowerCase()}
        </button>
        {rows.length >= max && (
          <p className="text-xs text-zinc-400 dark:text-zinc-500">
            At most {max} {title.toLowerCase()}.
          </p>
        )}
      </div>
    </div>
  );
}
