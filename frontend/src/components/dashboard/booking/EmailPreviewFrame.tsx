"use client";

import { useEffect, useRef, useState } from "react";
import { useReducedMotion } from "motion/react";
import { previewEmail } from "./api";
import type { EmailDraft } from "./api";

interface Props {
  slug: string;
  caseKey: string;
  draft: EmailDraft;
}

type PreviewState =
  | { status: "idle" }
  | { status: "loading"; html: string | null }
  | { status: "ready"; html: string }
  | { status: "error" };

/**
 * Server-rendered email preview in a sandboxed iframe.
 * Debounces draft + caseKey changes ~300 ms, cancels stale requests,
 * cross-fades between previews (reduced-motion respected).
 */
export function EmailPreviewFrame({ slug, caseKey, draft }: Props) {
  const [state, setState] = useState<PreviewState>({ status: "idle" });
  const reqIdRef = useRef(0);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const reduce = useReducedMotion();

  useEffect(() => {
    // Clear any pending debounce
    if (timerRef.current !== null) {
      clearTimeout(timerRef.current);
    }

    timerRef.current = setTimeout(async () => {
      const reqId = ++reqIdRef.current;

      setState((prev) => ({
        status: "loading",
        html: prev.status === "ready" ? prev.html : null,
      }));

      try {
        const result = await previewEmail(slug, caseKey, draft);
        // Discard if a newer request has already been issued
        if (reqId !== reqIdRef.current) return;
        setState({ status: "ready", html: result.html });
      } catch {
        if (reqId !== reqIdRef.current) return;
        setState({ status: "error" });
      }
    }, 300);

    return () => {
      if (timerRef.current !== null) {
        clearTimeout(timerRef.current);
      }
    };
    // Stringify draft to detect deep changes without adding it as object ref
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [slug, caseKey, JSON.stringify(draft)]);

  // Shimmer skeleton shown only on first-ever load (no prior html)
  if (state.status === "idle" || (state.status === "loading" && state.html === null)) {
    return (
      <div className="relative h-full min-h-[480px] w-full rounded-lg border border-zinc-200 bg-zinc-50 dark:border-zinc-800 dark:bg-zinc-900/60">
        <div className="absolute inset-0 animate-pulse rounded-lg bg-zinc-200 dark:bg-zinc-800" />
        <p className="absolute inset-0 flex items-center justify-center text-xs text-zinc-400 dark:text-zinc-500">
          Loading preview…
        </p>
      </div>
    );
  }

  if (state.status === "error") {
    return (
      <div className="flex h-full min-h-[480px] w-full items-center justify-center rounded-lg border border-zinc-200 bg-zinc-50 dark:border-zinc-800 dark:bg-zinc-900/60">
        <p className="text-sm text-zinc-400 dark:text-zinc-500">Preview unavailable.</p>
      </div>
    );
  }

  // Both "ready" and "loading" (with prior html) show the iframe
  const html = state.status === "ready" ? state.html : (state as { html: string }).html;
  const isUpdating = state.status === "loading";

  return (
    <div className="relative h-full min-h-[480px] w-full">
      <iframe
        sandbox=""
        srcDoc={html}
        title="Email preview"
        className="h-full w-full rounded-lg border border-zinc-200 bg-white dark:border-zinc-800"
        style={{ minHeight: 480 }}
      />
      {isUpdating && (
        <div
          className="pointer-events-none absolute inset-0 rounded-lg bg-white/40 dark:bg-zinc-900/40"
          style={{
            transition: reduce ? "none" : "opacity 150ms ease",
          }}
          aria-hidden="true"
        />
      )}
    </div>
  );
}
