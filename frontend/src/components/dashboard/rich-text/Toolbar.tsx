"use client";

import { useEffect, useRef, type FocusEvent, type KeyboardEvent, type ReactNode } from "react";
import { useEditorState, type Editor } from "@tiptap/react";
import {
  Bold,
  Italic,
  Link2,
  List,
  ListOrdered,
  Minus,
  Quote,
  Redo2,
  RemoveFormatting,
  Strikethrough,
  Underline,
  Undo2,
  Unlink,
} from "lucide-react";
import { LinkPopover } from "./LinkPopover";
import type { RichMode } from "./serialize";

type BlockStyle = "p" | "h2" | "h3" | "h4";

function Btn({
  label,
  shortcut,
  active,
  disabled,
  onClick,
  children,
}: {
  label: string;
  shortcut?: string;
  active?: boolean;
  disabled?: boolean;
  onClick: () => void;
  children: ReactNode;
}) {
  return (
    <button
      type="button"
      aria-label={label}
      title={shortcut ? `${label} (${shortcut})` : label}
      aria-pressed={active === undefined ? undefined : active}
      disabled={disabled}
      onMouseDown={(e) => e.preventDefault()}
      onClick={onClick}
      className={`inline-flex h-7 w-7 cursor-pointer items-center justify-center rounded transition-colors disabled:cursor-not-allowed disabled:opacity-30 ${
        active
          ? "bg-zinc-900 text-white dark:bg-zinc-100 dark:text-zinc-900"
          : "text-zinc-600 hover:bg-zinc-100 dark:text-zinc-300 dark:hover:bg-zinc-800"
      }`}
    >
      {children}
    </button>
  );
}

const Sep = () => <span aria-hidden className="mx-1 h-4 w-px bg-zinc-200 dark:bg-zinc-700" />;
const ic = "h-3.5 w-3.5";

export function Toolbar({
  editor,
  mode,
  linkOpen,
  setLinkOpen,
}: {
  editor: Editor | null;
  mode: RichMode;
  linkOpen: boolean;
  setLinkOpen: (open: boolean) => void;
}) {
  const barRef = useRef<HTMLDivElement>(null);
  const s = useEditorState({
    editor,
    selector: ({ editor: e }) =>
      e
        ? {
            bold: e.isActive("bold"),
            italic: e.isActive("italic"),
            underline: e.isActive("underline"),
            strike: e.isActive("strike"),
            bullet: e.isActive("bulletList"),
            ordered: e.isActive("orderedList"),
            quote: e.isActive("blockquote"),
            link: e.isActive("link"),
            block: (e.isActive("heading", { level: 2 })
              ? "h2"
              : e.isActive("heading", { level: 3 })
                ? "h3"
                : e.isActive("heading", { level: 4 })
                  ? "h4"
                  : "p") as BlockStyle,
            canUndo: e.can().undo(),
            canRedo: e.can().redo(),
          }
        : null,
  });

  const items = () =>
    Array.from(
      barRef.current?.querySelectorAll<HTMLElement>("button:not(:disabled), select") ?? []
    );

  // Real roving tabindex: exactly one control is in the page's Tab order at a
  // time (the last-focused one, or the first by default); Tab enters/leaves
  // the toolbar as a single stop, arrows move focus within it. Self-healing —
  // reapplied after every render — so a control that becomes disabled (e.g.
  // Undo when the history is empty) never leaves the toolbar with zero
  // tabbable controls.
  useEffect(() => {
    const els = items();
    if (!els.length) return;
    const current = els.find((el) => el.tabIndex === 0) ?? els[0];
    els.forEach((el) => {
      el.tabIndex = el === current ? 0 : -1;
    });
  });

  const onFocus = (ev: FocusEvent<HTMLDivElement>) => {
    const target = ev.target;
    if (target === barRef.current) return;
    items().forEach((el) => {
      el.tabIndex = el === target ? 0 : -1;
    });
  };

  if (!editor || !s)
    return <div className="h-9 border-b border-zinc-200 dark:border-zinc-700" aria-hidden />;
  const chain = () => editor.chain().focus();

  const onKeyDown = (ev: KeyboardEvent<HTMLDivElement>) => {
    if (ev.key !== "ArrowRight" && ev.key !== "ArrowLeft") return;
    const els = items();
    const idx = els.indexOf(document.activeElement as HTMLElement);
    if (idx === -1) return;
    ev.preventDefault();
    els[(idx + (ev.key === "ArrowRight" ? 1 : els.length - 1)) % els.length]?.focus();
  };

  return (
    <div className="relative">
      <div
        ref={barRef}
        role="toolbar"
        aria-label="Formatting"
        onKeyDown={onKeyDown}
        onFocus={onFocus}
        className="sticky top-0 z-10 flex flex-wrap items-center gap-0.5 rounded-t-lg border-b border-zinc-200 bg-white px-1.5 py-1 dark:border-zinc-700 dark:bg-zinc-900"
      >
        <Btn
          label="Undo"
          shortcut="Ctrl+Z"
          disabled={!s.canUndo}
          onClick={() => chain().undo().run()}
        >
          <Undo2 className={ic} />
        </Btn>
        <Btn
          label="Redo"
          shortcut="Ctrl+Shift+Z"
          disabled={!s.canRedo}
          onClick={() => chain().redo().run()}
        >
          <Redo2 className={ic} />
        </Btn>
        <Sep />
        {mode === "rich" && (
          <>
            <select
              aria-label="Text style"
              value={s.block}
              onChange={(e) => {
                const v = e.target.value as BlockStyle;
                if (v === "p") chain().setParagraph().run();
                else
                  chain()
                    .setHeading({ level: Number(v[1]) as 2 | 3 | 4 })
                    .run();
              }}
              className="h-7 cursor-pointer rounded border border-zinc-200 bg-transparent px-1.5 text-xs text-zinc-700 dark:border-zinc-700 dark:text-zinc-200"
            >
              <option value="p">Paragraph</option>
              <option value="h2">Heading 2</option>
              <option value="h3">Heading 3</option>
              <option value="h4">Heading 4</option>
            </select>
            <Sep />
          </>
        )}
        <Btn
          label="Bold"
          shortcut="Ctrl+B"
          active={s.bold}
          onClick={() => chain().toggleBold().run()}
        >
          <Bold className={ic} />
        </Btn>
        <Btn
          label="Italic"
          shortcut="Ctrl+I"
          active={s.italic}
          onClick={() => chain().toggleItalic().run()}
        >
          <Italic className={ic} />
        </Btn>
        <Btn
          label="Underline"
          shortcut="Ctrl+U"
          active={s.underline}
          onClick={() => chain().toggleUnderline().run()}
        >
          <Underline className={ic} />
        </Btn>
        <Btn
          label="Strikethrough"
          shortcut="Ctrl+Shift+S"
          active={s.strike}
          onClick={() => chain().toggleStrike().run()}
        >
          <Strikethrough className={ic} />
        </Btn>
        {mode === "rich" && (
          <>
            <Sep />
            <Btn
              label="Bullet list"
              shortcut="Ctrl+Shift+8"
              active={s.bullet}
              onClick={() => chain().toggleBulletList().run()}
            >
              <List className={ic} />
            </Btn>
            <Btn
              label="Numbered list"
              shortcut="Ctrl+Shift+7"
              active={s.ordered}
              onClick={() => chain().toggleOrderedList().run()}
            >
              <ListOrdered className={ic} />
            </Btn>
            <Btn
              label="Quote"
              shortcut="Ctrl+Shift+B"
              active={s.quote}
              onClick={() => chain().toggleBlockquote().run()}
            >
              <Quote className={ic} />
            </Btn>
            <Btn label="Divider" onClick={() => chain().setHorizontalRule().run()}>
              <Minus className={ic} />
            </Btn>
          </>
        )}
        <Sep />
        <Btn label="Link" shortcut="Ctrl+K" active={s.link} onClick={() => setLinkOpen(true)}>
          <Link2 className={ic} />
        </Btn>
        <Btn
          label="Remove link"
          disabled={!s.link}
          onClick={() => chain().extendMarkRange("link").unsetLink().run()}
        >
          <Unlink className={ic} />
        </Btn>
        <Btn label="Clear formatting" onClick={() => chain().unsetAllMarks().clearNodes().run()}>
          <RemoveFormatting className={ic} />
        </Btn>
      </div>
      {/* Rendered outside the role="toolbar" element on purpose: it must not
          be part of the toolbar's roving-tabindex item list, and its own
          arrow-key/Tab behavior must not be hijacked by the toolbar's
          keydown handler. */}
      {linkOpen && <LinkPopover editor={editor} onClose={() => setLinkOpen(false)} />}
    </div>
  );
}
