"use client";

import { AnimatePresence, motion } from "framer-motion";

type Phase = "idle" | "sending" | "sent";

interface SubmitOverlayProps {
  phase: Phase;
  messages?: {
    sending?: string;
    sent?: string;
  };
}

const DEFAULT_MESSAGES = {
  sending: "Sending request…",
  sent: "Request received",
} as const;

/**
 * Full-bleed overlay for form submission feedback. Designed to be
 * dropped inside a `position:relative` parent (`<div className="relative
 * min-h-full">`). Covers the parent (i.e. the page content area
 * inside the dashboard's right pane — sidebar stays interactive).
 *
 * Phases:
 *   • `idle`    — nothing rendered.
 *   • `sending` — comet arc spinner (mirrors `LoadingScreen`),
 *                 white/zinc track, "Sending…" label.
 *   • `sent`    — same arc but tinted emerald + checkmark sigil; label
 *                 fades in from below.
 *
 * Theme: matches the rest of the dashboard via `dark:` utilities.
 *   • Light → near-white scrim with dark text.
 *   • Dark  → near-black scrim with light text.
 */
export function SubmitOverlay({ phase, messages = {} }: SubmitOverlayProps) {
  const sendingLabel = messages.sending ?? DEFAULT_MESSAGES.sending;
  const sentLabel = messages.sent ?? DEFAULT_MESSAGES.sent;
  const visible = phase !== "idle";
  const isSent = phase === "sent";

  return (
    <AnimatePresence>
      {visible && (
        <motion.div
          key="submit-overlay"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.28, ease: [0.32, 0.72, 0, 1] }}
          className="absolute inset-0 z-40 flex flex-col items-center justify-center backdrop-blur-md bg-white/85 text-zinc-700 dark:bg-zinc-950/90 dark:text-zinc-200"
          style={{ gap: 22 }}
          role="status"
          aria-live="polite"
        >
          {/* Arc spinner — same conic-gradient comet as LoadingScreen,
              tinted emerald when sent. The track ring stays the
              theme-neutral hairline so the colour shift on the comet
              reads cleanly against it. */}
          <div className="relative" style={{ width: 64, height: 64 }}>
            <div
              className="absolute inset-0 rounded-full border border-zinc-300/60 dark:border-zinc-700/60"
              style={{ borderWidth: 1.5 }}
            />
            <motion.div
              className="absolute inset-0 rounded-full"
              animate={{ rotate: 360 }}
              transition={{ duration: 1.2, repeat: Infinity, ease: "linear" }}
              style={{
                background: isSent
                  ? "conic-gradient(from 0deg, transparent 0deg, transparent 190deg, rgba(16,185,129,0.06) 210deg, rgba(16,185,129,0.18) 240deg, rgba(16,185,129,0.45) 278deg, rgba(16,185,129,0.85) 322deg, #10b981 352deg, transparent 360deg)"
                  : "conic-gradient(from 0deg, transparent 0deg, transparent 190deg, rgba(120,120,120,0.08) 210deg, rgba(120,120,120,0.22) 240deg, rgba(120,120,120,0.5) 278deg, rgba(50,50,50,0.85) 322deg, currentColor 352deg, transparent 360deg)",
                WebkitMask:
                  "radial-gradient(farthest-side, transparent calc(100% - 1.5px), #000 calc(100% - 1.5px))",
                mask: "radial-gradient(farthest-side, transparent calc(100% - 1.5px), #000 calc(100% - 1.5px))",
                transition: "background 400ms ease",
              }}
            />
            {/* Centre check sigil — fades in only on `sent`. Slight
                scale pop so the eye notices the state change without
                a layout shift. */}
            <AnimatePresence>
              {isSent && (
                <motion.div
                  key="check"
                  initial={{ opacity: 0, scale: 0.6 }}
                  animate={{ opacity: 1, scale: 1 }}
                  exit={{ opacity: 0, scale: 0.6 }}
                  transition={{ duration: 0.32, ease: [0.16, 1, 0.3, 1] }}
                  className="absolute inset-0 flex items-center justify-center"
                >
                  <svg
                    className="h-6 w-6 text-emerald-500 dark:text-emerald-400"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth={2.5}
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  >
                    <path d="M20 6L9 17l-5-5" />
                  </svg>
                </motion.div>
              )}
            </AnimatePresence>
          </div>

          {/* Phase label — uses inner AnimatePresence with `phase` as
              key so the swap from "Sending…" to "Request received"
              fades cleanly without a flicker. */}
          <div className="relative h-5 w-72 text-center text-sm font-medium tracking-tight">
            <AnimatePresence mode="wait" initial={false}>
              <motion.p
                key={phase}
                initial={{ opacity: 0, y: 6 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -6 }}
                transition={{ duration: 0.2, ease: "easeOut" }}
                className={
                  isSent
                    ? "text-emerald-700 dark:text-emerald-300"
                    : "text-zinc-700 dark:text-zinc-200"
                }
              >
                {isSent ? sentLabel : sendingLabel}
              </motion.p>
            </AnimatePresence>
          </div>

          {/* Hairline progress shimmer — same metric as LoadingScreen,
              but emerald when sent. Visually anchors the spinner. */}
          <div
            className="relative overflow-hidden rounded-full bg-zinc-200/70 dark:bg-zinc-800/70"
            style={{ width: 140, height: 1 }}
          >
            <motion.div
              className="absolute inset-y-0 left-0"
              animate={{ x: ["-100%", "280%"] }}
              transition={{
                duration: 1.9,
                repeat: Infinity,
                ease: "easeInOut",
                repeatDelay: 0.3,
              }}
              style={{
                width: "42%",
                background: isSent
                  ? "linear-gradient(to right, transparent, rgba(16,185,129,0.5), transparent)"
                  : "linear-gradient(to right, transparent, rgba(115,115,115,0.55), transparent)",
                transition: "background 400ms ease",
              }}
            />
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
