"use client";

import { m, type Transition } from "motion/react";
import type { CSSProperties, ReactNode } from "react";

export type RevealDirection = "up" | "down" | "left" | "right" | "none";

/** Shared easing token so every reveal across the site feels identical. */
export const REVEAL_EASE: Transition["ease"] = [0.16, 1, 0.3, 1];

function negate(distance: number | string) {
  return typeof distance === "number" ? -distance : `-${distance}`;
}

/** Hidden-state offset for a direction. "up" enters from above, etc. */
export function directionOffset(direction: RevealDirection, distance: number | string) {
  switch (direction) {
    case "up":
      return { y: negate(distance) };
    case "down":
      return { y: distance };
    case "left":
      return { x: negate(distance) };
    case "right":
      return { x: distance };
    default:
      return {};
  }
}

export interface RevealProps {
  children: ReactNode;
  /** Direction the element travels FROM as it enters. Default "up". */
  direction?: RevealDirection;
  /** Seconds before the animation starts. Default 0. */
  delay?: number;
  /** Animation duration in seconds (how fast it moves). Default 0.6. */
  duration?: number;
  /** Travel distance — number (px) or any CSS length ("0.5em", "2rem"). Default 24. */
  distance?: number | string;
  /** Easing curve. Default REVEAL_EASE (ease-out-expo). */
  ease?: Transition["ease"];
  /** Trigger when scrolled into view instead of on mount. Default false. */
  inView?: boolean;
  /** Fraction visible before an inView trigger fires (0–1). Default 0.3. */
  amount?: number;
  /** Replay every time it re-enters view (inView only). Default false. */
  repeat?: boolean;
  className?: string;
  style?: CSSProperties;
  /** Wrapper element. Default "div". */
  as?: "div" | "span" | "li";
}

/**
 * Reveal — slides/drops any content in from a chosen direction with a fade.
 * Reuse it on every element for a consistent entrance feel.
 *
 * Reduced motion: rely on an ancestor `<MotionConfig reducedMotion="user">`
 * (motion then keeps the fade but skips the movement). The marketing hero
 * already provides it.
 *
 * @example
 * <Reveal direction="left" delay={0.4} duration={0.7} distance={40}>
 *   <Button />
 * </Reveal>
 */
export function Reveal({
  children,
  direction = "up",
  delay = 0,
  duration = 0.6,
  distance = 24,
  ease = REVEAL_EASE,
  inView = false,
  amount = 0.3,
  repeat = false,
  className,
  style,
  as = "div",
}: RevealProps) {
  const MotionTag = m[as] as typeof m.div;

  const hidden = { opacity: 0, ...directionOffset(direction, distance) };
  const shown = { opacity: 1, x: 0, y: 0 };
  const transition: Transition = { duration, ease, delay };

  const trigger = inView
    ? { whileInView: shown, viewport: { once: !repeat, amount } }
    : { animate: shown };

  return (
    <MotionTag
      className={className}
      style={style}
      initial={hidden}
      transition={transition}
      {...trigger}
    >
      {children}
    </MotionTag>
  );
}
