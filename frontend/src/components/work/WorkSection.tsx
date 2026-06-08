"use client";

import { LazyMotion, domAnimation, MotionConfig } from "motion/react";
import { Reveal } from "@/components/motion/Reveal";
import { WhatWeDo } from "@/components/work/WhatWeDo";
import { ProjectsCarousel } from "@/components/work/ProjectsCarousel";

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
              <WhatWeDo layout="split" />

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
