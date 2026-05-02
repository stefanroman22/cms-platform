"use client";

import { useState } from "react";
import type { EditorProps } from "./index";
import { dashboardInputCn, dashboardFieldLabelCn, dashboardSectionCardCn } from "@/lib/styles";
import { InfoTooltip } from "@/components/dashboard/InfoTooltip";

export function TextBlockEditor({ initialContent, onChange }: EditorProps) {
  const [title, setTitle] = useState(String(initialContent.title ?? ""));
  const [body, setBody] = useState(String(initialContent.body ?? ""));

  function emit(next: { title: string; body: string }) {
    onChange(next);
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
