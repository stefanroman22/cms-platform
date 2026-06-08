"use client";

import { LazyMotion, domAnimation, MotionConfig, m } from "motion/react";
import { Bot, Globe, AppWindow, Workflow, type LucideIcon } from "lucide-react";
import { Reveal, REVEAL_EASE } from "@/components/motion/Reveal";

interface Service {
  icon: LucideIcon;
  title: string;
  desc: string;
}

/** What Roman Technologies does — AI agents first, as requested. */
export const SERVICES: Service[] = [
  {
    icon: Bot,
    title: "We build AI agents",
    desc: "Autonomous agents that handle real work end-to-end — not just chatbots.",
  },
  {
    icon: Globe,
    title: "We develop websites",
    desc: "Fast, beautiful, SEO-ready sites that turn visitors into customers.",
  },
  {
    icon: AppWindow,
    title: "We build software applications",
    desc: "Web, mobile and desktop apps engineered to scale with you.",
  },
  {
    icon: Workflow,
    title: "We create automation workflows with AI",
    desc: "AI-driven workflows that run your busywork around the clock.",
  },
];

/** The intro copy (eyebrow + heading + lead) shared by both layouts. */
function Intro({ centered }: { centered: boolean }) {
  return (
    <Reveal inView amount={0.4} direction="up" distance={24}>
      <p className="mb-4 text-[0.78rem] font-semibold uppercase tracking-[0.34em] text-accent">
        What we build
      </p>
      <h2 className="font-display text-[clamp(2rem,5vw,3.25rem)] font-bold leading-[1.05] tracking-[-0.02em] text-text-primary">
        What do we do?
      </h2>
      <p
        className={`mt-5 text-[1.0625rem] leading-relaxed text-text-secondary ${
          centered ? "mx-auto max-w-xl" : "max-w-md"
        }`}
      >
        From a single landing page to full AI platforms — here&apos;s how we help ambitious
        companies ship.
      </p>
    </Reveal>
  );
}

/**
 * "What do we do" — reused on the home page (`layout="split"`, the left column
 * beside the projects carousel) and the About page (`layout="full"`, a
 * full-width section). `split` renders only the column content and relies on an
 * ancestor `LazyMotion`/`MotionConfig` (WorkSection provides them); `full` is a
 * self-contained section.
 */
export function WhatWeDo({ layout }: { layout: "split" | "full" }) {
  if (layout === "split") {
    return (
      <div>
        <Intro centered={false} />
        <ul className="mt-8 space-y-5">
          {SERVICES.map((s, i) => (
            <Reveal
              as="li"
              key={s.title}
              inView
              amount={0.6}
              direction="up"
              distance={16}
              delay={i * 0.06}
              className="flex gap-4"
            >
              <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl border border-accent/25 bg-accent/10 text-accent">
                <s.icon className="h-5 w-5" strokeWidth={2} aria-hidden="true" />
              </span>
              <div>
                <h3 className="font-display text-base font-semibold text-text-primary">
                  {s.title}
                </h3>
                <p className="mt-1 text-sm leading-relaxed text-text-secondary">{s.desc}</p>
              </div>
            </Reveal>
          ))}
        </ul>
      </div>
    );
  }

  // layout === "full"
  return (
    <LazyMotion features={domAnimation}>
      <MotionConfig reducedMotion="user">
        <section className="relative overflow-hidden bg-black px-6 py-16 lg:py-24">
          <div
            aria-hidden="true"
            className="pointer-events-none absolute left-1/2 top-24 h-[460px] w-[760px] -translate-x-1/2 rounded-full opacity-60 blur-3xl"
            style={{
              background: "radial-gradient(circle, rgba(201,169,97,0.10), rgba(201,169,97,0) 70%)",
            }}
          />
          <div className="relative z-10 mx-auto max-w-6xl">
            <div className="mx-auto max-w-3xl text-center">
              <Intro centered />
            </div>
            <div className="mt-12 grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-4">
              {SERVICES.map((s, i) => (
                <Reveal
                  key={s.title}
                  inView
                  amount={0.3}
                  direction="up"
                  distance={20}
                  delay={i * 0.08}
                >
                  <m.div
                    whileHover={{ y: -6 }}
                    transition={{ duration: 0.3, ease: REVEAL_EASE }}
                    className="group h-full rounded-2xl border border-border bg-surface/30 p-6 backdrop-blur-sm transition-colors hover:border-accent/40"
                  >
                    <m.span
                      className="flex h-12 w-12 items-center justify-center rounded-xl border border-accent/25 bg-accent/10 text-accent"
                      initial={{ scale: 0.6, opacity: 0 }}
                      whileInView={{ scale: 1, opacity: 1 }}
                      viewport={{ once: true, amount: 0.5 }}
                      transition={{ duration: 0.5, ease: REVEAL_EASE, delay: i * 0.08 + 0.15 }}
                    >
                      <s.icon className="h-6 w-6" strokeWidth={2} aria-hidden="true" />
                    </m.span>
                    <h3 className="mt-5 font-display text-lg font-semibold text-text-primary">
                      {s.title}
                    </h3>
                    <p className="mt-2 text-sm leading-relaxed text-text-secondary">{s.desc}</p>
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
