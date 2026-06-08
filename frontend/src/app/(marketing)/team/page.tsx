import type { Metadata } from "next";
import { about } from "@/content/about";
import { TeamSection } from "@/components/about/TeamSection";
import { ValuesSection } from "@/components/team/ValuesSection";

export const metadata: Metadata = {
  title: "Team — Roman Technologies",
  description: about.team.subheading,
};

/**
 * Team page: a short hero, the team grid (moved off the About page), and the
 * culture values. Team copy + members live in `src/content/about.json`.
 */
export default function TeamPage() {
  return (
    <div className="bg-black">
      {/* Hero */}
      <section className="relative overflow-hidden px-6 pb-8 pt-14 sm:pb-12 sm:pt-24">
        <div
          aria-hidden="true"
          className="pointer-events-none absolute left-1/2 top-0 h-[400px] w-[660px] -translate-x-1/2 rounded-full opacity-50 blur-3xl"
          style={{
            background: "radial-gradient(circle, rgba(201,169,97,0.12), rgba(201,169,97,0) 70%)",
          }}
        />
        <div className="animate-fade-down relative z-10 mx-auto max-w-2xl text-center">
          <p className="mb-5 text-[0.78rem] font-semibold uppercase tracking-[0.34em] text-accent">
            Our team
          </p>
          <h1 className="text-balance font-display text-[clamp(2.25rem,6vw,4rem)] font-bold leading-[1.04] tracking-[-0.02em] text-text-primary">
            A small, senior team that ships.
          </h1>
          <p className="mx-auto mt-6 max-w-xl text-[1.0625rem] leading-relaxed text-text-secondary sm:text-[1.15rem]">
            The people behind every build — engineering, security and strategy under one roof, and
            the principles that guide how we work.
          </p>
        </div>
      </section>

      <TeamSection team={about.team} />
      <ValuesSection />
    </div>
  );
}
