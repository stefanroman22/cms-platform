"use client";

import { useId, useMemo, useRef, useState } from "react";
import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import { X } from "lucide-react";
import { searchLanguages } from "@/lib/languages";

interface Props {
  value: string[];
  onChange: (next: string[]) => void;
}

/**
 * Searchable add/remove multi-select for language names. Selected languages
 * render as removable chips; typing filters the ISO list; click or Enter adds
 * the highlighted match; Backspace on an empty input removes the last chip.
 */
export function LanguageMultiSelect({ value, onChange }: Props) {
  const prefersReduced = useReducedMotion();
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState(false);
  const [highlight, setHighlight] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);
  const listboxId = useId();
  const optionId = (i: number) => `${listboxId}-opt-${i}`;

  const matches = useMemo(() => searchLanguages(query, value), [query, value]);
  const listOpen = open && matches.length > 0;

  function add(name: string) {
    if (!value.includes(name)) onChange([...value, name]);
    setQuery("");
    setHighlight(0);
    inputRef.current?.focus();
  }

  function remove(name: string) {
    onChange(value.filter((l) => l !== name));
    inputRef.current?.focus();
  }

  function onKeyDown(e: React.KeyboardEvent<HTMLInputElement>) {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setOpen(true);
      setHighlight((h) => Math.min(h + 1, Math.max(matches.length - 1, 0)));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setHighlight((h) => Math.max(h - 1, 0));
    } else if (e.key === "Enter") {
      e.preventDefault();
      const pick = matches[highlight];
      if (pick) add(pick.name);
    } else if (e.key === "Escape") {
      setOpen(false);
    } else if (e.key === "Backspace" && query === "" && value.length > 0) {
      remove(value[value.length - 1]);
    }
  }

  return (
    <div className="rounded-lg border border-zinc-200 dark:border-zinc-800 bg-zinc-50 dark:bg-zinc-900 p-3">
      {value.length > 0 && (
        <div className="mb-2 flex flex-wrap gap-1.5">
          {value.map((name) => (
            <span
              key={name}
              className="inline-flex items-center gap-1 rounded-full bg-zinc-200 dark:bg-zinc-800 pl-2.5 pr-1 py-0.5 text-xs text-zinc-800 dark:text-zinc-200"
            >
              {name}
              <button
                type="button"
                aria-label={`Remove ${name}`}
                onClick={() => remove(name)}
                className="inline-flex items-center justify-center h-4 w-4 rounded-full text-zinc-500 hover:text-zinc-900 dark:hover:text-zinc-100 hover:bg-zinc-300 dark:hover:bg-zinc-700 cursor-pointer transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-zinc-400 dark:focus-visible:ring-zinc-500"
              >
                <X className="h-3 w-3" />
              </button>
            </span>
          ))}
        </div>
      )}

      <div>
        <input
          ref={inputRef}
          type="text"
          role="combobox"
          aria-label="Search languages"
          aria-expanded={listOpen}
          aria-controls={listboxId}
          aria-autocomplete="list"
          aria-activedescendant={listOpen ? optionId(highlight) : undefined}
          autoComplete="off"
          value={query}
          placeholder="Search languages…"
          onChange={(e) => {
            setQuery(e.target.value);
            setOpen(true);
            setHighlight(0);
          }}
          onFocus={() => setOpen(true)}
          onBlur={() => setTimeout(() => setOpen(false), 120)}
          onKeyDown={onKeyDown}
          className="w-full rounded-md border border-zinc-200 dark:border-zinc-700 bg-white dark:bg-zinc-900 px-2.5 py-1.5 text-sm text-zinc-900 dark:text-zinc-100 placeholder:text-zinc-400 dark:placeholder:text-zinc-500 focus:outline-none focus:ring-2 focus:ring-zinc-400 dark:focus:ring-zinc-600"
        />

        <AnimatePresence>
          {listOpen && (
            <motion.ul
              id={listboxId}
              role="listbox"
              initial={{ opacity: 0, y: prefersReduced ? 0 : -4 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: prefersReduced ? 0 : -4 }}
              transition={{ duration: prefersReduced ? 0 : 0.16, ease: "easeOut" }}
              // Inline (not absolute): the section sits inside EditableSectionShell's
              // overflow-hidden container, which would clip an absolute dropdown. Rendering
              // it in normal flow lets it push content down and scroll within the drawer.
              className="mt-1 max-h-52 w-full overflow-y-auto rounded-md border border-zinc-200 bg-white shadow-lg ring-1 ring-black/5 dark:border-zinc-600 dark:bg-zinc-800 dark:ring-white/10"
            >
              {matches.map((lang, i) => (
                <li key={lang.code}>
                  <button
                    type="button"
                    id={optionId(i)}
                    role="option"
                    aria-selected={i === highlight}
                    // onMouseDown (not onClick) fires before input blur closes the list.
                    onMouseDown={(e) => {
                      e.preventDefault();
                      add(lang.name);
                    }}
                    onMouseEnter={() => setHighlight(i)}
                    className={`flex w-full items-center justify-between gap-2 px-2.5 py-2 text-left text-sm cursor-pointer transition-colors ${
                      i === highlight
                        ? "bg-zinc-100 dark:bg-zinc-700 text-zinc-900 dark:text-zinc-50"
                        : "text-zinc-700 dark:text-zinc-200"
                    }`}
                  >
                    <span>{lang.name}</span>
                    <span className="text-[10px] uppercase tracking-wider text-zinc-400 dark:text-zinc-400">
                      {lang.code}
                    </span>
                  </button>
                </li>
              ))}
            </motion.ul>
          )}
        </AnimatePresence>
      </div>

      <p className="mt-1.5 text-[11px] text-zinc-400 dark:text-zinc-500">
        Type to search · <kbd className="font-sans">↑</kbd> <kbd className="font-sans">↓</kbd> to
        navigate · <kbd className="font-sans">Enter</kbd> to add ·{" "}
        <kbd className="font-sans">⌫</kbd> removes the last
      </p>
    </div>
  );
}
