"use client";

import { LazyMotion, domAnimation, MotionConfig, m } from "motion/react";
import { HeartHandshake, Users, KeyRound, Eye, type LucideIcon } from "lucide-react";
import { Reveal, REVEAL_EASE } from "@/components/motion/Reveal";

interface Value {
  icon: LucideIcon;
  title: string;
  description: string;
}

/** Culture values shown on the Team page. Local const mirrors WorkSection's SERVICES. */
const VALUES: Value[] = [
  {
    icon: HeartHandshake,
    title: "Client comes first",
    description:
      "We start from your goals, not our stack. Every decision is measured by what moves your business forward.",
  },
  {
    icon: Users,
    title: "Teamwork",
    description:
      "Engineering, security and strategy work as one team, so nothing falls between the cracks.",
  },
  {
    icon: KeyRound,
    title: "Ownership",
    description:
      "You own everything we build — code, data and roadmap. No lock-in, no black boxes.",
  },
  {
    icon: Eye,
    title: "Transparency",
    description:
      "Clear quotes, honest timelines, and a human who answers. You always know where things stand.",
  },
];

export function ValuesSection() {
  return (
    <LazyMotion features={domAnimation}>
      <MotionConfig reducedMotion="user">
        <section className="relative overflow-hidden px-6 pb-24 pt-8 sm:pb-32">
          {/* Brass ambient glow, echoing the other sections. */}
          <div
            aria-hidden="true"
            className="pointer-events-none absolute left-1/2 top-10 h-[420px] w-[720px] -translate-x-1/2 rounded-full opacity-50 blur-3xl"
            style={{
              background: "radial-gradient(circle, rgba(201,169,97,0.10), rgba(201,169,97,0) 70%)",
            }}
          />

          <div className="relative z-10 mx-auto max-w-6xl">
            <div className="mx-auto max-w-2xl text-center">
              <Reveal inView amount={0.4}>
                <p className="mb-4 text-[0.78rem] font-semibold uppercase tracking-[0.34em] text-accent">
                  What we stand for
                </p>
                <h2 className="font-display text-[clamp(1.8rem,4vw,2.75rem)] font-bold leading-[1.1] tracking-[-0.02em] text-text-primary">
                  Our values
                </h2>
              </Reveal>
            </div>

            <div className="mt-12 grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-4">
              {VALUES.map((value, i) => (
                <Reveal
                  key={value.title}
                  inView
                  amount={0.3}
                  direction="up"
                  distance={24}
                  delay={i * 0.1}
                >
                  <m.div
                    whileHover={{ y: -6 }}
                    transition={{ duration: 0.3, ease: REVEAL_EASE }}
                    className="group h-full rounded-2xl border border-border bg-surface/30 p-6 backdrop-blur-sm transition-colors hover:border-accent/40"
                  >
                    <m.span
                      initial={{ scale: 0.6, opacity: 0 }}
                      whileInView={{ scale: 1, opacity: 1 }}
                      viewport={{ once: true, amount: 0.5 }}
                      transition={{ duration: 0.5, ease: REVEAL_EASE, delay: i * 0.1 + 0.15 }}
                      className="flex h-12 w-12 items-center justify-center rounded-xl border border-accent/25 bg-accent/10 text-accent"
                    >
                      <value.icon className="h-6 w-6" strokeWidth={2} aria-hidden="true" />
                    </m.span>
                    <h3 className="mt-5 font-display text-lg font-semibold text-text-primary">
                      {value.title}
                    </h3>
                    <p className="mt-2 text-sm leading-relaxed text-text-secondary">
                      {value.description}
                    </p>
                  </m.div>
                </Reveal>
              ))}
            </div>
          </div>
        </section>
      </MotionConfig>
    </LazyMotion>
  );
}
