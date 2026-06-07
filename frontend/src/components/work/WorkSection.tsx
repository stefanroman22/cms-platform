"use client";

import { LazyMotion, domAnimation, MotionConfig } from "motion/react";
import { Bot, Globe, AppWindow, Workflow } from "lucide-react";
import { Reveal } from "@/components/motion/Reveal";
import { ProjectsCarousel } from "@/components/work/ProjectsCarousel";

/** What Roman Technologies does — AI agents first, as requested. */
const SERVICES = [
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
] as const;

/**
 * Home "Projects" section: what we do (left) beside a live projects carousel
 * (right). Anchored as #projects for the nav + deep links. Each block fades in
 * on scroll, echoing the contact and pricing sections.
 */
export function WorkSection() {
  return (
    <section id="projects" className="relative overflow-hidden bg-black px-6 py-16 lg:py-24">
      {/* Subtle gold ambient glow, matching the surrounding sections. */}
      <div
        aria-hidden="true"
        className="pointer-events-none absolute left-1/2 top-24 h-[460px] w-[760px] -translate-x-1/2 rounded-full opacity-60 blur-3xl"
        style={{
          background: "radial-gradient(circle, rgba(201,169,97,0.10), rgba(201,169,97,0) 70%)",
        }}
      />

      <LazyMotion features={domAnimation}>
        <MotionConfig reducedMotion="user">
          <div className="relative z-10 mx-auto max-w-6xl">
            <div className="grid grid-cols-1 items-start gap-12 lg:grid-cols-2 lg:gap-16">
              {/* Left — features */}
              <div>
                <Reveal inView amount={0.4} direction="up" distance={24}>
                  <p className="mb-4 text-[0.78rem] font-semibold uppercase tracking-[0.34em] text-accent">
                    What we build
                  </p>
                  <h2 className="font-display text-[clamp(2rem,5vw,3.25rem)] font-bold leading-[1.05] tracking-[-0.02em] text-text-primary">
                    What do we do?
                  </h2>
                  <p className="mt-5 max-w-md text-[1.0625rem] leading-relaxed text-text-secondary">
                    From a single landing page to full AI platforms — here&apos;s how we help
                    ambitious companies ship.
                  </p>
                </Reveal>

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

              {/* Right — projects carousel */}
              <Reveal inView amount={0.15} direction="up" distance={28} delay={0.1}>
                <ProjectsCarousel />
              </Reveal>
            </div>
          </div>
        </MotionConfig>
      </LazyMotion>
    </section>
  );
}
