"use client";

import { LazyMotion, domAnimation, MotionConfig } from "motion/react";
import { Reveal } from "@/components/motion/Reveal";
import { TeamMemberCard } from "./TeamMemberCard";
import type { AboutContent } from "@/content/about";

export function TeamSection({ team }: { team: AboutContent["team"] }) {
  return (
    <LazyMotion features={domAnimation}>
      <MotionConfig reducedMotion="user">
        <section className="px-6 pb-24 pt-14 sm:pb-32 sm:pt-20">
          <div className="mx-auto max-w-6xl">
            <div className="mx-auto max-w-2xl text-center">
              <Reveal inView amount={0.4}>
                <h2 className="font-display text-[clamp(1.8rem,4vw,2.75rem)] font-bold leading-[1.1] tracking-[-0.02em] text-text-primary">
                  {team.heading}
                </h2>
              </Reveal>
              <Reveal inView amount={0.3} delay={0.1}>
                <p className="mt-4 text-[1rem] leading-relaxed text-text-secondary sm:text-[1.0625rem]">
                  {team.subheading}
                </p>
              </Reveal>
            </div>

            <div className="mx-auto mt-12 grid max-w-4xl grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-3">
              {team.members.map((member, i) => (
                <TeamMemberCard key={member.name} member={member} index={i} />
              ))}
            </div>
          </div>
        </section>
      </MotionConfig>
    </LazyMotion>
  );
}
