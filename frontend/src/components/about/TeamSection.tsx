"use client";

import { useTranslations } from "next-intl";
import { LazyMotion, domAnimation, MotionConfig, m } from "motion/react";
import { Reveal } from "@/components/motion/Reveal";
import { staggerFast } from "@/lib/animations";
import { TeamMemberCard } from "./TeamMemberCard";
import type { AboutContent } from "@/content/about";

export function TeamSection({ members }: { members: AboutContent["members"] }) {
  const t = useTranslations("about.team");
  const tm = useTranslations("about.team.members");
  return (
    <LazyMotion features={domAnimation}>
      <MotionConfig reducedMotion="user">
        <section className="px-6 pb-24 pt-14 sm:pb-32 sm:pt-20">
          <div className="mx-auto max-w-6xl">
            <div className="mx-auto max-w-2xl text-center">
              <Reveal inView amount={0.4}>
                <h2 className="font-display text-[clamp(1.8rem,4vw,2.75rem)] font-bold leading-[1.1] tracking-[-0.02em] text-text-primary">
                  {t("heading")}
                </h2>
              </Reveal>
              <Reveal inView amount={0.3} delay={0.1}>
                <p className="mt-4 text-[1rem] leading-relaxed text-text-secondary sm:text-[1.0625rem]">
                  {t("subheading")}
                </p>
              </Reveal>
            </div>

            <m.div
              variants={staggerFast}
              initial="hidden"
              whileInView="visible"
              viewport={{ once: true, amount: 0.15 }}
              className="mx-auto mt-12 grid max-w-4xl grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-3"
            >
              {members.map((member) => (
                <TeamMemberCard
                  key={member.id}
                  member={member}
                  role={tm(`${member.id}.role`)}
                  description={tm(`${member.id}.description`)}
                />
              ))}
            </m.div>
          </div>
        </section>
      </MotionConfig>
    </LazyMotion>
  );
}
