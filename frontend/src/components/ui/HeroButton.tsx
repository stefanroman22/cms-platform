"use client";

import * as React from "react";
import { m } from "motion/react";
import { cn } from "@/lib/utils";

type Variant = "primary" | "secondary";

const base =
  "inline-flex h-12 select-none items-center justify-center gap-2 rounded-[10px] px-6 text-[0.95rem] font-medium tracking-tight transition-colors duration-300 [transition-timing-function:var(--ease-out-expo)] outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-2 focus-visible:ring-offset-bg";

const variants: Record<Variant, string> = {
  primary: "bg-accent text-bg hover:bg-accent-muted",
  secondary:
    "border border-border bg-transparent text-text-primary hover:border-accent/50 hover:bg-white/5",
};

const hover = { scale: 1.02 };
const tap = { scale: 0.97 };
const spring = { type: "spring" as const, stiffness: 420, damping: 26 };

// Motion redefines drag/animation event handlers, so omit the native DOM
// versions to avoid the type clash when spreading button props.
type SafeButtonProps = Omit<
  React.ComponentPropsWithoutRef<"button">,
  | "onDrag"
  | "onDragStart"
  | "onDragEnd"
  | "onAnimationStart"
  | "onAnimationEnd"
  | "onAnimationIteration"
>;

type HeroButtonProps = {
  variant?: Variant;
  href?: string;
  className?: string;
  children: React.ReactNode;
} & SafeButtonProps &
  Pick<React.ComponentPropsWithoutRef<"a">, "target" | "rel">;

export function HeroButton({
  variant = "primary",
  href,
  className,
  children,
  target,
  rel,
  type,
  ...buttonProps
}: HeroButtonProps) {
  const cls = cn(base, variants[variant], className);

  if (href) {
    return (
      <m.a
        href={href}
        target={target}
        rel={rel}
        className={cls}
        whileHover={hover}
        whileTap={tap}
        transition={spring}
      >
        {children}
      </m.a>
    );
  }

  return (
    <m.button
      type={type ?? "button"}
      className={cls}
      whileHover={hover}
      whileTap={tap}
      transition={spring}
      {...buttonProps}
    >
      {children}
    </m.button>
  );
}
