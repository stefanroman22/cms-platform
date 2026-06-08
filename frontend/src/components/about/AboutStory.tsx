"use client";

import { LazyMotion, domAnimation, MotionConfig } from "motion/react";
import { Reveal } from "@/components/motion/Reveal";
import type { AboutContent } from "@/content/about";

export function AboutStory({ story }: { story: AboutContent["story"] }) {
  return (
    <LazyMotion features={domAnimation}>
      <MotionConfig reducedMotion="user">
        <section className="px-6 py-14 sm:py-20">
          <div className="mx-auto max-w-5xl">
            <div className="mx-auto max-w-3xl text-center">
              <Reveal inView amount={0.4}>
                <h2 className="font-display text-[clamp(1.8rem,4vw,2.75rem)] font-bold leading-[1.1] tracking-[-0.02em] text-text-primary">
                  {story.heading}
                </h2>
              </Reveal>

              {story.paragraphs.map((paragraph, i) => (
                <Reveal key={i} inView amount={0.3} delay={0.08 + i * 0.08}>
                  <p className="mt-5 text-[1rem] leading-relaxed text-text-secondary sm:text-[1.0625rem]">
                    {paragraph}
                  </p>
                </Reveal>
              ))}
            </div>
          </div>
        </section>
      </MotionConfig>
    </LazyMotion>
  );
}
