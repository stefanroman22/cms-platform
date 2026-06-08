"use client";

import { LazyMotion, domAnimation, MotionConfig } from "motion/react";
import { Reveal } from "@/components/motion/Reveal";
import type { AboutContent } from "@/content/about";

export function AboutHero({ hero }: { hero: AboutContent["hero"] }) {
  return (
    <LazyMotion features={domAnimation}>
      <MotionConfig reducedMotion="user">
        <section className="relative overflow-hidden px-6 pb-14 pt-14 sm:pb-20 sm:pt-24">
          {/* Brass ambient glow, echoing the home hero. */}
          <div
            aria-hidden="true"
            className="pointer-events-none absolute left-1/2 top-0 h-[420px] w-[680px] -translate-x-1/2 rounded-full opacity-50 blur-3xl"
            style={{
              background: "radial-gradient(circle, rgba(201,169,97,0.12), rgba(201,169,97,0) 70%)",
            }}
          />

          <div className="relative z-10 mx-auto max-w-3xl text-center">
            <Reveal>
              <p className="mb-5 text-[0.78rem] font-semibold uppercase tracking-[0.34em] text-accent">
                {hero.eyebrow}
              </p>
            </Reveal>

            <Reveal delay={0.1}>
              <h1 className="font-display text-[clamp(2.25rem,6vw,4rem)] font-bold leading-[1.04] tracking-[-0.02em] text-text-primary">
                {hero.title}
              </h1>
            </Reveal>

            <Reveal delay={0.2}>
              <p className="mx-auto mt-6 max-w-2xl text-[1.0625rem] leading-relaxed text-text-secondary sm:text-[1.15rem]">
                {hero.lead}
              </p>
            </Reveal>
          </div>
        </section>
      </MotionConfig>
    </LazyMotion>
  );
}
