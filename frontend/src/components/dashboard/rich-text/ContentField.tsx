"use client";

import { escapeText, plainText } from "@/lib/cms-rich-text";
import { dashboardInputCn } from "@/lib/styles";
import { RichTextEditor } from "./RichTextEditor";

export type FieldFormat = "plain" | "inline" | "rich";

export function ContentField({
  format,
  value,
  onChange,
  label,
  placeholder,
  inputType = "text",
}: {
  format: FieldFormat;
  value: string;
  onChange: (v: string) => void;
  label: string;
  placeholder?: string;
  inputType?: "text" | "url" | "email" | "tel";
}) {
  if (format === "plain") {
    return (
      <input
        type={inputType}
        value={value}
        aria-label={label}
        placeholder={placeholder}
        onChange={(e) => onChange(e.target.value)}
        className={dashboardInputCn}
      />
    );
  }
  // Keyed by format so an admin format change remounts the editor in the new mode.
  return (
    <RichTextEditor
      key={format}
      mode={format}
      value={value}
      onChange={onChange}
      label={label}
      placeholder={placeholder}
    />
  );
}

/** Convert a value when an admin changes a field's format, so nothing is lost or double-escaped. */
export function convertValue(value: string, from: FieldFormat, to: FieldFormat): string {
  if (from === to || !value) return value;
  if (to === "plain")
    return plainText(value, {
      format: from === "rich" ? "rich" : "inline",
      keepLineBreaks: from === "rich",
    });
  if (from === "plain") {
    const escaped = value.split("\n").map(escapeText);
    return to === "inline" ? escaped.join("<br>") : `<p>${escaped.join("<br>")}</p>`;
  }
  if (to === "rich") return `<p>${value}</p>`; // inline → rich: one paragraph
  return plainText(value, { format: "rich", keepLineBreaks: true })
    .split("\n")
    .map(escapeText)
    .join("<br>"); // rich → inline
}
