"use client";

import { createElement, useEffect, useMemo, useRef, useState } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import type { LucideIcon } from "lucide-react";
import { dashboardInputCn } from "@/lib/styles";

const MAX_RESULTS = 60;

/** Searchable grid over the Lucide set. Loaded lazily by IconField, and the
 *  icon map is imported on mount, so the dashboard bundle never carries it. */
export function IconPicker({ onPick }: { onPick: (svg: string, name: string) => void }) {
  const [icons, setIcons] = useState<Record<string, LucideIcon> | null>(null);
  const [failed, setFailed] = useState(false);
  const [query, setQuery] = useState("");
  const searchRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    let live = true;
    import("lucide-react").then(
      (m) => live && setIcons(m.icons),
      () => live && setFailed(true)
    );
    return () => {
      live = false;
    };
  }, []);

  useEffect(() => {
    if (icons) searchRef.current?.focus();
  }, [icons]);

  const names = useMemo(() => (icons ? Object.keys(icons) : []), [icons]);
  const q = query.toLowerCase().replace(/[\s_-]+/g, "");
  const matches = q ? names.filter((n) => n.toLowerCase().includes(q)) : names;
  const shown = matches.slice(0, MAX_RESULTS);

  function pick(name: string) {
    if (!icons) return;
    const svg = renderToStaticMarkup(
      createElement(icons[name], { size: 24, strokeWidth: 2, color: "currentColor" })
    );
    onPick(svg, name);
  }

  if (failed) {
    return <p className="text-xs text-red-600 dark:text-red-400">Could not load the icons.</p>;
  }
  if (!icons) {
    return <p className="text-xs text-zinc-400 dark:text-zinc-500">Loading icons…</p>;
  }

  return (
    <div className="space-y-2">
      <input
        ref={searchRef}
        type="search"
        aria-label="Search icons"
        placeholder="Search icons, e.g. wrench"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        className={dashboardInputCn}
      />
      <div className="grid max-h-64 grid-cols-[repeat(auto-fill,minmax(2.5rem,1fr))] gap-1 overflow-y-auto">
        {shown.map((name) => {
          const Icon = icons[name];
          return (
            <button
              key={name}
              type="button"
              aria-label={name}
              title={name}
              onClick={() => pick(name)}
              className="flex h-10 items-center justify-center rounded-lg text-zinc-600 hover:bg-zinc-100 focus-visible:outline-2 focus-visible:outline-zinc-400 dark:text-zinc-300 dark:hover:bg-zinc-800 cursor-pointer transition-colors"
            >
              <Icon className="h-5 w-5" aria-hidden />
            </button>
          );
        })}
      </div>
      <p aria-live="polite" className="text-xs text-zinc-400 dark:text-zinc-500">
        {matches.length === 0
          ? "No icons match."
          : matches.length > MAX_RESULTS
            ? `Showing ${MAX_RESULTS} of ${matches.length} icons. Type to narrow the search.`
            : `${matches.length} ${matches.length === 1 ? "icon" : "icons"}`}
      </p>
    </div>
  );
}
