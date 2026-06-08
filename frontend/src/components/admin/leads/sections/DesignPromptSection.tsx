"use client";

import { useEffect, useRef, useState } from "react";
import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import DOMPurify from "isomorphic-dompurify";
import { Check, ChevronDown, Copy } from "lucide-react";
import type { Lead } from "../types";
import { EditableSectionShell } from "./EditableSectionShell";
import { useLeadPatch } from "../hooks/useLeadPatch";
import { DesignPromptEditor } from "./DesignPromptEditor";

interface Props {
  lead: Lead;
  onPatched: (lead: Lead) => void;
}

/** Collapsed preview height for a long design prompt before "Show full prompt". */
const COLLAPSED_PREVIEW_PX = 150;

/** Convert the stored prompt HTML to readable plain text (block elements keep
 *  their line breaks) so the clipboard copy is paste-ready, not raw markup. */
function htmlToPlainText(html: string): string {
  const el = document.createElement("div");
  el.innerHTML = html;
  el.style.position = "fixed";
  el.style.left = "-99999px";
  el.style.whiteSpace = "pre-wrap";
  document.body.appendChild(el);
  const text = el.innerText;
  document.body.removeChild(el);
  return text.trim();
}

/** One-click copy of the full design prompt, with a brief check-mark confirm. */
function CopyPromptButton({ html }: { html: string }) {
  const [copied, setCopied] = useState(false);

  async function copy() {
    try {
      await navigator.clipboard.writeText(htmlToPlainText(html));
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      // Clipboard unavailable (e.g. insecure context) — fail silently.
    }
  }

  return (
    <button
      type="button"
      aria-label={copied ? "Design prompt copied" : "Copy design prompt"}
      onClick={copy}
      className="opacity-0 group-hover:opacity-100 focus-visible:opacity-100 transition-opacity inline-flex items-center justify-center h-6 w-6 rounded-md text-zinc-500 hover:text-zinc-900 dark:hover:text-zinc-100 hover:bg-zinc-100 dark:hover:bg-zinc-800 cursor-pointer"
    >
      <AnimatePresence mode="wait" initial={false}>
        <motion.span
          key={copied ? "check" : "copy"}
          initial={{ scale: 0.6, opacity: 0 }}
          animate={{ scale: 1, opacity: 1 }}
          exit={{ scale: 0.6, opacity: 0 }}
          transition={{ duration: 0.15, ease: "easeOut" }}
          className="inline-flex"
        >
          {copied ? (
            <Check className="h-3.5 w-3.5 text-emerald-600 dark:text-emerald-400" />
          ) : (
            <Copy className="h-3.5 w-3.5" />
          )}
        </motion.span>
      </AnimatePresence>
    </button>
  );
}

/** Read view: shows a clamped preview of the design prompt and expands to the
 *  full brief on demand, so the drawer doesn't become one long scroll. Heights
 *  animate between two pixel values (never to/from "auto") so both expand and
 *  collapse glide smoothly. */
function DesignPromptPreview({ html }: { html: string }) {
  const prefersReduced = useReducedMotion();
  const contentRef = useRef<HTMLDivElement>(null);
  const [fullHeight, setFullHeight] = useState(0);
  const [overflowing, setOverflowing] = useState(false);
  const [measured, setMeasured] = useState(false);
  const [expanded, setExpanded] = useState(false);

  useEffect(() => {
    const el = contentRef.current;
    if (!el) return;
    const h = el.scrollHeight;
    setFullHeight(h);
    setOverflowing(h > COLLAPSED_PREVIEW_PX + 8);
    setExpanded(false);
    setMeasured(true);
  }, [html]);

  function toggle() {
    // Re-measure right before expanding in case the content reflowed.
    if (!expanded && contentRef.current) setFullHeight(contentRef.current.scrollHeight);
    setExpanded((v) => !v);
  }

  const showToggle = measured && overflowing;
  const collapsed = showToggle && !expanded;

  // Numeric targets only (clamp until measured) → smooth in both directions.
  let heightTarget: number | "auto";
  if (!measured) heightTarget = COLLAPSED_PREVIEW_PX;
  else if (!overflowing) heightTarget = "auto";
  else heightTarget = expanded ? fullHeight : COLLAPSED_PREVIEW_PX;

  return (
    <div className="rounded-lg border border-zinc-200 dark:border-zinc-800 bg-zinc-50 dark:bg-zinc-900 p-3">
      <div className="relative">
        <motion.div
          initial={false}
          animate={{ height: heightTarget }}
          transition={{ duration: prefersReduced ? 0 : 0.3, ease: "easeInOut" }}
          className="overflow-hidden"
        >
          <div
            ref={contentRef}
            className="prose prose-sm prose-zinc dark:prose-invert max-w-none"
            // SEC-018/SEC-043: design_prompt is model-generated HTML derived from
            // untrusted scraped lead data, and the agent writeback bypasses the
            // backend bleach sanitizer. Sanitize on render so any write path is
            // safe in the admin dashboard (strips <script>, event handlers, etc.).
            dangerouslySetInnerHTML={{ __html: DOMPurify.sanitize(html) }}
          />
        </motion.div>
        <AnimatePresence>
          {collapsed && (
            <motion.div
              key="fade"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: prefersReduced ? 0 : 0.2 }}
              className="pointer-events-none absolute inset-x-0 bottom-0 h-14 bg-gradient-to-t from-zinc-50 dark:from-zinc-900 to-transparent"
            />
          )}
        </AnimatePresence>
      </div>
      {showToggle && (
        <button
          type="button"
          onClick={toggle}
          aria-expanded={expanded}
          className="mt-2 inline-flex items-center gap-1 text-xs font-medium text-blue-600 dark:text-blue-400 hover:underline cursor-pointer"
        >
          {expanded ? "Show less" : "Show full prompt"}
          <motion.span
            animate={{ rotate: expanded ? 180 : 0 }}
            transition={{ duration: prefersReduced ? 0 : 0.2 }}
            className="inline-flex"
          >
            <ChevronDown className="h-3.5 w-3.5" />
          </motion.span>
        </button>
      )}
    </div>
  );
}

export function DesignPromptSection({ lead, onPatched }: Props) {
  const { patch, saving, error, clearError } = useLeadPatch(lead.id, onPatched);

  const [html, setHtml] = useState(lead.design_prompt ?? "");

  useEffect(() => {
    setHtml(lead.design_prompt ?? "");
    clearError();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [lead.id, lead.design_prompt]);

  async function handleSave() {
    const next = html.trim() === "" ? null : html;
    if (next === (lead.design_prompt ?? null)) return;
    await patch({ design_prompt: next });
  }

  function handleCancel() {
    setHtml(lead.design_prompt ?? "");
    clearError();
  }

  const readView = lead.design_prompt ? (
    <DesignPromptPreview html={lead.design_prompt} />
  ) : (
    <div className="rounded-lg border border-zinc-200 dark:border-zinc-800 bg-zinc-50 dark:bg-zinc-900 p-3">
      <p className="text-xs text-zinc-500 dark:text-zinc-400 italic">Not set yet.</p>
    </div>
  );

  const editView = (
    <div className="rounded-lg border border-zinc-200 dark:border-zinc-800 bg-zinc-50 dark:bg-zinc-900 p-3">
      <DesignPromptEditor value={html} onChange={setHtml} />
    </div>
  );

  return (
    <EditableSectionShell
      id="design_prompt"
      title="Design prompt"
      readView={readView}
      editView={editView}
      onSave={handleSave}
      onCancel={handleCancel}
      saving={saving}
      error={error}
      canSave={true}
      headerExtra={lead.design_prompt ? <CopyPromptButton html={lead.design_prompt} /> : undefined}
    />
  );
}
