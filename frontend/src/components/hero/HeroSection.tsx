"use client";

import { LazyMotion, domAnimation, MotionConfig, m } from "motion/react";
import { ChevronDown } from "lucide-react";
import { HeroButton } from "@/components/ui/HeroButton";
import { TrustBadge } from "@/components/ui/TrustBadge";
import { scrollToHash } from "@/lib/scroll";

const TRUST = [
  "Human-reviewed code",
  "EU-based",
  "GDPR compliant",
  "Managed hosting included",
] as const;

const EYEBROW_TEXT = "Roman Technologies";
const HEADLINE_TEXT = "We make your idea or need come alive";
const SUBTEXT =
  "Custom websites, apps and AI workflows for ambitious companies — at a price that respects your budget.";

const EXPO = [0.16, 1, 0.3, 1] as const;

// One smooth fade per beat. Each beat starts a touch BEFORE the previous one
// finishes (STAGGER < FADE) so they overlap slightly and flow into each other
// instead of waiting on a hard gap.
//   1. eyebrow  — drops in FROM THE TOP
//   2. headline — drops in FROM THE TOP
//   3. subtext  — rises in FROM THE BOTTOM
//   4. buttons + trust — rise in together FROM THE BOTTOM
const FADE = 0.5; // per-beat fade duration
const STAGGER = 0.28; // delay between consecutive beat starts (< FADE → overlap)
const D_EYEBROW = 0.1;
const D_HEADLINE = D_EYEBROW + STAGGER;
const D_SUBTEXT = D_HEADLINE + STAGGER;
const D_ACTIONS = D_SUBTEXT + STAGGER;

// Shared "rise in from the bottom" fade for the lower groups.
function FadeIn({
  delay,
  className,
  children,
}: {
  delay: number;
  className?: string;
  children: React.ReactNode;
}) {
  return (
    <m.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: FADE, ease: EXPO, delay }}
      className={className}
    >
      {children}
    </m.div>
  );
}

export function HeroSection() {
  return (
    <LazyMotion features={domAnimation}>
      <MotionConfig reducedMotion="user">
        <section className="relative flex min-h-[calc(100dvh-4rem)] flex-col items-center justify-center overflow-hidden bg-black px-6 py-12 text-center">
          <m.p
            className="mb-5 text-[0.78rem] font-semibold uppercase tracking-[0.34em] text-accent"
            initial={{ opacity: 0, y: -18 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: FADE, ease: EXPO, delay: D_EYEBROW }}
          >
            {EYEBROW_TEXT}
          </m.p>

          <m.h1
            className="max-w-[20ch] font-display text-[clamp(2.5rem,7vw,6rem)] font-bold leading-[0.96] tracking-[-0.02em] text-text-primary"
            initial={{ opacity: 0, y: -28 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: FADE, ease: EXPO, delay: D_HEADLINE }}
          >
            {HEADLINE_TEXT}
          </m.h1>

          <m.p
            className="mt-6 max-w-[620px] text-[1.0625rem] leading-relaxed text-text-secondary sm:text-[1.125rem]"
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: FADE, ease: EXPO, delay: D_SUBTEXT }}
          >
            {SUBTEXT}
          </m.p>

          <FadeIn
            delay={D_ACTIONS}
            className="mt-9 flex flex-col items-center gap-3 sm:flex-row sm:gap-4"
          >
            <HeroButton variant="primary" onClick={() => scrollToHash("contact")}>
              Get a free preview
            </HeroButton>
            <HeroButton variant="secondary" onClick={() => scrollToHash("pricing")}>
              See pricing
            </HeroButton>
          </FadeIn>

          <FadeIn delay={D_ACTIONS} className="mt-4 text-[0.8125rem] text-text-tertiary">
            No call required to get pricing.
          </FadeIn>

          <FadeIn
            delay={D_ACTIONS}
            className="mt-8 flex flex-wrap items-center justify-center gap-x-3 gap-y-2 text-[0.8125rem]"
          >
            {TRUST.map((label, i) => (
              <span key={label} className="flex items-center gap-x-3">
                <TrustBadge label={label} />
                {i < TRUST.length - 1 && (
                  <span aria-hidden="true" className="text-text-tertiary/50">
                    ·
                  </span>
                )}
              </span>
            ))}
          </FadeIn>

          {/* Flashing scroll cue — sits just below the trust strip */}
          <m.div
            aria-hidden="true"
            initial={{ opacity: 0 }}
            animate={{ opacity: [0.35, 1, 0.35], y: [0, 6, 0] }}
            transition={{
              delay: D_ACTIONS + FADE + 0.2,
              duration: 1.6,
              repeat: Infinity,
              ease: "easeInOut",
            }}
            className="mt-2.5 text-accent"
          >
            <ChevronDown className="h-6 w-6" strokeWidth={2} />
          </m.div>
        </section>
      </MotionConfig>
    </LazyMotion>
  );
}
