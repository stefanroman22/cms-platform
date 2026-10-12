"use client";

import {
  useEffect,
  useMemo,
  useRef,
  useState,
  type FocusEvent,
  type KeyboardEvent,
  type ReactNode,
  type Ref,
  type RefObject,
} from "react";
import { useEditorState, type Editor } from "@tiptap/react";
import {
  Bold,
  Italic,
  Link2,
  List,
  ListOrdered,
  Minus,
  Palette,
  Quote,
  Redo2,
  RemoveFormatting,
  Strikethrough,
  Underline,
  Undo2,
  Unlink,
} from "lucide-react";
import { fontStack, parseStyle, type ThemeColor } from "@/lib/cms-rich-text";
import { LinkPopover } from "./LinkPopover";
import { AnimatedSelect } from "../AnimatedSelect";
import { useProjectTheme } from "../theme/ProjectThemeContext";

const BLOCK_OPTIONS = [
  { value: "p", label: "Paragraph" },
  { value: "h2", label: "Heading 2" },
  { value: "h3", label: "Heading 3" },
  { value: "h4", label: "Heading 4" },
] as const;
const SIZE_OPTIONS = [
  { value: "", label: "Default" },
  { value: "0.75em", label: "75%" },
  { value: "0.9em", label: "90%" },
  { value: "1.1em", label: "110%" },
  { value: "1.25em", label: "125%" },
  { value: "1.5em", label: "150%" },
  { value: "2em", label: "200%" },
  { value: "2.5em", label: "250%" },
  { value: "3em", label: "300%" },
] as const;
import type { RichMode } from "./serialize";

/** The selection's colour/font/size marks in the kit's canonical form (ADR-0011). */
function markStyle(e: Editor) {
  const a = e.getAttributes("textStyle");
  return parseStyle(
    `color:${a.color ?? ""};font-family:${a.fontFamily ?? ""};font-size:${a.fontSize ?? ""}`
  );
}

type BlockStyle = "p" | "h2" | "h3" | "h4";

function Btn({
  label,
  shortcut,
  active,
  disabled,
  popup,
  expanded,
  ref,
  onClick,
  children,
}: {
  label: string;
  shortcut?: string;
  active?: boolean;
  disabled?: boolean;
  popup?: "dialog";
  expanded?: boolean;
  ref?: Ref<HTMLButtonElement>;
  onClick: () => void;
  children: ReactNode;
}) {
  return (
    <button
      ref={ref}
      type="button"
      aria-label={label}
      title={shortcut ? `${label} (${shortcut})` : label}
      aria-pressed={active === undefined ? undefined : active}
      aria-haspopup={popup}
      aria-expanded={expanded}
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

function ColourPopover({
  editor,
  colors,
  current,
  triggerRef,
  onClose,
}: {
  editor: Editor;
  colors: ThemeColor[];
  current?: string;
  /** The toolbar button that toggles this popover; its mousedown is not "outside". */
  triggerRef: RefObject<HTMLButtonElement | null>;
  onClose: () => void;
}) {
  const boxRef = useRef<HTMLDivElement>(null);
  // Same as LinkPopover: the Toolbar passes a fresh `onClose` every render.
  const onCloseRef = useRef(onClose);
  useEffect(() => {
    onCloseRef.current = onClose;
  });

  useEffect(() => {
    boxRef.current?.querySelector<HTMLElement>("button, input")?.focus();
  }, []);

  useEffect(() => {
    const onDown = (e: MouseEvent) => {
      const target = e.target as Node;
      if (boxRef.current?.contains(target) || triggerRef.current?.contains(target)) return;
      onCloseRef.current();
    };
    document.addEventListener("mousedown", onDown);
    return () => document.removeEventListener("mousedown", onDown);
  }, [triggerRef]);

  function pick(color: string | null) {
    if (color) editor.chain().focus().setColor(color).run();
    else editor.chain().focus().unsetColor().run();
    onClose();
  }

  return (
    <div
      ref={boxRef}
      role="dialog"
      aria-label="Text colour"
      className="absolute left-1.5 top-full z-20 mt-1 w-56 rounded-lg border border-zinc-200 bg-white p-3 shadow-lg dark:border-zinc-700 dark:bg-zinc-900"
      onKeyDown={(e) => {
        if (e.key === "Escape") {
          e.preventDefault();
          onClose();
          editor.commands.focus();
        }
      }}
    >
      {colors.length > 0 && (
        <div className="mb-3 grid grid-cols-6 gap-1.5">
          {colors.map((c) => {
            // `current` is canonical (#rrggbb, lowercase); compare like with like.
            const pressed = !!current && parseStyle(`color:${c.value}`).color === current;
            return (
              <button
                key={`${c.name}${c.value}`}
                type="button"
                aria-label={c.name}
                title={`${c.name} (${c.value})`}
                aria-pressed={pressed}
                onClick={() => pick(c.value)}
                style={{ backgroundColor: c.value }}
                className={`h-6 w-6 cursor-pointer rounded-full border border-zinc-200 dark:border-zinc-700 ${
                  pressed
                    ? "ring-2 ring-zinc-900 ring-offset-1 dark:ring-zinc-100 dark:ring-offset-zinc-900"
                    : ""
                }`}
              />
            );
          })}
        </div>
      )}
      <div className="flex items-center justify-between gap-2">
        <button
          type="button"
          onClick={() => pick(null)}
          className="cursor-pointer rounded-md px-2 py-1 text-xs font-medium text-zinc-600 hover:bg-zinc-100 dark:text-zinc-300 dark:hover:bg-zinc-800"
        >
          Default
        </button>
        <label className="flex cursor-pointer items-center gap-1.5 text-xs text-zinc-600 dark:text-zinc-300">
          Custom
          {/* No focus(): moving focus to the editor would close the native picker mid-drag. */}
          <input
            type="color"
            aria-label="Custom colour"
            value={current ?? "#000000"}
            onChange={(e) => editor.chain().setColor(e.target.value).run()}
            className="h-6 w-8 cursor-pointer rounded border border-zinc-200 bg-transparent dark:border-zinc-700"
          />
        </label>
      </div>
    </div>
  );
}

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
  const [colourOpen, setColourOpen] = useState(false);
  const colourRef = useRef<HTMLButtonElement>(null);
  // Font/size/colour controls only for a project with a theme (ADR-0011).
  const { theme } = useProjectTheme();
  const fontOptions = useMemo(
    () => [
      { value: "", label: "Default" },
      ...(theme?.fonts ?? []).map((f) => ({
        value: f.family,
        label: f.family,
        style: { fontFamily: fontStack(f.family) },
      })),
    ],
    [theme]
  );
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
            ...markStyle(e),
          }
        : null,
  });

  const items = () =>
    Array.from(barRef.current?.querySelectorAll<HTMLElement>("button:not(:disabled)") ?? []);
  const disabledItems = () =>
    Array.from(barRef.current?.querySelectorAll<HTMLElement>("button:disabled") ?? []);

  // Real roving tabindex: exactly one control is in the page's Tab order at a
  // time (the last-focused one, or the first by default); Tab enters/leaves
  // the toolbar as a single stop, arrows move focus within it. Self-healing —
  // reapplied after every render — so a control that becomes disabled (e.g.
  // Undo when the history is empty) never leaves the toolbar with zero
  // tabbable controls.
  useEffect(() => {
    // A disabled control keeps the browser's native default tabIndex (0)
    // until something explicitly sets it — it's excluded from `items()`
    // below, so the roving loop never touches it while disabled. Force it to
    // -1 now, so that if it later becomes enabled (e.g. Undo once there's
    // history), it doesn't join `items()` still carrying that stale 0 and
    // get mistaken for "the" current stop ahead of whatever the user
    // actually last focused.
    disabledItems().forEach((el) => {
      el.tabIndex = -1;
    });
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
    // `sticky` (not `relative`) is the positioning context here: sticky is
    // itself a positioned element, so it still anchors the popover's
    // `absolute`, exactly like `relative` did — but unlike a plain `relative`
    // wrapper sized to the toolbar's own height, `sticky` needs room to move
    // within a taller ancestor to actually stick, and that ancestor is this
    // div's parent, the full (tall) editor container. Putting `sticky` on an
    // inner div whose own parent was only as tall as the toolbar (the
    // previous structure) gave it nowhere to travel, so it scrolled away
    // instead of staying pinned in a long field.
    <div className="sticky top-0 z-10 rounded-t-lg border-b border-zinc-200 bg-white dark:border-zinc-700 dark:bg-zinc-900">
      <div
        ref={barRef}
        role="toolbar"
        aria-label="Formatting"
        onKeyDown={onKeyDown}
        onFocus={onFocus}
        className="flex flex-wrap items-center gap-0.5 px-1.5 py-1"
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
            <AnimatedSelect
              ariaLabel="Text style"
              compact
              value={s.block}
              onChange={(v) => {
                if (v === "p") chain().setParagraph().run();
                else
                  chain()
                    .setHeading({ level: Number(v[1]) as 2 | 3 | 4 })
                    .run();
              }}
              options={BLOCK_OPTIONS}
            />
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
        {theme && (
          <>
            <Sep />
            <AnimatedSelect
              ariaLabel="Font"
              compact
              value={s.fontFamily ?? ""}
              onChange={(v) => {
                if (v) chain().setFontFamily(`'${v}'`).run();
                else chain().unsetFontFamily().run();
              }}
              options={fontOptions}
            />
            <AnimatedSelect
              ariaLabel="Size"
              compact
              value={s.fontSize ?? ""}
              onChange={(v) => {
                if (v) chain().setFontSize(v).run();
                else chain().unsetFontSize().run();
              }}
              options={SIZE_OPTIONS}
            />
            <Btn
              ref={colourRef}
              label="Colour"
              popup="dialog"
              expanded={colourOpen}
              onClick={() => setColourOpen((open) => !open)}
            >
              <span className="flex flex-col items-center gap-px">
                <Palette className="h-3 w-3" />
                <span
                  aria-hidden
                  className="h-0.5 w-3.5 rounded-full"
                  style={{ backgroundColor: s.color ?? "currentColor" }}
                />
              </span>
            </Btn>
          </>
        )}
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
      {theme && colourOpen && (
        <ColourPopover
          editor={editor}
          colors={theme.colors}
          current={s.color}
          triggerRef={colourRef}
          onClose={() => setColourOpen(false)}
        />
      )}
    </div>
  );
}
