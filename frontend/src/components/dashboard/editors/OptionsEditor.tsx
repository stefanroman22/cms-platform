"use client";

import { useState } from "react";
import type { EditorProps } from "./index";
import { dashboardSectionCardCn } from "@/lib/styles";
import {
  OPTION_FIELD_TYPES,
  OptionFieldInput,
  readOptionValue,
  type OptionField,
  type OptionValue,
} from "./OptionFields";

function parseSchema(raw: unknown): OptionField[] {
  if (Array.isArray(raw)) return raw as OptionField[];
  return [];
}

function parseValues(raw: unknown): Record<string, unknown> {
  if (raw && typeof raw === "object" && !Array.isArray(raw)) return raw as Record<string, unknown>;
  return {};
}

/** A Display Options service (ADR-0013): one value per declared toggle,
 *  select or color field. Never translated; the schema is fixed. */
export function OptionsEditor({ initialContent, onChange }: EditorProps) {
  const schema = parseSchema(initialContent._schema);
  const fields = schema.filter((f) => OPTION_FIELD_TYPES.includes(f.type));
  const [values, setValues] = useState<Record<string, unknown>>(() =>
    parseValues(initialContent.values)
  );

  function update(key: string, val: OptionValue) {
    const next: Record<string, OptionValue> = {};
    fields.forEach((f) => {
      next[f.key] = f.key === key ? val : readOptionValue(f, values[f.key]);
    });
    setValues(next);
    onChange({ _schema: schema, values: next });
  }

  if (fields.length === 0) {
    return (
      <div className={dashboardSectionCardCn}>
        <div className="p-5">
          <p className="text-sm text-zinc-500 dark:text-zinc-400">
            These display options have no field schema defined.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className={dashboardSectionCardCn}>
      <div className="divide-y divide-zinc-100 dark:divide-zinc-800">
        {fields.map((field) => (
          <div
            key={field.key}
            className={`px-5 py-4 ${
              field.type === "toggle" ? "flex items-center justify-between gap-4" : "space-y-2"
            }`}
          >
            <p className="text-sm font-medium text-zinc-700 dark:text-zinc-300">{field.label}</p>
            <OptionFieldInput
              field={field}
              value={values[field.key]}
              onChange={(val) => update(field.key, val)}
            />
          </div>
        ))}
      </div>
    </div>
  );
}
