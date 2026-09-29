"use client";

import { useState } from "react";
import type { EditorProps } from "./index";
import { dashboardInputCn, dashboardFieldLabelCn, dashboardSectionCardCn } from "@/lib/styles";
import { InfoTooltip } from "@/components/dashboard/InfoTooltip";
import { ContentField } from "@/components/dashboard/rich-text/ContentField";

export function TextBlockEditor({ initialContent, onChange, richText, fieldFormats }: EditorProps) {
  const [title, setTitle] = useState(String(initialContent.title ?? ""));
  const [body, setBody] = useState(String(initialContent.body ?? ""));

  function emit(next: { title: string; body: string }) {
    onChange(next);
  }

  if (richText) {
    return (
      <div className={`${dashboardSectionCardCn} divide-y divide-zinc-100 dark:divide-zinc-800`}>
        <div className="p-5">
          <span className={dashboardFieldLabelCn}>Title</span>
          <ContentField
            format={fieldFormats?.title ?? "inline"}
            value={title}
            label="Title"
            placeholder="Enter section title…"
            onChange={(v) => {
              setTitle(v);
              emit({ title: v, body });
            }}
          />
        </div>
        <div className="p-5">
          <span className={dashboardFieldLabelCn}>Body</span>
          <ContentField
            format={fieldFormats?.body ?? "rich"}
            value={body}
            label="Body"
            placeholder="Write content here…"
            onChange={(v) => {
              setBody(v);
              emit({ title, body: v });
            }}
          />
        </div>
      </div>
    );
  }

  return (
    <div className={`${dashboardSectionCardCn} divide-y divide-zinc-100 dark:divide-zinc-800`}>
      {/* Title */}
      <div className="p-5">
        <label className={dashboardFieldLabelCn}>Title</label>
        <input
          type="text"
          value={title}
          onChange={(e) => {
            setTitle(e.target.value);
            emit({ title: e.target.value, body });
          }}
          placeholder="Enter section title…"
          className={dashboardInputCn}
        />
      </div>

      {/* Body */}
      <div className="p-5">
        <div className="flex items-center justify-between mb-1.5">
          <span className="flex items-center gap-1.5">
            <label className={dashboardFieldLabelCn} style={{ marginBottom: 0 }}>
              Body
            </label>
            <InfoTooltip hint="Supports Markdown: **bold**, *italic*, [link text](https://url.com), # Heading, - bullet list" />
          </span>
          <span className="text-[10px] text-zinc-400 dark:text-zinc-500">Markdown supported</span>
        </div>
        <textarea
          value={body}
          onChange={(e) => {
            setBody(e.target.value);
            emit({ title, body: e.target.value });
          }}
          rows={10}
          placeholder="Write content here…"
          className={`${dashboardInputCn} resize-y`}
        />
      </div>
    </div>
  );
}
