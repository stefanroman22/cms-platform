"use client";

import { useState } from "react";
import { X } from "lucide-react";
import { dashboardInputCn } from "@/lib/styles";
import { useProjectTheme } from "@/components/dashboard/theme/ProjectThemeContext";

/** A display-option field definition (ADR-0013): a `_schema` entry of type
 *  toggle, select or color, in a repeater or an options service. */
export interface OptionField {
  key: string;
  label: string;
  type: "toggle" | "select" | "color";
  options?: { value: string; label: string }[];
  default?: boolean | string;
}

export type OptionValue = boolean | string;

export const OPTION_FIELD_TYPES: readonly string[] = ["toggle", "select", "color"];

/** `#abc` / `#AABBCC` / `aabbcc` → `#aabbcc`; null when not a hex colour. */
function normalizeHex(raw: string): string | null {
  const m = /^#?([0-9a-f]{3}|[0-9a-f]{6})$/i.exec(raw.trim());
  if (!m) return null;
  const h = m[1].toLowerCase();
  return `#${h.length === 3 ? [...h].map((c) => c + c).join("") : h}`;
}

/** The value a field shows: the stored one when valid for the field, else the
 *  field's `default` (else off / not chosen / no colour). */
export function readOptionValue(field: OptionField, raw: unknown): OptionValue {
  if (field.type === "toggle") {
    if (typeof raw === "boolean") return raw;
    return typeof field.default === "boolean" ? field.default : false;
  }
  if (field.type === "select") {
    const values = (field.options ?? []).map((o) => o.value);
    if (typeof raw === "string") return values.includes(raw) ? raw : "";
    return typeof field.default === "string" && values.includes(field.default) ? field.default : "";
  }
  if (typeof raw === "string") return raw === "" ? "" : (normalizeHex(raw) ?? "");
  return typeof field.default === "string" ? (normalizeHex(field.default) ?? "") : "";
}

const btnCn =
  "flex items-center gap-1.5 rounded-lg border border-zinc-200 dark:border-zinc-700 px-3 py-1.5 text-xs text-zinc-600 dark:text-zinc-300 hover:bg-zinc-50 dark:hover:bg-zinc-800 disabled:opacity-40 disabled:cursor-not-allowed transition-colors cursor-pointer";
const pressedRingCn =
  "ring-2 ring-zinc-900 ring-offset-1 dark:ring-zinc-100 dark:ring-offset-zinc-900";

/** One control for a toggle, select or color field. */
export function OptionFieldInput({
  field,
  value,
  onChange,
}: {
  field: OptionField;
  value: unknown;
  onChange: (value: OptionValue) => void;
}) {
  if (field.type === "toggle") {
    const on = readOptionValue(field, value) === true;
    return (
      <button
        type="button"
        role="switch"
        aria-checked={on}
        aria-label={field.label}
        onClick={() => onChange(!on)}
        className={`relative inline-flex h-5 w-9 shrink-0 cursor-pointer items-center rounded-full transition-colors ${
          on ? "bg-zinc-900 dark:bg-zinc-100" : "bg-zinc-200 dark:bg-zinc-700"
        }`}
      >
        <span
          className={`inline-block h-3.5 w-3.5 rounded-full bg-white transition-transform dark:bg-zinc-900 ${
            on ? "translate-x-4" : "translate-x-0.5"
          }`}
        />
      </button>
    );
  }
  if (field.type === "select") {
    const current = readOptionValue(field, value) as string;
    return (
      <select
        aria-label={field.label}
        value={current}
        onChange={(e) => onChange(e.target.value)}
        className={`${dashboardInputCn} cursor-pointer`}
      >
        {current === "" && <option value="">Default</option>}
        {(field.options ?? []).map((o) => (
          <option key={o.value} value={o.value}>
            {o.label}
          </option>
        ))}
      </select>
    );
  }
  return (
    <ColorOption
      label={field.label}
      value={readOptionValue(field, value) as string}
      onChange={onChange}
    />
  );
}

function ColorOption({
  label,
  value,
  onChange,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
}) {
  const { theme } = useProjectTheme();
  // What the hex box shows; only a valid colour is committed.
  const [text, setText] = useState(value);
  const [seen, setSeen] = useState(value);
  if (value !== seen) {
    setSeen(value);
    setText(value);
  }

  function commit(hex: string, shown = hex) {
    setSeen(hex);
    setText(shown);
    if (hex !== value) onChange(hex);
  }

  const swatches: { name: string; value: string }[] = [];
  for (const c of theme ? [...theme.colors, ...theme.surfaces] : []) {
    const hex = normalizeHex(c.value);
    if (hex && !swatches.some((s) => s.value === hex)) swatches.push({ name: c.name, value: hex });
  }

  return (
    <div role="group" aria-label={label} className="space-y-2">
      <div className="flex flex-wrap items-center gap-2">
        {value ? (
          <span
            aria-hidden
            className="h-8 w-8 shrink-0 rounded-lg border border-zinc-200 dark:border-zinc-700"
            style={{ backgroundColor: value }}
          />
        ) : (
          <span className="flex h-8 shrink-0 items-center rounded-lg border border-dashed border-zinc-300 px-2.5 text-xs text-zinc-500 dark:border-zinc-600 dark:text-zinc-400">
            Default
          </span>
        )}
        {/* Neutral placeholder, not black: re-picking the shown value fires no change. */}
        <input
          type="color"
          aria-label={`Pick ${label} colour`}
          value={value || "#777777"}
          onChange={(e) => commit(e.target.value.toLowerCase())}
          className="h-8 w-10 shrink-0 cursor-pointer rounded border border-zinc-200 bg-transparent p-0.5 dark:border-zinc-700"
        />
        <input
          type="text"
          aria-label={`${label} hex`}
          value={text}
          onChange={(e) => {
            const hex = normalizeHex(e.target.value);
            if (hex) commit(hex, e.target.value);
            else setText(e.target.value);
          }}
          onBlur={() => setText(value)}
          placeholder="Default"
          className={`${dashboardInputCn} w-32 shrink-0 font-mono`}
        />
        <button type="button" disabled={value === ""} onClick={() => commit("")} className={btnCn}>
          <X className="h-3.5 w-3.5" />
          Clear
        </button>
      </div>
      {swatches.length > 0 && (
        <div className="flex flex-wrap items-center gap-2">
          {swatches.map((s) => {
            const pressed = value === s.value;
            return (
              <button
                key={s.value}
                type="button"
                aria-pressed={pressed}
                title={`${s.name} (${s.value})`}
                onClick={() => commit(s.value)}
                className={`${btnCn} ${pressed ? pressedRingCn : ""}`}
              >
                <span
                  aria-hidden
                  className="h-4 w-4 rounded-full border border-zinc-200 dark:border-zinc-700"
                  style={{ backgroundColor: s.value }}
                />
                {s.name}
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}
