"use client";

import { createElement, Fragment } from "react";
import { m, type Transition } from "motion/react";
import type { CSSProperties, ElementType } from "react";
import { REVEAL_EASE, directionOffset, type RevealDirection } from "./Reveal";

export interface TextRevealProps {
  /** The full string to reveal. */
  text: string;
  /** Reveal one word at a time or one character at a time. Default "word". */
  by?: "word" | "char";
  /** Direction each token travels FROM. Default "up" (drops in from above). */
  direction?: RevealDirection;
  /** Seconds before the first token starts. Default 0. */
  delay?: number;
  /** Seconds between each token — this is the "typing" rhythm. Default 0.06.
   *  Increase it for a slower, more deliberate type-on feel. */
  stagger?: number;
  /** Per-token animation duration (how fast each token settles). Default 0.5. */
  duration?: number;
  /** Travel distance — number (px) or CSS length ("0.5em"). Default "0.4em". */
  distance?: number | string;
  /** Easing curve. Default REVEAL_EASE (ease-out-expo). */
  ease?: Transition["ease"];
  className?: string;
  style?: CSSProperties;
  /** Container tag — use "h1"/"h2"/"p" to render the real text element. Default "span". */
  as?: ElementType;
}

/**
 * TextReveal — reveals text token-by-token for a typing-style cascade.
 * The container carries an aria-label so screen readers announce the whole
 * string once (the animated tokens are aria-hidden).
 *
 * Reduced motion: rely on an ancestor `<MotionConfig reducedMotion="user">`.
 *
 * @example
 * <TextReveal as="h1" className="text-6xl font-bold"
 *   text="AI-built. Human-perfected."
 *   delay={0.9} stagger={0.18} duration={0.6} distance="0.6em" />
 */
export function TextReveal({
  text,
  by = "word",
  direction = "up",
  delay = 0,
  stagger = 0.06,
  duration = 0.5,
  distance = "0.4em",
  ease = REVEAL_EASE,
  className,
  style,
  as,
}: TextRevealProps) {
  const Tag: ElementType = as ?? "span";
  const tokens = by === "char" ? Array.from(text) : text.split(" ");
  const hidden = { opacity: 0, ...directionOffset(direction, distance) };

  const children = tokens.map((token, i) => (
    <Fragment key={i}>
      <m.span
        aria-hidden="true"
        className="inline-block whitespace-pre-wrap"
        initial={hidden}
        animate={{ opacity: 1, x: 0, y: 0 }}
        transition={{ duration, ease, delay: delay + i * stagger }}
      >
        {token}
      </m.span>
      {by === "word" && i < tokens.length - 1 ? " " : ""}
    </Fragment>
  ));

  return createElement(Tag, { className, style, "aria-label": text }, children);
}
