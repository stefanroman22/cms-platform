"use client";

import { useEffect, useId, useRef, useState } from "react";
import { EditorContent, useEditor, type Editor } from "@tiptap/react";
import { normalizeInline, parse, serialize } from "@/lib/cms-rich-text";
import { inlineExtensions, richExtensions } from "./extensions";
import { fromStored, toStored, type RichMode } from "./serialize";
import { Toolbar } from "./Toolbar";

export const RICH_LIMITS: Record<RichMode, number> = { inline: 2000, rich: 50000 };

export interface RichTextEditorProps {
  value: string;
  onChange: (value: string) => void;
  mode: RichMode;
  /** Accessible name of the editing area. */
  label: string;
  placeholder?: string;
  disabled?: boolean;
  id?: string;
  /** Test/advanced hook: receives the TipTap editor once created. */
  onReady?: (editor: Editor) => void;
}

/** Inline paste: an inline document holds one paragraph, so flatten blocks to <br>. */
const inlinePaste = (html: string) => `<p>${serialize(normalizeInline(parse(html).children))}</p>`;

export function RichTextEditor({
  value,
  onChange,
  mode,
  label,
  placeholder,
  disabled,
  id,
  onReady,
}: RichTextEditorProps) {
  const autoId = useId();
  const onChangeRef = useRef(onChange);
  useEffect(() => {
    onChangeRef.current = onChange;
  });
  const [length, setLength] = useState(() => value.length);
  const [linkOpen, setLinkOpen] = useState(false);

  const editor = useEditor({
    extensions: mode === "inline" ? inlineExtensions(placeholder) : richExtensions(placeholder),
    content: fromStored(value, mode),
    editable: !disabled,
    immediatelyRender: false,
    editorProps: {
      attributes: {
        role: "textbox",
        "aria-multiline": mode === "rich" ? "true" : "false",
        "aria-label": label,
        id: id ?? autoId,
        class: `prose prose-sm prose-zinc dark:prose-invert max-w-none px-3 py-2 focus:outline-none ${
          mode === "rich" ? "min-h-[10rem]" : "min-h-[2.25rem]"
        }`,
      },
      transformPastedHTML: mode === "inline" ? inlinePaste : undefined,
      handleKeyDown: (_view, event) => {
        if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k") {
          event.preventDefault();
          setLinkOpen(true);
          return true;
        }
        return false;
      },
    },
    onUpdate: ({ editor: e }) => {
      const stored = toStored(e.getHTML(), mode);
      setLength(stored.length);
      onChangeRef.current(stored);
    },
  });

  useEffect(() => {
    if (editor) onReady?.(editor);
  }, [editor, onReady]);
  useEffect(() => {
    editor?.setEditable(!disabled);
  }, [editor, disabled]);

  const limit = RICH_LIMITS[mode];
  const over = length > limit;
  return (
    <div
      data-mode={mode}
      className={`relative rounded-lg border bg-white transition-colors focus-within:ring-2 focus-within:ring-zinc-900/10 dark:bg-zinc-950 dark:focus-within:ring-zinc-100/10 ${
        over ? "border-red-400 dark:border-red-500" : "border-zinc-200 dark:border-zinc-700"
      }`}
    >
      <Toolbar editor={editor} mode={mode} linkOpen={linkOpen} setLinkOpen={setLinkOpen} />
      <EditorContent editor={editor} />
      {length >= limit * 0.8 && (
        <p
          aria-live="polite"
          className={`px-3 pb-1.5 text-right text-[11px] ${over ? "text-red-600 dark:text-red-400" : "text-zinc-400"}`}
        >
          {length.toLocaleString()} / {limit.toLocaleString()} characters incl. formatting
          {over && " — too long, the save will be rejected"}
        </p>
      )}
    </div>
  );
}
