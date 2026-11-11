// Vendored from CMS client-kit/rich-text v1.3.1 — do not edit; re-sync instead.
// Display options (ADR-0013): toggle / select / color fields and the `options` service.
import { contrastRatio } from "./theme";

export interface OptionChoice { value: string; label: string }
export interface OptionField {
  key: string; label: string; type: "toggle" | "select" | "color";
  options?: OptionChoice[]; default?: boolean | string;
}
export type OptionValue = boolean | string;

const HEX_RE = /^#[0-9a-fA-F]{6}$/;

const isObj = (v: unknown): v is Record<string, unknown> => typeof v === "object" && v !== null && !Array.isArray(v);

/** "#rrggbb" (lowercased) or "" when `raw` is not a 6-digit hex colour. */
export function readColor(raw: unknown): string {
  return typeof raw === "string" && HEX_RE.test(raw) ? raw.toLowerCase() : "";
}

/** `raw` when it is a real boolean, else `fallback`. */
export function readToggle(raw: unknown, fallback: boolean): boolean {
  return typeof raw === "boolean" ? raw : fallback;
}

function readField(f: unknown): OptionField | null {
  if (!isObj(f) || typeof f.key !== "string" || typeof f.label !== "string") return null;
  const type = f.type;
  if (type !== "toggle" && type !== "select" && type !== "color") return null;
  const field: OptionField = { key: f.key, label: f.label, type };
  if (type === "select") {
    const options: OptionChoice[] = [];
    if (Array.isArray(f.options)) {
      for (const o of f.options) {
        if (isObj(o) && typeof o.value === "string" && typeof o.label === "string") options.push({ value: o.value, label: o.label });
      }
    }
    if (!options.length) return null;
    field.options = options;
  }
  if (typeof f.default === (type === "toggle" ? "boolean" : "string")) field.default = f.default as boolean | string;
  return field;
}

/** The well-formed option field definitions (toggle/select/color) of a service's or repeater's `_schema`; anything else is skipped. */
export function readOptionFields(schema: unknown): OptionField[] {
  if (!Array.isArray(schema)) return [];
  const out: OptionField[] = [];
  for (const f of schema) {
    const field = readField(f);
    if (field) out.push(field);
  }
  return out;
}

// The stored value when it is valid for the field and the field's type matches the site default's; else undefined.
function readValue(field: OptionField, v: unknown, fallback: OptionValue): OptionValue | undefined {
  if (field.type === "toggle") return typeof fallback === "boolean" && typeof v === "boolean" ? v : undefined;
  if (typeof fallback !== "string" || typeof v !== "string") return undefined;
  if (field.type === "select") return v !== "" && field.options?.some((o) => o.value === v) ? v : undefined;
  return v === "" || HEX_RE.test(v) ? v.toLowerCase() : undefined;
}

/** Typed values of an `options` service. */
export function readOptions<T extends Record<string, OptionValue>>(raw: unknown, defaults: T): T {
  const out: Record<string, OptionValue> = { ...defaults };
  if (!isObj(raw) || !isObj(raw.values)) return out as T;
  const values = raw.values;
  const fields = readOptionFields(raw._schema);
  for (const key of Object.keys(defaults)) {
    const field = fields.find((f) => f.key === key);
    if (!field || !Object.prototype.hasOwnProperty.call(values, key)) continue;
    const v = readValue(field, values[key], defaults[key]);
    if (v !== undefined) out[key] = v;
  }
  return out as T;
}

/** `dark` or `light`, whichever has the higher WCAG contrast against `background` (a #rrggbb colour); `dark` when `background` is not a valid colour. */
export function inkOn(background: string, dark = "#111827", light = "#ffffff"): string {
  if (!HEX_RE.test(background) || !HEX_RE.test(light)) return dark;
  if (!HEX_RE.test(dark)) return light;
  return contrastRatio(background, dark) >= contrastRatio(background, light) ? dark : light;
}
