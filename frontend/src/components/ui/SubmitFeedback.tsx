"use client";

import type { ReactNode } from "react";
import { AnimatePresence, m } from "motion/react";
import { cn } from "@/lib/utils";

const EXPO = [0.16, 1, 0.3, 1] as const;

export type SubmitStatus = "loading" | "success" | "error";

/** Gold comet spinner that morphs into a checkmark (or an X on error). Pure visual. */
function SpinnerCheck({ status, size = 56 }: { status: SubmitStatus; size?: number }) {
  return (
    <div className="relative" style={{ width: size, height: size }}>
      {/* Dim static track ring — constant backdrop behind both states. */}
      <svg
        viewBox="0 0 56 56"
        width={size}
        height={size}
        className="absolute inset-0 text-text-secondary"
        aria-hidden="true"
      >
        <circle
          cx="28"
          cy="28"
          r="25"
          fill="none"
          stroke="currentColor"
          strokeOpacity={0.12}
          strokeWidth={3}
        />
      </svg>

      <AnimatePresence mode="wait" initial={false}>
        {status === "loading" ? (
          <m.svg
            key="spinner"
            viewBox="0 0 56 56"
            width={size}
            height={size}
            className="absolute inset-0 animate-spin text-accent"
            style={{ animationDuration: "1.1s" }}
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.25, ease: EXPO }}
            aria-hidden="true"
          >
            <circle
              cx="28"
              cy="28"
              r="25"
              fill="none"
              stroke="currentColor"
              strokeOpacity={0.92}
              strokeWidth={3}
              strokeLinecap="round"
              strokeDasharray="47 110"
            />
          </m.svg>
        ) : (
          <m.svg
            key="done"
            viewBox="0 0 56 56"
            width={size}
            height={size}
            className={cn("absolute inset-0", status === "error" ? "text-red-400" : "text-accent")}
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ duration: 0.3, ease: EXPO }}
            aria-hidden="true"
          >
            {/* Arc settles into a full ring. */}
            <m.circle
              cx="28"
              cy="28"
              r="25"
              fill="none"
              stroke="currentColor"
              strokeOpacity={0.92}
              strokeWidth={3}
              strokeLinecap="round"
              initial={{ pathLength: 0.3 }}
              animate={{ pathLength: 1 }}
              transition={{ duration: 0.45, ease: EXPO }}
            />
            {status === "success" ? (
              <m.path
                d="M16.5 29 L24.5 37 L40 20"
                fill="none"
                stroke="currentColor"
                strokeWidth={3.2}
                strokeLinecap="round"
                strokeLinejoin="round"
                initial={{ pathLength: 0 }}
                animate={{ pathLength: 1 }}
                transition={{ duration: 0.4, ease: EXPO, delay: 0.35 }}
              />
            ) : (
              <m.path
                d="M20 20 L36 36 M36 20 L20 36"
                fill="none"
                stroke="currentColor"
                strokeWidth={3.2}
                strokeLinecap="round"
                initial={{ pathLength: 0 }}
                animate={{ pathLength: 1 }}
                transition={{ duration: 0.4, ease: EXPO, delay: 0.25 }}
              />
            )}
          </m.svg>
        )}
      </AnimatePresence>
    </div>
  );
}

export interface SubmitFeedbackProps {
  status: SubmitStatus;
  loadingText?: string;
  successText?: string;
  errorText?: ReactNode;
  className?: string;
}

/**
 * Reusable submit confirmation: a gold spinner fades in with a line of text
 * below it; on success the spinner morphs into a checkmark and the text
 * smoothly recolours + changes content. Drive it with the `status` prop —
 * the parent owns the async work. Use inside an ancestor <LazyMotion>.
 */
export function SubmitFeedback({
  status,
  loadingText = "Sending your message…",
  successText = "Message sent — talk soon!",
  errorText = "Something went wrong. Please try again.",
  className,
}: SubmitFeedbackProps) {
  const text: ReactNode =
    status === "loading" ? loadingText : status === "success" ? successText : errorText;
  const tone =
    status === "success"
      ? "text-accent"
      : status === "error"
        ? "text-red-400"
        : "text-text-secondary";

  return (
    <m.div
      role="status"
      aria-live="polite"
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.45, ease: EXPO }}
      className={cn("flex flex-col items-center py-12 text-center", className)}
    >
      <SpinnerCheck status={status} />
      <div className="mt-5 min-h-6">
        <AnimatePresence mode="wait" initial={false}>
          <m.p
            key={status}
            initial={{ opacity: 0, y: 6 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -6 }}
            transition={{ duration: 0.35, ease: EXPO }}
            className={cn("text-sm font-medium leading-relaxed", tone)}
          >
            {text}
          </m.p>
        </AnimatePresence>
      </div>
    </m.div>
  );
}
