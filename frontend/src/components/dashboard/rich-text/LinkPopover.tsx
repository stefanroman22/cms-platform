"use client";

import { useEffect, useId, useRef, useState } from "react";
import type { Editor } from "@tiptap/react";
import { dashboardFieldLabelCn, dashboardInputCn, dashboardPrimaryBtnCn } from "@/lib/styles";
import { normalizeLinkInput } from "./linkInput";

export function LinkPopover({ editor, onClose }: { editor: Editor; onClose: () => void }) {
  const initial = (editor.getAttributes("link").href as string | undefined) ?? "";
  const [value, setValue] = useState(initial);
  const [error, setError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const boxRef = useRef<HTMLDivElement>(null);
  const id = useId();

  // The parent (Toolbar) re-renders on every keystroke's editor-state read and
  // passes a fresh `onClose` arrow each time; keeping it in a ref (updated
  // every render, not just on change) means the outside-click listener below
  // never needs to be torn down and re-added mid-typing.
  const onCloseRef = useRef(onClose);
  useEffect(() => {
    onCloseRef.current = onClose;
  });

  // Mount-only: focusing/selecting on every render (e.g. because `onClose`'s
  // identity changed) would blow away whatever the user had already typed.
  useEffect(() => {
    inputRef.current?.focus();
    inputRef.current?.select();
  }, []);

  useEffect(() => {
    const onDown = (e: MouseEvent) => {
      if (boxRef.current && !boxRef.current.contains(e.target as Node)) onCloseRef.current();
    };
    document.addEventListener("mousedown", onDown);
    return () => document.removeEventListener("mousedown", onDown);
  }, []);

  function apply() {
    const href = normalizeLinkInput(value);
    if (!href) {
      setError("Enter a web address, email address, phone number, /page or #section.");
      return;
    }
    const { empty } = editor.state.selection;
    if (empty && !editor.isActive("link")) {
      editor
        .chain()
        .focus()
        .insertContent({
          type: "text",
          text: value.trim(),
          marks: [{ type: "link", attrs: { href } }],
        })
        .unsetMark("link")
        .run();
    } else {
      editor.chain().focus().extendMarkRange("link").setLink({ href }).run();
    }
    onClose();
  }

  function remove() {
    editor.chain().focus().extendMarkRange("link").unsetLink().run();
    onClose();
  }

  return (
    <div
      ref={boxRef}
      role="dialog"
      aria-label="Edit link"
      className="absolute left-1.5 top-full z-20 mt-1 w-80 rounded-lg border border-zinc-200 bg-white p-3 shadow-lg dark:border-zinc-700 dark:bg-zinc-900"
      onKeyDown={(e) => {
        // Never let the toolbar's roving-tabindex handler (role="toolbar",
        // an ancestor) see arrow keys typed/pressed in here — it would hijack
        // focus away from this popover's own input/buttons.
        if (e.key === "ArrowLeft" || e.key === "ArrowRight") {
          e.stopPropagation();
          return;
        }
        if (e.key === "Escape") {
          e.preventDefault();
          onClose();
          editor.commands.focus();
        }
      }}
    >
      <label htmlFor={id} className={dashboardFieldLabelCn}>
        Link address
      </label>
      <input
        ref={inputRef}
        id={id}
        value={value}
        onChange={(e) => {
          setValue(e.target.value);
          setError(null);
        }}
        onKeyDown={(e) => {
          if (e.key === "Enter") {
            e.preventDefault();
            apply();
          }
        }}
        placeholder="https://…, name@email.com, +40…, /contact"
        aria-invalid={error ? true : undefined}
        aria-describedby={error ? `${id}-err` : undefined}
        className={dashboardInputCn}
      />
      {error && (
        <p id={`${id}-err`} role="alert" className="mt-1.5 text-xs text-red-600 dark:text-red-400">
          {error}
        </p>
      )}
      <div className="mt-3 flex justify-end gap-2">
        {initial && (
          <button
            type="button"
            onClick={remove}
            className="cursor-pointer rounded-md px-3 py-1.5 text-xs font-medium text-red-600 hover:bg-red-50 dark:hover:bg-red-950"
          >
            Remove link
          </button>
        )}
        <button
          type="button"
          onClick={onClose}
          className="cursor-pointer rounded-md px-3 py-1.5 text-xs font-medium text-zinc-600 hover:bg-zinc-100 dark:text-zinc-300 dark:hover:bg-zinc-800"
        >
          Cancel
        </button>
        <button type="button" onClick={apply} className={dashboardPrimaryBtnCn}>
          Apply
        </button>
      </div>
    </div>
  );
}
